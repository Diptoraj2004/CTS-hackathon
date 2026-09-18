"""Retrieval: query -> top-K chunks from Chroma, optionally filtered by drug."""
from typing import Optional

from backend.rag import config
from backend.rag.schemas import Chunk, RetrievedChunk
from backend.rag.vector_store import embed, get_collection


def retrieve(query: str, drug_names: Optional[list[str]] = None,
             top_k: int = config.TOP_K) -> list[RetrievedChunk]:
    col = get_collection()
    total = col.count()
    if total == 0:
        return []

    where = None
    if drug_names:
        names = [d.lower() for d in drug_names]
        where = {"drug_name": names[0]} if len(names) == 1 else {"drug_name": {"$in": names}}

    res = col.query(
        query_embeddings=embed([query]),
        n_results=min(top_k, total),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    results = []
    for cid, text, meta, dist in zip(res["ids"][0], res["documents"][0],
                                     res["metadatas"][0], res["distances"][0]):
        # Normalized vectors: squared L2 distance d -> cosine similarity 1 - d/2
        score = max(0.0, min(1.0, 1 - dist / 2))
        results.append(RetrievedChunk(chunk=Chunk(chunk_id=cid, text=text, **meta),
                                      score=round(score, 3)))
    return results


if __name__ == "__main__":
    tests = [
        ("What is the maximum daily dose of metformin?", ["metformin"]),
        ("Who should not take this drug?", ["amoxicillin"]),
        ("What is the dose for severe infections?", None),
    ]
    for q, drugs in tests:
        print(f"\nQ: {q}   (filter: {drugs})")
        for r in retrieve(q, drugs, top_k=3):
            print(f"  {r.score:.3f}  {r.chunk.chunk_id:<11} {r.chunk.section}")
