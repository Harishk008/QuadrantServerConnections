# app.py
import streamlit as st
from client import (
    upload_pdf, list_collections, create_collection,
    delete_collection, query_collection
)
import time # For potential sleep/delay if needed

# --- Session State Initialization ---
if 'collections' not in st.session_state:
    st.session_state.collections = list_collections()
    if not st.session_state.collections:
        st.toast("No collections found or failed to connect to backend.")

def refresh_collections():
    """Function to refresh the list of collections."""
    st.session_state.collections = list_collections()
    if not st.session_state.collections:
         st.toast("Refreshed: No collections found or failed to connect.")
    else:
        st.toast("Collections list refreshed.")
    # Force rerun to update widgets that depend on the collection list
    # st.rerun() # Use rerun cautiously, can cause loops if not managed well

# --- UI Setup ---
st.set_page_config(page_title="DocuQuery", layout="wide")
st.title("📄 DocuQuery: Document Understanding with Text + Images")

# Use session state for collection list
collections_list = st.session_state.get('collections', [])

tab1, tab2, tab3 = st.tabs(["📁 Collection Manager", "⬆️ Upload PDF", "🔍 Query Collection"])

# --- Tab 1: Collection Manager ---
with tab1:
    st.header("📁 Manage Collections")
    st.button("Refresh List", on_click=refresh_collections)

    st.write("### Existing Collections:")
    if collections_list:
        st.write(collections_list)
    else:
        st.info("No collections found. Create one below or check backend connection.")

    # --- Create Collection ---
    st.write("---")
    st.write("### Create New Collection")
    new_collection_name = st.text_input("New Collection Name", key="new_collection_input")
    if st.button("Create Collection"):
        if new_collection_name:
            response = create_collection(new_collection_name)
            if response and response.get("status") == "created":
                st.success(f"Collection '{response.get('collection_name')}' created!")
                # Clear input field after success
                st.session_state.new_collection_input = ""
                # Refresh collection list
                refresh_collections()
                st.rerun() # Rerun to update the selectbox immediately
            else:
                # Error message handled by client.py
                pass
        else:
            st.warning("Please enter a name for the new collection.")

    # --- Delete Collection ---
    st.write("---")
    st.write("### Delete Existing Collection")
    if collections_list:
        # Use a unique key for the selectbox
        del_collection_name = st.selectbox("Select Collection to Delete", options=collections_list, key="delete_collection_select")
        if st.button("Delete Collection", type="primary"): # Make delete button more prominent
            if del_collection_name:
                # Confirmation dialog
                # st.session_state['confirm_delete'] = True # Requires more complex state handling
                # For simplicity, delete directly for now
                response = delete_collection(del_collection_name)
                if response and response.get("status") == "deleted":
                    st.warning(f"Collection '{response.get('collection_name')}' deleted.")
                    # Refresh collection list
                    refresh_collections()
                    st.rerun() # Rerun to update the selectbox immediately
                else:
                    # Error message handled by client.py
                    pass
            else:
                st.warning("Please select a collection to delete.")
    else:
        st.info("No collections available to delete.")


# --- Tab 2: Upload PDF ---
with tab2:
    st.header("⬆️ Upload PDF")
    if collections_list:
        # Use a unique key
        collection_to_upload_to = st.selectbox("Select Collection to Upload To", options=collections_list, key="upload_collection_select")
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf_uploader")

        if uploaded_file is not None and collection_to_upload_to:
            if st.button("Upload and Process PDF"):
                with st.spinner(f"Uploading and processing '{uploaded_file.name}'..."):
                    response = upload_pdf(uploaded_file, collection_to_upload_to)
                if response and response.get("message"):
                    st.success(f"Successfully processed '{uploaded_file.name}'!")
                    st.json(response) # Show details like chunks/images stored
                     # Clear the uploader state after successful upload
                    st.session_state.pdf_uploader = None
                    st.rerun()
                else:
                    st.error("PDF upload failed. Check backend logs for details.")
                    # Error message may already be shown by client.py
    else:
        st.warning("Please create a collection first in the 'Collection Manager' tab before uploading.")


# --- Tab 3: Query Collection ---
with tab3:
    st.header("🔍 Query Collection")
    if collections_list:
        # Use a unique key
        collection_to_query = st.selectbox("Select Collection to Query", options=collections_list, key="query_collection_select")
        user_query = st.text_input("Ask a question about the documents in the selected collection", key="query_input")

        if st.button("Submit Query"):
            if user_query and collection_to_query:
                with st.spinner("Searching..."):
                    response = query_collection(user_query, collection_to_query)

                if response:
                    st.markdown("---")
                    st.markdown("### 📌 Answer")
                    st.info(response.get("answer", "No answer provided.")) # Use info box for answer

                    images = response.get("images")
                    if images:
                        st.markdown("### 🖼️ Retrieved Images")
                        # Display images - st.image handles list of bytes/files
                        st.image(images, use_column_width='auto') # Adjust width as needed
                    else:
                         st.markdown("*(No relevant images found)*")

                else:
                    # Error should be handled by client.py, but have a fallback
                    st.error("Query failed. Please check the backend connection and logs.")
            elif not collection_to_query:
                 st.warning("Please select a collection.")
            else:
                st.warning("Please enter a question.")
    else:
        st.warning("Please create a collection and upload documents first.")