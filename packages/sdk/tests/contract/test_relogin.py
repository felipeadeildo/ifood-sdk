"""Re-login OTP: o caminho de reserva, e por que ele não é automático.

O operador decidiu (e a medição apoia): jar de sessão é o caminho principal; o
re-login é reserva. Este arquivo existe para deixar o procedimento executável e
honesto, não para rodar em CI.

Por que nunca roda sozinho:

- o passo ``authorization-codes`` **manda um OTP de verdade** para o telefone do
  operador (WhatsApp/SMS), com ``timeout_in_seconds: 60`` e ``key`` de uso único;
- o código chega no aparelho dele: alguém precisa digitar;
- o PX/CF não é resolvido por login: um jar de borda vencido barra a própria
  chamada de ``/v4/identity-providers`` (medido).

Ou seja: automatizar re-login sem humano produz desafio queimado, conta com
tentativas gastas e nenhum teste confiável. O correto é a tool do MCP **pedir o
código** e esperar, que é o desenho já registrado (C12/C17 do CRITIQUE).

Procedimento manual, quando o jar morrer:

1. ``python -m playwright ...`` ou o Chrome do perfil do projeto abre a página de
   login; resolver o "Press & Hold" se aparecer.
2. Pedir o OTP, digitar no browser, concluir o login.
3. Exportar o jar Netscape (o gravador do projeto já faz: ``cookies.json`` +
   conversão para Netscape).
4. Rodar ``uv run pytest tests/test_smoke_session.py --live --jar <jar>``.
"""

import pytest
from support.pending.web_paths import IDENTITY_ROUTES

pytestmark = pytest.mark.manual


def test_relogin_is_documented_as_manual() -> None:
    """O procedimento está escrito no docstring e a cadeia está declarada."""
    paths = [route.path for route in IDENTITY_ROUTES if route.confidence == "capturado"]
    assert "/v2/identity-providers/OTP/authorization-codes" in paths
    assert "/v3/identity-providers/OTP/authentications" in paths


@pytest.mark.skip(
    reason="passo humano: envia OTP real e espera o código; ver docstring para o procedimento"
)
def test_relogin_otp_end_to_end() -> None:
    """Só com humano presente. Esqueleto do que seria feito se fosse automatizável."""
    raise AssertionError("não deve rodar: requer OTP digitado pelo operador")
