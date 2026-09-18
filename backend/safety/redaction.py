"""PHI/PII redaction. Runs twice: once on ingested text before it's embedded,
once on the generated answer before it reaches the user."""
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

TARGET_ENTITIES = [
    "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
    "MEDICAL_LICENSE", "US_SSN", "LOCATION", "CREDIT_CARD",
]


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    analyzer = AnalyzerEngine()
    # The built-in URL recognizer tries to fetch a public-suffix list over the
    # network on first use. We don't redact URLs anyway (not in TARGET_ENTITIES),
    # so drop it rather than depend on internet access at demo time.
    analyzer.registry.remove_recognizer("UrlRecognizer")
    return analyzer


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    return AnonymizerEngine()


def redact(text: str) -> str:
    if not text:
        return text
    results = get_analyzer().analyze(text=text, entities=TARGET_ENTITIES, language="en")
    return get_anonymizer().anonymize(text=text, analyzer_results=results).text


if __name__ == "__main__":
    cases = [
        "Patient John Doe (phone 9124502346) started the new dose.",
        "Contact dr.mehta@clinic.com about the metformin refill.",
        "No dosage information should ever be redacted, only identity.",
    ]
    for c in cases:
        print(f"  in:  {c}")
        print(f"  out: {redact(c)}\n")
