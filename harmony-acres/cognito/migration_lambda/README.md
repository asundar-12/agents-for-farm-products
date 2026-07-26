# Cognito user-migration Lambda

Attaches to the User Pool's **User Migration** trigger so existing customers
keep their current password (see the docstring in `handler.py` for the flow).

## Build & deploy

`bcrypt` ships native code, so build the zip on a Linux/x86_64 target that
matches the Lambda runtime (or use Docker). From this directory:

```bash
mkdir -p build
pip install \
  --platform manylinux2014_x86_64 --only-binary=:all: \
  --target build bcrypt pg8000
cp handler.py build/
( cd build && zip -r ../migration.zip . )
```

Create the function (runtime python3.12, handler `handler.handler`) and set its
`DATABASE_URL` env var to the same Neon connection string the API uses:

```bash
aws lambda create-function \
  --function-name harmony-acres-user-migration \
  --runtime python3.12 --handler handler.handler \
  --zip-file fileb://migration.zip \
  --role <lambda-exec-role-arn> \
  --environment "Variables={DATABASE_URL=<neon-url>}" \
  --timeout 15
```

If Neon is not publicly reachable from Lambda, put the function in a VPC with
egress to the DB. Grant the pool permission to invoke it:

```bash
aws lambda add-permission \
  --function-name harmony-acres-user-migration \
  --statement-id cognito-invoke \
  --action lambda:InvokeFunction \
  --principal cognito-idp.amazonaws.com \
  --source-arn <user-pool-arn>
```

Then in the User Pool → **Extensions / Triggers → User migration**, select this
function. Also set the App Client's auth flow to allow
`ALLOW_USER_PASSWORD_AUTH` — the migration trigger only fires on the
username/password (USER_PASSWORD_AUTH) sign-in flow, not SRP.

## Retiring it

Once your dashboards show no new migrations happening (every active user has
signed in at least once), detach the trigger and delete the function. The
`hashed_password` column can then be dropped in a later migration.
