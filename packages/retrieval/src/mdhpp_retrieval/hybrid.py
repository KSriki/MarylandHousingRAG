"""Hybrid retrieval against pgvector (imperative shell — does I/O).

One SQL query scores both halves of hybrid search and fuses them:
- dense: cosine similarity between the query embedding and each chunk vector
  (pgvector `<=>` operator, HNSW index)
- lexical: Postgres full-text rank of the chunk's generated tsvector against the
  query terms (GIN index)

Fusion is a weighted sum of the two normalized scores. Keeping both in one
statement is the point of the single-data-plane design — no second search
service, no application-side merge.
"""

from __future__ import annotations

import psycopg
from pgvector.psycopg import Vector, register_vector

from mdhpp_core import Chunk, Citation, RetrievalResult

# Weights for fusing normalized dense + lexical scores. Dense leads because the
# corpus is paraphrase-heavy; lexical breaks ties on exact section refs.
_DENSE_WEIGHT = 0.6
_LEXICAL_WEIGHT = 0.4

_HYBRID_SQL = """
WITH dense AS (
    SELECT id,
           1 - (embedding <=> %(qvec)s::vector) AS dense_score
    FROM chunks
    WHERE jurisdiction = %(jurisdiction)s
      AND embedding IS NOT NULL
    ORDER BY embedding <=> %(qvec)s::vector
    LIMIT %(candidates)s
),
lexical AS (
    SELECT id,
           ts_rank(ts, plainto_tsquery('english', %(qtext)s)) AS lex_score
    FROM chunks
    WHERE jurisdiction = %(jurisdiction)s
      AND ts @@ plainto_tsquery('english', %(qtext)s)
    LIMIT %(candidates)s
),
fused AS (
    SELECT c.id,
           COALESCE(d.dense_score, 0) AS dense_score,
           COALESCE(l.lex_score, 0)   AS lex_score
    FROM chunks c
    LEFT JOIN dense d   ON d.id = c.id
    LEFT JOIN lexical l ON l.id = c.id
    WHERE d.id IS NOT NULL OR l.id IS NOT NULL
)
SELECT c.id, c.text, c.doc, c.section, c.breadcrumb, c.url, c.snippet,
       c.jurisdiction,
       (
           %(dw)s * f.dense_score
           + %(lw)s * COALESCE(
               f.lex_score / NULLIF(MAX(f.lex_score) OVER (), 0),
               0
           )
       ) AS score
FROM fused f
JOIN chunks c ON c.id = f.id
ORDER BY score DESC
LIMIT %(top_k)s
"""


def hybrid_search(
    dsn: str,
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    jurisdiction: str = "MD",
    candidates: int | None = None,
) -> RetrievalResult:
    """Run hybrid dense + lexical retrieval, returning the top_k fused chunks.

    `candidates` caps each half's shortlist before fusion; defaults to 4x top_k.
    """
    candidates = candidates or top_k * 4

    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        rows = conn.execute(
            _HYBRID_SQL,
            {
                "qvec": Vector(query_embedding),
                "qtext": query_text,
                "jurisdiction": jurisdiction,
                "candidates": candidates,
                "top_k": top_k,
                "dw": _DENSE_WEIGHT,
                "lw": _LEXICAL_WEIGHT,
            },
        ).fetchall()

    chunks: list[Chunk] = []
    scores: list[float] = []
    for row in rows:
        cid, text, doc, section, breadcrumb, url, snippet, juris, score = row
        chunks.append(
            Chunk(
                id=cid,
                text=text,
                citation=Citation(
                    doc=doc,
                    section=section,
                    breadcrumb=breadcrumb,
                    url=url,
                    snippet=snippet,
                ),
                jurisdiction=juris,
            )
        )
        scores.append(float(score) if score is not None else 0.0)

    return RetrievalResult(chunks=chunks, scores=scores)
