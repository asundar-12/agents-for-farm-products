"""Importing every model module here ensures they're all registered on Base's
mapper registry before Alembic autogenerate (or anything else) inspects
Base.metadata — otherwise tables defined in modules nobody imported yet would
silently be missing from the migration.
"""

from app.models.customer import Address, User  # noqa: F401
from app.models.inventory import Delivery, DeliveryPickup, Inventory  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.subscription import Subscription, SubscriptionItem  # noqa: F401
