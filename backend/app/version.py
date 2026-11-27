"""Versión y capacidades públicas del backend.

Permite que el navegador distinga un servidor incompatible de un historial
vacío o de un almacén no disponible sin interpretar respuestas de error
ambiguas. No expone configuración, claves ni datos de las cuentas.
"""

from __future__ import annotations

import os

API_VERSION = "2026.11.27"
FEATURES = (
    "ios_local_import",
    "ios_read_only_report",
    "ios_native_read_only",
    "ios_candidate_preparation",
    "ios_remote_write_pending_validation",
    "ios_remote_write_experimental",
    "platform_capability_matrix",
    "native_backup_history",
    "native_backup_history_pagination",
    "native_backup_manual",
    "native_backup_preventive",
    "native_backup_restore_historical",
    "native_backup_metadata",
)


def version_info() -> dict[str, object]:
    commit = os.environ.get("SOURCE_COMMIT", "").strip()
    return {
        "service": "sk-under",
        "api_version": API_VERSION,
        "features": list(FEATURES),
        "commit": commit[:40] if commit and all(char in "0123456789abcdef" for char in commit[:40]) else None,
    }