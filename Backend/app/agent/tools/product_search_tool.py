"""
Product Search Tool — the agent's connection to the vector store. This is
the piece that actually does "course similarity search": it embeds a
query built from the agent's reasoning step and asks Qdrant for the
nearest products by cosine similarity, filtered to exclude what the user
has already interacted with.

This tool never touches Postgres — vector search is the whole point of
routing through here instead of ProductRepository.list_products, which
only does exact category/price matching, not semantic similarity (e.g.
someone repeatedly viewing "agentic AI" content should surface a course
titled "Building Autonomous LLM Systems" even if neither the title nor
category literally contains the words "agentic AI").
"""
from dataclasses import dataclass

from app.retrieval.embeddings import mesh_embed
from app.retrieval.qdrant_services import search 


@dataclass
class SimilarProduct:
    product_id: str
    title: str
    category: str | None
    description: str | None
    price: float | None
    rating: float | None
    tags: list[str]
    similarity_score: float


def search_similar_products(
    query_text: str,
    top_k: int = 8,
    exclude_ids: list[str] | None = None,
) -> list[SimilarProduct]:
    """Embed `query_text` (typically the agent's synthesized interest
    summary, not the raw event log) and return the top-k most similar
    products from Qdrant, ranked by cosine similarity.

    This is a synchronous, blocking call (both mesh_embed and the Qdrant
    client are sync) — call it from a BackgroundTask or via
    asyncio.to_thread if called from inside a request handler's hot path.
    """
    if not query_text.strip():
        return []

    query_vector = mesh_embed([query_text])[0]
    raw_results = search(query_vector, top_k=top_k, exclude_ids=exclude_ids, active_only=True)

    return [
        SimilarProduct(
            product_id=r["product_id"],
            title=r["name"],
            category=r["category"],
            description=r["description"],
            price=r["price"],
            rating=r["rating"],
            tags=r["tags"],
            similarity_score=r["similarity_score"],
        )
        for r in raw_results
    ]
