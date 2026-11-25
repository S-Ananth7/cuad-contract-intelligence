# 0010. Separate clients, sign in with Google or Microsoft, and keep an audit trail

Status: accepted. Replaces the shared access code of [ADR 0009](0009-hosted-live-review.md) and the single API key of [ADR 0008](0008-live-review-reuses-the-pipeline.md).

## Context

The hosted live review (ADR 0009) was gated by one shared access code. Everyone with the code saw and could delete every upload, reviewer names were typed, and nothing recorded who did what. That is acceptable for one client you know, not for several clients whose contracts must never reach each other.

## Decision

- **Clients.** An upload belongs to exactly one client (`live_submissions.tenant`). Every function that reads or changes uploads, answers or reviews takes the client id and puts it in the SQL, so an id that belongs to another client is answered as "not found". The client id never comes from anything a person types: it comes from the sign-in or from an API key.
- **Sign-in.** Streamlit's built-in OpenID Connect login (`st.login`) with Google, and optionally Microsoft. A person may enter only if their verified email is on the allow-list (`live_users`), which also says which client they belong to. The list is checked on every page run, so removing someone takes effect on their next click.
- **Trusting the email.** Google states whether it verified the address; we require it. Microsoft does not, and in a shared app anyone can write any address into their own account, so a Microsoft address counts only when the account comes from an organisation listed as trusted by its tenant id and the token's issuer and tenant agree (`live/signin.py`).
- **API keys.** One key per client, stored only as a hash, shown once. The endpoints exist only when `LIVE_API=1`.
- **Audit trail.** `live_audit` records login, upload, view, review and delete with who, when and the file name, never the contract text. It outlives the upload it describes.
- **Retention and caps.** Each client has a retention period (default 30 days) and may have its own daily cap; a global daily cap protects the model bill. The worker deletes expired uploads every six hours while the page is in use; `live-admin purge` does the same on demand.
- **Administration** is a command (`python -m cuad_ai live-admin`), not manual edits in the database.

## Consequences

- One client cannot read, review, delete or even detect another client's uploads, and this is covered by automated tests at the database and API levels.
- Reviewer names are verified email addresses, so a decision can be traced to a person.
- The free hosting tiers stay: Streamlit Community Cloud and Neon. The in-page worker and sleeping apps remain (ADR 0009); retention clean-up runs only while the page is used.
- Each client's Microsoft sign-in needs its own provider entry in the secrets, because Streamlit supports one organisation endpoint per provider. Google needs one entry for all clients.
- Old uploads from before this change sit under a `legacy` client nobody can sign in to, and are deleted by the retention period.
- Not provided: single sign-on (SAML), roles within a client, per-client encryption keys, and a guaranteed backup (see [security](../security.md)).

## Alternatives considered

- **Keep one code per client.** Cheaper, but a code is shared, never revoked per person, and says nothing about who acted.
- **Passwords stored by us.** More code and more risk than letting Google verify the person.
- **A separate database per client.** Stronger separation but each one needs setting up and paying for; the same-database approach is tested and can be tightened later with row-level security.
- **Row-level security in Postgres now.** A good next hardening step; the application-level checks come first because they are covered by tests today.
