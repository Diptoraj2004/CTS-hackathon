// ── Real RAG Service ────────────────────────────────────────────────────────
// Calls the actual FastAPI backend (/query) and maps its response into the
// same RagResponse shape the UI already consumes, so the page components
// below don't need to change.

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export interface RagSource {
  id: number;
  name: string;
  type?: string;
  url?: string;
  // Raw citation fields from the backend — used by SourcesEvidence
  doc?: string;
  section?: string;
  page?: number | string | null;
  chunk_id?: string;
  source?: string;
}

export interface RagBulletItem {
  label?: string;
  text: string;
}

export interface RagQualityMetrics {
  retrieval_precision?: number | null;
  answer_correctness?: number | null;
  citation_accuracy?: number | null;
  estimated?: boolean;
  methodology?: string;
}

export interface RagResponse {
  question: string;
  medication: string;
  mode: "patient" | "professional";
  risk_level: "low" | "medium" | "high" | "normal";
  answerLead: string;
  bulletPoints: RagBulletItem[];
  answerFollowUp: string;
  disclaimer: string;
  confidence: "High" | "Medium" | "Low" | "low" | "medium" | "high";
  confidenceDetail: string;
  sources: RagSource[];
  requestId?: string | null;
  intent?: string | null;
  intentConfidence?: number | null;
  retrievalUsed?: boolean;
  historyUsed?: boolean;
  faersUsed?: boolean;
  qualityMetrics?: RagQualityMetrics;
}

const DISCLAIMER =
  "This information is from official medical sources and is not a substitute for professional medical advice.";

// crypto.randomUUID() only exists in "secure contexts" (HTTPS or localhost).
// A demo served over plain HTTP on a LAN (a common "point a laptop at it"
// setup) throws here on every single call, breaking every query. This
// fallback is not cryptographically strong, which is fine — it's a
// throwaway per-tab session key, not a security token.
function makeUuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    try {
      return crypto.randomUUID();
    } catch {
      // fall through to the manual version below (insecure-context throw)
    }
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getSessionId(): string {
  const key = "drugdoc_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = makeUuid();
    sessionStorage.setItem(key, id);
  }
  return id;
}

export function setSessionId(newId: string): void {
  const key = "drugdoc_session_id";
  sessionStorage.setItem(key, newId);
}


