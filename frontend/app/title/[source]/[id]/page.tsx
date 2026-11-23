import { notFound } from "next/navigation";
import { CutDetail } from "@/components/cut/detail";

export default async function TitlePage({ params }: { params: Promise<{ source: string; id: string }> }) {
  const { source, id } = await params;
  if (!["media", "catalogue", "tvmaze", "movie", "tv", "anime"].includes(source) || !/^[1-9]\d{0,9}$/.test(id)) notFound();
  return <CutDetail key={`${source}/${id}`} source={source} id={id}/>;
}
