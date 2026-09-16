export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type MediaItem = { id:number; media_type:string; title:string; description:string; genres:string; personal_rating:number|null; sentiment:string; status:string; notes:string; tags:string; runtime:string; release_year:number|null; image_url:string; is_demo:boolean; date_added:string };
export type Memory = { id:number; category:string; content:string; source:string; confidence:number|null; is_demo:boolean };
export type Recommendation = { item:MediaItem; score:number; reasons:string[] };

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options?.headers || {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => ({detail: "Request failed"}))).detail || "Request failed");
  return response.status === 204 ? undefined as T : response.json();
}

