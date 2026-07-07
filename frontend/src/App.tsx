import { useState } from "react";
import { AskPage } from "@/pages/AskPage";
import { SourcesPage } from "@/pages/SourcesPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { useHistory } from "@/lib/useHistory";

type Tab = "ask" | "sources" | "history";

const TABS: { id: Tab; label: string }[] = [
  { id: "ask", label: "Ask" },
  { id: "sources", label: "Sources" },
  { id: "history", label: "History" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");
  const history = useHistory();
  // Bump to force a fresh AskPage when replaying a history question.
  const [askKey, setAskKey] = useState(0);
  const [pending, setPending] = useState<string | null>(null);

  const replay = (question: string) => {
    setPending(question);
    setAskKey((k) => k + 1);
    setTab("ask");
  };

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 flex items-baseline gap-4 border-b border-border bg-bg/85 px-6 py-5 backdrop-blur">
        <button
          onClick={() => setTab("ask")}
          className="font-sans text-[19px] font-semibold tracking-[-0.01em]"
        >
          Maryland Housing <span className="text-accent">Policy</span>
        </button>
        <nav className="ml-auto flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-md px-3 py-1.5 font-sans text-[13px] tracking-[0.02em] ${
                tab === t.id
                  ? "bg-surface-2 text-text"
                  : "text-text-dim hover:text-text"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-reading px-6 pb-32 pt-14">
        {tab === "ask" && (
          <AskPage
            key={askKey}
            initialQuestion={pending}
            onAsked={(q) => {
              history.add(q);
              setPending(null);
            }}
          />
        )}
        {tab === "sources" && <SourcesPage />}
        {tab === "history" && (
          <HistoryPage
            items={history.items}
            onPick={replay}
            onClear={history.clear}
          />
        )}
      </main>
    </div>
  );
}
