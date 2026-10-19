"""Sessão do operador como artefato: jar de cookies Netscape e diagnóstico.

Motivo: a recomendação medida é *jar de sessão como artefato de primeira classe* —
o browser faz o bootstrap (Cloudflare + PerimeterX) e o resto roda por HTTP puro.
Um jar é um arquivo que envelhece, então a suíte precisa saber lê-lo, dizer o que
está vencido e falhar com mensagem que diga "renove o jar", não "a API mudou".

Formato: Netscape (``cookies.txt``), o mesmo que ``curl --cookie-jar`` escreve e
que os gravadores do projeto produzem.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import httpx

#: Cookies de borda que decidem se a chamada passa. Nome → dono.
EDGE_COOKIES = {
    "_px3": "PerimeterX (reavalia por path)",
    "_pxvid": "PerimeterX (visitante)",
    "_pxhd": "PerimeterX (hash de dispositivo)",
    "pxcts": "PerimeterX (contador)",
    "cf_clearance": "Cloudflare (challenge resolvido)",
    "__cf_bm": "Cloudflare (bot management)",
}

#: Prefixos de cookie que carregam sessão/flag e não borda.
SESSION_COOKIE_HINTS = ("aAccessToken", "aRefreshToken", "fstr.")


@dataclass(frozen=True, slots=True)
class JarCookie:
    domain: str
    name: str
    value: str
    expires_at: float | None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= time.time()

    @property
    def remaining_seconds(self) -> int | None:
        if self.expires_at is None:
            return None
        return int(self.expires_at - time.time())


class JarError(RuntimeError):
    """Jar ausente, vazio ou ilegível."""


def read_jar(path: Path) -> list[JarCookie]:
    """Lê o jar Netscape. Linha malformada é ignorada; jar vazio é erro."""
    if not path.exists():
        raise JarError(f"jar não encontrado: {path}")
    cookies: list[JarCookie] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        # Netscape: as linhas de comentário começam com '#', mas o cookie
        # "HttpOnly_" vem prefixado com '#HttpOnly_' e é válido.
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_") :]
        elif line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _flag, _path, _secure, expires, name, value = parts[:7]
        try:
            expires_at: float | None = float(expires) if expires not in {"", "0"} else None
        except ValueError:
            expires_at = None
        cookies.append(JarCookie(domain=domain, name=name, value=value, expires_at=expires_at))
    if not cookies:
        raise JarError(f"jar sem cookies: {path}")
    return cookies


def to_httpx_cookies(cookies: list[JarCookie]) -> httpx.Cookies:
    jar = httpx.Cookies()
    for cookie in cookies:
        if cookie.expired:
            continue
        jar.set(cookie.name, cookie.value, domain=cookie.domain, path="/")
    return jar


def describe(cookies: list[JarCookie]) -> str:
    """Relatório curto: quais cookies de borda existem e quanto tempo resta.

    É isto que a suíte imprime quando uma chamada toma 403, para separar
    "jar vencido" de "a API mudou" — as duas causas têm conserto diferente.
    """
    lines: list[str] = []
    by_name = {cookie.name: cookie for cookie in cookies}
    for name, owner in EDGE_COOKIES.items():
        cookie = by_name.get(name)
        if cookie is None:
            lines.append(f"  {name:14s} ausente   ({owner})")
            continue
        remaining = cookie.remaining_seconds
        if cookie.expired:
            lines.append(f"  {name:14s} VENCIDO   ({owner})")
        elif remaining is None:
            lines.append(f"  {name:14s} sessão    ({owner})")
        else:
            lines.append(f"  {name:14s} {remaining:6d}s ({owner})")
    for hint in SESSION_COOKIE_HINTS:
        present = [name for name in by_name if name.startswith(hint)]
        lines.append(f"  {hint:14s} {'presente' if present else 'ausente'}")
    return "\n".join(lines)


def has_session(cookies: list[JarCookie]) -> bool:
    """Sessão de usuário, não só borda: precisa dos dois tokens da conta."""
    names = {cookie.name for cookie in cookies if not cookie.expired}
    return any(name.startswith(hint) for hint in SESSION_COOKIE_HINTS[:2] for name in names)


@dataclass
class Session:
    """O jar embrulhado: cliente + cookies + relatório de validade."""

    client: httpx.Client
    cookies: list[JarCookie]
    path: Path

    @property
    def report(self) -> str:
        return describe(self.cookies)

    @property
    def has_user_session(self) -> bool:
        return has_session(self.cookies)

    @property
    def headers(self) -> dict[str, str]:
        """Headers da sessão: constante do perfil + o que o cookie atualiza."""
        from .config import WEB_USER_AGENT, app_headers

        base = app_headers(
            header_hints(self.cookies).get("x-ifood-session-id", ""),
            header_hints(self.cookies).get("x-ifood-device-id", ""),
        )
        base["user-agent"] = WEB_USER_AGENT
        base.update(header_hints(self.cookies))
        # O BFF não lê o JWT do cookie: exige ``Authorization: Bearer`` (medido:
        # sem ele, 401 ``{"message":"no jwt token"}`` mesmo com aAccessToken no jar).
        token = next(
            (c.value for c in self.cookies if c.name == "aAccessToken" and not c.expired), ""
        )
        if token:
            base["authorization"] = f"Bearer {token}"
        return base

    @property
    def coordinates(self) -> tuple[str, str] | None:
        return saved_coordinates(self.cookies)

    @property
    def has_payment_secret(self) -> bool:
        return has_device_payment_secret(self.cookies)

    @property
    def checkout_headers(self) -> dict[str, str]:
        """Os três headers do ``POST /v6/order/checkout``, montados do jar.

        Todos vêm do jar: ``X-Ifood-Device-Id`` de ``aDeviceId``,
        ``X-Ifood-Device-Payment-Secret`` do cookie de mesmo prefixo e
        ``X-Ifood-Customer-Id`` de ``aAccountId``. Sem eles o checkout não é
        possível fora do browser — e é por isso que o C11 caiu.
        """
        by_name = {cookie.name: cookie.value for cookie in self.cookies if not cookie.expired}
        headers: dict[str, str] = {}
        if "aDeviceId" in by_name:
            headers["X-Ifood-Device-Id"] = by_name["aDeviceId"]
        secret = device_payment_secret(self.cookies)
        if secret:
            headers["X-Ifood-Device-Payment-Secret"] = secret
        if "aAccountId" in by_name:
            headers["X-Ifood-Customer-Id"] = by_name["aAccountId"]
        return headers

    def missing_checkout_headers(self) -> list[str]:
        """Quais dos três headers de checkout o jar não permite montar."""
        have = set(self.checkout_headers)
        return [
            name
            for name in (
                "X-Ifood-Device-Id",
                "X-Ifood-Device-Payment-Secret",
                "X-Ifood-Customer-Id",
            )
            if name not in have
        ]

    def describe(self) -> str:
        return (
            f"jar: {self.path}\nsessão de usuário: {'sim' if self.has_user_session else 'não'}\n"
            + self.report
        )

    def close(self) -> None:
        self.client.close()


def build_client(cookies: list[JarCookie], *, base_url: str = "") -> httpx.Client:
    """``httpx.Client`` com o jar carregado e sem retry automático.

    Sem retry por desenho: 429 é bucket curto e 4xx de negócio nunca se repete;
    quem decide repetir é o fluxo, não a biblioteca.
    """
    return httpx.Client(
        cookies=to_httpx_cookies(cookies),
        base_url=base_url,
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=False,
    )


#: Cookie → header. O browser guarda no cookie o que manda em header, então o jar
#: não serve só para autenticar: ele também **atualiza as constantes do protocolo**
#: (versão do app, chave do Faster), que assim sobrevivem a deploy sem editar código.
COOKIE_TO_HEADER = {
    "aSessionId": "x-ifood-session-id",
    "aDeviceId": "x-ifood-device-id",
    "aAppVersion": "app_version",
    "aFasterAppKey": "x-client-application-key",
}

#: Cookie com o segredo de pagamento do device (nome tem hash do aparelho). Não se
#: resolve aqui: só se registra que existe, porque é o que decide se o checkout com
#: cartão salvo é possível fora do browser.
DEVICE_PAYMENT_COOKIE_PREFIX = "x-ifood-device-payment-"


def header_hints(cookies: list[JarCookie]) -> dict[str, str]:
    """Headers derivados do jar, com o valor do cookie (que é o mais fresco)."""
    by_name = {cookie.name: cookie for cookie in cookies if not cookie.expired}
    hints: dict[str, str] = {}
    for cookie_name, header in COOKIE_TO_HEADER.items():
        cookie = by_name.get(cookie_name)
        if cookie is not None and cookie.value:
            hints[header] = cookie.value
    return hints


def saved_coordinates(cookies: list[JarCookie]) -> tuple[str, str] | None:
    """Coordenada do endereço ativo da sessão (``address-latitude``/``longitude``)."""
    by_name = {cookie.name: cookie for cookie in cookies if not cookie.expired}
    lat = by_name.get("address-latitude")
    lon = by_name.get("address-longitude")
    if lat is None or lon is None:
        return None
    return lat.value, lon.value


def device_payment_secret(cookies: list[JarCookie]) -> str | None:
    """Valor do segredo de pagamento do device (o próprio valor do cookie).

    Medido pelo ifood-api no bundle: ``X-Ifood-Device-Payment-Secret`` recebe
    ``getCookie("x-ifood-device-payment-" + config)`` **direto**, sem hash nem
    transformação. Continua *inferido* que o servidor exige o par
    (device id ↔ segredo) coerente.
    """
    for cookie in cookies:
        if cookie.name.startswith(DEVICE_PAYMENT_COOKIE_PREFIX) and not cookie.expired:
            return cookie.value
    return None


def has_device_payment_secret(cookies: list[JarCookie]) -> bool:
    return any(
        cookie.name.startswith(DEVICE_PAYMENT_COOKIE_PREFIX) and not cookie.expired
        for cookie in cookies
    )
