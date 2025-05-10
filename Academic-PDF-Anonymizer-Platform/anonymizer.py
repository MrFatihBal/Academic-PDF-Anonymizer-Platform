import re
import os
import PyPDF2
from config import UPLOAD_FOLDER, ANONYMIZED_FOLDER

def anonymize_text(text):
    text = re.sub(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", "***", text)  
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "***@***.com", text)  
    return text

def anonymize_pdf(file_name):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    output_path = os.path.join(ANONYMIZED_FOLDER, "anon_" + file_name)

    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        writer = PyPDF2.PdfWriter()

        for page in reader.pages:
            text = page.extract_text()
            anonymized_text = anonymize_text(text)
            page_content = PyPDF2.pdf.PageObject.create_blank_page(None, page.mediabox.width, page.mediabox.height)
            writer.add_page(page_content)

        with open(output_path, "wb") as out_f:
            writer.write(out_f)
    
    return output_path
