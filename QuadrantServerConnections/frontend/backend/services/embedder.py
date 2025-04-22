# services/embedder.py
from langchain_ollama import OllamaEmbeddings

class Embedder:
    def __init__(self, model: str, base_url: str):
        self.embedding_model = OllamaEmbeddings(model=model, base_url=base_url)

    def embed(self, text: str):
        return self.embedding_model.embed_query(text)
