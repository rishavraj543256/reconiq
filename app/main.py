import csv
import hashlib
import io
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from app.anomaly import AnomalyDetector
from app.config import get_settings
from app.database import Base, engine, get_db
from app.demo import fingerprint, seed_demo
from app.models import Anomaly, AuditEvent, MatchStatus, MatchingRule, Membership, Organization, ReconciliationRun, Role, RunStatus, Transaction, TransactionMatch, TxKind, User
from app.reconciliation import Candidate, ReconciliationEngine, Rule
from app.schemas import Dashboard, LoginRequest, RegisterRequest, RuleIn, TokenPair, TransactionIn, TransactionOut
from app.security import create_token, decode_token, hash_password, verify_password

settings = get_settings()
app = FastAPI(title="ReconIQ API", version="1.0.0", docs_url="/docs", redoc_url="/redoc")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)


def current_context(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        return decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


def require_roles(*roles: Role):
    def dependency(ctx: dict = Depends(current_context)) -> dict:
        if ctx["role"] not in {role.value for role in roles}:
            raise HTTPException(403, "Insufficient role")
        return ctx
    return dependency


def audit(db: Session, ctx: dict, event: str, entity: str, entity_id: str | None = None, payload: dict | None = None):
    db.add(AuditEvent(organization_id=ctx["org"], user_id=ctx.get("sub"), event_type=event, entity_type=entity, entity_id=entity_id, payload=payload or {}))


@app.get("/health")
def health():
    return {"status": "healthy", "service": "reconiq-api"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ready"}


@app.post("/api/v1/auth/register", response_model=TokenPair, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email already registered")
    slug = re.sub(r"[^a-z0-9]+", "-", body.organization_name.lower()).strip("-")
    if db.scalar(select(Organization).where(Organization.slug == slug)):
        slug = f"{slug}-{hashlib.sha1(body.email.encode()).hexdigest()[:6]}"
    org = Organization(name=body.organization_name, slug=slug)
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name)
    db.add_all([org, user]); db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.admin))
    db.commit()
    return TokenPair(access_token=create_token(user.id, org.id, Role.admin.value, "access", settings.access_token_minutes), refresh_token=create_token(user.id, org.id, Role.admin.value, "refresh", 60 * 24 * 7))


