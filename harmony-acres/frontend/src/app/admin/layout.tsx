"use client";

// Shared shell for every /admin page. A Next layout wraps all nested routes, so
// this is the one place the admin guard and the sidebar live. Desktop-oriented:
// a fixed sidebar on the left, content on the right; on small screens the nav
// collapses to a scrollable strip along the top.

import {
  CalendarDays,
  LayoutDashboard,
  ListChecks,
  MessageCircle,
  ShoppingBasket,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { useRequireAdmin } from "@/lib/use-require-admin";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard },
  { href: "/admin/shopping-list", label: "Shopping list", icon: ListChecks },
  { href: "/admin/weeks", label: "Weeks", icon: CalendarDays },
  { href: "/admin/customers", label: "Customers", icon: Users },
  { href: "/admin/assistant", label: "Assistant", icon: MessageCircle },
  { href: "/order", label: "Catalog", icon: ShoppingBasket },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { loading, isAdmin } = useRequireAdmin();
  const { logout, user } = useAuth();
  const pathname = usePathname();

  // Until we know the user is an admin, show nothing but a spinner — the guard
  // is already redirecting anyone who shouldn't be here.
  if (loading || !isAdmin) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  function isActive(href: string) {
    // Exact match for the dashboard root; prefix match for the sections.
    return href === "/admin" ? pathname === href : pathname.startsWith(href);
  }

  return (
    <div className="flex min-h-full flex-col md:flex-row">
      {/* Sidebar (desktop) / top strip (mobile) */}
      <aside className="border-b bg-card md:w-60 md:shrink-0 md:border-b-0 md:border-r print:hidden">
        <div className="flex items-center justify-between px-4 py-4 md:block">
          <div>
            <p className="font-semibold">{user?.full_name || "Farm Product Agent"}</p>
            <p className="text-xs text-muted-foreground">Farm admin</p>
          </div>
          <button
            onClick={logout}
            className="text-sm text-muted-foreground hover:text-foreground md:hidden"
          >
            Sign out
          </button>
        </div>

        <nav className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:px-2 md:pb-0">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors",
                isActive(href)
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          ))}
        </nav>

        <div className="hidden px-4 py-4 md:block">
          <button
            onClick={logout}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
