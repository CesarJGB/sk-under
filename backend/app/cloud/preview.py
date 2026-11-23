"""Comprobaciones estructurales antes de interpretar una vista previa.

La Fase 5.3 demostró que el agregado distingue una sección ausente de una
sección nula y que el formateador de la vista previa puede recibir colecciones
nulas. Este módulo no reproduce `GetExtraDescribe` ni conoce su esquema
completo: solo informa de los estados que el agregado ya permite distinguir.
"""

from dataclasses import dataclass
from typing import Literal

from ..cloud_save import OPTIONAL_SECTIONS, ReconstructedCloudSave

type PreviewIssueCode = Literal["null_section", "missing_section"]


@dataclass(frozen=True)
class PreviewIssue:
    code: PreviewIssueCode
    section: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "section": self.section}


def preview_issues(save: ReconstructedCloudSave) -> tuple[PreviewIssue, ...]:
    """Describe secciones ausentes o nulas que la vista previa podría necesitar.

    No es un veredicto de compatibilidad: una sección ausente puede ser normal
    y una nula puede ser intencional. El cliente oficial decide qué colecciones
    exige cada versión y cada rama de restauración.
    """
    issues: list[PreviewIssue] = []
    for name in OPTIONAL_SECTIONS:
        if name not in save.data.optional_sections:
            issues.append(PreviewIssue("missing_section", name))
        elif save.data.optional_sections[name] is None:
            issues.append(PreviewIssue("null_section", name))
    return tuple(issues)
