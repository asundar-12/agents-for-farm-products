import uuid
from datetime import date

from fastapi import HTTPException
from pydantic import ValidationError
from strands import tool

from app.core.db import AsyncSessionLocal
from app.models.product import ProductCategory
from app.schemas.inventory import InventorySummaryItem
from app.schemas.order import OrderCreate, OrderItemCreate, OrderRead
from app.schemas.product import ProductAvailability, ProductRead
from app.schemas.subscription import SubscriptionCreate, SubscriptionItemCreate, SubscriptionRead
from app.services import inventory_service, order_service, product_service, subscription_service


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"'{value}' is not a valid {field_name} — expected a UUID.") from exc


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"'{value}' is not a valid {field_name} — expected YYYY-MM-DD.") from exc


def _parse_items(items: list[dict], item_cls: type) -> list:
    try:
        return [item_cls(**item) for item in items]
    except ValidationError as exc:
        raise ValueError(f"Invalid item in items list: {exc.errors()[0]['msg']}") from exc
    except TypeError as exc:
        raise ValueError(f"Each item must be an object with product_id and quantity: {exc}") from exc


@tool
async def get_subscription(user_id: str, subscription_id: str | None = None) -> dict | str:
    """Look up a customer's subscription(s).

    If subscription_id is given, returns that one subscription (only if it
    belongs to user_id). If subscription_id is omitted, returns every
    subscription belonging to user_id — use this first when the user refers to
    "my subscription" without an ID, so you can see how many they have before
    deciding whether to ask which one they mean.

    Args:
        user_id: UUID of the customer making the request.
        subscription_id: UUID of a specific subscription, or omit to list all.

    Returns:
        A dict with subscription details (or a list of them), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        async with AsyncSessionLocal() as db:
            if subscription_id is not None:
                sid = _parse_uuid(subscription_id, "subscription_id")
                subscription = await subscription_service.get_subscription_by_id(db, sid)
                subscription_service.assert_owned_by(subscription, uid)
                return SubscriptionRead.model_validate(subscription).model_dump(mode="json")

            subscriptions = await subscription_service.list_subscriptions_for_user(db, uid)
            return {
                "subscriptions": [SubscriptionRead.model_validate(s).model_dump(mode="json") for s in subscriptions]
            }
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong looking up the subscription. Please try again."


@tool
async def get_order_status(order_id: str) -> dict | str:
    """Look up the status of an order by its ID.

    Note: this tool does not take a user_id, so it does not verify the order
    belongs to any particular customer — in this MVP the agent trusts that an
    order_id was legitimately surfaced earlier in the conversation (e.g. from
    get_subscription or a prior order lookup). A production, multi-tenant
    deployment would thread the caller's identity through here too.

    Args:
        order_id: UUID of the order to look up.

    Returns:
        A dict with order status and line items, or an error string.
    """
    try:
        oid = _parse_uuid(order_id, "order_id")
        async with AsyncSessionLocal() as db:
            order = await order_service.get_order_by_id(db, oid)
            return OrderRead.model_validate(order).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong looking up the order. Please try again."


@tool
async def get_next_delivery(user_id: str) -> dict | str:
    """Find the soonest upcoming delivery across a customer's active subscriptions.

    Paused or cancelled subscriptions are ignored — only active subscriptions
    have a real upcoming delivery.

    Args:
        user_id: UUID of the customer making the request.

    Returns:
        A dict with the subscription ID, pickup location, and next delivery
        date, a message if there's no upcoming delivery, or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        async with AsyncSessionLocal() as db:
            subscription = await subscription_service.get_next_delivery_for_user(db, uid)
            if subscription is None:
                return "This customer has no active subscriptions, so there's no upcoming delivery."
            return {
                "subscription_id": str(subscription.id),
                "pickup_location": subscription.pickup_location,
                "next_delivery_date": subscription.next_delivery_date.isoformat(),
                "frequency": subscription.frequency.value,
            }
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong looking up the next delivery. Please try again."


