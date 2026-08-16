// Client-side mirror of aggregation_service.subscription_due_in_cycle — used
// on Home to decide which subscription lines land in this week's demand.

import type { CycleSummary, Subscription, SubscriptionFrequency } from "./types";

const FREQUENCY_INTERVAL_DAYS: Record<SubscriptionFrequency, number> = {
  weekly: 7,
  biweekly: 14,
  monthly: 28,
};

/** Parse a "YYYY-MM-DD" (or ISO) string as local midnight. */
function localDate(iso: string): Date {
  const value = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00` : iso;
  return new Date(value);
}

export function subscriptionDueInCycle(
  subscription: Subscription,
  cycle: Pick<CycleSummary, "delivery_date">,
): boolean {
  if (subscription.status !== "active") return false;

  const daysOut = Math.round(
    (localDate(cycle.delivery_date).getTime() -
      localDate(subscription.next_delivery_date).getTime()) /
      (1000 * 60 * 60 * 24),
  );
  if (daysOut < 0) return false;
  const interval = FREQUENCY_INTERVAL_DAYS[subscription.frequency];
  return daysOut % interval === 0;
}
