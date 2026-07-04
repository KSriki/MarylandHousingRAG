# Corpus

Source documents for ingestion, organized by document type. The ingestion
pipeline (`uv run ingest`) reads from these subdirectories, chunks with
section-aware breadcrumb headers, embeds, and upserts to pgvector.

Large source files (`*.pdf`, `*.html`) are **gitignored** — this directory is
version-controlled for its *structure and manifest*, not its contents. Drop the
real documents in locally (or mount them) before running ingestion.

## Layout

```
corpus/
  statute/   Maryland state law (Real Property Article) — the controlling layer
  county/    County / municipal code — local rules beneath statute
  ccrs/      Recorded HOA covenants, conditions & restrictions — lowest layer
```

Statute overrides a conflicting covenant; the `jurisdiction` and document-type
metadata carried on each chunk preserves this hierarchy so retrieval and the
answer can reflect which layer governs.

## v1 source list (Maryland)

These are the public primary sources for v1. Section numbers are stored on each
chunk's citation so answers can point to the exact provision.

### statute/
- **Maryland Homeowners Association Act** — Real Property Article, Title 11B.
  Key provisions: disclosures (11B-105 to 11B-111), meetings and notice
  (11B-111), architectural review and enforcement, assessments and liens.
- **Maryland Condominium Act** — Real Property Article, Title 11.
  Governance, bylaws, common elements, resale certificates.
- **Maryland Contract Lien Act** — Real Property Article, Title 14, Subtitle 2.
  How HOA/condo liens attach and are enforced.

### county/
- County code excerpts relevant to housing/land use for the counties covered in
  v1 (e.g., zoning, permitting, nuisance, short-term-rental rules). One file per
  county, named `{county}-{topic}.pdf` or `.html`.

### ccrs/
- Sample publicly-recorded CC&Rs used for demonstration only. v1 ships with
  documents that are public record or that the maintainer is authorized to use;
  per-user private CC&R upload is a v2 feature (see design doc Non-goals).

## Naming convention

`{doc-slug}.{pdf|html}` — the slug becomes part of the citation's `doc` field.
Examples: `md-hoa-act-title-11b.pdf`, `md-condominium-act-title-11.pdf`,
`montgomery-county-zoning.html`.

## Metadata carried per chunk

Set during ingestion (see `mdhpp_core.models.Chunk` / `Citation`):
- `jurisdiction` — `MD` for v1 (filter key; leaves the seam open for other states)
- `doc` — human name, e.g. "Maryland HOA Act"
- `section` — statute/section ref, e.g. "RP 11B-111"
- `breadcrumb` — full hierarchy path, e.g. "MD HOA Act > 11B-111 > Meetings"
- `url` — link to the public source, when available

## Legal note

All v1 sources are public records or authorized-use documents. This corpus
supports *informational* retrieval only; the system surfaces policy and
citations, not legal advice (see design doc Legal / compliance section).