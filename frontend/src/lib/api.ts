export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Language = "uz" | "ru";

export type EvidenceItem = { label: string; value: string };

export type AskResponse = {
  question: string;
  language: Language;
  found: boolean;
  answer: string;
  confidence: number;
  intent: string;
  reasoning_summary: string;
  sql: string | null;
  evidence: EvidenceItem[];
  sources: string[];
  rows: Record<string, unknown>[];
  execution_ms: number;
  verification: { passed: boolean; method: string; notes: string[] };
  cached: boolean;
};

export async function askQuestion(question: string, language: Language | null) {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, language }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as AskResponse;
}

export async function fetchStats() {
  const res = await fetch(`${API_URL}/stats`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<{
    stats: Record<string, unknown>;
    suggested_questions: Record<Language, string[]>;
  }>;
}

export async function fetchHealth() {
  const res = await fetch(`${API_URL}/health`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json() as Promise<{
    status: string;
    database_ready: boolean;
    llm_sql_enabled: boolean;
    stats: Record<string, unknown>;
  }>;
}
