# Task Queue Design

## Goal

Long-running work must not block HTTP requests. Refresh, feature-store build, training dataset build, candidate training, institutional validation, research backtest, and learning scheduler runs now start through a backend task queue and return a `task_id` immediately.

## API

- `POST /api/terminal/tasks/start`
- `GET /api/terminal/tasks/status?id=...`
- `GET /api/terminal/tasks/recent`
- `POST /api/terminal/tasks/cancel?id=...`

## Task Kinds

- `refresh_market`
- `refresh_news`
- `refresh_cross_market`
- `refresh_all`
- `build_feature_store`
- `build_training_dataset`
- `train_candidate`
- `run_validation`
- `run_research_backtest`
- `run_learning_scheduler`

## Rules

- Same-kind tasks are deduped while queued or running.
- Task state is persisted under `outputs/tasks/<task_id>.json`.
- Logs and error messages are sanitized before writing.
- Start APIs return immediately with `task_id`, `kind`, `status`, `progress`, and `message_zh`.
- Frontend polls task status and refreshes relevant pages after completion.
- The queue never writes `active_model.json` by itself and never generates customer predictions.

## Frontend

`TaskMonitorPanel` shows current task status, progress, sanitized error summary, recent tasks, and cancellation controls. It is designed for refresh, training, validation, backtest, and scheduler tasks.
