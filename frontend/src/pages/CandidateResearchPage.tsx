import { useEffect, useState } from "react";
import { getCandidateV10Report, getCandidateV12Report, getCostStressAttribution, getCpcvValidationReport, getYearConcentration } from "../api/terminal";
import type { CandidateV10ResearchPayload, CandidateV12ResearchPayload, CostStressAttributionPayload, CPCVValidationPayload, YearConcentrationPayload } from "../api/types";
import { DataTable } from "../components/common/DataTable";
import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { formatCandidateStatus } from "../utils/statusTaxonomy";
import type { PageKey } from "../App";

export function CandidateResearchPage({ onNavigate }: { onNavigate?: (page: PageKey) => void }) {
  const [v10, setV10] = useState<CandidateV10ResearchPayload | null>(null);
  const [v12, setV12] = useState<CandidateV12ResearchPayload | null>(null);
  const [year, setYear] = useState<YearConcentrationPayload | null>(null);
  const [cost, setCost] = useState<CostStressAttributionPayload | null>(null);
  const [cpcv, setCpcv] = useState<CPCVValidationPayload | null>(null);

  useEffect(() => {
    void getCandidateV10Report().then(setV10).catch(() => setV10(null));
    void getCandidateV12Report().then(setV12).catch(() => setV12(null));
    void getYearConcentration().then(setYear).catch(() => setYear(null));
    void getCostStressAttribution().then(setCost).catch(() => setCost(null));
    void getCpcvValidationReport("v10").then(setCpcv).catch(() => setCpcv(null));
  }, []);

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Candidate Research" source={{ status: v12?.status ?? v10?.status ?? "blocked" }} />
      <SectionCard title="Candidate Research" subtitle="Current candidates are evidence-only and cannot write active artifacts or customer output.">
        <DataTable
          data={[
            { item: "Candidate v12 current blocked summary", status: formatCandidateStatus(v12?.status ?? "blocked"), detail: String(v12?.reason_zh ?? "waiting for v12 managed data chain") },
            { item: "Candidate v10 research-only summary", status: formatCandidateStatus(v10?.status ?? "research_only"), detail: formatCandidateStatus(v10?.promotion_dry_run?.status ?? "dry_run_only") },
            { item: "Cost/year/CPCV short summary", status: formatCandidateStatus(cost?.status ?? year?.status ?? cpcv?.status ?? "blocked"), detail: "cost attribution, year evidence, and CPCV remain evidence only" },
          ]}
          columns={[
            { key: "item", title: "summary" },
            { key: "status", title: "status" },
            { key: "detail", title: "detail" }
          ]}
        />
        <div className="notice-card">
          <strong>no active / no prediction notice</strong>
          <span>Candidate evidence does not create active_model.json or customer_predictions.</span>
        </div>
        <button className="secondary-button" type="button" onClick={() => onNavigate?.("research-archive")}>Open research-archive</button>
      </SectionCard>
    </div>
  );
}
