"use client";

// A dropdown shown only to admins on the customer-facing app, so an admin who
// lands on the catalog can jump into the farm dashboard and back. Uses a native
// <details> element so it opens/closes and handles keyboard focus without any
// extra state or click-outside wiring.

import {
  CalendarDays,
  ChevronDown,
  LayoutDashboard,
  ListChecks,
  MessageCircle,
  ShieldCheck,
  ShoppingBasket,
  Users,
} from "lucide-react";
import Link from "next/link";

const LINKS = [
  { href: "/order", label: "Catalog", icon: ShoppingBasket },
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/shopping-list", label: "Shopping list", icon: ListChecks },
  { href: "/admin/weeks", label: "Weeks", icon: CalendarDays },
  { href: "/admin/customers", label: "Customers", icon: Users },
  { href: "/admin/assistant", label: "Assistant", icon: MessageCircle },
];

export function AdminMenu() {
  return (
    <details className="group relative [&>summary]:list-none">
      <summary className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent [&::-webkit-details-marker]:hidden">
        <ShieldCheck className="size-4" />
        Admin
        <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="absolute right-0 z-30 mt-2 w-52 rounded-xl border bg-popover p-1 shadow-lg">
        {LINKS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-foreground transition-colors hover:bg-accent"
          >
            <Icon className="size-4 text-muted-foreground" />
            {label}
          </Link>
        ))}
      </div>
    </details>
  );
}
