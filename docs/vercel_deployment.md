# Vercel login and hosted research snapshot

Production URL: [atlas-drug-repurposing.vercel.app](https://atlas-drug-repurposing.vercel.app/).

The project is deployed in the requested `resum-projects` team as `atlas-drug-repurposing`. The live site provides a server-protected login page, the real 1,054-entity / 1,639-relationship graph, measured model evaluation and the three saved real-disease analyses. These are actual published results from the local pipeline, not fabricated predictions. Every hosted analysis and agent view is labeled as recorded snapshot data.

This deployment does not expose the local Python server, PostgreSQL or Neo4j to the internet. It does not run fresh PyTorch training or new data ingestion. The published edition hides those controls and returns an explicit error if those endpoints are requested directly. New full-pipeline computation still runs in the local Python application. A separately provisioned public backend is required to extend that behavior online.

## Authentication

The initial workspace account is `researcher`. Its generated password and URL are saved in ignored local storage at `runtime/cloud-auth/login.txt`. Do not commit that file or the private `credentials.json`. The password is never embedded in frontend assets. Vercel stores `LOGIN_PASSWORD_HASH` and `SESSION_SECRET` as server-side secrets; the username is stored as configuration.

Passwords use a random salt and Node scrypt. Sessions use HMAC-SHA256 signatures and expire after eight hours. Cookies are host-only, Secure, HttpOnly and SameSite=Lax. All research API endpoints reject unauthenticated requests. Cross-origin state-changing requests are rejected. Logout clears the browser cookie. Additional administrator-provisioned accounts remain supported through `LOGIN_USERS_JSON`; the original accounts and their valid sessions are preserved. All accounts share the same published research snapshot. Self-service registration is now available through **Create account** on the login page. There is no password-reset email, role hierarchy or durable token revocation list. Request limiters are per function instance; use a managed identity provider and distributed abuse controls if deploying sensitive data or broad multi-user access.

### Self-service account creation

Choose **Create account**, enter a name or nickname, enter a password of at least 12 characters, and confirm it. Successful registration opens the protected workspace immediately; the account can subsequently sign in from a fresh session. Simple short names, spaces and international letters are accepted. Usernames are trimmed and normalized to lowercase, with a 32-character limit. Existing usernames cannot be overwritten, including the original administrator-provisioned accounts. The registration form uses a simple placeholder rather than displaying a long formatting rule.

Registered account records persist in the private Vercel Blob store `atlas-accounts`, connected to this project. Only username, salted password hash and creation timestamp are stored; plaintext passwords are not stored. The SDK uses authenticated private access and origin reads (`useCache:false`). A registry with ETag conditional writes prevents concurrent registrations from losing other users or overwriting the same username. The workspace currently caps self-service registrations at 100 accounts. The `BLOB_READ_WRITE_TOKEN` remains server-side and is never included in frontend assets or API responses. Storage failure fails closed with a temporary-unavailability response.

`POST /api/auth/register` accepts `{username,password,confirmPassword}`, validates input, rejects duplicate usernames with HTTP 409, writes the account privately and issues the same secure session cookie used by sign-in. `GET /api/auth/session` reports `registration_available`. Registration and login have separate per-instance rate limits. Both configured and privately stored accounts remain valid after deployment; persisted-user sessions recheck the registry. No private per-user research datasets are created: all accounts access the same published research results.

To add an account, run `node scripts/add_cloud_account.mjs <username>`, then configure the Vercel variables and redeploy using the commands below. Existing usernames cannot be overwritten by this helper. It saves the generated password only in ignored local storage and uploads only the username/password hash. `python scripts/verify_cloud_accounts.py` verifies that every configured account can sign in, access protected data and sign out without printing passwords. Account removal from the configured list invalidates its signed sessions; sessions for retained accounts remain valid.

## Packaging and deployment

The protected frontend is built to `runtime/atlas-frontend`, preserving the existing local dashboard build. The Build Output API package under `runtime/atlas-vercel/.vercel/output` includes only static UI assets and a Node 22 function. Original research data, saved candidate explanations and actual recorded agent logs are placed inside the private function bundle, not in public static JSON files. Model checkpoints, database credentials, raw caches and local database binaries are not uploaded.

Build and test from the repository root (with existing frontend dependencies installed):

```powershell
$env:VITE_AUTH_ENABLED='true'
Push-Location frontend
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\vite.cmd build --outDir ../runtime/atlas-frontend
Pop-Location
python scripts/prepare_vercel.py
node --test web/auth.test.mjs
```

The original deployment used the official Vercel CLI 65.12.1 and the existing authenticated CLI session. `scripts/configure_vercel_auth.py` sends values over stdin so secrets do not appear in command-line arguments or logs. It configures production/preview variables in the linked project. The initial creation helper is `node scripts/create_cloud_login.mjs`; it preserves existing credentials on repeated runs.

After linking the prepared directory to this project, production deployment is:

```powershell
python scripts/configure_vercel_auth.py
.\runtime\vercel-cli\node_modules\.bin\vercel.cmd deploy --prebuilt --prod --yes --scope resum-projects --cwd runtime/atlas-vercel
python scripts/verify_vercel.py
```

Only the explicit prepared Build Output bundle is published. Rotating the generated password/session secret requires updating the private credential material, setting the Vercel variables and redeploying. Rotate the session secret too if existing sessions must become invalid.

## Observed verification — 8 November 2026

- Ten frontend tests passed, including registration success, mismatched password rejection, duplicate-username feedback and sign-in behavior. TypeScript validation and the isolated production build passed.
- Eight Node tests passed: four authentication/API tests and four private-store tests covering hashed storage, persistence across adapter instances, concurrent registration, duplicate races, validation and simple names with spaces or international letters.
- The public production login page returned HTTP 200 and was visually inspected.
- The deployed API rejected unauthenticated data requests and invalid passwords; valid credentials established a Secure/HttpOnly session.
- All three saved disease analyses and their nine recorded agent stages were retrieved successfully after sign-in. Measured metrics matched the published graph hash. Logout restored HTTP 401 on protected data.
- Machine-readable evidence: `runtime/vercel-verification.json`. Login-page preview: `runtime/cloud-auth/login-page.png`.
- Live self-service registration, a subsequent independent sign-in, duplicate rejection and protected-data access passed. Both existing accounts remained usable. Evidence: `runtime/cloud-auth/registration-verification.json` and `account-verification.json`; registration-page preview: `runtime/cloud-auth/create-account-page.png`. A uniquely named QA account is retained with credentials only in ignored local test storage so the persistence verifier can repeat sign-in without creating more test accounts.

The hosted graph uses hash `424006a5efc2df196f73f0afb74a7db706dc9d4019a2324151ef6cd33cba9f38`. Results remain computational research hypotheses and do not establish clinical efficacy or safety.
