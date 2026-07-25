"use client";

// The week's consolidated buy list. This is the screen the admin actually works
// from: it rolls submitted orders + subscriptions into a per-product total, lets
// them expand each line to see who's buying what, and lets them override the
// quantity to actually order (a phoned-in change after the deadline, say).
//
// Two affordances exist purely because the admin re-types this into the real
// farm website by hand: a print-friendly mode (`window.print`, with the sidebar
// and controls hidden via `print:hidden`) and copy-as-plain-text.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Copy, Printer, Send, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDeadline, money } from "@/lib/format";
import { CYCLE_STATUS } from "@/lib/status";
import type { ShoppingList, ShoppingListLine } from "@/lib/types";
import { cn } from "@/lib/utils";

// The admin can only move the consolidated total while the cycle is still being
// planned. Once it's been ordered, the buy quantity is locked.
const EDITABLE_STATUSES = new Set(["aggregated", "approved"]);

export default function AdminShoppingListPage() {
  const cycle = useQuery({ queryKey: ["admin", "current-cycle"], queryFn: api.adminCurrentCycle });
  const cycleId = cycle.data?.id;

  const list = useQuery({
    queryKey: ["admin", "shopping-list", cycleId],
    queryFn: () => api.adminShoppingList(cycleId!),
    enabled: !!cycleId,
  });

  const data = list.data;
  const editable = data ? EDITABLE_STATUSES.has(data.cycle.status) : false;
  const pill = data ? CYCLE_STATUS[data.cycle.status] : null;

  // Lines grouped by category, categories alphabetical, so the printout reads
  // like aisles of a shop rather than one flat list.
  const groups = useMemo(() => groupByCategory(data?.lines ?? []), [data]);

  function sendToAccounting() {
    // Not wired up yet — this will POST the week's buy list once the accounting
    // integration exists. Kept visible so the flow is discoverable in the
    // meantime.
    toast("Send to accounting is coming soon", {
      description: "This will connect once the accounting interface is added.",
    });
  }

  function copyPlainText() {
    if (!data) return;
    navigator.clipboard.writeText(toPlainText(data)).then(
      () => toast.success("Copied the shopping list."),
      () => toast.error("Couldn't copy to the clipboard."),
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-8">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Shopping list</h1>
          {data && (
            <p className="text-sm text-muted-foreground">
              Delivery {formatDate(data.cycle.delivery_date)} · closes{" "}
              {formatDeadline(data.cycle.submission_deadline)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 print:hidden">
          <Button variant="outline" onClick={copyPlainText} disabled={!data}>
            <Copy /> Copy
          </Button>
          <Button variant="outline" onClick={() => window.print()} disabled={!data}>
            <Printer /> Print
          </Button>
          <Button onClick={sendToAccounting} disabled={!data}>
            <Send /> Send to accounting
          </Button>
          {pill && (
            <span className={cn("rounded-full px-3 py-1 text-sm font-medium", pill.className)}>
              {pill.label}
            </span>
          )}
        </div>
      </header>

      {/* Summary strip */}
      {data && (
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <span>
            <strong className="font-medium text-foreground">{money(data.total_cost)}</strong> total
          </span>
          <span>{data.lines.length} products</span>
          <span>{data.order_count} orders</span>
          <span>{data.subscription_count} subscriptions</span>
          <span>{data.customer_count} customers</span>
        </div>
      )}

      {!editable && data && (
        <p className="mt-4 rounded-lg border border-dashed p-3 text-sm text-muted-foreground print:hidden">
          {data.cycle.status === "open" || data.cycle.status === "locked"
            ? "This is a live preview. Aggregate the week to lock in a snapshot and enable quantity overrides."
            : "This week has been ordered — the buy quantities are locked."}
        </p>
      )}

      <div className="mt-6 space-y-8">
        {list.isLoading || !data ? (
          <Skeleton className="h-64 w-full rounded-xl" />
        ) : data.lines.length === 0 ? (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            Nothing to buy yet — no orders or subscriptions for this week.
          </p>
        ) : (
          groups.map(({ category, lines }) => (
            <section key={category}>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {category}
              </h2>
              <ul className="divide-y overflow-hidden rounded-xl border bg-card">
                {lines.map((line) => (
                  <LineRow
                    key={line.product_id}
                    line={line}
                    cycleId={cycleId!}
                    editable={editable}
                  />
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  );
}

function LineRow({
  line,
  cycleId,
  editable,
}: {
  line: ShoppingListLine;
  cycleId: string;
  editable: boolean;
}) {
  const queryClient = useQueryClient();
  // Expanded by default so the customers behind each product's total are visible
  // at a glance; still collapsible per line.
  const [expanded, setExpanded] = useState(true);
  // Draft of the override input, seeded from whatever the server currently has.
  const [draft, setDraft] = useState<string>(
    line.adjusted_quantity == null ? "" : String(line.adjusted_quantity),
  );

  const adjust = useMutation({
    mutationFn: (quantity: number | null) =>
      api.adminAdjustLine(cycleId, line.product_id, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "shopping-list", cycleId] });
      queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Couldn't adjust the quantity."),
  });

  // Only send the change when the value actually differs from the server's, so
  // clicking away without editing doesn't fire a pointless request.
  function commit() {
    const trimmed = draft.trim();
    const next = trimmed === "" ? null : Number(trimmed);
    if (next !== null && (!Number.isInteger(next) || next < 0)) {
      toast.error("Enter a whole number, or clear the field to reset.");
      setDraft(line.adjusted_quantity == null ? "" : String(line.adjusted_quantity));
      return;
    }
    if (next === line.adjusted_quantity) return;
    adjust.mutate(next);
  }

  const overridden = line.adjusted_quantity != null;

  return (
    <li>
      <div className="flex items-center gap-3 p-4">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={expanded}
        >
          <ChevronRight
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform print:hidden",
              expanded && "rotate-90",
            )}
          />
          <div className="min-w-0">
            <p className="truncate font-medium">
              {line.product_name}
              <span className="ml-1.5 text-sm font-normal text-muted-foreground">
                / {line.product_unit}
              </span>
            </p>
            <p className="truncate text-sm text-muted-foreground">
              {line.order_quantity} order + {line.subscription_quantity} subscription
              {line.is_spike && (
                <span className="ml-2 inline-flex items-center gap-1 font-medium text-amber-600">
                  <TrendingUp className="size-3.5" />
                  {line.delta_pct == null ? "spike" : `+${Math.round(line.delta_pct)}%`}
                </span>
              )}
            </p>
          </div>
        </button>

        {/* Buy quantity: an editable override when the cycle allows it, else read-only. */}
        <div className="flex shrink-0 items-center gap-3">
          {editable ? (
            <div className="flex items-center gap-1.5 print:hidden">
              <Input
                type="number"
                min={0}
                inputMode="numeric"
                value={draft}
                placeholder={String(line.total_quantity)}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commit}
                onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                disabled={adjust.isPending}
                className="h-8 w-20 text-right tabular-nums"
                aria-label={`Buy quantity for ${line.product_name}`}
              />
              {overridden && (
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={() => {
                    setDraft("");
                    adjust.mutate(null);
                  }}
                  disabled={adjust.isPending}
                >
                  Reset
                </Button>
              )}
            </div>
          ) : null}
          <div className="w-14 text-right">
            <p className="text-lg font-semibold tabular-nums">{line.effective_quantity}</p>
            {overridden && (
              <p className="text-xs text-muted-foreground tabular-nums line-through">
                {line.total_quantity}
              </p>
            )}
          </div>
          <div className="hidden w-20 text-right text-sm text-muted-foreground tabular-nums sm:block">
            {money(line.line_total)}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t bg-muted/30 px-4 py-3 pl-10">
          <ul className="space-y-1 text-sm">
            {line.customers.map((c) => (
              <li key={`${c.user_id}-${c.source}`} className="flex items-center justify-between gap-3">
                <span className="min-w-0 truncate">
                  {c.full_name}
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {c.source === "subscription" ? "subscription" : "order"}
                  </span>
                </span>
                <span className="shrink-0 tabular-nums">{c.quantity}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}

// --- helpers ----------------------------------------------------------------

function groupByCategory(lines: ShoppingListLine[]): { category: string; lines: ShoppingListLine[] }[] {
  const byCategory = new Map<string, ShoppingListLine[]>();
  for (const line of lines) {
    const bucket = byCategory.get(line.category) ?? [];
    bucket.push(line);
    byCategory.set(line.category, bucket);
  }
  return [...byCategory.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, lines]) => ({
      category,
      lines: lines.sort((a, b) => a.product_name.localeCompare(b.product_name)),
    }));
}

// Plain text for pasting into the farm's own website. One product per line, the
// effective (post-override) quantity, grouped under category headers.
function toPlainText(data: ShoppingList): string {
  const out: string[] = [`Shopping list — delivery ${formatDate(data.cycle.delivery_date)}`, ""];
  for (const { category, lines } of groupByCategory(data.lines)) {
    out.push(`${category.toUpperCase()}`);
    for (const line of lines) {
      out.push(`  ${line.effective_quantity} × ${line.product_name} (${line.product_unit})`);
    }
    out.push("");
  }
  out.push(`Total: ${money(data.total_cost)}`);
  return out.join("\n");
}
