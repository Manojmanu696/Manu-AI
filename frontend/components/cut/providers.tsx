"use client";

import Image from "next/image";
import { useState } from "react";
import { safeUrl, type CutTitle, type WatchProvider } from "@/lib/cut";

const logos: Record<string, string> = {
  "prime video": "/providers/prime-video.png",
  "amazon prime video": "/providers/prime-video.png",
  "jiohotstar": "/providers/jiohotstar.png",
  "vi movies and tv": "/providers/vi-movies-tv.png",
  "vi movies & tv": "/providers/vi-movies-tv.png",
};

export function catalogueProviders(title: CutTitle): WatchProvider[] {
  const note = title.ott_india?.trim() || "";
  if (/^(?:not |unavailable|unknown|none|n\/a)/i.test(note)) return [];
  return note.split(/[,;|]/).map(name => name.trim()).filter(Boolean).map(name => ({ name, access: "Unverified" }));
}

function ProviderTile({ provider }: { provider: WatchProvider }) {
  const [failed, setFailed] = useState<string>();
  const logo = logos[provider.name.toLowerCase()] ||
    (/^https:\/\/(?:image\.tmdb\.org\/t\/p\/original\/|images\.justwatch\.com\/icon(?:_wide)?\/\d+\/s\d+\/)[A-Za-z0-9_.-]+\.(?:png|jpe?g|webp)$/.test(provider.logo_url || "") ? provider.logo_url : undefined);
  const url = safeUrl(provider.url);
  const copy = <>
    {logo && logo !== failed && <Image src={logo} alt="" width={56} height={56} unoptimized onError={() => setFailed(logo)}/>}
    <div><strong>{provider.name}</strong><span>{provider.access}</span></div>
  </>;
  return <li className="cut-provider-tile">{url ? <a href={url} target="_blank" rel="noreferrer">{copy}</a> : copy}</li>;
}

export function ProviderTiles({ providers }: { providers: WatchProvider[] }) {
  const unique = new Map<string, WatchProvider>();
  for (const provider of providers) {
    unique.set(`${provider.name.toLowerCase()}-${provider.access}`, provider);
  }
  return <ul className="cut-provider-tiles" aria-label="Streaming providers">
    {[...unique.entries()].map(([key, provider]) => <ProviderTile provider={provider} key={key}/>)}
  </ul>;
}

export function streamingListings(title: CutTitle, region = "IN") {
  return safeUrl(title.watch_url) || `https://www.justwatch.com/${region.toLowerCase()}/search?q=${encodeURIComponent(title.title)}`;
}
