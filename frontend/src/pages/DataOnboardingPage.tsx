import { useEffect, useState } from "react";
import {
  getFeatureStoreV12BuildPlan,
  getFeatureStoreV12ControlledBuild,
  getFeatureStoreV12InputContract,
  getLocalApiProviderHub,
  getManagedDataBackfillPlan,
  getManagedDataProductionCacheGate,
  getManagedProxyEndpointSmoke,
  getManagedProxyOperatorRunbook,
  getManagedProxyQuarantineContract,
  getManagedProxyQuarantineSnapshot,
  getManagedProxySampleFixture,
} from "../api/terminal";
import { DataTable } from "../components/common/DataTable";
import { WorkspaceGuardBanner } from "../components/common/WorkspaceGuardBanner";
import { SectionCard } from "../components/layout/SectionCard";
import { GuidedSetupChecklist } from "../components/setup/GuidedSetupChecklist";
import { LocalApiProviderHandoffCard } from "../components/setup/LocalApiProviderHandoffCard";
import { formatNextAction, formatStatusLabel } from "../utils/statusTaxonomy";

type ChainRow = { item: string; status: string; next: string };

export function DataOnboardingPage() {
  const [rows, setRows] = useState<ChainRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([
      getLocalApiProviderHub(),
      getManagedProxyOperatorRunbook(),
      getManagedProxyEndpointSmoke(),
      getManagedProxySampleFixture(),
      getManagedProxyQuarantineSnapshot(),
      getManagedProxyQuarantineContract(),
      getManagedDataBackfillPlan(),
      getManagedDataProductionCacheGate(),
      getFeatureStoreV12InputContract(),
      getFeatureStoreV12BuildPlan(),
      getFeatureStoreV12ControlledBuild(),
    ]).then((results) => {
      if (cancelled) return;
      const labels = [
        "Local API Provider Hub",
        "Operator Runbook",
        "Provider / Endpoint Smoke",
        "Sample Fixture Contract",
        "Quarantine Snapshot",
        "Quarantine Contract",
        "Backfill Planner",
        "Production Cache Gate",
        "v12 Input Contract",
        "v12 Build Plan",
        "v12 Controlled Build",
      ];
      setRows(results.map((result, index) => {
        const payload = result.status === "fulfilled" && result.value && typeof result.value === "object" ? result.value as Record<string, unknown> : {};
        return {
          item: labels[index],
          status: formatStatusLabel(payload.status ?? "blocked"),
          next: formatNextAction(payload.next_allowed_action ?? payload.blocking_reasons ?? "wait_for_upstream_readiness"),
        };
      }));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-stack">
      <WorkspaceGuardBanner workspace="Data Onboarding" />
      <LocalApiProviderHandoffCard />
      <GuidedSetupChecklist compact />
      <SectionCard title="Data Onboarding" subtitle="Local API Provider -> verified local cache -> v12 chain. This page only reads reports.">
        <DataTable
          data={rows}
          emptyLabel="Local API provider / v12 chain reports are not loaded yet"
          columns={[
            { key: "item", title: "Local provider / v12 chain" },
            { key: "status", title: "status" },
            { key: "next", title: "next" }
          ]}
        />
      </SectionCard>
      <details aria-label="Detailed data source cards" className="technical-details-drawer">
        <summary>Detailed data source cards</summary>
        <div className="notice-card">
          <strong>Details collapsed by default</strong>
          <span>Provider-level cards remain available for diagnostics, but the onboarding chain is the primary view.</span>
        </div>
      </details>
    </div>
  );
}
