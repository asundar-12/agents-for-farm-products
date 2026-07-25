"use client";

// The root just routes: signed-in users go straight to the order screen (the
// heart of the app), everyone else to login. No content of its own.

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/order" : "/login");
  }, [user, loading, router]);

  return (
    <main className="flex-1 grid place-items-center text-muted-foreground">
      Loading…
    </main>
  );
}
