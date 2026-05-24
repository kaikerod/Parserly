from __future__ import annotations

import pytest

from app.core.authorization import (
    ALL_FEATURES_PERMISSION,
    BASIC_FEATURES_PERMISSION,
    MASTER_ADMIN_ACCESS_LEVEL,
    STANDARD_USER_ACCESS_LEVEL,
    get_session_access_profile,
    is_master_admin_email,
)


def test_master_email_gets_master_access_profile() -> None:
    profile = get_session_access_profile("kaikevinicius789@gmail.com")

    assert profile.access_level == MASTER_ADMIN_ACCESS_LEVEL
    assert profile.permissions == (ALL_FEATURES_PERMISSION,)
    assert is_master_admin_email("kaikevinicius789@gmail.com")


def test_master_email_matching_uses_system_normalization() -> None:
    profile = get_session_access_profile("  KaikeVinicius789@Gmail.com  ")

    assert profile.access_level == MASTER_ADMIN_ACCESS_LEVEL
    assert profile.permissions == (ALL_FEATURES_PERMISSION,)
    assert is_master_admin_email("  KaikeVinicius789@Gmail.com  ")


@pytest.mark.parametrize(
    "email",
    [
        "person@example.com",
        "kaikevinicius789+admin@gmail.com",
        "kaikevinicius789@gmail.com.br",
        "admin-kaikevinicius789@gmail.com",
    ],
)
def test_non_master_and_near_miss_emails_get_standard_access_profile(email: str) -> None:
    profile = get_session_access_profile(email)

    assert profile.access_level == STANDARD_USER_ACCESS_LEVEL
    assert profile.permissions == (BASIC_FEATURES_PERMISSION,)
    assert not is_master_admin_email(email)
