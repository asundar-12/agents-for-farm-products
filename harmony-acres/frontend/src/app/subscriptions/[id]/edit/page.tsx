"use client";

// Edit an existing subscription. Loads the plan, feeds its current values into
// the shared form as initial state, and saves changes with the update API.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo } from "react";
import { toast } from "sonner";

import { SubscriptionForm, type SubscriptionFormValues } from "@/components/subscription-form";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import type { SubscriptionInput } from "@/lib/types";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

export default function EditSubscriptionPage() {
  const { loading, user } = useRequireAuth();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const sub = useQuery({
    queryKey: ["subscription", params.id],
    queryFn: () => api.subscription(params.id),
    enabled: !!user && !!params.id,
  });

  // Translate the loaded subscription into the form's initial-values shape:
  // items go from a list to a product_id -> quantity map.
  const initial: Partial<SubscriptionFormValues> | undefined = useMemo(() => {
    if (!sub.data) return undefined;
    const items: Record<string, number> = {};
    for (const i of sub.data.items) items[i.product_id] = i.quantity;
    return {
      pickup_location: sub.data.pickup_location,
      frequency: sub.data.frequency,
      next_delivery_date: sub.data.next_delivery_date,
      items,
    };
  }, [sub.data]);

  const update = useMutation({
    mutationFn: (data: SubscriptionInput) => api.updateSubscription(params.id, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      await queryClient.invalidateQueries({ queryKey: ["subscription", params.id] });
      toast.success("Subscription updated.");
      router.push("/subscriptions");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Couldn't save your changes."),
  });

  if (loading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 pb-16">
      <header className="sticky top-0 z-10 border-b bg-background/80 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-md items-center gap-3">
          <Link
            href="/subscriptions"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
            aria-label="Back to subscriptions"
          >
            <ArrowLeft className="size-5" />
          </Link>
          <h1 className="text-lg font-semibold">Edit subscription</h1>
        </div>
      </header>

      <div className="mx-auto max-w-md px-4 py-6">
        {sub.isLoading || !initial ? (
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
        ) : (
          // `key` forces a fresh form once real data arrives, so the initial
          // values seed correctly instead of being ignored after first render.
          <SubscriptionForm
            key={sub.data!.id}
            initial={initial}
            submitLabel="Save changes"
            submitting={update.isPending}
            onSubmit={(data) => update.mutate(data)}
          />
        )}
      </div>
    </main>
  );
}
