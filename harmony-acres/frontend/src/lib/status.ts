// Maps a status value to a human label and a Tailwind color class, so the
// colored pills look the same everywhere they appear. Kept as plain data (not
// components) so any screen can use it however it likes.

import type { CycleStatus, OrderStatus, SubscriptionStatus } from "./types";

interface Pill {
  label: string;
  className: string;
}

// A customer order's own lifecycle. Only draft/submitted are reachable in the
// weekly model, but the older values still exist on the type, so we cover them.
export const ORDER_STATUS: Record<OrderStatus, Pill> = {
  draft: { label: "Draft", className: "bg-muted text-muted-foreground" },
  submitted: { label: "Submitted", className: "bg-emerald-100 text-emerald-700" },
  pending: { label: "Pending", className: "bg-amber-100 text-amber-700" },
  confirmed: { label: "Confirmed", className: "bg-blue-100 text-blue-700" },
  ready: { label: "Ready", className: "bg-blue-100 text-blue-700" },
  picked_up: { label: "Picked up", className: "bg-emerald-100 text-emerald-700" },
  cancelled: { label: "Cancelled", className: "bg-red-100 text-red-700" },
};

// The farm-side weekly cycle lifecycle.
export const CYCLE_STATUS: Record<CycleStatus, Pill> = {
  open: { label: "Open", className: "bg-emerald-100 text-emerald-700" },
  locked: { label: "Locked", className: "bg-amber-100 text-amber-700" },
  aggregated: { label: "Aggregated", className: "bg-blue-100 text-blue-700" },
  approved: { label: "Approved", className: "bg-violet-100 text-violet-700" },
  ordered: { label: "Ordered", className: "bg-indigo-100 text-indigo-700" },
  received: { label: "Received", className: "bg-teal-100 text-teal-700" },
  closed: { label: "Closed", className: "bg-muted text-muted-foreground" },
};

export const SUBSCRIPTION_STATUS: Record<SubscriptionStatus, Pill> = {
  active: { label: "Active", className: "bg-emerald-100 text-emerald-700" },
  paused: { label: "Paused", className: "bg-amber-100 text-amber-700" },
  cancelled: { label: "Cancelled", className: "bg-muted text-muted-foreground" },
};
