"""Turn the claims from a Google or Microsoft sign-in into an email address we are willing to trust.

The sign-in only proves who the provider says the person is. Two things keep that safe:
  - Google states whether it verified the address (email_verified). We require it.
  - Microsoft does not, and in a shared (multi-organisation) app an attacker can put any address in their own
    account's email claim. So a Microsoft address is accepted only when the account comes from an organisation
    you listed as trusted (its Entra tenant id), and the token's issuer, tenant and that list all agree.
Whether the address may use the service, and for which client, is decided separately by the allow-list in the database.
"""
MICROSOFT = "https://login.microsoftonline.com/"


def tenant_ids(text):
    """'id1, id2' -> {'id1', 'id2'} (lower case). Used for the LIVE_TRUSTED_MS_TENANTS setting."""
    return {part.strip().lower() for part in (text or "").split(",") if part.strip()}


def _address(value):
    value = str(value or "").strip().lower()
    return value if "@" in value else None


def verified_email(claims, trusted_microsoft_tenants=()):
    """The lower-case email to look up in the allow-list, or None when the sign-in cannot be trusted."""
    claims = claims or {}
    if claims.get("email_verified") is True or str(claims.get("email_verified")).lower() == "true":
        return _address(claims.get("email"))
    issuer = str(claims.get("iss") or "")
    if issuer.startswith(MICROSOFT):
        tenant = issuer[len(MICROSOFT):].split("/")[0].lower()
        if tenant and tenant == str(claims.get("tid") or "").lower() and tenant in set(trusted_microsoft_tenants):
            return _address(claims.get("email") or claims.get("preferred_username"))
    return None
