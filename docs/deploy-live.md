# Hosting the live review for a client

The public demo (`app/streamlit_app.py`) is read-only. This guide hosts the **upload page** so a client can review their own contracts. It uses three free or low-cost pieces: a hosted Postgres (Neon), Streamlit Community Cloud for the page, and your model key. The decisions behind it are in [ADR 0009](adr/0009-hosted-live-review.md).

**Before you start:** the client's contract text goes to your model provider and is stored in the hosted database until deleted. Get the client's agreement first, and use a provider you have vetted.

## 1. Create the hosted database

1. Create a project at neon.tech (free plan is enough). Choose a region near you.
2. Copy the **connection string** (it starts with `postgresql://`, and ends with `sslmode=require`). Treat it like a password.

## 2. Copy the example bank into it

The pipeline compares answers with the lawyer-marked passages from CUAD. Copy them from your local database once (your local Postgres must be running with the bank loaded):

```powershell
$env:HOSTED_DATABASE_URL = "paste-the-neon-connection-string"
python scripts/copy_bank.py
```

It creates the tables, copies three of them (about 13,000 marked passages with their vectors, tens of megabytes) and prints the row counts. Running it again is safe.

## 3. Deploy the page on Streamlit Cloud

Create a new app (a second one; leave the public demo as it is):

| Field | Value |
|---|---|
| Repository | `S-Ananth7/cuad-contract-intelligence` |
| Branch | `main` |
| Main file path | `deploy/live/streamlit_app.py` |
| Python version (Advanced settings) | **3.12** (the embedding library may not support newer versions) |

Then open **Advanced settings > Secrets** and paste the values from `deploy/live/secrets.example.toml`, replacing every placeholder with your own: the Neon string, your model settings and an access code. Keep the daily cap low until you trust it.

## 4. Check it

1. Open the app URL. You should see only an access-code screen.
2. Enter the code, then upload `data/Brightwave_Orion_Software_Services_Agreement.txt` (any short contract works).
3. The first run downloads the embedding model, so it can take a few minutes. After that a contract takes 1 to 3 minutes. The progress bar should move.
4. Confirm one answer, reload, and check your decision is still there.

Send the client the URL and the code in separate messages.

## How it behaves

- **The worker runs inside the page.** Streamlit Cloud has no background process, so a thread does the work. It asks the database for jobs only while someone has used the page in the last 30 minutes.
- **Sleeping apps.** Streamlit Cloud puts idle apps to sleep. Uploads and decisions stay in the database. Opening the app wakes it and restarts the worker; a job interrupted mid-run is put back in the queue after 10 minutes without progress.
- **Cost control.** `LIVE_DAILY_CAP` (uploads per day, all users together), `LIVE_TOKEN_CAP` (tokens per upload) and `LIVE_MAX_CHARS` (file size). A typical contract uses about 100,000 tokens.
- **Access.** One shared code. Change the secret to lock everyone out and give a new code to let people back in. If the secret is missing the page stays closed.
- **Deleting data.** Each contract page has a delete button that removes the upload and everything derived from it.

## When something goes wrong

| You see | Likely cause |
|---|---|
| "The LIVE_ACCESS_CODE secret is missing" | Add it under Secrets and reboot the app |
| "The database did not answer" | Wrong `DATABASE_URL`, or the Neon project is paused; open the Neon console |
| "The background worker stopped…" | The message names the error. Often a wrong secret, or the embedding model could not download. Reboot the app |
| Upload stays "waiting" | The worker thread is not running; reboot the app and check the page for the warning above |
| "The model could not be reached" | `LLM_API_KEY`, `LLM_BASE_URL` or `LLM_MODEL` is wrong, or the provider is down |

## Not included

Per-person accounts, audit logs of who viewed what, PDF and Word upload, and an alert when the daily cap is hit. For a production rollout with several customers, move the worker to its own service ([ADR 0009](adr/0009-hosted-live-review.md)).
