"""Typed views over API payloads.

Responses carry more fields than the SDK needs and iFood adds fields without notice, so
every model allows extras. Typed attributes give autocompletion; `model_dump()` still
returns the whole payload, which is what the cart and checkout builders need.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base for API payloads: accept extras, read camelCase, write snake_case."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, str_strip_whitespace=False)


class Coordinates(ApiModel):
    latitude: float
    longitude: float


class Address(ApiModel):
    id: str
    street_name: str | None = Field(default=None, alias="streetName")
    street_number: str | None = Field(default=None, alias="streetNumber")
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = Field(default=None, alias="postalCode")
    coordinates: Coordinates | None = None
    favorite: bool | None = None


class Merchant(ApiModel):
    id: str
    name: str | None = None
    type: str | None = None


class BagItem(ApiModel):
    id: str
    external_id: str | None = Field(default=None, alias="externalId")
    name: str | None = None
    quantity: int = 1
    unit_price: int | None = Field(default=None, alias="unitPrice")
    total_price: int | None = Field(default=None, alias="totalPrice")
    notes: str | None = None
    sub_items: list[BagItem] = Field(default_factory=list, alias="subItems")


class Bag(ApiModel):
    items: list[BagItem] = Field(default_factory=list)


class EstimatedArrival(ApiModel):
    delivers_at: str | None = Field(default=None, alias="deliversAt")
    delivers_end_at: str | None = Field(default=None, alias="deliversEndAt")


class Delivery(ApiModel):
    address: Address | None = None
    estimated_time_of_arrival: EstimatedArrival | None = Field(
        default=None, alias="estimatedTimeOfArrival"
    )


class VerificationCode(ApiModel):
    name: str | None = None
    value: str | None = None
    required: bool = False


class PaymentMethod(ApiModel):
    name: str | None = None
    description: str | None = None


class Payment(ApiModel):
    method: PaymentMethod | None = None
    type: PaymentMethod | None = None


class Order(ApiModel):
    id: str
    short_id: str | None = Field(default=None, alias="shortId")
    order_number: str | None = Field(default=None, alias="orderNumber")
    created_at: str | None = Field(default=None, alias="createdAt")
    last_status: str | None = Field(default=None, alias="lastStatus")
    merchant: Merchant | None = None
    delivery: Delivery | None = None
    bag: Bag | None = None
    payments: list[Payment] = Field(default_factory=list)
    verification_codes: list[VerificationCode] = Field(
        default_factory=list, alias="verificationCodes"
    )

    @property
    def number(self) -> str | None:
        """The number printed on the receipt, which is what support asks for."""
        return self.order_number

    @property
    def status(self) -> str | None:
        """CREATED, PLACED, CONFIRMED, DISPATCHED, CONCLUDED."""
        return self.last_status

    @property
    def delivery_code(self) -> str | None:
        """The four digits spoken to the courier."""
        for code in self.verification_codes:
            if code.name == "DELIVERY_CODE":
                return code.value
        return None


class CartSnapshot(ApiModel):
    """The signed cart the checkout must echo back verbatim."""

    id: str
    cart_type: str | None = Field(default=None, alias="cartType")
    merchant: Merchant | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = Field(default=None, alias="createdAt")
    expires_at: str | None = Field(default=None, alias="expiresAt")

    @property
    def total(self) -> Any:
        return self.summary.get("total")


class CheckoutResult(ApiModel):
    order_id: str = Field(alias="orderId")
    pix_qr_code: str | None = Field(default=None, alias="pixQRCode")
    cart_response: dict[str, Any] | None = Field(default=None, alias="cartResponse")


class Phone(ApiModel):
    country_code: int = Field(default=55, alias="countryCode")
    area_code: str | None = Field(default=None, alias="areaCode")
    number: str | None = None


class AccountInfo(ApiModel):
    """The account block the API returns inside the profile."""

    id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: Phone | None = None


class Profile(ApiModel):
    """Account payload. Only the stable bits are typed; the rest stays reachable."""

    account: AccountInfo | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    name: str | None = None
    email: str | None = None


class Reorder(ApiModel):
    """What `reorder` returns: the previous merchant and bag, plus divergence flags."""

    id: str
    merchant: Merchant | None = None
    bag: Bag | None = None
    divergence: bool = False


class CartResponse(ApiModel):
    """Response of a cart mutation: the snapshot plus the server signature."""

    data: CartSnapshot | None = None
    signature: str | None = None
    warning: str | None = None

    @property
    def cart(self) -> CartSnapshot | None:
        return self.data


class PreparedCart(ApiModel):
    """A cart built from a past order, ready to inspect before sending."""

    merchant: Merchant | None = None
    address: Address | None = None
    items: list[BagItem] = Field(default_factory=list)
    total: float | None = None
    diverged: bool = False
    warnings: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
