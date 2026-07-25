"use client";

// Client-side providers mounted once at the root: TanStack Query for server
// state (catalog, draft, cycle) and the auth context. Kept in its own file so
// the root layout can stay a server component.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { AuthProvider } from "@/lib/auth";
import { ServiceWorkerRegister } from "@/components/sw-register";
import { Toaster } from "@/components/ui/sonner";

export function Providers({ children }: { children: React.ReactNode }) {
  // One client per browser session. useState so it isn't recreated on every
  // render, which would throw away the cache.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // The catalog and cycle rarely change mid-session; don't refetch on
            // every window focus. Individual queries can override.
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      <ServiceWorkerRegister />
      <Toaster position="top-center" richColors />
    </QueryClientProvider>
  );
}
