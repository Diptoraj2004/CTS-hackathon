"""Synthetic RAG diagnostic harness.

Runs the REAL backend.rag pipeline (understand -> retrieve -> gate -> the
same relevant() function calib/calibrate.py uses) against a small synthetic
corpus with known answers, in an isolated LanceDB instance that is deleted
afterward. This never touches your production drug-label store.

Point of this: isolate whether "calibration shows near-zero numbers" is a
mechanics problem (retrieval/gate genuinely broken) or a definitions problem
(the evaluator's idea of "correct" doesn't match what was actually asked for)
-- without burning a run against the real 2000+ question set to find out.

Usage (must run inside .venv311 -- see COLAB_RUN_DEBUG.md):
    python -m rag_debug.debug_rag
"""
import os
import shutil
import sys
import tempfile

# MUST happen before any backend.rag import -- config.py reads LANCEDB_DIR
# from the environment at import time. This guarantees a fresh, empty,
# throwaway store instead of touching data/lancedb_data.
TEMP_DB = tempfile.mkdtemp(prefix="rag_debug_lancedb_")
os.environ["LANCEDB_DIR"] = TEMP_DB
print(f"Isolated LanceDB for this run: {TEMP_DB}  (production store untouched)\n")

from backend.rag.schemas import Chunk                          # noqa: E402
from backend.rag.vector_store import add_chunks, get_table     # noqa: E402
from backend.rag.query_understanding import understand         # noqa: E402
from backend.rag.retriever import retrieve                     # noqa: E402
from backend.rag.relevance_gate import check                   # noqa: E402
from calib.calibrate import relevant as calib_relevant          # noqa: E402
# ^ imported, not reimplemented -- this harness tests the exact same
# gold-evidence definition your real calibration run scores against.
# If calibrate.py's relevant() ever changes, this stays in sync automatically.

SYNTHETIC_CHUNKS = [
    Chunk(chunk_id="alpha-dosage", drug_name="Zynovex", section="Dosage and Administration",
          source_file="synthetic_alpha.txt",
          text="Zynovex is given as 10 mg by mouth once daily with food."),
    Chunk(chunk_id="alpha-adverse", drug_name="Zynovex", section="Adverse Reactions",
          source_file="synthetic_alpha.txt",
          text="Common adverse reactions to Zynovex include nausea and headache."),
    Chunk(chunk_id="alpha-pregnancy", drug_name="Zynovex", section="Use in Specific Populations",
          source_file="synthetic_alpha.txt",
          text="Zynovex has not been studied in pregnancy; fetal risk is unknown."),
    Chunk(chunk_id="beta-dosage", drug_name="Cortabrium", section="Dosage and Administration",
          source_file="synthetic_beta.txt",
          text="Cortabrium dosing starts at 5 mg twice daily, titrated to effect."),
    Chunk(chunk_id="beta-adverse", drug_name="Cortabrium", section="Adverse Reactions",
          source_file="synthetic_beta.txt",
          text="Cortabrium may cause dizziness and dry mouth in some patients."),
    Chunk(chunk_id="beta-kidney", drug_name="Cortabrium", section="Warnings",
          source_file="synthetic_beta.txt",
          text="Cortabrium clearance is reduced in renal impairment; monitor kidney function."),
]

# target_sections/gold_topic here mirror exactly what make_questions.py puts
# in calibration_questions.csv for a real "generated" row -- this is the
# field pair the fixed relevant() actually reads.
TEST_CASES = [
    {"id": "Q1", "question": "What is the dosage of Zynovex?", "drug": "Zynovex",
     "target_sections": "Dosage and Administration", "gold_topic": "", "expected_keywords": "", "expected_chunk": ""},
    {"id": "Q2", "question": "What are the side effects of Zynovex?", "drug": "Zynovex",
     "target_sections": "Adverse Reactions", "gold_topic": "", "expected_keywords": "", "expected_chunk": ""},
    {"id": "Q3", "question": "Is Zynovex safe to take during pregnancy?", "drug": "Zynovex",
     "target_sections": "", "gold_topic": "pregnancy", "expected_keywords": "", "expected_chunk": ""},
    {"id": "Q4", "question": "How is Cortabrium dosed?", "drug": "Cortabrium",
     "target_sections": "Dosage and Administration", "gold_topic": "", "expected_keywords": "", "expected_chunk": ""},
    {"id": "Q5", "question": "Does Cortabrium affect the kidneys?", "drug": "Cortabrium",
     "target_sections": "", "gold_topic": "kidney", "expected_keywords": "", "expected_chunk": ""},
]


def main():
    print("=== STAGE: STORAGE (writing synthetic chunks via the real add_chunks()) ===")
    written = add_chunks(SYNTHETIC_CHUNKS)
    table = get_table()
    row_count = table.count_rows() if table else 0
    print(f"Wrote {written} chunks. Table row count: {row_count}")
    if table is None or row_count != len(SYNTHETIC_CHUNKS):
        print("STORAGE: FAIL -- row count doesn't match what was written. Stop here, "
              "the problem is in add_chunks()/embed(), not in retrieval or the gate.")
        return
    print("STORAGE: PASS\n")

    print("=== STAGE: PER-QUESTION TRACE (real understand -> retrieve -> gate -> evaluator) ===")
    outcomes = []
    for case in TEST_CASES:
        print(f"\n--- {case['id']}: {case['question']!r} ---")
        info = understand(case["question"], mode="patient", session_id=f"debug-{case['id']}")
        print(f"  understood: drug_names={info.drug_names}  standalone_query={info.standalone_query!r}")

        retrieved = retrieve(info.standalone_query, info.drug_names or [case["drug"]],
                              top_k=5, sections=info.section_hints)
        print(f"  RETRIEVAL: {len(retrieved)} chunk(s)")
        for r in retrieved:
            print(f"    score={r.score:.3f}  {r.chunk.chunk_id:<16} section={r.chunk.section!r}")

        gate = check(info, retrieved)
        print(f"  GATE: passed={gate.passed}  reason={gate.reason!r}  top_score={gate.top_score:.3f}")

        matches = [calib_relevant(r, case) for r in retrieved]
        hit = any(matches)

        if not retrieved:
            stage = "RETRIEVAL"
        elif not hit:
            stage = "EVALUATOR (or wrong chunk retrieved)"
        elif not gate.passed:
            stage = "GATE"
        else:
            stage = None

        print(f"  EVALUATOR match found: {hit}")
        print(f"  RESULT: {'PASS' if hit else 'FAIL -- failure_stage=' + stage}")
        outcomes.append((case["id"], hit, stage))

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, hit, _ in outcomes if hit)
    print(f"{passed}/{len(outcomes)} synthetic questions found their expected evidence.\n")
    for cid, hit, stage in outcomes:
        print(f"  {cid}: {'PASS' if hit else f'FAIL ({stage})'}")

    if passed == len(outcomes):
        print("\nAll synthetic cases pass: understand/retrieve/gate/evaluator mechanics are sound.")
        print("If a real calibration run still shows near-zero numbers, the problem is specific to")
        print("the real corpus or real question set -- e.g. a category whose make_questions.py rows")
        print("aren't populating target_sections/gold_topic the way these synthetic cases do.")
    else:
        print("\nSome synthetic cases failed. Fix the named stage before trusting any real-corpus")
        print("calibration numbers -- they'll be measuring the same failure, just less visibly.")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(TEMP_DB, ignore_errors=True)
