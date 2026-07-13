"""Grounded-prompt assembly (pure, no I/O).

Builds the LLM prompt from retrieved chunks. The instruction enforces the two
load-bearing behaviors from the design: answers are grounded in the provided
context (with citations), and the system gives *guidance and the governing
policy*, never a legal verdict. Context is XML-tagged and kept structurally
separate from the user's question so injected text in the question can't
override the instruction.
"""

from __future__ import annotations

from mdhpp_core import Chunk

_SYSTEM_INSTRUCTION = """\
You are an assistant that helps Maryland residents understand housing, HOA, and \
condominium law. You provide informational guidance and point to the governing \
policy — you do NOT give legal advice or a verdict on what someone is allowed to \
do.

Rules:
- Answer ONLY from the <context> passages below. Every statement you make must be \
directly supported by text in a passage.
- Do NOT add facts, numbers, deadlines, requirements, or exceptions that do not \
appear in the passages — not even if you believe them to be true of HOAs in \
general. If the passages don't state it, don't say it.
- Do NOT generalize ("associations typically...", "usually...") or infer beyond \
what the passages say. Stick to what the cited text actually states.
- If the passages do not contain the governing policy for the question, say you \
can't find it in the sources and suggest consulting a licensed Maryland attorney \
or the relevant county office. A short honest answer beats a padded one.
- Cite the specific section for every substantive statement, using the \
breadcrumb shown with each passage.
- Frame the answer as "here is what the law says" and "here is the policy that \
applies", never as "you are allowed to" or "you cannot".
- Be concise and plain-language. Do not pad the answer with background context.
"""


def build_prompt(question: str, chunks: list[Chunk]) -> str:
    """Assemble the grounded prompt from the question and retrieved chunks.

    Each chunk is rendered with its breadcrumb so the model can cite it. The
    user's question is quoted in its own tagged block, not concatenated into the
    instruction, to blunt prompt injection.
    """
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f'<passage id="{i}" cite="{chunk.citation.breadcrumb}">\n{chunk.text}\n</passage>'
        )
    context = "\n".join(context_blocks) if context_blocks else "(no passages found)"

    return (
        f"{_SYSTEM_INSTRUCTION}\n"
        f"<context>\n{context}\n</context>\n\n"
        f"<question>\n{question}\n</question>\n\n"
        f"Answer:"
    )


def has_grounding(chunks: list[Chunk], scores: list[float], floor: float) -> bool:
    """Whether retrieval cleared the relevance floor.

    If the best rerank score is below the floor, the caller should refuse
    ("can't find it in the sources") rather than let the model improvise.
    """
    if not chunks or not scores:
        return False
    return max(scores) >= floor
