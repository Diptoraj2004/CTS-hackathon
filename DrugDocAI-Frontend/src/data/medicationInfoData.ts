// ─────────────────────────────────────────────────────────────────────────────
// Medication Information Data Definition (MedicationInfo / /medication-info)
// Designed for seamless future backend API integration.
// ─────────────────────────────────────────────────────────────────────────────

export interface SourceReference {
  id: number;
  name: string;
  documentId?: string;
}

export interface MedicationInfoDetails {
  medicationId: string;
  name: string;
  description: string;
  drugClass: string;
  overview: string;
  uses: string[];
  availableForms: string[];
  formsNote?: string;
  dosageInformation: string[];
  commonSideEffects: string[];
  sideEffectsNote?: string;
  interactions: string[];
  interactionsNote?: string;
  warnings: string[];
  sources: SourceReference[];
}

export const MOCK_MEDICATION_INFO: Record<string, MedicationInfoDetails> = {
  Amoxicillin: {
    medicationId: "amoxicillin",
    name: "Amoxicillin",
    description: "Broad-spectrum antibiotic",
    drugClass: "Antibiotic (Penicillin)",
    overview:
      "Amoxicillin is a penicillin-type antibiotic used to treat a wide range of bacterial infections. It works by stopping the growth of bacteria. Amoxicillin is effective against many gram-positive and some gram-negative bacteria and is commonly prescribed for ear, nose, throat, respiratory, urinary tract, skin, and other bacterial infections.",
    uses: [
      "Ear infections (otitis media)",
      "Sinus infections (sinusitis)",
      "Respiratory tract infections",
      "Urinary tract infections",
      "Skin and soft tissue infections",
      "Certain gastrointestinal infections (e.g., H. pylori in combination therapy)",
    ],
    availableForms: [
      "Capsule",
      "Tablet (including chewable tablets)",
      "Oral suspension (liquid)",
      "Injection (IV/IM)",
    ],
    formsNote: "Specific forms and strengths may vary by manufacturer and region.",
    dosageInformation: [
      "The usual dose of amoxicillin depends on the type and severity of the infection, patient age, and kidney function. Always follow your healthcare provider's instructions.",
      "Do not change your dose or stop taking amoxicillin without consulting your healthcare professional.",
    ],
    commonSideEffects: [
      "Nausea",
      "Vomiting",
      "Diarrhoea",
      "Rash",
      "Headache",
      "Stomach upset",
    ],
    sideEffectsNote:
      "Most side effects are mild and temporary. Contact a healthcare professional if they persist or become severe.",
    interactions: [
      "May interact with blood thinners (e.g., warfarin)",
      "Can affect the efficacy of oral contraceptives",
      "Possible interactions with methotrexate, allopurinol, and other medications",
    ],
    interactionsNote:
      "Always inform your healthcare provider about all medications you are taking.",
    warnings: [
      "Do not use if you are allergic to penicillins or have had a severe allergic reaction to any antibiotic.",
      "Use with caution in patients with a history of allergies, asthma, or kidney problems.",
      "May cause allergic reactions, ranging from mild rashes to severe anaphylaxis (rare).",
      "Contact your healthcare provider immediately if you experience a severe rash, difficulty breathing, or swelling.",
    ],
    sources: [
      { id: 1, name: "FDA Drug Label (Amoxicillin)", documentId: "doc_fda_amoxicillin_001" },
      { id: 2, name: "EMA Product Information", documentId: "doc_ema_amoxicillin_002" },
      { id: 3, name: "MedlinePlus (NIH)", documentId: "doc_nih_amoxicillin_003" },
    ],
  },
};

export function getMedicationInfo(drugName: string): MedicationInfoDetails {
  const normalized = drugName.trim();
  if (MOCK_MEDICATION_INFO[normalized]) {
    return MOCK_MEDICATION_INFO[normalized];
  }

  // Generates drug-tailored mock info for any requested drug parameter
  return {
    medicationId: normalized.toLowerCase().replace(/\s+/g, "_"),
    name: normalized,
    description: "Prescription medication",
    drugClass: "Therapeutic Agent",
    overview: `${normalized} is a prescription medication used under medical supervision to manage specific health conditions. Always consult official drug documentation or a licensed healthcare professional for verified indications and guidelines.`,
    uses: [
      `Treatment of specific conditions diagnosed by a healthcare provider`,
      `Management of related symptoms according to clinical guidelines`,
      `Short-term or long-term therapy as prescribed`,
    ],
    availableForms: ["Oral tablet / capsule", "Oral liquid / solution"],
    formsNote: "Specific forms and strengths may vary by manufacturer and region.",
    dosageInformation: [
      `The dose of ${normalized} depends on patient age, weight, medical history, and condition severity.`,
      "Always follow your healthcare provider's exact instructions and complete the full prescribed course.",
    ],
    commonSideEffects: ["Nausea", "Mild dizziness", "Headache", "Gastrointestinal discomfort"],
    sideEffectsNote:
      "Most side effects are mild and temporary. Contact a healthcare professional if they persist or become severe.",
    interactions: [
      "May interact with other prescription medications, OTC drugs, or supplements.",
      "Consult your pharmacist or physician regarding potential drug-drug interactions.",
    ],
    interactionsNote:
      "Always inform your healthcare provider about all medications you are taking.",
    warnings: [
      `Do not take ${normalized} if you have a known hypersensitivity or severe allergic reaction to it.`,
      "Inform your healthcare provider of pre-existing kidney, liver, or cardiac conditions.",
      "Seek emergency medical attention if you observe severe allergic symptoms (swelling, hives, trouble breathing).",
    ],
    sources: [
      { id: 1, name: `FDA Drug Label (${normalized})`, documentId: `doc_fda_${normalized.toLowerCase()}_001` },
      { id: 2, name: "EMA Product Information", documentId: `doc_ema_${normalized.toLowerCase()}_002` },
      { id: 3, name: "MedlinePlus (NIH)", documentId: `doc_nih_${normalized.toLowerCase()}_003` },
    ],
  };
}
