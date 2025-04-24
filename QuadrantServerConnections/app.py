# app.py
import streamlit as st
from client import (
    upload_pdf, list_collections, create_collection,
    delete_collection, query_collection
)
import time

# --- Page Configuration (MUST BE THE FIRST Streamlit command) ---
st.set_page_config(
    page_title="DocuQuery",
    layout="wide",
    # You can add other options here like page_icon
    # page_icon="📄"
)

# --- Session State Initialization & Initial Checks ---
# It's now SAFE to use st commands here because set_page_config already ran.
if 'collections' not in st.session_state:
    st.session_state.collections = list_collections()
    # You can show a message here if needed, AFTER set_page_config
    if not st.session_state.collections:
        st.toast("Attempted to load collections: None found or backend connection failed.")

# --- Helper Functions (Definition is fine anywhere before use) ---
def refresh_collections():
    """Function to refresh the list of collections."""
    st.session_state.collections = list_collections()
    # It's safe to use st.toast inside functions too, as long as the
    # function itself is CALLED after set_page_config has run.
    if not st.session_state.collections:
         st.toast("Refreshed: No collections found or failed to connect.")
    else:
        st.toast("Collections list refreshed.")

# --- Main UI Setup ---
st.title("📄 DocuQuery: Document Understanding with Text + Images")

# Use session state for collection list
collections_list = st.session_state.get('collections', [])

tab1, tab2, tab3 = st.tabs(["📁 Collection Manager", "⬆️ Upload PDF", "🔍 Query Collection"])

# --- Tab 1: Collection Manager ---
with tab1:
    st.header("📁 Manage Collections")
    # Calling refresh_collections here is fine now
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
                st.session_state.new_collection_input = ""
                refresh_collections() # Refresh list after creation
                st.rerun()
            # Error handled by client.py
        else:
            st.warning("Please enter a name for the new collection.")

    # --- Delete Collection ---
    st.write("---")
    st.write("### Delete Existing Collection")
    if collections_list:
        del_collection_name = st.selectbox("Select Collection to Delete", options=collections_list, key="delete_collection_select", index=None, placeholder="Select collection...") # Added placeholder
        if st.button("Delete Collection", type="primary"):
            if del_collection_name:
                response = delete_collection(del_collection_name)
                if response and response.get("status") == "deleted":
                    st.warning(f"Collection '{response.get('collection_name')}' deleted.")
                    refresh_collections() # Refresh list after deletion
                    st.rerun()
                # Error handled by client.py
            else:
                st.warning("Please select a collection to delete.")
    else:
        st.info("No collections available to delete.")


# --- Tab 2: Upload PDF ---
with tab2:
    st.header("⬆️ Upload PDF")
    if collections_list:
        collection_to_upload_to = st.selectbox("Select Collection to Upload To", options=collections_list, key="upload_collection_select", index=None, placeholder="Select collection...") # Added placeholder
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", key="pdf_uploader")

        if uploaded_file is not None and collection_to_upload_to:
            if st.button("Upload and Process PDF"):
                with st.spinner(f"Uploading and processing '{uploaded_file.name}'..."):
                    response = upload_pdf(uploaded_file, collection_to_upload_to)
                if response and response.get("message"):
                    st.success(f"Successfully processed '{uploaded_file.name}'!")
                    st.json(response)
                    st.session_state.pdf_uploader = None # Clear uploader state
                    st.rerun() # Optional: rerun to clear the button state etc.
                else:
                    st.error("PDF upload failed. Check backend logs for details.")
        elif st.button("Upload and Process PDF", disabled=True): # Show disabled button if conditions not met
             pass # Or add a note why it's disabled
    else:
        st.warning("Please create a collection first in the 'Collection Manager' tab before uploading.")


# --- Tab 3: Query Collection ---
with tab3:
    st.header("🔍 Query Collection")
    if collections_list:
        collection_to_query = st.selectbox("Select Collection to Query", options=collections_list, key="query_collection_select", index=None, placeholder="Select collection...") # Added placeholder
        user_query = st.text_input("Ask a question about the documents in the selected collection", key="query_input")

        if st.button("Submit Query"):
            if user_query and collection_to_query:
                with st.spinner("Searching and generating answer..."):
                    response = query_collection(user_query, collection_to_query)

                if response:
                    st.markdown("---")
                    st.markdown("### 📌 Answer")
                    st.info(response.get("answer", "No answer provided."))

                    images = response.get("images")
                    if images:
                        st.markdown("### 🖼️ Retrieved Images (Score >= Threshold)")
                        # Make columns slightly wider if needed
                        num_cols = min(len(images), 4) # Display max 4 images per row
                        cols = st.columns(num_cols)
                        for i, img_bytes in enumerate(images):
                            with cols[i % num_cols]:
                                st.image(img_bytes, use_column_width=True) # use_column_width adapts to column size
                    else:
                         st.markdown("*(No relevant images found meeting the score threshold)*") # Updated message
                else:
                    st.error("Query failed. Please check the backend connection and logs.")
            elif not collection_to_query:
                 st.warning("Please select a collection.")
            else:
                st.warning("Please enter a question.")
    else:
        st.warning("Please create a collection and upload documents first.")