from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchAny,
)

VECTOR_SIZE = 1024
COLLECTION_NAME = "get"


def get_client() -> QdrantClient:
    return QdrantClient(
        url="http://qdrant:6333/",
        timeout=30,
    )


def ensure_collection() -> None:
    client = get_client()

    existing = {
        c.name
        for c in client.get_collections().collections
    }

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )


def upsert_chunks(
    products: list[dict],
    embeddings: list[list[float]],
):
    ensure_collection()

    client = get_client()

    points = [
        PointStruct(
            id=product["id"],
            vector=vector,
            payload={
                "product_id": product["id"],
                "name": product["title"],
                "category": product["category"],
                "description": product["description"],
                "price": product["price"],
                "rating": product["rating"],
                "tags": product["tags"],
            },
        )
        for product, vector in zip(
            products,
            embeddings,
            strict=True,
        )
    ]

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )


def search(
    query_embedding: list[float],
    top_k: int = 5,
    exclude_ids: list[str] | None = None,
    active_only: bool = True,
) -> list[dict]:

    client = get_client()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding,
        limit=top_k,
        with_payload=True,
    ).points

    # Exclude already interacted products in Python
    if exclude_ids:
        exclude_ids = {
            str(product_id).replace("-", "")
            for product_id in exclude_ids
        }

        results = [
            p
            for p in results
            if str(p.payload.get("product_id", "")).replace("-", "")
            not in exclude_ids
        ]

    return [
    {
        "product_id": p.payload.get("product_id"),
        "name": p.payload.get("name"),
        "category": p.payload.get("category"),
        "description": p.payload.get("description"),
        "price": p.payload.get("price"),
        "rating": p.payload.get("rating"),
        "tags": p.payload.get("tags"),
        "similarity_score": p.score,
    }
    for p in results
]