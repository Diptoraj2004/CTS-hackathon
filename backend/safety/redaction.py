"""PHI/PII redaction. Runs twice: once on ingested text before it's embedded,
once on the generated answer before it reaches the user."""
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

TARGET_ENTITIES = [
    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
    "MEDICAL_LICENSE", "US_SSN", "LOCATION", "CREDIT_CARD",
]

# Presidio's default NlpEngineProvider config pulls en_core_web_lg (~400MB) on
# first use, downloaded lazily inside the first real request — that's a
# multi-minute stall (or a hard failure offline) the first time anyone asks a
# question. en_core_web_sm (~12MB, added to requirements.txt as a direct
# wheel URL so `pip install -r requirements.txt` gets it) is enough for the
# entity types we actually redact.
_NLP_CONFIG = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
}

_redaction_disabled_reason: str | None = None


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine | None:
    global _redaction_disabled_reason
    try:
        provider = NlpEngineProvider(nlp_configuration=_NLP_CONFIG)
        analyzer = AnalyzerEngine(nlp_engine=provider.create_engine())
        # The built-in URL recognizer tries to fetch a public-suffix list over
        # the network on first use. We don't redact URLs (not in
        # TARGET_ENTITIES), so drop it rather than depend on internet access.
        analyzer.registry.remove_recognizer("UrlRecognizer")
        return analyzer
    except Exception as e:
        # Fail safe, not fail loud: a missing/broken spaCy model should not
        # turn every answer into a 500. redact() below returns the text
        # unredacted in this case rather than raising, and this is logged
        # loudly (audit + stdout) so it's visible, not silent.
        _redaction_disabled_reason = f"{type(e).__name__}: {e}"
        print(f"[redaction] DISABLED — Presidio analyzer failed to initialize: {_redaction_disabled_reason}")
        return None


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def redact(text: str) -> str:
    if not text:
        return text
    analyzer = get_analyzer()
    if analyzer is None:
        # Redaction is genuinely off right now (bad model install) — this is
        # a real gap, not something to hide. Caller (audit_log / main.py)
        # should still log that redaction was skipped; see redaction_status().
        return text
    results = analyzer.analyze(text=text, entities=TARGET_ENTITIES, language="en")
    return get_anonymizer().anonymize(text=text, analyzer_results=results).text


def redaction_status() -> dict:
    """So a health-check or the audit log can tell whether redaction is
    actually running, instead of silently passing text through."""
    get_analyzer()  # ensure the lru_cache has resolved one way or the other
    return {"active": _redaction_disabled_reason is None, "reason": _redaction_disabled_reason}


if __name__ == "__main__":
    cases = [
        "Patient John Doe (phone 9124502346) started the new dose.",
        "Contact dr.mehta@clinic.com about the metformin refill.",
        "No dosage information should ever be redacted, only identity.",
    ]
    for c in cases:
        print(f"  in:  {c}")
        print(f"  out: {redact(c)}\n")
