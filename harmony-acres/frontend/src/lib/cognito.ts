"use client";

// Cognito integration, isolated here so auth.tsx stays a thin state layer.
// Only used when NEXT_PUBLIC_AUTH_MODE === "cognito"; in legacy mode none of
// this runs and the old email/password-against-our-API flow is used instead.

import { Amplify } from "aws-amplify";
import {
  confirmSignUp,
  fetchAuthSession,
  resendSignUpCode,
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
): Promise<{ needsConfirmation: boolean }> {
  const { nextStep } = await signUp({
    username: email,
    password,
    options: { userAttributes: { email, name: fullName } },
  });
  // For a pool configured to auto-confirm (pre-signup Lambda), nextStep is
  // already DONE and the caller can log in immediately.
  return { needsConfirmation: nextStep.signUpStep === "CONFIRM_SIGN_UP" };
}

export async function cognitoConfirmSignUp(email: string, code: string): Promise<void> {
  await confirmSignUp({ username: email, confirmationCode: code });
}

export async function cognitoResendCode(email: string): Promise<void> {
  await resendSignUpCode({ username: email });
}

export async function cognitoLogout(): Promise<void> {
  await signOut();
}
