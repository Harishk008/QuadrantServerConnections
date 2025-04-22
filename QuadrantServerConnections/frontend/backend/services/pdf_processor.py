# services/pdf_processor.py
import os, json
import fitz
from PIL import Image

class PDFProcessor:
    def __init__(self, image_dir: str):
        os.makedirs(image_dir, exist_ok=True)
        self.image_dir = image_dir

    def extract_images_from_page(self, doc, page, file_base, page_num):
        image_paths = []
        for i, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            if not base_image or not base_image.get("image"): continue
            ext = base_image.get("ext", "png")
            img_name = f"{file_base}_page{page_num}_img{i}.{ext}"
            img_path = os.path.join(self.image_dir, img_name)
            with open(img_path, "wb") as f: f.write(base_image["image"])
            image_paths.append(img_path.replace("\\", "/"))
        return image_paths

    def parse_pdf(self, file_bytes: bytes, filename: str):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return doc
