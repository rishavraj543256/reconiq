# Security policy

Report vulnerabilities privately to `rishavraj543256@gmail.com`. Do not include real financial or client data in reports.

## Controls

- JWTs are short-lived and tenant/role claims are checked on protected routes.
- Every financial query is scoped by organization ID.
- Money uses fixed-precision `Decimal`/`NUMERIC(18,2)`.
- Upload size, type, schema and record values are validated; invalid rows are quarantined.
- Database uniqueness prevents duplicate source records and double matching inside a run.
- Audit events are append-only through the public API.
- Demo records are synthetic. Anomalies are signals, never assertions of fraud.
- Secrets are supplied by environment variables and `.env` is ignored.

Production deployments must replace `SECRET_KEY`, use HTTPS, restrict CORS, use managed secret storage, configure database backups, and place an edge rate limiter/WAF in front of the API.
