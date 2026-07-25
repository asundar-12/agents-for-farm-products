"use client";

// Minimal auth state: hold the current user in React, back the token in
// localStorage (via api.ts). On mount we try /customers/me with whatever token
// is stored, so a refresh keeps you signed in. This is bearer-token auth, not
// httpOnly cookies — simple and matching the backend, at the cost of the token
// living in JS-readable storage.

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, getToken, setToken } from "./api";
import type { User } from "./types";

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
  // Start loading only if there's a token worth validating; otherwise we're
  // immediately "known to be logged out" and guards can act without a flash.
  const [loading, setLoading] = useState<boolean>(() => !!getToken());

  useEffect(() => {
    // No token → initial `loading` is already false (see useState above), so
    // there's nothing to do and nothing to set synchronously here.
    if (!getToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await api.login({ email, password });
    setToken(access_token);
    const me = await api.me();
    setUser(me);
    return me;
  }, []);

  const register = useCallback(
    async (email: string, password: string, full_name: string) => {
      await api.register({ email, password, full_name });
      // Registration doesn't return a token; log in to get one.
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    setToken(null);
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
