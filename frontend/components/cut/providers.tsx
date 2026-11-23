"use client";

import Image from "next/image";
import { useState } from "react";
import { type CutTitle, type WatchProvider } from "@/lib/cut";

const logos: Record<string, string> = {
  "prime video": "/providers/prime-video.png",
  "amazon prime video": "/providers/prime-video.png",
  "jiohotstar": "/providers/jiohotstar.png",
  "vi movies and tv": "/providers/vi-movies-tv.png",
  "vi movies & tv": "/providers/vi-movies-tv.png",
};

export function catalogueProvider(title: CutTitle): WatchProvider | undefined {
  const note = title.ott_india?.trim();
  if (note && logos[note.toLowerCase()]) return { name: note, access: "Unverified" };
}

function ProviderTile({ provider }: { provider: WatchProvider }) {
  const [failed, setFailed] = useState<string>();
  const logo = logos[provider.name.toLowerCase()] ||
    (/^https:\/\/image\.tmdb\.org\/t\/p\/original\/[A-Za-z0-9_-]+\.(png|jpg)$/.test(provider.logo_url || "") ? provider.logo_url : undefined);
  return <li className="cut-provider-tile">
    {logo && logo !== failed && <Image src={logo} alt="" width={56} height={56} unoptimized onError={() => setFailed(logo)}/>}
    <div><strong>{provider.name}</strong><span>{provider.access}</span></div>
  </li>;
}

export function ProviderTiles({ providers }: { providers: WatchProvider[] }) {
  return <ul className="cut-provider-tiles" aria-label="Streaming providers">
    {providers.map(provider => <ProviderTile provider={provider} key={`${provider.name}-${provider.access}`}/>)}
  </ul>;
}
