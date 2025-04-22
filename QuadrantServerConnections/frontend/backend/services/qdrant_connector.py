# services/qdrant_connector.py
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

class QdrantConnector:
    def __init__(self, url: str, api_key: str | None = None, vector_size: int = 1024):
        self.url = url
        self.api_key = api_key
        self.vector_size = vector_size
        self.client = QdrantClient(url=url, api_key=api_key)

    def get_client(self):
        return self.client

    def ensure_collection(self, collection_name: str):
        try:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=rest.VectorParams(size=self.vector_size, distance=rest.Distance.COSINE),
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
