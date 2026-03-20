from __future__ import annotations

import argparse
import csv
import html
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_OUTPUT = Path("data/processed/quran_translations/quran_en_single_translation.csv")
DEFAULT_API_BASE_URL = "https://apis.quran.foundation/content/api/v4"
DEFAULT_AUTH_BASE_URL = "https://oauth2.quran.foundation"
DEFAULT_FIELDS = "text"
DEFAULT_TRANSLATION_NAME = "Quran.Foundation translation"
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def load_env_file() -> None:
    """Load a simple .env file into os.environ if present.

    This avoids requiring python-dotenv just for the translation import script.
    Existing process env vars win over file values.
    """
    candidate_paths = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]

    env_path = next((p for p in candidate_paths if p.exists()), None)
    if env_path is None:
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download one English Quran translation from Quran.Foundation and save it as a local CSV for Dalil Verify."
    )
    parser.add_argument("--translation-id", type=int, required=True, help="Quran.Foundation translation resource id")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV output path")
    parser.add_argument("--api-base-url", default=os.getenv("QF_CONTENT_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--auth-base-url", default=os.getenv("QF_AUTH_BASE_URL", DEFAULT_AUTH_BASE_URL))
    parser.add_argument("--client-id", default=os.getenv("QF_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("QF_CLIENT_SECRET"))
    parser.add_argument("--auth-token", default=os.getenv("QF_AUTH_TOKEN"))
    parser.add_argument("--sleep-ms", type=int, default=0, help="Optional sleep between requests in milliseconds")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def get_access_token(*, auth_base_url: str, client_id: str | None, client_secret: str | None) -> str:
    missing = [name for name, value in [("QF_CLIENT_ID", client_id), ("QF_CLIENT_SECRET", client_secret)] if not value]
    if missing:
        raise SystemExit(f"Missing required credentials for OAuth2 token retrieval: {', '.join(missing)}")

    token_url = f"{auth_base_url.rstrip('/')}/oauth2/token"
    try:
        response = httpx.post(
            token_url,
            auth=(client_id or "", client_secret or ""),
            headers={"Content-Type": "application/x-www-form-urlencoded", "accept": "application/json"},
            data={"grant_type": "client_credentials", "scope": "content"},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        status = getattr(exc.response, "status_code", None) if hasattr(exc, "response") else None
        raise SystemExit(
            "Failed to obtain access token from Quran Foundation OAuth2"
            + (f" (status {status})" if status else "")
        ) from exc

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise SystemExit("OAuth2 token response did not contain access_token")
    return str(access_token)


def build_headers(
    *,
    client_id: str | None,
    auth_token: str | None,
    auth_base_url: str,
    client_secret: str | None,
) -> dict[str, str]:
    if not client_id:
        raise SystemExit("Missing required credential: QF_CLIENT_ID")

    token = auth_token or get_access_token(
        auth_base_url=auth_base_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    return {
        "x-client-id": client_id,
        "x-auth-token": token,
        "accept": "application/json",
        "user-agent": "dalil-verify/0.4 translation-import",
    }


def fetch_verses_for_chapter(
    client: httpx.Client,
    *,
    api_base_url: str,
    chapter_number: int,
    translation_id: int,
) -> list[dict[str, Any]]:
    verses: list[dict[str, Any]] = []
    page = 1
    per_page = 50

    while True:
        response = client.get(
            f"{api_base_url.rstrip('/')}/verses/by_chapter/{chapter_number}",
            params={
                "words": "false",
                "translations": str(translation_id),
                "translation_fields": DEFAULT_FIELDS,
                "page": page,
                "per_page": per_page,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("verses") or []
        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected response shape for chapter {chapter_number}, page {page}: {payload}")

        verses.extend(batch)
        pagination = payload.get("pagination") or {}
        current_page = int(pagination.get("current_page", page))
        next_page = pagination.get("next_page")
        total_pages = int(pagination.get("total_pages", current_page))

        if next_page in (None, "", False) or current_page >= total_pages:
            break
        page = int(next_page)

    return verses


def clean_translation_text(text: str) -> str:
    cleaned = HTML_TAG_RE.sub(" ", text or "")
    cleaned = html.unescape(cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def normalize_translation_rows(verses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    translation_name = DEFAULT_TRANSLATION_NAME

    for verse in verses:
        verse_key = str(verse.get("verse_key") or "")
        if not verse_key or ":" not in verse_key:
            continue
        surah_str, ayah_str = verse_key.split(":", 1)
        translations = verse.get("translations") or []
        first_translation = translations[0] if translations else {}
        if first_translation.get("resource_name"):
            translation_name = first_translation["resource_name"]

        rows.append(
            {
                "surah_no": int(surah_str),
                "ayah_no": int(ayah_str),
                "ayah_key": verse_key,
                "translation_name": translation_name,
                "language": first_translation.get("language_name") or "english",
                "source_id": f"qf:{first_translation.get('resource_id') or ''}",
                "text_display": clean_translation_text(first_translation.get("text") or ""),
                "text_raw_html": (first_translation.get("text") or "").strip(),
            }
        )

    rows.sort(key=lambda row: (row["surah_no"], row["ayah_no"]))
    return rows, translation_name


def write_csv(rows: list[dict[str, Any]], output_path: Path, *, overwrite: bool) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not overwrite:
        raise SystemExit(f"Output already exists: {output_path}. Use --overwrite to replace it.")

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "surah_no",
                "ayah_no",
                "ayah_key",
                "translation_name",
                "language",
                "source_id",
                "text_display",
                "text_raw_html",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    headers = build_headers(
        client_id=args.client_id,
        auth_token=args.auth_token,
        auth_base_url=args.auth_base_url,
        client_secret=args.client_secret,
    )

    all_verses: list[dict[str, Any]] = []
    with httpx.Client(headers=headers, follow_redirects=True) as client:
        for chapter_number in range(1, 115):
            verses = fetch_verses_for_chapter(
                client,
                api_base_url=args.api_base_url,
                chapter_number=chapter_number,
                translation_id=args.translation_id,
            )
            if not verses:
                raise RuntimeError(f"No verses returned for chapter {chapter_number}")
            all_verses.extend(verses)
            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

    rows, translation_name = normalize_translation_rows(all_verses)
    if len(rows) != 6236:
        raise RuntimeError(f"Expected 6236 ayah rows, got {len(rows)}")

    write_csv(rows, args.output, overwrite=args.overwrite)
    print(
        f"Saved {len(rows)} rows to {args.output} using translation '{translation_name}' (id={args.translation_id}).",
        file=sys.stdout,
    )


if __name__ == "__main__":
    main()
