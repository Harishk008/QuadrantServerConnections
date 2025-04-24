# main.py
from fastapi import FastAPI, UploadFile, HTTPException, Form, Request
from pydantic import BaseModel
from services.qdrant_connector import QdrantConnector
from services.embedder import Embedder
from services.pdf_processor import PDFProcessor
from services.text_chunker import TextChunker
from services.document_uploader import DocumentUploader
import os
import uvicorn
import json
import base64
from typing import List
import traceback

# --- Import Ollama LLM ---
from langchain_ollama import OllamaLLM

app = FastAPI()

# --- Configuration ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://ai-lab.sagitec.com:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ai-lab.sagitec.com:11434/")
EMBED_MODEL = "mxbai-embed-large:latest"
EMBEDDING_DIM = 1024
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-r1:8b")
DEFAULT_COLLECTION = "my_docs"
IMAGE_DIR = "./stored_images"
# --- Add Score Threshold Configuration ---
# Adjust this value based on testing. Higher means stricter relevance required for images.
# Assumes Cosine similarity (higher is better).
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.75"))
# ---
# --- End Configuration ---

# --- Initialization ---
os.makedirs(IMAGE_DIR, exist_ok=True)

qdrant = QdrantConnector(url=QDRANT_URL, vector_size=EMBEDDING_DIM)
embedder = Embedder(EMBED_MODEL, OLLAMA_URL)
chunker = TextChunker()
pdf_processor = PDFProcessor(IMAGE_DIR)
uploader = DocumentUploader(qdrant, embedder, chunker, pdf_processor, DEFAULT_COLLECTION)

try:
    llm = OllamaLLM(model=LLM_MODEL, base_url=OLLAMA_URL)
    print(f"LLM initialized with model: {LLM_MODEL} from {OLLAMA_URL}")
except Exception as e:
    print(f"!!! ERROR initializing LLM: {e} !!!")
    llm = None

# --- End Initialization ---

# --- Pydantic Models ---
class CollectionNamePayload(BaseModel):
    collection_name: str

class QueryPayload(BaseModel):
    query: str
    collection_name: str
# --- End Pydantic Models ---


# --- API Endpoints ---
# (Keep /upload, /list_collections, /create_collection, /delete_collection as they are)
@app.post("/upload/")
async def upload_pdf_endpoint(
    collection_name: str = Form(...),
    file: UploadFile = UploadFile(...)
):
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files allowed.")
    contents = await file.read()
    return uploader.upload(contents, file.filename, collection_name)

@app.get("/list_collections")
def list_collections_endpoint():
    try:
        collections_response = qdrant.get_client().get_collections()
        collection_names = [col.name for col in collections_response.collections]
        return {"collections": collection_names}
    except Exception as e:
        print(f"Error listing collections: {e}")
        if "connection refused" in str(e).lower() or "failed to connect" in str(e).lower():
             raise HTTPException(status_code=503, detail=f"Could not connect to Qdrant at {QDRANT_URL}. Is it running?")
        return {"collections": []}

