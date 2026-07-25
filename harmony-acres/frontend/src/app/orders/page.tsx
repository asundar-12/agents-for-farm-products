"use client";

// Order history: every order this customer has placed, newest first. Filter
// chips narrow by status. Each row links to the read-only detail screen.

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BottomNav } from "@/components/bottom-nav";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate, money } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/status";
import type { OrderStatus } from "@/lib/types";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

type Filter = "all" | "draft" | "submitted";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "draft", label: "Drafts" },
  { value: "submitted", label: "Submitted" },
];

export default function OrdersPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const [filter, setFilter] = useState<Filter>("all");

  const orders = useQuery({ queryKey: ["orders"], queryFn: api.orders, enabled: !!user });

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  // Newest first. The API sorts too, but sorting here keeps us safe if that
  // ever changes.
  const all = [...(orders.data ?? [])].sort(
    (a, b) => +new Date(b.created_at) - +new Date(a.created_at),
  );
  const visible = filter === "all" ? all : all.filter((o) => o.status === filter);

  return (
    <>
      <main className="flex-1 pb-24">
        <div className="mx-auto max-w-md px-4 py-6">
          <h1 className="text-2xl font-semibold tracking-tight">Order history</h1>

          <div className="mt-4 flex gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition-colors",
                  filter === f.value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-input bg-background hover:bg-accent",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="mt-4 space-y-3">
            {orders.isLoading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))
            ) : visible.length === 0 ? (
              <p className="py-16 text-center text-muted-foreground">No orders here yet.</p>
            ) : (
              visible.map((o) => {
                const count = o.items.reduce((n, i) => n + i.quantity, 0);
                const pill = ORDER_STATUS[o.status as OrderStatus];
                return (
                  <Link
                    key={o.id}
                    href={`/orders/${o.id}`}
                    className="flex items-center gap-3 rounded-xl border bg-card p-4 transition-colors hover:bg-accent"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">Week of {formatDate(o.order_date)}</span>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium",
                            pill.className,
                          )}
                        >
                          {pill.label}
                        </span>
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {count} {count === 1 ? "item" : "items"} · {money(o.total_amount)}
                      </p>
                    </div>
                    <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
                  </Link>
                );
              })
            )}
          </div>
        </div>
      </main>
      <BottomNav />
    </>
  );
}