@app.post("/api/v1/auth/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
    if not membership:
        raise HTTPException(403, "No organization membership")
    return TokenPair(access_token=create_token(user.id, membership.organization_id, membership.role.value, "access", settings.access_token_minutes), refresh_token=create_token(user.id, membership.organization_id, membership.role.value, "refresh", 60 * 24 * 7))


@app.post("/api/v1/demo/session", response_model=TokenPair)
def demo_session(db: Session = Depends(get_db)):
    org = db.scalar(select(Organization).where(Organization.slug == "public-demo"))
    if not org:
        org = Organization(name="ReconIQ Public Demo", slug="public-demo", is_demo=True); db.add(org); db.flush()
        user = User(email="demo@reconiq.local", password_hash=hash_password("disabled-demo-password"), full_name="Demo Analyst"); db.add(user); db.flush()
        db.add(Membership(organization_id=org.id, user_id=user.id, role=Role.analyst)); db.commit(); seed_demo(db, org)
    membership = db.scalar(select(Membership).where(Membership.organization_id == org.id))
    return TokenPair(access_token=create_token(membership.user_id, org.id, membership.role.value, "access", 60), refresh_token=create_token(membership.user_id, org.id, membership.role.value, "refresh", 60))


@app.post("/api/v1/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(body: TransactionIn, ctx: dict = Depends(require_roles(Role.admin, Role.analyst)), db: Session = Depends(get_db)):
    fp = fingerprint(ctx["org"], body.kind.value, body.external_id)
    if db.scalar(select(Transaction).where(Transaction.organization_id == ctx["org"], Transaction.source_fingerprint == fp)):
        raise HTTPException(409, "Duplicate transaction")
    tx = Transaction(organization_id=ctx["org"], source_fingerprint=fp, **body.model_dump())
    db.add(tx); db.flush(); audit(db, ctx, "transaction.created", "transaction", tx.id); db.commit(); db.refresh(tx)
    return tx


@app.get("/api/v1/transactions", response_model=list[TransactionOut])
def list_transactions(kind: TxKind | None = None, offset: int = 0, limit: int = 100, ctx: dict = Depends(current_context), db: Session = Depends(get_db)):
    query = select(Transaction).where(Transaction.organization_id == ctx["org"])
    if kind: query = query.where(Transaction.kind == kind)
    return list(db.scalars(query.order_by(Transaction.transaction_date.desc()).offset(offset).limit(min(limit, 500))))


@app.post("/api/v1/uploads/csv")
async def upload_csv(file: UploadFile = File(...), ctx: dict = Depends(require_roles(Role.admin, Role.analyst)), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Only CSV is accepted by this endpoint")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, "File exceeds configured limit")
    try: rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    except UnicodeDecodeError as exc: raise HTTPException(422, "CSV must be UTF-8") from exc
    required = {"kind", "external_id", "amount", "transaction_date"}
    if not rows or not required.issubset(rows[0]): raise HTTPException(422, f"Required columns: {sorted(required)}")
    imported, quarantined = 0, []
    for index, row in enumerate(rows, start=2):
        try:
            body = TransactionIn(kind=row["kind"], external_id=row["external_id"], reference=row.get("reference", ""), vendor=row.get("vendor", ""), amount=Decimal(row["amount"]), currency=row.get("currency", "USD"), transaction_date=row["transaction_date"])
            fp = fingerprint(ctx["org"], body.kind.value, body.external_id)
            if db.scalar(select(Transaction.id).where(Transaction.organization_id == ctx["org"], Transaction.source_fingerprint == fp)): raise ValueError("duplicate")
            db.add(Transaction(organization_id=ctx["org"], source_fingerprint=fp, raw_data={"filename": file.filename, "row": index}, **body.model_dump())); imported += 1
        except (ValueError, InvalidOperation) as exc: quarantined.append({"row": index, "reason": str(exc)})
    audit(db, ctx, "upload.processed", "uploaded_file", payload={"filename": file.filename, "imported": imported, "quarantined": len(quarantined)}); db.commit()
    return {"imported": imported, "quarantined": quarantined[:100]}


@app.post("/api/v1/rules", status_code=201)
def create_rule(body: RuleIn, ctx: dict = Depends(require_roles(Role.admin, Role.analyst)), db: Session = Depends(get_db)):
    rule = MatchingRule(organization_id=ctx["org"], **body.model_dump()); db.add(rule); db.flush(); audit(db, ctx, "rule.created", "matching_rule", rule.id); db.commit()
    return {"id": rule.id, **body.model_dump(mode="json")}


@app.get("/api/v1/rules")
def list_rules(ctx: dict = Depends(current_context), db: Session = Depends(get_db)):
    return [{"id": x.id, "name": x.name, "amount_tolerance": str(x.amount_tolerance), "date_tolerance_days": x.date_tolerance_days, "fuzzy_threshold": x.fuzzy_threshold, "auto_approve_threshold": x.auto_approve_threshold} for x in db.scalars(select(MatchingRule).where(MatchingRule.organization_id == ctx["org"]).order_by(MatchingRule.priority))]


@app.post("/api/v1/reconciliations/run")
def run_reconciliation(rule_id: str | None = None, ctx: dict = Depends(require_roles(Role.admin, Role.analyst)), db: Session = Depends(get_db)):
    rule_model = db.scalar(select(MatchingRule).where(MatchingRule.organization_id == ctx["org"], MatchingRule.id == rule_id)) if rule_id else db.scalar(select(MatchingRule).where(MatchingRule.organization_id == ctx["org"], MatchingRule.is_active.is_(True)).order_by(MatchingRule.priority))
    if not rule_model: raise HTTPException(422, "Create a matching rule first")
    run = ReconciliationRun(organization_id=ctx["org"], status=RunStatus.running, started_at=datetime.now(timezone.utc)); db.add(run); db.flush()
    left_rows = list(db.scalars(select(Transaction).where(Transaction.organization_id == ctx["org"], Transaction.kind == TxKind.invoice, Transaction.is_quarantined.is_(False))))
    right_rows = list(db.scalars(select(Transaction).where(Transaction.organization_id == ctx["org"], Transaction.kind == TxKind.bank, Transaction.is_quarantined.is_(False))))
    candidate = lambda x: Candidate(x.id, Decimal(x.amount), x.transaction_date, x.reference, x.vendor)
    rule = Rule(Decimal(rule_model.amount_tolerance), rule_model.date_tolerance_days, rule_model.fuzzy_threshold, rule_model.auto_approve_threshold)
    started = time.perf_counter(); results = ReconciliationEngine().reconcile([candidate(x) for x in left_rows], [candidate(x) for x in right_rows], rule)
    for result in results:
        db.add(TransactionMatch(organization_id=ctx["org"], run_id=run.id, left_transaction_id=result.left_id, right_transaction_id=result.right_id, status=MatchStatus(result.status), confidence=result.confidence, amount_difference=result.amount_difference, reasoning=result.reasoning, approved=result.confidence >= rule.auto_approve_threshold))
    run.status = RunStatus.completed; run.total_records = len(left_rows); run.matched_records = len(results); run.completed_at = datetime.now(timezone.utc); run.duration_ms = int((time.perf_counter() - started) * 1000)
    audit(db, ctx, "reconciliation.completed", "reconciliation_run", run.id, {"matched": len(results), "total": len(left_rows)}); db.commit()
    return {"id": run.id, "status": run.status.value, "total_records": run.total_records, "matched_records": run.matched_records, "duration_ms": run.duration_ms}


@app.post("/api/v1/anomalies/detect")
def detect_anomalies(ctx: dict = Depends(require_roles(Role.admin, Role.analyst)), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Transaction).where(Transaction.organization_id == ctx["org"], Transaction.kind == TxKind.bank)))
    db.execute(delete(Anomaly).where(Anomaly.organization_id == ctx["org"]))
    detected = AnomalyDetector().detect([{"id": x.id, "amount": x.amount, "transaction_date": x.transaction_date} for x in rows])
    for x in detected: db.add(Anomaly(organization_id=ctx["org"], **x))
    audit(db, ctx, "anomaly_detection.completed", "anomaly", payload={"count": len(detected)}); db.commit()
    return {"detected": len(detected), "items": detected}


@app.get("/api/v1/dashboard", response_model=Dashboard)
def dashboard(ctx: dict = Depends(current_context), db: Session = Depends(get_db)):
    org = ctx["org"]
    total = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.organization_id == org)) or 0
    latest = db.scalar(select(ReconciliationRun).where(ReconciliationRun.organization_id == org).order_by(ReconciliationRun.started_at.desc()))
    matched = latest.matched_records if latest else 0
    diffs = db.scalar(select(func.coalesce(func.sum(TransactionMatch.amount_difference), 0)).where(TransactionMatch.organization_id == org)) or Decimal("0")
    anomaly_count = db.scalar(select(func.count()).select_from(Anomaly).where(Anomaly.organization_id == org)) or 0
    pending = db.scalar(select(func.count()).select_from(TransactionMatch).where(TransactionMatch.organization_id == org, TransactionMatch.approved.is_(False))) or 0
    runs = list(db.scalars(select(ReconciliationRun).where(ReconciliationRun.organization_id == org).order_by(ReconciliationRun.started_at.desc()).limit(5)))
    return Dashboard(total_transactions=total, matched_transactions=matched, match_percentage=round((matched / latest.total_records * 100) if latest and latest.total_records else 0, 2), unmatched_transactions=max(0, (latest.total_records if latest else 0) - matched), discrepancy_amount=diffs, anomalies=anomaly_count, pending_approvals=pending, recent_runs=[{"id": x.id, "status": x.status.value, "matched": x.matched_records, "total": x.total_records, "duration_ms": x.duration_ms} for x in runs])


