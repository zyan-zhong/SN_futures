# Managed Data Proxy MVP

The managed data proxy is the issuer-operated path for structured tin fundamentals when public sources are unstable or unavailable. Customers do not need CSV or Excel files. A private release or a license token can enable the client.

## Client endpoints

- `GET /api/sn/status`
- `GET /api/sn/fundamentals/latest`
- `GET /api/sn/fundamentals/history?symbol=SN&start=YYYY-MM-DD&end=YYYY-MM-DD`

The client sends `X-SN-License-Token`. Runtime status and diagnostics only show masked token values.

## Outputs

- `outputs/fundamentals/managed_fundamentals.json`
- `outputs/fundamentals/managed_proxy_status.json`
- `outputs/fundamentals/last_good_managed_fundamentals.json`

If refresh fails and a last-good file exists, the client uses cache with `from_cache=true`. Cache is not marked as fresh data.

## Guardrails

- No CSV or Excel required from customers.
- No fake spot, basis, inventory, LME, or term structure values.
- No model training, active promotion, customer prediction, or baseline generation.
- Non-SN rows are rejected rather than relabelled.
