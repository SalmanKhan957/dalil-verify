from __future__ import annotations

from dataclasses import dataclass
import os

from domains.quran.repositories.db_repository import (
    DEFAULT_QURAN_TEXT_WORK_SOURCE_ID,
    DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID,
    is_database_required,
    resolve_quran_repository_mode,
)
from domains.source_registry.db_registry import SourceRegistryDatabaseError
from domains.source_registry.registry import (
    SOURCE_REGISTRY_BOOTSTRAP,
    resolve_quran_text_source,
    resolve_quran_translation_source,
)
from infrastructure.db.session import get_database_url
from shared.schemas.source_record import SourceRecord


@dataclass(frozen=True, slots=True)
class QuranRepositoryContext:
    repository_mode: str
    database_url: str | None
    quran_work_source_id: str
    translation_work_source_id: str
    source_resolution_strategy: str = "registry"


@dataclass(frozen=True, slots=True)
class QuranRepositoryGovernanceIssue:
    code: str
    message: str
    severity: str = "error"


_ENV_QURAN_TEXT_SOURCE_IDS = ("DALIL_QURAN_TEXT_SOURCE_ID",)
_ENV_QURAN_TRANSLATION_SOURCE_IDS = ("DALIL_QURAN_TRANSLATION_SOURCE_ID",)


def _read_env_source_id(variable_names: tuple[str, ...]) -> str | None:
    for name in variable_names:
        value = os.getenv(name)
        if value is None:
            continue
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return None


def _resolve_requested_quran_text_source_id(requested_source_id: str | None) -> str | None:
    return requested_source_id or _read_env_source_id(_ENV_QURAN_TEXT_SOURCE_IDS) or DEFAULT_QURAN_TEXT_WORK_SOURCE_ID


def _resolve_requested_quran_translation_source_id(requested_source_id: str | None) -> str | None:
    return (
        requested_source_id
        or _read_env_source_id(_ENV_QURAN_TRANSLATION_SOURCE_IDS)
        or DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID
    )


def resolve_requested_quran_repository_source_inputs(
    *,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
) -> tuple[str | None, str | None]:
    return (
        _resolve_requested_quran_text_source_id(quran_work_source_id),
        _resolve_requested_quran_translation_source_id(translation_work_source_id),
    )


def _resolve_bootstrap_quran_text_source(requested_source_id: str | None) -> SourceRecord | None:
    if requested_source_id:
        source = SOURCE_REGISTRY_BOOTSTRAP.get(requested_source_id)
        if source is None or source.source_domain != "quran" or source.source_kind != "canonical_text":
            return None
        if not (source.enabled and source.approved_for_answering):
            return None
        return source

    eligible = [
        source
        for source in SOURCE_REGISTRY_BOOTSTRAP.values()
        if source.source_domain == "quran"
        and source.source_kind == "canonical_text"
        and source.enabled
        and source.approved_for_answering
    ]
    return sorted(eligible, key=lambda source: (source.priority_rank, source.source_id))[0] if eligible else None


def _resolve_bootstrap_quran_translation_source(
    requested_source_id: str | None,
    *,
    language: str | None = "en",
) -> SourceRecord | None:
    if requested_source_id:
        source = SOURCE_REGISTRY_BOOTSTRAP.get(requested_source_id)
        if source is None or source.source_domain != "quran" or source.source_kind != "translation":
            return None
        if not (source.enabled and source.approved_for_answering):
            return None
        if language is not None and source.language != language:
            return None
        return source

    eligible = [
        source
        for source in SOURCE_REGISTRY_BOOTSTRAP.values()
        if source.source_domain == "quran"
        and source.source_kind == "translation"
        and source.enabled
        and source.approved_for_answering
    ]
    if language is not None:
        filtered = [source for source in eligible if source.language == language]
        if filtered:
            eligible = filtered
    return sorted(eligible, key=lambda source: (source.priority_rank, source.source_id))[0] if eligible else None


