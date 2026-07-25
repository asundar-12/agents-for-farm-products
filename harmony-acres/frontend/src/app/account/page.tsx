"use client";

// Account screen: edit your display name, see your email (read-only — it's the
// login), and sign out. Admins also get a link into the farm dashboard.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { BottomNav } from "@/components/bottom-nav";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useRequireAuth } from "@/lib/use-require-auth";
import { cn } from "@/lib/utils";

export default function AccountPage() {
  const { loading: authLoading, user } = useRequireAuth();
  const { logout } = useAuth();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  // Seed the editable name once the user loads.
  useEffect(() => {
    if (user) setName(user.full_name);
  }, [user]);

  const save = useMutation({
    mutationFn: (full_name: string) => api.updateMe(full_name),
    onSuccess: () => {
      // The name lives on the auth user; refresh it so the greeting elsewhere
      // updates too.
      queryClient.invalidateQueries();
      toast.success("Saved.");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Couldn't save your name."),
  });

  if (authLoading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  const nameChanged = name.trim() !== "" && name.trim() !== user.full_name;

  return (
    <>
      <main className="flex-1 pb-24">
        <div className="mx-auto max-w-md space-y-8 px-4 py-6">
          <h1 className="text-2xl font-semibold tracking-tight">Account</h1>

          {/* Profile */}
          <section className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={user.email} disabled />
              <p className="text-xs text-muted-foreground">
                Your email is your login and can&apos;t be changed here.
              </p>
            </div>
            <Button
              onClick={() => save.mutate(name.trim())}
              disabled={!nameChanged || save.isPending}
            >
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
          </section>

          {/* Admin shortcut */}
          {user.role === "admin" && (
            <Link
              href="/admin"
              className={cn(buttonVariants({ variant: "outline" }), "w-full")}
            >
              <ShieldCheck className="size-4" /> Farm dashboard
            </Link>
          )}

          <Button variant="ghost" className="w-full text-muted-foreground" onClick={logout}>
            <LogOut className="size-4" /> Sign out
          </Button>
        </div>
      </main>
      <BottomNav />
    </>
  );
}
