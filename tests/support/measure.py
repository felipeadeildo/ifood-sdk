"""CLI do inventário: ``uv run python -m ifood_contract.measure <requests.jsonl> [...]``.

Uso típico, depois de uma captura do browser:

    uv run python -m tests.support.measure ../evidence/recon-03/requests.jsonl \\
        --cassettes tests/cassettes/inventory
"""

import argparse
import json
from pathlib import Path

from .inventory import (
    is_third_party,
    load_events,
    pair_exchanges,
    representative,
    slug,
    summarize,
    to_cassette,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventário de endpoints a partir de requests.jsonl"
    )
    parser.add_argument("captures", nargs="+", type=Path, help="arquivos requests.jsonl")
    parser.add_argument(
        "--cassettes", type=Path, default=None, help="diretório para um cassete por endpoint"
    )
    parser.add_argument("--include-static", action="store_true", help="inclui .js/.css/imagens")
    parser.add_argument(
        "--include-third-party",
        action="store_true",
        help="inclui telemetria de terceiros (google/facebook/...) no mapa e nos cassetes",
    )
    args = parser.parse_args()

    all_exchanges = []
    orphans = 0
    for capture in args.captures:
        exchanges, missing = pair_exchanges(load_events(capture))
        all_exchanges.extend(exchanges)
        orphans += missing
        print(f"{capture}: {len(exchanges)} exchanges, {missing} órfãos")

    endpoints = summarize(all_exchanges, include_static=args.include_static)
    if not args.include_third_party:
        endpoints = [endpoint for endpoint in endpoints if not is_third_party(endpoint.url)]
    print(f"{len(endpoints)} endpoints distintos")

    if args.cassettes is not None:
        args.cassettes.mkdir(parents=True, exist_ok=True)
        written = 0
        for endpoint in endpoints:
            exchange = representative(all_exchanges, endpoint)
            if exchange is None or exchange.status is None:
                continue
            target = args.cassettes / f"{slug(endpoint)}.json"
            target.write_text(
                json.dumps(to_cassette(exchange, name=slug(endpoint)), indent=2, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            written += 1
        print(f"cassetes: {written} em {args.cassettes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
