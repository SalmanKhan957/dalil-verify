from domains.ask.route_types import AskRouteType
from domains.ask.workflows import explain_answer as module


def test_anchored_followup_hadith_bypasses_quran_repository_resolution(monkeypatch) -> None:
    route = {"route_type": AskRouteType.ANCHORED_FOLLOWUP_HADITH.value, "action_type": "explain"}

    def fail_repository_resolution(**kwargs):
        raise AssertionError("Quran repository resolution should be bypassed for anchored hadith follow-up")

    monkeypatch.setattr(module, "resolve_quran_repository_context", fail_repository_resolution)
    monkeypatch.setattr(module, "build_ask_plan", lambda *args, **kwargs: {"plan": "ok", "route": kwargs.get("route")})
    monkeypatch.setattr(module, "execute_plan", lambda plan, request=None, database_url=None: {"evidence": True})
    monkeypatch.setattr(module, "build_explain_answer_payload", lambda plan, evidence: {"ok": True, "plan": plan, "evidence": evidence})

    result = module.explain_answer(
        query="Summarize this hadith",
        route=route,
        request_context={"anchor_refs": ["hadith:sahih-al-bukhari-en:7"]},
    )

    assert result["ok"] is True
