# Root cause found + how to verify it

## What was actually wrong

`calib/calibrate.py`'s `relevant()` function is what decides, for every
retrieved chunk, whether it counts as correct evidence. It was checking
`expected_keywords` and `expected_chunk` first. Those two fields are **only
ever populated** for the small number of rows pulled from
`gold_standard_qa.json`/`eval_set.json`. Every "generated" row --
everything `calib/make_questions.py`'s section/topic/keyword/hinglish/
followup/mentor-routing generators produce, which is ~98% of your 2086
questions -- has `expected_keywords=""` and `expected_chunk=""`, but DOES
have `target_sections`/`gold_topic` populated correctly.

So `relevant()` was falling through to `bool("" and ...)` -> `False` for
almost every question, regardless of what retrieval actually found. That's
precision/recall/hit@k reading near-zero across the board -- not because
retrieval is broken, but because the evaluator had no gold definition to
check against for almost every question. This is "failure pattern E" (a
gold/evaluator problem, not an actual retrieval problem).

Fixed: `relevant()` now checks `gold_topic`/`target_sections` first (falling
back to keywords/expected_chunk for the JSON-sourced rows that use those
instead) -- same logic your repo's original `calibrate_lancedb_base.py`
already had, that got dropped when the more advanced handoff version was
adopted a few turns back.

## How to verify this before re-running the full 2086-question calibration

`rag_debug/debug_rag.py` runs your REAL `understand -> retrieve -> gate ->
relevant()` chain (imports the actual function from `calib.calibrate`, not a
copy) against 5 synthetic questions with known answers, in a throwaway
LanceDB instance -- your production `data/lancedb_data` is never touched.

```python
# Colab cell
%cd /content/CTS-hackathon
venv_py = "/content/CTS-hackathon/.venv311/bin/python"
import subprocess
subprocess.run([venv_py, "-m", "rag_debug.debug_rag"], cwd="/content/CTS-hackathon", check=True)
```

Read the per-question trace it prints. Every `RESULT: PASS` line confirms
the mechanics (embedding, retrieval, gate, evaluator) are sound end to end.
If any come back `FAIL`, the printed `failure_stage` tells you exactly which
of the four stages to look at -- don't guess, don't touch thresholds, look
at that one stage first.

Once this shows 5/5, re-run your real calibration -- with both the
`relevant()` fix and this confirmation, the numbers it reports should now
actually reflect retrieval quality instead of an evaluator that couldn't
find gold evidence to check against.
