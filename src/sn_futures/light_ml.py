from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


def _as_2d(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return arr


class StandardScalerLite:
    def __init__(self) -> None:
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def fit(self, x: np.ndarray) -> "StandardScalerLite":
        arr = _as_2d(x)
        self.mean_ = np.nanmean(arr, axis=0)
        self.scale_ = np.nanstd(arr, axis=0)
        self.scale_[~np.isfinite(self.scale_) | (self.scale_ == 0)] = 1.0
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise ValueError("Scaler must be fitted before transform.")
        arr = _as_2d(x)
        return (arr - self.mean_) / self.scale_

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)


class LinearRegressionLite:
    def __init__(self, alpha: float = 0.0) -> None:
        self.alpha = alpha
        self.coef_: np.ndarray | None = None
        self.intercept_: float = 0.0

    def fit(self, x: np.ndarray, y: np.ndarray) -> "LinearRegressionLite":
        x_arr = _as_2d(x)
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        ones = np.ones((len(x_arr), 1), dtype=float)
        design = np.hstack([ones, x_arr])
        penalty = np.eye(design.shape[1], dtype=float) * self.alpha
        penalty[0, 0] = 0.0
        beta = np.linalg.pinv(design.T @ design + penalty) @ design.T @ y_arr
        self.intercept_ = float(beta[0])
        self.coef_ = beta[1:]
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise ValueError("Model must be fitted before predict.")
        x_arr = _as_2d(x)
        return x_arr @ self.coef_ + self.intercept_

    def score(self, x: np.ndarray, y: np.ndarray) -> float:
        y_true = np.asarray(y, dtype=float).reshape(-1)
        preds = self.predict(x)
        ss_res = float(np.sum((y_true - preds) ** 2))
        ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
        if ss_tot <= 1e-12:
            return 0.0
        return 1.0 - ss_res / ss_tot


class RidgeRegressorLite(LinearRegressionLite):
    def __init__(self, alpha: float = 1.0) -> None:
        super().__init__(alpha=alpha)


