# ReconIQ

ReconIQ is an open-source financial reconciliation platform for finance teams, analysts, and auditors. It imports tenant-scoped financial records, deterministically matches invoices and payments, preserves evidence for every decision, and applies Isolation Forest to surface unusual payment patterns. Demo data is synthetic; detected anomalies are not claims of fraud.

## What works

- Registration/login, JWT access and refresh tokens, organization isolation, and Admin/Analyst/Auditor/Viewer roles
- Fixed-precision transaction storage, duplicate prevention, CSV validation and invalid-row quarantine
- Exact, normalized-reference, amount/date-tolerance and fuzzy matching with weighted confidence
- Stable candidate ordering, database-enforced no-double-match constraints, and one-to-many aggregate strategy
- Configurable matching rules and deterministic evidence for each result
- Real scikit-learn Isolation Forest with severity and plain-language context
- Grounded deterministic discrepancy summaries without sending data to an LLM
- Calculated dashboard metrics, CSV reports, append-only audit events, responsive dark/light dashboard
- PostgreSQL, Redis and Celery deployment topology with SQLite local-demo fallback

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:5173`, select **Try Live Demo**, run reconciliation, then run anomaly detection. API docs: `http://localhost:8000/docs`.

For a Python-only local run:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[test]"
uvicorn app.main:app --reload
```

## System design

See [architecture and ER diagrams](docs/architecture.md), [API guide](docs/api.md), and [security policy](SECURITY.md).

## Tests and benchmarks

```bash
pytest --cov=app --cov-report=term-missing
python benchmarks/run.py
```

Measured locally on 27 November 2026 with Python 3.14.3 on the development machine (synthetic exact-match ground truth; time includes matching, not dataset generation):

| Records per side | Duration | Accuracy | False matches | Peak traced memory |
|---:|---:|---:|---:|---:|
| 1,000 | 0.3042 s | 100% | 0 | 1.35 MB |
| 10,000 | 2.6732 s | 100% | 0 | 12.80 MB |
| 100,000 | 35.4785 s | 100% | 0 | 127.48 MB |

Raw output is committed in `benchmark-results.json`. These measurements describe the generated exact-reference workload only; they are not a promise for fuzzy real-world datasets. The generated datasets contain no client data.

## Deployment

The frontend can deploy to Netlify/Vercel with `VITE_API_URL`. The API/worker require a container host plus PostgreSQL and Redis. Required production settings: a random `SECRET_KEY`, restricted `CORS_ORIGINS`, `DATABASE_URL`, and `REDIS_URL`. No paid service is provisioned by this repository.

## License

MIT © 2026 Rishav Raj.
