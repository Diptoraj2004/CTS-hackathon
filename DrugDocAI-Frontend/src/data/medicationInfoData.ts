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

export const MOCK_MEDICATION_INFO: Record<string, MedicationInfoDetails> = {};

export function getMedicationInfo(drugName: string): MedicationInfoDetails | null {
  const normalized = drugName.trim();
  // Case-insensitive match for predefined verified medication details
  const matchKey = Object.keys(MOCK_MEDICATION_INFO).find(
    (key) => key.toLowerCase() === normalized.toLowerCase()
  );
  if (matchKey) {
    return MOCK_MEDICATION_INFO[matchKey];
  }

  // Return null when verified information is unavailable in mock/hardcoded store
  // Do NOT fabricate or infer medical facts for unknown drugs.
  return null;
}

