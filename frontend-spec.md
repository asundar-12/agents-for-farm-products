# Farm Product Agent — Frontend Page Specification

> Paste the **Global context** section plus **one page section** per v0 generation.
> Don't paste the whole file at once — v0 goes shallow on multi-screen prompts.
> Suggested build order: `/order` → `/order/review` → `/dashboard` → `/subscriptions`
> → `/assistant` → admin pages.

---

## Global context

Internal weekly ordering platform for a small farm-products co-op. Customers place a
weekly grocery order before a deadline; an admin aggregates everyone's orders into one
consolidated shopping list and manually places it on the real farm's website.

**Stack:** Next.js 15 App Router, React 19, TypeScript, Tailwind, shadcn/ui, Lucide
React, React Hook Form + Zod, Framer Motion (light use).

*(For v0: omit next-pwa and TanStack Query from what you paste — v0 generates
components, not app infrastructure. Wire data fetching yourself after export. Also add
"use mock data inline" or v0 will invent fetch calls to endpoints that don't exist.)*

**Design tokens** (existing brand):

```
bg          #f7f5f0   warm off-white
surface     #ffffff
border      #e0dcd3
text        #2b2a26
muted       #7a766c
accent      #4c7a3f   farm green
accent-dark #3b6030
```

For v0, phrase these as prose rather than a code block: "warm off-white background
#f7f5f0, farm green accent #4c7a3f, borders #e0dcd3."

Rounded 12px cards, soft shadow `0 2px 12px rgba(0,0,0,0.06)`, system font stack.

**Rules:** Mobile-first. Touch targets 44px minimum. Bottom nav on mobile, sidebar on
desktop. Minimal typing — most interaction is taps. Auth is JWT bearer; two roles,
`customer` and `admin`, which see completely different navigation.

**Weekly cycle** is the spine of the whole app: every week has a `submission_deadline`.
Before it, customers edit freely. After it, everything is locked and the admin takes
over.

---

# CURRENT STATE (one page, to be replaced)

## `/` — Chat demo

Single static HTML file. Centered login card (email + password) that swaps to a
full-screen chat column: message bubbles (user = green right-aligned, assistant = pale
green left-aligned), text input with send button. No catalog, no navigation, no order
UI. This is a throwaway prototype — the assistant becomes one route among many.

---

# PLANNED — CUSTOMER PORTAL

## `/login`

Centered card on the warm background. Farm wordmark, email + password fields, "Sign in"
button in accent green, link to register. Inline validation, error banner for bad
credentials. Full-bleed and vertically centered on mobile.

## `/register`

Same card treatment. Full name, email, password, confirm password. Password strength
hint. On success, auto-login and route to `/order`.

## `/dashboard` — Home

The at-a-glance week view. Top: a **countdown banner** — "Orders close Tuesday 8pm ·
2 days left" — in accent green when open, muted grey and locked when closed.

Then stacked cards:

- **This week's order** — status pill (Draft / Submitted), item count, running total,
  primary button "Continue order" or "View submitted order"
- **Active subscriptions** — compact list with next delivery date, quick pause toggle
- **Recent orders** — last 3, tappable to detail
- Empty state when nothing exists yet: illustration + "Start your first order"

## `/order` — Product catalog ⭐ *primary screen*

The most important page in the app. This is how ordering actually happens.

**Header:** sticky, contains search input and horizontal scrolling category chips
(All · Dairy · Eggs · Pantry · Other).

**Grid:** responsive product cards — 1 column on small phones, 2 on large phones, 3 on
tablet, 4 on desktop. Each card:

- Product image, 1:1 aspect ratio, top of card, rounded
- Product name, prominent
- Category label, small and muted
- Price: **"$5.99"**. The size/measure is already part of the product name as the
  catalog encodes it today ("Whole Milk (1 Gal)", "Butter (1 lb)"), so appending a
  unit would read as "$5.99 / each" or duplicate what the name already says. The
  card renders `"$X / {unit}"` only when a product carries a real unit; with every
  product currently at the `"each"` default, that means price alone.
- Quantity stepper at the bottom: `[−] 2 [+]` — large circular buttons, 44px+, accent
  green. The `−` is disabled at zero. Quantity animates on change (subtle scale pop).

**Behavior:** any product with quantity > 0 is automatically in the weekly order. There
is no separate "add to cart" action. Quantity changes optimistically update the UI and
persist to the draft in the background with a debounce; a small "Saved" indicator
confirms.

**Sticky bottom bar** (above the nav on mobile): item count + running total on the left,
"Review order" button on the right. Slides up with a spring animation the moment the
first item is added.

**Locked state:** after the deadline, steppers become read-only and a banner explains
orders are closed for the week.

## `/order/review` — Order summary & submit

Line-item list: thumbnail, name, quantity stepper (still editable here), line subtotal,
remove button. Order total. Optional note-to-admin textarea.

Two actions: **Save draft** (secondary) and **Submit order** (primary, accent green).
Submit opens a confirmation dialog — "Once submitted you can still edit until Tuesday
8pm" — then a success screen with a checkmark animation.

## `/orders` — Order history

Reverse-chronological list grouped by week. Each row: week-of date, status pill, item
count, total. Status pills use distinct colors across the lifecycle (Draft, Submitted,
Aggregated, Approved, Ordered, Received, Closed). Filter chips at top. Infinite scroll or
pagination.

## `/orders/[id]` — Order detail

Read-only. Week header, status timeline (horizontal stepper showing lifecycle position,
completed steps in accent green), line items with quantities and locked-in prices, total.
"Reorder these items into this week's draft" button when the current week is open.

## `/subscriptions` — Subscription list

Card per subscription: item summary line ("2 gal Whole Milk, 1 dz Eggs"), frequency badge
(Weekly / Biweekly / Monthly), next delivery date, status pill (Active / Paused /
Cancelled). Each card has quick actions — Pause, Resume, Edit. Paused cards render dimmed
with a "Paused until Mar 14" note. FAB or header button to create new.

## `/subscriptions/new` and `/subscriptions/[id]/edit`

Multi-step on mobile, single form on desktop:

1. **Pick products** — same catalog grid and stepper as `/order`, reused component
2. **Schedule** — frequency selector (segmented control), first delivery date picker
   restricted to **Wednesdays only** (all other days disabled — this is a hard business
   rule)
3. **Pickup location** — select
4. **Review & confirm** — summary card, per-delivery total

Edit mode pre-fills and shows a destructive "Cancel subscription" action at the bottom
behind a confirm dialog warning that cancellation is permanent.

## `/assistant` — Customer AI chat

Full-height chat. Assistant bubbles pale green left, user bubbles solid green right.
Streaming responses with a typing indicator. Suggested-prompt chips on the empty state:
"Add two gallons of whole milk" · "Pause my subscription next week" · "Show my current
order" · "When's my next delivery?"

When the assistant modifies an order or subscription, render an inline **result card** in
the thread rather than plain text — the changed order with its new total, tappable
through to `/order`. Input pinned to the bottom above the nav.

## `/account`

Name, email, addresses list with default badge, add-address form, notification
preferences, sign out. Plain settings layout.

## Customer navigation

Bottom tab bar, 4 items, Lucide icons: **Home** (`home`) · **Order**
(`shopping-basket`) · **Subscriptions** (`repeat`) · **AI** (`sparkles`). Active tab in
accent green. Badge dot on Order when a draft has unsubmitted items. Collapses to a left
sidebar at `md` and above.

---

# PLANNED — ADMIN PORTAL

Desktop-first. Denser, more tabular. Sidebar navigation, not bottom tabs.

## `/admin` — Weekly dashboard

Top row of stat tiles: Orders submitted (with "18 of 24 customers"), Total units,
Estimated cost, Days until deadline.

**Lifecycle tracker** — prominent horizontal stepper across the full week status: Open →
Closed → Aggregated → Approved → Ordered → Received → Closed. Current stage highlighted,
completed stages in accent green.

**AI weekly summary panel** — generated prose in a bordered card: what's being ordered,
notable changes from last week, anything needing attention. "Regenerate" button.

**Alerts** — demand spike callouts ("Whole milk up 40% vs last week") and a
non-submitters list with names.

Primary action button changes by stage: "Aggregate now" → "Approve weekly order" → "Mark
as ordered" → "Mark received" → "Close week".

## `/admin/shopping-list` — Consolidated list ⭐

The page the admin actually works from while typing the order into the real farm website.

Dense table, sorted by category: Product · Total quantity · Unit · Unit price · Line
total, with a **grand total row**. Each row expands to show the per-customer breakdown
(who ordered how much, and which lines came from subscriptions vs one-time orders).

Needs a **print-friendly / high-contrast mode** and a "copy as plain text" button — the
admin is transcribing this into another site. Checkbox per row so they can track what
they've entered. Sticky header on scroll.

## `/admin/weeks` — Week history

Table of past cycles: week-of, status, customer count, total units, total cost. Row click
→ `/admin/weeks/[id]`, a read-only archive of that week's dashboard and shopping list.

## `/admin/customers`

Table: name, email, this-week submission status, active subscription count, joined date.
Search and filter by "hasn't submitted". Row expands to that customer's recent order
history.

## `/admin/assistant` — Admin AI chat

Same chat shell as the customer assistant, different suggested prompts: "How many gallons
of whole milk this week?" · "Summarize this week's orders" · "Which products increased
the most?" · "Who hasn't submitted?"

Responses that contain tabular data render as actual tables in the thread, not markdown
text. Responses with comparisons may render a small bar chart.

## Admin navigation

Left sidebar: **Dashboard** (`layout-dashboard`) · **Shopping list** (`list-checks`) ·
**Weeks** (`calendar`) · **Customers** (`users`) · **AI** (`sparkles`). Collapsible to
icon-only.

---

# Cross-cutting

**States:** every list needs a designed empty state, skeleton loaders (not spinners)
while data fetches, and an error state with retry. Never render a bare blank screen.

**Offline (PWA):** installable, app icon, splash screen. Catalog cached for offline
browsing; quantity changes queue and sync when the connection returns, with a visible
"Offline — changes will sync" banner.

**Motion:** restrained. Quantity pop, sticky bar slide-in, page transitions, success
checkmark. No decorative animation.

**The two hard business rules to surface in the UI:** delivery dates are Wednesdays only,
and the weekly submission deadline locks all editing. Both should be visible and enforced
in the interface, not just rejected by the server.

---

# What v0 won't get right

Expect to hand-build these after export — they're logic, not layout:

- Debounced optimistic quantity persistence to the draft order
- Wednesday-only date restriction in the subscription picker
- Deadline lock cascading across every screen
- Offline sync queue

v0 output is a fresh Next.js app. This repo currently has a FastAPI backend and a single
static HTML file for a frontend, so you'll be pulling generated components into a new
`frontend/` app you still need to scaffold and point at the API.
