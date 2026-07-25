"use client";

// Read-only detail for a single past order: a small status timeline, the
// locked-in line items and prices, and the total. When the current week is
// still open, a button copies these items into this week's draft.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate, money } from "@/lib/format";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

// A customer order moves through just these two states of its own; everything
// after submission happens to the whole weekly cycle, not the individual order.
const TIMELINE = ["draft", "submitted"] as const;

export default function OrderDetailPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const order = useQuery({
    queryKey: ["order", params.id],
    queryFn: () => api.order(params.id),
    enabled: !!user && !!params.id,
  });
  const cycle = useQuery({ queryKey: ["cycle"], queryFn: api.currentCycle, enabled: !!user });

  // Reorder: set each product's quantity on this week's draft to match, one
  // after another (sequential so the requests don't race), then send the user
  // to the order screen to review.
  const reorder = useMutation({
    mutationFn: async () => {
      const items = order.data?.items ?? [];
      for (const item of items) {
        await api.setItem(item.product_id, item.quantity);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["draft"] });
      toast.success("Added to this week's order.");
      router.push("/order");
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : "Couldn't add those items.");
    },
  });

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  const o = order.data;
  const canReorder = cycle.data?.is_open ?? false;
  const currentStep = o ? TIMELINE.indexOf(o.status as (typeof TIMELINE)[number]) : -1;

  return (
    <main className="flex-1 pb-28">
      <header className="sticky top-0 z-10 border-b bg-background/80 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <Link
            href="/orders"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
            aria-label="Back to orders"
          >
            <ArrowLeft className="size-5" />
          </Link>
          <h1 className="text-lg font-semibold">Order details</h1>
        </div>
      </header>

      <div className="mx-auto max-w-md px-4 py-6">
        {order.isLoading || !o ? (
          <div className="space-y-3">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">Week of {formatDate(o.order_date)}</p>

            {/* Status timeline — completed steps in accent green */}
            <ol className="mt-4 flex items-center">
              {TIMELINE.map((step, i) => {
                const done = i <= currentStep;
                const label = step === "draft" ? "Draft" : "Submitted";
                return (
                  <li key={step} className="flex flex-1 items-center last:flex-none">
                    <div className="flex flex-col items-center">
                      <span
                        className={cn(
                          "grid size-8 place-items-center rounded-full border text-xs font-medium",
                          done
                            ? "border-emerald-600 bg-emerald-600 text-white"
                            : "border-input text-muted-foreground",
                        )}
                      >
                        {done ? <Check className="size-4" /> : i + 1}
                      </span>
                      <span className="mt-1 text-xs text-muted-foreground">{label}</span>
                    </div>
                    {i < TIMELINE.length - 1 && (
                      <span
                        className={cn(
                          "mx-2 h-0.5 flex-1",
                          i < currentStep ? "bg-emerald-600" : "bg-input",
                        )}
                      />
                    )}
                  </li>
                );
              })}
            </ol>

            {/* Line items */}
            <ul className="mt-6 divide-y rounded-xl border bg-card">
              {o.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <p className="truncate font-medium leading-tight">{item.product_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {item.quantity} × {money(item.unit_price)}
                    </p>
                  </div>
                  <p className="font-medium tabular-nums">
                    {money(parseFloat(item.unit_price) * item.quantity)}
                  </p>
                </li>
              ))}
            </ul>

            <div className="mt-4 flex items-center justify-between px-1">
              <span className="text-muted-foreground">Total</span>
              <span className="text-lg font-semibold tabular-nums">{money(o.total_amount)}</span>
            </div>

            {o.note && (
              <div className="mt-4 rounded-xl border bg-muted/40 p-4 text-sm">
                <p className="font-medium">Your note</p>
                <p className="mt-1 text-muted-foreground">{o.note}</p>
              </div>
            )}

            {canReorder && (
              <Button
                className="mt-6 w-full"
                size="lg"
                onClick={() => reorder.mutate()}
                disabled={reorder.isPending}
              >
                {reorder.isPending ? "Adding…" : "Reorder into this week"}
              </Button>
            )}
          </>
        )}
      </div>
    </main>
  );
}
