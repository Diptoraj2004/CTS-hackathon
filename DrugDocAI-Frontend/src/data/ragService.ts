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
}

export interface RagBulletItem {
  label?: string;
  text: string;
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
  confidence: "High" | "Medium" | "Low" | "low" | "high";
  confidenceDetail: string;
  sources: RagSource[];
  requestId?: string | null;
}

const DISCLAIMER =
  "This information is from official medical sources and is not a substitute for professional medical advice.";

function sessionId(): string {
  const key = "drugdoc_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(key, id);
  }
  return id;
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
  }));
}

export async function getRagResponse(
  question: string,
  medication: string,
  mode: "patient" | "professional"
): Promise<RagResponse> {
  const backendMode = mode === "professional" ? "clinician" : "patient";

  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId(), query: question, mode: backendMode }),
  });

  if (!res.ok) {
    // blocked query (injection / malformed) or server error
    return {
      question,
      medication,
      mode,
      risk_level: "normal",
      answerLead: "This question couldn't be processed.",
      bulletPoints: [],
      answerFollowUp: "Please rephrase your question and try again.",
      disclaimer: DISCLAIMER,
      confidence: "Low",
      confidenceDetail: "Request was rejected before an answer could be generated.",
      sources: [],
      requestId: null,
    };
  }

  const data = await res.json();

  if (data.status === "ESCALATED") {
    // Mode-mismatch / category-gate reasons read as "high risk" in the UI;
    // a plain insufficient-evidence escalation reads as "low confidence".
    const reason: string = data.reason || "";
    const isHighRisk =
      /clinician-level|high-risk|mode mismatch/i.test(reason);

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
    };
  }

  // APPROVED
  return {
    question,
    medication,
    mode,
    risk_level: "low",
    answerLead: data.answer || "",
    bulletPoints: [],
    answerFollowUp: "",
    disclaimer: DISCLAIMER,
    confidence: confidenceBucket(data.confidence ?? 0),
    confidenceDetail: "Based on the documents in the uploaded knowledge base.",
    sources: mapSources(data.citations),
    requestId: null,
  };
}
