from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
import logfire

VECTOR_SIZE = 1024

def get_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url='http://localhost:6333/', timeout=30)

async def ensure_collection() -> None:
    client = get_client()
    try:
        collections = await client.get_collections()
        existing = {c.name for c in collections.collections}

        if "get" not in existing:
            await client.create_collection(
                collection_name="get",
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
    finally:
        await client.close()

async def upsert_chunks(products: list[dict], embeddings: list[list[float]]):
    logfire.info(f"Upserting {len(products)} products into Qdrant")
    await ensure_collection()
    client = get_client()
    try:
        points = [
            PointStruct(
                id=product['id'],
                vector=vector,
                payload={
                    "product_id": product['id'],
                    "name": product['title'],
                    "category": product['category'],
                    "description": product['description'],
                    "price": product['price'],
                    "rating": product['rating'],
                    "tags": product['tags'],
                }
            )
            for product, vector in zip(products, embeddings, strict=True)
        ]
        await client.upsert(collection_name="get", points=points)
    finally:
        await client.close()

async def search(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    client = get_client()
    try:
        result = await client.query_points(
            collection_name="get",
            query=query_embedding,
            limit=top_k,
            with_payload=True,
        )
        points = result.points

        return [
            {
                "product_id": p.id,
                "name": p.payload.get("name"),
                "category": p.payload.get("category"),
                "description": p.payload.get("description"),
                "price": p.payload.get("price"),
                "rating": p.payload.get("rating"),
                "tags": p.payload.get("tags"),
            }
            for p in points
        ]
    finally:
        await client.close()