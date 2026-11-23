export const mediaTypes = { movie: "Movie", tv: "TV Series", anime: "Anime" } as const;
export type ScreenType = keyof typeof mediaTypes;
export const statuses = {
  recommended: "Recommended", want: "Want to Watch", current: "Watching",
  completed: "Watched", dropped: "Dropped", on_hold: "On Hold",
} as const;
export type Status = keyof typeof statuses;
export type Credit = { name: string; role: string };
export type WatchProvider = { name: string; access: string; logo_url?: string; url?: string };
export type RatingFeedback = { score: number; title: string };

export type Prediction = {
  score: number;
  explanation: string;
  what_you_might_like: string[];
  what_you_might_dislike: string[];
  verdict: string;
  recommendation: string;
  model: string;
  rating_feedback: RatingFeedback | null;
};

export type CutTitle = {
  id: number;
  source: "media" | "catalogue" | "tvmaze" | "ranked" | ScreenType;
  media_type: ScreenType;
  title: string;
  description?: string;
  genres?: string;
  release_year?: number;
  runtime?: string;
  seasons?: number | null;
  episodes?: number | null;
  episode_duration?: string;
  total_runtime_minutes?: number;
  image_url?: string;
  backdrop_url?: string;
  status?: Status;
  media_id?: number;
  personal_rating?: number | null;
  imdb_rating?: number | null;
  public_rating?: number | null;
  rating_source?: string;
  external_id?: string;
  external_url?: string;
  source_url?: string;
  release_label?: string;
  language?: string;
  trailer_url?: string;
  cast?: Credit[];
  crew?: Credit[];
  providers?: WatchProvider[];
  provider_data_available?: boolean;
  provider_source?: string;
  watch_url?: string;
  ott_india?: string;
  score?: number;
  reasons?: string[];
  intensity?: string;
  related?: CutTitle[];
  is_demo?: boolean;
};

export type BrowseData = { library: CutTitle[]; catalogue: CutTitle[]; reviewed: CutTitle[]; public_search: boolean };
export type Checkpoint = {
  id: number; viewing_date: string; minute: number | null; season: number | null; episode: number | null;
  headline: string; notes: string; feeling: string; pacing: string; rating: number | null;
  rewatch: string; tags: string; spoiler: boolean;
};
export type Review = {
  rating: number; verdict: string; body: string; tags: string; spoiler_notes: string; spoiler: boolean;
  finalized_at: string; updated_at: string;
};
export type TitleData = { title: CutTitle; checkpoints: Checkpoint[]; review: Review | null; rating_feedback: RatingFeedback | null; metadata_notice: string; region: string };

export const cutPath = (title: CutTitle) => `/title/${title.source}/${title.id}`;
export const titleApi = (title: CutTitle) => `/cinema/titles/${title.source}/${title.id}`;
export const splitLabels = (text = "") => text.split(/[,|]/).map(label => label.trim()).filter(Boolean);
export const titleTime = (title: CutTitle) => title.seasons ? `${title.seasons} ${title.seasons === 1 ? "season" : "seasons"}` : title.runtime || (title.episodes ? `${title.episodes} episodes` : "");
export function totalWatchTime(title: CutTitle) {
  if (title.media_type === "movie") return title.runtime;
  const duration = /^(\d+)\s*min(?:\s+per episode)?$/i.exec(title.episode_duration || title.runtime || "");
  const minutes = title.total_runtime_minutes || (duration && title.episodes ? Number(duration[1]) * title.episodes : 0);
  if (!minutes) return undefined;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return `${title.total_runtime_minutes ? "" : "≈ "}${hours ? hours + "h" : ""}${hours && remainder ? " " : ""}${remainder ? remainder + "m" : ""}`;
}
export const publicRating = (title: CutTitle) => title.imdb_rating != null
  ? { value: title.imdb_rating, source: "IMDb" }
  : title.public_rating != null ? { value: title.public_rating, source: title.rating_source || "Catalogue" } : null;
export const cardRating = (title: CutTitle) => title.personal_rating != null
  ? { value: title.personal_rating, source: "Your rating" } : publicRating(title);
export const sameTitle = (a: CutTitle, b: CutTitle) => {
  if (a.media_type !== b.media_type) return false;
  if (a.source === b.source && a.id === b.id) return true;
  if (a.external_id && b.external_id) return a.external_id === b.external_id;
  return a.release_year === b.release_year && a.title.trim().toLowerCase() === b.title.trim().toLowerCase();
};
export const messageFrom = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Try again.";
export const formatDate = (value: string) => new Intl.DateTimeFormat("en", {
  year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
}).format(new Date(value.length === 10 ? value + "T00:00:00Z" : /Z$|[+-]\d\d:\d\d$/.test(value) ? value : value + "Z"));

export function safeUrl(value?: string) {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : undefined;
  } catch {
    return undefined;
  }
}

export const browseViews = ["discover", "movies", "tv", "anime", "library", "reviews"];
