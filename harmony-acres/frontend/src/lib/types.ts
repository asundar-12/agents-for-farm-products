// Mirror of the backend's Pydantic read schemas. Hand-kept in sync with
// app/schemas/*.py — there's no codegen, so if a field changes on the backend
// it changes here too.

export type UserRole = "customer" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export type ProductCategory = "dairy" | "eggs" | "pantry" | "other";

export interface Product {
  id: string;
  name: string;
  category: ProductCategory;
  description: string | null;
  unit_price: string; // Decimal serializes to string
  unit: string;
  image_url: string | null;
  is_available: boolean;
  created_at: string;
}

export type CycleStatus =
  | "open"
  | "locked"
  | "aggregated"
  | "approved"
  | "ordered"
  | "received"
  | "closed";

export interface CycleSummary {
  id: string;
  week_start: string;
  submission_deadline: string;
  delivery_date: string;
  status: CycleStatus;
  is_open: boolean;
}

export type OrderStatus =
  | "draft"
  | "submitted"
  | "pending"
  | "confirmed"
  | "ready"
  | "picked_up"
  | "cancelled";

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  product_unit: string;
  quantity: number;
  unit_price: string;
}

export interface Order {
  id: string;
  user_id: string;
  subscription_id: string | null;
  weekly_cycle_id: string | null;
  order_date: string;
  status: OrderStatus;
  note: string | null;
  total_amount: string;
  refund_amount: string | null;
  submitted_at: string | null;
  created_at: string;
  items: OrderItem[];
}

// --- Subscriptions ---

export type SubscriptionFrequency = "weekly" | "biweekly" | "monthly";
export type SubscriptionStatus = "active" | "paused" | "cancelled";

export interface SubscriptionItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
}

export interface Subscription {
  id: string;
  user_id: string;
  frequency: SubscriptionFrequency;
  next_delivery_date: string; // date-only, "YYYY-MM-DD"
  status: SubscriptionStatus;
  paused_until: string | null;
  created_at: string;
  updated_at: string;
  items: SubscriptionItem[];
}

// The shape we POST/PATCH when creating or editing a subscription.
export interface SubscriptionInput {
  frequency: SubscriptionFrequency;
  next_delivery_date: string;
  items: { product_id: string; quantity: number }[];
}

// --- Admin / weekly aggregation ---
// These mirror app/schemas/weekly.py. Prices and quantities that the backend
// serializes from Decimal come across as strings.

export interface WeeklyCycle {
  id: string;
  week_start: string;
  submission_deadline: string;
  delivery_date: string;
  status: CycleStatus;
  admin_notes: string | null;
  approved_at: string | null;
  ordered_at: string | null;
  received_at: string | null;
  created_at: string;
}

// Headline numbers for the admin dashboard.
export interface AdminDashboard {
  cycle: WeeklyCycle;
  total_cost: string;
  product_count: number;
  total_units: number;
  customer_count: number;
  // Unit totals from the shopping list (sum of order/subscription quantities).
  order_count: number;
  subscription_count: number;
  non_submitter_count: number;
  spike_count: number;
}

// One customer's share of a single product's weekly total.
export interface CustomerBreakdownEntry {
  user_id: string;
  full_name: string;
  email: string;
  quantity: number;
  source: "order" | "subscription";
}

export interface ShoppingListLine {
  product_id: string;
  product_name: string;
  product_unit: string;
  category: string;
  unit_price: string;
  order_quantity: number;
  subscription_quantity: number;
  total_quantity: number;
  adjusted_quantity: number | null;
  effective_quantity: number;
  line_total: string;
  previous_total: number | null;
  delta: number | null;
  delta_pct: number | null;
  is_spike: boolean;
  customers: CustomerBreakdownEntry[];
}

export interface ShoppingList {
  cycle: WeeklyCycle;
  lines: ShoppingListLine[];
  total_cost: string;
  customer_count: number;
  // Unit totals summed from the lines (not the number of order/subscription records).
  order_count: number;
  subscription_count: number;
}

export interface NonSubmitter {
  user_id: string;
  full_name: string;
  email: string;
  has_draft: boolean;
  draft_item_count: number;
}

export interface AdminCustomer {
  id: string;
  full_name: string;
  email: string;
  created_at: string;
}

export interface AdminSubscriptionsForWeek {
  cycle: WeeklyCycle;
  customers: {
    user_id: string;
    full_name: string;
    email: string;
    subscriptions: Subscription[];
  }[];
}

// --- Assistant chat ---

export interface ChatResponse {
  result: string;
  session_id: string;
}
