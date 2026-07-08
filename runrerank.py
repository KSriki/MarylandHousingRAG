"""Isolate the reranker: score an obvious match vs an obvious non-match.
If the obvious match doesn't score high, the reranker itself is the problem.
"""

from FlagEmbedding import FlagReranker

m = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

q = "Can my HOA stop me from installing solar panels?"
good = (
    "A homeowner association may not impose or enforce any covenant that "
    "prohibits or restricts the installation of a solar collector system."
)
bad = "The implied warranties provided in this section may not be excluded."

# Try both normalized and raw to see what's happening
print("normalize=True:")
print("  good match:", m.compute_score([[q, good]], normalize=True))
print("  bad match: ", m.compute_score([[q, bad]], normalize=True))
print("normalize=False (raw logits):")
print("  good match:", m.compute_score([[q, good]], normalize=False))
print("  bad match: ", m.compute_score([[q, bad]], normalize=False))
