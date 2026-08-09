import pytest
from pydantic import ValidationError

from api.v1.auth.schemas import LocalePreferenceRequest
from models.sql.user import User
from utils.api_errors import StableAPIError


def test_locale_schema_accepts_only_supported_locales():
    assert LocalePreferenceRequest(preferred_locale="en").preferred_locale == "en"
    assert LocalePreferenceRequest(preferred_locale="ar").preferred_locale == "ar"
    with pytest.raises(ValidationError):
        LocalePreferenceRequest(preferred_locale="fr")


def test_user_model_declares_locale_constraint():
    constraints = {constraint.name: str(constraint.sqltext) for constraint in User.__table__.constraints if constraint.name}
    assert "ck_user_preferred_locale" in constraints
    assert "'en'" in constraints["ck_user_preferred_locale"]
    assert "'ar'" in constraints["ck_user_preferred_locale"]


def test_stable_api_error_preserves_legacy_detail_and_machine_contract():
    error = StableAPIError(
        429,
        "AUTH_RATE_LIMITED",
        "Too many failed login attempts.",
        params={"retry_after_seconds": 30},
        headers={"Retry-After": "30"},
    )
    assert error.status_code == 429
    assert error.response_body() == {
        "detail": "Too many failed login attempts.",
        "code": "AUTH_RATE_LIMITED",
        "params": {"retry_after_seconds": 30},
    }
    assert error.headers == {"Retry-After": "30"}
