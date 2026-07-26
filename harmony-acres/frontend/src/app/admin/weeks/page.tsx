"use client";

// Admin weeks: the lifecycle console. The top card is the live cycle with the
// buttons that walk it through open → locked → aggregated → approved → ordered
// → received → closed; below is the history of every cycle, each row
// expandable to pull that (possibly archived) week's aggregated summary.
//
// The legal moves mirror the backend's `_ALLOWED_TRANSITIONS`. Each button maps
// to a named lifecycle endpoint (lock/aggregate/approve/...), so the client
// can't invent a transition — the backend rejects anything off the map.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDeadline, money } from "@/lib/format";
import { CYCLE_STATUS } from "@/lib/status";
import type { CycleStatus, WeeklyCycle } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Action {
  label: string;
  action: string; // lifecycle endpoint suffix
  variant?: "default" | "outline";
  // Steps that place the real order or archive the week are hard to walk back;
  // ask before firing them.
  confirm?: string;
}

// One entry per status the cycle can currently be in, listing the moves offered
// from there. The primary (forward) action comes first.
const ACTIONS: Record<CycleStatus, Action[]> = {
  open: [{ label: "Close ordering", action: "lock" }],
  locked: [
    { label: "Aggregate demand", action: "aggregate" },
    { label: "Reopen ordering", action: "reopen", variant: "outline" },
  ],
  aggregated: [{ label: "Approve", action: "approve" }],
  approved: [
    {
      label: "Mark ordered",
      action: "mark-ordered",
      confirm: "Mark this week as ordered? Do this once you've placed the order with the farm.",
    },
    { label: "Send back", action: "reject", variant: "outline" },
  ],
  ordered: [{ label: "Mark received", action: "mark-received" }],
  received: [
    {
      label: "Close week",
      action: "close",
      variant: "outline",
      confirm: "Close this week for good? Nothing can move after this.",
    },
  ],
  closed: [],
};

export default function AdminWeeksPage() {
  const current = useQuery({ queryKey: ["admin", "current-cycle"], queryFn: api.adminCurrentCycle });
  const cycles = useQuery({ queryKey: ["admin", "cycles"], queryFn: api.adminCycles });
  const queryClient = useQueryClient();

  const act = useMutation({
    mutationFn: ({ cycleId, action }: { cycleId: string; action: string }) =>
      api.adminCycleAction(cycleId, action),
    onSuccess: () => {
      // A transition can move the headline numbers and the current cycle, so
      // refresh everything the admin surfaces read from.
      queryClient.invalidateQueries({ queryKey: ["admin"] });
      toast.success("Week updated.");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Couldn't update the week."),
  });

  function run(cycleId: string, a: Action) {
    if (a.confirm && !window.confirm(a.confirm)) return;
    act.mutate({ cycleId, action: a.action });
  }

  const currentId = current.data?.id;
  // The history list already includes the current cycle; drop it from the lower
  // list so it doesn't appear twice.
  const past = (cycles.data ?? []).filter((c) => c.id !== currentId);

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 md:px-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Weeks</h1>
        <p className="text-sm text-muted-foreground">
          Walk the current week through its lifecycle, and revisit past weeks.
        </p>
      </header>

      {/* Current cycle */}
      <section className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          This week
        </h2>
        {current.isLoading || !current.data ? (
          <Skeleton className="h-32 w-full rounded-xl" />
        ) : (
          <CurrentCycleCard
            cycle={current.data}
            actions={ACTIONS[current.data.status]}
            onRun={(a) => run(current.data!.id, a)}
            pending={act.isPending}
          />
        )}
      </section>

      {/* History */}
      <section className="mt-8">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Past weeks
        </h2>
        {cycles.isLoading ? (
          <Skeleton className="h-40 w-full rounded-xl" />
        ) : past.length === 0 ? (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            No earlier weeks yet.
          </p>
        ) : (
          <ul className="divide-y overflow-hidden rounded-xl border bg-card">
            {past.map((c) => (
              <HistoryRow key={c.id} cycle={c} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CurrentCycleCard({
  cycle,
  actions,
  onRun,
  pending,
}: {
  cycle: WeeklyCycle;
  actions: Action[];
  onRun: (a: Action) => void;
  pending: boolean;
}) {
  const pill = CYCLE_STATUS[cycle.status];
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium">Delivery {formatDate(cycle.delivery_date)}</p>
          <p className="text-sm text-muted-foreground">
            Ordering closes {formatDeadline(cycle.submission_deadline)}
          </p>
        </div>
        <span className={cn("rounded-full px-3 py-1 text-sm font-medium", pill.className)}>
          {pill.label}
        </span>
      </div>

      {actions.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {actions.map((a) => (
            <Button
              key={a.action}
              variant={a.variant ?? "default"}
              onClick={() => onRun(a)}
              disabled={pending}
            >
              {a.label}
            </Button>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          This week is closed — nothing more to do.
        </p>
      )}
    </div>
  );
}

function HistoryRow({ cycle }: { cycle: WeeklyCycle }) {
  const [expanded, setExpanded] = useState(false);
  const pill = CYCLE_STATUS[cycle.status];

  // Only pull the aggregated summary once the row is opened — no point fetching
  // every archived week up front.
  const list = useQuery({
    queryKey: ["admin", "shopping-list", cycle.id],
    queryFn: () => api.adminShoppingList(cycle.id),
    enabled: expanded,
  });

  return (
    <li>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 p-4 text-left"
        aria-expanded={expanded}
      >
        <ChevronRight
          className={cn(
            "size-4 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-90",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium">Delivery {formatDate(cycle.delivery_date)}</p>
          <p className="truncate text-sm text-muted-foreground">
            Week of {formatDate(cycle.week_start)}
          </p>
        </div>
        <span className={cn("shrink-0 rounded-full px-3 py-1 text-sm font-medium", pill.className)}>
          {pill.label}
        </span>
      </button>

      {expanded && (
        <div className="border-t bg-muted/30 px-4 py-3 pl-11">
          {list.isLoading ? (
            <Skeleton className="h-6 w-48" />
          ) : list.isError ? (
            <p className="text-sm text-muted-foreground">Couldn&apos;t load this week&apos;s summary.</p>
          ) : list.data ? (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
              <span>
                <strong className="font-medium text-foreground">{money(list.data.total_cost)}</strong>{" "}
                total
              </span>
              <span>{list.data.lines.length} products</span>
              <span>{list.data.order_count} orders</span>
              <span>{list.data.subscription_count} subscriptions</span>
              <span>{list.data.customer_count} customers</span>
            </div>
          ) : null}
        </div>
      )}
    </li>
  );
}
