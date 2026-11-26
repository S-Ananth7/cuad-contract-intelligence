# Hosting the live review

This guide deploys the **upload page** for real clients: sign in with Google, each client sees only its own contracts, and an audit trail records who did what. It uses a hosted Postgres (Neon), Streamlit Community Cloud for the page, and your model key. Decisions: [ADR 0009](adr/0009-hosted-live-review.md) (hosting) and [ADR 0010](adr/0010-clients-sign-in-and-audit.md) (clients and sign-in). What is and is not protected: [security.md](security.md).

**Before you start:** a client's contract text goes to your model provider and is stored in the hosted database until it is deleted or its retention period ends. Agree this with each client first and use a provider whose terms suit them.

## 1. Create the hosted database

1. Create a project at neon.tech (the free plan is enough to start). Choose a region near you.
2. Copy the **connection string** (it starts with `postgresql://` and ends with `sslmode=require`). Treat it like a password and put it only in `.env` as `HOSTED_DATABASE_URL` and in the app's Secrets as `DATABASE_URL`.

## 2. Copy the example bank into it

The pipeline compares answers with the lawyer-marked passages from CUAD. Copy them from your local database once (your local Postgres must be running with the bank loaded):

```powershell
python scripts/copy_bank.py
```

It creates the tables, copies three of them (about 13,000 marked passages with their vectors) and prints the row counts. Running it again is safe.

## 3. Create the Google sign-in

1. At console.cloud.google.com create a project, then open **Google Auth Platform** (or APIs & Services > OAuth consent screen).
2. Set up the consent screen: choose **External**, enter an app name and your email, keep only the `openid`, `email` and `profile` scopes, and **publish** the app. (Left in "Testing", only listed test users can sign in.)
3. Create an **OAuth client ID** of type **Web application**. Under *Authorized redirect URIs* add `https://YOUR-APP.streamlit.app/oauth2callback` with your app's exact address.
4. Copy the client ID and secret into the app's Secrets (next step), nowhere else.
5. Make a cookie secret: `python -c "import secrets; print(secrets.token_hex(32))"`.

*Microsoft (optional):* register an app in Microsoft Entra, set `server_metadata_url` to `https://login.microsoftonline.com/TENANT-ID/v2.0/.well-known/openid-configuration` in an `[auth.microsoft]` section, add `microsoft` to `LIVE_SIGNIN_PROVIDERS`, and list the trusted organisations' tenant ids in `LIVE_TRUSTED_MS_TENANTS`. Streamlit supports one organisation endpoint per provider entry; for several organisations add one entry each, for example `[auth.microsoft_acme]`, and list the names in `LIVE_SIGNIN_PROVIDERS`.

## 4. Deploy the page on Streamlit Cloud

Create a new app (separate from the public demo, which uses `app/streamlit_app.py`):

| Field | Value |
|---|---|
| Repository | `S-Ananth7/cuad-contract-intelligence` |
| Branch | `main` |
| Main file path | `deploy/live/streamlit_app.py` |
| Python version (Advanced settings) | **3.12** (the embedding library may not support newer versions) |

Open **Advanced settings > Secrets** and paste the values from `deploy/live/secrets.example.toml`, replacing every placeholder with your own. `LIVE_SIGNIN_PROVIDERS` must sit above the first `[section]` line. Keep the daily caps low until you trust the setup.

Then open the app's **Settings > Sharing** and make the app **public**. This is not the same as open access: the page itself shows only the sign-in screen until a person on the allow-list signs in. A private Streamlit app would put Streamlit's own viewer login in front, and your clients would never reach yours.

*Optional: sample results for visitors.* Deploy the public read-only demo as its own app (main file `app/streamlit_app.py`), then add `LIVE_SAMPLE_URL = "https://YOUR-SAMPLE-APP.streamlit.app"` to the live app's Secrets and reboot it. The sign-in screen then shows a "View sample results" button. Without the secret there is no button.

