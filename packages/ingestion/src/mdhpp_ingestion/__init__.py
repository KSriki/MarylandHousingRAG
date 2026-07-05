"""mdhpp-ingestion — offline pipeline: parse -> chunk -> embed -> upsert."""

from mdhpp_ingestion.chunk import TokenCodec, chunk_section, chunk_sections
from mdhpp_ingestion.parse import Section, parse_sections
from mdhpp_ingestion.pipeline import IngestReport, ingest_dir, ingest_file

__all__ = [
    "IngestReport",
    "Section",
    "TokenCodec",
    "chunk_section",
    "chunk_sections",
    "ingest_dir",
    "ingest_file",
    "parse_sections",
]
