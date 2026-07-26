"""Cognito User Migration Lambda trigger.

How the seamless migration works: we do NOT bulk-import the old users into
Cognito (their passwords are bcrypt hashes and Cognito can't accept pre-hashed
passwords). Instead we attach this Lambda to the pool's "User Migration"
trigger. The first time a legacy user signs in with their existing email +
password, Cognito — finding no such user — calls this function. We verify the
password against the old Postgres `users` table; on success we return the user's
attributes and Cognito creates + confirms the account, storing the password it
just received. From then on the user lives entirely in Cognito.

Two trigger sources fire this:
  - "UserMigration_Authentication": normal sign-in (password is present).
  - "UserMigration_ForgotPassword": the user started a reset; there's no
    password to check, we just confirm the account exists so the reset can send.

Packaging: this needs `bcrypt` and `pg8000` (a pure-Python Postgres driver, so
no native build step). See README.md for the build/zip command. Configuration
comes from env vars DATABASE_URL (the same Neon connection string the API uses).
"""

import os

import bcrypt
import pg8000.dbapi


def _lookup_user(email: str):
    """Return (hashed_password, full_name, role) for an active legacy user, or None."""
    # DATABASE_URL is the API's async URL (postgresql+asyncpg://...). pg8000 is a
    # sync driver and wants a plain DSN, so strip the SQLAlchemy driver suffix.
    dsn = os.environ["DATABASE_URL"].replace("+asyncpg", "").replace("postgresql://", "", 1)
    # dsn now looks like user:pass@host:port/dbname[?params]
    creds, _, rest = dsn.partition("@")
    user, _, password = creds.partition(":")
    hostport, _, dbpart = rest.partition("/")
    host, _, port = hostport.partition(":")
    dbname = dbpart.split("?")[0]

    conn = pg8000.dbapi.connect(
        user=user,
        password=password,
        host=host,
        port=int(port or 5432),
        database=dbname,
        ssl_context=True,  # Neon requires TLS
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT hashed_password, full_name, role FROM users WHERE email = %s",
            (email,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _verify(password: str, hashed_password: str) -> bool:
    if not hashed_password:  # Cognito-created users have no local hash
        return False
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def handler(event, context):
    trigger = event.get("triggerSource")
    email = event["userName"]
    row = _lookup_user(email)

    if row is None:
        # No such legacy user — let Cognito report "user not found".
        raise Exception("Bad credentials")

    hashed_password, full_name, _role = row

    if trigger == "UserMigration_Authentication":
        password = event["request"]["password"]
        if not _verify(password, hashed_password):
            raise Exception("Bad credentials")
    elif trigger != "UserMigration_ForgotPassword":
        # Unexpected trigger source; refuse rather than migrate blindly.
        raise Exception("Unsupported trigger")

    # Success: hand Cognito the attributes for the new account.
    event["response"] = {
        "userAttributes": {
            "email": email,
            "email_verified": "true",  # they proved control by signing in
            "name": full_name or "",
        },
        # CONFIRMED = ready to use immediately, no verification code round-trip.
        "finalUserStatus": "CONFIRMED",
        # Don't send Cognito's "welcome" email — this is an existing customer.
        "messageAction": "SUPPRESS",
    }
    return event
