"use client";

// Minimal auth state: hold the current user in React, back the token in
// localStorage (via api.ts). On mount we try /customers/me with whatever token
// is stored, so a refresh keeps you signed in. This is bearer-token auth, not
// httpOnly cookies — simple and matching the backend, at the cost of the token
// living in JS-readable storage.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, getToken, setToken, setTokenProvider } from "./api";
import {
  cognitoLogin,
  cognitoLogout,
  cognitoRegister,
  getIdToken,
  isCognito,
} from "./cognito";
import type { User } from "./types";

// In Cognito mode, api.ts should pull a fresh ID token per request rather than
// read the stale localStorage value. Installed at module load so it's in place
// before any request fires. Legacy mode leaves the provider unset.
if (isCognito) setTokenProvider(getIdToken);

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // In Cognito mode there's no localStorage token to gate on — Amplify holds
  // the session — so we always start in `loading` and let the mount effect
  // resolve it. In legacy mode we only load if there's a token worth validating.
  const [loading, setLoading] = useState<boolean>(() => (isCognito ? true : !!getToken()));

  useEffect(() => {
    // Both modes verify the session by calling /customers/me: legacy sends the
    // stored bearer token, Cognito sends a fresh ID token via the token
    // provider. Either way, a 200 means we're signed in.
    if (!isCognito && !getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => {
        if (!isCognito) setToken(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    if (isCognito) {
      await cognitoLogin(email, password);
    } else {
      const { access_token } = await api.login({ email, password });
      setToken(access_token);
    }
    const me = await api.me();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (email: string, password: string, full_name: string) => {
      if (isCognito) {
        await cognitoRegister(email, password, full_name);
      } else {
        await api.register({ email, password, full_name });
      }
      // Neither path returns a usable session directly; log in to establish one.
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    if (isCognito) {
      void cognitoLogout();
    } else {
      setToken(null);
    }
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
