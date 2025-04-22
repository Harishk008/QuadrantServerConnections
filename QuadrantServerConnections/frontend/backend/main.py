# main.py
from fastapi import FastAPI, UploadFile, HTTPException
from services.qdrant_connector import QdrantConnector
from services.embedder import Embedder
from services.pdf_processor import PDFProcessor
from services.text_chunker import TextChunker
from services.document_uploader import DocumentUploader
import os

app = FastAPI()

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/")
EMBED_MODEL = "mxbai-embed-large:latest"
COLLECTION = "my_docs"
IMAGE_DIR = "./stored_images"

# Init
qdrant = QdrantConnector(url=QDRANT_URL)
embedder = Embedder(EMBED_MODEL, OLLAMA_URL)
chunker = TextChunker()
pdf_processor = PDFProcessor(IMAGE_DIR)
uploader = DocumentUploader(qdrant, embedder, chunker, pdf_processor, COLLECTION)

@app.post("/upload/")
async def upload_pdf(file: UploadFile, collection_name: str | None = None):
    if "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files allowed.")
    contents = await file.read()
    return uploader.upload(contents, file.filename, collection_name)
