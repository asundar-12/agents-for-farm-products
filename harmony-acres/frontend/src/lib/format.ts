// Small formatting helpers. Prices come off the API as decimal strings
// ("5.99"); parse then format as USD.

export function money(value: string | number): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    Number.isFinite(n) ? n : 0,
  );
}

export function formatDate(iso: string): string {
  // A bare "YYYY-MM-DD" is otherwise parsed as UTC midnight, which renders as
  // the day before in western timezones. Anchor it to local time instead.
  const value = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00` : iso;
  return new Date(value).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function formatDeadline(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// A "YYYY-MM-DD" string in local time — the format the API's date-only fields
// expect. Built by hand rather than toISOString() (which is UTC and can shift
// the day across a timezone boundary).
export function toDateInput(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// The next `count` Wednesdays (delivery is Wednesday-only). Starts from the
// coming Wednesday; if today is Wednesday it's included as the first option.
export function upcomingWednesdays(count = 8, from: Date = new Date()): string[] {
  const WEDNESDAY = 3; // Sun=0 … Wed=3
  const start = new Date(from.getFullYear(), from.getMonth(), from.getDate());
  const daysUntilWed = (WEDNESDAY - start.getDay() + 7) % 7;
  start.setDate(start.getDate() + daysUntilWed);

  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i * 7);
    out.push(toDateInput(d));
  }
  return out;
}

// "Wed, Mar 12" from a "YYYY-MM-DD" string, parsed in local time (appending
// T00:00 avoids the browser treating a bare date as UTC).
export function formatDateOnly(ymd: string): string {
  return new Date(`${ymd}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}
