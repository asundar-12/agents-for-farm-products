"use client";

// Client-side route guard. Pages that need a signed-in user call this; while
// auth is resolving it returns `loading`, and once resolved-as-logged-out it
// redirects to /login. Server-side enforcement still lives in the API (every
// endpoint checks the token) — this is only about not showing a logged-out
// user a screen that will 401.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "./auth";

export function useRequireAuth() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  return { user, loading };
}
