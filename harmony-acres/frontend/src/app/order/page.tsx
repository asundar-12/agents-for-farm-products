"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { AdminMenu } from "@/components/admin-menu";
import { QuantityStepper } from "@/components/quantity-stepper";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDeadline, money } from "@/lib/format";
import type { Product, ProductCategory } from "@/lib/types";
import { useOrderDraft } from "@/lib/use-order-draft";
import { useRequireAuth } from "@/lib/use-require-auth";

const CATEGORIES: { value: ProductCategory | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "dairy", label: "Dairy" },
  { value: "eggs", label: "Eggs" },
  { value: "pantry", label: "Pantry" },
  { value: "other", label: "Other" },
];

export default function OrderPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const { logout } = useAuth();
  const [category, setCategory] = useState<ProductCategory | "all">("all");

  const cycle = useQuery({ queryKey: ["cycle"], queryFn: api.currentCycle, enabled: !!user });
  const products = useQuery({ queryKey: ["products"], queryFn: api.products, enabled: !!user });
  const draft = useQuery({ queryKey: ["draft"], queryFn: api.draft, enabled: !!user });

  const { quantities, setQuantity, saveState, totalItems } = useOrderDraft(draft.data);

  const isOpen = cycle.data?.is_open ?? false;

  const visible = useMemo(() => {
    const list = products.data ?? [];
    const inCategory = category === "all" ? list : list.filter((p) => p.category === category);
    // Available items first, then by name — sold-out-for-the-season items sink.
    return [...inCategory].sort(
      (a, b) => Number(b.is_available) - Number(a.is_available) || a.name.localeCompare(b.name),
    );
  }, [products.data, category]);

  const totalPrice = useMemo(() => {
    const byId = new Map((products.data ?? []).map((p) => [p.id, p]));
    let sum = 0;
    for (const [id, qty] of Object.entries(quantities)) {
      const p = byId.get(id);
      if (p) sum += parseFloat(p.unit_price) * qty;
    }
    return sum;
  }, [quantities, products.data]);

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 pb-28">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-lg font-semibold">This week&apos;s order</h1>
            {cycle.data && (
              <p className="text-xs text-muted-foreground">
                Deliver {new Date(cycle.data.delivery_date).toLocaleDateString("en-US", {
                  weekday: "long",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <SaveIndicator state={saveState} />
            {user.role === "admin" && <AdminMenu />}
            <Button variant="ghost" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>

        {/* Category filter */}
        <div className="mx-auto flex max-w-5xl gap-2 overflow-x-auto px-4 pb-3">
          {CATEGORIES.map((c) => (
            <button
              key={c.value}
              onClick={() => setCategory(c.value)}
              className={`whitespace-nowrap rounded-full border px-3 py-1 text-sm transition-colors ${
                category === c.value
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-input bg-background hover:bg-accent"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
      </header>

      {/* Deadline / lock banner */}
      {cycle.data && (
        <div
          className={`mx-auto max-w-5xl px-4 py-2 text-sm ${
            isOpen ? "text-muted-foreground" : "bg-destructive/10 text-destructive"
          }`}
        >
          {isOpen
            ? `Ordering closes ${formatDeadline(cycle.data.submission_deadline)}.`
            : "This week's ordering window has closed. Your next chance opens with the following week."}
        </div>
      )}

      {/* Grid */}
      <div className="mx-auto max-w-5xl px-4 py-4">
        {products.isLoading ? (
          <GridSkeleton />
        ) : visible.length === 0 ? (
          <p className="py-16 text-center text-muted-foreground">No products in this category.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {visible.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                quantity={quantities[p.id] ?? 0}
                onChange={(q) => setQuantity(p.id, q)}
                locked={!isOpen}
              />
            ))}
          </div>
        )}
      </div>

      {/* Sticky summary bar */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div>
            <p className="text-sm text-muted-foreground">
              {totalItems} {totalItems === 1 ? "item" : "items"}
            </p>
            <p className="text-lg font-semibold tabular-nums">{money(totalPrice)}</p>
          </div>
          <div className="flex items-center gap-2">
            {/* Admins can still place their own order (Review order → submit,
                which joins the week's total) and also jump to the week's
                consolidated buy list (totals per item, with customers). */}
            {user.role === "admin" && (
              <Link
                href="/admin/shopping-list"
                className={cn(buttonVariants({ size: "lg", variant: "outline" }))}
              >
                Consolidated list
              </Link>
            )}
            {totalItems === 0 || !isOpen ? (
              <Button size="lg" disabled>
                Review order
              </Button>
            ) : (
              <Link href="/order/review" className={cn(buttonVariants({ size: "lg" }))}>
                Review order
              </Link>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}

function ProductCard({
  product,
  quantity,
  onChange,
  locked,
}: {
  product: Product;
  quantity: number;
  onChange: (q: number) => void;
  locked: boolean;
}) {
  const unavailable = !product.is_available;
  return (
    <div className="flex flex-col rounded-xl border bg-card p-3">
      <div className="mb-3 aspect-square overflow-hidden rounded-lg bg-muted">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- remote images, no loader config for the MVP
          <img
            src={product.image_url}
            alt={product.name}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="grid h-full w-full place-items-center text-3xl font-semibold text-muted-foreground/50">
            {product.name.charAt(0)}
          </div>
        )}
      </div>

      <h2 className="font-medium leading-tight">{product.name}</h2>
      <p className="text-xs capitalize text-muted-foreground">{product.category}</p>
      <p className="mt-1 text-sm font-semibold">
        {money(product.unit_price)}
        {product.unit && product.unit !== "each" && (
          <span className="font-normal text-muted-foreground"> / {product.unit}</span>
        )}
      </p>

      <div className="mt-3">
        {unavailable ? (
          <p className="py-2 text-sm text-muted-foreground">Not available this week</p>
        ) : (
          <QuantityStepper value={quantity} onChange={onChange} disabled={locked} />
        )}
      </div>
    </div>
  );
}

function SaveIndicator({ state }: { state: "idle" | "saving" | "saved" | "error" }) {
  if (state === "idle") return null;
  const text = state === "saving" ? "Saving…" : state === "saved" ? "Saved" : "Save failed";
  const color = state === "error" ? "text-destructive" : "text-muted-foreground";
  return <span className={`text-xs ${color}`}>{text}</span>;
}

function GridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="rounded-xl border p-3">
          <Skeleton className="mb-3 aspect-square w-full rounded-lg" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="mt-2 h-3 w-1/3" />
          <Skeleton className="mt-3 h-11 w-full rounded-full" />
        </div>
      ))}
    </div>
  );
}
