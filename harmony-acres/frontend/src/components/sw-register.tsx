"use client";

// Registers the service worker once, on the client, in production only. We skip
// it in development because caching pages fights with hot-reload and would serve
// stale bundles while you're editing.

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration failing just means no offline support — not fatal.
    });
  }, []);

  return null;
}
