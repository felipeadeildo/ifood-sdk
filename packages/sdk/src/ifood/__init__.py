"""ifood-sdk: unofficial Python client for the iFood consumer API.

import ifood

client = ifood.Client(phone="+55 11 90000-0000")
client.login()
client.verify("123456")

for order in client.orders.recent(3):
    print(order.number, order.status, order.merchant.name)
"""

from .auth import Auth, Channel, OtpChallenge, Phone
from .client import Client, NotLoggedIn
from .errors import AuthMissing, BusinessRule, EdgeBlocked, IfoodError, RateLimited
from .models import (
    Address,
    Bag,
    BagItem,
    CartResponse,
    CartSnapshot,
    CheckoutResult,
    Coordinates,
    Delivery,
    Merchant,
    Order,
    Payment,
    Profile,
    Reorder,
    VerificationCode,
)
from .resources.cart_build import (
    CART_MISSING,
    CART_WRONG_TYPE,
    ITEM_MISSING_GARNISH,
    Account,
    CartDraft,
    CartItem,
    CartPayloadError,
    SubItem,
    build_payload,
    validate_payload,
)
from .resources.carts import Carts
from .resources.customers import Customers
from .resources.merchants import Merchants
from .resources.orders import Orders
from .resources.vouchers import Vouchers
from .wire.config import DEFAULT_PROFILE, WireProfile, profile_from_session
from .wire.endpoints import bff_path
from .wire.session import Session
from .wire.settings import Settings
from .wire.store import FileStore, MemoryStore, SessionStore, default_store
from .wire.transport import Transport

__all__ = [
    "CART_MISSING",
    "CART_WRONG_TYPE",
    "DEFAULT_PROFILE",
    "ITEM_MISSING_GARNISH",
    "Account",
    "Address",
    "Auth",
    "AuthMissing",
    "Bag",
    "BagItem",
    "BusinessRule",
    "CartDraft",
    "CartItem",
    "CartPayloadError",
    "CartResponse",
    "CartSnapshot",
    "Carts",
    "Channel",
    "CheckoutResult",
    "Client",
    "Coordinates",
    "Customers",
    "Delivery",
    "EdgeBlocked",
    "FileStore",
    "IfoodError",
    "MemoryStore",
    "Merchant",
    "Merchants",
    "NotLoggedIn",
    "Order",
    "Orders",
    "OtpChallenge",
    "Payment",
    "Phone",
    "Profile",
    "RateLimited",
    "Reorder",
    "Session",
    "SessionStore",
    "Settings",
    "SubItem",
    "Transport",
    "VerificationCode",
    "Vouchers",
    "WireProfile",
    "bff_path",
    "build_payload",
    "default_store",
    "profile_from_session",
    "validate_payload",
]