@tool
async def search_products(query: str | None = None, category: str | None = None) -> dict | str:
    """Search the product catalog by name substring and/or category.

    Args:
        query: Case-insensitive substring to match against product names. Omit to skip name filtering.
        category: One of "dairy", "eggs", "pantry", "other". Omit to include all categories.

    Returns:
        A dict with the list of matching products, or an error string.
    """
    try:
        parsed_category: ProductCategory | None = None
        if category is not None:
            try:
                parsed_category = ProductCategory(category.lower())
            except ValueError:
                valid = ", ".join(c.value for c in ProductCategory)
                return f"Error: '{category}' is not a valid category. Valid categories: {valid}."

        async with AsyncSessionLocal() as db:
            products = await product_service.search_products(db, query=query, category=parsed_category)
            return {"products": [ProductRead.model_validate(p).model_dump(mode="json") for p in products]}
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except Exception:
        return "Error: something went wrong searching products. Please try again."


@tool
async def check_availability(product_id: str) -> dict | str:
    """Check whether a specific product is currently available and how many units are on hand.

    Args:
        product_id: UUID of the product to check.

    Returns:
        A dict with availability and quantity on hand, or an error string.
    """
    try:
        pid = _parse_uuid(product_id, "product_id")
        async with AsyncSessionLocal() as db:
            availability = await product_service.check_availability(db, pid)
            return availability.model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong checking availability. Please try again."


@tool
async def get_inventory_summary() -> dict | str:
    """Get stock levels for every product, including which items are low on stock.

    Admin context only — this reflects operational inventory data, not
    something a customer-facing conversation should surface. Only call this
    when you know you're assisting an admin/staff user.

    Returns:
        A dict with per-product quantity on hand, low-stock threshold, and a
        low-stock flag, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            summary = await inventory_service.get_inventory_summary(db)
            return {"inventory": [item.model_dump(mode="json") for item in summary]}
    except Exception:
        return "Error: something went wrong loading the inventory summary. Please try again."


@tool
async def create_order(user_id: str, pickup_location: str, order_date: str, items: list[dict]) -> dict | str:
    """Place a one-time order for a customer.

    Validates that every product exists and is available, that there's enough
    stock on hand for the requested quantities, and computes the total cost at
    current prices. Deliveries/pickups only happen on Wednesdays, so order_date
    must fall on one.

    Args:
        user_id: UUID of the customer placing the order.
        pickup_location: Where the order will be picked up.
        order_date: The Wednesday this order should be ready, as YYYY-MM-DD.
        items: List of objects, each with "product_id" (UUID string) and
            "quantity" (positive integer). Must contain at least one item.

    Returns:
        A dict with the created order (including total_amount), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        parsed_date = _parse_date(order_date, "order_date")
        parsed_items = _parse_items(items, OrderItemCreate)
        order_data = OrderCreate(pickup_location=pickup_location, order_date=parsed_date, items=parsed_items)
        async with AsyncSessionLocal() as db:
            order = await order_service.create_order(db, uid, order_data)
            return OrderRead.model_validate(order).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong placing the order. Please try again."


