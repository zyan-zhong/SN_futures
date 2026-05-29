from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


ModelStatus = Literal["candidate", "paper_active", "active", "degraded", "retired"]


@dataclass
class ModelRecord:
    model_id: str
    model_type: str
    horizon: str
    feature_set_version: str
    label_version: str
    train_period: dict[str, str]
    validation_period: dict[str, str]
    test_period: dict[str, str]
    created_at: str
    status: ModelStatus
    metrics: dict[str, Any]
    artifact_path: str
    promotion_result: dict[str, Any] = field(default_factory=dict)
    failure_reasons: list[str] = field(default_factory=list)
    data_quality_snapshot: dict[str, Any] = field(default_factory=dict)
    backtest_config_hash: str = ""
    feature_columns: list[str] = field(default_factory=list)
    label_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelRecord":
        return cls(
            model_id=str(payload.get("model_id", "")),
            model_type=str(payload.get("model_type", "")),
            horizon=str(payload.get("horizon", "")),
            feature_set_version=str(payload.get("feature_set_version", "")),
            label_version=str(payload.get("label_version", "")),
            train_period=dict(payload.get("train_period") or {}),
            validation_period=dict(payload.get("validation_period") or {}),
            test_period=dict(payload.get("test_period") or {}),
            created_at=str(payload.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            status=str(payload.get("status", "candidate")),  # type: ignore[arg-type]
            metrics=dict(payload.get("metrics") or {}),
            artifact_path=str(payload.get("artifact_path", "")),
            promotion_result=dict(payload.get("promotion_result") or {}),
            failure_reasons=list(payload.get("failure_reasons") or []),
            data_quality_snapshot=dict(payload.get("data_quality_snapshot") or {}),
            backtest_config_hash=str(payload.get("backtest_config_hash", "")),
            feature_columns=[str(col) for col in payload.get("feature_columns", [])],
            label_columns=[str(col) for col in payload.get("label_columns", [])],
        )


class ModelRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, ModelRecord] = {}
        self.load_model_metadata()

    def load_model_metadata(self) -> list[ModelRecord]:
        if not self.path.exists():
            self._records = {}
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        rows = payload.get("models", []) if isinstance(payload, dict) else []
        self._records = {
            row.model_id: row
            for row in (ModelRecord.from_dict(item) for item in rows if isinstance(item, dict))
            if row.model_id
        }
        return list(self._records.values())

    def save_model_metadata(self) -> None:
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "models": [record.to_dict() for record in sorted(self._records.values(), key=lambda item: (item.horizon, item.created_at, item.model_id))],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def register_candidate(self, record: ModelRecord | dict[str, Any]) -> ModelRecord:
        model = record if isinstance(record, ModelRecord) else ModelRecord.from_dict(record)
        model.status = "candidate"
        self._records[model.model_id] = model
        self.save_model_metadata()
        return model

    def get_active_model(self, horizon: str) -> ModelRecord | None:
        active = [
            record
            for record in self._records.values()
            if record.horizon == horizon and record.status in {"active", "paper_active"}
        ]
        if not active:
            return None
        return sorted(active, key=lambda item: item.created_at)[-1]

    def list_candidates(self, horizon: str | None = None) -> list[ModelRecord]:
        rows = [record for record in self._records.values() if record.status == "candidate"]
        if horizon is not None:
            rows = [record for record in rows if record.horizon == horizon]
        return sorted(rows, key=lambda item: item.created_at)

    def promote_model(self, model_id: str, *, promotion_result: dict[str, Any] | None = None, paper: bool = False) -> ModelRecord:
        if model_id not in self._records:
            raise KeyError(f"模型不存在：{model_id}")
        model = self._records[model_id]
        for record in self._records.values():
            if record.horizon == model.horizon and record.status == "active":
                record.status = "retired"
        model.status = "paper_active" if paper else "active"
        model.promotion_result = promotion_result or {"passed": True, "result": "candidate_promoted"}
        model.failure_reasons = []
        self.save_model_metadata()
        return model

    def degrade_model(self, model_id: str, reasons: list[str] | None = None) -> ModelRecord:
        if model_id not in self._records:
            raise KeyError(f"模型不存在：{model_id}")
        model = self._records[model_id]
        model.status = "degraded"
        model.failure_reasons = list(reasons or ["模型表现退化，已降级为研究观察模式"])
        self.save_model_metadata()
        return model

    def retire_model(self, model_id: str, reasons: list[str] | None = None) -> ModelRecord:
        if model_id not in self._records:
            raise KeyError(f"模型不存在：{model_id}")
        model = self._records[model_id]
        model.status = "retired"
        model.failure_reasons = list(reasons or model.failure_reasons)
        self.save_model_metadata()
        return model

    def records(self) -> list[ModelRecord]:
        return list(self._records.values())


def make_model_record(
    *,
    model_id: str,
    horizon: str,
    metrics: dict[str, Any],
    status: ModelStatus = "candidate",
    model_type: str = "direction_first",
    feature_set_version: str = "unknown_features",
    label_version: str = "unknown_labels",
    artifact_path: str = "",
    train_period: dict[str, str] | None = None,
    validation_period: dict[str, str] | None = None,
    test_period: dict[str, str] | None = None,
    data_quality_snapshot: dict[str, Any] | None = None,
    feature_columns: list[str] | None = None,
    label_columns: list[str] | None = None,
    backtest_config_hash: str = "",
) -> ModelRecord:
    return ModelRecord(
        model_id=model_id,
        model_type=model_type,
        horizon=horizon,
        feature_set_version=feature_set_version,
        label_version=label_version,
        train_period=train_period or {},
        validation_period=validation_period or {},
        test_period=test_period or {},
        created_at=datetime.now().isoformat(timespec="seconds"),
        status=status,
        metrics=metrics,
        artifact_path=artifact_path,
        data_quality_snapshot=data_quality_snapshot or {},
        backtest_config_hash=backtest_config_hash,
        feature_columns=feature_columns or [],
        label_columns=label_columns or [],
    )
