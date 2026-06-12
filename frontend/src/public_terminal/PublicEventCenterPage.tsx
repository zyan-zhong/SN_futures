import { useEffect, useState } from "react";
import { getPublicEvents } from "./api";
import { EventSummary } from "./components/EventSummary";
import type { PublicEventItem, PublicEventsPayload } from "./types";
import { friendlyReason, friendlyStatus, technicalSummary } from "./userCopy";

function relevanceLabel(value: number | undefined) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "relevance n/a";
  return `relevance ${value.toFixed(2)}`;
}

function eventCardId(event: PublicEventItem, index: number) {
  return `event-card-${event.event_id || `event-${index}`}`;
}

function blockReasons(event: PublicEventItem) {
  const reasons = event.blocking_reasons || [];
  if (reasons.length > 0) return reasons.join(", ");
  return event.used_in_model ? "eligible" : "not eligible";
}

function EventCard({ event, index }: { event: PublicEventItem; index: number }) {
  const used = Boolean(event.used_in_model);
  return (
    <article className="event-item" data-testid={eventCardId(event, index)}>
      <div className="event-item__header">
        <div>
          <strong>{event.title || "Untitled event"}</strong>
          <span>{event.summary || "No summary available."}</span>
        </div>
        <span className={used ? "status-pill tone-good" : "status-pill tone-warning"}>{used ? "used in model" : "not used in model"}</span>
      </div>
      <div className="tag-strip">
        <span className="status-pill">{event.source_name || event.provider_id || "unknown_source"}</span>
        <span className="status-pill">{event.category || "uncategorized"}</span>
        <span className="status-pill">{event.region || "unknown_region"}</span>
        <span className="status-pill">{event.language || "unknown_language"}</span>
        <span className="status-pill">{relevanceLabel(event.relevance_score)}</span>
      </div>
      <span>published {event.source_published_at || "missing_source_published_at"}</span>
      <span>fetched {event.fetched_at || "missing_fetched_at"}</span>
      <span>block reason: {blockReasons(event)}</span>
    </article>
  );
}

export function PublicEventCenterPage() {
  const [payload, setPayload] = useState<PublicEventsPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getPublicEvents()
      .then(setPayload)
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Events unavailable."));
  }, []);

  const center = payload?.event_center;
  const summary = center?.summary;
  const events = center?.events || [];

  return (
    <div className="page-stack public-terminal-page">
      <section className="section-card">
        <div className="section-card__header">
          <div>
            <h1>Events</h1>
            <p>Policy, news, exchange notices, and supply-chain events are shown only with source provenance and SHFE SN relevance.</p>
          </div>
          <span className="status-pill">{friendlyStatus(center?.status)}</span>
        </div>

        <div data-testid="event-summary">
          <EventSummary
            dataTestId="event-summary-section"
            summary={{
              ...summary,
              reason: error || friendlyReason(center?.reason, "event rows loaded"),
              status: center?.status
            }}
          />
        </div>
      </section>

      {events.length > 0 ? (
        <section className="event-center-list">
          {events.map((event, index) => (
            <EventCard event={event} index={index} key={event.event_id || index} />
          ))}
        </section>
      ) : (
        <section className="guided-empty-state" data-testid="event-empty-state">
          <header>
            <strong>{friendlyStatus("blocked")}</strong>
            <span>{error || friendlyReason(center?.reason, "No event rows in the local data layer.")}</span>
            {center?.reason ? <small>{center.reason}</small> : null}
          </header>
        </section>
      )}

      <details className="technical-details-drawer">
        <summary>Diagnostics</summary>
        <pre className="diagnostics-pre">
{`events payload
${technicalSummary(payload)}`}
        </pre>
      </details>
    </div>
  );
}
