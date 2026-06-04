"use client";

import * as React from "react";

import { AttemptStatusBadge } from "@/entities/attempt";
import { usePollingStatusApiStatusPollingGet } from "@/shared/api/status/status";
import type { PollingStatusItem } from "@/shared/api/schemas/pollingStatusItem";
import { formatRelativeTime } from "@/shared";

const REFETCH_INTERVAL_MS = 5000;

const NO_ITEMS: PollingStatusItem[] = [];

function PollingCard({ item }: { item: PollingStatusItem }) {
  return (
    <li
      data-testid="polling-card"
      data-config-id={item.config_id}
      className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50/60 p-4"
    >
      {/* config + credential names — the headline the user asked for. */}
      <div className="flex flex-col gap-0.5">
        <span className="text-base font-semibold text-gray-900 sm:text-lg">
          {item.config_name}
        </span>
        <span className="text-sm text-gray-600">
          <span className="text-gray-400">계정 </span>
          {item.credential_name ?? "—"}
        </span>
      </div>

      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-700">
        <div>
          <dt className="inline text-gray-400">Shape </dt>
          <dd className="inline font-mono">{item.shape}</dd>
        </div>
        <div>
          <dt className="inline text-gray-400">스펙 </dt>
          <dd className="inline">
            {item.ocpus} OCPU / {item.memory_gb} GB
          </dd>
        </div>
        <div>
          <dt className="inline text-gray-400">간격 </dt>
          <dd className="inline">{item.retry_interval_sec}s</dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <div className="flex items-center gap-2">
          {item.last_attempt_status ? (
            <>
              <AttemptStatusBadge status={item.last_attempt_status} />
              <span className="text-xs text-gray-500">
                {formatRelativeTime(item.last_attempt_at)}
              </span>
            </>
          ) : (
            <span className="text-xs text-gray-500">아직 시도 없음</span>
          )}
        </div>
        <span className="text-xs text-gray-600">
          누적 <span className="font-semibold">{item.total_attempts}</span>회
        </span>
      </div>
    </li>
  );
}

/**
 * Dashboard "currently polling" widget (PRD §7.3, §7.4).
 *
 * Lists every enabled config the worker is polling with its config + credential
 * names front and center, the requested shape/spec, the last attempt status
 * (badge + relative time) and the cumulative attempt count. Polls every 5s.
 */
export function PollingStatus() {
  const { data, isLoading } = usePollingStatusApiStatusPollingGet({
    query: { refetchInterval: REFETCH_INTERVAL_MS },
  });

  const items = data ?? NO_ITEMS;

  return (
    <section data-testid="polling-status" className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-gray-700">🔄 폴링 중인 설정</h2>
      {items.length > 0 ? (
        <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {items.map((item) => (
            <PollingCard key={item.config_id} item={item} />
          ))}
        </ul>
      ) : (
        !isLoading && (
          <p
            data-testid="polling-empty"
            className="rounded-lg border border-dashed border-gray-300 px-4 py-6 text-center text-sm text-gray-400"
          >
            활성화된 설정이 없습니다.
          </p>
        )
      )}
    </section>
  );
}
