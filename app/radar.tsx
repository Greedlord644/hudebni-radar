"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Bookmark, CalendarDays, Check, Link2, MapPin, Sparkles } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

type Ad = { id: string; title: string; url: string; date: string; location: string; author: string; excerpt: string; score: number; reasons: string[]; externalLinks?: string[]; influences?: string[]; genres?: string[]; isPrague?: boolean };
type RadarData = { updatedAt: string; windowDays: number; singerSeeking: Ad[]; interesting: Ad[] };
type Section = "singer" | "interesting";
type SavedAd = { ad: Ad; sections: Section[] };
type FilterKey = "prague" | "genres" | "bands";
type StatusFilter = "all" | "new" | "read" | "saved";

const date = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Prague" });
const checkedAt = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Prague" });
const READ_KEY = "hudebni-radar-read-ads-v2";
const SAVED_KEY = "hudebni-radar-saved-ads-v1";

function adKey(ad: Ad) {
  const author = ad.author.trim().toLocaleLowerCase("cs");
  const title = ad.title.trim().toLocaleLowerCase("cs").replace(/\s+/g, " ");
  return author && author !== "neuvedeno" ? `${author}|${title}` : ad.id;
}

function AdCard({ ad, isRead, isSaved, onRead, onSave }: { ad: Ad; isRead: boolean; isSaved: boolean; onRead: () => void; onSave: () => void }) {
  return <article className={`group relative overflow-hidden rounded-2xl border p-5 transition hover:-translate-y-0.5 ${isRead ? "border-white/8 bg-white/[0.02] opacity-75 hover:opacity-100" : "border-cyan-300/45 bg-cyan-300/[0.075] shadow-[inset_3px_0_0_rgba(103,232,249,0.65)] hover:border-cyan-300/65"}`}>
    <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-slate-400">
      <span className="inline-flex items-center gap-1.5"><CalendarDays className="size-4" />{date.format(new Date(ad.date))}</span><span className="text-slate-700">•</span>
      <span className="inline-flex items-center gap-1.5"><MapPin className="size-4" />{ad.location}</span>
      {!isRead && <span className="rounded-full border border-cyan-300/35 bg-cyan-300/15 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-cyan-200">Nový</span>}
      {isSaved && <span className="inline-flex items-center gap-1 rounded-full border border-amber-300/25 bg-amber-300/10 px-2.5 py-1 text-xs font-semibold text-amber-200"><Bookmark className="size-3" /> Uložený</span>}
      <span className="ml-auto rounded-full border border-white/10 bg-black/20 px-2.5 py-1 text-xs font-semibold text-slate-300">shoda {ad.score}%</span>
    </div>
    <h2 className="pr-8 text-xl font-semibold leading-snug tracking-tight text-white">{ad.title}</h2>
    <p className="mt-3 line-clamp-3 max-w-3xl leading-7 text-slate-300">{ad.excerpt}</p>
    <div className="mt-4 flex flex-wrap gap-2">{ad.reasons.map((reason) => <span key={reason} className="rounded-full bg-white/[0.07] px-3 py-1 text-xs font-medium text-slate-300">{reason}</span>)}</div>
    {!!ad.externalLinks?.length && <div className="mt-4 flex flex-wrap gap-2">{ad.externalLinks.map((link) => <a key={link} href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-1.5 text-sm font-semibold text-cyan-200 hover:bg-cyan-300/[0.12]"><Link2 className="size-3.5" />{link.includes("youtube") || link.includes("youtu.be") ? "YouTube" : link.includes("instagram") ? "Instagram" : link.includes("facebook") ? "Facebook" : link.includes("spotify") ? "Spotify" : "Externí odkaz"}</a>)}</div>}
    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-white/8 pt-4 text-sm">
      <span className="w-full text-slate-500 sm:mr-auto sm:w-auto">{ad.author}</span>
      <Button type="button" size="sm" variant="outline" aria-pressed={isRead} onClick={onRead} className="w-full border-white/10 bg-white/[0.035] text-slate-300 hover:bg-white/10 hover:text-white sm:w-auto"><Check className="size-4" />{isRead ? "Přečteno" : "Označit jako přečtené"}</Button>
      <Button type="button" size="sm" variant="outline" aria-pressed={isSaved} onClick={onSave} className={`${isSaved ? "border-amber-300/30 bg-amber-300/10 text-amber-200 hover:bg-amber-300/15" : "border-white/10 bg-white/[0.035] text-slate-300 hover:bg-white/10 hover:text-white"} w-full sm:w-auto`}><Bookmark className="size-4" />{isSaved ? "Uloženo" : "Uložit"}</Button>
      <a className="inline-flex min-h-9 w-full items-center justify-center gap-1.5 px-2 font-semibold text-cyan-300 outline-none hover:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-300 sm:w-auto" href={ad.url} target="_blank" rel="noreferrer">Otevřít inzerát <ArrowUpRight className="size-4" /></a>
    </div>
  </article>;
}

function EmptyState() { return <div className="rounded-2xl border border-dashed border-white/15 px-6 py-14 text-center text-slate-400">Tomuto filtru momentálně neodpovídá žádný inzerát.</div>; }
function matchesFilter(ad: Ad, filter: FilterKey) { if (filter === "prague") return Boolean(ad.isPrague); if (filter === "genres") return Boolean(ad.genres?.length); return Boolean(ad.influences?.length); }

function TopicFilters({ ads, active, onToggle, onClear }: { ads: Ad[]; active: Set<FilterKey>; onToggle: (value: FilterKey) => void; onClear: () => void }) {
  const options: { key: FilterKey; label: string }[] = [{ key: "prague", label: "Praha" }, { key: "genres", label: "Relevantní žánry" }, { key: "bands", label: "Zmíněné kapely" }];
  const count = (key: FilterKey) => ads.filter((ad) => [...active].filter((x) => x !== key).every((x) => matchesFilter(ad, x)) && matchesFilter(ad, key)).length;
  return <div className="flex flex-wrap items-center gap-2"><span className="mr-1 w-full text-sm font-semibold text-slate-400 sm:w-auto">Obsah</span><Button type="button" size="sm" variant="outline" aria-pressed={!active.size} onClick={onClear} className={`min-h-9 rounded-full border-white/10 shadow-none ${!active.size ? "bg-cyan-300 text-slate-950 hover:bg-cyan-300 hover:text-slate-950" : "bg-white/[0.035] text-slate-300"}`}>Vše <span className="text-xs">{ads.length}</span></Button>{options.map(({ key, label }) => <Button key={key} type="button" size="sm" variant="outline" aria-pressed={active.has(key)} onClick={() => onToggle(key)} className={`min-h-9 rounded-full border-white/10 shadow-none ${active.has(key) ? "bg-cyan-300 text-slate-950 hover:bg-cyan-300 hover:text-slate-950" : "bg-white/[0.035] text-slate-300"}`}>{label} <span className="text-xs">{count(key)}</span></Button>)}</div>;
}

function StatusFilters({ value, onChange, counts }: { value: StatusFilter; onChange: (value: StatusFilter) => void; counts: Record<StatusFilter, number> }) {
  const options: { key: StatusFilter; label: string }[] = [{ key: "all", label: "Vše" }, { key: "new", label: "Nové" }, { key: "read", label: "Přečtené" }, { key: "saved", label: "Uložené" }];
  return <div className="flex flex-wrap items-center gap-2"><span className="mr-1 w-full text-sm font-semibold text-slate-400 sm:w-auto">Stav</span>{options.map(({ key, label }) => <Button key={key} type="button" size="sm" variant="outline" aria-pressed={value === key} onClick={() => onChange(key)} className={`min-h-9 rounded-full border-white/10 shadow-none ${value === key ? key === "new" ? "bg-cyan-300 text-slate-950 hover:bg-cyan-300 hover:text-slate-950" : key === "saved" ? "bg-amber-300 text-slate-950 hover:bg-amber-300 hover:text-slate-950" : "bg-white text-slate-950 hover:bg-white hover:text-slate-950" : "bg-white/[0.035] text-slate-300"}`}>{label} <span className="text-xs">{counts[key]}</span></Button>)}</div>;
}

export function Radar({ data }: { data: RadarData }) {
  const [filters, setFilters] = useState<Set<FilterKey>>(() => new Set());
  const [sort, setSort] = useState("newest");
  const [unreadOnly, setUnreadOnly] = useState(true);
  const [status, setStatus] = useState<Record<Section, StatusFilter>>({ singer: "all", interesting: "all" });
  const [readKeys, setReadKeys] = useState<Set<string>>(() => new Set());
  const [savedAds, setSavedAds] = useState<SavedAd[]>([]);
  const [ready, setReady] = useState(false);
  const currentAds = useMemo(() => [...data.singerSeeking, ...data.interesting], [data.singerSeeking, data.interesting]);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(READ_KEY);
      const oldSeen = JSON.parse(window.localStorage.getItem("hudebni-radar-seen-ads-v1") || "[]") as string[];
      const initial = stored ? JSON.parse(stored) as string[] : currentAds.filter((ad) => oldSeen.includes(ad.id)).map(adKey);
      const baseline = initial.length || stored ? initial : currentAds.map(adKey);
      setReadKeys(new Set(baseline)); window.localStorage.setItem(READ_KEY, JSON.stringify(baseline));
      setSavedAds(JSON.parse(window.localStorage.getItem(SAVED_KEY) || "[]"));
    } catch { setReadKeys(new Set(currentAds.map(adKey))); }
    setReady(true);
  }, []);

  const savedMap = useMemo(() => new Map(savedAds.map((item) => [adKey(item.ad), item])), [savedAds]);
  const isRead = (ad: Ad) => readKeys.has(adKey(ad)) || readKeys.has(ad.id);
  const toggleRead = (ad: Ad) => { const next = new Set(readKeys); const key = adKey(ad); if (next.has(key)) next.delete(key); else next.add(key); setReadKeys(next); window.localStorage.setItem(READ_KEY, JSON.stringify([...next])); };
  const toggleSaved = (ad: Ad, section: Section) => { const key = adKey(ad); const sections = (["singer", "interesting"] as Section[]).filter((name) => (name === "singer" ? data.singerSeeking : data.interesting).some((item) => adKey(item) === key)); if (!sections.length) sections.push(section); const next = savedMap.has(key) ? savedAds.filter((item) => adKey(item.ad) !== key) : [...savedAds, { ad, sections }]; setSavedAds(next); window.localStorage.setItem(SAVED_KEY, JSON.stringify(next)); };
  const sectionAds = (section: Section) => { const live = section === "singer" ? data.singerSeeking : data.interesting; const archived = savedAds.filter((x) => x.sections.includes(section)).map((x) => x.ad); const map = new Map(archived.map((ad) => [adKey(ad), ad])); live.forEach((ad) => map.set(adKey(ad), ad)); return [...map.values()]; };
  const counts = (ads: Ad[]): Record<StatusFilter, number> => ({ all: ads.length, new: ready ? ads.filter((ad) => !isRead(ad)).length : 0, read: ads.filter(isRead).length, saved: ads.filter((ad) => savedMap.has(adKey(ad))).length });
  const byStatus = (ads: Ad[], value: StatusFilter) => ads.filter((ad) => value === "all" || value === "new" && !isRead(ad) || value === "read" && isRead(ad) || value === "saved" && savedMap.has(adKey(ad)));
  const singerAll = sectionAds("singer"), interestingAll = sectionAds("interesting");
  const singerBase = unreadOnly ? (ready ? data.singerSeeking.filter((ad) => !isRead(ad)) : []) : byStatus(status.singer === "saved" ? singerAll : data.singerSeeking, status.singer);
  const interestingStatusBase = unreadOnly ? (ready ? data.interesting.filter((ad) => !isRead(ad)) : []) : byStatus(status.interesting === "saved" ? interestingAll : data.interesting, status.interesting);
  const singerShown = [...singerBase].sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  const interestingBase = interestingStatusBase.filter((ad) => [...filters].every((f) => matchesFilter(ad, f)));
  const interestingShown = [...interestingBase].sort(sort === "score" ? (a, b) => b.score - a.score || Date.parse(b.date) - Date.parse(a.date) : (a, b) => Date.parse(b.date) - Date.parse(a.date) || b.score - a.score);
  const newSinger = ready ? data.singerSeeking.filter((ad) => !isRead(ad)).length : 0, newInteresting = ready ? data.interesting.filter((ad) => !isRead(ad)).length : 0;
  const toggleFilter = (filter: FilterKey) => setFilters((current) => { const next = new Set(current); if (next.has(filter)) next.delete(filter); else next.add(filter); return next; });
  const cards = (ads: Ad[], section: Section) => ads.length ? ads.map((ad) => <AdCard key={`${section}-${adKey(ad)}`} ad={ad} isRead={isRead(ad)} isSaved={savedMap.has(adKey(ad))} onRead={() => toggleRead(ad)} onSave={() => toggleSaved(ad, section)} />) : <EmptyState />;

  return <main className="min-h-screen bg-[#070a10] text-slate-100"><div className="radar-glow pointer-events-none fixed inset-0" /><div className="relative mx-auto max-w-6xl px-4 pb-20 pt-8 sm:px-6 sm:pt-12">
    <header className="mb-9 flex flex-col gap-6 border-b border-white/10 pb-8 md:flex-row md:items-end md:justify-between"><div><h1 className="text-4xl font-bold tracking-[-0.04em] text-white sm:text-6xl">Hudební radar<span className="text-cyan-300">.</span></h1><p className="mt-3 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">Zajímaví lidé a vznikající projekty z Hudebního bazaru — pro hledání zpěvu, networking a objevování nové hudby.</p>{ready && newSinger + newInteresting > 0 && <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1.5 text-sm font-bold text-cyan-200"><Sparkles className="size-4" />{newSinger + newInteresting} nových inzerátů</div>}</div><div className="shrink-0 text-sm leading-6 text-slate-500"><span className="block font-semibold text-slate-300">Poslední kontrola</span>{checkedAt.format(new Date(data.updatedAt))} · okno {data.windowDays} dní</div></header>
    <div className="mb-5 flex items-center justify-between gap-4 rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.06] px-4 py-3"><label htmlFor="unread-only" className="cursor-pointer"><span className="block font-semibold text-white">Pouze nové inzeráty</span><span className="mt-0.5 block text-sm text-slate-400">Skrýt všechno, co už bylo označeno jako přečtené</span></label><Switch id="unread-only" checked={unreadOnly} onCheckedChange={setUnreadOnly} aria-label="Zobrazovat pouze nové inzeráty" className="data-[state=checked]:bg-cyan-300" /></div>
    <Tabs defaultValue="singer" className="gap-6"><TabsList className="!flex !h-auto w-full flex-col items-stretch gap-2 overflow-visible rounded-xl border border-white/10 bg-white/[0.04] p-1.5 sm:w-fit sm:flex-row sm:items-center"><TabsTrigger value="singer" className="!h-auto min-h-11 w-full flex-none justify-between gap-2 whitespace-normal rounded-lg px-4 py-2 text-left text-sm leading-tight sm:w-auto data-[state=active]:bg-cyan-300 data-[state=active]:text-slate-950">Zpěv hledá <span className="ml-auto rounded-full bg-black/10 px-2 py-0.5 text-xs">{unreadOnly ? newSinger : data.singerSeeking.length}</span>{!unreadOnly && newSinger > 0 && <span className="text-xs font-bold">+{newSinger} nové</span>}</TabsTrigger><TabsTrigger value="interesting" className="!h-auto min-h-11 w-full flex-none justify-between gap-2 whitespace-normal rounded-lg px-4 py-2 text-left text-sm leading-tight sm:w-auto data-[state=active]:bg-cyan-300 data-[state=active]:text-slate-950">Obecně zajímavé <span className="ml-auto rounded-full bg-black/10 px-2 py-0.5 text-xs">{unreadOnly ? newInteresting : data.interesting.length}</span>{!unreadOnly && newInteresting > 0 && <span className="text-xs font-bold">+{newInteresting} nové</span>}</TabsTrigger></TabsList>
      <TabsContent value="singer" className="space-y-4"><div className="mb-5"><h2 className="text-2xl font-semibold tracking-tight text-white">Zpěv hledá kapelu nebo projekt</h2><p className="mt-1 text-slate-400">Pouze Praha a Středočeský kraj; bez coverů, tribute a zábavových kapel.</p></div>{!unreadOnly && <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.025] p-4"><StatusFilters value={status.singer} onChange={(value) => setStatus((s) => ({ ...s, singer: value }))} counts={counts(singerAll)} /></div>}{cards(singerShown, "singer")}</TabsContent>
      <TabsContent value="interesting" className="space-y-4"><div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between"><div><h2 className="text-2xl font-semibold tracking-tight text-white">Obecně zajímavé inzeráty</h2><p className="mt-1 text-slate-400">Moderní rock a metal, vlastní tvorba a nové projekty vhodné ke sledování, propojení nebo podpoře.</p></div><div className="shrink-0"><label className="mb-1.5 block text-sm font-semibold text-slate-400">Řazení</label><Select value={sort} onValueChange={setSort}><SelectTrigger className="min-w-44 border-white/10 bg-white/[0.035] text-slate-200"><SelectValue /></SelectTrigger><SelectContent className="border-white/10 bg-[#111821] text-slate-100"><SelectItem value="newest">Nejnovější</SelectItem><SelectItem value="score">Nejvyšší shoda</SelectItem></SelectContent></Select></div></div><div className="mb-6 space-y-3 rounded-2xl border border-white/10 bg-white/[0.025] p-4">{!unreadOnly && <StatusFilters value={status.interesting} onChange={(value) => setStatus((s) => ({ ...s, interesting: value }))} counts={counts(interestingAll)} />}<TopicFilters ads={unreadOnly ? interestingStatusBase : status.interesting === "saved" ? interestingAll : data.interesting} active={filters} onToggle={toggleFilter} onClear={() => setFilters(new Set())} /></div>{cards(interestingShown, "interesting")}</TabsContent>
    </Tabs></div></main>;
}
