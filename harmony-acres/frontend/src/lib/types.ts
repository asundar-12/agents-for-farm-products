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
  pickup_location: string;
  order_date: string;
  status: OrderStatus;
  note: string | null;
  total_amount: string;
  refund_amount: string | null;
  submitted_at: string | null;
  created_at: string;
  items: OrderItem[];
}
