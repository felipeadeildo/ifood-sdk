"""Types that describe the wire, so signatures say what is required and what is optional.

`Json` is the shape of anything that comes back from or goes into a request body. Concrete
payloads narrow it: a cart body is not an arbitrary dict, and the type says which fields
exist.
"""

from typing import NotRequired, TypedDict

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None
type JsonObject = dict[str, Json]
type Query = dict[str, str | int | float | bool]


class CartItemPayload(TypedDict):
    """One item as v2 accepts it. v1 uses `garnish` instead of `subItems`."""

    id: str
    quantity: int
    subItems: list[SubItemPayload]
    observation: NotRequired[str]


class SubItemPayload(TypedDict):
    id: str
    quantity: int


class MerchantPayload(TypedDict):
    id: str
    name: NotRequired[str]


class DeliveryPayload(TypedDict, total=False):
    id: str
    now: bool
    deliveryBy: str


class AccountPayload(TypedDict, total=False):
    id: str
    name: str
    email: str
    phone: PhonePayload


class PhonePayload(TypedDict):
    countryCode: int
    areaCode: str
    number: str


class SourcePayload(TypedDict):
    name: str
    platform: str
    requester: str
    parameters: list[ParameterPayload]


class ParameterPayload(TypedDict):
    name: str
    value: str


class CartPayload(TypedDict, total=False):
    """A cart body. Required fields are required; the version decides the rest."""

    merchant: MerchantPayload
    address: JsonObject
    items: list[CartItemPayload]
    delivery: DeliveryPayload
    account: AccountPayload
    source: SourcePayload


class CheckoutPayload(TypedDict, total=False):
    """The checkout body. `cartRequest` is a JSON string, which is the whole trap."""

    cartRequest: str
    signature: str
    cpfCnpj: str
    paymentSources: JsonObject


def as_object(value: Json) -> JsonObject:
    """Narrow a response to an object, or say clearly that the shape changed."""
    if not isinstance(value, dict):
        raise TypeError(f"expected an object, got {type(value).__name__}")
    return value


def as_list(value: Json) -> list[Json]:
    if not isinstance(value, list):
        raise TypeError(f"expected a list, got {type(value).__name__}")
    return value


def as_text(value: Json, field: str = "value") -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field}: expected text, got {type(value).__name__}")
    return value
