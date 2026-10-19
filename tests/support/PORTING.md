# Porting `tests/support/pending` → `src/ifood`

Regra: um arquivo de `pending/` só é apagado **no mesmo commit** em que o
equivalente em `src/ifood` cobrir o comportamento, e a suíte de `tests/contract/`
passa a importar de `ifood.*`. Nunca os dois ao mesmo tempo.

| pending | destino em `src/ifood` | o que o `src/` ainda não tem |
|---|---|---|
| `cart.py` | `carts.py` | `build_payload`/`validate` v1×v2 com os códigos da API (`CART-006`, `CART-007`, `ITEM-001`), `CartSnapshot`/`parse_cart_response`, `snapshot_total`, `SNAPSHOT_LEASE_SECONDS` |
| `wire_profile.py` | `config.py` | `extract_from_bundle()` + `test_wire_profile_matches_bundle` (detector de deriva) e `WireProfile.resolve(bundle=...)` |
| `session.py` | `session.py` | `checkout_headers`/`missing_checkout_headers`, `saved_coordinates` |
| `web_paths.py` | `endpoints.py` | a tabela completa de rotas com status, `GARNISH_VARIANTS`, `CART_VALIDATION_CHAIN`, `VERIFICATION_ROUTES`, `bff_path` |
| `http.py` | `transport.py` | redação de PII/cassete (`redact_json`, `redact_url`, `is_opaque_value`, `looks_like_email`, JSON aninhado em string) e o cassete transport de teste |
| `errors.py` | `errors.py` | `IfoodApiError.from_response` com `envelope`/`header_code`/`retryable` (o `src/` usa classes; os testes de envelope devem ser reescritos para elas ao portar) |
| `config.py` | `config.py` | nada além do que está acima; é fachada |
| `tests/support/inventory.py`, `measure.py` | nenhum (ferramenta de teste) | captura `requests.jsonl` → `report/ENDPOINTS.md` + cassete por rota |

Fora de `pending/`, mas ainda na suíte: `tests/support/shape.py` (skeleton de JSON).

## Por que `pending/` existe

A suíte é a especificação executável do contrato medido. Manter os módulos aqui,
em vez de reescrever os testes contra `src/` antes de portar, evita duas coisas:
teste vermelho por recurso que ainda não existe, e teste verde contra uma cópia que
depois divergiria. O `PORTING.md` é o contrato de saída: quando o item da tabela
estiver em `src/`, o arquivo sai.

## Decisão pendente que bloqueia o port do `cart.py` (4)

**O construtor recebe códigos já resolvidos. Não recebe catálogo nem snapshot.**

Assinatura pretendida:

```python
build_payload(draft: CartDraft, version: CartVersion = "v2") -> dict[str, object]
```

`CartItem(id=<id do catálogo>, quantity=1, observation=None, sub_items=(SubItem(id=..., quantity=1), ...))`

Por quê: `subItems[].id` é o id da **opção no catálogo atual**, e o `choiceCode` do
histórico é de outra camada (medido: `ITEM-001` nas duas tentativas). Resolver isso
dentro do construtor obrigaria o SDK a buscar menu no meio da montagem, o que
introduz browser (PX) numa função que hoje é pura e testável offline.

Separar em duas camadas mantém as duas honestas:

1. `build_payload` — puro, sem rede, valida com os códigos da própria API
   (`CART-006` ausente, `CART-007` tipo errado, `ITEM-001` complemento);
2. adaptador `reorder -> CartDraft` (fica em `orders.py`/`carts.py`, recebe o
   catálogo resolvido de fora) — é este que "precisa de menu", e ele pode falhar
   dizendo exatamente qual item não tem equivalente no catálogo atual.

## Mapa de asserção ao portar `test_error_envelopes.py`

O `src` classifica por tipo; o teste usa propriedade. Tradução exata:

| hoje (pending) | depois do port |
|---|---|
| `err.is_edge` | `isinstance(err, ifood.EdgeBlocked)` |
| `err.is_rate_limited` | `isinstance(err, ifood.RateLimited)` |
| `err.is_auth_missing` | `isinstance(err, ifood.AuthMissing)` |
| `err.is_business_rule` | `isinstance(err, ifood.BusinessRule)` |
| `err.retryable` | `isinstance(err, (ifood.RateLimited,))` ou status >= 500 |

Confirmado no `src/ifood/errors.py`: `from_response` decide **borda antes de 429**,
então `429` com corpo flat vira `RateLimited` (e não `BusinessRule`). É o que o
`test_429_without_retry_after_is_retryable` afirma — a tradução acima preserva isso.

## Removido por decisão do operador

- `render_markdown` e `--markdown`: geração de markdown saiu. `inventory.py` só
  inventaria e `measure.py` só grava cassetes. Não reintroduzir.
