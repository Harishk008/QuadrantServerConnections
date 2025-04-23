import requests
import base64

BASE_URL = "http://localhost:8000"

def list_collections():
    try:
        response = requests.get(f"{BASE_URL}/list_collections")
        return response.json().get("collections", [])
    except Exception as e:
        return [f"Error: {e}"]

def create_collection(collection_name):
    return requests.post(f"{BASE_URL}/create_collection", json={"collection_name": collection_name}).json()

def delete_collection(collection_name):
    return requests.delete(f"{BASE_URL}/delete_collection", json={"collection_name": collection_name}).json()

def upload_pdf(file, collection_name):
    files = {'file': (file.name, file, 'application/pdf')}
    data = {'collection_name': collection_name}
    return requests.post(f"{BASE_URL}/upload_pdf", files=files, data=data).json()

def query_collection(query, collection_name):
    payload = {
        "query": query,
        "collection_name": collection_name
    }
    try:
        response = requests.post(f"{BASE_URL}/query", json=payload)
        result = response.json()
        
        # If images exist, decode base64 to bytes
        if "images" in result:
            result["images"] = [base64.b64decode(img_str) for img_str in result["images"]]
        return result
    except Exception as e:
        return {"answer": f"Error: {e}"}
