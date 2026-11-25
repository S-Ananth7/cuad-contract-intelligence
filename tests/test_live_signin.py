import pytest

from cuad_ai.live.signin import tenant_ids, verified_email

TID = "11111111-2222-3333-4444-555555555555"
OTHER = "99999999-2222-3333-4444-555555555555"


def microsoft(**claims):
    return {"iss": f"https://login.microsoftonline.com/{TID}/v2.0", "tid": TID, **claims}


def test_a_verified_google_address_is_accepted_and_lower_cased():
    assert verified_email({"email": " Ann@Acme.COM ", "email_verified": True}) == "ann@acme.com"
    assert verified_email({"email": "ann@acme.com", "email_verified": "true"}) == "ann@acme.com"


@pytest.mark.parametrize("claims", [
    {}, None, {"email": "ann@acme.com"}, {"email": "ann@acme.com", "email_verified": False},
    {"email": "ann@acme.com", "email_verified": "false"}, {"email_verified": True},
    {"email": "not-an-email", "email_verified": True},
])
def test_an_unverified_or_missing_address_is_refused(claims):
    assert verified_email(claims, {TID}) is None


def test_a_microsoft_address_needs_a_trusted_organisation():
    claims = microsoft(email="Ann@Acme.com")
    assert verified_email(claims, {TID}) == "ann@acme.com"
    assert verified_email(claims, {OTHER}) is None  # a different organisation: anyone can claim any address there
    assert verified_email(claims) is None  # nothing trusted by default
    assert verified_email(microsoft(preferred_username="ann@acme.com"), {TID}) == "ann@acme.com"


def test_a_microsoft_token_whose_tenant_and_issuer_disagree_is_refused():
    assert verified_email({**microsoft(email="ann@acme.com"), "tid": OTHER}, {TID, OTHER}) is None
    forged = {"iss": "https://evil.example/" + TID, "tid": TID, "email": "ann@acme.com"}
    assert verified_email(forged, {TID}) is None


def test_the_trusted_tenant_setting_is_split_and_cleaned():
    assert tenant_ids(f" {TID.upper()} , {OTHER},, ") == {TID, OTHER}
    assert tenant_ids("") == set() and tenant_ids(None) == set()