class RandomSubspaceRegressorLite:
    def __init__(
        self,
        n_estimators: int = 48,
        max_features: int | None = None,
        alpha: float = 1.0,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.max_features = max_features
        self.alpha = alpha
        self.random_state = random_state
        self.models_: list[tuple[np.ndarray, RidgeRegressorLite]] = []
        self.feature_importances_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "RandomSubspaceRegressorLite":
        x_arr = _as_2d(x)
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        n_samples, n_features = x_arr.shape
        feature_count = self.max_features or max(1, int(math.sqrt(n_features)))
        feature_count = min(feature_count, n_features)
        rng = np.random.default_rng(self.random_state)
        importances = np.zeros(n_features, dtype=float)
        self.models_ = []

        for _ in range(self.n_estimators):
            feature_idx = np.sort(rng.choice(n_features, size=feature_count, replace=False))
            sample_idx = rng.integers(0, n_samples, size=n_samples)
            model = RidgeRegressorLite(alpha=self.alpha)
            model.fit(x_arr[sample_idx][:, feature_idx], y_arr[sample_idx])
            self.models_.append((feature_idx, model))
            importances[feature_idx] += np.abs(model.coef_)

        total = importances.sum()
        self.feature_importances_ = importances / total if total > 0 else np.full(n_features, 1 / n_features)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        x_arr = _as_2d(x)
        if not self.models_:
            raise ValueError("Model must be fitted before predict.")
        stacked = [model.predict(x_arr[:, feature_idx]) for feature_idx, model in self.models_]
        return np.mean(np.vstack(stacked), axis=0)


class StagewiseBoostingRegressorLite:
    def __init__(
        self,
        n_estimators: int = 32,
        learning_rate: float = 0.08,
        alpha: float = 0.8,
        random_state: int = 42,
    ) -> None:
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.alpha = alpha
        self.random_state = random_state
        self.base_value_: float = 0.0
        self.models_: list[tuple[np.ndarray, RidgeRegressorLite]] = []
        self.feature_importances_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "StagewiseBoostingRegressorLite":
        x_arr = _as_2d(x)
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        n_samples, n_features = x_arr.shape
        rng = np.random.default_rng(self.random_state)
        residual = y_arr.copy()
        self.base_value_ = float(np.mean(y_arr))
        residual -= self.base_value_
        self.models_ = []
        importances = np.zeros(n_features, dtype=float)
        subset_size = max(1, min(n_features, int(0.7 * n_features)))

        for _ in range(self.n_estimators):
            feature_idx = np.sort(rng.choice(n_features, size=subset_size, replace=False))
            model = RidgeRegressorLite(alpha=self.alpha)
            model.fit(x_arr[:, feature_idx], residual)
            step = model.predict(x_arr[:, feature_idx])
            residual -= self.learning_rate * step
            self.models_.append((feature_idx, model))
            importances[feature_idx] += np.abs(model.coef_)

        total = importances.sum()
        self.feature_importances_ = importances / total if total > 0 else np.full(n_features, 1 / n_features)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        x_arr = _as_2d(x)
        preds = np.full(len(x_arr), self.base_value_, dtype=float)
        for feature_idx, model in self.models_:
            preds += self.learning_rate * model.predict(x_arr[:, feature_idx])
        return preds


class LogisticRegressionLite:
    def __init__(
        self,
        C: float = 1.0,
        max_iter: int = 400,
        learning_rate: float = 0.25,
        tol: float = 1e-5,
    ) -> None:
        self.C = C
        self.max_iter = max_iter
        self.learning_rate = learning_rate
        self.tol = tol
        self.intercept_: float = 0.0
        self.coef_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "LogisticRegressionLite":
        x_arr = _as_2d(x)
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        ones = np.ones((len(x_arr), 1), dtype=float)
        design = np.hstack([ones, x_arr])
        weights = np.zeros(design.shape[1], dtype=float)
        reg = 1.0 / max(self.C, 1e-6)

        for _ in range(self.max_iter):
            logits = np.clip(design @ weights, -30, 30)
            probs = 1.0 / (1.0 + np.exp(-logits))
            grad = design.T @ (probs - y_arr) / len(design)
            grad[1:] += reg * weights[1:] / len(design)
            weights -= self.learning_rate * grad
            if float(np.linalg.norm(grad)) < self.tol:
                break

        self.intercept_ = float(weights[0])
        self.coef_ = weights[1:]
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise ValueError("Model must be fitted before predict_proba.")
        x_arr = _as_2d(x)
        logits = np.clip(x_arr @ self.coef_ + self.intercept_, -30, 30)
        prob_1 = 1.0 / (1.0 + np.exp(-logits))
        prob_0 = 1.0 - prob_1
        return np.column_stack([prob_0, prob_1])


class KMeansLite:
    def __init__(self, n_clusters: int = 4, n_init: int = 20, max_iter: int = 100, random_state: int = 42) -> None:
        self.n_clusters = n_clusters
        self.n_init = n_init
        self.max_iter = max_iter
        self.random_state = random_state
        self.cluster_centers_: np.ndarray | None = None

    def _distance(self, x: np.ndarray, centers: np.ndarray) -> np.ndarray:
        return np.sum((x[:, None, :] - centers[None, :, :]) ** 2, axis=2)

    def _fit_once(self, x: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, float]:
        rng = np.random.default_rng(seed)
        indices = rng.choice(len(x), size=min(self.n_clusters, len(x)), replace=False)
        centers = x[indices].copy()

        for _ in range(self.max_iter):
            distances = self._distance(x, centers)
            labels = np.argmin(distances, axis=1)
            new_centers = centers.copy()
            for cluster_id in range(len(centers)):
                members = x[labels == cluster_id]
                if len(members) == 0:
                    new_centers[cluster_id] = x[rng.integers(0, len(x))]
                else:
                    new_centers[cluster_id] = members.mean(axis=0)
            if np.allclose(new_centers, centers):
                centers = new_centers
                break
            centers = new_centers

        distances = self._distance(x, centers)
        labels = np.argmin(distances, axis=1)
        inertia = float(np.take_along_axis(distances, labels[:, None], axis=1).sum())
        return centers, labels, inertia

    def fit(self, x: np.ndarray) -> "KMeansLite":
        x_arr = _as_2d(x)
        best_centers = None
        best_inertia = float("inf")
        for offset in range(self.n_init):
            centers, _, inertia = self._fit_once(x_arr, self.random_state + offset)
            if inertia < best_inertia:
                best_centers = centers
                best_inertia = inertia
        self.cluster_centers_ = best_centers
        return self

    def fit_predict(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).predict(x)

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.cluster_centers_ is None:
            raise ValueError("Model must be fitted before predict.")
        x_arr = _as_2d(x)
        return np.argmin(self._distance(x_arr, self.cluster_centers_), axis=1)

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.cluster_centers_ is None:
            raise ValueError("Model must be fitted before transform.")
        return np.sqrt(self._distance(_as_2d(x), self.cluster_centers_))


@dataclass
class SpearmanResult:
    correlation: float
    pvalue: float


def spearmanr_lite(x: pd.Series | np.ndarray, y: pd.Series | np.ndarray, nan_policy: str = "omit") -> SpearmanResult:
    x_series = pd.Series(x, dtype=float)
    y_series = pd.Series(y, dtype=float)
    sample = pd.concat([x_series, y_series], axis=1)
    if nan_policy == "omit":
        sample = sample.dropna()
    if len(sample) < 3:
        return SpearmanResult(np.nan, np.nan)

    rank_x = sample.iloc[:, 0].rank(method="average").to_numpy(dtype=float)
    rank_y = sample.iloc[:, 1].rank(method="average").to_numpy(dtype=float)
    corr = float(np.corrcoef(rank_x, rank_y)[0, 1]) if np.std(rank_x) > 0 and np.std(rank_y) > 0 else np.nan
    if not np.isfinite(corr):
        return SpearmanResult(np.nan, np.nan)
    if abs(corr) >= 0.999999:
        return SpearmanResult(corr, 0.0)

    n = len(sample)
    t_stat = abs(corr) * math.sqrt((n - 2) / max(1e-12, 1.0 - corr * corr))
    pvalue = math.erfc(t_stat / math.sqrt(2.0))
    return SpearmanResult(corr, pvalue)
