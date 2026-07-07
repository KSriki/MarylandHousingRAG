"""mdhpp CLI entry point.

Installed as the `mdhpp` console script by the root pyproject.toml. Run
`mdhpp --help` to see subcommands.

Design notes (mirrors the LivingMemories pattern):
- Subcommand implementations are imported lazily inside the handler functions
  so `mdhpp --help` stays fast and doesn't trigger model/DB imports.
- Real work lives in the member packages (mdhpp_ingestion, mdhpp_api). This
  file is dispatch only — never put business logic here.
"""

from __future__ import annotations

from pathlib import Path

import typer

from mdhpp import __version__

app = typer.Typer(
    name="mdhpp",
    help="MDHousingPolicyPipeline operational CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command()
def version() -> None:
    """Print the mdhpp version."""
    typer.echo(__version__)


@app.command()
def ingest(
    source: Path | None = typer.Option(
        None, help="Ingest a single file. Mutually exclusive with --corpus."
    ),
    corpus: Path = typer.Option(
        Path("corpus"), help="Ingest all supported files under this directory."
    ),
) -> None:
    """Parse, chunk, embed, and delta-upsert source docs into pgvector."""
    from mdhpp._impl import ingest as _ingest

    _ingest.run(source=source, corpus=corpus)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host (container-internal)."),
    port: int = typer.Option(8000, help="Bind port; the proxy fronts it on :80."),
) -> None:
    """Run the FastAPI app under uvicorn."""
    from mdhpp._impl import serve as _serve

    _serve.run(host=host, port=port)


@app.command(name="download-models")
def download_models() -> None:
    """Pre-download embedder + reranker weights into the model cache volume.

    Run once per environment after deploy so the first /api/ask request doesn't
    pay the model-download cost mid-request.
    """
    from mdhpp._impl import download_models as _dl

    _dl.run()


if __name__ == "__main__":
    app()
