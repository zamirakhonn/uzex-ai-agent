"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Clock3,
  Copy,
  Database,
  Download,
  Languages,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  API_URL,
  AskResponse,
  Language,
  fetchHealth,
  fetchStats,
  askQuestion,
} from "@/lib/api";

const FALLBACK_SUGGEST: Record<Language, string[]> = {
  uz: [
    "2025 yilda nechta bitim tuzilgan?",
    "Eng katta bitim qaysi?",
    "ABC kompaniyasi qancha bitim qilgan?",
  ],
  ru: [
    "Сколько сделок было в 2025 году?",
    "Какая самая крупная сделка?",
    "Сколько сделок было в январе 2024 года?",
  ],
};

export default function HomePage() {
  const [lang, setLang] = useState<Language | "auto">("auto");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<AskResponse[]>([]);
  const [health, setHealth] = useState<string>("checking");
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [suggest, setSuggest] = useState(FALLBACK_SUGGEST);
  const [showSql, setShowSql] = useState(false);

  useEffect(() => {
    fetchHealth()
      .then((h) => setHealth(h.database_ready ? "ready" : h.status))
      .catch(() => setHealth("offline"));
    fetchStats()
      .then((s) => {
        setStats(s.stats);
        setSuggest(s.suggested_questions);
      })
      .catch(() => undefined);
  }, []);

  const uiLang: Language = lang === "ru" || result?.language === "ru" ? "ru" : "uz";

  async function submit(question: string) {
    const text = question.trim();
    if (!text) return;
    setLoading(true);
    setError(null);
    setQ(text);
    try {
      const data = await askQuestion(text, lang === "auto" ? null : lang);
      setResult(data);
      setHistory((prev) => [data, ...prev.filter((x) => x.question !== data.question)].slice(0, 12));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const copy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.answer);
  };

  const exportJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "uzex-answer.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const years = useMemo(() => {
    const raw = stats?.by_year;
    return Array.isArray(raw) ? (raw as { year: number; deals: number }[]) : [];
  }, [stats]);

  return (
    <div className="grid-fade min-h-screen">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 md:px-8">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-emerald-300/80">UZEX AI Hackathon</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight md:text-4xl">
              UZEX <span className="text-amber-300">Insight</span>
            </h1>
            <p className="mt-2 max-w-xl text-sm text-slate-400">
              Savollarga javob faqat datasetdan. Taxmin yo‘q. Har bir raqam — bitim, shartnoma yoki kurs
              qatori.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill health={health} />
            <LangSwitch value={lang} onChange={setLang} />
          </div>
        </header>

        <section className="glass rounded-3xl p-4 shadow-2xl shadow-black/40 md:p-6">
          <form
            className="flex flex-col gap-3 md:flex-row"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(q);
            }}
          >
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={uiLang === "ru" ? "Спросите о сделках UZEX…" : "UZEX bitimlari haqida so‘rang…"}
                className="h-14 w-full rounded-2xl border border-white/10 bg-black/30 pl-12 pr-4 text-base outline-none ring-emerald-300/0 transition focus:border-emerald-400/40 focus:ring-4 focus:ring-emerald-400/10"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="h-14 rounded-2xl bg-gradient-to-r from-emerald-400 to-teal-300 px-7 text-sm font-semibold text-slate-950 transition hover:brightness-110 disabled:opacity-60"
            >
              {loading ? "…" : uiLang === "ru" ? "Спросить" : "So‘rash"}
            </button>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            {(suggest[uiLang] || []).map((item) => (
              <button
                key={item}
                onClick={() => void submit(item)}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition hover:border-amber-300/40 hover:text-white"
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <main className="space-y-4">
            {error && (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
                {error}. API: {API_URL}
              </div>
            )}
            {loading && <LoadingCard />}
            {result && !loading && (
              <article className="glass overflow-hidden rounded-3xl">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
                  <div className="flex items-center gap-2 text-sm text-slate-400">
                    <Sparkles className="h-4 w-4 text-amber-300" />
                    {result.question}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge>{result.language.toUpperCase()}</Badge>
                    <Badge tone={result.found ? "ok" : "warn"}>{result.found ? "grounded" : "not found"}</Badge>
                    <button onClick={copy} className="rounded-lg p-2 hover:bg-white/5" title="Copy">
                      <Copy className="h-4 w-4" />
                    </button>
                    <button onClick={exportJson} className="rounded-lg p-2 hover:bg-white/5" title="Export">
                      <Download className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <div className="space-y-5 p-5 md:p-6">
                  <section>
                    <h2 className="text-xs uppercase tracking-widest text-slate-500">
                      {uiLang === "ru" ? "Ответ" : "Javob"}
                    </h2>
                    <p className="mt-2 whitespace-pre-wrap text-lg leading-relaxed text-slate-100">
                      {result.answer}
                    </p>
                  </section>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Meter label="Confidence" value={Math.round(result.confidence * 100)} />
                    <Info icon={<Clock3 className="h-4 w-4" />} label="Time" value={`${result.execution_ms} ms`} />
                    <Info icon={<Activity className="h-4 w-4" />} label="Intent" value={result.intent} />
                  </div>
                  {result.evidence.length > 0 && (
                    <section>
                      <h3 className="text-xs uppercase tracking-widest text-slate-500">
                        {uiLang === "ru" ? "Доказательства" : "Dalillar"}
                      </h3>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {result.evidence.map((e) => (
                          <div key={e.label} className="rounded-xl border border-white/10 bg-black/20 p-3">
                            <div className="text-[11px] uppercase tracking-wide text-slate-500">{e.label}</div>
                            <div className="mt-1 text-sm text-slate-100">{e.value}</div>
                          </div>
                        ))}
                      </div>
                    </section>
                  )}
                  <section className="flex flex-wrap gap-2 text-xs text-slate-400">
                    <Database className="h-4 w-4" />
                    {(result.sources.length ? result.sources : ["dataset"]).map((s) => (
                      <span key={s} className="rounded-full bg-white/5 px-2 py-1">
                        {s}
                      </span>
                    ))}
                    {result.cached && <span className="rounded-full bg-amber-300/10 px-2 py-1 text-amber-200">cached</span>}
                  </section>
                  <section className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-300">
                    <div className="mb-2 flex items-center gap-2 text-emerald-300">
                      <ShieldCheck className="h-4 w-4" />
                      {result.verification.method}
                    </div>
                    {result.reasoning_summary}
                    {result.sql && (
                      <div className="mt-3">
                        <button className="text-xs text-amber-200" onClick={() => setShowSql((v) => !v)}>
                          {showSql ? "Hide SQL" : "Show SQL"}
                        </button>
                        {showSql && (
                          <pre className="mt-2 overflow-x-auto rounded-xl bg-black/40 p-3 text-[11px] text-emerald-100">
                            {result.sql}
                          </pre>
                        )}
                      </div>
                    )}
                  </section>
                </div>
              </article>
            )}
            {!result && !loading && (
              <div className="glass rounded-3xl p-10 text-center text-slate-400">
                <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-300" />
                Datasetdan tashqari hech narsa aytilmaydi. Savol bering — 90 soniya ichida dalilli javob.
              </div>
            )}
          </main>

          <aside className="space-y-4">
            <div className="glass rounded-3xl p-5">
              <h3 className="text-sm font-medium text-slate-200">Dataset</h3>
              <dl className="mt-3 space-y-2 text-sm">
                <Row k="Bitimlar" v={String(stats?.deals ?? "—")} />
                <Row k="Shartnomalar" v={String(stats?.contracts ?? "—")} />
                <Row k="Ishtirokchilar" v={String(stats?.participants ?? "—")} />
                <Row k="Brokerlar" v={String(stats?.brokers ?? "—")} />
                <Row k="Davr" v={`${fmt(stats?.min_date)} → ${fmt(stats?.max_date)}`} />
              </dl>
              <div className="mt-4 space-y-1">
                {years.map((y) => (
                  <div key={y.year} className="flex items-center gap-2 text-xs text-slate-400">
                    <span className="w-10">{y.year}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-emerald-300"
                        style={{ width: `${Math.min(100, (y.deals / 120000) * 100)}%` }}
                      />
                    </div>
                    <span className="w-16 text-right">{y.deals.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="glass rounded-3xl p-5">
              <h3 className="text-sm font-medium text-slate-200">Tarix</h3>
              <ul className="mt-3 space-y-2">
                {history.length === 0 && <li className="text-xs text-slate-500">Hali savol yo‘q</li>}
                {history.map((h) => (
                  <li key={h.question}>
                    <button
                      onClick={() => void submit(h.question)}
                      className="w-full rounded-xl px-2 py-2 text-left text-xs text-slate-300 hover:bg-white/5"
                    >
                      {h.question}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function fmt(v: unknown) {
  if (!v) return "—";
  return String(v).slice(0, 10);
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium text-slate-100">{v}</dd>
    </div>
  );
}

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "ok" | "warn" }) {
  const cls =
    tone === "ok"
      ? "bg-emerald-400/15 text-emerald-200"
      : tone === "warn"
        ? "bg-amber-400/15 text-amber-200"
        : "bg-white/10 text-slate-300";
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${cls}`}>{children}</span>;
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}%</div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-gradient-to-r from-amber-300 to-emerald-300" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function Info({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wide text-slate-500">
        {icon}
        {label}
      </div>
      <div className="mt-1 truncate text-lg font-medium">{value}</div>
    </div>
  );
}

function StatusPill({ health }: { health: string }) {
  const on = health === "ready" || health === "ok";
  return (
    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-xs">
      <span className={`h-2 w-2 rounded-full ${on ? "bg-emerald-400" : "bg-amber-400"}`} />
      {on ? "DuckDB ready" : health}
    </div>
  );
}

function LangSwitch({
  value,
  onChange,
}: {
  value: Language | "auto";
  onChange: (v: Language | "auto") => void;
}) {
  return (
    <div className="flex items-center gap-1 rounded-full border border-white/10 bg-black/30 p-1 text-xs">
      <Languages className="ml-2 h-3.5 w-3.5 text-slate-400" />
      {(["auto", "uz", "ru"] as const).map((k) => (
        <button
          key={k}
          onClick={() => onChange(k)}
          className={`rounded-full px-2.5 py-1 ${value === k ? "bg-white/10 text-white" : "text-slate-400"}`}
        >
          {k}
        </button>
      ))}
    </div>
  );
}

function LoadingCard() {
  return (
    <div className="glass rounded-3xl p-6">
      <div className="h-2 w-40 animate-pulse rounded bg-white/10" />
      <div className="mt-4 space-y-2">
        <div className="h-4 w-full animate-pulse rounded bg-white/10" />
        <div className="h-4 w-4/5 animate-pulse rounded bg-white/10" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-white/10" />
      </div>
    </div>
  );
}
