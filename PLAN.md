# Farm Product Agent — Implementation Plan

Companion to [frontend-spec.md](frontend-spec.md) (page-by-page UI spec) and
[CLAUDE.md](CLAUDE.md) (product vision). This file tracks *what gets built and in what
order*.

---

## Where the codebase stands

The backend is roughly 70% of the way to the Customer Portal deliverables. What exists
and should **not** be rebuilt:

| Area | Status |
|---|---|
| Auth | JWT + bcrypt, register/login, `require_role()` helper written but unused |
| Users | `User` with `customer`/`admin` roles, `Address` |
| Products | Model, search by name/category, availability endpoint |
| Orders | `Order`/`OrderItem`, price snapshot, `total_amount`, create/list/get/cancel |
| Subscriptions | Full CRUD + pause/resume/cancel, items, frequency |
| Inventory | Model, summary, low-stock flags |
| Customer AI agent | 13 Strands tools, Bedrock, AgentCore Memory STM, deployed to AgentCore Runtime, proxied via `POST /agent/chat` |
| Web UI | Single-file chat-only demo (`web/index.html`, 370 lines) |

### The four real gaps

The vision describes a **weekly consolidated-ordering** model. The code implements a
**per-customer e-commerce/pickup** model. They diverge structurally:

1. **No draft/weekly-order concept.** `OrderStatus` is
   `pending → confirmed → ready → picked_up → cancelled`. The vision needs
   `Draft → Submitted` on the customer order plus a *separate* weekly aggregate entity
   with `Aggregated → Approved → Ordered → Received → Closed`. Two lifecycles currently
   collapsed into one enum.
2. **No aggregation layer.** Nothing sums orders + subscriptions into weekly product
   totals. This is the core of the product.
3. **No admin surface.** No admin router, dashboard, approval flow, or admin agent.
   `require_role("admin")` exists but is never applied — `get_inventory_summary` is
   guarded only by a *prompt instruction*, which is not enforcement.
4. **No catalog UI.** The +/- quantity grid — "the primary ordering experience" —
   doesn't exist. Only the optional chat does.

---

## Decisions made

**Product images and units** — `Product` gains `image_url` and `unit`.

