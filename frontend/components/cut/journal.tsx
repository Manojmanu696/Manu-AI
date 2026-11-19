"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { api } from "@/lib/api";
import { formatDate, messageFrom, splitLabels, type Checkpoint, type Review } from "@/lib/cut";
import { Glyph, TagList } from "./ui";

function Editor({ title, busy, close, children }: { title: string; busy: boolean; close: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => { if (element?.open) element.close(); };
  }, []);
  return <dialog className="cut-dialog" ref={dialog} aria-labelledby="cut-editor-title" onCancel={event => { event.preventDefault(); if (!busy) close(); }}>
    <div className="cut-dialog-heading"><h2 id="cut-editor-title">{title}</h2><button type="button" className="cut-icon-button" aria-label="Close editor" onClick={close} disabled={busy}><Glyph name="close"/></button></div>
    {children}
  </dialog>;
}

function localDate() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function numberField(values: FormData, key: string) {
  const value = values.get(key);
  return value ? Number(value) : null;
}

export function CheckpointEditor({ movie, runtime, previous, close, submit }: {
  movie: boolean; runtime?: string; previous?: Checkpoint; close: () => void; submit: (values: Omit<Checkpoint, "id">) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const runtimeMinutes = runtime?.match(/^(\d+)\s*min(?:utes)?$/i)?.[1];
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await submit({
        viewing_date: String(values.get("viewing_date")), minute: numberField(values, "minute"),
        season: numberField(values, "season"), episode: numberField(values, "episode"),
        headline: String(values.get("headline")).trim(), notes: String(values.get("notes")).trim(),
        feeling: String(values.get("feeling")).trim(), pacing: String(values.get("pacing")),
        rating: numberField(values, "rating"), rewatch: String(values.get("rewatch")),
        tags: String(values.get("tags")).trim(), spoiler: values.has("spoiler"),
      });
      close();
    } catch (failure) {
      setError(messageFrom(failure));
    } finally {
      setBusy(false);
    }
  }
  return <Editor title="Log progress" close={close} busy={busy}>
    <form className="cut-form" onSubmit={save}>
      <div className="cut-form-row">
        {movie ? <label>Minute<input name="minute" type="number" min="0" max={runtimeMinutes || 10000} defaultValue={previous?.minute ?? undefined} required autoFocus/></label> : <>
          <label>Season<input name="season" type="number" min="0" max="1000" defaultValue={previous?.season ?? 1} required autoFocus/></label>
          <label>Episode<input name="episode" type="number" min="1" max="10000" defaultValue={previous?.episode != null ? Math.min(previous.episode + 1, 10000) : 1} required/></label>
        </>}
        <label>Viewing date<input name="viewing_date" type="date" defaultValue={localDate()} required/></label>
      </div>
      <label>Headline<input name="headline" maxLength={160} placeholder="What stands out so far?"/></label>
      <label>Notes<textarea name="notes" maxLength={10000} rows={3}/></label>
      <details className="cut-more-fields"><summary>Feeling, pacing, rating and tags</summary>
        <div className="cut-form-row">
          <label>How did you feel?<input name="feeling" maxLength={100} placeholder="Tense, moved, curious…"/></label>
          <label>Pacing<select name="pacing" aria-label="Pacing"><option value="">Select pacing</option><option>Slow</option><option>Steady</option><option>Fast</option><option>Uneven</option></select></label>
        </div>
        <div className="cut-form-row">
          <label>Rating out of 10<input name="rating" type="number" min="0" max="10" step="0.1"/></label>
          <label>Would you rewatch?<select name="rewatch" aria-label="Would you rewatch?"><option value="">Undecided</option><option value="yes">Yes</option><option value="maybe">Maybe</option><option value="no">No</option></select></label>
        </div>
        <label>Tags<input name="tags" maxLength={600} placeholder="Separate tags with commas"/></label>
      </details>
      <label className="cut-checkbox"><input name="spoiler" type="checkbox"/> Contains spoilers</label>
      {error && <p role="alert" className="cut-error-text">{error}</p>}
      <div className="cut-dialog-actions"><button className="cut-btn cut-primary" disabled={busy}>{busy ? "Saving…" : "Save checkpoint"}</button></div>
    </form>
  </Editor>;
}

