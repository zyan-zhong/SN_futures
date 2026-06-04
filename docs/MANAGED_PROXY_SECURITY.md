# Managed Proxy Security

The managed proxy token is stored only in the local user configuration or private release bundle import path. It is never written to frontend dist, logs, diagnostics bundles, cache URLs, or release logs.

Runtime requests use the `X-SN-License-Token` header. Provider status, key diagnostics, and frontend views return only masked token/source/configured fields.

The mock server in `src/sn_futures/devtools/mock_managed_proxy.py` is for local tests only. Mock data is labelled as sample data and must not be used for promotion to active models.