The catalog encodes size in the product *name* today ("Whole Milk (1 Gal)", "Butter
(1 lb)"), and the migration backfilled every row to `unit = "each"`. Rather than
re-cut that data, the UI follows it: the card shows the name as-is and the price
alone. `unit` stays on the model and renders as `"$X / {unit}"` only for products
that carry a real one — so splitting name and unit apart later is a data edit, not
a schema or UI change.

**Inventory: demand-forwarding only.** Farm Product Agent is the upstream supplier; we don't
hold stock. Consequences:

- `order_service.create_order` decrement and `cancel_order` restore both come out
- `check_availability` stops meaning "units on hand" and becomes just
  `Product.is_available` (farm isn't carrying it this season). The agent tool keeps its
  name, changes semantics
- `Inventory` model, `inventory_service`, `routers/inventory.py`, and the
  `get_inventory_summary` tool lose their consumer

**Keep the `Inventory` table and migration in place but stop writing to it**; drop the
router and agent tool. A later stock-tracking MVP then needs no schema archaeology.
Deleting the model outright would mean rebuilding it in a few months.

**Frontend: Next.js 15 PWA** per `frontend.txt` — React 19, TypeScript, Tailwind,
shadcn/ui, Lucide, TanStack Query, React Hook Form + Zod, Framer Motion (light),
next-pwa. Mobile-first.

---

## Phases

### Phase 1 — Weekly domain model

Migration + models.

- `WeeklyCycle` — week_start, submission_deadline, status
  (`open/closed/aggregated/approved/ordered/received/closed`)
- `WeeklyOrderLine` — per-cycle per-product aggregated totals
- `Order.weekly_cycle_id`
- `Order.note` — the note-to-admin textarea on `/order/review`
- `Product.image_url`, `Product.unit`
- `OrderStatus` gains `draft` / `submitted`; existing values retained so current rows
  survive the migration
- Unique constraint: one draft per customer per cycle

### Phase 2 — Order flow rework

`order_service`.

- `get_or_create_draft(user, cycle)`
- `set_item_quantity()` — upsert; quantity 0 removes. This is what the +/- control binds
  to
- `submit_order()` with deadline enforcement; edits blocked post-submission
- Strip stock decrement/restore from create and cancel

### Phase 3 — Aggregation service

New `app/services/aggregation_service.py`.

- Roll up submitted orders + active subscriptions due in-cycle → per-product totals with
  per-customer breakdown
- Week-over-week deltas
- Demand-spike detection
- Non-submitter list

### Phase 4 — Admin API

New `app/routers/admin.py`, every endpoint behind `require_role("admin")`.

- Dashboard totals
- Shopping list with per-customer expansion
- Approve / reject
- Mark-ordered, mark-received, close
- Lifecycle transitions
- **List past cycles + fetch archived cycle** (backs `/admin/weeks`)
- Retire `routers/inventory.py`
- **Admin line override** — `PATCH /admin/cycles/{id}/lines/{product_id}` sets a
  `WeeklyOrderLine.adjusted_quantity` so the admin can change the consolidated buy
  quantity for a product (e.g. a customer phones a post-deadline change). Customer
  orders stay frozen; only the aggregated total moves. Allowed in `aggregated`/
  `approved`, not after `ordered`. Cost and the "received in full" default follow
  `effective_quantity` (override if set, else total); week-over-week deltas keep
  tracking real demand, not the override.

### Phase 5 — Admin AI assistant

- Separate Strands agent (`app/agent/admin_main.py`), own system prompt, admin-only
  toolset over Phase 3, plus a summary-generation tool
- `/agent/chat` routes on the JWT role claim rather than adding a second endpoint
- Drop `get_inventory_summary` from the customer agent — removes the prompt-only guard,
  which was never real enforcement

### Phase 5b — Streaming chat

The spec calls for streaming responses with a typing indicator. Current `/agent/chat`
blocks on `invoke_agent_runtime` and returns a complete string.

- SSE endpoint using `invoke_agent_runtime_with_response_stream`
- Client-side incremental rendering

Deferrable — the UI works without it, just less pleasantly.

### Phase 6a — Customer PWA: ordering spine

Scaffold `frontend/`. Routes: `/login`, `/register`, `/order`, `/order/review`.

`/order` is the most important screen in the app — catalog grid, 44px+ steppers, sticky
summary bar, optimistic debounced persistence to the draft.

### Phase 6b — Customer PWA: everything else

`/dashboard`, `/orders`, `/orders/[id]`, `/subscriptions`, `/subscriptions/new`,
`/subscriptions/[id]/edit`, `/assistant`, `/account`. Bottom nav, PWA manifest, offline
catalog cache.

`web/index.html` is retired once `/assistant` lands.

### Phase 7 — Admin dashboard

Same Next.js app, desktop-oriented layout. `/admin`, `/admin/shopping-list`,
`/admin/weeks`, `/admin/customers`, `/admin/assistant`. Sidebar nav.

`/admin/shopping-list` needs print-friendly mode and copy-as-plain-text — the admin
transcribes it into the real farm website by hand.

---

## Sequencing

```
1 → 2 → 3 → ┬→ 4 → 7
            └→ 5 → 5b

6a → 6b    (parallel with 4/5, once API shapes are fixed)
```

- Phases 1 and 2 are strictly sequential
- Phase 3 depends on 1
- Phases 4 and 5 both depend on 3, and are independent of each other
- Phase 6a can start against agreed API shapes in parallel with 4–5
- Phase 7 needs Phase 4 live
- Phase 5b is optional polish, deferrable past launch

---

## Things v0 won't produce

Hand-built after export, per `frontend-spec.md` — these are logic, not layout:

- Debounced optimistic quantity persistence
- Wednesday-only date restriction in the subscription picker
- Deadline lock cascading across every screen
- Offline sync queue
