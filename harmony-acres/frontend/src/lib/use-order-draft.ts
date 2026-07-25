"use client";

// The debounced, optimistic quantity persistence behind the order grid — the
// piece the frontend spec calls out as hand-built.
//
// Design: the loaded draft is the baseline; local state holds only the products
// the user has *touched* this session ("overrides"). The displayed quantity is
// override ?? draft-baseline ?? 0, merged with useMemo. This means there's no
// "seed local state from async data" step to fight React's render rules — the
// baseline just comes from the query data, and overrides layer on top.
//
// - Tapping +/- sets an override instantly, so the UI never waits on the wire.
// - Each product has its own debounce timer; rapid taps collapse into one PUT.
// - The PUT sends the *absolute* quantity, so out-of-order responses are
//   harmless — the last value the user chose wins, nothing to reconcile.
// - On failure we drop the override, reverting that product to the server's
//   last-known baseline, and surface a toast.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { api, ApiError } from "./api";
import type { Order } from "./types";

const DEBOUNCE_MS = 500;

export type SaveState = "idle" | "saving" | "saved" | "error";

export function useOrderDraft(draft: Order | undefined) {
  // Only products the user changed this session. Everything else falls back to
  // the draft baseline below.
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [saveState, setSaveState] = useState<SaveState>("idle");

  // Per-product debounce timers and an in-flight counter. Refs because they're
  // only read/written in callbacks (never during render), which keeps them off
  // React's render-purity radar.
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const inflight = useRef(0);

  const baseline = useMemo(() => {
    const base: Record<string, number> = {};
    if (draft) for (const item of draft.items) base[item.product_id] = item.quantity;
    return base;
  }, [draft]);

  // What the grid actually shows: baseline with the user's edits layered on.
  const quantities = useMemo(() => ({ ...baseline, ...overrides }), [baseline, overrides]);

  const flush = useCallback(
    (productId: string, quantity: number) => {
      inflight.current += 1;
      setSaveState("saving");
      api
        .setItem(productId, quantity)
        .catch((err) => {
          // Revert this product to the server's last-known baseline.
          setOverrides((prev) => {
            const next = { ...prev };
            delete next[productId];
            return next;
          });
          setSaveState("error");
          toast.error(err instanceof ApiError ? err.message : "Couldn't save that change.");
        })
        .finally(() => {
          inflight.current -= 1;
          // Flip to "saved" only once every queued write settles, so the
          // indicator doesn't flicker mid-edit.
          if (inflight.current === 0) {
            setSaveState((s) => (s === "error" ? "error" : "saved"));
          }
        });
    },
    [],
  );

  const setQuantity = useCallback(
    (productId: string, quantity: number) => {
      const next = Math.max(0, quantity);
      setOverrides((prev) => ({ ...prev, [productId]: next }));

      clearTimeout(timers.current[productId]);
      timers.current[productId] = setTimeout(() => flush(productId, next), DEBOUNCE_MS);
    },
    [flush],
  );

  // Clear any pending timers on unmount.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const t of Object.values(pending)) clearTimeout(t);
    };
  }, []);

  const totalItems = useMemo(
    () => Object.values(quantities).reduce((sum, q) => sum + q, 0),
    [quantities],
  );

  return { quantities, setQuantity, saveState, totalItems };
}
