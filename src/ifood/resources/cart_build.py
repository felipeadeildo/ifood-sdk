"""Cart payloads for both API versions.

The same cart has two incompatible contracts, and the difference is not cosmetic.

v2 is what the web BFF uses today: complements go in `items[].subItems[]` with `id` and
`quantity`, `delivery.now` is a boolean, there is no `mode`, and the body carries
`account` and `source`.

v1 is the WSV3 path: complements go in `items[].garnish`, `delivery.now` must be the
string `"true"`, and `delivery.mode` exists.

Sending one where the other is expected returns CART-007. The builder therefore takes the
version as a required argument instead of guessing.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from ..errors import BusinessRule
from ..models import Address, Merchant
from ..types import Json, JsonObject

CartVersion = Literal["v1", "v2"]

CART_MISSING = "CART-006"
CART_WRONG_TYPE = "CART-007"
ITEM_MISSING_GARNISH = "ITEM-001"

REQUIRED_TOP_LEVEL = ("merchant", "address", "items", "delivery")
REQUIRED_TOP_LEVEL_V2 = (*REQUIRED_TOP_LEVEL, "account", "source")


class CartPayloadError(BusinessRule):
    """Local validation, raised with the same code the server would return."""

    def __init__(self, code: str, field_name: str, message: str) -> None:
        super().__init__(f"{field_name}: {message}", status=0, code=code, envelope="flat")
        self.field_name = field_name


@dataclass(frozen=True, slots=True)
class SubItem:
    """One option inside a catalog item. The id is the current catalog option id."""

    id: str
    quantity: int = 1


@dataclass(frozen=True, slots=True, init=False)
class CartItem:
    """One catalog item. Options can be passed positionally: `CartItem("id", 1, SubItem("x"))`."""

    id: str
    quantity: int
    observation: str | None
    sub_items: tuple[SubItem, ...]

    def __init__(
        self,
        id: str,
        quantity: int = 1,
        *sub_items: SubItem,
        observation: str | None = None,
    ) -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "observation", observation)
        object.__setattr__(self, "sub_items", tuple(sub_items))


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    name: str | None = None
    email: str | None = None
    country_code: int = 55
    area_code: str | None = None
    phone_number: str | None = None


@dataclass(frozen=True, slots=True)
class CartDraft:
    """Everything the payload needs, with ids already resolved against the current catalog."""

    merchant_id: str
    address: dict[str, Any]
    items: Sequence[CartItem]
    merchant_name: str | None = None
    account: Account | None = None
    delivery_id: str = "DEFAULT"
    now: bool = True
    delivery_by: str = "IFOOD"
    source_version: str = "9.178.5"
    source_name: str = "web"
    source_platform: str = "desktop"
    source_requester: str = "ifood"
    extra: dict[str, Any] = field(default_factory=dict)


def build_payload(draft: CartDraft, version: CartVersion = "v2") -> dict[str, Any]:
    """Build the request body. Pure: no network, no menu lookup."""
    merchant: dict[str, Any] = {"id": draft.merchant_id}
    if draft.merchant_name:
        merchant["name"] = draft.merchant_name
    payload: dict[str, Any] = {
        "merchant": merchant,
        "address": draft.address,
        "items": [_item(item, version) for item in draft.items],
        "delivery": _delivery(draft, version),
    }
    if version == "v2":
        if draft.account is None:
            raise CartPayloadError(CART_MISSING, "account", "v2 sends account in the body")
        payload["account"] = _account(draft.account)
        payload["source"] = {
            "name": draft.source_name,
            "platform": draft.source_platform,
            "requester": draft.source_requester,
            "parameters": [{"name": "version", "value": draft.source_version}],
        }
    payload.update(draft.extra)
    validate_payload(payload, version=version)
    return payload


def validate_payload(payload: dict[str, Any], *, version: CartVersion = "v2") -> None:
    """Check a payload against the rules the server enforces, in the order it checks."""
    required = REQUIRED_TOP_LEVEL_V2 if version == "v2" else REQUIRED_TOP_LEVEL
    for name in required:
        if name not in payload:
            raise CartPayloadError(CART_MISSING, name, "missing from the payload")

    merchant = payload["merchant"]
    if not isinstance(merchant, dict) or "id" not in merchant:
        raise CartPayloadError(CART_WRONG_TYPE, "merchant", "expected an object with id")

    items = payload["items"]
    if not isinstance(items, list) or not items:
        raise CartPayloadError(CART_MISSING, "items", "expected a non-empty list")
    for index, item in enumerate(items):
        _validate_item(item, index, version)

    delivery = payload["delivery"]
    if not isinstance(delivery, dict):
        raise CartPayloadError(CART_WRONG_TYPE, "delivery", "expected an object")
    _validate_delivery(delivery, version)


def _item(item: CartItem, version: CartVersion) -> dict[str, Any]:
    if version == "v2":
        body: dict[str, Any] = {
            "id": item.id,
            "quantity": item.quantity,
            "subItems": [{"id": sub.id, "quantity": sub.quantity} for sub in item.sub_items],
        }
        if item.observation is not None:
            body["observation"] = item.observation
        return body
    return {
        "id": item.id,
        "quantity": item.quantity,
        "garnish": [{"id": sub.id, "quantity": sub.quantity} for sub in item.sub_items],
    }


def _delivery(draft: CartDraft, version: CartVersion) -> dict[str, Any]:
    if version == "v2":
        return {"id": draft.delivery_id, "now": draft.now, "deliveryBy": draft.delivery_by}
    return {"id": draft.delivery_id, "mode": "DELIVERY", "now": "true" if draft.now else "false"}


def _account(account: Account) -> dict[str, Any]:
    body: dict[str, Any] = {"id": account.id}
    for key, value in (
        ("name", account.name),
        ("email", account.email),
    ):
        if value is not None:
            body[key] = value
    if account.area_code and account.phone_number:
        body["phone"] = {
            "countryCode": account.country_code,
            "areaCode": account.area_code,
            "number": account.phone_number,
        }
    return body


def _validate_item(item: Any, index: int, version: CartVersion) -> None:
    if not isinstance(item, dict):
        raise CartPayloadError(CART_WRONG_TYPE, "items", f"item {index} is not an object")
    if "id" not in item:
        raise CartPayloadError(CART_MISSING, "id", f"item {index} has no id")
    quantity = item.get("quantity", 1)
    if not isinstance(quantity, int) or quantity < 1:
        raise CartPayloadError(CART_WRONG_TYPE, "quantity", f"item {index} is not an int >= 1")
    if version == "v2":
        if "garnish" in item:
            raise CartPayloadError(CART_WRONG_TYPE, "garnish", "v2 uses subItems, not garnish")
        if not isinstance(item.get("subItems", []), list):
            raise CartPayloadError(CART_WRONG_TYPE, "subItems", "expected a list")
    elif "subItems" in item:
        raise CartPayloadError(CART_WRONG_TYPE, "subItems", "v1 uses garnish, not subItems")


def _validate_delivery(delivery: dict[str, Any], version: CartVersion) -> None:
    if "id" not in delivery:
        raise CartPayloadError(CART_MISSING, "id", "delivery has no id")
    now = delivery.get("now")
    if version == "v2":
        if not isinstance(now, bool):
            raise CartPayloadError(CART_WRONG_TYPE, "now", "v2 requires a boolean")
        if "mode" in delivery:
            raise CartPayloadError(CART_WRONG_TYPE, "mode", "v2 has no mode")
    else:
        if now != "true" and now != "false":
            raise CartPayloadError(CART_WRONG_TYPE, "now", 'v1 requires the string "true"')
        if "mode" not in delivery:
            raise CartPayloadError(CART_MISSING, "mode", "v1 requires mode")


def draft_from(
    *,
    merchant: Merchant | JsonObject | str | None = None,
    address: Address | JsonObject | None = None,
    items: Sequence[CartItem | JsonObject] | None = None,
    account: Account | JsonObject | None = None,
    merchant_id: str | None = None,
    merchant_name: str | None = None,
    delivery_id: str = "DEFAULT",
    now: bool = True,
    delivery_by: str = "IFOOD",
) -> CartDraft:
    """Normalise whatever the caller has into a draft.

    Accepts our models or raw dicts for merchant, address, items and account.
    """
    resolved_id, resolved_name = _read_merchant(merchant, merchant_id, merchant_name)
    if items is None:
        raise TypeError("build needs items")
    resolved = tuple(_read_item(item) for item in items)
    return CartDraft(
        merchant_id=resolved_id,
        merchant_name=resolved_name,
        address=_as_dict(address, "address"),
        items=resolved,
        account=_read_account(account),
        delivery_id=delivery_id,
        now=now,
        delivery_by=delivery_by,
    )


def _read_merchant(
    merchant: Merchant | JsonObject | str | None,
    merchant_id: str | None,
    merchant_name: str | None,
) -> tuple[str, str | None]:
    if merchant is not None:
        if isinstance(merchant, str):
            return merchant, merchant_name
        data = merchant if isinstance(merchant, dict) else merchant.model_dump(by_alias=True)
        found = data.get("id")
        if not isinstance(found, str):
            raise TypeError("merchant needs an id")
        return found, _text(data.get("name")) or merchant_name
    if merchant_id is None:
        raise TypeError("build needs a merchant")
    return merchant_id, merchant_name


def _read_item(item: CartItem | JsonObject) -> CartItem:
    if isinstance(item, CartItem):
        return item
    item_id = item.get("id")
    if not isinstance(item_id, str):
        raise TypeError("item needs an id")
    raw_subs = item.get("subItems", [])
    collected: list[SubItem] = []
    for sub in raw_subs if isinstance(raw_subs, list) else []:
        if not isinstance(sub, dict):
            continue
        sub_id = sub.get("id")
        if not isinstance(sub_id, str):
            continue
        sub_quantity = sub.get("quantity", 1)
        collected.append(SubItem(sub_id, sub_quantity if isinstance(sub_quantity, int) else 1))
    sub_items = tuple(collected)
    quantity = item.get("quantity", 1)
    return CartItem(
        item_id,
        quantity if isinstance(quantity, int) else 1,
        *sub_items,
        observation=_text(item.get("observation")),
    )


def _text(value: Json) -> str | None:
    return value if isinstance(value, str) else None


def _read_account(account: Account | JsonObject | None) -> Account | None:
    if account is None or isinstance(account, Account):
        return account
    account_id = account.get("id")
    if not isinstance(account_id, str):
        raise TypeError("account needs an id")
    raw_phone = account.get("phone")
    phone = raw_phone if isinstance(raw_phone, dict) else {}
    country = phone.get("countryCode", 55)
    return Account(
        account_id,
        _text(account.get("name")),
        _text(account.get("email")),
        country if isinstance(country, int) else 55,
        _text(phone.get("areaCode")),
        _text(phone.get("number")),
    )


def _as_dict(value: Address | JsonObject | None, name: str) -> JsonObject:
    if value is None:
        raise TypeError(f"build needs {name}")
    if isinstance(value, dict):
        return value
    return value.model_dump(by_alias=True, exclude_none=True)
