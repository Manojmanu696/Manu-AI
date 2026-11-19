"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cutPath, mediaTypes, messageFrom, safeUrl, splitLabels, statuses, titleApi, titleTime, type Checkpoint, type CutTitle, type Review, type Status, type TitleData } from "@/lib/cut";
import { Artwork, CutFrame, Glyph, Shelf, StatePanel } from "./ui";
import { CheckpointEditor, FinalReview, ReviewEditor, Timeline } from "./journal";

const sections = [["credits", "Cast & crew"], ["release", "Release & language"], ["watch", "Where to watch"], ["timeline", "Timeline"], ["review", "Final review"], ["related", "Related titles"]];
const regionNames = new Intl.DisplayNames(["en"], { type: "region" });

function TitleIntro({ title, status, busy, reviewed, setStatus, open }: {
  title: CutTitle; status: Status; busy: boolean; reviewed: boolean; setStatus: (status: Status) => void; open: (editor: "progress" | "review") => void;
}) {
  const trailer = safeUrl(title.trailer_url);
  const ratings = [
    { value: title.imdb_rating, label: "IMDb" },
    { value: title.public_rating, label: title.rating_source || "Catalogue" },
    { value: title.personal_rating, label: "Your rating" },
  ];
  const saved = !!title.media_id && status !== "recommended";
  return <section className="cut-detail-hero">
    <Artwork title={title} backdrop eager/>
    <div className="cut-container cut-detail-hero-inner">
      <Link href="/browse/discover" className="cut-back"><Glyph name="back" size={17}/> Discover</Link>
      <div className="cut-title-layout">
        {title.image_url && <div className="cut-detail-poster"><Artwork title={title}/></div>}
        <div className="cut-title-copy">
          <div className="cut-kicker"><span/>{mediaTypes[title.media_type]}{title.is_demo && <span className="cut-sample">Sample</span>}</div>
          <h1>{title.title}</h1>
          <div className="cut-hero-meta">
            {[title.release_year, titleTime(title), ...splitLabels(title.genres)].filter(Boolean).map((part, index) => <span key={index}>{part}</span>)}
          </div>
          <p className="cut-hero-description">{title.description || "A synopsis hasn’t been added for this title."}</p>
          {ratings.some(rating => rating.value != null) && <div className="cut-ratings">{ratings.map(rating => rating.value != null && <span key={rating.label} className={`cut-rating ${rating.label === "Your rating" ? "personal" : ""}`}><Glyph name="star" size={15}/>{rating.label} <strong>{rating.value}/10</strong></span>)}</div>}
          <div className="cut-actions cut-title-actions">
            {trailer && <a href={trailer} target="_blank" rel="noreferrer" className="cut-btn cut-primary"><Glyph name="play"/> Watch trailer</a>}
            {!saved && <button className={`cut-btn ${trailer ? "cut-secondary" : "cut-primary"}`} onClick={() => setStatus("want")} disabled={busy}><Glyph name="bookmark"/> Save to watchlist</button>}
            <button className="cut-btn cut-secondary" onClick={() => open("progress")} disabled={busy}><Glyph name="plus"/> Log progress</button>
            <button className="cut-btn cut-secondary" onClick={() => open("review")} disabled={busy}><Glyph name="pen"/> {reviewed ? "Edit review" : "Write review"}</button>
          </div>
          <label className="cut-status-field"><span>Watch status</span>
            <select aria-label="Watch status" value={status} disabled={busy} onChange={event => setStatus(event.target.value as Status)}>
              {Object.entries(statuses).filter(([key]) => key !== "on_hold" || status === "on_hold").map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>
        </div>
      </div>
    </div>
  </section>;
}

function TitleFacts({ data, region, onRegion }: { data: TitleData; region: string; onRegion: (region: string) => void }) {
  const { title } = data;
  const providerLink = safeUrl(title.watch_url);
  const source = safeUrl(title.source_url || title.external_url);
  const regions = [...new Set([region, "IN", "US", "GB", "CA", "AU", "DE", "FR", "JP", "KR"])];

  return <aside className="cut-facts">
    {!!title.reasons?.length && <section className="cut-detail-section cut-recommendation">
      <div className="cut-detail-section-head"><h2>Why it fits</h2>{title.score != null && <span className="cut-match">{title.score}% match</span>}</div>
      <ul>{title.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      {title.intensity && <p className="cut-muted">Intensity · {title.intensity}</p>}
      <p className="cut-muted">The match reflects your saved viewing history and preferences.</p>
    </section>}
    <section className="cut-detail-section" id="release">
      <h2>Release &amp; language</h2>
      <dl className="cut-fact-list">
        <div><dt>Release</dt><dd>{title.release_label || title.release_year || "Unavailable"}</dd></div>
        <div><dt>Language</dt><dd>{title.language || "Unavailable"}</dd></div>
        <div><dt>{title.media_type === "movie" ? "Runtime" : "Length"}</dt><dd>{titleTime(title) || "Unavailable"}</dd></div>
      </dl>
      {source && <a href={source} target="_blank" rel="noreferrer" className="cut-text-link">{source.includes("themoviedb.org/") ? "View on TMDB" : "View title source"} <Glyph name="outward" size={16}/></a>}
    </section>
    <section className="cut-detail-section" id="watch">
      <div className="cut-detail-section-head"><h2>Where to watch</h2>
        {typeof title.provider_data_available === "boolean" && <label className="cut-region"><span className="cut-sr">Streaming region</span><select aria-label="Streaming region" value={region} onChange={event => onRegion(event.target.value)}>
          {regions.map(code => <option key={code} value={code}>{regionNames.of(code) || code}</option>)}
        </select></label>}
      </div>
      {title.providers?.length ? <><ul className="cut-providers">{title.providers.map(provider => <li key={`${provider.name}-${provider.access}`}><strong>{provider.name}</strong><span>{provider.access}</span></li>)}</ul>
        {providerLink && <a className="cut-text-link" href={providerLink} target="_blank" rel="noreferrer">See provider listings <Glyph name="outward" size={16}/></a>}
        <p className="cut-muted">Availability for {regionNames.of(data.region)} from TMDB and JustWatch.</p></>
        : title.provider_data_available ? <p className="cut-muted">No providers listed for {regionNames.of(data.region)}.</p>
        : <p className="cut-muted">{data.region === "IN" && title.ott_india ? `Catalogue note for India: ${title.ott_india}. Current availability is unverified.` : "Verified streaming availability is unavailable for this title."}</p>}
    </section>
  </aside>;
}

export function CutDetail({ source, id }: { source: string; id: string }) {
  const endpoint = `/cinema/titles/${source}/${id}`;
  const [data, setData] = useState<TitleData>();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ text: string; error?: boolean }>();
  const [region, setRegion] = useState("IN");
  const [retry, setRetry] = useState(0);
  const [pendingRegion, setPendingRegion] = useState(false);
  const [busy, setBusy] = useState(false);
  const [savingRelated, setSavingRelated] = useState("");
  const [editor, setEditor] = useState<"progress" | "review">();
  const statusBusy = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setPendingRegion(true);
    api<TitleData>(`${endpoint}?region=${region}`, { signal: controller.signal })
      .then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(failure => { if (!controller.signal.aborted) setError(messageFrom(failure)); })
      .finally(() => { if (!controller.signal.aborted) setPendingRegion(false); });
    return () => controller.abort();
  }, [endpoint, region, retry]);

  async function updateStatus(status: Status) {
    if (!data) throw new Error("Title unavailable.");
    const result = await api<CutTitle>(`${titleApi(data.title)}/status`, { method: "PUT", body: JSON.stringify({ status }) });
    setData(current => current && ({ ...current, title: { ...current.title, media_id: result.media_id, status: result.status, personal_rating: result.personal_rating } }));
  }

  async function changeStatus(status: Status) {
    if (statusBusy.current) return;
    statusBusy.current = true;
    setBusy(true);
    setNotice(undefined);
    try {
      await updateStatus(status);
      setNotice({ text: `Watch status set to ${statuses[status]}.` });
    } catch (failure) {
      setNotice({ text: messageFrom(failure), error: true });
    } finally {
      statusBusy.current = false;
      setBusy(false);
    }
  }

  async function saveRelated(title: CutTitle) {
    if (savingRelated) return;
    setSavingRelated(cutPath(title));
    setNotice(undefined);
    try {
      const result = await api<CutTitle>(`${titleApi(title)}/status`, { method: "PUT", body: JSON.stringify({ status: "want" }) });
      setData(current => current && ({ ...current, title: {
        ...current.title,
        related: current.title.related?.map(item => cutPath(item) === cutPath(title)
          ? { ...item, media_id: result.media_id, status: result.status, personal_rating: result.personal_rating }
          : item),
      } }));
      setNotice({ text: `${title.title} added to your watchlist.` });
    } catch (failure) {
      setNotice({ text: messageFrom(failure), error: true });
    } finally {
      setSavingRelated("");
    }
  }

  async function log(values: Omit<Checkpoint, "id">) {
    const result = await api<{ checkpoint: Checkpoint; title: CutTitle }>(`${endpoint}/checkpoints`, { method: "POST", body: JSON.stringify(values) });
    setData(current => current && ({
      ...current,
      title: { ...current.title, media_id: result.title.media_id, status: result.title.status },
      checkpoints: [...current.checkpoints, result.checkpoint].sort((a, b) => a.viewing_date.localeCompare(b.viewing_date) || a.id - b.id),
    }));
    setNotice({ text: "Checkpoint saved." });
  }

  async function review(values: Omit<Review, "finalized_at" | "updated_at">) {
    const result = await api<{ review: Review; title: CutTitle }>(`${endpoint}/review`, { method: "PUT", body: JSON.stringify(values) });
    setData(current => current && ({
      ...current, review: result.review,
      title: { ...current.title, media_id: result.title.media_id, status: result.title.status, personal_rating: result.review.rating },
    }));
    setNotice({ text: data?.review ? "Review updated." : "Review finalized." });
  }

  return <CutFrame>
    {notice && <div className={`cut-toast ${notice.error ? "is-error" : ""}`} role={notice.error ? "alert" : "status"}>{notice.text}<button aria-label="Dismiss message" onClick={() => setNotice(undefined)}><Glyph name="close" size={17}/></button></div>}
    {!data ? <div className="cut-container cut-body-spacing">
      {error ? <StatePanel title="Couldn’t open this title" error><p>{error}</p><div className="cut-actions"><button className="cut-btn cut-secondary" onClick={() => setRetry(value => value + 1)}>Retry</button><Link href="/browse/discover" className="cut-btn cut-primary">Discover titles</Link></div></StatePanel>
      : <div role="status" aria-busy="true"><div className="cut-loading"/><p>Opening title…</p></div>}
    </div> : <>
      <TitleIntro title={data.title} status={data.title.status || "recommended"} reviewed={!!data.review} busy={busy || pendingRegion} setStatus={changeStatus} open={setEditor}/>
      <nav className="cut-jumps" aria-label="On this page"><div className="cut-container">{sections.map(([target, label]) => <a key={target} href={`#${target}`}>{label}</a>)}</div></nav>
      <div className="cut-container">
        {(error || data.metadata_notice) && <p className="cut-inline-notice" role="alert">{error || data.metadata_notice} <button className="cut-text-button" onClick={() => setRetry(value => value + 1)}>Retry</button></p>}
        {pendingRegion && <p className="cut-inline-notice" role="status">Checking availability for {regionNames.of(region)}…</p>}
        <div className="cut-detail-grid">
          <div>
            <section className="cut-detail-section" id="credits">
              <h2>Cast &amp; crew</h2>
              <div className="cut-credits">
                {(["cast", "crew"] as const).map(kind => <div key={kind}><h3>{kind === "cast" ? "Cast" : "Crew"}</h3>
                  {data.title[kind]?.length ? <ul>{data.title[kind].map((person, index) => <li key={`${person.name}-${index}`}><strong>{person.name}</strong><span>{person.role}</span></li>)}</ul>
                  : <p className="cut-muted">Credits unavailable.</p>}
                </div>)}
              </div>
              {!safeUrl(data.title.trailer_url) && <p className="cut-muted">Trailer unavailable for this title.</p>}
            </section>
            <Timeline checkpoints={data.checkpoints} open={() => setEditor("progress")}/>
            <FinalReview review={data.review} count={data.checkpoints.length} open={() => setEditor("review")}/>
          </div>
          <TitleFacts data={data} region={region} onRegion={setRegion}/>
        </div>
        <div id="related" className="cut-related">{data.title.related?.length ? <Shelf name="Related titles" titles={data.title.related} saving={savingRelated} onSave={saveRelated}/> : <section className="cut-detail-section"><h2>Related titles</h2><p className="cut-muted">No related titles are available.</p></section>}</div>
      </div>
      {editor === "progress" && <CheckpointEditor movie={data.title.media_type === "movie"} runtime={data.title.runtime} previous={data.checkpoints.at(-1)} close={() => setEditor(undefined)} submit={log}/>}
      {editor === "review" && <ReviewEditor review={data.review} rating={data.title.personal_rating} close={() => setEditor(undefined)} submit={review}/>}
    </>}
  </CutFrame>;
}
