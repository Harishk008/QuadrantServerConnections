# main.py
from fastapi import FastAPI, UploadFile, HTTPException, Form
from pydantic import BaseModel # Import BaseModel for request body validation
from services.qdrant_connector import QdrantConnector
from services.embedder import Embedder
from services.pdf_processor import PDFProcessor
from services.text_chunker import TextChunker
from services.document_uploader import DocumentUploader
import os
import uvicorn
import json # Needed for loading image paths
import base64 # Needed for encoding images
from typing import List # For type hinting

app = FastAPI()

# --- Configuration ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://ai-lab.sagitec.com:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ai-lab.sagitec.com:11434/")
EMBED_MODEL = "mxbai-embed-large:latest" # Make sure this model is available in Ollama
# Check model dimension, mxbai-embed-large is likely 1024, but verify if needed
EMBEDDING_DIM = 1024 # Typically 1024 for mxbai-embed-large
DEFAULT_COLLECTION = "my_docs" # Changed default collection name slightly
IMAGE_DIR = "./stored_images"
# --- End Configuration ---

# --- Initialization ---
# Ensure IMAGE_DIR exists before PDFProcessor uses it
os.makedirs(IMAGE_DIR, exist_ok=True)

qdrant = QdrantConnector(url=QDRANT_URL, vector_size=EMBEDDING_DIM)
embedder = Embedder(EMBED_MODEL, OLLAMA_URL)
chunker = TextChunker()
pdf_processor = PDFProcessor(IMAGE_DIR)
# Pass the correct default collection name
uploader = DocumentUploader(qdrant, embedder, chunker, pdf_processor, DEFAULT_COLLECTION)
# --- End Initialization ---

# --- Pydantic Models for Request Bodies ---
class CollectionNamePayload(BaseModel):
    collection_name: str

class QueryPayload(BaseModel):
    query: str
    collection_name: str
# --- End Pydantic Models ---


@app.post("/upload/")
async def upload_pdf_endpoint( # Renamed function to avoid conflict with client function name
    collection_name: str = Form(...), # Use Form for data alongside file
    file: UploadFile = UploadFile(...)
):
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files allowed.")
    contents = await file.read()
    # Use the uploader instance
    return uploader.upload(contents, file.filename, collection_name)


@app.get("/list_collections")
def list_collections_endpoint(): # Renamed function
    try:
        collections_response = qdrant.get_client().get_collections()
        # Extract collection names
        collection_names = [col.name for col in collections_response.collections]
        return {"collections": collection_names}
    except Exception as e:
        print(f"Error listing collections: {e}")
        # Return empty list on error, client expects a list
        return {"collections": []}


@app.post("/create_collection")
def create_collection_endpoint(payload: CollectionNamePayload): # Use Pydantic model
    try:
        qdrant.ensure_collection(payload.collection_name)
        return {"status": "created", "collection_name": payload.collection_name}
    except Exception as e:
        # Provide more context on error
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


@app.delete("/delete_collection")
def delete_collection_endpoint(payload: CollectionNamePayload): # Use Pydantic model
    try:
        # Check if collection exists before attempting deletion
        # Note: Qdrant client might throw error if it doesn't exist, which is handled below
        qdrant.get_client().delete_collection(collection_name=payload.collection_name)
        return {"status": "deleted", "collection_name": payload.collection_name}
    except Exception as e:
         # Improve error handling for non-existent collections or other issues
        error_message = str(e)
        status_code = 500
        if "not found" in error_message.lower() or "doesn't exist" in error_message.lower():
            status_code = 404
            detail = f"Collection '{payload.collection_name}' not found."
        else:
            detail = f"Failed to delete collection: {error_message}"
        raise HTTPException(status_code=status_code, detail=detail)


@app.post("/query")
def query_endpoint(payload: QueryPayload): # Use Pydantic model
    try:
        query_text = payload.query
        collection_name = payload.collection_name

        # 1. Embed the query
        query_vector = embedder.embed(query_text)

        # 2. Search Qdrant
        search_result = qdrant.get_client().search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3,  # Retrieve top 3 results
            with_payload=True  # Ensure payload (metadata) is returned
        )

        # 3. Process results
        context_texts = []
        retrieved_image_paths = set() # Use set to avoid duplicate image paths

        for hit in search_result:
            payload_data = hit.payload
            if payload_data:
                context_texts.append(payload_data.get("text", ""))
                # Image paths are stored as a JSON string, parse it
                image_paths_json = payload_data.get("associated_image_paths", "[]")
                try:
                    image_paths = json.loads(image_paths_json)
                    # Add valid paths relative to IMAGE_DIR
                    for img_path in image_paths:
                         # Only add if it seems like a valid path within our storage
                         if img_path.startswith(IMAGE_DIR.replace("./","").replace(".\\", "")):
                            retrieved_image_paths.add(img_path)
                         elif not os.path.isabs(img_path): # Handle relative paths stored differently
                             potential_path = os.path.join(IMAGE_DIR, os.path.basename(img_path))
                             if os.path.exists(potential_path):
                                 retrieved_image_paths.add(potential_path)

                except json.JSONDecodeError:
                    print(f"Warning: Could not decode image paths JSON: {image_paths_json}")

        # Combine context for a basic answer (can be enhanced with LLM later)
        answer = "\n---\n".join(context_texts) if context_texts else "No relevant information found."

        # 4. Load and encode images
        encoded_images: List[str] = []
        for img_path in retrieved_image_paths:
            try:
                # Construct full path if needed (though paths should be stored correctly now)
                full_img_path = img_path # Paths should be stored directly usable
                if os.path.exists(full_img_path):
                    with open(full_img_path, "rb") as image_file:
                        image_data = image_file.read()
                        encoded_string = base64.b64encode(image_data).decode('utf-8')
                        encoded_images.append(encoded_string)
                else:
                     print(f"Warning: Image file not found at {full_img_path}")
            except Exception as e:
                print(f"Error reading or encoding image {img_path}: {e}")

        return {"answer": answer, "images": encoded_images}

    except Exception as e:
        print(f"Error during query processing: {e}")
        # Provide detailed error back if needed, or a generic message
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


if __name__ == "__main__":
    print("Starting FastAPI server...")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Embedding Model: {EMBED_MODEL}")
    #print(f"Embedding Dimension: {EMBEDDING_DIM}")
    print(f"Image Directory: {IMAGE_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=8000)