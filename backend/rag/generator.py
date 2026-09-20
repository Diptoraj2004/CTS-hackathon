"""Generation call: grounded, cited answer in clinician or patient style.
Uses Groq if GROQ_API_KEY is set (with Ollama fallback), otherwise local Ollama."""
import os

import ollama
from dotenv import load_dotenv
from pydantic import BaseModel

from backend.rag import config
from backend.rag.schemas import QueryInfo, RetrievedChunk

load_dotenv()

NOT_IN_CONTEXT = "NOT_IN_CONTEXT"

GROUNDING_RULES = f"""You answer questions about medicines using ONLY the numbered drug-label excerpts provided.
Rules:
- Use only facts stated in the excerpts. Never use outside knowledge.
- Start directly with the answer. Do not write introductions such as "According to the excerpts".
- For yes/no questions, begin with "Yes" or "No" and give the reason in the same sentence, with its citation.
- Give a complete answer: use every excerpt that is relevant to the question.
- EVERY sentence and EVERY bullet point that states a fact must include its excerpt number in square brackets, placed right BEFORE the final full stop. Example: "The maximum dose is 2550 mg per day [2]."
- Copy numbers (doses, ages, lab values) exactly as written in the excerpts.
- If the excerpts do not contain the answer, reply with exactly: {NOT_IN_CONTEXT}
- Never invent doses, numbers, units, or drug names.
- Do not diagnose anyone or tell them to change their treatment."""

PERSONAS = {
    "clinician": "Audience: a healthcare professional. Be precise and concise. Give exact doses, "
                 "ranges, units, titration steps, and conditions exactly as written. Mention relevant "
                 "contraindications and warnings from the excerpts. Use standard medical terms.",
    "patient": "Audience: a patient or caregiver. Use plain, simple English and short sentences. "
               "Explain any medical word you use. Use short bullet points for steps, and every "
               "bullet must end with its citation number. Finish with this exact sentence (no "
               "citation needed): Please talk to your doctor or pharmacist before making any "
               "change to your medicine.",
}


class Generation(BaseModel):
    text: str
    model: str


def build_context(evidence: list[RetrievedChunk]) -> str:
    blocks = []
    for i, r in enumerate(evidence, start=1):
        c = r.chunk
        page = f", page {c.page}" if c.page else ""
        blocks.append(f"[{i}] ({c.drug_name} | {c.section} | {c.source_file}{page})\n{c.text}")
    return "\n\n".join(blocks)


def build_messages(info: QueryInfo, evidence: list[RetrievedChunk]) -> list[dict]:
    about = f" (about {', '.join(info.drug_names)})" if info.drug_names else ""
    user = (f"Drug-label excerpts:\n\n{build_context(evidence)}\n\n"
            f"Question{about}: {info.original_query}")
    return [
        {"role": "system", "content": GROUNDING_RULES + "\n\n" + PERSONAS[info.mode]},
        {"role": "user", "content": user},
    ]


def _call_groq(messages: list[dict]) -> str:
    from groq import Groq
    resp = Groq().chat.completions.create(model=config.GROQ_MODEL, messages=messages,
                                          temperature=config.TEMPERATURE)
    return resp.choices[0].message.content


class GenerationError(Exception):
    """Raised when no generation backend could produce an answer — caught in
    main.py and turned into a clean escalation instead of an unhandled 500."""


def _call_ollama(messages: list[dict]) -> str:
    try:
        resp = ollama.chat(model=config.OLLAMA_MODEL, messages=messages,
                           options={"temperature": config.TEMPERATURE})
        return resp.message.content
    except Exception as e:
        # Previously unguarded: an Ollama that isn't running (connection
        # refused) or hasn't pulled config.OLLAMA_MODEL surfaced as a raw
        # exception all the way up through main.py as an opaque 500.
        raise GenerationError(f"Ollama call failed ({type(e).__name__}): {e}") from e


def generate(info: QueryInfo, evidence: list[RetrievedChunk]) -> Generation:
    messages = build_messages(info, evidence)
    if os.getenv("GROQ_API_KEY"):
        try:
            return Generation(text=_call_groq(messages).strip(), model=f"groq:{config.GROQ_MODEL}")
        except Exception as e:  # network, quota, bad key -> fall back to local model
            print(f"[generator] Groq failed ({type(e).__name__}); using Ollama")
    return Generation(text=_call_ollama(messages).strip(), model=f"ollama:{config.OLLAMA_MODEL}")


if __name__ == "__main__":
    from backend.rag.citation import process
    from backend.rag.query_understanding import understand
    from backend.rag.relevance_gate import check
    from backend.rag.retriever import retrieve

    q = "What is the maximum dose of metformin?"
    for mode in ("clinician", "patient"):
        info = understand(q, mode=mode, session_id=mode)
        gate = check(info, retrieve(info.standalone_query, info.drug_names,
                                    sections=info.section_hints))
        print(f"\n===== {mode.upper()} MODE =====")
        if not gate.passed:
            print(f"ESCALATED: {gate.reason}")
            continue
        g = generate(info, gate.evidence)
        cit = process(g.text, gate.evidence)
        print(f"(model: {g.model})\n{cit.text}")
        print(f"\ncitation coverage: {cit.coverage}   uncited: {cit.uncited}")
