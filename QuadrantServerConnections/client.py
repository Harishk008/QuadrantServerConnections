# client.py
import requests
import base64
import streamlit as st # Import streamlit for error display

BASE_URL = "http://127.0.0.1:8000" # Use 127.0.0.1 consistent with server

def handle_request_error(response: requests.Response, operation: str):
    """Handles common request errors and displays messages in Streamlit."""
    try:
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.ConnectionError as e:
        st.error(f"Connection Error during {operation}: Cannot connect to the backend at {BASE_URL}. Is it running?")
        print(f"Connection Error: {e}")
        return None # Indicate failure
    except requests.exceptions.Timeout as e:
        st.error(f"Timeout Error during {operation}: The request timed out.")
        print(f"Timeout Error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error during {operation}: {e}")
        try:
            # Try to get more details from response if available
            detail = response.json().get("detail", response.text)
            st.error(f"Backend Detail: {detail}")
        except:
            pass # Ignore if response is not JSON or text is unavailable
        print(f"Request Error: {e}")
        return None

def list_collections():
    try:
        response = requests.get(f"{BASE_URL}/list_collections")
        result = handle_request_error(response, "listing collections")
        return result.get("collections", []) if result else [] # Return empty list on error
    except Exception as e:
        # Catch potential errors before handle_request_error if request itself fails badly
        st.error(f"Failed to initiate request to list collections: {e}")
        return []

def create_collection(collection_name):
    if not collection_name or not collection_name.strip():
        st.error("Collection name cannot be empty.")
        return None
    response = requests.post(f"{BASE_URL}/create_collection", json={"collection_name": collection_name})
    return handle_request_error(response, f"creating collection '{collection_name}'")

def delete_collection(collection_name):
    if not collection_name:
        st.error("No collection selected for deletion.")
        return None
    # Use json payload as expected by the refined endpoint
    response = requests.delete(f"{BASE_URL}/delete_collection", json={"collection_name": collection_name})
    return handle_request_error(response, f"deleting collection '{collection_name}'")

def upload_pdf(file, collection_name):
    if not file:
        st.error("No file selected.")
        return None
    if not collection_name:
        st.error("No collection selected for upload.")
        return None

    files = {'file': (file.name, file.getvalue(), file.type)} # Use getvalue() for bytes
    # Data needs to be passed separately for multipart/form-data
    data = {'collection_name': collection_name}
    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, data=data) # Endpoint is /upload/
        return handle_request_error(response, f"uploading PDF '{file.name}'")
    except Exception as e:
        st.error(f"Error during PDF upload request: {e}")
        return None


def query_collection(query, collection_name):
    if not query or not query.strip():
        st.warning("Please enter a query.")
        return None # Or maybe {"answer": "Please enter a query.", "images": []}
    if not collection_name:
        st.error("No collection selected for query.")
        return {"answer": "Error: No collection selected.", "images": []}

    payload = {
        "query": query,
        "collection_name": collection_name
    }
    print(f"--- Sending Query ---") # DEBUG
    print(f"URL: {BASE_URL}/query") # DEBUG
    print(f"Method: POST")          # DEBUG
    print(f"JSON Payload: {payload}") # DEBUG
    try:
        response = requests.post(f"{BASE_URL}/query", json=payload)
        result = handle_request_error(response, "querying collection")

        if result and "images" in result and isinstance(result["images"], list):
            # Decode base64 images if present
            decoded_images = []
            for img_str in result["images"]:
                try:
                    decoded_images.append(base64.b64decode(img_str))
                except Exception as decode_error:
                    print(f"Error decoding base64 image string: {decode_error}")
                    st.warning("Received an invalid image format from the backend.")
            result["images"] = decoded_images
        elif result:
             result["images"] = [] # Ensure images key exists even if empty

        # Provide default structure on error
        return result if result else {"answer": "Query failed. Check backend logs.", "images": []}

    except Exception as e:
        st.error(f"Error during query request: {e}")
        return {"answer": f"Error sending query: {e}", "images": []}