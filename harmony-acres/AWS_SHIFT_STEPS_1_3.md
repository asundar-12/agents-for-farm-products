# AWS shift so far (steps 1–6) — notes for a new engineer

This is a log of **what we actually did** to start hosting Harmony Acres, not a rewrite of the product. The application already had Cognito-aware code; early steps **turned that code on in AWS** and **applied the matching database schema**. The public API is on **Render** (free web service) instead of Lightsail, because Lightsail’s trial ends after 90 days and then bills monthly.

Local development is unchanged: leave `AUTH_MODE` and `NEXT_PUBLIC_AUTH_MODE` unset so the API still uses `/auth/login` with bcrypt + our JWT.

---

## Mental model (why these three steps exist)

Today, customers live in **Neon Postgres** (`users` table) with a **bcrypt** `hashed_password`. Cognito **cannot import those hashes**. So we do not bulk-copy users into Cognito.

Instead:

1. Create a Cognito User Pool (identity store for production).
2. Attach a **User migration Lambda**. On a user’s **first** production login with their **existing email + password**, Cognito has no user yet, so it calls the Lambda. The Lambda checks Neon. If the password matches, Cognito **creates** the user and stores that password going forward.
3. Alter Neon so we can store Cognito’s stable user id (`sub`) on the same `users` row, and so password can be missing for people who only exist in Cognito.

Admin vs customer **role still lives in Neon** (`users.role`), not in Cognito groups.

```
Browser ── Amplify Hosting (Next.js)
              │  NEXT_PUBLIC_API_BASE
              ▼
           Render (FastAPI)  ──▶  Neon Postgres
              │  verifies Cognito ID tokens
              ▼
           Cognito User Pool ──▶ migration Lambda (first login only)
```

---

## Step 1 — Cognito User Pool

**What changed:** AWS resources only. **No git files were edited in this step.**

**Where:** AWS account `410244537857`, region **`us-east-1`**.

**What we created / configured:**

| Thing | Value |
|---|---|
| User pool name | `User pool - lj6boc` |
| User pool id | `us-east-1_x0rDyMmrO` |
| User pool ARN | `arn:aws:cognito-idp:us-east-1:410244537857:userpool/us-east-1_x0rDyMmrO` |
| Sign-in | Email (`UsernameAttributes: email`) |
| App client name | `Farm Products Agent` |
| App client id | `6h8oipq8d2446viev236par37b` |
| App client | Public (no secret) |

**Auth flows on the app client** (needed later for the migration trigger):

- `ALLOW_USER_PASSWORD_AUTH` — **required**. Migration only runs on username/password sign-in, not SRP.
- Also present: `ALLOW_USER_SRP_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`, `ALLOW_CUSTOM_AUTH`.

**Password policy** (Cognito default-style): min length 8, upper + lower + number + symbol.

**Files that *will* consume these IDs later (not set in prod yet):**

- Backend: `harmony-acres/app/core/config.py` — `cognito_region`, `cognito_user_pool_id`, `cognito_app_client_id`, `auth_mode`
- Frontend: `harmony-acres/frontend/src/lib/cognito.ts` — `NEXT_PUBLIC_COGNITO_*` and `NEXT_PUBLIC_AUTH_MODE`

Until Lightsail / Amplify env vars are set (steps 4–5), those stay at local defaults (`auth_mode = "legacy"`).

---

## Step 2 — User-migration Lambda

**What changed:** AWS resources. **Repo source for the Lambda was not rewritten**; we packaged and deployed code that already lived in the repo.

### Files involved (already in git)

| File | Role |
|---|---|
| `harmony-acres/cognito/migration_lambda/handler.py` | Lambda entrypoint (`handler.handler`) |
| `harmony-acres/cognito/migration_lambda/README.md` | Build / deploy instructions we followed |

We built the zip **on the laptop** targeting Linux x86_64 (Lambda’s architecture). `bcrypt` is a native wheel, so we used:

```bash
pip install \
  --platform manylinux2014_x86_64 --only-binary=:all: \
  --python-version 3.12 \
  --target build bcrypt pg8000
cp handler.py build/
( cd build && zip -r ../migration.zip . )
```

The zip was **not committed**. It lived in `/tmp/harmony-acres-migration-lambda/migration.zip`.

### AWS resources created

