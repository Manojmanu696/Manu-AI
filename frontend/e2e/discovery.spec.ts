import { expect, test, type Page } from "@playwright/test";

const title = {
  id: 42,
  media_type: "movie",
  title: "The Signal",
  description: "A clever mystery built around a strange transmission.",
  genres: "Mystery, Science Fiction",
  release_year: 2024,
  image_url: "",
  backdrop_url: "",
  public_rating: 7.8,
  vote_count: 450,
  runtime: "108 min",
  runtime_minutes: 108,
  source_provider: "tmdb",
  provider_id: "42",
  external_id: "tmdb:movie:42",
  external_url: "https://www.themoviedb.org/movie/42",
  source_url: "https://www.themoviedb.org/movie/42",
  watch_providers_json: "[]",
  credits_json: "{}",
  countries_json: '["US"]',
  recommendation: { label: "Strong match", reasons: ["Matches a saved mystery preference"], caveats: [] },
  personal: null,
};

function recommendation(item = title) {
  return { item, fit: "Strong match", reasons: ["Matches a saved mystery preference"], source: "tmdb" };
}

async function mockApi(page: Page) {
  const feedback: Array<{ path: string; body: unknown }> = [];
  await page.route("http://127.0.0.1:8000/**", async route => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/home") {
      return route.fulfill({ json: {
        sections: {
          personalized_movies: { items: [recommendation()], provider: "personalized", stale: false },
          personalized_tv: { items: [], provider: "personalized", stale: false },
          trending_movies: { items: [], provider: "tmdb", stale: false },
          because_you_liked: { items: [], based_on: null, provider: "personalized", stale: false },
          continue_watching: { items: [], provider: "local", stale: false },
        },
        refreshing: false,
        stale: false,
        last_updated: "2026-11-07T10:00:00",
        providers: { tmdb: { status: "available" }, anilist: { status: "available" }, tvmaze: { status: "available" } },
        attribution: { tmdb: "This product uses the TMDB API but is not endorsed or certified by TMDB." },
      } });
    }
    if (path === "/media" || path === "/recommendations" || path === "/memories" || path === "/taste-signals") return route.fulfill({ json: [] });
    if (path === "/data/summary") return route.fulfill({ json: { database_bytes: 4096, counts: { movie: 0, anime: 0, tv: 0, game: 0, book: 0 }, memories: 0, last_backup: null, backup_location: "" } });
    if (path === "/discover" && request.method() === "GET") {
      if (url.searchParams.get("query")) {
        const alternate = { ...title, id: 43, title: "Dune", genres: "Mystery", external_id: "tmdb:movie:43" };
        return route.fulfill({ json: [recommendation({ ...title, title: "Dune: Part Two", genres: "Science Fiction", external_id: "tmdb:movie:42" }), recommendation(alternate)] });
      }
      return route.fulfill({ json: [recommendation()] });
    }
    if (path === "/catalogue/42") return route.fulfill({ json: title });
    if (path === "/catalogue/43") return route.fulfill({ json: { ...title, id: 43, title: "Dune" } });
    if (path === "/discover/42/feedback") {
      feedback.push({ path, body: request.postDataJSON() });
      return route.fulfill({ json: { saved: true, action: request.postDataJSON().action, feedback_id: 71 } });
    }
    if (path === "/feedback/71/undo") {
      feedback.push({ path, body: request.postData() ? request.postDataJSON() : null });
      return route.fulfill({ json: { undone: true } });
    }
    if (path === "/data/export/zip") return route.fulfill({ status: 200, contentType: "application/zip", body: Buffer.from("test backup") });
    if (path === "/data/export/json") return route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    if (path === "/data/export/csv") return route.fulfill({ status: 200, contentType: "text/csv", body: "title\\n" });
    return route.fulfill({ status: 200, json: {} });
  });
  return feedback;
}

test("home discovery accepts feedback and undo", async ({ page }) => {
  const feedback = await mockApi(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your next watch." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Picked for your taste" })).toBeVisible();
  await page.getByRole("button", { name: "Like The Signal" }).click();
  await expect(page.getByText("Saved your feedback for The Signal")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Feedback undone")).toBeVisible();
  expect(feedback.map(event => event.path)).toEqual(["/discover/42/feedback", "/feedback/71/undo"]);
  expect(feedback[0].body).toMatchObject({ action: "like", context: "best_fit:any" });
});

test("search filters live results and opens a title detail", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("textbox", { name: "Search films, series and anime" }).fill("Dune");
  await expect(page.getByRole("heading", { name: "Results for “Dune”" })).toBeVisible();
  await page.getByText("Refine search results").click();
  await page.getByLabel("Genre").fill("mystery");
  await expect(page.getByRole("link", { name: "Open Dune", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Dune: Part Two", exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Open Dune", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dune", exact: true })).toBeVisible();
  await expect(page.getByText("A clever mystery built around a strange transmission.")).toBeVisible();
});

test("local data page starts a complete backup download", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Data" }).click();
  await expect(page.getByRole("heading", { name: "Your data." })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download full backup" }).click();
  expect((await download).suggestedFilename()).toBe("ManuAI_Backup.zip");
});
