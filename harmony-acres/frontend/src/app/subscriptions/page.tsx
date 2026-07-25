"use client";

// Subscription list. One card per plan with a summary line, frequency badge,
// next delivery, status pill, and quick actions (Pause / Resume / Edit /
// Cancel). A button up top creates a new one.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Pencil, Play, Plus, X } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { BottomNav } from "@/components/bottom-nav";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDateOnly } from "@/lib/format";
import { SUBSCRIPTION_STATUS } from "@/lib/status";
import type { Subscription, SubscriptionFrequency } from "@/lib/types";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

const FREQUENCY_LABEL: Record<SubscriptionFrequency, string> = {
  weekly: "Weekly",
  biweekly: "Every 2 weeks",
  monthly: "Monthly",
};

export default function SubscriptionsPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const queryClient = useQueryClient();

  const subs = useQuery({
    queryKey: ["subscriptions"],
    queryFn: api.subscriptions,
    enabled: !!user,
  });

  // One mutation drives every quick action; `run` is the API call to make, and
  // on success we refetch the list so the card reflects the new state.
  const action = useMutation({
    mutationFn: (run: () => Promise<Subscription>) => run(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "That didn't work. Try again."),
  });

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  const list = subs.data ?? [];

  return (
    <>
      <main className="flex-1 pb-24">
        <div className="mx-auto max-w-md px-4 py-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold tracking-tight">Subscriptions</h1>
            <Link href="/subscriptions/new" className={cn(buttonVariants({ size: "sm" }))}>
              <Plus className="size-4" /> New
            </Link>
          </div>

          <div className="mt-4 space-y-3">
            {subs.isLoading ? (
              Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-32 w-full rounded-xl" />
              ))
            ) : list.length === 0 ? (
              <div className="rounded-xl border border-dashed p-8 text-center">
                <p className="text-muted-foreground">No subscriptions yet.</p>
                <Link
                  href="/subscriptions/new"
                  className={cn(buttonVariants({ variant: "outline" }), "mt-4")}
                >
                  Create your first plan
                </Link>
              </div>
            ) : (
              list.map((s) => {
                const pill = SUBSCRIPTION_STATUS[s.status];
                const summary = s.items
                  .map((i) => `${i.quantity} × ${i.product_name}`)
                  .join(", ");
                const cancelled = s.status === "cancelled";
                return (
                  <div
                    key={s.id}
                    className={cn(
                      "rounded-xl border bg-card p-4",
                      s.status === "paused" && "opacity-70",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{summary || "Empty plan"}</p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {FREQUENCY_LABEL[s.frequency]} · next {formatDateOnly(s.next_delivery_date)}
                        </p>
                        {s.status === "paused" && s.paused_until && (
                          <p className="mt-0.5 text-xs text-amber-700">
                            Paused until {formatDateOnly(s.paused_until)}
                          </p>
                        )}
                      </div>
                      <span
                        className={cn(
                          "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                          pill.className,
                        )}
                      >
                        {pill.label}
                      </span>
                    </div>

                    {!cancelled && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {s.status === "active" ? (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={action.isPending}
                            onClick={() => action.mutate(() => api.pauseSubscription(s.id, null))}
                          >
                            <Pause className="size-4" /> Pause
                          </Button>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={action.isPending}
                            onClick={() => action.mutate(() => api.resumeSubscription(s.id))}
                          >
                            <Play className="size-4" /> Resume
                          </Button>
                        )}
                        <Link
                          href={`/subscriptions/${s.id}/edit`}
                          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                        >
                          <Pencil className="size-4" /> Edit
                        </Link>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive hover:text-destructive"
                          disabled={action.isPending}
                          onClick={() => {
                            if (confirm("Cancel this subscription?")) {
                              action.mutate(() => api.cancelSubscription(s.id));
                            }
                          }}
                        >
                          <X className="size-4" /> Cancel
                        </Button>
                      </div>
                    )}
                  </div>
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
