"""Retrieval thresholds.

Scores are the top-1 real cosine similarity (all-MiniLM-L6-v2) and the top-1
normalized BM25 score (score / most the query could score, 0-1; see
memory.vector_store._bm25_upper_bound). Values were chosen on the 24-golden
offline eval (evals/): every off-topic golden has top-1 cosine <= 0.26 and
BM25 <= 0.08, every sparse golden has cosine >= 0.45, and ds-02 is found only
by BM25 (cosine 0.28, BM25 0.45).
"""

# A retrieved chunk is used when its own cosine reaches RELEVANCE_THRESHOLD,
# or its own normalized BM25 score reaches STRONG_BM25 (keyword-only matches
# that embeddings miss, e.g. "data contracts").
RELEVANCE_THRESHOLD = 0.30
STRONG_BM25 = 0.30

# Coverage gate: draft only when the best chunk reaches COVERAGE_MIN_COSINE or
# the best BM25 hit reaches COVERAGE_MIN_BM25. Otherwise /generate returns
# status "low_coverage" (unless the request asks for a no-specifics post).
COVERAGE_MIN_COSINE = 0.30
COVERAGE_MIN_BM25 = 0.30

# Retrieval confidence: "high" when top-1 cosine reaches this; "medium" when
# the coverage gate passes; "low" otherwise.
HIGH_CONFIDENCE_COSINE = 0.45

# How many nearest sources a low-coverage response lists.
CLOSEST_SOURCES = 3
