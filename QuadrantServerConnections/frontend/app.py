# app.py
import streamlit as st
from api.client import (
    upload_pdf, list_collections, create_collection,
    delete_collection, query_collection
)

st.set_page_config(page_title="DocuQuery", layout="wide")
st.title("📄 DocuQuery: Document Understanding with Text + Images")

tab1, tab2, tab3 = st.tabs(["📁 Collection Manager", "⬆️ Upload PDF", "🔍 Query Collection"])

with tab1:
    st.header("📁 Manage Collections")
    # List existing collections
    collections = list_collections()
    st.write("### Existing Collections:")
    st.write(collections)

    # Create collection
    new_collection = st.text_input("New Collection Name")
    if st.button("Create Collection"):
        create_collection(new_collection)
        st.success(f"Collection '{new_collection}' created!")

    # Delete collection
    del_collection = st.selectbox("Delete Collection", collections)
    if st.button("Delete Collection"):
        delete_collection(del_collection)
        st.warning(f"Collection '{del_collection}' deleted.")

with tab2:
    st.header("⬆️ Upload PDF")
    uploaded_file = st.file_uploader("Choose a PDF", type="pdf")
    collection_to_upload = st.selectbox("Select Collection", list_collections())
    if uploaded_file and st.button("Upload"):
        upload_pdf(uploaded_file, collection_to_upload)
        st.success("PDF uploaded and processed successfully!")

with tab3:
    st.header("🔍 Query Collection")
    collection_to_query = st.selectbox("Select Collection", list_collections())
    user_query = st.text_input("Ask a question")
    if st.button("Query"):
        if user_query:
            response = query_collection(user_query, collection_to_query)
            st.markdown("### 📌 Response:")
            st.write(response["answer"])
            if response.get("images"):
                st.image(response["images"], caption="Retrieved Images", use_column_width=True)
        else:
            st.warning("Please enter a query first.")
