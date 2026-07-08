"""Diagnostic: run retrieval for the solar query and print scores.
Run inside the api container:
  docker compose exec policy-api python /tmp/diag_retrieval.py
(or locally with the DB reachable)
"""

from mdhpp_core import load_settings
from mdhpp_retrieval.embed import BGEM3Embedder
from mdhpp_retrieval.hybrid import hybrid_search
from mdhpp_retrieval.rerank import BGEReranker

q = "Can my HOA stop me from installing solar panels?"
s = load_settings()
emb = BGEM3Embedder(s.embedding_model)
(qv,) = emb.embed([q])

hits = hybrid_search(s.pg_dsn, q, qv, top_k=s.retrieve_top_k)
print(f"\n=== hybrid top {len(hits.chunks)} (pre-rerank) ===")
for c, sc in zip(hits.chunks, hits.scores, strict=False):
    print(f"  {sc:.3f}  {c.citation.section:12} {c.citation.snippet[:60]!r}")

rr = BGEReranker(s.reranker_model)
reranked = rr.rerank(q, hits.chunks, s.rerank_top_k)
print(f"\n=== reranked top {len(reranked.chunks)} (floor={s.relevance_floor}) ===")
for c, sc in zip(reranked.chunks, reranked.scores, strict=False):
    flag = "PASS" if sc >= s.relevance_floor else "CUT "
    print(f"  [{flag}] {sc:.3f}  {c.citation.section:12} {c.citation.snippet[:60]!r}")

best = max(reranked.scores) if reranked.scores else 0
print(
    f"\nbest rerank score: {best:.3f}  |  floor: {s.relevance_floor}  |  "
    f"{'GROUNDED' if best >= s.relevance_floor else 'REFUSAL'}"
)
