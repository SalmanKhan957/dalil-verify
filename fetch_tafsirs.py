import json
from pathlib import Path
from infrastructure.clients.quran_foundation import (
    QuranFoundationContentClient,
    QuranFoundationResourcesAPI,
    QuranFoundationSettings,
)

def fetch_and_export_tafsirs():
    # 1. Initialize client and fetch data
    settings = QuranFoundationSettings.from_env()
    with QuranFoundationContentClient.from_settings(settings) as client:
        api = QuranFoundationResourcesAPI(client)
        tafsirs = api.list_tafsirs(language="en")

    print(f"Found {len(tafsirs)} English tafsir resources:\n")

    # 2. Print sorted output to console
    sorted_tafsirs = sorted(
        tafsirs, 
        key=lambda x: (x.author_name or "", x.name or "", x.resource_id)
    )
    
    for item in sorted_tafsirs:
        print(
            f"{item.resource_id}\t"
            f"name={item.name}\t"
            f"author={item.author_name or '-'}\t"
            f"slug={item.slug or '-'}\t"
            f"lang={item.language_name or '-'}"
        )

    # 3. Format and save raw JSON payload
    payload = [
        {
            "resource_id": t.resource_id,
            "name": t.name,
            "author_name": t.author_name,
            "slug": t.slug,
            "language_name": t.language_name,
            "raw": t.raw,
        }
        for t in tafsirs
    ]

    out = Path("data/raw/quran_foundation/tafsir_available_en.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Wrote {len(payload)} resources -> {out}")

if __name__ == "__main__":
    fetch_and_export_tafsirs()