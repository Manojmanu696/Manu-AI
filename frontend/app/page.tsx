import Dashboard from "./dashboard";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ view?: string | string[] }>;
}) {
  const { view } = await searchParams;
  return <Dashboard view={typeof view === "string" ? view : undefined} />;
}
