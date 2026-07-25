"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Check, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { QuantityStepper } from "@/components/quantity-stepper";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDeadline, money } from "@/lib/format";
import type { Product } from "@/lib/types";
import { useOrderDraft } from "@/lib/use-order-draft";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

export default function OrderReviewPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const cycle = useQuery({ queryKey: ["cycle"], queryFn: api.currentCycle, enabled: !!user });
  const products = useQuery({ queryKey: ["products"], queryFn: api.products, enabled: !!user });
  const draft = useQuery({ queryKey: ["draft"], queryFn: api.draft, enabled: !!user });

  const { quantities, setQuantity, saveState, totalItems } = useOrderDraft(draft.data);

  const [note, setNote] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const isOpen = cycle.data?.is_open ?? false;
  // The note the user sees: their in-session edit, else the persisted draft note.
  const noteValue = note ?? draft.data?.note ?? "";

  const byId = useMemo(
    () => new Map((products.data ?? []).map((p) => [p.id, p])),
    [products.data],
  );

  // The lines actually in the order: every product with a quantity > 0, joined to
  // its catalog record so we can show thumbnail/name/price.
  const lines = useMemo(() => {
    const out: { product: Product; quantity: number }[] = [];
    for (const [id, qty] of Object.entries(quantities)) {
      const product = byId.get(id);
      if (product && qty > 0) out.push({ product, quantity: qty });
    }
    return out.sort((a, b) => a.product.name.localeCompare(b.product.name));
  }, [quantities, byId]);

  const total = useMemo(
    () => lines.reduce((sum, l) => sum + parseFloat(l.product.unit_price) * l.quantity, 0),
    [lines],
  );

  async function persistNote() {
    // Only hit the wire if the note actually changed this session.
    if (note !== null && note !== (draft.data?.note ?? "")) {
      await api.setDraftDetails({ note });
    }
  }

  async function onSaveDraft() {
    setSavingDraft(true);
    try {
      await persistNote();
      toast.success("Draft saved.");
      router.push("/order");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't save your draft.");
    } finally {
      setSavingDraft(false);
    }
  }

  async function onSubmit() {
    setSubmitting(true);
    try {
      await persistNote();
      await api.submitDraft();
      // The cached draft now reflects the pre-submit state; refetch so /order
      // renders the submitted order when the user goes back.
      await queryClient.invalidateQueries({ queryKey: ["draft"] });
      setConfirming(false);
      setSubmitted(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't submit your order.");
      setConfirming(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  if (submitted) {
    return <SuccessScreen />;
  }

  return (
    <main className="flex-1 pb-40">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center gap-3 px-4 py-3">
          <Link
            href="/order"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "shrink-0")}
            aria-label="Back to order"
          >
            <ArrowLeft className="size-5" />
          </Link>
          <div>
            <h1 className="text-lg font-semibold">Review your order</h1>
            {cycle.data && (
              <p className="text-xs text-muted-foreground">
                Deliver{" "}
                {new Date(cycle.data.delivery_date).toLocaleDateString("en-US", {
                  weekday: "long",
                  month: "short",
                  day: "numeric",
                })}
              </p>
            )}
          </div>
        </div>
      </header>

      {/* Closed-window banner — mirrors /order's lock */}
      {!isOpen && cycle.data && (
        <div className="mx-auto max-w-2xl px-4 py-2 text-sm bg-destructive/10 text-destructive">
          This week&apos;s ordering window has closed. You can no longer edit or submit.
        </div>
      )}

      <div className="mx-auto max-w-2xl px-4 py-4">
        {draft.isLoading || products.isLoading ? (
          <LinesSkeleton />
        ) : lines.length === 0 ? (
          <div className="py-16 text-center">
            <p className="text-muted-foreground">Your order is empty.</p>
            <Link
              href="/order"
              className={cn(buttonVariants({ variant: "outline" }), "mt-4")}
            >
              Browse the catalog
            </Link>
          </div>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {lines.map(({ product, quantity }) => (
              <li key={product.id} className="flex items-center gap-3 p-3">
                <div className="size-16 shrink-0 overflow-hidden rounded-lg bg-muted">
                  {product.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element -- remote images, no loader config for the MVP
                    <img
                      src={product.image_url}
                      alt={product.name}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="grid h-full w-full place-items-center text-xl font-semibold text-muted-foreground/50">
                      {product.name.charAt(0)}
                    </div>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium leading-tight">{product.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {money(product.unit_price)}
                    {product.unit && product.unit !== "each" && ` / ${product.unit}`}
                  </p>
                  <p className="mt-0.5 text-sm font-semibold tabular-nums">
                    {money(parseFloat(product.unit_price) * quantity)}
                  </p>
                </div>

                <div className="flex flex-col items-end gap-2">
                  <QuantityStepper
                    value={quantity}
                    onChange={(q) => setQuantity(product.id, q)}
                    disabled={!isOpen}
                  />
                  <button
                    type="button"
                    onClick={() => setQuantity(product.id, 0)}
                    disabled={!isOpen}
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive disabled:opacity-40"
                    aria-label={`Remove ${product.name}`}
                  >
                    <Trash2 className="size-3.5" /> Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {/* Note to admin */}
        {lines.length > 0 && (
          <div className="mt-6 space-y-2">
            <label htmlFor="note" className="text-sm font-medium">
              Note to the farm <span className="text-muted-foreground">(optional)</span>
            </label>
            <textarea
              id="note"
              value={noteValue}
              onChange={(e) => setNote(e.target.value)}
              disabled={!isOpen}
              rows={3}
              placeholder="Anything the farm should know about this week's order?"
              className="w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            />
          </div>
        )}
      </div>

      {/* Sticky action bar */}
      {lines.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t bg-background/95 backdrop-blur">
          <div className="mx-auto max-w-2xl space-y-3 px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {totalItems} {totalItems === 1 ? "item" : "items"}
                {saveState === "saving" && " · Saving…"}
              </p>
              <p className="text-xl font-semibold tabular-nums">{money(total)}</p>
            </div>
            <div className="flex gap-3">
              <Button
                variant="outline"
                size="lg"
                className="flex-1"
                onClick={onSaveDraft}
                disabled={!isOpen || savingDraft || submitting}
              >
                {savingDraft ? "Saving…" : "Save draft"}
              </Button>
              <Button
                size="lg"
                className="flex-1 bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={() => setConfirming(true)}
                disabled={!isOpen || submitting}
              >
                Submit order
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation dialog */}
      <AnimatePresence>
        {confirming && (
          <motion.div
            className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !submitting && setConfirming(false)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-sm rounded-2xl bg-background p-6 shadow-xl"
              initial={{ scale: 0.95, y: 10 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-lg font-semibold">Submit this order?</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {cycle.data
                  ? `Once submitted you can still edit until ${formatDeadline(
                      cycle.data.submission_deadline,
                    )}.`
                  : "Once submitted you can still edit until the deadline."}
              </p>
              <div className="mt-6 flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => setConfirming(false)}
                  disabled={submitting}
                >
                  Keep editing
                </Button>
                <Button
                  className="flex-1 bg-emerald-600 text-white hover:bg-emerald-700"
                  onClick={onSubmit}
                  disabled={submitting}
                >
                  {submitting ? "Submitting…" : "Submit"}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

function SuccessScreen() {
  return (
    <main className="flex-1 grid place-items-center px-4 py-16 text-center">
      <div className="flex flex-col items-center">
        <motion.div
          className="grid size-20 place-items-center rounded-full bg-emerald-100 text-emerald-600"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 18 }}
        >
          <motion.span
            initial={{ scale: 0, rotate: -20 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ delay: 0.15, type: "spring", stiffness: 300, damping: 15 }}
          >
            <Check className="size-10" strokeWidth={3} />
          </motion.span>
        </motion.div>
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Order submitted</h1>
        <p className="mt-2 max-w-xs text-sm text-muted-foreground">
          You&apos;ll still be able to edit it until the deadline. We&apos;ll roll it into this
          week&apos;s farm order.
        </p>
        <Link href="/order" className={cn(buttonVariants({ size: "lg" }), "mt-8")}>
          Back to my order
        </Link>
      </div>
    </main>
  );
}

function LinesSkeleton() {
  return (
    <div className="space-y-3 rounded-xl border p-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-16 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-3 w-1/4" />
          </div>
          <Skeleton className="h-11 w-32 rounded-full" />
        </div>
      ))}
    </div>
  );
}
