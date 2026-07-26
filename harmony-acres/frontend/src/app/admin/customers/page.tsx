"use client";

// Admin customers: a simple roster of everyone with a customer account. The
// backend only exposes name, email, and when they joined — there's no per-
// customer detail screen yet, so this is a searchable read-only list.

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

export default function AdminCustomersPage() {
  const customers = useQuery({ queryKey: ["admin", "customers"], queryFn: api.adminCustomers });
  const [query, setQuery] = useState("");

  // Filter on name or email, case-insensitively. The list is small enough that
  // doing this client-side is fine and keeps the search instant.
  const filtered = useMemo(() => {
    const all = customers.data ?? [];
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (c) => c.full_name.toLowerCase().includes(q) || c.email.toLowerCase().includes(q),
    );
  }, [customers.data, query]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 md:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Customers</h1>
          {customers.data && (
            <p className="text-sm text-muted-foreground">
              {customers.data.length} {customers.data.length === 1 ? "account" : "accounts"}
            </p>
          )}
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name or email"
            className="w-56 pl-9"
            aria-label="Search customers"
          />
        </div>
      </header>

      <div className="mt-6">
        {customers.isLoading ? (
          <Skeleton className="h-64 w-full rounded-xl" />
        ) : filtered.length === 0 ? (
          <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
            {query ? "No customers match that search." : "No customers yet."}
          </p>
        ) : (
          <ul className="divide-y overflow-hidden rounded-xl border bg-card">
            {filtered.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate font-medium">{c.full_name}</p>
                  <p className="truncate text-sm text-muted-foreground">{c.email}</p>
                </div>
                <span className="shrink-0 text-sm text-muted-foreground">
                  Joined {formatDate(c.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
