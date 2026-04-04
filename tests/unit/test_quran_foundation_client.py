from __future__ import annotations

import json
import time

import httpx

from services.quran_foundation_client.auth import QuranFoundationTokenProvider
from services.quran_foundation_client.client import QuranFoundationContentClient
from services.quran_foundation_client.config import QuranFoundationSettings
from services.quran_foundation_client.resources_api import QuranFoundationResourcesAPI
from services.quran_foundation_client.tafsir_api import QuranFoundationTafsirAPI


TEST_SETTINGS = QuranFoundationSettings(
    environment="preprod",
    client_id="client-id",
    client_secret="client-secret",
    auth_base_url="https://prelive-oauth2.quran.foundation",
    api_base_url="https://apis-prelive.quran.foundation",
    timeout_seconds=5.0,
    token_skew_seconds=60,
)


def test_token_provider_caches_until_expiry() -> None:
    calls = {"token": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth2/token"
        calls["token"] += 1
        return httpx.Response(
            200,
            json={"access_token": "token-1", "token_type": "Bearer", "expires_in": 3600, "scope": "content"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = QuranFoundationTokenProvider(settings=TEST_SETTINGS, client=client)

    assert provider.get_access_token() == "token-1"
    assert provider.get_access_token() == "token-1"
    assert calls["token"] == 1
    client.close()


def test_content_client_retries_once_on_401() -> None:
    calls = {"token": 0, "content": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            calls["token"] += 1
            return httpx.Response(
                200,
                json={"access_token": f"token-{calls['token']}", "expires_in": 3600},
            )
        if request.url.path == "/content/api/v4/resources/tafsirs":
            calls["content"] += 1
            if calls["content"] == 1:
                return httpx.Response(401, json={"message": "expired"})
            return httpx.Response(
                200,
                json={
                    "tafsirs": [
                        {"id": 169, "name": "Tafsir Ibn Kathir", "author_name": "Ibn Kathir", "slug": "ibn-kathir"}
                    ]
                },
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = QuranFoundationTokenProvider(settings=TEST_SETTINGS, client=http_client)
    content_client = QuranFoundationContentClient(settings=TEST_SETTINGS, token_provider=provider, client=http_client)
    api = QuranFoundationResourcesAPI(content_client)

    items = api.list_tafsirs()

    assert len(items) == 1
    assert items[0].resource_id == 169
    assert calls["token"] == 2
    assert calls["content"] == 2
    http_client.close()


def test_tafsir_api_paginates_chapter_fetch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})

        if request.url.path == "/content/api/v4/tafsirs/169/by_chapter/1":
            page = int(request.url.params.get("page", "1"))
            if page == 1:
                return httpx.Response(
                    200,
                    json={
                        "tafsirs": [
                            {
                                "id": 1001,
                                "resource_id": 169,
                                "verse_id": 1,
                                "verse_key": "1:1",
                                "chapter_id": 1,
                                "verse_number": 1,
                                "text": "Commentary one",
                                "resource_name": "Tafsir Ibn Kathir",
                                "slug": "ibn-kathir",
                            }
                        ],
                        "pagination": {"per_page": 1, "current_page": 1, "next_page": 2},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "tafsirs": [
                        {
                            "id": 1002,
                            "resource_id": 169,
                            "verse_id": 2,
                            "verse_key": "1:2",
                            "chapter_id": 1,
                            "verse_number": 2,
                            "text": "Commentary two",
                            "resource_name": "Tafsir Ibn Kathir",
                            "slug": "ibn-kathir",
                        }
                    ],
                    "pagination": {"per_page": 1, "current_page": 2, "next_page": None},
                },
            )
        raise AssertionError(f"Unexpected path: {request.url.path}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = QuranFoundationTokenProvider(settings=TEST_SETTINGS, client=http_client)
    content_client = QuranFoundationContentClient(settings=TEST_SETTINGS, token_provider=provider, client=http_client)
    api = QuranFoundationTafsirAPI(content_client)

    items = list(api.iter_surah_tafsirs(resource_id=169, chapter_number=1, per_page=1))

    assert [item.verse_key for item in items] == ["1:1", "1:2"]
    http_client.close()
