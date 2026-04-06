from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "DEFAULT_QURAN_REPOSITORY_MODE": ("domains.quran.repositories.db_repository", "DEFAULT_QURAN_REPOSITORY_MODE"),
    "DEFAULT_QURAN_TEXT_WORK_SOURCE_ID": ("domains.quran.repositories.db_repository", "DEFAULT_QURAN_TEXT_WORK_SOURCE_ID"),
    "DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID": ("domains.quran.repositories.db_repository", "DEFAULT_QURAN_TRANSLATION_WORK_SOURCE_ID"),
    "SqlAlchemyQuranRepository": ("domains.quran.repositories.db_repository", "SqlAlchemyQuranRepository"),
    "build_arabic_work_seed": ("domains.quran.repositories.db_repository", "build_arabic_work_seed"),
    "build_surah_rows_from_arabic_csv": ("domains.quran.repositories.db_repository", "build_surah_rows_from_arabic_csv"),
    "build_translation_work_seed": ("domains.quran.repositories.db_repository", "build_translation_work_seed"),
    "resolve_quran_repository_mode": ("domains.quran.repositories.db_repository", "resolve_quran_repository_mode"),
    "DEFAULT_QURAN_ARABIC_PATH": ("domains.quran.repositories.metadata_repository", "DEFAULT_QURAN_ARABIC_PATH"),
    "load_quran_metadata": ("domains.quran.repositories.metadata_repository", "load_quran_metadata"),
    "DEFAULT_QURAN_PASSAGE_DATA_PATH": ("domains.quran.repositories.runtime_assets_repository", "DEFAULT_QURAN_PASSAGE_DATA_PATH"),
    "DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH": ("domains.quran.repositories.runtime_assets_repository", "DEFAULT_QURAN_PASSAGE_NEIGHBOR_INDEX_PATH"),
    "DEFAULT_QURAN_TRANSLATION_PATH": ("domains.quran.repositories.runtime_assets_repository", "DEFAULT_QURAN_TRANSLATION_PATH"),
    "DEFAULT_QURAN_UTHMANI_DATA_PATH": ("domains.quran.repositories.runtime_assets_repository", "DEFAULT_QURAN_UTHMANI_DATA_PATH"),
    "DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH": ("domains.quran.repositories.runtime_assets_repository", "DEFAULT_QURAN_UTHMANI_PASSAGE_DATA_PATH"),
    "RuntimeArtifactError": ("domains.quran.repositories.runtime_assets_repository", "RuntimeArtifactError"),
    "QuranRuntimeArtifactBundle": ("domains.quran.repositories.runtime_assets_repository", "QuranRuntimeArtifactBundle"),
    "resolve_runtime_artifact_bundle": ("domains.quran.repositories.runtime_assets_repository", "resolve_runtime_artifact_bundle"),
    "inspect_runtime_artifact_bundle": ("domains.quran.repositories.runtime_assets_repository", "inspect_runtime_artifact_bundle"),
    "build_runtime_manifest_for_bundle": ("domains.quran.repositories.runtime_assets_repository", "build_runtime_manifest_for_bundle"),
    "write_runtime_manifest": ("domains.quran.repositories.runtime_assets_repository", "write_runtime_manifest"),
    "load_quran_row_index": ("domains.quran.repositories.text_repository", "load_quran_row_index"),
    "lookup_quran_span": ("domains.quran.repositories.text_repository", "lookup_quran_span"),
    "attach_english_translation": ("domains.quran.repositories.translation_repository", "attach_english_translation"),
    "fetch_translation_span": ("domains.quran.repositories.translation_repository", "fetch_translation_span"),
    "load_english_translation_map": ("domains.quran.repositories.translation_repository", "load_english_translation_map"),
    "load_translation_row_index": ("domains.quran.repositories.translation_repository", "load_translation_row_index"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), attr_name)