| Resource | Value |
|---|---|
| Function name | `harmony-acres-user-migration` |
| ARN | `arn:aws:lambda:us-east-1:410244537857:function:harmony-acres-user-migration` |
| Runtime | Python 3.12 |
| Handler | `handler.handler` |
| Timeout | 15 seconds |
| Architecture | x86_64 |
| Env | `DATABASE_URL` = same Neon URL as `harmony-acres/.env` (SQLAlchemy form with `+asyncpg`; the handler strips the driver suffix) |
| IAM role | `harmony-acres-user-migration-role` |
| Role ARN | `arn:aws:iam::410244537857:role/harmony-acres-user-migration-role` |
| Role policy | `AWSLambdaBasicExecutionRole` (CloudWatch logs only) |
| Resource policy | Statement `cognito-invoke`: principal `cognito-idp.amazonaws.com`, source ARN = this user pool |

**Trigger:** User pool → **User migration** → this function.

`LambdaConfig` on the pool after attach:

```json
{ "UserMigration": "arn:aws:lambda:us-east-1:410244537857:function:harmony-acres-user-migration" }
```

**Caveat for juniors:** Cognito `update-user-pool` replaces unspecified settings with defaults. After we attached the trigger, `AutoVerifiedAttributes` was empty. If we later need Cognito to auto-verify emails on self-sign-up, turn that back on in the console. Sign-in with email and `ALLOW_USER_PASSWORD_AUTH` were still in place.

### What the Lambda code does (this *is* the “code change,” already written)

Cognito calls `handler(event, context)` with `userName` (email) and `triggerSource`.

1. **`_lookup_user`** — parse `DATABASE_URL`, connect with **pg8000** + TLS (`ssl_context=True` for Neon), run:

   ```sql
   SELECT hashed_password, full_name, role FROM users WHERE email = %s
   ```

   `role` is read but **not** sent to Cognito. Role stays in Postgres.

2. **`UserMigration_Authentication`** — bcrypt-check `event["request"]["password"]` against `hashed_password`. Wrong password or missing hash → raise (Cognito shows login failure).

3. **`UserMigration_ForgotPassword`** — no password in the event; if the email exists in Neon, allow the reset flow.

4. **Success response** — Cognito creates the user immediately:

   - `email_verified: "true"`
   - `name` from Neon `full_name`
   - `finalUserStatus: CONFIRMED`
   - `messageAction: SUPPRESS` (no “welcome to Cognito” email)

Full handler (this is what is deployed):

```python
# harmony-acres/cognito/migration_lambda/handler.py

def handler(event, context):
    trigger = event.get("triggerSource")
    email = event["userName"]
    row = _lookup_user(email)

    if row is None:
        raise Exception("Bad credentials")

    hashed_password, full_name, _role = row

    if trigger == "UserMigration_Authentication":
        password = event["request"]["password"]
        if not _verify(password, hashed_password):
            raise Exception("Bad credentials")
    elif trigger != "UserMigration_ForgotPassword":
        raise Exception("Unsupported trigger")

    event["response"] = {
        "userAttributes": {
            "email": email,
            "email_verified": "true",
            "name": full_name or "",
        },
        "finalUserStatus": "CONFIRMED",
        "messageAction": "SUPPRESS",
    }
    return event
```

The Lambda does **not** write `cognito_sub`. That happens later in the **API** when it verifies an ID token (see “Related app code” below).

---

## Step 3 — Database migration (Neon, once)

**What changed:** Neon schema (and Alembic version table). **We did not edit Python files.** We ran:

```bash
cd harmony-acres
alembic upgrade head
```

Alembic reads `DATABASE_URL` from `.env` via `app.core.config.Settings` (`alembic/env.py`).

**Result:** Neon was **already at head**. `alembic upgrade head` was a no-op.

| Check | Value |
|---|---|
| `alembic_version` | `8c4d6e7f2a91` (head) |
| Cognito revision on that chain | `6f1a3d4b0c52` (already applied) |

### The migration that matters for Cognito

File: `harmony-acres/alembic/versions/6f1a3d4b0c52_cognito_user_link.py`  
Parent: `5e0f2c3a8b41`

Exact upgrade:

```python
def upgrade() -> None:
    op.alter_column("users", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("cognito_sub", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_cognito_sub", "users", ["cognito_sub"])
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"])
```

**Verified on Neon:**

- `cognito_sub` — `character varying`, nullable, unique + index
- `hashed_password` — still `character varying`, now **nullable**

Existing customers keep their bcrypt hashes. `cognito_sub` is `NULL` until they log in through Cognito and the API backfills it.