export function ReviewEditor({ review, rating, close, submit }: {
  review: Review | null; rating?: number | null; close: () => void; submit: (values: Omit<Review, "finalized_at" | "updated_at">) => Promise<void>;
}) {
  const [body, setBody] = useState(review?.body || "");
  const [draft, setDraft] = useState<string>();
  const [available, setAvailable] = useState<boolean>();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    api<{ available: boolean }>("/cinema/review-editor", { signal: controller.signal })
      .then(result => setAvailable(result.available))
      .catch(() => { if (!controller.signal.aborted) setAvailable(false); });
    return () => controller.abort();
  }, []);

  async function generate() {
    setEditing(true);
    setError("");
    try {
      const result = await api<{ draft: string }>("/cinema/review-editor", { method: "POST", body: JSON.stringify({ text: body }) });
      setDraft(result.draft);
    } catch (failure) {
      setError(messageFrom(failure));
    } finally {
      setEditing(false);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    setSaving(true);
    setError("");
    try {
      await submit({
        rating: Number(values.get("rating")), verdict: String(values.get("verdict")).trim(),
        body: body.trim(), tags: String(values.get("tags")).trim(),
        spoiler_notes: String(values.get("spoiler_notes")).trim(), spoiler: values.has("spoiler"),
      });
      close();
    } catch (failure) {
      setError(messageFrom(failure));
    } finally {
      setSaving(false);
    }
  }

  return <Editor title={review ? "Edit final review" : "Write final review"} close={close} busy={saving || editing}>
    <form className="cut-form" onSubmit={save}>
      <label>Rating out of 10<input name="rating" type="number" min="1" max="10" step="0.1" defaultValue={review?.rating ?? rating ?? undefined} required autoFocus/></label>
      <label>Short verdict<input name="verdict" maxLength={240} defaultValue={review?.verdict} required/></label>
      <label>Full review<textarea name="review_body" value={body} onChange={event => setBody(event.target.value)} rows={5} maxLength={20000} required/></label>
      {available && <button type="button" className="cut-btn cut-secondary cut-ai-button" disabled={editing || saving || !body.trim()} onClick={generate}>{editing ? "Preparing draft…" : "Copyedit with local AI"}</button>}
      {available === false && <p className="cut-muted">AI copyediting requires a local Ollama model.</p>}
      {draft !== undefined && <div className="cut-draft">
        <label>Suggested draft<textarea rows={5} maxLength={20000} value={draft} onChange={event => setDraft(event.target.value)}/></label>
        <div className="cut-actions"><button type="button" className="cut-btn cut-secondary" onClick={() => { setBody(draft); setDraft(undefined); }} disabled={!draft.trim()}>Use draft</button><button type="button" className="cut-btn cut-secondary" onClick={() => setDraft(undefined)}>Discard draft</button></div>
      </div>}
      <label>Tags<input name="tags" maxLength={600} placeholder="Separate tags with commas" defaultValue={review?.tags}/></label>
      <label>Spoiler notes<textarea name="spoiler_notes" rows={2} maxLength={20000} defaultValue={review?.spoiler_notes}/></label>
      <label className="cut-checkbox"><input name="spoiler" type="checkbox" defaultChecked={review?.spoiler}/> Verdict or full review also contains spoilers</label>
      {error && <p role="alert" className="cut-error-text">{error}</p>}
      <div className="cut-dialog-actions"><button className="cut-btn cut-primary" disabled={saving || editing || draft !== undefined}>{saving ? "Saving…" : review ? "Save changes" : "Finalize review"}</button></div>
    </form>
  </Editor>;
}

function Spoiler({ label, children }: { label: string; children: ReactNode }) {
  return <details className="cut-spoiler"><summary>{label}</summary><div>{children}</div></details>;
}

export function Timeline({ checkpoints, open }: { checkpoints: Checkpoint[]; open: () => void }) {
  return <section className="cut-detail-section" id="timeline">
    <div className="cut-detail-section-head"><h2>Viewing timeline</h2><button className="cut-btn cut-secondary" onClick={open}><Glyph name="plus"/> Log progress</button></div>
    {checkpoints.length ? <ol className="cut-timeline">{checkpoints.map(point => {
      const content = <>
        {point.headline && <h3>{point.headline}</h3>}
        {point.notes && <p className="cut-prose">{point.notes}</p>}
        {(point.feeling || point.pacing || point.rating != null || point.rewatch) && <div className="cut-point-meta">
          {point.feeling && <span>{point.feeling}</span>}{point.pacing && <span>{point.pacing} pacing</span>}
          {point.rating != null && <span>{point.rating}/10</span>}{point.rewatch && <span>Rewatch {point.rewatch}</span>}
        </div>}
        <TagList tags={splitLabels(point.tags)}/>
      </>;
      return <li key={point.id}><article>
        <div className="cut-timeline-meta"><strong>{point.minute != null ? `${point.minute} min` : `Season ${point.season} · Episode ${point.episode}`}</strong><time dateTime={point.viewing_date}>{formatDate(point.viewing_date)}</time></div>
        {point.spoiler ? <Spoiler label="Reveal checkpoint spoiler">{content}</Spoiler> : content}
      </article></li>;
    })}</ol> : <p className="cut-muted">No checkpoints yet. Log a moment while you watch.</p>}
  </section>;
}

export function FinalReview({ review, count, open }: { review: Review | null; count: number; open: () => void }) {
  const content = review && <><h3>{review.verdict}</h3><p className="cut-prose">{review.body}</p><TagList tags={splitLabels(review.tags)}/></>;
  return <section className="cut-detail-section" id="review">
    <div className="cut-detail-section-head"><h2>Final review</h2><button className="cut-btn cut-secondary" onClick={open}><Glyph name="pen"/> {review ? "Edit review" : "Write review"}</button></div>
    {review ? <article className="cut-review">
      <div className="cut-review-meta"><span className="cut-rating personal"><Glyph name="star" size={16}/> Your rating <strong>{review.rating}/10</strong></span><span>Finalized <time dateTime={review.finalized_at + "Z"}>{formatDate(review.finalized_at)}</time></span></div>
      {review.spoiler ? <Spoiler label="Reveal review spoiler">{content}</Spoiler> : content}
      {review.spoiler_notes && <Spoiler label="Reveal spoiler notes"><p className="cut-prose">{review.spoiler_notes}</p></Spoiler>}
      <a className="cut-text-link" href="#timeline">{count} viewing {count === 1 ? "checkpoint" : "checkpoints"} <Glyph name="arrow" size={16}/></a>
    </article> : <p className="cut-muted">Your review will appear here alongside your viewing timeline.</p>}
  </section>;
}
