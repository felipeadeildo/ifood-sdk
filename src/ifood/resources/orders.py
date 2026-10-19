"""Order history, tracking and reorder.

`reorder` is the cheapest path to "buy last week's burger": it returns the merchant and
the bag, but the sub-item ids belong to the old catalog snapshot, so they must be
resolved against the current menu before they can be added to a cart.
"""

from collections.abc import Sequence

from ..models import Order, Reorder
from ..types import JsonObject, as_list, as_object
from ..wire import endpoints
from ..wire.transport import Transport


class Orders:
    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def last(self) -> Order:
        """The most recent order. One call, no list handling."""
        orders = self.recent(1)
        if not orders:
            raise LookupError("this account has no orders")
        return orders[0]

    def recent(self, size: int = 5) -> Sequence[Order]:
        """The last orders, newest first. The common case, with no pagination noise."""
        return self.list(size=size)

    def list(self, *, page: int = 0, size: int = 10, **params: str | int) -> Sequence[Order]:
        """One page of the order history. Extra keyword arguments go to the query string."""
        query: dict[str, str | int | float | bool] = {"page": page, "size": size, **params}
        payload = self._t.get(endpoints.CUSTOMER_ORDERS, params=query)
        return [Order.model_validate(item) for item in as_list(payload)]

    def get(self, order_id: str) -> Order:
        return Order.model_validate(self._t.get(endpoints.ORDER_DETAIL.format(order_id=order_id)))

    def events(self, order_id: str) -> Sequence[JsonObject]:
        result = self._t.get(endpoints.ORDER_EVENTS.format(order_id=order_id))
        return [as_object(item) for item in as_list(result)]

    def reorder(self, order: str | Order, *, latitude: float, longitude: float) -> Reorder:
        """Previous bag. Latitude and longitude are required (400 SCO-3000 without them).

        The sub-item ids belong to the catalog snapshot of that order, so adding them to a
        cart needs the current menu to resolve option groups.
        """
        order_id = order.id if isinstance(order, Order) else order
        return Reorder.model_validate(
            self._t.get(
                endpoints.ORDER_REORDER.format(order_id=order_id),
                params={"lat": latitude, "lon": longitude},
            )
        )

    def delivery_code(self, order: str | Order) -> str | None:
        """Four digits spoken to the courier; not required to receive the order."""
        return self.get(order.id if isinstance(order, Order) else order).delivery_code