Head also includes later revisions (`7a2b5c6d1e43` unique subscription line, `8c4d6e7f2a91` product image URLs). Those are unrelated to Cognito; they were already on Neon.

### Matching ORM (already in the codebase)

File: `harmony-acres/app/models/customer.py`

```python
hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
cognito_sub: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
```

If the ORM said nullable/`cognito_sub` but Neon did not, production Cognito login would fail. Step 3 is that alignment.

---

## Related app code (not changed in steps 1–3, but you will hit it in steps 4–6)

When the API runs with `AUTH_MODE=cognito`, `harmony-acres/app/core/security.py` maps a Cognito **ID token** to a Neon row:

1. Look up `users.cognito_sub == token.sub`
2. Else look up by email and **backfill** `cognito_sub`
3. Else insert a new customer row (no local password)

```python
# app/core/security.py — _resolve_cognito_user

user = await db.scalar(select(User).where(User.cognito_sub == sub))
if user is not None:
    return user

if email is not None:
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.cognito_sub = sub  # first Cognito login after Lambda migration
        ...
```

That is why step 3 had to exist **before** production login: the column must be there for the backfill.

---

## Step 4 — API on Render (not Lightsail)

**Why not Lightsail:** the Lightsail free trial is 90 days, then the VM bills every month even when idle. For initial development we switched to a **Render free web service** (HTTPS included, sleeps when idle).

**What we did in AWS:** a Lightsail instance `harmony-acres-api` (`micro_3_0`, Ubuntu, `44.213.133.46`) was created while we were still following the old plan, then **deleted** so it would not bill. Nothing from that VM is in use.

**Repo file added (not yet on `main` until you commit/push):** `render.yaml` at the repo root.

That Blueprint tells Render:

| Setting | Value |
|---|---|
| Service name | `harmony-acres-api` |
| Runtime | Python (not Docker — simpler on the free plan) |
| Plan | `free` |
| Region | `ohio` |
| Root dir | `harmony-acres` |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health | `GET /health` |

Render injects `$PORT`. Do **not** hardcode 8000.

Non-secret env vars are in the YAML (`AUTH_MODE=cognito`, Cognito pool/client ids, `AWS_REGION`). Secrets use `sync: false` so they are **not** in git. You paste them once in the Render dashboard from local `harmony-acres/.env`:

| Env var | Where it comes from |
|---|---|
| `DATABASE_URL` | same Neon URL as local `.env` |
| `JWT_SECRET` | local `.env` |
| `CORS_ALLOW_ORIGINS` | `https://main.dlq25q6ua33.amplifyapp.com` (Amplify origin from step 5) |
| `AGENT_RUNTIME_ARN`, `AGENT_MEMORY_ID`, `BEDROCK_MODEL_ID` | local `.env` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | only if the chat agent must call Bedrock/AgentCore from Render |

**You still need to finish this in the Render UI** (no Render API key was on this machine):

