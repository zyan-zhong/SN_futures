import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";

export function ResearchArchivePage() {
  const archived = ["candidate_v3", "candidate_v4", "candidate_v6", "candidate_v7", "candidate_v8", "candidate_v9"];

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Research Archive" />
      <SectionCard title="Research Archive" subtitle="Historical research evidence is collapsed by default and cannot run candidates from this page.">
        <details aria-label="Archived Candidates" className="technical-details-drawer">
          <summary>Archived Candidates</summary>
          <div className="notice-card">
            <strong>Advanced research-only toggle</strong>
            <span>Historical run buttons are hidden by default. research-only/no-active/no-prediction. does not write active artifacts or create customer-facing forecast output.</span>
          </div>
          <ul>
            {archived.map((candidate) => (
              <li key={candidate}>{candidate}</li>
            ))}
          </ul>
        </details>
        <details aria-label="OOF trace historical panels" className="technical-details-drawer">
          <summary>OOF trace historical panels</summary>
          <div className="notice-card">
            <strong>older diagnostics</strong>
            <span>OOF trace and older validation diagnostics stay archived until explicitly reviewed.</span>
          </div>
        </details>
      </SectionCard>
    </div>
  );
}