function confidenceBucket(score: number): "High" | "Medium" | "Low" {
  if (score >= 0.75) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

// Backend citation -> frontend source
function mapSources(citations: any[]): RagSource[] {
  return (citations || []).map((c, i) => ({
    id: i + 1,
    name: c.page ? `${c.doc} — ${c.section}, p.${c.page}` : `${c.doc} — ${c.section}`,
    doc: c.doc,
    section: c.section,
    page: c.page ?? null,
    chunk_id: c.chunk_id,
    url: c.url || (c.doc ? `${API_BASE}/documents/${encodeURIComponent(c.doc)}/view` : undefined),
    type: c.source,
  }));
}

// ── Citation persistence (sessionStorage) ────────────────────────────────────
// SourcesEvidence reads this to display real RAG citations without a
// second network request. Key is scoped by drug+mode so switching drugs
// does not show stale citations from a previous query.
const SOURCES_KEY_PREFIX = "drugdoc_last_sources";

export function saveRagSources(
  drug: string,
  mode: string,
  sources: RagSource[]
): void {
  try {
    const key = `${SOURCES_KEY_PREFIX}:${drug.toLowerCase()}:${mode}`;
    sessionStorage.setItem(key, JSON.stringify(sources));
  } catch {
    // sessionStorage can throw in private/restricted contexts — ignore silently.
  }
}

export function loadRagSources(
  drug: string,
  mode: string
): RagSource[] | null {
  try {
    const key = `${SOURCES_KEY_PREFIX}:${drug.toLowerCase()}:${mode}`;
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    return JSON.parse(raw) as RagSource[];
  } catch {
    return null;
  }
}

// The backend returns "- bullet" lines and inline "[n]" citation markers as
// plain text with real newlines. Split into a lead paragraph plus a bullet
// list so the UI can render an actual <ul> instead of one flattened <p>
// where every bullet and newline has collapsed into a single line.
function splitAnswer(text: string): { lead: string; bullets: RagBulletItem[] } {
  if (!text) return { lead: "", bullets: [] };
  const lines = text.split(/\r?\n/);
  const leadLines: string[] = [];
  const bulletLines: string[] = [];
  let inBullets = false;

  for (const raw of lines) {
    const trimmed = raw.trim();
    if (/^[-*]\s+/.test(trimmed)) {
      inBullets = true;
      bulletLines.push(trimmed.replace(/^[-*]\s+/, ""));
    } else if (trimmed === "") {
      continue; // blank lines are just paragraph/list separators
    } else if (!inBullets) {
      leadLines.push(trimmed);
    } else {
      // a continuation line wrapped under the previous bullet
      if (bulletLines.length > 0) {
        bulletLines[bulletLines.length - 1] += " " + trimmed;
      } else {
        leadLines.push(trimmed);
      }
    }
  }

  return {
    lead: leadLines.join(" ").trim(),
    bullets: bulletLines.map((t) => ({ text: t })),
  };
}

function networkErrorResponse(question: string, medication: string, mode: "patient" | "professional"): RagResponse {
  return {
    question,
    medication,
    mode,
    risk_level: "normal",
    answerLead: "DrugDoc AI couldn't reach the server.",
    bulletPoints: [],
    answerFollowUp: "Check your connection (or the backend URL, if you're running this against a tunnel) and try again.",
    disclaimer: DISCLAIMER,
    confidence: "Low",
    confidenceDetail: "No response was received from the server.",
    sources: [],
    requestId: null,
  };
}

export async function getRagResponse(
  question: string,
  medication: string,
  mode: "patient" | "professional"
): Promise<RagResponse> {
  const backendMode = mode === "professional" ? "clinician" : "patient";

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: getSessionId(),
        query: question,
        mode: backendMode,
        // Previously never sent — the selected drug (from the medication
        // dropdown) was silently discarded, so retrieval relied entirely on
        // the drug name being spelled out inside the question text itself.
        drug_name: medication || undefined,
      }),
    });
  } catch {
    // fetch() itself throws on a network failure (DNS, refused connection,
    // dead tunnel) — this was completely unhandled before, an unguarded
    // throw straight out of this function into the caller.
    return networkErrorResponse(question, medication, mode);
  }

  if (!res.ok) {
    // Previously every non-OK response (429 rate-limited, 422 corpus safety
    // failure, 500/503 server error) rendered the exact same generic
    // "please rephrase" message, which is actively misleading for a rate
    // limit or a server outage — neither is fixed by rephrasing.
    let lead = "This question couldn't be processed.";
    let followUp = "Please rephrase your question and try again.";
    if (res.status === 400) {
      lead = "This request was blocked by the prompt-injection safety layer.";
      followUp = "Please submit a medication question instead of an instruction to change the assistant's operating rules.";
    } else if (res.status === 429) {
      lead = "Too many questions at once.";
      followUp = "Please wait a moment before asking another question.";
    } else if (res.status === 422) {
      lead = "A source document failed a safety check.";
      followUp = "This has been logged. Try a different question, or contact an administrator.";
    } else if (res.status >= 500) {
      lead = "DrugDoc AI hit an error answering this.";
      followUp = "The answer service is temporarily unavailable. Please try again shortly.";
    }
    return {
      question,
      medication,
      mode,
      risk_level: "normal",
      answerLead: lead,
      bulletPoints: [],
      answerFollowUp: followUp,
      disclaimer: DISCLAIMER,
      confidence: "Low",
      confidenceDetail: `Request was rejected before an answer could be generated (status ${res.status}).`,
      sources: [],
      requestId: null,
    };
  }

  const data = await res.json();

  if (data.status === "ESCALATED") {
    if (data.reason === "PROMPT_INJECTION" || data.reason === "CORPUS_INJECTION") {
      return {
        question, medication, mode, risk_level: "high", confidence: "Low",
        confidenceDetail: "Prompt-injection safety policy blocked this request.",
        answerLead: data.answer || "This request was blocked by the prompt-injection safety layer.",
        bulletPoints: [], answerFollowUp: "Please submit a medication question instead of an instruction to change the assistant's operating rules.",
        disclaimer: DISCLAIMER, sources: [], requestId: null,
        intent: data.intent ?? data.reason, intentConfidence: data.intent_confidence ?? 1,
        retrievalUsed: false, historyUsed: false, faersUsed: false,
        qualityMetrics: data.quality_metrics ?? undefined,
      };
    }
    // risk_level now comes straight from the backend (see backend/main.py's
    // _escalate) instead of regex-matching the human-readable reason text,
    // which never actually contained the words the old regex looked for.
    const isHighRisk = data.risk_level === "high";
    const reason: string = data.reason || "";

    return {
      question,
      medication,
      mode,
      risk_level: isHighRisk ? "high" : "normal",
      confidence: isHighRisk ? "High" : "Low",
      confidenceDetail: isHighRisk
        ? "Escalation protocol triggered based on safety guidelines."
        : "Insufficient reliable documentation found in the uploaded sources.",
      answerLead: isHighRisk
        ? "This appears to be a potentially serious situation that may require personalized medical evaluation. DrugDoc AI cannot provide specific medical advice for this type of question."
        : "DrugDoc AI could not find enough reliable, consistent information from the uploaded documents to provide a confident answer.",
      bulletPoints: [],
      answerFollowUp: reason || "This question has been flagged for human review.",
      disclaimer: DISCLAIMER,
      sources: [],
      requestId: data.request_id ?? null,
      intent: data.intent ?? null,
      intentConfidence: data.intent_confidence ?? null,
      retrievalUsed: data.retrieval_used ?? false,
      historyUsed: data.history_used ?? false,
      faersUsed: data.faers_used ?? false,
      qualityMetrics: data.quality_metrics ?? undefined,
    };
  }

  // APPROVED
  const { lead, bullets } = splitAnswer(data.answer || "");
  const sources = mapSources(data.citations);
  // Persist citations so SourcesEvidence can display them without re-querying.
  if (sources.length > 0) {
    saveRagSources(medication, mode, sources);
  }
  return {
    question,
    medication,
    mode,
    risk_level: "low",
    answerLead: lead || data.answer || "",
    bulletPoints: bullets,
    answerFollowUp: "",
    disclaimer: DISCLAIMER,
    confidence: data.confidence_bucket
      ? data.confidence_bucket
      : confidenceBucket(data.confidence ?? 0),
    confidenceDetail: "Based on the documents in the uploaded knowledge base.",
    sources,
    requestId: null,
    intent: data.intent ?? null,
    intentConfidence: data.intent_confidence ?? null,
    retrievalUsed: data.retrieval_used ?? true,
    historyUsed: data.history_used ?? false,
    faersUsed: data.faers_used ?? false,
    qualityMetrics: data.quality_metrics ?? undefined,
  };
}

