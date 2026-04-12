from domains.conversation.followup_resolver import resolve_followup
from domains.conversation.session_state import ActiveScope, ConversationAnchorSet, SessionState


def test_resolve_tafheem_followup() -> None:
    state = SessionState(
        followup_ready=True,
        anchors=ConversationAnchorSet(refs=["quran:2:255"], domains=["quran", "tafsir"]),
        scope=ActiveScope(
            domains=["quran", "tafsir"],
            quran_ref="quran:2:255",
            quran_span_ref="quran:2:255",
            tafsir_source_ids=["tafsir:tafheem-al-quran-en", "tafsir:ibn-kathir-en"],
        ),
    )

    result = resolve_followup("What does Tafheem say?", state)

    assert result.matched is True
    assert result.target_source_id == "tafsir:tafheem-al-quran-en"


def test_resolve_hadith_summary_followup() -> None:
    state = SessionState(
        followup_ready=True,
        anchors=ConversationAnchorSet(refs=["hadith:sahih-al-bukhari-en:7"], domains=["hadith"]),
        scope=ActiveScope(
            domains=["hadith"],
            hadith_ref="hadith:sahih-al-bukhari-en:7",
            hadith_source_id="hadith:sahih-al-bukhari-en",
        ),
    )

    result = resolve_followup("Summarize this hadith", state)

    assert result.matched is True
    assert result.target_domain == "hadith"
