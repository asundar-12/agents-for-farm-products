"use client";

// The fixed tab bar at the bottom of the customer app. It reads the current URL
// with usePathname and highlights the matching tab. Order history lives one tap
// deeper (off the dashboard), so it isn't a top-level tab — five is already the
// comfortable maximum on a phone.

import { Home, MessageCircle, Repeat, ShoppingBasket, User } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/order", label: "Order", icon: ShoppingBasket },
  { href: "/subscriptions", label: "Plans", icon: Repeat },
  { href: "/assistant", label: "Assistant", icon: MessageCircle },
  { href: "/account", label: "Account", icon: User },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 backdrop-blur">
      <div className="mx-auto grid max-w-md grid-cols-5">
        {TABS.map(({ href, label, icon: Icon }) => {
          // Highlight the tab whose section we're in — e.g. /subscriptions/new
          // still lights up "Plans".
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center gap-1 py-2 text-xs transition-colors",
                active ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="size-5" strokeWidth={active ? 2.4 : 1.8} />
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
