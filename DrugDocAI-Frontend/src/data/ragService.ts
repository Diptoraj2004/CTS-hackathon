// ── Structured Mock RAG Service ───────────────────────────────────────────────
// Separates response data, risk classification, and RAG simulation logic from UI components.
// Ready to be swapped with the real RAG API endpoint later.

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
}

export function isHighRiskQuestion(question: string, explicitRisk?: string | null): boolean {
  if (explicitRisk === "high" || explicitRisk === "true") return true;
  const q = (question || "").toLowerCase();
  return (
    q.includes("twice my prescribed dose") ||
    q.includes("double dose") ||
    q.includes("overdose") ||
    q.includes("accidentally took") ||
    q.includes("took too much") ||
    q.includes("swallowed whole") ||
    q.includes("poison") ||
    q.includes("emergency")
  );
}

export function isLowConfidenceQuestion(
  question: string,
  explicitConfidence?: string | null
): boolean {
  if (explicitConfidence === "low" || explicitConfidence === "true") return true;
  const q = (question || "").toLowerCase();
  return (
    q.includes("ibuprofen") ||
    q.includes("can i take") ||
    q.includes("can it interact") ||
    q.includes("interact with other") ||
    q.includes("interaction") ||
    q.includes("low confidence") ||
    q.includes("combination") ||
    q.includes("mix with")
  );
}

export function getMockRagResponse(
  question: string,
  medication: string,
  mode: "patient" | "professional",
  explicitRisk?: string | null,
  explicitConfidence?: string | null
): RagResponse {
  const med = medication || "Amoxicillin";
  const isHighRisk = isHighRiskQuestion(question, explicitRisk);

  if (isHighRisk) {
    return {
      question:
        question || "I accidentally took twice my prescribed dose. What should I do?",
      medication: med,
      mode,
      risk_level: "high",
      answerLead:
        "This appears to be a potentially serious situation that may require personalized medical evaluation. DrugDoc AI cannot provide specific medical advice for this type of question.",
      bulletPoints: [],
      answerFollowUp:
        "Please consult a healthcare professional, contact a poison control center, or seek immediate medical attention, depending on the severity of the situation.",
      disclaimer:
        "This information is from official medical sources and is not a substitute for professional medical advice.",
      confidence: "High",
      confidenceDetail: "Escalation protocol triggered based on safety guidelines.",
      sources: [
        { id: 1, name: `FDA Drug Label (${med})` },
        { id: 2, name: "EMA Product Information" },
        { id: 3, name: "MedlinePlus (NIH)" },
      ],
    };
  }

  const isLowConfidence = isLowConfidenceQuestion(question, explicitConfidence);

  if (isLowConfidence) {
    return {
      question: question || `Can I take ${med.toLowerCase()} with ibuprofen?`,
      medication: med,
      mode,
      risk_level: "normal",
      confidence: "Low",
      confidenceDetail: "Insufficient reliable documentation found in official sources.",
      answerLead:
        "DrugDoc AI could not find enough reliable, consistent information from official medical sources to provide a confident answer to this question.",
      bulletPoints: [],
      answerFollowUp:
        "This topic may require further review or consultation with a healthcare professional. You can explore related documentation or try rephrasing your question.",
      disclaimer:
        "This information is from official medical sources and is not a substitute for professional medical advice.",
      sources: [
        { id: 1, name: `FDA Drug Label (${med})` },
        { id: 2, name: "EMA Product Information" },
        { id: 3, name: "MedlinePlus (NIH)" },
      ],
    };
  }

  const qLower = (question || "").toLowerCase();

  // Default side-effects / reference response
  const isSideEffects =
    qLower.includes("side effect") ||
    qLower.includes("adverse") ||
    qLower.includes("reaction") ||
    qLower.length === 0;

  if (isSideEffects) {
    return {
      question: question || `What are the common side effects of ${med}?`,
      medication: med,
      mode,
      risk_level: "low",
      answerLead: `${med} is generally well tolerated, but like all medications, it can cause side effects. The most common side effects include:`,
      bulletPoints: [
        {
          label: "Gastrointestinal symptoms:",
          text: "nausea, vomiting, diarrhoea, and abdominal discomfort",
        },
        {
          label: "Skin reactions:",
          text: "rash (usually mild and non-serious)",
        },
        {
          label: "Headache",
          text: "",
        },
        {
          label: "Changes in taste",
          text: "",
        },
        {
          label: "Yeast infections",
          text: "(e.g., oral or vaginal candidiasis), due to disruption of normal gut flora",
        },
      ],
      answerFollowUp:
        "These side effects are usually mild and temporary. If you experience a severe rash, persistent diarrhoea, or signs of an allergic reaction (such as difficulty breathing, swelling, or hives), seek medical attention immediately.",
      disclaimer:
        "This information is from official medical sources and is not a substitute for professional medical advice.",
      confidence: "High",
      confidenceDetail: "Based on available official documentation.",
      sources: [
        { id: 1, name: `FDA Drug Label (${med})` },
        { id: 2, name: "EMA Product Information" },
        { id: 3, name: "MedlinePlus (NIH)" },
      ],
    };
  }

  // Fallback / generalized medical response
  return {
    question,
    medication: med,
    mode,
    risk_level: "low",
    answerLead: `Based on official clinical documentation for ${med}, here is the relevant guidance:`,
    bulletPoints: [
      {
        label: "Primary Indication & Usage:",
        text: `Consult verified prescribing information for approved dosages and indications of ${med}.`,
      },
      {
        label: "Precautions:",
        text: "Monitor for unexpected physiological changes or contraindications.",
      },
      {
        label: "Administration:",
        text: "Take strictly as prescribed by a licensed healthcare professional.",
      },
    ],
    answerFollowUp: `Always verify treatment plans with your prescribing healthcare provider or clinical pharmacist.`,
    disclaimer:
      "This information is from official medical sources and is not a substitute for professional medical advice.",
    confidence: "High",
    confidenceDetail: "Based on available official documentation.",
    sources: [
      { id: 1, name: `FDA Drug Label (${med})` },
      { id: 2, name: "EMA Product Information" },
      { id: 3, name: "MedlinePlus (NIH)" },
    ],
  };
}

