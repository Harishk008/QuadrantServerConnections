# services/document_uploader.py
import io, os, json
from qdrant_client.models import PointStruct

class DocumentUploader:
    def __init__(self, qdrant_connector, embedder, chunker, pdf_processor, default_collection):
        self.qdrant = qdrant_connector
        self.embedder = embedder
        self.chunker = chunker
        self.pdf_processor = pdf_processor
        self.default_collection = default_collection

    def upload(self, file_bytes: bytes, file_name: str, collection_name: str = None):
        collection = collection_name or self.default_collection
        client = self.qdrant.get_client()
        self.qdrant.ensure_collection(collection)

        doc = self.pdf_processor.parse_pdf(file_bytes, file_name)
        base_name = os.path.splitext(file_name)[0]
        total_chunks, total_images = 0, 0
        points = []

        for page_num, page in enumerate(doc):
            images = self.pdf_processor.extract_images_from_page(doc, page, base_name, page_num)
            total_images += len(images)
            image_meta = json.dumps(images)

            text = page.get_text("text", sort=True)
            if not text.strip(): continue
            chunks = self.chunker.chunk(text)

            for chunk in chunks:
                try:
                    vector = self.embedder.embed(chunk.page_content)
                    payload = {
                        "source": file_name,
                        "page_number": page_num,
                        "chunk_index": total_chunks,
                        "text": chunk.page_content,
                        "associated_image_paths": image_meta,
                    }
                    points.append(PointStruct(id=total_chunks + 1, vector=vector, payload=payload))
                    total_chunks += 1
                except Exception as e:
                    print(f"Embedding failed: {e}")

        if points:
            client.upsert(collection_name=collection, points=points, wait=True)

        return {
            "message": f"{file_name} processed",
            "chunks_stored": total_chunks,
            "images_stored": total_images
        }
