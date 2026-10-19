"""Constantes do contrato: bases por host e o conjunto mínimo de headers que passa.

Este módulo é a fachada de :mod:`ifood_contract.wire_profile`, que guarda a
**procedência** de cada valor e a regra de rotação (o que muda a cada deploy, o que
roda com o serviço dono). Para saber de onde vem cada chave, leia lá — aqui só
está o que a suíte consome.
"""

from .wire_profile import ADDRESS_X_APPLICATION_KEY, FASTER_APP_KEY, WireProfile

BASE_URLS: dict[str, str] = {
    "logistics": "https://logistics-api.ifood.com.br",
    "consumer": "https://consumer-api.ifood.com.br",
    "marketplace": "https://marketplace.ifood.com.br",
    "www": "https://www.ifood.com.br",
    # Identidade: o dex cita os dois hosts; ``id`` é o que aparece como emissor de token.
    "id": "https://id.ifood.com.br",
    "identity": "https://identity.ifood.com.br",
    # MFA: host próprio, configurado no bundle do web app como ACCOUNT_CHALLENGES_URL.
    "account_challenges": "https://account-challenges.ifood.com.br",
    # Loja/checkout legado (WSV3), com access_key/secret_key estáticas no bundle.
    "wsloja": "https://wsloja.ifood.com.br/ifood-ws-v3",
}

#: ``app_version`` muda a cada deploy (ver ``wire_profile.APP_VERSION.rotation``).
APP_VERSION = WireProfile.default()["app_version"]
APP_APPLICATION_KEY = ADDRESS_X_APPLICATION_KEY.value
APP_CLIENT_APPLICATION_KEY = FASTER_APP_KEY.value

WEB_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36"


def app_headers(
    session_id: str,
    device_id: str,
    *,
    profile: WireProfile | None = None,
    include_address_key: bool = True,
) -> dict[str, str]:
    """Headers mínimos que o web app manda. ``session_id``/``device_id`` vêm de fora.

    ``profile`` permite seguir um bundle novo (``WireProfile.resolve(bundle=...)``)
    em vez de congelar os valores embutidos.
    """
    resolved = profile or WireProfile.default()
    headers = resolved.headers(include_address_key=include_address_key)
    headers["accept"] = "application/json"
    headers["user-agent"] = WEB_USER_AGENT
    headers["x-ifood-session-id"] = session_id
    headers["x-ifood-device-id"] = device_id
    return headers
