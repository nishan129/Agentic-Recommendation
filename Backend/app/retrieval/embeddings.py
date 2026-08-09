import logfire
from meshapi import EmbeddingsParams
from meshapi import MeshAPI


EMBEDDING_MODEL = "openai/text-embedding-3-small"
MESHAPI_BASE_URL = "https://api.meshapi.ai"
EMBEDDING_DIMENSIONS = 1024

client = MeshAPI(base_url=MESHAPI_BASE_URL, token='rsk_01KZK6QCFTWYEADYHEQEABRAQ0')

def mesh_embed(texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(
        EmbeddingsParams(model=EMBEDDING_MODEL, input=texts, dimensions=EMBEDDING_DIMENSIONS)
    )
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]