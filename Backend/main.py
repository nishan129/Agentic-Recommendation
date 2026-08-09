from app.retrieval.qdrant_services import upsert_chunks
from app.retrieval.embeddings import mesh_embed
from app.utils.product_data import create_text
import uuid

product_dict = {
    "id":uuid.uuid4().hex,
   "title": " Data Science and Model Deployment",
   "description": "A comprehensive guide to advanced data science techniques and model deployment strategies.",
   "category": "Data Science",
   "price": float(49.99) if 49.99 is not None else None,
    "rating": 4.8,
    "tags": ["data science", "machine learning", "model deployment", "advanced techniques"] or []
}


text = create_text(product_dict)
embeddings = mesh_embed(text)
print("Embeddings:", embeddings)
upsert_chunks([product_dict], embeddings)
print("OK")

