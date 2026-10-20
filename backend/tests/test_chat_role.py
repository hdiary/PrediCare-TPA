import pytest
from fastapi import HTTPException

from api.routers.chat import _require_chat_role


@pytest.mark.parametrize("role", ["assure", "professionnel_sante"])
def test_chat_role_allows_insured_and_provider(role):
    _require_chat_role({"role": role})


def test_chat_role_error_names_both_allowed_roles():
    with pytest.raises(HTTPException) as error:
        _require_chat_role({"role": "administrateur"})

    assert error.value.status_code == 403
    assert "assurés" in error.value.detail
    assert "professionnels de santé" in error.value.detail
