# Quran Foundation Translation Refresh Runbook

This runbook explains how to import one English Quran translation from Quran.Foundation into a local CSV for Dalil Verify.

## Purpose

The verifier remains Arabic-first for matching.
English translation is attached **after** an Arabic ayah or passage is identified.
This keeps matching deterministic while still letting the API return English display text.

## Output file

The importer writes to:

`data/processed/quran_translations/quran_en_single_translation.csv`

The API loads this file automatically at startup if it exists.

## Environment variables

Create a local `.env` file or export these in your shell:

- `QF_CLIENT_ID`
- `QF_CLIENT_SECRET`
- `QF_AUTH_BASE_URL`
- `QF_CONTENT_API_BASE_URL`
- `QF_TRANSLATION_ID`

Recommended production defaults:

- `QF_AUTH_BASE_URL=https://oauth2.quran.foundation`
- `QF_CONTENT_API_BASE_URL=https://apis.quran.foundation/content/api/v4`

Recommended pre-production defaults:

- `QF_AUTH_BASE_URL=https://prelive-oauth2.quran.foundation`
- `QF_CONTENT_API_BASE_URL=https://apis-prelive.quran.foundation/content/api/v4`

## Install dependencies

If you already have the project virtual environment, activate it and install dependencies.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

If `requirements.txt` gives encoding trouble on your machine, re-save it as UTF-8 once and re-run install.

## Import one translation

Example:

Windows PowerShell:

```powershell
$env:QF_CLIENT_ID="your-client-id"
$env:QF_CLIENT_SECRET="your-client-secret"
$env:QF_AUTH_BASE_URL="https://oauth2.quran.foundation"
$env:QF_CONTENT_API_BASE_URL="https://apis.quran.foundation/content/api/v4"
python -m scripts.ingestion.import_quran_foundation_translation --translation-id 131 --overwrite
```

macOS / Linux:

```bash
export QF_CLIENT_ID="your-client-id"
export QF_CLIENT_SECRET="your-client-secret"
export QF_AUTH_BASE_URL="https://oauth2.quran.foundation"
export QF_CONTENT_API_BASE_URL="https://apis.quran.foundation/content/api/v4"
python -m scripts.ingestion.import_quran_foundation_translation --translation-id 131 --overwrite
```

Replace `131` with the translation resource id you choose.

The script will:

1. Obtain an OAuth2 access token using client credentials.
2. Call Quran.Foundation Content API chapter by chapter.
3. Save exactly **6236** rows.
4. Store both:
   - `text_display` = cleaned plain text for API display
   - `text_raw_html` = raw translation text from the API

## Start the API

```bash
uvicorn apps.api.main:app --reload
```

## Check health

Open:

`http://127.0.0.1:8000/health`

You should see:

- `english_translation_loaded: true`
- `english_translation_rows_loaded: 6236`

## Test the verifier

Example request:

```bash
curl -X POST "http://127.0.0.1:8000/verify/quran?debug=true" \
  -H "Content-Type: application/json" \
  -d '{"text":"قل هو الله احد"}'
```

If translation import worked, `best_match` should include `english_translation`.

## Run tests

```bash
pytest -q
```

## Refresh workflow

Re-run the importer whenever you want to update the local translation CSV:

```bash
python -m scripts.ingestion.import_quran_foundation_translation --translation-id <ID> --overwrite
```

Then restart the API so the new CSV is reloaded.

## Safety notes

- Keep credentials server-side only.
- Do not commit `.env` with real secrets.
- Do not log access tokens or client secrets.
- If secrets were pasted into chat, email, screenshots, or shared docs, rotate them.
