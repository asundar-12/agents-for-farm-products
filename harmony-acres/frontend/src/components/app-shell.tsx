"use client";

// The one layout every customer screen uses.
//
// Before this existed the app had two unrelated layouts: /order and its review
// step were built wide (max-w-5xl, their own sticky header), and everything
// added later was a fixed 448px phone column with no header at all. On a phone
// they looked the same; on a laptop, moving between them looked like moving
// between two different apps.
//
// So: one header, one bottom nav, one container. Pages differ only in how wide
// that container is allowed to get — `wide` for the product grid, which really
// does want four columns on a desktop, `narrow` for lists, forms and detail
// screens, where a long line of text is harder to read, not easier. Both are
// max-widths, so on a phone every page is still edge-to-edge.

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { BottomNav } from "@/components/bottom-nav";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const CONTAINER = {
  narrow: "max-w-2xl",
  wide: "max-w-5xl",
} as const;

interface Props {
  title: string;
  subtitle?: React.ReactNode;
  /** Renders a back arrow to the left of the title. */
  backHref?: string;
  backLabel?: string;
  /** Right-hand side of the header — save indicators, admin menu, sign out. */
  actions?: React.ReactNode;
  /** Full-width row directly under the header, e.g. category filter chips. */
  toolbar?: React.ReactNode;
  /** A sticky bar pinned above the tab bar, e.g. the order summary. */
  footer?: React.ReactNode;
  width?: keyof typeof CONTAINER;
  children: React.ReactNode;
}

export function AppShell({
  title,
  subtitle,
  backHref,
  backLabel,
  actions,
  toolbar,
  footer,
  width = "narrow",
  children,
}: Props) {
  const container = CONTAINER[width];

  return (
    <>
      {/* Padding reserves room for whatever is pinned to the bottom: the tab
          bar alone (h-14), or the tab bar plus a page's own sticky footer. */}
      <main className={cn("flex-1", footer ? "pb-44" : "pb-24")}>
        <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
          <div className={cn("mx-auto flex items-center gap-3 px-4 py-3", container)}>
            {backHref && (
              <Link
                href={backHref}
                className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "-ml-2 shrink-0")}
                aria-label={backLabel ?? "Back"}
              >
                <ArrowLeft className="size-5" />
              </Link>
            )}
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-lg font-semibold leading-tight">{title}</h1>
              {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
            </div>
            {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
          </div>
          {toolbar && (
            <div className={cn("mx-auto flex gap-2 overflow-x-auto px-4 pb-3", container)}>
              {toolbar}
            </div>
          )}
        </header>

        <div className={cn("mx-auto px-4 py-6", container)}>{children}</div>
      </main>

      {footer && (
        // bottom-14 is the tab bar's height, so the two stack rather than overlap.
        <div className="fixed inset-x-0 bottom-14 z-20 border-t bg-background/95 backdrop-blur">
          <div className={cn("mx-auto px-4 py-3", container)}>{footer}</div>
        </div>
      )}

      <BottomNav />
    </>
  );
}
