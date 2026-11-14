import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { sendChat } from "./api";
import Results from "./Results";
import type { ChatMessage } from "./types";

const EXAMPLES = [
  "Show me Mumbai in 2016, 2020, and 2025",
  "How has Dubai's built-up area changed between 2017 and 2024?",
  "Compare Las Vegas in 2018 and 2025",
];

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const res = await sendChat(next);
      setMessages([
        ...next,
        { role: "assistant", content: res.reply, results: res.results },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setMessages([...next, { role: "assistant", content: msg, isError: true }]);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void submit(input);
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Earth Intelligence</h1>
        <p>Historical satellite imagery and land-cover change, powered by Google Earth Engine</p>
      </header>

      <main className="thread">
        {messages.length === 0 && (
          <div className="empty">
            <p>Ask about any place and the years you want to compare.</p>
            <div className="chips">
              {EXAMPLES.map((ex) => (
                <button key={ex} onClick={() => void submit(ex)}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}${m.isError ? " error" : ""}`}>
            {m.results?.map((r, j) => <Results key={j} data={r} />)}
            {m.content && <p>{m.content}</p>}
          </div>
        ))}

        {loading && (
          <div className="msg assistant">
            <p className="loading">Retrieving satellite data… this can take up to a minute.</p>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <form className="composer" onSubmit={onSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Show me Mumbai in 2016, 2020, and 2025"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
