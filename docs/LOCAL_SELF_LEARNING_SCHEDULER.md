# Local Self-Learning Scheduler

## Purpose

The local self-learning scheduler automates research-only iteration on the installed terminal:

- refresh market data, news, and cross-market backfill
- build Feature Store v5
- train candidate v5 research models
- run institutional validation
- run promotion dry-run only
- archive artifacts for review
- record degradation checks and failures

It never publishes an active model and never generates customer predictions.

## Tasks

| Task | Cadence | Action |
| --- | --- | --- |
| `daily_market_refresh` | daily | Refresh real market data. |
| `daily_news_refresh` | daily | Refresh NewsAPI and event relevance inputs. |
| `daily_cross_market_backfill` | daily | Run Alpha/backfill cross-market refresh. |
| `weekly_feature_store_build` | weekly | Build Feature Store v5. |
| `weekly_candidate_training` | weekly | Run candidate v5 research training. |
| `weekly_institutional_validation` | weekly | Run institutional validation in dry-run context. |
| `monthly_promotion_dry_run` | monthly | Run promotion gate with `dry_run=true`. |
| `artifact_archive` | each run | Archive manifests, validation reports, OOF summaries, and research outputs. |
| `degradation_check` | each run | Record research-only degradation status and next actions. |

## API

- `GET /api/terminal/learning-scheduler/status`
- `POST /api/terminal/learning-scheduler/run`
- `POST /api/terminal/learning-scheduler/pause`
- `POST /api/terminal/learning-scheduler/resume`

`run` accepts optional JSON:

```json
{
  "force": true,
  "manual": true,
  "tasks": ["daily_market_refresh", "monthly_promotion_dry_run"]
}
```

## Safety Rules

- `promote_candidate` is called only with `dry_run=true`.
- The scheduler response always includes `active_updated=false`.
- The scheduler response always includes `customer_prediction_generated=false`.
- If promotion dry-run passes, status becomes `manual_approval_required=true`; an operator must explicitly approve active publication outside this scheduler.
- Paused scheduler runs do nothing unless `force=true`.

## Artifacts

Status and history are written to:

- `outputs/learning_scheduler/learning_scheduler_status.json`
- `outputs/learning_scheduler/learning_scheduler_history.json`

Research archives are written by the existing research artifact center under:

- `outputs/research_runs/<run_id>/`

## Frontend

The Model Research page shows:

- scheduler status
- recent run time
- next task
- failure reasons
- artifact path
- manual approval state
- pause, resume, and manual run controls

The page explicitly states that the scheduler does not automatically publish `active_model.json`.
