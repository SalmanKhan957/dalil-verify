"""Backfill matn_embeddings for Bukhari hadith using OpenAI.

Usage:
    python -m pipelines.hadith_topical.backfill_embeddings
"""
from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import text as sa_text
from infrastructure.config.settings import settings
from infrastructure.db.session import get_session

# Use a standard print for the very first line to verify execution
print("--- DALIL Embedding Backfill Pipeline Initialized ---")

log = logging.getLogger(__name__)

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIM = 1536
_BATCH_SIZE = 100

def _get_embeddings_from_openai(texts: list[str]) -> list[list[float]] | None:
    if not settings.openai_api_key.strip():
        print("ERROR: OPENAI_API_KEY is missing from settings.")
        return None

    payload = {
        "model": _EMBEDDING_MODEL,
        "input": [t.replace("\n", " ") for t in texts],
        "dimensions": _EMBEDDING_DIM
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30.0) as response:
            res_payload = json.loads(response.read().decode("utf-8"))
            data = sorted(res_payload.get("data", []), key=lambda x: x["index"])
            return [item["embedding"] for item in data]
    except Exception as e:
        print(f"CRITICAL: OpenAI API error: {e}")
        return None

def backfill_bukhari_embeddings(database_url: str | None = None):
    print(f"Connecting to database to check for missing Bukhari embeddings...")

    with get_session(database_url=database_url) as session:
        # Diagnostic: Count all Bukhari records first
        total_stmt = sa_text("""
            SELECT count(*) FROM hadith_entries he 
            JOIN source_works sw ON he.work_id = sw.id
            WHERE sw.source_id = 'hadith:sahih-al-bukhari-en'
        """)
        total_count = session.execute(total_stmt).scalar()
        print(f"Total Bukhari records found in DB: {total_count}")

        fetch_stmt = sa_text("""
            SELECT he.id, he.english_text, he.metadata_json
            FROM hadith_entries he
            JOIN source_works sw ON he.work_id = sw.id
            WHERE sw.source_id = 'hadith:sahih-al-bukhari-en'
              AND (he.metadata_json->>'matn_embedding' IS NULL)
              AND he.english_text IS NOT NULL
            ORDER BY he.id ASC
        """)

        rows = session.execute(fetch_stmt).fetchall()
        if not rows:
            print("No records found requiring backfill. Check if DATABASE_URL matches your psql terminal.")
            return

        print(f"Successfully identified {len(rows)} records needing embeddings.")

        for i in range(0, len(rows), _BATCH_SIZE):
            batch = rows[i : i + _BATCH_SIZE]
            batch_ids = [r[0] for r in batch]
            batch_texts = [r[1] for r in batch]
            batch_metas = [dict(r[2]) if r[2] else {} for r in batch]

            print(f" -> Processing batch {i//_BATCH_SIZE + 1}... (IDs {batch_ids[0]}-{batch_ids[-1]})")

            embeddings = _get_embeddings_from_openai(batch_texts)
            
            if not embeddings:
                print("Failed to get embeddings for this batch. Stopping.")
                break

            for idx, entry_id in enumerate(batch_ids):
                meta = batch_metas[idx]
                meta['matn_embedding'] = embeddings[idx]
                
                update_stmt = sa_text("""
                    UPDATE hadith_entries
                    SET metadata_json = :meta
                    WHERE id = :id
                """)
                session.execute(update_stmt, {"meta": json.dumps(meta), "id": entry_id})
            
            session.commit()
            print(f"    [OK] Batch saved to database.")

    print("--- Backfill Complete ---")

if __name__ == "__main__":
    # Force logging to INFO even if other modules have already set it up
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s', force=True)
    backfill_bukhari_embeddings()