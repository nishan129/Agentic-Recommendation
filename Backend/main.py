from app.retrieval.qdrant_services import upsert_chunks
from app.retrieval.embeddings import mesh_embed
from app.utils.product_data import create_text


product = {
    "id":int(223423242),
   "title": "Advanced Data Science and Model Deployment",
   "description": "A comprehensive guide to advanced data science techniques and model deployment strategies.",
   "category": "Data Science",
   "price": 49.99,
    "rating": 4.8,
    "tags": ["data science", "machine learning", "model deployment", "advanced techniques"]
}

text = create_text(product)
embeddings = mesh_embed(text)
print("Embeddings:", embeddings)
upsert_chunks([product], embeddings)
print("OK")