export interface DrugProfileResponse {
  drug: string;
  class?: string;
  uses?: string[];
  forms?: string[];
  dosage?: string[];
  sideEffects?: string[];
  interactions?: string[];
  warnings?: string[];
}

const drugProfileCache = new Map<
  string,
  Promise<DrugProfileResponse | null>
>();

export function getDrugProfile(
  drug: string
): Promise<DrugProfileResponse | null> {
  const normalizedDrug = drug.trim().toLowerCase();

  if (!normalizedDrug) {
    return Promise.resolve(null);
  }

  const cached = drugProfileCache.get(normalizedDrug);
  if (cached) {
    return cached;
  }

  const request = fetch(`${API_BASE}/api/drug-profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ drug: normalizedDrug }),
  })
    .then(async (res) => {
      if (!res.ok) return null;
      return await res.json();
    })
    .catch(() => null);

  drugProfileCache.set(normalizedDrug, request);
  return request;
}

export interface ContextStatus {
  session_id: string;
  estimated_tokens: number;
  context_limit: number;
  response_reserve: number;
  remaining_tokens: number;
  warning_threshold: number;
  near_limit: boolean;
  message_count: number;
}

export interface SessionRollover {
  old_session_id: string;
  new_session_id: string;
  summary: string;
  prompt_to_send: string;
  status: "ROLLED_OVER";
}

export async function getContextStatus(
  sId?: string
): Promise<ContextStatus | null> {
  const id = sId || getSessionId();
  try {
    const res = await fetch(
      `${API_BASE}/session/${encodeURIComponent(id)}/context-status`
    );
    if (!res.ok) return null;
    return (await res.json()) as ContextStatus;
  } catch {
    return null;
  }
}

export async function rolloverSession(
  sId?: string
): Promise<SessionRollover | null> {
  const id = sId || getSessionId();
  try {
    const res = await fetch(
      `${API_BASE}/session/${encodeURIComponent(id)}/rollover`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }
    );
    if (!res.ok) return null;
    const data = (await res.json()) as SessionRollover;
    if (data && data.new_session_id) {
      setSessionId(data.new_session_id);
    }
    return data;
  } catch {
    return null;
  }
}