@app.get("/api/v1/assistant/explain")
def explain(run_id: str, ctx: dict = Depends(current_context), db: Session = Depends(get_db)):
    run = db.scalar(select(ReconciliationRun).where(ReconciliationRun.id == run_id, ReconciliationRun.organization_id == ctx["org"]))
    if not run: raise HTTPException(404, "Run not found")
    mismatches = db.scalar(select(func.count()).select_from(TransactionMatch).where(TransactionMatch.run_id == run.id, TransactionMatch.status != MatchStatus.fully_matched)) or 0
    return {"mode": "deterministic", "answer": f"Run {run.id[:8]} matched {run.matched_records} of {run.total_records} invoice records. {mismatches} candidate matches require discrepancy review. Explanations are derived from amount, date, and reference evidence stored with each match."}


@app.get("/api/v1/reports/matches.csv")
def export_matches(ctx: dict = Depends(current_context), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(TransactionMatch).where(TransactionMatch.organization_id == ctx["org"])))
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["match_id", "run_id", "status", "confidence", "amount_difference"])
    for x in rows: writer.writerow([x.id, x.run_id, x.status.value, x.confidence, x.amount_difference])
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=reconiq-matches.csv"})


@app.get("/api/v1/audit-events")
def audit_events(limit: int = 100, ctx: dict = Depends(require_roles(Role.admin, Role.auditor)), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == ctx["org"]).order_by(AuditEvent.created_at.desc()).limit(min(limit, 500)))
    return [{"id": x.id, "event_type": x.event_type, "entity_type": x.entity_type, "entity_id": x.entity_id, "payload": x.payload, "created_at": x.created_at} for x in rows]