@tool
async def cancel_order(user_id: str, order_id: str) -> dict | str:
    """Cancel a one-time order before it enters fulfillment.

    Only orders still in "pending" or "confirmed" status can be cancelled —
    once staff have marked it "ready" or later, it's too late. Cancelling
    restores the ordered quantities back to inventory and issues a full refund
    of the order's total_amount.

    Args:
        user_id: UUID of the customer who placed the order (must own it).
        order_id: UUID of the order to cancel.

    Returns:
        A dict with the updated order (status "cancelled" and refund_amount set), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        oid = _parse_uuid(order_id, "order_id")
        async with AsyncSessionLocal() as db:
            order = await order_service.cancel_order(db, uid, oid)
            return OrderRead.model_validate(order).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong cancelling the order. Please try again."


@tool
async def create_subscription(
    user_id: str, pickup_location: str, frequency: str, next_delivery_date: str, items: list[dict]
) -> dict | str:
    """Enroll a customer in a new recurring delivery subscription.

    Validates that every product exists and is available. Future orders are
    generated from this subscription on the given schedule (weekly, biweekly,
    or monthly) starting from next_delivery_date, which must fall on a Wednesday.

    Args:
        user_id: UUID of the customer enrolling.
        pickup_location: Where deliveries will be picked up.
        frequency: One of "weekly", "biweekly", "monthly".
        next_delivery_date: The first delivery date, as YYYY-MM-DD (must be a Wednesday).
        items: List of objects, each with "product_id" (UUID string) and
            "quantity" (positive integer). Must contain at least one item.

    Returns:
        A dict with the created subscription, or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        parsed_date = _parse_date(next_delivery_date, "next_delivery_date")
        parsed_items = _parse_items(items, SubscriptionItemCreate)
        try:
            subscription_data = SubscriptionCreate(
                pickup_location=pickup_location,
                frequency=frequency,
                next_delivery_date=parsed_date,
                items=parsed_items,
            )
        except ValidationError as exc:
            return f"Error: {exc.errors()[0]['msg']}"
        async with AsyncSessionLocal() as db:
            subscription = await subscription_service.create_subscription(db, uid, subscription_data)
            return SubscriptionRead.model_validate(subscription).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong creating the subscription. Please try again."


@tool
async def pause_subscription(user_id: str, subscription_id: str, resume_on: str | None = None) -> dict | str:
    """Temporarily suspend a customer's active subscription.

    While paused, no new orders are generated. resume_on is optional and only
    advisory in this MVP (there's no scheduler to auto-resume it) — the
    customer will need to call resume on their own unless a later automated
    process is added.

    Args:
        user_id: UUID of the customer who owns the subscription.
        subscription_id: UUID of the subscription to pause. Must currently be active.
        resume_on: Optional future date (YYYY-MM-DD) the customer intends to resume by.

    Returns:
        A dict with the updated subscription (status "paused"), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        sid = _parse_uuid(subscription_id, "subscription_id")
        parsed_resume_on = _parse_date(resume_on, "resume_on") if resume_on is not None else None
        async with AsyncSessionLocal() as db:
            subscription = await subscription_service.pause_subscription(db, uid, sid, parsed_resume_on)
            return SubscriptionRead.model_validate(subscription).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong pausing the subscription. Please try again."


@tool
async def resume_subscription(user_id: str, subscription_id: str) -> dict | str:
    """Reactivate a paused subscription so future orders resume being generated.

    Args:
        user_id: UUID of the customer who owns the subscription.
        subscription_id: UUID of the subscription to resume. Must currently be paused.

    Returns:
        A dict with the updated subscription (status "active"), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        sid = _parse_uuid(subscription_id, "subscription_id")
        async with AsyncSessionLocal() as db:
            subscription = await subscription_service.resume_subscription(db, uid, sid)
            return SubscriptionRead.model_validate(subscription).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong resuming the subscription. Please try again."


@tool
async def cancel_subscription(user_id: str, subscription_id: str) -> dict | str:
    """Permanently cancel a subscription, stopping all future recurring deliveries.

    Already-fulfilled orders from this subscription remain in the customer's
    order history untouched. Only a brand-new subscription can restart
    deliveries after this — cancellation cannot be undone.

    Args:
        user_id: UUID of the customer who owns the subscription.
        subscription_id: UUID of the subscription to cancel.

    Returns:
        A dict with the updated subscription (status "cancelled"), or an error string.
    """
    try:
        uid = _parse_uuid(user_id, "user_id")
        sid = _parse_uuid(subscription_id, "subscription_id")
        async with AsyncSessionLocal() as db:
            subscription = await subscription_service.cancel_subscription(db, uid, sid)
            return SubscriptionRead.model_validate(subscription).model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong cancelling the subscription. Please try again."
