"use client";

// Farm-wide view of active subscriptions due this week, grouped by customer.
// Separate from the admin's personal "Your Subscriptions" in the customer nav.

import { useQuery } from "@tanstack/react-query";

import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate, formatDateOnly } from "@/lib/format";
import type { SubscriptionFrequency } from "@/lib/types";

const POLL_MS = 8_000;

const FREQUENCY_LABEL: Record<SubscriptionFrequency, string> = {
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
};

export default function AdminSubscriptionsPage() {
  const data = useQuery({
    queryKey: ["admin", "subscriptions"],
    queryFn: () => api.adminSubscriptions(),
    refetchInterval: POLL_MS,
  });

  const customers = data.data?.customers ?? [];
  const cycle = data.data?.cycle;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Subscriptions</h1>
        <p className="text-sm text-muted-foreground">
          Active plans due this week
          {cycle ? ` · delivery ${formatDate(cycle.delivery_date)}` : ""}
        </p>
      </header>

      <div className="mt-6 space-y-4">
        {data.isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))
        ) : customers.length === 0 ? (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            No subscriptions due this week.
          </p>
        ) : (
          customers.map((customer) => (
            <section key={customer.user_id} className="rounded-xl border bg-card p-4">
              <div className="min-w-0">
                <p className="truncate font-medium">{customer.full_name}</p>
                <p className="truncate text-sm text-muted-foreground">{customer.email}</p>
              </div>
              <ul className="mt-3 space-y-3 border-t pt-3">
                {customer.subscriptions.map((sub) => {
                  const summary = sub.items
                    .map((i) => `${i.quantity} × ${i.product_name}`)
                    .join(", ");
                  const freq = FREQUENCY_LABEL[sub.frequency as SubscriptionFrequency] ?? sub.frequency;
                  return (
                    <li key={sub.id}>
                      <p className="text-sm font-medium">{summary || "Empty plan"}</p>
                      <p className="text-xs text-muted-foreground">
                        {freq} · next {formatDateOnly(sub.next_delivery_date)}
                      </p>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>
    </div>
  );
}