def resolve_quran_repository_context(
    *,
    repository_mode: str | None = None,
    database_url: str | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
) -> QuranRepositoryContext:
    resolved_mode = resolve_quran_repository_mode(repository_mode)
    resolved_database_url = database_url
    requested_quran_source_id = _resolve_requested_quran_text_source_id(quran_work_source_id)
    requested_translation_source_id = _resolve_requested_quran_translation_source_id(translation_work_source_id)

    if resolved_database_url is None and resolved_mode in {"db_preferred", "db_only"}:
        try:
            resolved_database_url = get_database_url()
        except RuntimeError:
            if is_database_required(resolved_mode):
                raise

    source_resolution_strategy = "registry"
    try:
        resolved_quran_source = resolve_quran_text_source(
            requested_quran_source_id,
            database_url=resolved_database_url,
        )
        resolved_translation_source = resolve_quran_translation_source(
            requested_translation_source_id,
            database_url=resolved_database_url,
            language="en",
        )
    except SourceRegistryDatabaseError:
        if is_database_required(resolved_mode):
            raise
        source_resolution_strategy = "bootstrap_fallback"
        resolved_quran_source = _resolve_bootstrap_quran_text_source(requested_quran_source_id)
        resolved_translation_source = _resolve_bootstrap_quran_translation_source(
            requested_translation_source_id,
            language="en",
        )

    if resolved_quran_source is None:
        raise ValueError(
            f"No enabled+approved Quran canonical text source available for source_id={requested_quran_source_id!r}"
        )

    if resolved_translation_source is None:
        raise ValueError(
            f"No enabled+approved Quran translation source available for source_id={requested_translation_source_id!r}"
        )

    return QuranRepositoryContext(
        repository_mode=resolved_mode,
        database_url=resolved_database_url,
        quran_work_source_id=str(resolved_quran_source.source_id or DEFAULT_QURAN_TEXT_WORK_SOURCE_ID),
        translation_work_source_id=str(
            resolved_translation_source.source_id or DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID
        ),
        source_resolution_strategy=source_resolution_strategy,
    )


def inspect_quran_repository_runtime(
    *,
    repository_mode: str | None = None,
    database_url: str | None = None,
    quran_work_source_id: str | None = None,
    translation_work_source_id: str | None = None,
) -> dict[str, object]:
    issues: list[QuranRepositoryGovernanceIssue] = []
    context: QuranRepositoryContext | None = None

    try:
        context = resolve_quran_repository_context(
            repository_mode=repository_mode,
            database_url=database_url,
            quran_work_source_id=quran_work_source_id,
            translation_work_source_id=translation_work_source_id,
        )
    except RuntimeError as exc:
        issues.append(
            QuranRepositoryGovernanceIssue(
                code="quran_repository_database_url_required",
                message=str(exc),
                severity="error",
            )
        )
    except SourceRegistryDatabaseError as exc:
        issues.append(
            QuranRepositoryGovernanceIssue(
                code="quran_source_registry_database_unavailable",
                message=str(exc),
                severity="error",
            )
        )
    except ValueError as exc:
        message = str(exc)
        code = "quran_repository_source_resolution_failed"
        if "translation source" in message:
            code = "quran_translation_source_not_available"
        elif "canonical text source" in message:
            code = "quran_text_source_not_available"
        issues.append(QuranRepositoryGovernanceIssue(code=code, message=message, severity="error"))

    if context is not None and context.source_resolution_strategy == "bootstrap_fallback":
        issues.append(
            QuranRepositoryGovernanceIssue(
                code="quran_source_registry_bootstrap_fallback",
                message="Quran repository source selection fell back to bootstrap registry defaults because DB-backed source registry lookup was unavailable.",
                severity="warning",
            )
        )

    return {
        "checked": True,
        "repository_mode": context.repository_mode if context else resolve_quran_repository_mode(repository_mode),
        "database_url": context.database_url if context else database_url,
        "quran_work_source_id": context.quran_work_source_id if context else _resolve_requested_quran_text_source_id(quran_work_source_id),
        "translation_work_source_id": context.translation_work_source_id
        if context
        else _resolve_requested_quran_translation_source_id(translation_work_source_id),
        "source_resolution_strategy": context.source_resolution_strategy if context else "unresolved",
        "issue_count": len(issues),
        "warning_count": sum(1 for issue in issues if issue.severity == "warning"),
        "error_count": sum(1 for issue in issues if issue.severity == "error"),
        "issues": [
            {"code": issue.code, "message": issue.message, "severity": issue.severity} for issue in issues
        ],
    }
