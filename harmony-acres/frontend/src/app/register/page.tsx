"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const schema = z.object({
  full_name: z.string().min(1, "Your name is required"),
  email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Use at least 8 characters"),
});

type FormValues = z.infer<typeof schema>;

const codeSchema = z.object({
  code: z.string().min(1, "Enter the code from your email"),
});

type CodeValues = z.infer<typeof codeSchema>;

export default function RegisterPage() {
  const { user, login, register: registerUser, confirmRegistration, resendConfirmationCode } =
    useAuth();
  const router = useRouter();
  // Set only when Cognito requires a confirmation code before the account is
  // usable. Held in memory (never the URL or storage) so we can log in with
  // it once the code checks out — see cognito.ts.
  const [pending, setPending] = useState<{ email: string; password: string } | null>(null);

  useEffect(() => {
    if (user) router.replace("/order");
  }, [user, router]);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const {
    register: registerCode,
    handleSubmit: handleCodeSubmit,
    formState: { errors: codeErrors, isSubmitting: isConfirming },
  } = useForm<CodeValues>({ resolver: zodResolver(codeSchema) });

  async function onSubmit(values: FormValues) {
    try {
      const { needsConfirmation } = await registerUser(
        values.email,
        values.password,
        values.full_name,
      );
      if (needsConfirmation) {
        setPending({ email: values.email, password: values.password });
      } else {
        router.replace("/order");
      }
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Couldn't create your account. Try again.",
      );
    }
  }

  async function onConfirm(values: CodeValues) {
    if (!pending) return;
    try {
      await confirmRegistration(pending.email, values.code);
      await login(pending.email, pending.password);
      router.replace("/order");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "That code didn't work. Try again.");
    }
  }

  async function onResend() {
    if (!pending) return;
    try {
      await resendConfirmationCode(pending.email);
      toast.success("Sent a new code.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't resend the code.");
    }
  }

  if (pending) {
    return (
      <main className="flex-1 grid place-items-center px-4 py-10">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1 text-center">
            <h1 className="text-2xl font-semibold tracking-tight">Check your email</h1>
            <p className="text-sm text-muted-foreground">
              Enter the code we sent to {pending.email}.
            </p>
          </div>

          <form onSubmit={handleCodeSubmit(onConfirm)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="code">Confirmation code</Label>
              <Input
                id="code"
                autoComplete="one-time-code"
                inputMode="numeric"
                {...registerCode("code")}
              />
              {codeErrors.code && (
                <p className="text-sm text-destructive">{codeErrors.code.message}</p>
              )}
            </div>

            <Button type="submit" className="w-full" disabled={isConfirming}>
              {isConfirming ? "Confirming…" : "Confirm and sign in"}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground">
            Didn&apos;t get a code?{" "}
            <button
              type="button"
              onClick={onResend}
              className="font-medium text-primary hover:underline"
            >
              Resend
            </button>
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 grid place-items-center px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-1 text-center">
          <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
          <p className="text-sm text-muted-foreground">
            Start ordering from Farm Product Agent.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="space-y-2">
            <Label htmlFor="full_name">Full name</Label>
            <Input id="full_name" autoComplete="name" {...register("full_name")} />
            {errors.full_name && (
              <p className="text-sm text-destructive">{errors.full_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              inputMode="email"
              {...register("email")}
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-sm text-destructive">{errors.password.message}</p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
