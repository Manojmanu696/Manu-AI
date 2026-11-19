import { notFound } from "next/navigation";
import { CutBrowse } from "@/components/cut/browse";
import { browseViews } from "@/lib/cut";
import { Suspense } from "react";

export default async function BrowsePage({ params }: { params: Promise<{ view: string }> }) {
  const { view } = await params;
  if (!browseViews.includes(view)) notFound();
  return <Suspense fallback={<main aria-busy="true">Opening Manu’s Cut…</main>}><CutBrowse view={view}/></Suspense>;
}
