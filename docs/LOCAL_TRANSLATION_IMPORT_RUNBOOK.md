# Local Translation Import Runbook

Use this when you already have a local Quran translation text file and want Dalil Verify to display English alongside matched Arabic ayat/passages.

## Supported input format

This importer supports the common Tanzil-style line format:

```text
1|1|In the name of Allah, the Merciful, the Compassionate
1|2|Praise be to Allah, the Lord of the entire universe.
```

It ignores blank lines and comment lines starting with `#`.

## Command

From the project root:

```bash
python -m scripts.ingestion.import_local_translation_text \
  --input-file PATH_TO_TRANSLATION_FILE \
  --translation-name "Towards Understanding the Quran" \
  --translator "Abul Ala Maududi" \
  --source-id "local:tanzil:maududi" \
  --source-name "tanzil_local_file" \
  --overwrite
```

This writes:

```text
data/processed/quran_translations/quran_en_single_translation.csv
```

## Start API

```bash
uvicorn apps.api.main:app --reload
```

## Verify translation is loaded

Open:

```text
http://127.0.0.1:8000/health
```

You should see:

- `english_translation_loaded: true`
- `english_translation_rows_loaded: 6236`

## Example verifier test

```bash
curl -X POST "http://127.0.0.1:8000/verify/quran?debug=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"قل هو الله احد"}'
```

If the translation CSV is present, the API attaches `english_translation` to the matched ayah/passage.

## Notes

- Dalil Verify still matches **Arabic only**. The English translation is attached **after** Arabic citation resolution.
- Keep the original source file and source metadata for provenance.
- For commercial/public deployment, verify that your translation license allows your intended usage.
