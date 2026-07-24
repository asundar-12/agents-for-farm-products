"""Tools for the admin assistant.

These differ from the customer tools in one structural way: they take no
user_id. The customer tools are scoped to a single caller ("show *my*
orders"); these are farm-wide by design ("how much milk does the whole co-op
need this week"). That's exactly why they must never be wired into the customer
agent — the scoping is the security boundary, and it's enforced by which agent
gets these tools at all, not by a prompt asking nicely.

The set is deliberately read-only plus one save. Lifecycle actions (approve,
mark-ordered, close) are irreversible and stay on the explicit admin API where
a human clicks a button — we don't want a chat message like "go ahead and order
it" to place a real order with the farm.
"""

import uuid

from fastapi import HTTPException
from strands import tool

from app.core.db import AsyncSessionLocal
from app.services import aggregation_service, cycle_service


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"'{value}' is not a valid {field_name} — expected a UUID.") from exc


async def _resolve_cycle(db, cycle_id: str | None):
    """A cycle id if given, otherwise the week currently in flight.

    Most admin questions are about "this week", so defaulting to the current
    cycle means the admin rarely has to know or type a UUID. Locking expired
    cycles first keeps the answer honest — a week past its deadline shows as
    locked, not still open.
    """
    await cycle_service.lock_expired_cycles(db)
    if cycle_id is not None:
        return await cycle_service.get_cycle_by_id(db, _parse_uuid(cycle_id, "cycle_id"))
    return await cycle_service.get_or_create_current_cycle(db)


@tool
async def get_week_summary(cycle_id: str | None = None) -> dict | str:
    """Get the headline numbers for a week: total cost, product and unit counts,
    how many customers ordered, how many haven't, and how many demand spikes.

    Defaults to the current week if no cycle_id is given. This is the right
    first call for "how's this week looking" before drilling into specifics.

    Args:
        cycle_id: UUID of a specific week, or omit for the current one.

    Returns:
        A dict of summary figures, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            cycle = await _resolve_cycle(db, cycle_id)
            summary = await aggregation_service.get_cycle_summary(db, cycle.id)
            return summary.model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong loading the week summary. Please try again."


@tool
async def get_shopping_list(cycle_id: str | None = None) -> dict | str:
    """Get the consolidated buy list for a week: every product with its total
    quantity, the order-vs-subscription split, line cost, week-over-week change,
    a spike flag, and the per-customer breakdown of who wants what.

    Defaults to the current week. Use this to answer "how many X do we need",
    "who ordered eggs", or "what jumped since last week".

    Args:
        cycle_id: UUID of a specific week, or omit for the current one.

    Returns:
        A dict with the shopping list and its lines, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            cycle = await _resolve_cycle(db, cycle_id)
            shopping_list = await aggregation_service.get_shopping_list(db, cycle.id)
            return shopping_list.model_dump(mode="json")
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong loading the shopping list. Please try again."


@tool
async def get_non_submitters(cycle_id: str | None = None) -> dict | str:
    """List customers who have nothing coming in a week — no submitted order and
    no subscription due. Flags who has an unsubmitted draft, so the admin can
    tell "forgot to hit submit" from "hasn't looked at it".

    Defaults to the current week. Useful for deciding who to nudge before the
    deadline.

    Args:
        cycle_id: UUID of a specific week, or omit for the current one.

    Returns:
        A dict with the list of non-submitters, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            cycle = await _resolve_cycle(db, cycle_id)
            non_submitters = await aggregation_service.list_non_submitters(db, cycle)
            return {"non_submitters": [n.model_dump(mode="json") for n in non_submitters]}
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong loading non-submitters. Please try again."


@tool
async def list_recent_weeks(limit: int = 8) -> dict | str:
    """List recent weekly cycles, newest first, with their status and dates.

    Use this to find the cycle_id of a past week the admin wants to ask about,
    or to see where the current week sits in its lifecycle.

    Args:
        limit: How many weeks back to return (default 8).

    Returns:
        A dict with the list of cycles, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            await cycle_service.lock_expired_cycles(db)
            cycles = await cycle_service.list_cycles(db, limit=limit)
            return {
                "weeks": [
                    {
                        "cycle_id": str(c.id),
                        "week_start": c.week_start.isoformat(),
                        "delivery_date": c.delivery_date.isoformat(),
                        "status": c.status.value,
                    }
                    for c in cycles
                ]
            }
    except Exception:
        return "Error: something went wrong listing recent weeks. Please try again."


@tool
async def save_week_summary(summary: str, cycle_id: str | None = None) -> dict | str:
    """Save a written summary of a week to its admin notes.

    You write the prose; this tool persists it against the cycle so it shows up
    on the dashboard and survives the conversation. Call it only after the admin
    has asked you to save or record the summary — generating a summary in chat
    doesn't require saving it.

    Args:
        summary: The summary text to store.
        cycle_id: UUID of the week, or omit for the current one.

    Returns:
        A dict confirming what was saved, or an error string.
    """
    try:
        async with AsyncSessionLocal() as db:
            cycle = await _resolve_cycle(db, cycle_id)
            cycle.admin_notes = summary
            await db.commit()
            return {"saved": True, "cycle_id": str(cycle.id), "week_start": cycle.week_start.isoformat()}
    except HTTPException as exc:
        return f"Error: {exc.detail}"
    except ValueError as exc:
        return f"Error: {exc}"
    except Exception:
        return "Error: something went wrong saving the summary. Please try again."
