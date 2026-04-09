#!/usr/bin/env python3
"""
DALIL ask smoke runner

Usage:
  python run_dalil_ask_smoke_pack.py
  python run_dalil_ask_smoke_pack.py --base-url http://127.0.0.1:8000
  python run_dalil_ask_smoke_pack.py --base-url http://127.0.0.1:8000 --endpoint /ask --out results.json

Sends a set of DALIL /ask requests and prints each response.
Uses only Python stdlib.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PAYLOADS: list[dict[str, Any]] = [
    {
        "name": "topical_hadith_anger",
        "body": {
            "query": "What did the Prophet ﷺ say about anger?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_lying",
        "body": {
            "query": "Give me hadith about lying",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_jealousy",
        "body": {
            "query": "What did the Prophet ﷺ say about jealousy?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_patience_hardships",
        "body": {
            "query": "What did the Prophet ﷺ say about being patient in hardships?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "clarify_broad_hadith_self_improvement",
        "body": {
            "query": "How can I improve myself according to hadith?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "explicit_hadith_bukhari_20",
        "body": {
            "query": "Sahih al-Bukhari 20",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "explicit_lookup_only"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_jealousy_explicit_only_should_block",
        "body": {
            "query": "What did the Prophet ﷺ say about jealousy?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "explicit_lookup_only"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "quran_tafsir_ayat_al_kursi",
        "body": {
            "query": "Explain Ayat al-Kursi with tafsir",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "quran": {"enabled": True},
                "tafsir": {"enabled": True, "mode": "auto"},
                "hadith": {"enabled": False},
            },
        },
    },
    {
        "name": "explicit_quran_94_5_6",
        "body": {
            "query": "What does 94:5-6 say?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "quran": {"enabled": True},
                "tafsir": {"enabled": False},
                "hadith": {"enabled": False},
            },
        },
    },
    {
        "name": "quran_named_anchor_tafsir_surah_ikhlas",
        "body": {
            "query": "Tafsir of Surah Ikhlas",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "quran": {"enabled": True},
                "tafsir": {"enabled": True, "mode": "auto"},
                "hadith": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_backbiting",
        "body": {
            "query": "What did the Prophet ﷺ say about backbiting?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_arrogance",
        "body": {
            "query": "What did the Prophet ﷺ say about arrogance?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_mercy",
        "body": {
            "query": "What did the Prophet ﷺ say about mercy?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
    {
        "name": "topical_hadith_forgiveness",
        "body": {
            "query": "What did the Prophet ﷺ say about forgiveness?",
            "preferences": {"language": "en", "verbosity": "standard", "citations": "inline"},
            "sources": {
                "hadith": {"enabled": True, "mode": "auto"},
                "quran": {"enabled": False},
                "tafsir": {"enabled": False},
            },
        },
    },
]


def post_json(url: str, payload: dict[str, Any], timeout: int) -> tuple[int, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--endpoint", default="/ask", help="Endpoint path, default: /ask")
    parser.add_argument("--timeout", type=int, default=90, help="Per-request timeout in seconds")
    parser.add_argument("--out", default="", help="Optional output JSON file")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    endpoint = args.endpoint if args.endpoint.startswith("/") else f"/{args.endpoint}"
    url = f"{base_url}{endpoint}"

    results: list[dict[str, Any]] = []

    print(f"Sending {len(PAYLOADS)} DALIL requests to {url}\n")
    for idx, item in enumerate(PAYLOADS, start=1):
        name = item["name"]
        body = item["body"]
        print(f"[{idx}/{len(PAYLOADS)}] {name}")
        print(f"Query: {body['query']}")
        try:
            status, response_data = post_json(url=url, payload=body, timeout=args.timeout)
        except Exception as exc:  # pragma: no cover
            response_data = {"transport_error": str(exc)}
            status = 0

        results.append(
            {
                "name": name,
                "query": body["query"],
                "request_body": body,
                "status_code": status,
                "response": response_data,
            }
        )

        print(f"HTTP {status}")
        print(json.dumps(response_data, ensure_ascii=False, indent=2))
        print("-" * 100)

    if args.out:
        output_path = Path(args.out)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved results -> {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
