"""The object people touch: one class, one flow.

import ifood

client = ifood.Client(phone="+55 11 90000-0000")
client.login()
client.verify("123456")

for order in client.orders.recent(3):
    print(order.number, order.status)
"""

from pathlib import Path

from .auth import Auth, Channel, OtpChallenge, Phone
from .errors import IfoodError
from .models import AccountInfo, Address, BagItem, Order, PreparedCart
from .resources.cart_build import Account
from .resources.carts import Carts
from .resources.customers import Customers
from .resources.merchants import Merchants
from .resources.orders import Orders
from .resources.vouchers import Vouchers
from .wire.config import DEFAULT_PROFILE, WireProfile
from .wire.session import Session
from .wire.store import FileStore, SessionStore, default_store
from .wire.transport import Transport

DEFAULT_COUNTRY_CODE = 55


class NotLoggedIn(IfoodError):
    """No session to use: call `login()` and `verify()` first."""


class Client:
    """A client bound to one session.

    With no arguments it reuses the saved session. With `phone=` it prepares a login.
    Pass `session=` or `jar=` when the session comes from somewhere else.
    """

    def __init__(
        self,
        phone: str | Phone | None = None,
        *,
        email: str | None = None,
        store: SessionStore | None = None,
        session: Session | None = None,
        jar: str | Path | None = None,
        profile: WireProfile | None = None,
    ) -> None:
        self.store = store or default_store()
        self.email = email
        self.phone = Phone.parse(phone) if phone is not None else None
        self._challenge: OtpChallenge | None = None
        self._account: Account | None = None

        resolved = self._resolve_session(session, jar, phone)
        self.transport = Transport(resolved, profile=profile or DEFAULT_PROFILE)
        self.auth = Auth(self.transport)
        self.customers = Customers(self.transport)
        self.orders = Orders(self.transport)
        self.merchants = Merchants(self.transport)
        self.carts = Carts(self.transport, account=self.cart_account)
        self.vouchers = Vouchers(self.transport)

    def _resolve_session(
        self, session: Session | None, jar: str | Path | None, phone: str | Phone | None
    ) -> Session:
        if session is not None:
            return session
        if jar is not None:
            return Session.from_jar(jar)
        if phone is not None:
            return Session()
        return self._load_saved() or Session()

    def _load_saved(self) -> Session | None:
        try:
            return self.store.load()
        except OSError, ValueError:
            return None

    @property
    def session(self) -> Session:
        return self.transport.session

    @property
    def logged_in(self) -> bool:
        return bool(self.session.access_token)

    def login(self, *, channel: Channel = "WHATSAPP") -> Client:
        """Send a one-time code and keep the challenge. Returns self for chaining."""
        if self.phone is None:
            raise ValueError("Client(phone=...) is required to log in")
        self._challenge = self.auth.start_otp(self.phone, email=self.email, channel=channel)
        return self

    def verify(self, code: str, *, save: bool = True) -> Client:
        """Check the code, keep the tokens and save the session. Returns self."""
        if self._challenge is None:
            raise ValueError("call login() before verify()")
        self._challenge.verify(code)
        self._challenge = None
        if save:
            self.store.save(self.session)
        return self

    def logout(self) -> None:
        """Forget the tokens in memory. The saved file stays where it is."""
        self.session.access_token = None
        self.session.refresh_token = None

    def cart_account(self) -> Account:
        """Who the order is for. Read from the profile once, then reused."""
        if self._account is None:
            self._account = self._read_account()
        return self._account

    def _read_account(self) -> Account:
        info = self._account_info()
        account_id = (info.id if info else None) or self.session.user_id
        if account_id is None:
            raise IfoodError("account unknown: log in before building a cart")
        phone = info.phone if info else None
        return Account(
            account_id,
            info.name if info else None,
            info.email if info else None,
            phone.country_code if phone else DEFAULT_COUNTRY_CODE,
            phone.area_code if phone else None,
            phone.number if phone else None,
        )

    def _account_info(self) -> AccountInfo | None:
        if not self.logged_in:
            return None
        try:
            return self.customers.profile().account
        except IfoodError:
            return None

    def repeat(self, order: Order | str | None = None) -> PreparedCart:
        """Build the cart for an order you already placed.

        With no argument it uses your last order. The payload is complete and validated;
        sending it needs a browser-originated session, which the client does not pretend
        to have. Anything that could make the repeat wrong lands in `warnings`.
        """
        address = self._delivery_address()
        coordinates = address.coordinates
        if coordinates is None:
            raise LookupError("the saved address has no coordinates")

        target = order if order is not None else self.orders.last()
        previous = self.orders.reorder(
            target, latitude=coordinates.latitude, longitude=coordinates.longitude
        )
        items = list(previous.bag.items) if previous.bag else []
        warnings = self._repeat_warnings(previous.divergence, items)
        payload = self.carts.build(
            merchant=previous.merchant or {},
            address=address,
            items=[{"id": item.id, "quantity": item.quantity} for item in items],
        )
        cents = sum((item.unit_price or 0) * item.quantity for item in items)
        return PreparedCart(
            merchant=previous.merchant,
            address=address,
            items=items,
            total=cents / 100 if items else None,
            diverged=previous.divergence,
            warnings=warnings,
            payload=payload,
        )

    @staticmethod
    def _repeat_warnings(diverged: bool, items: list[BagItem]) -> list[str]:
        warnings: list[str] = []
        if diverged:
            warnings.append("the merchant changed something since that order")
        if not items:
            warnings.append("the previous order has no items to repeat")
        return warnings

    def _delivery_address(self) -> Address:
        addresses = self.customers.addresses()
        if not addresses:
            raise LookupError("no saved address: add one in the app first")
        return addresses[0]


__all__ = ["Client", "FileStore", "NotLoggedIn"]
