"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { API_URL, api } from "@/lib/api";
import type { RatingFeedback } from "@/lib/cut";
import { Glyph } from "./cut/ui";
import "./local-chat.css";

type ChatRecord = {
  id: string;
  created_at: string;
  data: {
    role: "user" | "assistant";
    content: string;
    model?: string;
    suggested_preference?: string | null;
    saved_preference?: string;
    rating_feedback?: RatingFeedback | null;
  };
};
type ChatReply = { user: ChatRecord; assistant: ChatRecord | null; error: string | null };

function Preference({ entry, onSaved }: { entry: ChatRecord; onSaved: (record: ChatRecord) => void }) {
  const [content, setContent] = useState(entry.data.suggested_preference || "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function remember(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      onSaved(await api<ChatRecord>(`/local-chat/${entry.id}/remember`, {
        method: "POST", body: JSON.stringify({ content: content.trim() }),
      }));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save the preference.");
    } finally {
      setPending(false);
    }
  }

  if (entry.data.saved_preference) return <p className="local-chat-saved">
    <strong>Saved to your taste profile</strong><br/>{entry.data.saved_preference}
  </p>;
  if (!entry.data.suggested_preference) return null;
  return <form className="local-chat-preference" onSubmit={remember}>
    <label htmlFor={`preference-${entry.id}`}>Suggested preference</label>
    <textarea id={`preference-${entry.id}`} value={content} maxLength={500}
      onChange={event => setContent(event.target.value)} rows={2} required/>
    <button type="submit" disabled={pending || !content.trim()}>{pending ? "Saving…" : "Remember this"}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}

export function LocalChat() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [records, setRecords] = useState<ChatRecord[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const log = useRef<HTMLDivElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLTextAreaElement>(null);
  const title = /^\/title\/(media|catalogue|movie|tv|anime|tvmaze)\/(\d+)$/.exec(path || "");

  useEffect(() => {
    if (!open) return;
    field.current?.focus();
    const controller = new AbortController();
    setLoading(true);
    api<ChatRecord[]>("/local-chat", { signal: controller.signal })
      .then(entries => { if (!controller.signal.aborted) setRecords(entries); })
      .catch(() => { if (!controller.signal.aborted) setError("Chat history could not be loaded."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [open]);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [records, open, sending]);

  function close() {
    setOpen(false);
    launcher.current?.focus();
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending || loading) return;
    setSending(true);
    setError("");
    try {
      const response = await api<ChatReply>("/local-chat", {
        method: "POST", body: JSON.stringify({
          message: text, ...(title && { title_source: title[1], title_id: Number(title[2]) }),
        }),
      });
      const latest = [response.user, ...(response.assistant ? [response.assistant] : [])];
      setRecords(current => [...current.filter(row => !latest.some(entry => entry.id === row.id)), ...latest]);
      if (title && response.user.data.rating_feedback) {
        window.dispatchEvent(new CustomEvent("manu-taste-updated", {
          detail: { source: title[1], id: title[2], rating: response.user.data.rating_feedback },
        }));
      }
      setMessage("");
      if (response.error) setError(response.error);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not send the message.");
    } finally {
      setSending(false);
      field.current?.focus();
    }
  }

  return <div className="local-chat-widget">
    <button ref={launcher} className="local-chat-launcher" type="button" aria-expanded={open}
      aria-controls="local-chat-window" onClick={() => open ? close() : setOpen(true)}>✦ <span>Local chat</span></button>
    {open && <section id="local-chat-window" className="local-chat-window" role="dialog" aria-label="Local taste chat"
      onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); close(); } }}>
      <header className="local-chat-header">
        <div><h2>Talk to Manu</h2><p>Ollama · saved on this device</p></div>
        <button type="button" aria-label="Close local chat" onClick={close}><Glyph name="close" size={18}/></button>
      </header>
      <div className="local-chat-links">
        <Link href="/profile" onClick={close}>Taste profile</Link>
        <a href={`${API_URL}/data/export/json`}>Download all AI data (JSON)</a>
      </div>
      <div ref={log} className="local-chat-log" role="log" aria-label="Recent chat history" aria-live="polite">
        {loading && <p>Loading your conversations…</p>}
        {!loading && !records.length && <p>Tell Manu what you liked, what didn’t work, or why a recommendation missed the mark. You can review suggested preferences before saving them.</p>}
        {records.map(entry => <div className={`local-chat-message is-${entry.data.role}`} key={entry.id}>
          <div className="local-chat-author"><strong>{entry.data.role === "user" ? "You" : entry.data.model || "Manu"}</strong>
            <time dateTime={entry.created_at}>{new Date(entry.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</time></div>
          <p>{entry.data.content}</p>
          {entry.data.rating_feedback && <p className="local-chat-saved">
            <strong>Rating feedback saved</strong><br/>
            {entry.data.rating_feedback.title} · {entry.data.rating_feedback.score.toFixed(1)}/10
          </p>}
          <Preference entry={entry} onSaved={changed => {
            setRecords(current => current.map(row => row.id === changed.id ? changed : row));
            window.dispatchEvent(new CustomEvent("manu-taste-updated"));
          }}/>
        </div>)}
        {sending && <p role="status">Ollama is thinking…</p>}
        {error && <p className="local-chat-error" role="alert">{error}</p>}
      </div>
      <form className="local-chat-compose" onSubmit={send}>
        <textarea ref={field} aria-label="Message to Ollama" maxLength={4000} rows={2} value={message}
          readOnly={sending} placeholder={title ? "Discuss this title or your taste…" : "Tell Manu what you like…"}
          onChange={event => setMessage(event.target.value)}/>
        <button type="submit" disabled={!message.trim() || sending || loading}>Send</button>
      </form>
    </section>}
  </div>;
}
