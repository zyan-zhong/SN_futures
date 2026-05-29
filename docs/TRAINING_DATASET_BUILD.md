# 训练数据集构建说明

本模块基于真实沪锡行情历史和 Prompt 40R 的可用因子构建训练数据集。它只生成可审计的数据文件和 manifest，不训练 active model，不生成客户预测，不生成回测，不使用 baseline。

## 输入

- `outputs/sn_market_history.json`
- `outputs/sn_live_snapshot.json`
- `outputs/events/event_store.json`
- `outputs/events/news_events.json`
- `outputs/shfe_auxiliary_data.json`
- `outputs/data_watermark.json`

`sample=true` 或 `sample_mode=true` 的数据不会进入训练数据集。

## 输出

- `outputs/training_dataset_manifest.json`
- `outputs/training_datasets/train_1d.parquet` 或 `.csv`
- `outputs/training_datasets/train_3d.parquet` 或 `.csv`
- `outputs/training_datasets/train_5d.parquet` 或 `.csv`
- `outputs/training_datasets/train_10d.parquet` 或 `.csv`
- `outputs/training_datasets/train_20d.parquet` 或 `.csv`

如果当前环境缺少 parquet 依赖，会自动降级写 CSV。

## 样本结构

每个 horizon 的训练样本包含：

- `feature_cols`：来自真实可用因子，覆盖率不低于阈值。
- `y_direction`：对应 horizon 的 forward direction label。
- `y_return`：对应 horizon 的 forward return label。
- `label_start_time`
- `label_end_time`
- `horizon`
- `tb_*`：triple-barrier 研究标签，仅用于后续研究，不默认作为训练目标。

末尾未来窗口不足的样本会被删除。

## 泄漏控制

manifest 记录：

- `feature_cols`
- `label_cols`
- `removed_label_cols`
- `forbidden_feature_patterns`
- `leakage_check_pass`
- `leakage_check_details`
- `sample_data_used=false`
- `baseline_used=false`

以下前缀不会进入 `feature_cols`：

- `ret_`
- `direction_`
- `abs_ret_`
- `realized_vol_`
- `max_favorable_excursion_`
- `max_adverse_excursion_`
- `tb_`

## API

- `POST /api/terminal/training-dataset/build`
- `GET /api/terminal/training-dataset/status`

## 当前真实数据状态

基于当前 2710 行真实历史行情，可构建 `1d/3d/5d/10d/20d` 数据集。当前具备基础 OHLCV 技术/均值回归模型训练数据条件，但仍不具备完整基本面模型训练条件，因为基差、库存、外盘和宏观字段仍缺失。

## 边界

本步骤不训练模型，不晋级 active，不生成预测，不生成回测，不输出交易建议。
