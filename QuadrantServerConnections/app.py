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

# app.py (Tab 1 - Modified)

with tab1:
    st.header("📁 Manage Collections")
    st.button("Refresh List", on_click=refresh_collections)

    st.write("### Existing Collections:")
    if collections_list:
        st.write(collections_list)
    else:
        st.info("No collections found. Create one below or check backend connection.")

    # --- Create Collection (Using st.form) ---
    st.write("---")
    st.write("### Create New Collection")
    with st.form("create_collection_form", clear_on_submit=True): # Use form with clear_on_submit
        new_collection_name = st.text_input(
            "New Collection Name",
            key="new_collection_input_form" # Use a unique key for the widget inside the form
        )
        submitted_create = st.form_submit_button("Create Collection")

        if submitted_create: # Check if the form's submit button was pressed
            if new_collection_name and new_collection_name.strip(): # Check if name is not empty/whitespace
                # Call backend
                response = create_collection(new_collection_name)
                if response and response.get("status") == "created":
                    # Use toast for feedback as form clears
                    st.toast(f"Collection '{response.get('collection_name')}' created!", icon="✅")
                    # Refresh list (safe to call here)
                    refresh_collections()
                    # st.rerun() # No rerun needed, clear_on_submit handles input clearing. Refresh updates list display eventually.
                # Error message handled by client.py's handle_request_error
            else:
                st.warning("Please enter a valid name for the new collection.", icon="⚠️")

    # --- Delete Collection ---
    # (Keep the delete section as is, or optionally wrap it in its own form too for consistency)
    st.write("---")
    st.write("### Delete Existing Collection")
    if collections_list:
        # Optional: Wrap delete in a form
        with st.form("delete_collection_form"):
             del_collection_name = st.selectbox(
                 "Select Collection to Delete",
                 options=collections_list,
                 key="delete_collection_select_form", # Unique key
                 index=None,
                 placeholder="Select collection..."
             )
             submitted_delete = st.form_submit_button("Delete Collection", type="primary")

             if submitted_delete:
                if del_collection_name:
                    response = delete_collection(del_collection_name)
                    if response and response.get("status") == "deleted":
                        st.toast(f"Collection '{response.get('collection_name')}' deleted.", icon="🗑️")
                        refresh_collections()
                        # st.rerun() # Rerun if you want immediate update of selectbox list after delete
                    # Error handled by client.py
                else:
                    st.warning("Please select a collection to delete.", icon="⚠️")
    else:
        st.info("No collections available to delete.")


# --- Tab 2: Upload PDF ---
# app.py (Tab 2 - Using st.form)

with tab2:
    st.header("⬆️ Upload PDF")
    if collections_list:
        # --- Create a Form ---
        with st.form("upload_form", clear_on_submit=True): # Key change: clear_on_submit
            collection_to_upload_to = st.selectbox(
                "Select Collection to Upload To",
                options=collections_list,
                key="upload_collection_select_form", # Use a unique key inside the form
                index=None,
                placeholder="Select collection..."
            )
            uploaded_file = st.file_uploader(
                "Choose a PDF file",
                type="pdf",
                key="pdf_uploader_form" # Use a unique key inside the form
            )

            # --- Submit Button for the Form ---
            submitted = st.form_submit_button("Upload and Process PDF")

            # --- Process form submission ---
            if submitted: # Check if the form's submit button was pressed
                if uploaded_file is not None and collection_to_upload_to:
                    with st.spinner(f"Uploading and processing '{uploaded_file.name}'..."):
                        response = upload_pdf(uploaded_file, collection_to_upload_to)
                    if response is not None:
                         if response.get("message"):
                            st.success(f"Successfully processed '{uploaded_file.name}'!")
                            # Display response outside the form if needed after rerun, or use st.toast
                            # st.json(response) # This might disappear on rerun if inside form
                            st.session_state.last_upload_response = response # Store if needed after clear
                            # No need to manually clear or rerun, clear_on_submit handles it
                         # Error/Warning messages handled by client.py
                elif not collection_to_upload_to:
                     st.warning("Please select a collection.", icon="⚠️")
                elif not uploaded_file:
                     st.warning("Please choose a PDF file.", icon="⚠️")

        # Optional: Display details from the last successful upload outside the form
        if 'last_upload_response' in st.session_state and st.session_state.last_upload_response:
             st.write("Last Upload Details:")
             st.json(st.session_state.last_upload_response)
             # Clear it after displaying once if desired
             # del st.session_state.last_upload_response

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