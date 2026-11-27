# API guide

Interactive OpenAPI is available at `/docs`; ReDoc is at `/redoc`.

1. `POST /api/v1/demo/session` returns a one-hour demo token.
2. Send `Authorization: Bearer <access_token>`.
3. `POST /api/v1/reconciliations/run` runs real matching.
4. `POST /api/v1/anomalies/detect` trains and executes Isolation Forest on tenant payments.
5. `GET /api/v1/dashboard` returns calculated metrics.
6. `GET /api/v1/reports/matches.csv` exports match evidence.

CSV upload columns: `kind,external_id,reference,vendor,amount,currency,transaction_date`. Dates use ISO `YYYY-MM-DD`; kind is `bank`, `invoice`, or `erp`.
