# Security and data handling

What the hosted live review protects, how, and what it does not. It describes the code in this repository; the free hosting tiers it runs on set their own limits (last section). Decisions behind it: [ADR 0010](adr/0010-clients-sign-in-and-audit.md).

## Who can see what

- Every upload belongs to one client. Reading, listing, reviewing, deleting and exporting all go through functions that take the client id and filter on it in the database query. An upload id that belongs to another client is answered as "not found", the same as an id that does not exist.
- The client id comes from the sign-in (an allow-list lookup of the person's verified email) or from an API key. It is never taken from a form field, a URL or anything else a person can type.
- The reviewer name on a decision is the signed-in email, so a decision can be traced to a person.
- The owner (whoever holds the database and the hosting account) can read everything. That is true of any hosted service; the people who hold those credentials should be few.

## Signing in

- Google or Microsoft proves who the person is. The allow-list decides whether they may enter and for which client. A valid Google account that is not on the list sees "This account does not have access".
- Google addresses count only when Google marks them verified. Microsoft addresses count only for organisations listed by tenant id (`LIVE_TRUSTED_MS_TENANTS`), because Microsoft does not verify the address claim in a shared app.
- The allow-list is checked on every page run: removing a person takes effect on their next click, with no session to revoke.
- The page stays closed when sign-in is not configured.

## API access

HTTP endpoints exist only when `LIVE_API=1`. Each client has its own key, stored as a hash and shown once; making a new key stops the old one. A key reaches only its own client's uploads.

## What is recorded

`live_audit` stores who, when and what: login, upload, view, review, delete, and automatic deletion. It keeps the file name and never the contract text, and it remains after the upload is deleted. Read it with `python -m cuad_ai live-admin audit CLIENT`.

## What leaves the system

- **To the model provider:** the retrieved excerpts of each contract, sent to the provider named in `LLM_BASE_URL`. Choose a provider whose retention and training terms suit your clients, and tell clients which one it is.
- **To the database host (Neon):** the full contract text, the answers, the audit log. The connection requires TLS. Encryption at rest and backups are the host's, so read the host's current terms for your plan.
- **To Google or Microsoft:** the sign-in itself; no contract data.

## Retention and deletion

- Each client has a retention period (default 30 days). The worker deletes older uploads every six hours while the page is in use; `live-admin purge` does it on demand. An idle deployment cleans up on the next visit.
- A person can delete an upload at any time; the answers, reviews and text chunks derived from it go with it.
- Backups kept by the database host are outside this application's control.

## Cost and abuse limits

Per-client daily upload cap, a global daily cap, a token cap per upload and a file-size cap. A person who is not on the list cannot start a model call.

## What is not covered

- Single sign-on (SAML), roles within a client (everyone in a client sees all of that client's uploads) and approval workflows.
- Per-client encryption keys; clients share one database, separated by the checks above.
- Guaranteed uptime or backups on the free tiers: Streamlit Community Cloud puts idle apps to sleep, and Neon's free plan has limited storage and history.
- Content scanning: files are treated as text. Only `.txt` is accepted.
- Legal advice: answers are suggestions from a language model plus automatic checks.

## How the separation is verified

- `tests/test_live_tenants.py`: one client cannot read, list, review, clear a review of, or delete another client's upload; identical files from two clients are separate; caps apply per client; the allow-list, API keys, audit trail and retention behave as described.
- `tests/test_live_api.py`: another client's key gets "not found" for everything and leaves no trace in its audit log; every endpoint refuses a missing or wrong key.
- `tests/test_live_signin.py`: which emails are trusted, including a forged Microsoft token.
- `tests/test_hosted_app.py`: the page stays closed without sign-in.

Tests cover the code. Check the deployment too: before the first client, run the two-account check in [deploy-live.md](deploy-live.md#6-check-it-before-the-first-client).

## Before onboarding a client

1. Agree in writing what is uploaded, which model provider sees excerpts, and the retention period.
2. Create the client, set its retention and cap, and add only the people they name.
3. Run the two-account check on the live deployment.
4. Tell them how to ask for a person to be removed (you run `live-admin remove-user`).

## If something goes wrong

- A person should lose access: `live-admin remove-user EMAIL`. It applies on their next click.
- An API key leaked: `live-admin key CLIENT` makes a new one; the old one stops working.
- A client asks for deletion: delete their uploads in the page, or ask the owner to run the purge after shortening their retention. Then check the audit trail.
- Suspected exposure: read `live-admin audit CLIENT`, rotate the database password and the model key, and tell the affected client.