@app.post("/create_collection")
def create_collection_endpoint(payload: CollectionNamePayload):
    try:
        qdrant.ensure_collection(payload.collection_name)
        return {"status": "created", "collection_name": payload.collection_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")

@app.delete("/delete_collection")
def delete_collection_endpoint(payload: CollectionNamePayload):
    try:
        qdrant.get_client().delete_collection(collection_name=payload.collection_name)
        return {"status": "deleted", "collection_name": payload.collection_name}
    except Exception as e:
        error_message = str(e)
        status_code = 500
        if "not found" in error_message.lower() or "doesn't exist" in error_message.lower():
            status_code = 404
            detail = f"Collection '{payload.collection_name}' not found."
        else:
            detail = f"Failed to delete collection: {error_message}"
        raise HTTPException(status_code=status_code, detail=detail)


@app.post("/query")
async def query_endpoint(payload: QueryPayload):
    if not llm:
         raise HTTPException(status_code=500, detail="LLM (for query augmentation) is not initialized. Check backend logs.")

    # Main try block for the whole endpoint logic
    try:
        query_text = payload.query
        collection_name = payload.collection_name
        print(f"Received query for collection '{collection_name}': {query_text}")

        # 1. Embed the query
        query_vector = embedder.embed(query_text)

        # 2. Search Qdrant
        try:
            search_result = qdrant.get_client().query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=5,
                with_payload=True,
                with_vectors=False
            )
        except Exception as qdrant_error:
            print(f"!!! Qdrant query_points failed: {qdrant_error}")
            traceback.print_exc()
            raise HTTPException(status_code=503, detail=f"Failed to query Qdrant: {qdrant_error}")

        # Check results structure
        num_results = 0
        if hasattr(search_result, 'points'):
            num_results = len(search_result.points)
            print(f"Qdrant search returned QueryResponse with {num_results} results.")
        elif isinstance(search_result, list):
            num_results = len(search_result)
            print(f"Qdrant search returned a direct list with {num_results} results.")
        else:
            print(f"Qdrant search returned unexpected type: {type(search_result)}")

        # 3. Process results for context and images, applying threshold for images
        context_texts = []
        retrieved_image_paths = set()

        hits = []
        if hasattr(search_result, 'points'):
            hits = search_result.points
        elif isinstance(search_result, list):
            hits = search_result

        print(f"Applying image relevance threshold: {SCORE_THRESHOLD}")
        for hit in hits:
            try:
                payload_data = hit.payload
                score = hit.score
                print(f"  - Processing Hit ID: {hit.id}, Score: {score:.4f}")

                if payload_data:
                    chunk_text = payload_data.get("text")
                    if chunk_text:
                        context_texts.append(chunk_text)

                    if score >= SCORE_THRESHOLD:
                        print(f"    - Score meets threshold, processing images for this chunk.")
                        image_paths_json = payload_data.get("associated_image_paths", "[]")
                        try:
                            image_paths = json.loads(image_paths_json)
                            for img_path in image_paths:
                                potential_path = img_path
                                if not os.path.isabs(img_path) and not img_path.startswith(IMAGE_DIR):
                                     potential_path = os.path.join(IMAGE_DIR, os.path.basename(img_path))
                                if os.path.exists(potential_path):
                                     retrieved_image_paths.add(potential_path)
                        except json.JSONDecodeError:
                            print(f"    - Warning: Could not decode image paths JSON: {image_paths_json}")
                    else:
                         print(f"    - Score below threshold, skipping images for this chunk.")
                else:
                    print(f"  - Warning: Hit ID {hit.id} has no payload.")
            except AttributeError as ae:
                 print(f"  - Error processing hit: {ae}. Hit details: {hit}")
                 continue

        # 4. Generate Augmented Answer using LLM (if context found)
        final_answer = "No relevant information found in the documents." # Default

        if context_texts:
            print("Context found, invoking LLM for augmentation...")
            combined_context = "\n\n---\n\n".join(context_texts)
            prompt = f"""Based *only* on the following context retrieved from documents, please provide a concise answer to the user's question. Do not use any prior knowledge. If the context does not contain the answer, say so.

            Context:
            {combined_context}

            ---
            User Question: {query_text}
            ---

            Answer:"""

            # --- Correctly indented try/except INSIDE 'if context_texts:' ---
            try:
                print("Sending prompt to LLM...")
                # Use the 'llm' instance initialized earlier
                llm_response = llm.invoke(prompt)
                print("LLM response received.")
                final_answer = llm_response.strip() # Overwrite default answer
            except Exception as e:
                print(f"!!! ERROR invoking LLM: {e} !!!")
                # Fallback answer if LLM fails
                final_answer = "Error generating answer from context. Using raw context instead.\n\n" + combined_context
            # --- End of correctly indented try/except ---

        else: # This else corresponds to 'if context_texts:'
             print("No relevant text context found in Qdrant results.")
             # final_answer remains the default "No relevant information..."

        # 5. Load and encode images (only those that met the threshold)
        # --- Correctly indented block, aligned with Step 4 start ---
        encoded_images: List[str] = []
        print(f"Attempting to load {len(retrieved_image_paths)} unique image paths that met the score threshold...")
        for img_path in retrieved_image_paths:
            try:
                if os.path.exists(img_path):
                    with open(img_path, "rb") as image_file:
                        image_data = image_file.read()
                        encoded_string = base64.b64encode(image_data).decode('utf-8')
                        encoded_images.append(encoded_string)
                else:
                     print(f"Warning: Image file not found at final path check: {img_path}")
            except Exception as e:
                print(f"Error reading or encoding image {img_path}: {e}")
        # --- End of correctly indented block ---

        print(f"Returning answer and {len(encoded_images)} images.")
        return {"answer": final_answer, "images": encoded_images}

    # This except corresponds to the main 'try' at the start of the function
    except Exception as e:
        print(f"Error during query processing: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

# Rest of the file should be okay if it followed standard Python indentation

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting FastAPI server...")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Embedding Model: {EMBED_MODEL} (Dim: {EMBEDDING_DIM})")
    print(f"LLM Model for Augmentation: {LLM_MODEL}")
    print(f"Image Directory: {IMAGE_DIR}")
    print(f"Image Score Threshold: {SCORE_THRESHOLD}") # Print threshold at startup
    if not llm:
        print("WARNING: LLM failed to initialize. Query augmentation disabled.")
    uvicorn.run(app, host="127.0.0.1", port=8000)