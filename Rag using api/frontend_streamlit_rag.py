import streamlit as st
import requests

FASTAPI_URL = "http://127.0.0.1:8200"  # Adjust this URL if running FastAPI on a different port

st.title(" Chat with Your Documents")

# File Upload
st.header("Upload a PDF")
uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
    response = requests.post(f"{FASTAPI_URL}/upload/", files=files)
    if response.status_code == 200:
        result = response.json()
        if result["chunks_stored"] > 0:
            st.success(f"File uploaded and processed successfully and the total chunks created is {result['chunks_stored']}")
        else:
            st.warning("File is already processed and stored in the ChromaDB.")
    else:
        st.error("Failed to upload file.")

# Query Section
st.header("Ask a Question")
query_text = st.text_input("Enter your query:")

if st.button("Ask"):  # Query only when button is clicked
    if query_text:
        response = requests.get(f"{FASTAPI_URL}/query/", params={"query": query_text})
        if response.status_code == 200:
            result = response.json()
            st.subheader("Answer:")
            st.write(result["answer"], result["scores"])
            
            with st.expander("Retrieved Context"):
                st.write(result["retrieved_context"])
        else:
            st.error("Error fetching response from FastAPI server.")
    else:
        st.warning("Please enter a query.")
        
# View All Stored Documents
if st.button("View All Documents"):
    response = requests.get(f"{FASTAPI_URL}/view_all/")
    if response.status_code == 200:
        result = response.json()
        st.subheader("Stored Documents:")
        for i, doc in enumerate(result["documents"]):
            st.write(f"**Document {i+1}:**")
            st.write(f"**Text:** {doc}")
            st.write(f"**Metadata:** {result['metadatas'][i]}")
            st.write("---")  # Separator for readability
        st.write(f"metadata: {result['metadatas']} \n")
    else:
        st.error("Error fetching stored documents from FastAPI server.")

# Delete All Documents
if st.button("Delete All Documents"):
    response = requests.delete(f"{FASTAPI_URL}/delete_all/")
    if response.status_code == 200:
        st.success(response.json()["message"])
    else:
        st.error("Error deleting documents from FastAPI server.")
