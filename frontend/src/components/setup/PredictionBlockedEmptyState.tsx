import { deriveBlockedPredictionExplanation } from "../../utils/guidedSetup";

export function PredictionBlockedEmptyState({ nextAllowedAction }: { nextAllowedAction?: string }) {
  const state = deriveBlockedPredictionExplanation(nextAllowedAction);

  return (
    <section aria-label="Prediction blocked empty state" className="guided-empty-state prediction-blocked-empty-state">
      <header>
        <strong>{state.title}</strong>
        <span>{state.summary}</span>
      </header>
      <div className="guided-empty-state__grid">
        <div>
          <strong>Reasons</strong>
          <ul>
            {state.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
        <div>
          <strong>Next step</strong>
          <p>{state.nextAction}</p>
          <strong>Safe actions available</strong>
          <ul>
            {state.safeActions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ul>
        </div>
      </div>
      <div className="disabled-action-list" aria-label="Disabled actions and reasons">
        <strong>Currently unavailable actions</strong>
        <span>Disabled reason</span>
        <ul>
          {state.disabledActions.map((item) => (
            <li key={item.label}>
              <span>{item.label}</span>
              <em>{item.reason}</em>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
