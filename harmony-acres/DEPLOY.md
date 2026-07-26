# Deploying Harmony Acres (Amplify + App Runner + Cognito)

Three moving parts. The AI agent runtime on Bedrock AgentCore is unchanged.

```
Browser ── Amplify Hosting (Next.js frontend)
              │  NEXT_PUBLIC_API_BASE
              ▼
           App Runner (FastAPI backend)  ──▶  Neon Postgres
              │  verifies ID tokens                ▲
              ▼                                     │ migration Lambda
           Cognito User Pool ──────────────────────┘  (first-login import)
```

## 1. Cognito User Pool (do this first — the others reference its ids)

- Create a **User Pool**. Sign-in with email. Add an **App Client** (public, no
  secret) and enable the **ALLOW_USER_PASSWORD_AUTH** flow.
- Attach the **user-migration Lambda** — see
  [cognito/migration_lambda/README.md](cognito/migration_lambda/README.md). This
  is what lets existing customers keep their password.
- Note three values: region, User Pool id, App Client id.

## 2. Backend on App Runner

- Build & push the image with [deploy-api.sh](deploy-api.sh) (creates/uses an
  ECR repo; see the header comment for one-time setup).
- App Runner service settings: **port 8000**, health check path **/health**.
- Environment variables:

  | var | value |
  |-----|-------|
  | `DATABASE_URL` | Neon connection string (same as today) |
  | `AUTH_MODE` | `cognito` |
  | `COGNITO_REGION` | e.g. `us-east-1` |
  | `COGNITO_USER_POOL_ID` | from step 1 |
  | `COGNITO_APP_CLIENT_ID` | from step 1 |
  | `CORS_ALLOW_ORIGINS` | your Amplify domain, comma-separated |
  | `AGENT_RUNTIME_ARN`, `AGENT_MEMORY_ID`, `BEDROCK_MODEL_ID`, `AWS_REGION` | as in `.env` |

- Run the DB migration once against Neon: `alembic upgrade head` (adds the
  `cognito_sub` column and makes `hashed_password` nullable).

## 3. Frontend on AWS Amplify Hosting

- Connect the GitHub repo; Amplify uses [amplify.yml](../amplify.yml)
  (`appRoot: harmony-acres/frontend`).
- Environment variables (all `NEXT_PUBLIC_`, inlined at build time):

  | var | value |
  |-----|-------|
  | `NEXT_PUBLIC_API_BASE` | the App Runner URL |
  | `NEXT_PUBLIC_AUTH_MODE` | `cognito` |
  | `NEXT_PUBLIC_COGNITO_USER_POOL_ID` | from step 1 |
  | `NEXT_PUBLIC_COGNITO_APP_CLIENT_ID` | from step 1 |

## Local development is unaffected

Leave `AUTH_MODE` / `NEXT_PUBLIC_AUTH_MODE` unset (they default to `legacy`).
The old `/auth/register` + `/auth/login` email-password flow keeps working
against the local API with no Cognito pool required.

## Roles

`role` (customer/admin) stays authoritative in the Postgres `users` table, not
in Cognito — promoting someone to admin is still a DB change, exactly as today.

## Known follow-up

Cognito self-service **sign-up** may require an email confirmation-code screen
if the pool isn't set to auto-confirm; that UI isn't built yet (see the note in
`frontend/src/lib/cognito.ts`). Existing-user login needs nothing extra.
