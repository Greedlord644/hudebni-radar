"use client";

import { useMemo, useState } from "react";
import { ArrowUpRight, CalendarDays, Link2, MapPin, Radio, Sparkles } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Ad = { id: string; title: string; url: string; date: string; location: string; author: string; excerpt: string; score: number; reasons: string[]; externalLinks?: string[]; influences?: string[]; genres?: string[]; isPrague?: boolean };
type RadarData = { updatedAt: string; windowDays: number; singerSeeking: Ad[]; interesting: Ad[] };
const date = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric" });

function AdCard({ ad, featured = false }: { ad: Ad; featured?: boolean }) {
  return (
    <article className={`group relative overflow-hidden rounded-2xl border p-5 transition hover:-translate-y-0.5 hover:border-cyan-400/40 hover:bg-white/[0.055] ${featured ? "border-cyan-400/30 bg-cyan-400/[0.055]" : "border-white/10 bg-white/[0.035]"}`}>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-slate-400">
        <span className="inline-flex items-center gap-1.5"><CalendarDays className="size-4" />{date.format(new Date(ad.date))}</span><span className="text-slate-700">•</span>
        <span className="inline-flex items-center gap-1.5"><MapPin className="size-4" />{ad.location}</span>
        <span className="ml-auto rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs font-semibold text-slate-300">shoda {ad.score}%</span>
      </div>
      <h2 className="pr-8 text-xl font-semibold leading-snug tracking-tight text-white">{ad.title}</h2>
      <p className="mt-3 line-clamp-3 max-w-3xl leading-7 text-slate-300">{ad.excerpt}</p>
      <div className="mt-4 flex flex-wrap gap-2">{ad.reasons.map((reason) => <span key={reason} className="rounded-full bg-white/[0.07] px-3 py-1 text-xs font-medium text-slate-300">{reason}</span>)}</div>
      {!!ad.externalLinks?.length && <div className="mt-4 flex flex-wrap gap-2">{ad.externalLinks.map((link) => <a key={link} href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1.5 text-sm font-semibold text-cyan-200 hover:bg-cyan-300/[0.12]"><Link2 className="size-3.5" />{link.includes("youtube") || link.includes("youtu.be") ? "YouTube" : link.includes("instagram") ? "Instagram" : link.includes("spotify") ? "Spotify" : "Externí odkaz"}</a>)}</div>}
      <div className="mt-5 flex items-center justify-between border-t border-white/8 pt-4 text-sm">
        <span className="text-slate-500">{ad.author}</span>
        <a className="inline-flex items-center gap-1.5 font-semibold text-cyan-300 outline-none hover:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-300" href={ad.url} target="_blank" rel="noreferrer">Otevřít inzerát <ArrowUpRight className="size-4" /></a>
      </div>
    </article>
  );
}

function EmptyState({ singer }: { singer?: boolean }) {
  return <div className="rounded-2xl border border-dashed border-white/15 px-6 py-14 text-center text-slate-400">{singer ? "Za posledních 60 dní nebyl nalezen žádný vhodný zpěvák ani zpěvačka." : "Momentálně tu nejsou žádné dostatečně relevantní inzeráty."}</div>;
}

type FilterKey = "prague" | "genres" | "bands";

function matchesFilter(ad: Ad, filter: FilterKey) {
  if (filter === "prague") return Boolean(ad.isPrague);
  if (filter === "genres") return Boolean(ad.genres?.length);
  return Boolean(ad.influences?.length);
}

function Filters({ ads, active, onToggle, onClear }: { ads: Ad[]; active: Set<FilterKey>; onToggle: (value: FilterKey) => void; onClear: () => void }) {
  const filters: { key: FilterKey; label: string }[] = [
    { key: "prague", label: "Praha" },
    { key: "genres", label: "Relevantní žánry" },
    { key: "bands", label: "Zmíněné kapely" },
  ];
  const countFor = (key: FilterKey) => ads.filter((ad) => [...active].filter((item) => item !== key).every((item) => matchesFilter(ad, item)) && matchesFilter(ad, key)).length;
  const chip = ({ key, label }: { key: FilterKey; label: string }) => {
    const selected = active.has(key);
    return <Button key={key} type="button" size="sm" variant="outline" aria-pressed={selected} onClick={() => onToggle(key)} className={`rounded-full border-white/10 bg-white/[0.035] text-slate-300 shadow-none hover:border-cyan-300/30 hover:bg-cyan-300/[0.08] hover:text-cyan-100 ${selected ? "border-cyan-300/50 bg-cyan-300 text-slate-950 hover:bg-cyan-200 hover:text-slate-950" : ""}`}>{label}<span className={`rounded-full px-1.5 py-0.5 text-xs ${selected ? "bg-black/10" : "bg-white/[0.08]"}`}>{countFor(key)}</span></Button>;
  };
  const allSelected = active.size === 0;

  return <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.025] p-4">
    <div className="flex flex-wrap items-center gap-2"><span className="mr-1 text-sm font-semibold text-slate-400">Filtrovat</span><Button type="button" size="sm" variant="outline" aria-pressed={allSelected} onClick={onClear} className={`rounded-full border-white/10 bg-white/[0.035] text-slate-300 shadow-none hover:border-cyan-300/30 hover:bg-cyan-300/[0.08] hover:text-cyan-100 ${allSelected ? "border-cyan-300/50 bg-cyan-300 text-slate-950 hover:bg-cyan-200 hover:text-slate-950" : ""}`}>Vše<span className={`rounded-full px-1.5 py-0.5 text-xs ${allSelected ? "bg-black/10" : "bg-white/[0.08]"}`}>{ads.length}</span></Button>{filters.map(chip)}</div>
  </div>;
}

export function Radar({ data }: { data: RadarData }) {
  const [filters, setFilters] = useState<Set<FilterKey>>(() => new Set());
  const [sort, setSort] = useState("newest");
  const filteredInteresting = useMemo(() => {
    const result = data.interesting.filter((ad) => [...filters].every((filter) => matchesFilter(ad, filter)));
    return [...result].sort(sort === "score" ? (a, b) => b.score - a.score || Date.parse(b.date) - Date.parse(a.date) : (a, b) => Date.parse(b.date) - Date.parse(a.date) || b.score - a.score);
  }, [data.interesting, filters, sort]);
  const toggleFilter = (filter: FilterKey) => setFilters((current) => {
    const next = new Set(current);
    if (next.has(filter)) next.delete(filter); else next.add(filter);
    return next;
  });
  return (
    <main className="min-h-screen bg-[#070a10] text-slate-100">
      <div className="radar-glow pointer-events-none fixed inset-0" />
      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6 sm:pt-12">
        <header className="mb-9 flex flex-col gap-6 border-b border-white/10 pb-8 md:flex-row md:items-end md:justify-between">
          <div><div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-300/[0.06] px-3 py-1.5 text-sm font-semibold text-cyan-200"><Radio className="size-4" /> Automatický výběr</div>
            <h1 className="text-4xl font-bold tracking-[-0.04em] text-white sm:text-6xl">Hudební radar<span className="text-cyan-300">.</span></h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">Zajímaví lidé a vznikající projekty z Hudebního bazaru — pro hledání zpěvu, networking a objevování nové hudby.</p></div>
          <div className="shrink-0 text-sm leading-6 text-slate-500"><span className="block font-semibold text-slate-300">Poslední kontrola</span>{date.format(new Date(data.updatedAt))} · okno {data.windowDays} dní</div>
        </header>
        <Tabs defaultValue="singer" className="gap-6">
          <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto rounded-xl border border-white/10 bg-white/[0.04] p-1.5 sm:w-fit">
            <TabsTrigger value="singer" className="min-h-10 gap-2 rounded-lg px-4 text-sm data-[state=active]:bg-cyan-300 data-[state=active]:text-slate-950"><Sparkles className="size-4" />Zpěv hledá <span className="rounded-full bg-black/10 px-2 py-0.5 text-xs">{data.singerSeeking.length}</span></TabsTrigger>
            <TabsTrigger value="interesting" className="min-h-10 gap-2 rounded-lg px-4 text-sm data-[state=active]:bg-cyan-300 data-[state=active]:text-slate-950">Obecně zajímavé <span className="rounded-full bg-black/10 px-2 py-0.5 text-xs">{data.interesting.length}</span></TabsTrigger>
          </TabsList>
          <TabsContent value="singer" className="space-y-4"><div className="mb-5"><h2 className="text-2xl font-semibold tracking-tight text-white">Zpěv hledá kapelu nebo projekt</h2><p className="mt-1 text-slate-400">Pouze Praha a Středočeský kraj; bez coverů, tribute a zábavových kapel.</p></div>{data.singerSeeking.length ? data.singerSeeking.map((ad, i) => <AdCard key={ad.id} ad={ad} featured={i === 0} />) : <EmptyState singer />}</TabsContent>
          <TabsContent value="interesting" className="space-y-4"><div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-2xl font-semibold tracking-tight text-white">Obecně zajímavé inzeráty</h2><p className="mt-1 text-slate-400">Moderní rock a metal, vlastní tvorba a nové projekty vhodné ke sledování, propojení nebo podpoře.</p></div><div className="shrink-0"><label className="mb-1.5 block text-sm font-semibold text-slate-400">Řazení</label><Select value={sort} onValueChange={setSort}><SelectTrigger className="min-w-44 border-white/10 bg-white/[0.035] text-slate-200"><SelectValue /></SelectTrigger><SelectContent className="border-white/10 bg-[#111821] text-slate-100"><SelectItem value="newest">Nejnovější</SelectItem><SelectItem value="score">Nejvyšší shoda</SelectItem></SelectContent></Select></div></div><Filters ads={data.interesting} active={filters} onToggle={toggleFilter} onClear={() => setFilters(new Set())} />{filteredInteresting.length ? filteredInteresting.map((ad, i) => <AdCard key={ad.id} ad={ad} featured={i === 0} />) : <EmptyState />}</TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
