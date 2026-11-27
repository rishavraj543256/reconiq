# Architecture

```mermaid
flowchart LR
  UI[React TypeScript dashboard] -->|JWT / REST| API[FastAPI API]
  API --> AUTH[RBAC and tenant context]
  API --> RECON[Strategy-based reconciliation]
  API --> ML[Isolation Forest detector]
  API --> DB[(PostgreSQL)]
  API --> REDIS[(Redis)]
  REDIS --> WORKER[Celery workers]
  WORKER --> RECON
  WORKER --> ML
```

The local demo defaults to SQLite so the core workflow can run without infrastructure. Docker Compose switches the same SQLAlchemy models to PostgreSQL and starts Redis/Celery. Matching is deterministic: records are sorted, candidates are indexed, tie-breaking uses confidence, amount difference, then stable IDs. Database constraints prevent a transaction from being consumed twice in one run.

## ER diagram

```mermaid
erDiagram
  ORGANIZATION ||--o{ MEMBERSHIP : has
  USER ||--o{ MEMBERSHIP : joins
  ORGANIZATION ||--o{ TRANSACTION : owns
  ORGANIZATION ||--o{ MATCHING_RULE : configures
  ORGANIZATION ||--o{ RECONCILIATION_RUN : executes
  RECONCILIATION_RUN ||--o{ TRANSACTION_MATCH : produces
  TRANSACTION ||--o{ TRANSACTION_MATCH : evidence
  TRANSACTION ||--o{ ANOMALY : signals
  ORGANIZATION ||--o{ AUDIT_EVENT : records
```

## Trust boundaries

Uploaded data enters through validation and tenant context. External LLM access is not enabled; deterministic explanations operate only on stored match evidence. Public demo data is synthetic and isolated in a dedicated tenant.
