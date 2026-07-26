"use client";

// Cognito integration, isolated here so auth.tsx stays a thin state layer.
// Only used when NEXT_PUBLIC_AUTH_MODE === "cognito"; in legacy mode none of
// this runs and the old email/password-against-our-API flow is used instead.

import { Amplify } from "aws-amplify";
import {
  fetchAuthSession,
  signIn,
  signOut,
  signUp,
} from "aws-amplify/auth";

export const AUTH_MODE = process.env.NEXT_PUBLIC_AUTH_MODE ?? "legacy";
export const isCognito = AUTH_MODE === "cognito";

// Configure Amplify once, at import time, from build-time env vars. These are
// NEXT_PUBLIC_ so they're inlined into the client bundle (they're not secret —
// the pool/client ids appear in every token).
if (isCognito) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID!,
        userPoolClientId: process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID!,
      },
    },
  });
}

// The token provider api.ts calls per request. fetchAuthSession returns cached
// tokens and transparently refreshes them when they're near expiry, so this
// always hands back a currently-valid ID token (or null when signed out).
export async function getIdToken(): Promise<string | null> {
  try {
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString() ?? null;
  } catch {
    return null;
  }
}

export async function cognitoLogin(email: string, password: string): Promise<void> {
  // USER_PASSWORD_AUTH is the flow the migration Lambda hooks into; the pool's
  // app client must allow it (see cognito/migration_lambda/README.md).
  await signIn({
    username: email,
    password,
    options: { authFlowType: "USER_PASSWORD_AUTH" },
  });
}

export async function cognitoRegister(
  email: string,
  password: string,
  fullName: string,
): Promise<void> {
  await signUp({
    username: email,
    password,
    options: { userAttributes: { email, name: fullName } },
  });
  // NOTE: if the pool requires email verification, the user is now in an
  // UNCONFIRMED state and a confirmation-code step is needed before they can
  // sign in. Wiring that screen is a follow-up; for a pool configured to
  // auto-confirm (pre-signup Lambda) the subsequent login just works.
}

export async function cognitoLogout(): Promise<void> {
  await signOut();
}
