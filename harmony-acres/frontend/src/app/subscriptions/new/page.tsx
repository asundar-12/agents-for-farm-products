"use client";

// Create a subscription. All the form logic lives in <SubscriptionForm>; this
// page just wires its submit to the create API and navigates back on success.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { SubscriptionForm } from "@/components/subscription-form";
import { buttonVariants } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { SubscriptionInput } from "@/lib/types";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

export default function NewSubscriptionPage() {
  const { loading, user } = useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const create = useMutation({
    mutationFn: (data: SubscriptionInput) => api.createSubscription(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
      toast.success("Subscription created.");
      router.push("/subscriptions");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Couldn't create the subscription."),
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
          <h1 className="text-lg font-semibold">New subscription</h1>
        </div>
      </header>

      <div className="mx-auto max-w-md px-4 py-6">
        <SubscriptionForm
          submitLabel="Create subscription"
          submitting={create.isPending}
          onSubmit={(data) => create.mutate(data)}
        />
      </div>
    </main>
  );
}
