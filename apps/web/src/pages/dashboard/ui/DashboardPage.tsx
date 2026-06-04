"use client";

import { Check, Copy } from "lucide-react";
import * as React from "react";

import { AttemptsTable, useAttempts } from "@/entities/attempt";
import { useConfigs } from "@/entities/config";
import { PollingStatus } from "@/widgets/polling-status";

const REFETCH_INTERVAL_MS = 5000;

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      aria-label="Copy OCID"
      data-testid="copy-ocid"
      onClick={() => {
        void navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-green-700 hover:bg-green-100"
    >
      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
    </button>
  );
}

function StatCard({
  label,
  value,
  testid,
}: {
  label: string;
  value: React.ReactNode;
  testid: string;
}) {
  return (
    <div
      data-testid={testid}
      className="flex flex-col gap-1 rounded border border-gray-200 px-4 py-3"
    >
      <span className="text-xs uppercase tracking-wide text-gray-500">{label}</span>
      <span className="text-2xl font-semibold text-gray-800">{value}</span>
    </div>
  );
}

/** Dashboard: config counts, recent attempts, latest successful instance (PRD §7.4). */
export function DashboardPage() {
  const { data: configs } = useConfigs({
    query: { refetchInterval: REFETCH_INTERVAL_MS },
  });
  const { data: successes } = useAttempts(
    { status: "success", limit: 1 },
    { query: { refetchInterval: REFETCH_INTERVAL_MS } },
  );

  const list = configs ?? [];
  const activeCount = list.filter((c) => c.enabled).length;
  const inactiveCount = list.length - activeCount;
  const latestSuccess = (successes ?? [])[0];

  return (
    <div className="flex flex-col gap-6 p-6">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard testid="stat-active" label="Active configs" value={activeCount} />
        <StatCard
          testid="stat-inactive"
          label="Inactive configs"
          value={inactiveCount}
        />
        <StatCard testid="stat-total" label="Total configs" value={list.length} />
      </section>

      <PollingStatus />

      {latestSuccess && (
        <section
          data-testid="success-card"
          className="rounded border border-green-200 bg-green-50 px-4 py-3"
        >
          <h2 className="text-sm font-semibold text-green-800">
            ✅ 최근 생성된 인스턴스
          </h2>
          <dl className="mt-2 grid grid-cols-1 gap-1 text-sm text-green-900 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <dt className="inline text-green-700">OCID: </dt>
              <dd className="mt-0.5 flex items-start gap-1">
                <span className="min-w-0 break-all font-mono">
                  {latestSuccess.instance_ocid ?? "—"}
                </span>
                {latestSuccess.instance_ocid && (
                  <CopyButton value={latestSuccess.instance_ocid} />
                )}
              </dd>
            </div>
            <div>
              <dt className="inline text-green-700">생성 시각: </dt>
              <dd className="inline">
                {latestSuccess.attempted_at
                  ? new Date(latestSuccess.attempted_at).toLocaleString()
                  : "—"}
              </dd>
            </div>
          </dl>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">최근 시도 이력</h2>
        <AttemptsTable />
      </section>
    </div>
  );
}
