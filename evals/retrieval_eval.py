"""Deterministic retrieval eval — no LLM judge, CI-friendly.

For each `retrieve` case: run the real retrieval path (embed -> hybrid -> rerank
-> floor) and check whether an expected section appears in the surviving top-k.
For each `refuse` case: check that nothing clears the floor (correct decline).

Reports hit-rate, mean reciprocal rank (MRR), and refusal accuracy. Exits
non-zero if metrics fall below thresholds, so CI can gate on it.

Run:
    uv run python -m evals.retrieval_eval
    uv run python -m evals.retrieval_eval --hit-rate-min 0.8 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mdhpp_core import load_settings
from mdhpp_retrieval.embed import BGEM3Embedder
from mdhpp_retrieval.hybrid import hybrid_search
from mdhpp_retrieval.jurisdiction import detect_other_state
from mdhpp_retrieval.rerank import BGEReranker

_EVAL_SET = Path(__file__).parent / "eval_set.json"


@dataclass
class RetrieveResult:
    question: str
    expected: list[str]
    got_sections: list[str]
    hit: bool
    rank: int | None  # 1-based rank of the first expected section, or None
    top_score: float


@dataclass
class RefuseResult:
    question: str
    correctly_refused: bool
    top_score: float


@dataclass
class Report:
    retrieve: list[RetrieveResult] = field(default_factory=list)
    refuse: list[RefuseResult] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        if not self.retrieve:
            return 0.0
        return sum(r.hit for r in self.retrieve) / len(self.retrieve)

    @property
    def mrr(self) -> float:
        if not self.retrieve:
            return 0.0
        return sum((1.0 / r.rank) if r.rank else 0.0 for r in self.retrieve) / len(self.retrieve)

    @property
    def refusal_accuracy(self) -> float:
        if not self.refuse:
            return 1.0
        return sum(r.correctly_refused for r in self.refuse) / len(self.refuse)


def _section_matches(got: str, expected: str) -> bool:
    """A retrieved section counts as matching an expected label if it equals it
    or is a decimal child (e.g. expected '11B-111' matches '11B-111' exactly;
    expected '14-203' matches '14-203'). Exact match only — decimals are
    distinct sections."""
    return got.strip() == expected.strip()


def run_eval() -> Report:
    settings = load_settings()
    data = json.loads(_EVAL_SET.read_text())
    embedder = BGEM3Embedder(settings.embedding_model)
    reranker = BGEReranker(settings.reranker_model)
    report = Report()

    def retrieve_sections(question: str) -> tuple[list[str], list[float]]:
        (qv,) = embedder.embed([question])
        hits = hybrid_search(settings.pg_dsn, question, qv, top_k=settings.retrieve_top_k)
        reranked = reranker.rerank(question, hits.chunks, settings.rerank_top_k)
        # Keep only chunks above the floor (what the API would actually use).
        kept = [
            (c.citation.section, s)
            for c, s in zip(reranked.chunks, reranked.scores, strict=True)
            if s >= settings.relevance_floor
        ]
        return [sec for sec, _ in kept], [s for _, s in kept]

    for case in data.get("retrieve", []):
        q, expected = case["question"], case["expected_sections"]
        got, scores = retrieve_sections(q)
        rank: int | None = None
        for i, sec in enumerate(got, start=1):
            if any(_section_matches(sec, e) for e in expected):
                rank = i
                break
        report.retrieve.append(
            RetrieveResult(
                question=q,
                expected=expected,
                got_sections=got,
                hit=rank is not None,
                rank=rank,
                top_score=scores[0] if scores else 0.0,
            )
        )

    for case in data.get("refuse", []):
        q = case["question"]
        # The real retrieve() path refuses out-of-jurisdiction questions before
        # retrieval, so mirror that here.
        if detect_other_state(q) is not None:
            report.refuse.append(RefuseResult(question=q, correctly_refused=True, top_score=0.0))
            continue
        got, scores = retrieve_sections(q)
        # retrieve_sections already filtered to chunks above the floor, so a
        # correct refusal is simply: nothing survived.
        report.refuse.append(
            RefuseResult(
                question=q,
                correctly_refused=len(scores) == 0,
                top_score=scores[0] if scores else 0.0,
            )
        )

    return report


def print_report(report: Report, as_json: bool) -> None:
    if as_json:
        out = {
            "hit_rate": report.hit_rate,
            "mrr": report.mrr,
            "refusal_accuracy": report.refusal_accuracy,
            "retrieve": [vars(r) for r in report.retrieve],
            "refuse": [vars(r) for r in report.refuse],
        }
        print(json.dumps(out, indent=2))
        return

    print("\n=== retrieval eval ===")
    for r in report.retrieve:
        mark = "HIT " if r.hit else "MISS"
        rank = f"@{r.rank}" if r.rank else "  -"
        print(
            f"  [{mark}] {rank}  exp={','.join(r.expected):16} "
            f"got={','.join(r.got_sections) or '(refused)':24} "
            f"{r.question[:50]!r}"
        )
    print("\n=== refusal eval (should decline) ===")
    for rr in report.refuse:
        mark = "OK  " if rr.correctly_refused else "LEAK"
        print(f"  [{mark}] top={rr.top_score:.4f}  {rr.question[:55]!r}")

    print(
        f"\nhit_rate={report.hit_rate:.2%}  mrr={report.mrr:.3f}  "
        f"refusal_accuracy={report.refusal_accuracy:.2%}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic retrieval eval.")
    ap.add_argument("--hit-rate-min", type=float, default=0.70)
    ap.add_argument("--refusal-min", type=float, default=0.80)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report = run_eval()
    print_report(report, as_json=args.json)

    ok = report.hit_rate >= args.hit_rate_min and (report.refusal_accuracy >= args.refusal_min)
    if not ok and not args.json:
        print(
            f"\nFAIL: hit_rate {report.hit_rate:.2%} (min {args.hit_rate_min:.0%}) "
            f"or refusal {report.refusal_accuracy:.2%} (min {args.refusal_min:.0%})",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
