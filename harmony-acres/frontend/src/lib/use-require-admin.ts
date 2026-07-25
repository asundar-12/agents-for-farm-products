"use client";

// Route guard for the admin pages. Like useRequireAuth, but also sends a
// signed-in *customer* back to their own app — admin screens are farm-staff
// only. The backend still enforces this on every /admin endpoint; this guard
// just avoids rendering a page that would only 403.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "./auth";

export function useRequireAdmin() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
    else if (user.role !== "admin") router.replace("/order");
  }, [loading, user, router]);

  const isAdmin = !!user && user.role === "admin";
  return { user, loading, isAdmin };
}
