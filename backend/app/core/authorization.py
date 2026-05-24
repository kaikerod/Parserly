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
    if is_master_admin_email(email):
        return SessionAccessProfile(
            access_level=MASTER_ADMIN_ACCESS_LEVEL,
            permissions=(ALL_FEATURES_PERMISSION,),
        )

    return SessionAccessProfile(
        access_level=STANDARD_USER_ACCESS_LEVEL,
        permissions=(BASIC_FEATURES_PERMISSION,),
    )


def is_master_admin_email(email: str) -> bool:
    return email.strip().lower() == MASTER_ADMIN_EMAIL