1. Sign up / log in at [https://dashboard.render.com](https://dashboard.render.com).
2. **New → Blueprint** and connect GitHub repo `asundar-12/agents-for-farm-products` (push `render.yaml` first), **or** **New → Web Service**, connect the same repo, set root dir / build / start as in the table above.
3. Paste the secret env vars. Set `CORS_ALLOW_ORIGINS` to the Amplify origin.
4. Deploy. Expected URL: `https://harmony-acres-api.onrender.com` (if Render adds a suffix, copy the real URL).
5. Confirm `https://<render-host>/health` returns `{"status":"ok"}`. The first request after sleep can take 30–60s.

No FastAPI source changes for this step. `Dockerfile.api` is unused on Render (kept for a later AWS container deploy).

---

## Step 5 — Amplify frontend

**What changed:** AWS Amplify Hosting app. **No frontend source files were edited.** Env vars are inlined at **build** time (`NEXT_PUBLIC_*`).

| Thing | Value |
|---|---|
| App name | `harmony-acres` |
| App id | `dlq25q6ua33` |
| Repo | `https://github.com/asundar-12/agents-for-farm-products` |
| Platform | `WEB_COMPUTE` (Next.js SSR) |
| Branch | `main` (auto-build on) |
| URL | **https://main.dlq25q6ua33.amplifyapp.com** |

App environment variables:

| Var | Value |
|---|---|
| `AMPLIFY_MONOREPO_APP_ROOT` | `harmony-acres/frontend` |
| `NEXT_PUBLIC_API_BASE` | `https://harmony-acres-api.onrender.com` |
| `NEXT_PUBLIC_AUTH_MODE` | `cognito` |
| `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | `us-east-1_x0rDyMmrO` |
| `NEXT_PUBLIC_COGNITO_APP_CLIENT_ID` | `6h8oipq8d2446viev236par37b` |

Build spec is the existing repo-root `amplify.yml` (`appRoot: harmony-acres/frontend`, `npm ci`, `npm run build`).

**Job 1 failed:** Amplify looked for `package.json` at the repo root. Fix was `AMPLIFY_MONOREPO_APP_ROOT=harmony-acres/frontend`.

**Job 2 succeeded.** `GET https://main.dlq25q6ua33.amplifyapp.com/` returned **HTTP 200**.

If the Render URL is not exactly `harmony-acres-api.onrender.com`, update `NEXT_PUBLIC_API_BASE` in Amplify and **redeploy** (changing a `NEXT_PUBLIC_` var does nothing until a new build).

Build-time Cognito config lives in `harmony-acres/frontend/src/lib/cognito.ts` (`USER_PASSWORD_AUTH` so the migration Lambda can run). Unchanged this step.

---

## Step 6 — Smoke test

Automated checks (15 Aug 2026, after Render was healthy):

| Check | Result |
|---|---|
| `GET https://harmony-acres-api.onrender.com/health` | `{"status":"ok"}` HTTP 200 |
| `GET /products` | 5 catalog items (butter, eggs, honey, sourdough, milk) |
| `POST /auth/login` | HTTP 404 `"Password auth is disabled; sign in through Cognito"` — correct for `AUTH_MODE=cognito` |
| CORS from Amplify origin on `/products` | `access-control-allow-origin: https://main.dlq25q6ua33.amplifyapp.com` |
| Amplify `GET https://main.dlq25q6ua33.amplifyapp.com/` | HTTP 200 |
| Cognito users in pool `us-east-1_x0rDyMmrO` | **none yet** (no first login) |
| Neon `admintest@example.com` | `role=admin`, still has bcrypt hash, `cognito_sub` still null |

**Browser (you do this — needs the real password):**

1. Open https://main.dlq25q6ua33.amplifyapp.com
2. Log in as `admintest@example.com` (or another Neon email) with the **current** password.
3. First login: Cognito finds no user → migration Lambda → Neon bcrypt → Cognito creates CONFIRMED user.
4. You should land in the app as **admin** if that Neon row is `role=admin` (Cognito has no groups).
5. Browse products; place an order if you want; open admin pages.
6. Cognito console → Users: that email should appear. Neon `cognito_sub` should fill in after the API sees the ID token.

---

## Step 7 — Local stays unchanged

Leave `AUTH_MODE` / `NEXT_PUBLIC_AUTH_MODE` unset locally. Legacy `/auth/login` keeps working against a local API.

---

## Status snapshot

| Step | Status |
|---|---|
| 1 Cognito User Pool | Done |
| 2 Migration Lambda | Done |
| 3 Neon `alembic upgrade head` | Already at head |
| 4 API | Lightsail deleted. `render.yaml` written. **Create the Render service in the dashboard** (no API key here) |
| 5 Amplify | App live: https://main.dlq25q6ua33.amplifyapp.com |
| 6 Smoke test | API/CORS/catalog/Amplify OK; **first Cognito login still needs a browser sign-in** |
| 7 Local legacy auth | Unchanged |

---

## Quick “if something breaks” map

| Symptom | Likely place |
|---|---|
| First Cognito login always “user not found” | Lambda not attached, or `ALLOW_USER_PASSWORD_AUTH` missing, or frontend using SRP only |
| Lambda timeout / DB errors | `DATABASE_URL`, Neon TLS, or Lambda cannot reach Neon |
| Login works in Cognito but API 401 | Render missing `COGNITO_*` / `AUTH_MODE`, or sending an access token instead of an ID token |
| Browser CORS errors | `CORS_ALLOW_ORIGINS` on Render must be exactly `https://main.dlq25q6ua33.amplifyapp.com` (no trailing slash) |
| Frontend calls the wrong API | `NEXT_PUBLIC_API_BASE` is build-time; change it and redeploy Amplify |
| Amplify build: cannot read `next` version | `AMPLIFY_MONOREPO_APP_ROOT` must be `harmony-acres/frontend` |
| API 500 on user lookup | `cognito_sub` column missing (step 3) |
| Admin lost after login | Check Neon `users.role`, not Cognito groups |
| First Render request hangs ~1 min | Free plan cold start; wait and retry `/health` |
