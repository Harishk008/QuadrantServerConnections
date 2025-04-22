# services/text_chunker.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TextChunker:
    def __init__(self, chunk_size=1000, chunk_overlap=200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True
        )

    def chunk(self, text: str):
        return self.splitter.create_documents([text])
