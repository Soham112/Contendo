from pipeline.state import PipelineState
from memory.vector_store import query_similar

SYSTEM_PROMPT = """You are a retrieval agent. You surface semantically relevant chunks from a personal knowledge base to support content generation. Chunks are pre-filtered by cosine similarity — you receive only the most relevant ones."""


def retrieval_node(state: PipelineState) -> PipelineState:
    topic = state["topic"]
    context = state.get("context", "")

    query = topic
    if context:
        query = f"{topic}. {context}"

    chunks = query_similar(query, top_k=8)

    retrieved_texts = [chunk["text"] for chunk in chunks]
    state["retrieved_chunks"] = retrieved_texts
    return state
