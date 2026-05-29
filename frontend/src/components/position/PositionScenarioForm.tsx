import { useState } from "react";
import type { PositionScenarioInput } from "../../api/types";

const defaultInput: PositionScenarioInput = {
  direction: "observe",
  contracts: 1,
  entry_price: 0,
  account_equity: 100000,
  max_acceptable_loss: 5000,
  horizon: "tomorrow"
};

export function PositionScenarioForm({
  onSubmit,
  loading
}: {
  onSubmit: (input: PositionScenarioInput) => void;
  loading?: boolean;
}) {
  const [form, setForm] = useState(defaultInput);
  const update = (patch: Partial<PositionScenarioInput>) => setForm((prev) => ({ ...prev, ...patch }));
  return (
    <form
      className="position-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(form);
      }}
    >
      <label>
        持仓方向
        <select value={form.direction} onChange={(event) => update({ direction: event.target.value as PositionScenarioInput["direction"] })}>
          <option value="long">多头</option>
          <option value="short">空头</option>
          <option value="observe">观望</option>
        </select>
      </label>
      <label>
        手数
        <input min={0} type="number" value={form.contracts} onChange={(event) => update({ contracts: Number(event.target.value) })} />
      </label>
      <label>
        均价
        <input min={0} type="number" value={form.entry_price} onChange={(event) => update({ entry_price: Number(event.target.value) })} />
      </label>
      <label>
        账户权益
        <input min={0} type="number" value={form.account_equity} onChange={(event) => update({ account_equity: Number(event.target.value) })} />
      </label>
      <label>
        最大可承受亏损
        <input min={0} type="number" value={form.max_acceptable_loss} onChange={(event) => update({ max_acceptable_loss: Number(event.target.value) })} />
      </label>
      <label>
        计划周期
        <select value={form.horizon} onChange={(event) => update({ horizon: event.target.value })}>
          <option value="next_5m">5分钟</option>
          <option value="next_15m">15分钟</option>
          <option value="next_30m">30分钟</option>
          <option value="next_hour">1小时</option>
          <option value="tomorrow">1日</option>
          <option value="one_to_two_weeks">1-2周</option>
          <option value="one_to_three_months">1-3个月</option>
        </select>
      </label>
      <button className="primary-button" disabled={loading} type="submit">
        {loading ? "正在计算情景..." : "生成持仓情景"}
      </button>
    </form>
  );
}
