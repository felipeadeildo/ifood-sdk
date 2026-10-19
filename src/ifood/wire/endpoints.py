"""Every route the SDK uses, with the measurement status behind it.

Status legend:
  measured  - seen working in a real capture
  legacy    - present in the web bundle only; never seen on the wire
  unknown   - assumed, must be verified before being relied on
"""

# identity (measured)
IDENTITY_PROVIDERS = "/v4/identity-providers"
OTP_AUTHORIZATION_CODE = "/v2/identity-providers/OTP/authorization-codes"
OTP_ACCESS_TOKEN = "/v2/identity-providers/OTP/access-tokens"
OTP_CHALLENGE = "/v1/identity-providers/OTP/challenges"
OTP_AUTHENTICATION = "/v3/identity-providers/OTP/authentications"

# customer (measured)
CUSTOMER_ME = "/v1/customers/me"
CUSTOMER_ADDRESSES = "/v1/customers/me/addresses"
CUSTOMER_ORDERS = "/v4/customers/me/orders"
ORDER_DETAIL = "/v3/customers/me/orders/{order_id}"
ORDER_EVENTS = "/v1/customers/me/orders/{order_id}/events"
ORDER_REORDER = "/v1/customers/me/orders/{order_id}/reorder"

# cart (measured; writes require a browser-originated session)
CART_CREATE = "/v2/carts"
CART_CHECKOUT = "/v2/carts/{cart_id}/checkout"
CART_PAYMENT_METHOD = "/v2/carts/{cart_id}/paymentMethod"
CART_VOUCHER = "/v2/carts/{cart_id}/voucher"  # current flow, same base as the cart
CART_VOUCHER_LEGACY = "/v1/carts/{cart_id}/voucher"  # WSV3 base, bundle only

# discovery (menu and search are PerimeterX-gated)
MERCHANT_CATALOG = "/v1/merchants/restaurant/{merchant_id}/catalog"
# SEARCH: only an edge 403 was ever observed. A 403 at the edge does not prove the route
# exists, so this stays `unknown` until a 200 or a routing 404 shows up.
SEARCH = "/v2/cardstack/search/results"

# other hosts
GEOCODE = "/location/v1/addresses:geocode"
# Reverse geocode: assumed from the module name, never seen on the wire.
REVERSE_GEOCODE = "/location/v1/coordinates:reverse-geocode"
MERCHANT_DETAIL = "/v1/merchants/{merchant_id}"


def bff_path(path: str) -> str:
    """Absolute BFF URL for logs and docs; the transport already carries the base."""
    return "https://www.ifood.com.br/site-api" + ("" if path.startswith("/") else "/") + path
