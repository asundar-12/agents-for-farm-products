"use client";

// Admin assistant. The same shared chat panel the customers use, but the
// backend routes to the admin agent based on the signed-in user's role — so the
// only thing that changes here is the intro copy and the suggested prompts,
// which are framed around running the week rather than shopping.

import { ChatPanel } from "@/components/chat-panel";

export default function AdminAssistantPage() {
  return (
    // The admin shell already guards the route and renders the sidebar, so this
    // page just fills the content column. A fixed viewport height keeps the
    // composer pinned to the bottom with the message list scrolling above it.
    <main className="flex h-[100dvh] flex-col">
      <ChatPanel
        title="Farm admin assistant"
        intro="Ask about this week's demand, who hasn't ordered, or draft a summary of the buy list."
        suggestions={[
          "Summarize this week's shopping list",
          "Which products spiked compared to last week?",
          "Who hasn't submitted an order yet?",
        ]}
      />
    </main>
  );
}
