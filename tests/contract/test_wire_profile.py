"""O perfil do protocolo: procedência e detector de deriva.

Estes testes existem para uma pergunta de manutenção: "quando o iFood mudar o web
app, a biblioteca quebra em silêncio?". Aqui a resposta tem que ser não — quem
rotaciona uma constante derruba um teste com o nome dela.
"""

from pathlib import Path

import pytest
from support.pending import wire_profile
from support.pending.wire_profile import ROTATION, WireConstant, WireProfile, extract_from_bundle

#: Bundle de produção baixado pelo harness (5,4 MB). Se não existir, os testes de
#: deriva pulam: a suíte continua offline e verde em CI sem os artefatos.
BUNDLE = (
    Path(__file__).resolve().parents[3] / "research" / "web" / "full" / "_app-6a5d151cf7ebe925.js"
)


def test_every_constant_declares_provenance() -> None:
    """Constante sem procedência é dívida: aqui vira erro, não comentário."""
    for constant in wire_profile.CONSTANTS:
        assert constant.source, f"{constant.name} sem source"
        assert constant.derivation, f"{constant.name} sem derivation"
        assert constant.sent_as, f"{constant.name} sem 'enviado como'"
        assert constant.rotation in ROTATION
        assert constant.confidence in {"observado-no-bundle", "observado-na-captura"}


def test_rotation_classification_is_honest() -> None:
    """`app_version` muda a cada deploy; as chaves rodam com o serviço; nome não."""
    assert wire_profile.APP_VERSION.rotation == "deploy"
    assert wire_profile.FASTER_APP_KEY.rotation == "service"
    assert wire_profile.ADDRESS_X_APPLICATION_KEY.rotation == "service"
    assert wire_profile.APP_NAME.rotation == "stable"


def test_faster_key_is_not_an_ifood_client_key() -> None:
    """A chave do header `x-client-application-key` é do Faster, não do iFood.

    Isto estava mal atribuído no ledger antigo; o teste impede que volte.
    """
    key = wire_profile.FASTER_APP_KEY
    assert key.name == "faster_app_key"
    assert "Faster" in key.derivation
    headers = WireProfile.default().headers()
    assert headers["x-client-application-key"] == key.value


def test_app_headers_cover_every_mandatory_identity_header() -> None:
    """Se faltar um header de identidade, o corpo exato vira 400 OTP-2000."""
    from support.pending.config import app_headers
    from support.pending.web_paths import IDENTITY_REQUIRED_HEADERS

    headers = app_headers(
        "00000000-0000-4000-8000-000000000000", "11111111-1111-4111-8111-111111111111"
    )
    missing = [name for name in IDENTITY_REQUIRED_HEADERS if name not in headers]
    assert not missing, f"faltando header obrigatório: {missing}"
    assert headers["x-device-model"] == wire_profile.DEVICE_MODEL.value
    assert headers["browser"] == wire_profile.BROWSER.value


def test_address_key_is_optional_and_address_scoped() -> None:
    """`x-application-key` é chave do serviço de endereço: pode ser omitida."""
    with_key = WireProfile.default().headers()
    without_key = WireProfile.default().headers(include_address_key=False)
    assert "x-application-key" in with_key
    assert "x-application-key" not in without_key
    assert without_key["x-client-application-key"], "a chave do Faster continua indo"


@pytest.mark.skipif(not BUNDLE.exists(), reason="bundle do web app não baixado")
def test_wire_profile_matches_bundle() -> None:
    """DERIVA: o valor embutido tem que casar com o bundle servido.

    Quando isto falhar, o iFood rotacionou algo. O conserto é rodar
    ``extract_from_bundle`` e atualizar ``wire_profile.py`` — nunca "dar bypass".
    """
    extracted = extract_from_bundle(BUNDLE)
    assert extracted, "nada extraído: os padrões do bundle mudaram de forma"
    assert extracted["ADDRESS_X_APPLICATION_KEY"] == wire_profile.ADDRESS_X_APPLICATION_KEY.value
    assert extracted["FASTER_APP_KEY"] == wire_profile.FASTER_APP_KEY.value
    assert extracted["APP_NAME"] == wire_profile.APP_NAME.value
    assert extracted["APP_VERSION"] == wire_profile.APP_VERSION.value


@pytest.mark.skipif(not BUNDLE.exists(), reason="bundle do web app não baixado")
def test_bundle_profile_can_follow_a_deploy() -> None:
    """Simula um deploy novo: com o bundle lido na hora, a versão acompanha."""
    resolved = WireProfile.resolve(bundle=BUNDLE, overrides={"app_version": "0.0.0-teste"})
    assert resolved["app_version"] == "0.0.0-teste"
    from_bundle = WireProfile.resolve(bundle=BUNDLE)
    assert from_bundle["app_version"] == extract_from_bundle(BUNDLE)["APP_VERSION"]


def test_platform_is_per_endpoint_not_global() -> None:
    """O config global diz `Desktop`; o serviço de endereço manda `webapp`."""
    assert wire_profile.PLATFORM_WEBAPP.value == "webapp"
    assert "Desktop" in wire_profile.PLATFORM_WEBAPP.derivation


def test_wire_constant_rejects_anonymous_value() -> None:
    """Construtor recusa constante sem procedência — o contrato é executável."""
    with pytest.raises(ValueError):
        WireConstant(
            name="x",
            value="y",
            sent_as="header z",
            source="",
            derivation="",
            rotation="stable",
        )
    with pytest.raises(ValueError):
        WireConstant(
            name="x", value="y", sent_as="h", source="s", derivation="d", rotation="inventada"
        )


def test_describe_lists_rotation_for_the_ledger() -> None:
    table = WireProfile.default().describe()
    assert "deploy" in table
    assert "faster_app_key" in table
    assert "address_x_application_key" in table
