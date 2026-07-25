"use client";

// The home screen. A quick read on "what's happening this week" — the ordering
// window, this week's order (still a draft, or submitted), and shortcuts into
// history and subscriptions.

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, ClipboardList, Repeat } from "lucide-react";
import Link from "next/link";

import { BottomNav } from "@/components/bottom-nav";
import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatDeadline, money } from "@/lib/format";
import { ORDER_STATUS } from "@/lib/status";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const { loading: authLoading, user } = useRequireAuth();

  const cycle = useQuery({ queryKey: ["cycle"], queryFn: api.currentCycle, enabled: !!user });
  const draft = useQuery({ queryKey: ["draft"], queryFn: api.draft, enabled: !!user });
  const subs = useQuery({ queryKey: ["subscriptions"], queryFn: api.subscriptions, enabled: !!user });

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  const order = draft.data;
  const isDraft = !order || order.status === "draft";
  const itemCount = order?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  const activeSubs = (subs.data ?? []).filter((s) => s.status === "active").length;
  const firstName = user.full_name.split(" ")[0];

  return (
    <>
      <main className="flex-1 pb-24">
        <div className="mx-auto max-w-md space-y-6 px-4 py-6">
          <header>
            <h1 className="text-2xl font-semibold tracking-tight">Hi {firstName}</h1>
            {cycle.data && (
              <p className="text-sm text-muted-foreground">
                Delivery {formatDate(cycle.data.delivery_date)}
                {cycle.data.is_open
                  ? ` · ordering closes ${formatDeadline(cycle.data.submission_deadline)}`
                  : " · ordering closed for this week"}
              </p>
            )}
          </header>

          {/* This week's order */}
          <section className="rounded-2xl border bg-card p-5">
            <div className="flex items-center justify-between">
              <h2 className="font-medium">This week&apos;s order</h2>
              {order && (
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-medium",
                    ORDER_STATUS[order.status].className,
                  )}
                >
                  {ORDER_STATUS[order.status].label}
                </span>
              )}
            </div>

            {draft.isLoading ? (
              <Skeleton className="mt-4 h-6 w-40" />
            ) : itemCount === 0 ? (
              <p className="mt-3 text-sm text-muted-foreground">
                You haven&apos;t added anything yet.
              </p>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                {itemCount} {itemCount === 1 ? "item" : "items"} ·{" "}
                <span className="font-semibold text-foreground">{money(order!.total_amount)}</span>
              </p>
            )}

            <Link
              href="/order"
              className={cn(buttonVariants(), "mt-4 w-full")}
            >
              {itemCount === 0
                ? "Start this week's order"
                : isDraft
                  ? "Continue order"
                  : "View submitted order"}
            </Link>
          </section>

          {/* Quick links */}
          <section className="grid gap-3">
            <DashLink
              href="/orders"
              icon={<ClipboardList className="size-5" />}
              title="Order history"
              subtitle="Past weeks and receipts"
            />
            <DashLink
              href="/subscriptions"
              icon={<Repeat className="size-5" />}
              title="Subscriptions"
              subtitle={
                subs.isLoading
                  ? "Loading…"
                  : `${activeSubs} active ${activeSubs === 1 ? "plan" : "plans"}`
              }
            />
          </section>

          <Link
            href="/assistant"
            className={cn(buttonVariants({ variant: "outline" }), "w-full")}
          >
            Ask the assistant
          </Link>
        </div>
      </main>
      <BottomNav />
    </>
  );
}

function DashLink({
  href,
  icon,
  title,
  subtitle,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-xl border bg-card p-4 transition-colors hover:bg-accent"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium leading-tight">{title}</span>
        <span className="block text-sm text-muted-foreground">{subtitle}</span>
      </span>
      <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
    </Link>
  );
}
