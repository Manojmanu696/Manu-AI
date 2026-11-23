"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { titleApi, totalWatchTime, type CutTitle, type Prediction, type RatingFeedback } from "@/lib/cut";
import { catalogueProviders, ProviderTiles, streamingListings } from "./providers";

type CardData = { title: CutTitle; rating_feedback: RatingFeedback | null; prediction: Pick<Prediction, "score" | "model"> | null };

const metadataRequests = new Map<string, Promise<CardData>>();
let scoreQueue = Promise.resolve();

function loadCard(endpoint: string) {
  const active = metadataRequests.get(endpoint);
  if (active) return active;
  const request = api<CardData>(`${endpoint}?card=true`).finally(() => {
    if (metadataRequests.get(endpoint) === request) metadataRequests.delete(endpoint);
  });
  metadataRequests.set(endpoint, request);
  return request;
}

function loadPrediction(endpoint: string, signal: AbortSignal) {
  const request = scoreQueue.then(() => {
    if (signal.aborted) throw new DOMException("Card left the page", "AbortError");
    return api<Prediction>(`${endpoint}/prediction?reuse=true`, { method: "POST" });
  });
  scoreQueue = request.then(() => {}, () => {});
  return request;
}

export function useTitleCard(title: CutTitle) {
  const ref = useRef<HTMLElement>(null);
  const [started, setStarted] = useState(false);
  const [card, setCard] = useState<CardData>();
  const [unavailable, setUnavailable] = useState(false);
  const [revision, setRevision] = useState(0);
  const endpoint = titleApi(title);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setStarted(true);
        observer.disconnect();
      }
    }, { rootMargin: "180px" });
    if (ref.current) observer.observe(ref.current);
    function refresh() {
      metadataRequests.delete(endpoint);
      setRevision(value => value + 1);
    }
    window.addEventListener("manu-taste-updated", refresh);
    return () => {
      observer.disconnect();
      window.removeEventListener("manu-taste-updated", refresh);
    };
  }, [endpoint]);

  useEffect(() => {
    if (!started) return;
    let ignore = false;
    setCard(undefined);
    setUnavailable(false);
    loadCard(endpoint)
      .then(result => { if (!ignore) setCard(result); })
      .catch(() => { if (!ignore) setUnavailable(true); });
    return () => { ignore = true; };
  }, [endpoint, started, revision]);

  useEffect(() => {
    if (!card || card.prediction || unavailable) return;
    const controller = new AbortController();
    loadPrediction(endpoint, controller.signal)
      .then(prediction => {
        if (!controller.signal.aborted) setCard({ ...card, prediction, rating_feedback: prediction.rating_feedback });
      })
      .catch(error => {
        if (!controller.signal.aborted && error?.name !== "AbortError") setUnavailable(true);
      });
    return () => controller.abort();
  }, [endpoint, card, unavailable]);

  return { ref, title: card?.title ?? title, feedback: card?.rating_feedback, prediction: card?.prediction,
    pending: started && !unavailable && !card?.prediction, unavailable };
}

export function CardFacts({ title, prediction, feedback, pending, unavailable }: Omit<ReturnType<typeof useTitleCard>, "ref">) {
  const series = title.media_type !== "movie";
  const providers = title.providers?.length ? title.providers : !title.provider_data_available ? catalogueProviders(title) : [];
  return <div className="cut-card-facts">
    <dl>
      <div><dt>{series ? "Total watch time" : "Runtime"}</dt><dd>{totalWatchTime(title) || "—"}</dd></div>
      {series && <div><dt>Seasons · Episodes</dt><dd>{title.seasons ?? "—"} · {title.episodes ?? "—"}</dd></div>}
      <div><dt>AI prediction</dt><dd title={prediction?.model}>
        {prediction ? `${prediction.score.toFixed(1)}/10` : unavailable ? "Unavailable" : pending ? "Pending…" : "—"}
      </dd></div>
      {feedback && <div><dt>Your feedback</dt><dd>{feedback.score.toFixed(1)}/10</dd></div>}
    </dl>
    <div className="cut-poster-providers">
      <span>Watch in India</span>
      {providers.length ? <ProviderTiles providers={providers}/> : <p>{title.provider_data_available ? "No listings found" : "Availability unverified"}</p>}
      <a href={streamingListings(title)} target="_blank" rel="noreferrer">JustWatch ↗</a>
    </div>
  </div>;
}
