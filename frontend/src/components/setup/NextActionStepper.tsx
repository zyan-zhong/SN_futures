import type { SetupChecklistStep } from "../../utils/guidedSetup";
import { formatStatusLabel } from "../../utils/statusTaxonomy";

export function NextActionStepper({ steps }: { steps: SetupChecklistStep[] }) {
  return (
    <ol aria-label="Setup Checklist steps" className="next-action-stepper">
      {steps.map((step, index) => {
        const isCurrent = step.is_current_step || step.isCurrent;
        const disabledReason = step.action_disabled_reason || step.disabledReason;
        return (
          <li
            key={step.step_id ?? step.id}
            className={isCurrent ? "current" : ""}
            data-status={step.status}
            tabIndex={0}
            {...(isCurrent ? { "aria-current": "step" } : {})}
          >
            <span>Step {index + 1}</span>
            <strong>{step.label ?? step.title}</strong>
            <p>{step.short_reason ?? step.description}</p>
            <em>{formatStatusLabel(step.status === "current" ? "blocked" : step.status)}</em>
            <small>{step.safe_action_id ?? step.safeAction}</small>
            {disabledReason ? <small className="disabled-reason">禁用原因：{disabledReason}</small> : ""}
          </li>
        );
      })}
    </ol>
  );
}
