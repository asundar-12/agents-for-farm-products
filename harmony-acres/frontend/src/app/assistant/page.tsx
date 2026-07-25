"use client";

// Customer assistant. Just the shared chat panel with customer-flavored intro
// copy, laid out to fill the screen above the bottom nav.

import { BottomNav } from "@/components/bottom-nav";
import { ChatPanel } from "@/components/chat-panel";
import { useRequireAuth } from "@/lib/use-require-auth";

export default function AssistantPage() {
  const { loading, user } = useRequireAuth();

  if (loading || !user) {
    return <main className="flex-1 grid place-items-center text-muted-foreground">Loading…</main>;
  }

  return (
    <>
      {/* Fixed viewport height with room reserved for the bottom nav, so the
          chat input sits just above it and the message list scrolls inside. */}
      <main className="flex h-[100dvh] flex-col pb-14">
        <ChatPanel
          title="Your farm assistant"
          intro="Ask about products, your order, or your subscriptions — I can help you add items too."
          suggestions={[
            "What's fresh this week?",
            "Add 2 gallons of milk to my order",
            "When's my next delivery?",
          ]}
        />
      </main>
      <BottomNav />
    </>
  );
}
