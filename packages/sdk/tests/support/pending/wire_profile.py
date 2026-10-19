"""Constantes do protocolo, com procedência e regra de rotação.

Motivo de existir: chave mágica sem procedência em biblioteca é dívida. Estas
constantes vêm do bundle de produção do web app (`www.ifood.com.br`), e cada uma
tem dono, origem e tempo de vida diferente. Se o iFood rotacionar uma delas, o
que quebra é diferente em cada caso — e é isso que este módulo registra.

Procedência exata (o bundle é minificado; o trecho citado é o contexto literal):

- ``ADDRESS_X_APPLICATION_KEY`` — em ``web/full/_app-6a5d151cf7ebe925.js``, no
  bloco de config: ``ADDRESS_X_APPLICATION_KEY:"Zw@W#GbKp@UyXMYcBTsZFavt3"``. É
  enviada como header ``X-Application-Key`` **só** nas chamadas de endereço
  (``/location/v1/addresses:geocode``, ``reverse-geocode``) — ver o serviço de
  endereço no mesmo bundle. No build, o valor vem de
  ``NEXT_PUBLIC_CO_ADDRESS_X_APPLICATION_KEY``, então é público por construção.
- ``FASTER_APP_KEY`` — mesma config:
  ``FASTER_APP_KEY:"41a266ee-51b7-4c37-9e9d-5cd331f280d5"``. **Não** é "client
  application key" do iFood: é a chave do *Faster* (``env-var.fstr.rocks``), o
  serviço de feature flag deles. O web a reusa no header
  ``x-client-application-key`` no construtor de headers de telemetria. É esta a
  chave que o ledger antigo chamava de ``x-client-application-key`` sem dizer de
  onde vinha.
- ``APP_VERSION`` — o valor ``9.178.5`` é o campo ``version`` do ``package.json``
  de ``ifood-consumer-webapp`` embutido no bundle:
  ``JSON.parse('{"name":"ifood-consumer-webapp","version":"9.178.5",...}')``.
  Logo, **muda a cada deploy**. Tratar como constante fixa é a pior opção aqui.
- ``APP_NAME`` — ``"consumer_webapp"``; ``APP_PLATFORM`` — ``"Desktop"`` no
  config global, mas o serviço de endereço manda ``platform: "webapp"`` na mão.
  Ou seja: header por endpoint, não valor global.

Regra de manutenção adotada:

1. O valor vive aqui, com ``source`` e ``rotation`` preenchidos.
2. ``extract_from_bundle()`` relê as mesmas constantes do bundle servido. Rodar
   isso contra um bundle novo é o detector de deriva — o teste
   ``test_wire_profile_matches_bundle`` falha quando o app rotaciona algo.
3. O cliente não deve congelar ``app_version``: use
   ``WireProfile.resolve(bundle=...)`` para seguir o deploy, e ``DEFAULT`` só como
   último recurso offline.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: Rótulos de rotação, para quem for manter a biblioteca saber o que esperar.
ROTATION = {
    "deploy": "muda a cada deploy do web app (sem aviso, sem changelog)",
    "service": "roda com a rotação do serviço dono (Faster, endereço)",
    "stable": "estável há muito tempo; não é segredo, é identificador público",
}


@dataclass(frozen=True, slots=True)
class WireConstant:
    """Um valor do protocolo, com a vida útil declarada."""

    name: str
    value: str
    sent_as: str
    source: str
    derivation: str
    rotation: str
    confidence: str = "observado-no-bundle"

    def __post_init__(self) -> None:
        if self.rotation not in ROTATION:
            raise ValueError(f"{self.name}: rotação desconhecida {self.rotation!r}")
        if not self.source or not self.derivation:
            raise ValueError(f"{self.name}: procedência obrigatória")


ADDRESS_X_APPLICATION_KEY = WireConstant(
    name="address_x_application_key",
    value="Zw@W#GbKp@UyXMYcBTsZFavt3",
    sent_as="header X-Application-Key (só nas rotas de endereço)",
    source="web/full/_app-6a5d151cf7ebe925.js — config: ADDRESS_X_APPLICATION_KEY",
    derivation="build injeta NEXT_PUBLIC_CO_ADDRESS_X_APPLICATION_KEY (valor público)",
    rotation="service",
)

FASTER_APP_KEY = WireConstant(
    name="faster_app_key",
    value="41a266ee-51b7-4c37-9e9d-5cd331f280d5",
    sent_as="header x-client-application-key",
    source="web/full/_app-6a5d151cf7ebe925.js — config: FASTER_APP_KEY",
    derivation="chave do serviço Faster (env-var.fstr.rocks), reusada no header de telemetria",
    rotation="service",
)

APP_VERSION = WireConstant(
    name="app_version",
    value="9.178.5",
    sent_as="header app_version",
    source='web/full/_app-6a5d151cf7ebe925.js — package.json embutido: {"name":"ifood-consumer-webapp","version":"9.178.5"}',
    derivation="campo version do pacote ifood-consumer-webapp, congelado no build",
    rotation="deploy",
)

APP_NAME = WireConstant(
    name="app_name",
    value="consumer_webapp",
    sent_as="header app_name",
    source="web/full/_app-6a5d151cf7ebe925.js — config: APP_NAME",
    derivation="constante do build",
    rotation="stable",
)

#: ``platform`` não é global: o config diz ``Desktop`` e o serviço de endereço manda
#: ``webapp`` na mão. Guardamos o que é enviado por rota, não o config.
PLATFORM_WEBAPP = WireConstant(
    name="platform_webapp",
    value="webapp",
    sent_as="header platform (rotas de endereço e de marketplace)",
    source='web/full/_app-6a5d151cf7ebe925.js — chamada de geocode: {platform:"webapp", ...}',
    derivation='literal na chamada, diverge do APP_PLATFORM global ("Desktop")',
    rotation="stable",
)

DEVICE_MODEL = WireConstant(
    name="device_model",
    value="Linux Chrome",
    sent_as="header x-device-model (obrigatório nas rotas de identidade)",
    source="evidence/login-01 — captura do browser: x-device-model: Linux Chrome",
    derivation="'<SO> <navegador>'; o web monta a partir do user agent",
    rotation="stable",
)

BROWSER = WireConstant(
    name="browser",
    value="Linux",
    sent_as="header browser (obrigatório nas rotas de identidade)",
    source="evidence/login-01 — captura do browser: browser: Linux",
    derivation="só o SO; sem este header a identidade devolve 400 OTP-2000",
    rotation="stable",
)

COUNTRY = WireConstant(
    name="country",
    value="br",
    sent_as="header country",
    source="APP_PLATFORM/_country do web app; confirmado nas capturas (header country: br)",
    derivation="constante por mercado",
    rotation="stable",
    confidence="observado-na-captura",
)

#: Ordem canônica dos headers de aplicação.
CONSTANTS: tuple[WireConstant, ...] = (
    APP_NAME,
    APP_VERSION,
    PLATFORM_WEBAPP,
    COUNTRY,
    FASTER_APP_KEY,
    ADDRESS_X_APPLICATION_KEY,
    DEVICE_MODEL,
    BROWSER,
)

#: Nome no bundle → constante. Usado pela extração e pelo detector de deriva.
_BUNDLE_RE = {
    "ADDRESS_X_APPLICATION_KEY": re.compile(r'ADDRESS_X_APPLICATION_KEY:"([^"]+)"'),
    "FASTER_APP_KEY": re.compile(r'FASTER_APP_KEY:"([^"]+)"'),
    "APP_NAME": re.compile(r'APP_NAME:"([^"]+)"'),
}
_PACKAGE_VERSION_RE = re.compile(
    r'\\?"name\\?":\\?"ifood-consumer-webapp\\?",\\?"version\\?":\\?"([^"]+)\\?"'
)


def extract_from_bundle(bundle: Path) -> dict[str, str]:
    """Relê as constantes do bundle servido. É o detector de deriva da biblioteca.

    Devolve ``{nome_da_constante: valor}`` para as que casarem; chave ausente no
    bundle simplesmente não aparece (o teste decide se isso é falha).
    """
    text = bundle.read_text(encoding="utf-8", errors="replace")
    found: dict[str, str] = {}
    for key, pattern in _BUNDLE_RE.items():
        match = pattern.search(text)
        if match:
            found[key] = match.group(1)
    version = _PACKAGE_VERSION_RE.search(text)
    if version:
        found["APP_VERSION"] = version.group(1).replace('\\"', "")
    return found


class WireProfile:
    """Conjunto resolvido de constantes, com override explícito."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    @classmethod
    def default(cls) -> WireProfile:
        return cls({constant.name: constant.value for constant in CONSTANTS})

    @classmethod
    def resolve(
        cls,
        *,
        bundle: Path | None = None,
        overrides: Mapping[str, str] | None = None,
    ) -> WireProfile:
        """Prioridade: override explícito > bundle lido na hora > valor embutido."""
        values = {constant.name: constant.value for constant in CONSTANTS}
        if bundle is not None and bundle.exists():
            extracted = extract_from_bundle(bundle)
            values["address_x_application_key"] = extracted.get(
                "ADDRESS_X_APPLICATION_KEY", values["address_x_application_key"]
            )
            values["faster_app_key"] = extracted.get("FASTER_APP_KEY", values["faster_app_key"])
            values["app_name"] = extracted.get("APP_NAME", values["app_name"])
            values["app_version"] = extracted.get("APP_VERSION", values["app_version"])
        values.update(overrides or {})
        return cls(values)

    def __getitem__(self, name: str) -> str:
        return self._values[name]

    def get(self, name: str, fallback: str = "") -> str:
        return self._values.get(name, fallback)

    def headers(self, *, include_address_key: bool = True) -> dict[str, str]:
        """Headers de aplicação. A chave de endereço é opcional por desenho."""
        headers = {
            "app_name": self["app_name"],
            "platform": self["platform_webapp"],
            "app_version": self["app_version"],
            "country": self["country"],
            "x-client-application-key": self["faster_app_key"],
            "x-device-model": self["device_model"],
            "browser": self["browser"],
        }
        if include_address_key:
            headers["x-application-key"] = self["address_x_application_key"]
        return headers

    def with_overrides(self, overrides: Mapping[str, str]) -> WireProfile:
        return WireProfile({**self._values, **overrides})

    def describe(self) -> str:
        """Tabela pronta para o ledger: valor, onde é enviado e o que o derruba."""
        lines = ["| constante | enviado como | rotação | procedência |", "|---|---|---|---|"]
        for constant in CONSTANTS:
            value = self._values.get(constant.name, constant.value)
            lines.append(
                f"| `{constant.name}` = `{value}` | {constant.sent_as} | "
                f"{ROTATION[constant.rotation]} | {constant.source} |"
            )
        return "\n".join(lines)

    def as_json(self) -> str:
        return json.dumps(self._values, indent=2, ensure_ascii=False)


def bundled_profile(path: Path) -> WireProfile:
    """Atalho para ler um bundle já baixado (ex.: ``web/full/_app-*.js``)."""
    if not path.exists():
        return WireProfile.default()
    return WireProfile.resolve(bundle=path)


__all__ = [
    "ADDRESS_X_APPLICATION_KEY",
    "APP_NAME",
    "APP_VERSION",
    "BROWSER",
    "CONSTANTS",
    "COUNTRY",
    "DEVICE_MODEL",
    "FASTER_APP_KEY",
    "PLATFORM_WEBAPP",
    "ROTATION",
    "WireConstant",
    "WireProfile",
    "bundled_profile",
    "extract_from_bundle",
]
