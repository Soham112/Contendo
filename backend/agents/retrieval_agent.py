from pipeline.state import PipelineState
from memory.vector_store import query_similar

SYSTEM_PROMPT = """You are a retrieval agent. You surface semantically relevant chunks from a personal knowledge base to support content generation. Chunks are pre-filtered by cosine similarity — you receive only the most relevant ones."""


def retrieval_node(state: PipelineState) -> PipelineState:
    topic = state["topic"]
    context = state.get("context", "")

    query = topic
    if context:
        query = f"{topic}. {context}"

    chunks = query_similar(query, top_k=8, user_id=state.get("user_id", "default"))

    retrieved_texts = []
    for chunk in chunks:
        source_type = chunk.get("source_type", "")
        # Default unknown/missing source_type to "article" — safe assumption that
        # content came from an external source rather than the user's own notes.
        if not source_type or source_type == "unknown":
            source_type = "article"
        retrieved_texts.append(f"[source_type: {source_type}] {chunk['text']}")

    # Debug: print a sample so the attribution labels can be verified at runtime.
    if retrieved_texts:
        print(f"[retrieval_node] {len(retrieved_texts)} chunks retrieved. Sample: {retrieved_texts[0][:120]!r}")

    state["retrieved_chunks"] = retrieved_texts
    return state
