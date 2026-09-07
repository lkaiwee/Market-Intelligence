# Step 7.3 — Custom Stock Universe

Adds a persistent custom-stock registry.

New GUI page:

`http://localhost:3000/universe`

You can add any Yahoo Finance-supported ticker and choose:
- include in daily screening
- include in earnings monitoring
- earnings impact score (1-10)

If Screening is enabled, the stock is included in:
- `POST /api/screener/refresh`
- the Tue-Sat 07:35 SGT automatic screener job

If Earnings is enabled, the stock is included in:
- `POST /api/earnings/refresh`
- the Sunday earnings update

New PostgreSQL table:

`custom_universe_stocks`

New API endpoints:
- `GET /api/universe/stocks`
- `POST /api/universe/stocks`
- `PUT /api/universe/stocks/{ticker}`
- `DELETE /api/universe/stocks/{ticker}`

Example POST body:

```json
{
  "ticker": "SNDK",
  "screening_enabled": true,
  "earnings_enabled": true,
  "earnings_impact_score": 8
}
```

Apply on top of Step 7.2.

Restart backend and frontend after copying the patch.

API version: `0.7.3`
