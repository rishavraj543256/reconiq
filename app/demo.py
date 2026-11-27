import hashlib
import random
from datetime import date, timedelta
from decimal import Decimal
from app.models import MatchingRule, Organization, Transaction, TxKind


def fingerprint(org_id: str, kind: str, external_id: str) -> str:
    return hashlib.sha256(f"{org_id}:{kind}:{external_id}".encode()).hexdigest()


def seed_demo(db, org: Organization, count: int = 80) -> None:
    rng = random.Random(42)
    vendors = ["Northstar Logistics", "Apex Supplies", "Vertex Cloud", "BlueRiver Energy", "Metro Office"]
    base = date.today() - timedelta(days=90)
    for i in range(count):
        amount = Decimal(str(round(rng.uniform(75, 8500), 2)))
        vendor = vendors[i % len(vendors)]
        reference = f"INV-{2026000 + i}"
        invoice_date = base + timedelta(days=i % 75)
        invoice = Transaction(organization_id=org.id, kind=TxKind.invoice, external_id=f"I-{i:05d}", reference=reference,
            vendor=vendor, amount=amount, currency="USD", transaction_date=invoice_date,
            source_fingerprint=fingerprint(org.id, "invoice", f"I-{i:05d}"), raw_data={"synthetic": True})
        db.add(invoice)
        if i % 9 != 0:
            paid_amount = amount + (Decimal("3.50") if i % 13 == 0 else Decimal("0"))
            paid_date = invoice_date + timedelta(days=rng.randint(0, 4))
            bank = Transaction(organization_id=org.id, kind=TxKind.bank, external_id=f"B-{i:05d}", reference=reference if i % 7 else reference.replace("-", ""),
                vendor=vendor, amount=paid_amount, currency="USD", transaction_date=paid_date,
                source_fingerprint=fingerprint(org.id, "bank", f"B-{i:05d}"), raw_data={"synthetic": True})
            db.add(bank)
    # deterministic large outlier for real anomaly detection
    db.add(Transaction(organization_id=org.id, kind=TxKind.bank, external_id="B-OUTLIER", reference="SPECIAL-REVIEW", vendor="Unknown Vendor",
        amount=Decimal("125000.00"), currency="USD", transaction_date=date.today(), source_fingerprint=fingerprint(org.id, "bank", "B-OUTLIER"), raw_data={"synthetic": True}))
    db.add(MatchingRule(organization_id=org.id, name="Default operational rule", amount_tolerance=Decimal("5.00"), date_tolerance_days=5, fuzzy_threshold=82, auto_approve_threshold=92))
    db.commit()
