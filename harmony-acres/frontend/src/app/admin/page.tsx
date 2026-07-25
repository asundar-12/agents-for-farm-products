"use client";

// Admin dashboard: the week's headline numbers up top, then who still hasn't
// submitted so the admin can nudge them before the deadline.

import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate, formatDeadline, money } from "@/lib/format";
import { CYCLE_STATUS } from "@/lib/status";
import { cn } from "@/lib/utils";

export default function AdminDashboardPage() {
  const dash = useQuery({ queryKey: ["admin", "dashboard"], queryFn: api.adminDashboard });
  const cycleId = dash.data?.cycle.id;

  const nonSubmitters = useQuery({
    queryKey: ["admin", "non-submitters", cycleId],
    queryFn: () => api.adminNonSubmitters(cycleId!),
    enabled: !!cycleId,
  });

  const d = dash.data;
  const pill = d ? CYCLE_STATUS[d.cycle.status] : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">This week</h1>
          {d && (
            <p className="text-sm text-muted-foreground">
              Delivery {formatDate(d.cycle.delivery_date)} · closes{" "}
              {formatDeadline(d.cycle.submission_deadline)}
            </p>
          )}
        </div>
        {pill && (
          <span className={cn("rounded-full px-3 py-1 text-sm font-medium", pill.className)}>
            {pill.label}
          </span>
        )}
      </header>

      {/* Stat tiles */}
      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {dash.isLoading || !d ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))
        ) : (
          <>
            <Stat
              label="Orders submitted"
              value={`${d.order_count}`}
              sub={`of ${d.customer_count} customers`}
            />
            <Stat label="Total units" value={`${d.total_units}`} sub={`${d.product_count} products`} />
            <Stat label="Total cost" value={money(d.total_cost)} sub={`${d.subscription_count} subscriptions`} />
            <Stat
              label="Demand spikes"
              value={`${d.spike_count}`}
              sub={d.spike_count === 1 ? "product up sharply" : "products up sharply"}
              highlight={d.spike_count > 0}
            />
          </>
        )}
      </div>

      <Link
        href="/admin/shopping-list"
        className="mt-4 flex items-center justify-between rounded-xl border bg-card p-4 transition-colors hover:bg-accent"
      >
        <span className="font-medium">Open this week&apos;s shopping list</span>
        <ArrowRight className="size-5 text-muted-foreground" />
      </Link>

      {/* Non-submitters */}
      <section className="mt-8">
        <h2 className="font-medium">
          Hasn&apos;t submitted{d ? ` (${d.non_submitter_count})` : ""}
        </h2>
        <p className="text-sm text-muted-foreground">
          Customers with no submitted order and no subscription due this week.
        </p>

        <div className="mt-3">
          {nonSubmitters.isLoading ? (
            <Skeleton className="h-32 w-full rounded-xl" />
          ) : (nonSubmitters.data ?? []).length === 0 ? (
            <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
              Everyone&apos;s in. 🎉
            </p>
          ) : (
            <ul className="divide-y rounded-xl border bg-card">
              {nonSubmitters.data!.map((c) => (
                <li key={c.user_id} className="flex items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{c.full_name}</p>
                    <p className="truncate text-sm text-muted-foreground">{c.email}</p>
                  </div>
                  {c.has_draft ? (
                    <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                      Draft ({c.draft_item_count})
                    </span>
                  ) : (
                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      Not started
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  highlight,
}: {
  label: string;
  value: string;
  sub: string;
  highlight?: boolean;
}) {
  return (
    <div className={cn("rounded-xl border bg-card p-4", highlight && "border-amber-300 bg-amber-50")}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}
