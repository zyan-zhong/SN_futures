# System Stability Audit

The stability audit checks deterministic P0/P1 operational issues before model work continues:

- backend process lifecycle and shutdown markers
- data watermark consistency after refresh/build/training/backtest tasks
- cache invalidation after task completion
- sample data boundary and real-data precedence
- task UI stability and no global loading blocker
- all-terminal-API smoke coverage
- full TXT report availability

The audit deliberately does not write `active_model.json`, does not generate customer prediction cards, and does not lower promotion gates.

Run targeted checks:

```powershell
pytest -q tests/test_system_stability_audit.py tests/test_backend_process_lifecycle.py tests/test_data_freshness_consistency.py
```
