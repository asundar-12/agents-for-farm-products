"use client";

// Shared form for creating and editing a subscription. Both /subscriptions/new
// and /subscriptions/[id]/edit render this; the only difference is the initial
// values and what the submit button says. Keeping it in one place means the
// Wednesday-only date rule and the item picker can't drift between the two.

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { QuantityStepper } from "@/components/quantity-stepper";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { formatDateOnly, money, upcomingWednesdays } from "@/lib/format";
import type { SubscriptionFrequency, SubscriptionInput } from "@/lib/types";

const FREQUENCIES: { value: SubscriptionFrequency; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Every 2 weeks" },
  { value: "monthly", label: "Monthly" },
];

export interface SubscriptionFormValues {
  pickup_location: string;
  frequency: SubscriptionFrequency;
  next_delivery_date: string;
  items: Record<string, number>; // product_id -> quantity
}

interface Props {
  initial?: Partial<SubscriptionFormValues>;
  submitLabel: string;
  submitting: boolean;
  onSubmit: (data: SubscriptionInput) => void;
}

export function SubscriptionForm({ initial, submitLabel, submitting, onSubmit }: Props) {
  const products = useQuery({ queryKey: ["products"], queryFn: api.products });

  // The Wednesday options. If the subscription's existing date isn't in the
  // generated list (e.g. it's further out), fold it in so it stays selected.
  const wednesdays = useMemo(() => {
    const base = upcomingWednesdays(10);
    if (initial?.next_delivery_date && !base.includes(initial.next_delivery_date)) {
      return [initial.next_delivery_date, ...base];
    }
    return base;
  }, [initial?.next_delivery_date]);

  const [pickup, setPickup] = useState(initial?.pickup_location ?? "Farm stand");
  const [frequency, setFrequency] = useState<SubscriptionFrequency>(
    initial?.frequency ?? "weekly",
  );
  const [date, setDate] = useState(initial?.next_delivery_date ?? wednesdays[0]);
  const [items, setItems] = useState<Record<string, number>>(initial?.items ?? {});
  const [error, setError] = useState<string | null>(null);

  const catalog = products.data ?? [];
  const available = catalog.filter((p) => p.is_available);

  const total = useMemo(() => {
    const byId = new Map(catalog.map((p) => [p.id, p]));
    let sum = 0;
    for (const [id, qty] of Object.entries(items)) {
      const p = byId.get(id);
      if (p) sum += parseFloat(p.unit_price) * qty;
    }
    return sum;
  }, [items, catalog]);

  function setQty(productId: string, qty: number) {
    setItems((prev) => {
      const next = { ...prev };
      if (qty <= 0) delete next[productId];
      else next[productId] = qty;
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const chosen = Object.entries(items).filter(([, q]) => q > 0);
    if (chosen.length === 0) {
      setError("Add at least one item to the plan.");
      return;
    }
    setError(null);
    onSubmit({
      pickup_location: pickup,
      frequency,
      next_delivery_date: date,
      items: chosen.map(([product_id, quantity]) => ({ product_id, quantity })),
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <Label htmlFor="pickup">Pickup location</Label>
        <Input id="pickup" value={pickup} onChange={(e) => setPickup(e.target.value)} required />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="frequency">How often</Label>
          <select
            id="frequency"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as SubscriptionFrequency)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {FREQUENCIES.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="date">Next delivery</Label>
          {/* Only Wednesdays — delivery day. A dropdown makes an invalid day
              impossible, rather than validating a free date input after the fact. */}
          <select
            id="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {wednesdays.map((w) => (
              <option key={w} value={w}>
                {formatDateOnly(w)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-2">
        <Label>Items</Label>
        {products.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading catalog…</p>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {available.map((p) => (
              <li key={p.id} className="flex items-center justify-between gap-3 p-3">
                <div className="min-w-0">
                  <p className="truncate font-medium leading-tight">{p.name}</p>
                  <p className="text-sm text-muted-foreground">{money(p.unit_price)}</p>
                </div>
                <QuantityStepper
                  value={items[p.id] ?? 0}
                  onChange={(q) => setQty(p.id, q)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">Est. per delivery</span>
        <span className="text-lg font-semibold tabular-nums">{money(total)}</span>
      </div>

      <Button type="submit" size="lg" className="w-full" disabled={submitting}>
        {submitting ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
