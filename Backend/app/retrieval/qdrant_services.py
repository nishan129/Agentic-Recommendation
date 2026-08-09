
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


VECTOR_SIZE = 1024

def get_client() -> QdrantClient:
    return QdrantClient(url='http://qdrant:6333/', timeout=30)

def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}

    if "get" not in existing:
        client.create_collection(
            collection_name="get",
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        )

def upsert_chunks(products: list[dict], embeddings: list[list[float]]):
    ensure_collection()
    client = get_client()
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
    client.upsert(collection_name="get", points=points)

def search(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    client = get_client()
    results = client.query_points(
        collection_name="get",
        query=query_embedding,
        limit=top_k,
        with_payload=True,
    ).points

    return [
        {
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "price": p.price,
                "rating": p.rating,
                "tags": p.tags,
            }
        for p in results
    ]