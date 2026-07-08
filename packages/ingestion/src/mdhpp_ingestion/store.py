"""Persist chunks to pgvector with delta semantics (imperative shell).

Upsert keyed on the content-hash `id`: an unchanged chunk (same breadcrumb +
body) keeps its id and is left alone; a changed chunk gets a new id and is
inserted, and ids no longer present for a document can be pruned. This makes
re-ingesting an amended statute a delta update, not a full rebuild.
"""

from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector

from mdhpp_core import Chunk


def upsert_chunks(
    dsn: str,
    chunks: list[Chunk],
    embedding_model: str,
) -> int:
    """Insert or update the given chunks. Returns the count written.

    Chunks whose id already exists with identical text are updated in place
    (ON CONFLICT), so re-running is idempotent. Callers pass chunks that already
    carry embeddings.
    """
    if not chunks:
        return 0

    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            for chunk in chunks:
                cur.execute(
                    """
                    INSERT INTO chunks (
                        id, text, embedding, embedding_model,
                        jurisdiction, doc, section, breadcrumb, url, snippet
                    )
                    VALUES (
                        %(id)s, %(text)s, %(embedding)s, %(embedding_model)s,
                        %(jurisdiction)s, %(doc)s, %(section)s, %(breadcrumb)s,
                        %(url)s, %(snippet)s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        embedding_model = EXCLUDED.embedding_model
                    """,
                    {
                        "id": chunk.id,
                        "text": chunk.text,
                        "embedding": chunk.embedding,
                        "embedding_model": embedding_model,
                        "jurisdiction": chunk.jurisdiction,
                        "doc": chunk.citation.doc,
                        "section": chunk.citation.section,
                        "breadcrumb": chunk.citation.breadcrumb,
                        "url": chunk.citation.url,
                        "snippet": chunk.citation.snippet,
                    },
                )
        conn.commit()

    return len(chunks)


def existing_ids(dsn: str, ids: list[str]) -> set[str]:
    """Return the subset of `ids` already present in the index.

    Lets the pipeline skip re-embedding chunks whose content is unchanged (the
    id is a content hash), so re-running ingest over an already-populated corpus
    only embeds new or amended chunks instead of the whole set.
    """
    if not ids:
        return set()
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT id FROM chunks WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
    return {r[0] for r in rows}


def prune_missing(dsn: str, doc: str, keep_ids: list[str]) -> int:
    """Delete chunks for `doc` whose id is not in `keep_ids` (removed content).

    Returns the number pruned. Called after upserting a re-ingested document so
    sections deleted from the source no longer linger in the index.
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if keep_ids:
                cur.execute(
                    "DELETE FROM chunks WHERE doc = %s AND NOT (id = ANY(%s))",
                    (doc, keep_ids),
                )
            else:
                cur.execute("DELETE FROM chunks WHERE doc = %s", (doc,))
            pruned = cur.rowcount
        conn.commit()
    return pruned
