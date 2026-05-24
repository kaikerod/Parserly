from __future__ import annotations

from dataclasses import dataclass

MASTER_ADMIN_EMAIL = "kaikevinicius789@gmail.com"
MASTER_ADMIN_ACCESS_LEVEL = "Administrador Master"
STANDARD_USER_ACCESS_LEVEL = "Usuário Padrão"
ALL_FEATURES_PERMISSION = "todas_as_funcionalidades"
BASIC_FEATURES_PERMISSION = "funcionalidades_basicas"


@dataclass(frozen=True, slots=True)
class SessionAccessProfile:
    access_level: str
    permissions: tuple[str, ...]


def get_session_access_profile(email: str) -> SessionAccessProfile:
    normalized_email = email.strip().lower()
    if normalized_email == MASTER_ADMIN_EMAIL:
        return SessionAccessProfile(
            access_level=MASTER_ADMIN_ACCESS_LEVEL,
            permissions=(ALL_FEATURES_PERMISSION,),
        )

    return SessionAccessProfile(
        access_level=STANDARD_USER_ACCESS_LEVEL,
        permissions=(BASIC_FEATURES_PERMISSION,),
    )
