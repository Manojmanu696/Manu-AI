const approvedHosts = new Set(["image.tmdb.org", "s4.anilist.co", "static.tvmaze.com"]);

export async function GET(request: Request) {
  const source = new URL(request.url).searchParams.get("src");
  if (!source) return new Response("Missing source", { status: 400 });
  let imageUrl: URL;
  try { imageUrl = new URL(source); } catch { return new Response("Invalid source", { status: 400 }); }
  if (imageUrl.protocol !== "https:" || !approvedHosts.has(imageUrl.hostname)) return new Response("Source not allowed", { status: 403 });

  try {
    const upstream = await fetch(imageUrl, { signal: AbortSignal.timeout(8000), headers: { Accept: "image/avif,image/webp,image/png,image/jpeg" } });
    const contentType = upstream.headers.get("content-type")?.split(";")[0] || "";
    const length = Number(upstream.headers.get("content-length") || 0);
    if (!upstream.ok || !contentType.startsWith("image/") || (length && length > 8_000_000)) return new Response("Artwork unavailable", { status: 502 });
    const bytes = await upstream.arrayBuffer();
    if (bytes.byteLength > 8_000_000) return new Response("Artwork too large", { status: 413 });
    return new Response(bytes, { headers: { "Content-Type": contentType, "Cache-Control": "public, max-age=3600, s-maxage=86400", "X-Content-Type-Options": "nosniff" } });
  } catch {
    return new Response("Artwork provider unavailable", { status: 502 });
  }
}
