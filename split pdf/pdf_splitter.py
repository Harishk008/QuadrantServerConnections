from PyPDF2 import PdfReader, PdfWriter

def split_pdf(input_pdf: str, output_chapter1: str, output_chapter2: str, chapter_1_pages: list, chapter_2_pages: list):
    """
    Splits a PDF into two separate PDFs based on the given page ranges.
    
    :param input_pdf: Path to the input PDF file.
    :param output_chapter1: Path to save the first chapter PDF.
    :param output_chapter2: Path to save the second chapter PDF.
    :param chapter_1_pages: List of page numbers start from 0 for chapter 1.
    :param chapter_2_pages: List of page numbers start from 0 for chapter 2.
    :If there are total 30 pages and there are 10 pages for chapter 1 and 20 pages for chapter 2, then chapter_1_pages = list(range(1,11)) and chapter_2_pages = list(range(11,31))
    """
    with open(input_pdf, "rb") as file:
        reader = PdfReader(file)
        writer1 = PdfWriter()
        writer2 = PdfWriter()
        
        for page_num in range(1, len(reader.pages) + 1):
            if page_num in chapter_1_pages:
                writer1.add_page(reader.pages[page_num-1])
            elif page_num in chapter_2_pages:
                writer2.add_page(reader.pages[page_num-1])
        
        with open(output_chapter1, "wb") as out1:
            writer1.write(out1)
        
        with open(output_chapter2, "wb") as out2:
            writer2.write(out2)

#chapter_1_pages = list(range(1,11)) and chapter_2_pages = list(range(11,31), add your page numbers accordingly.
split_pdf("split pdf\Claimant Handbook.pdf", "chapter_1.pdf", "chapter_2.pdf", list(range(1,25)), list(range(25,49)))