## 5. Add clients and people

```powershell
python -m cuad_ai live-admin --hosted add-client acmecorp "Acme Corp" --retention 30
python -m cuad_ai live-admin --hosted add-user acmecorp person@acmecorp.com
python -m cuad_ai live-admin --hosted list
```

Use real values, with no angle brackets. One email belongs to exactly one client. Keep a client of your own, for example `internal`, for testing so your test contracts never mix with a client's.

## 6. Check it before the first client

1. Signed out (a private window): only the sign-in screen appears.
2. Sign in with a Google account that is **not** on the list: you see "This account does not have access".
3. **Two-account check.** Add one address to `internal` and another to a second client. Upload a small contract as the first. Sign in as the second: the workspace must be empty, with the first person's contract nowhere.
4. As the first account, wait for results, confirm one answer, reload, and check the decision is still there under your email.
5. Read the trail: `python -m cuad_ai live-admin --hosted audit internal` should show login, upload, view and review.

## 7. Everyday administration

| Task | Command |
|---|---|
| Add a person | `live-admin --hosted add-user CLIENT EMAIL` |
| Remove a person (effective on their next click) | `live-admin --hosted remove-user EMAIL` |
| Change a client's retention or cap | `live-admin --hosted add-client CLIENT "Name" --retention DAYS --daily-cap N` |
| New API key (shown once; the old one stops) | `live-admin --hosted key CLIENT` |
| Who did what | `live-admin --hosted audit CLIENT` |
| Delete expired uploads now | `live-admin --hosted purge` |

Running `add-client` again replaces that client's settings, so repeat the values you want to keep.

## How it behaves

- **The worker runs inside the page.** Streamlit Cloud has no background process, so a thread does the work. It asks the database for jobs only while someone used the page in the last 30 minutes, and it deletes expired uploads every six hours while it runs.
- **Sleeping apps.** Streamlit Cloud puts idle apps to sleep. Uploads and decisions stay in the database. Opening the app wakes it and restarts the worker; a job interrupted mid-run is put back in the queue after 10 minutes without progress.
- **Cost control.** `LIVE_DAILY_CAP` (uploads per client per day), `LIVE_GLOBAL_DAILY_CAP` (all clients together), `LIVE_TOKEN_CAP` (tokens per upload) and `LIVE_MAX_CHARS` (file size). A typical contract uses about 100,000 tokens.
- **Deleting data.** Each contract page has a delete button that removes the upload and everything derived from it. The audit trail keeps the file name and the fact of deletion, never the text.

## When something goes wrong

| You see | Likely cause |
|---|---|
| "Sign-in is not set up on this deployment" | The `[auth]` secrets are missing, or sit under another section heading. Fix them and reboot |
| Google says `redirect_uri_mismatch` | The redirect URI in Google and `redirect_uri` in Secrets are not the same address, character for character |
| Streamlit says "You do not have access to this app" | The address is wrong, or the app belongs to another Streamlit account, or it is private; open it from your app list and make it public |
| "This account does not have access" | The signed-in email is not on the allow-list; check `live-admin --hosted list` |
| "The database did not answer" | Wrong `DATABASE_URL`, or the Neon project is paused; open the Neon console |
| "The background worker stopped..." | The message names the error. Often a wrong secret, or the embedding model could not download. Reboot the app |
| Upload stays "waiting" | The worker thread is not running; reboot the app and check the page for the warning |
| "The model could not be reached" | `LLM_API_KEY`, `LLM_BASE_URL` or `LLM_MODEL` is wrong, or the provider is down |

## Not included

Single sign-on (SAML), roles within a client, per-client encryption keys, PDF and Word upload, an alert when a cap is hit, and guaranteed uptime or backups on the free tiers. For a larger rollout, move the worker to its own service and the database to a paid plan ([ADR 0009](adr/0009-hosted-live-review.md), [security.md](security.md)).
