export const FIELD_LABELS: Record<string, string> = {
  "active_model_available": "Active 模型文件",
  "active_publish_allowed": "Active 发布权限",
  "blocking_reasons": "阻断原因",
  "current_state": "当前状态",
  "customer_prediction_generated": "客户预测文件",
  "next_allowed_action": "下一步允许动作",
  "prediction_generation_allowed": "预测生成权限",
  "prediction_status": "预测工作区状态",
  "status": "状态"
};

export function formatWorkspaceFieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key.replace(/[_-]+/g, " ");
}

export function formatBooleanFlag(value: unknown): string {
  return value === true ? "是" : "否";
}

export function formatRawStatusLabel(key: string): string {
  return `Raw status: ${key}`;
}
