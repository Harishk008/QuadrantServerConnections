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
from langchain_ollama import OllamaLLM

app = FastAPI()

# --- Configuration ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://ai-lab.sagitec.com:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ai-lab.sagitec.com:11434/")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma3:12b")
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

# --- Initialize the LLM ---
try:
    llm = OllamaLLM(model=LLM_MODEL, base_url=OLLAMA_URL)
    print(f"LLM initialized with model: {LLM_MODEL} from {OLLAMA_URL}")
    # Optional: Test LLM with a simple invoke on startup
    # llm.invoke("Why is the sky blue?")
    # print("LLM test invoke successful.")
except Exception as e:
    print(f"!!! ERROR initializing LLM: {e} !!!")
    print("!!! Query augmentation will likely fail. Check Ollama status and model name. !!!")
    llm = None # Set llm to None if initialization fails

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
# async def query_endpoint(request: Request, payload: QueryPayload): # Add async if using await llm.ainvoke
async def query_endpoint(payload: QueryPayload): # Keep sync for now if llm.invoke is sync
    if not llm:
         raise HTTPException(status_code=500, detail="LLM (for query augmentation) is not initialized. Check backend logs.")

    try:
        query_text = payload.query
        collection_name = payload.collection_name
        print(f"Received query for collection '{collection_name}': {query_text}")

        # 1. Embed the query
        query_vector = embedder.embed(query_text)

        # 2. Search Qdrant
        # Use query_points instead of search
        search_result = qdrant.get_client().query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=5,  # Retrieve maybe a few more chunks for better context
            with_payload=True
        )
        print(f"Qdrant search returned {len(search_result.points)} results.")


        # 3. Process results for context and images
        context_texts = []
        retrieved_image_paths = set()

        # Handle both search_result structure (older) and query_points result structure (newer)
        hits = []
        if hasattr(search_result, 'points'): # For query_points result
            hits = search_result.points
        elif isinstance(search_result, list): # For older search result
            hits = search_result

        for hit in hits:
            payload_data = hit.payload
            if payload_data:
                chunk_text = payload_data.get("text")
                if chunk_text:
                    context_texts.append(chunk_text)

                image_paths_json = payload_data.get("associated_image_paths", "[]")
                try:
                    image_paths = json.loads(image_paths_json)
                    for img_path in image_paths:
                        # Basic validation - adapt path if needed based on how it's stored
                        potential_path = img_path
                        if not os.path.isabs(img_path) and not img_path.startswith(IMAGE_DIR):
                             potential_path = os.path.join(IMAGE_DIR, os.path.basename(img_path))

                        if os.path.exists(potential_path):
                             retrieved_image_paths.add(potential_path)
                        # else:
                        #      print(f"Debug: Image path {img_path} (resolved to {potential_path}) not found.")

                except json.JSONDecodeError:
                    print(f"Warning: Could not decode image paths JSON: {image_paths_json}")

        # 4. Generate Augmented Answer using LLM (if context found)
        final_answer = "No relevant information found in the documents." # Default answer

        if context_texts:
            print("Context found, invoking LLM for augmentation...")
            combined_context = "\n\n---\n\n".join(context_texts)

            # --- Basic Prompt Template ---
            prompt = f"""Based *only* on the following context retrieved from documents, please provide a concise answer to the user's question. Do not use any prior knowledge. If the context does not contain the answer, say so.

                        Context:
                        {combined_context}

                        ---
                        User Question: {query_text}
                        ---

                        Answer:"""

            try:
                # Use the initialized LLM instance
                print("Sending prompt to LLM...")
                # print(f"Prompt:\n{prompt}") # Uncomment to debug the exact prompt
                llm_response = llm.invoke(prompt)
                print("LLM response received.")
                final_answer = llm_response.strip() # Use the LLM's response
            except Exception as e:
                print(f"!!! ERROR invoking LLM: {e} !!!")
                final_answer = "Error generating answer from context. Using raw context instead.\n\n" + combined_context # Fallback

        else:
             print("No relevant text context found in Qdrant results.")


        # 5. Load and encode images
        encoded_images: List[str] = []
        print(f"Attempting to load {len(retrieved_image_paths)} unique image paths...")
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

        print(f"Returning answer and {len(encoded_images)} images.")
        return {"answer": final_answer, "images": encoded_images}

    except Exception as e:
        print(f"Error during query processing: {e}")
        # Include traceback in logs for detailed debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

if __name__ == "__main__": 
    print("Starting FastAPI server...")
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Ollama URL: {OLLAMA_URL}")
    print(f"Embedding Model: {EMBED_MODEL}")
    #print(f"Embedding Dimension: {EMBEDDING_DIM}")
    print(f"Image Directory: {IMAGE_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=8000)