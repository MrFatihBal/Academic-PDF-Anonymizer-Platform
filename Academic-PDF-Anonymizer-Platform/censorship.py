import fitz  
import re
import io
import spacy


nlp = spacy.load("en_core_web_sm")


ORG_PATTERNS = [
    "university", "college", "institute", "department", "school",
    "faculty", "lab", "laboratory", ".edu", ".ac", "email", "@",
    "corresponding author","support"
]


def is_org_related(text):
    lowered = text.lower()
    return any(p in lowered for p in ORG_PATTERNS)


def has_person_entity(text):
    doc = nlp(text)
    return any(ent.label_ == "PERSON" for ent in doc.ents)

def apply_text_censorship(page):
    blocks = page.get_text("blocks")
    reached_abstract = False

    for b in blocks:
        text = b[4].strip()
        rect = fitz.Rect(b[:4])

        
        if text.lower().startswith("abstract"):
            reached_abstract = True
            continue

        if reached_abstract:
            continue

        
        if len(text.split()) <= 3 and text.istitle():
            continue

        
        if is_org_related(text):
            page.add_redact_annot(rect, fill=(0, 0, 0))
            continue

        
        if has_person_entity(text):
            page.add_redact_annot(rect, fill=(0, 0, 0))


def censor_pdf_bytes(pdf_bytes):
    doc = fitz.open("pdf", io.BytesIO(pdf_bytes))
    
    apply_text_censorship(doc[0])

    
    censor_biography_blocks(doc)
    
    censor_acknowledgment(doc)
    censor_exact_header(doc)
    for page in doc:
        page.apply_redactions()

    output_stream = io.BytesIO()
    annots = list(page.annots() or [])
    print(f"[DEBUG] Sayfa {page.number} → Redaction sayısı: {len(annots)}")

    doc.save(output_stream, deflate=True, clean=True)
    doc.close()
    return output_stream.getvalue()





def is_biography_related(text):
    bio_patterns = [
        "born", "received", "degree", "currently", "working", "joined",
        "department", "faculty", "institute", "university", "college",
        "email", "@", "member", "editor", "reviewer"
    ]
    lowered = text.lower()
    return any(p in lowered for p in bio_patterns)

def is_reference_number(text):
    
    return bool(re.match(r"^\[?\d{1,3}\]?\.*$", text.strip()))

def is_biography_related(text):
    bio_patterns = [
        "born", "received", "degree", "currently", "working", "joined",
        "department", "faculty", "institute", "university", "college",
        "email", "@", "member", "editor", "reviewer"
    ]
    lowered = text.lower()
    return any(p in lowered for p in bio_patterns)

def censor_biography_blocks(doc):
    print("[DEBUG] Biyografi blok sansürleme başladı")

    reference_page_indexes = set()

    
    for page in doc:
        text = page.get_text().lower()
        if "references" in text:
            reference_page_indexes.add(page.number)

    if not reference_page_indexes:
        print("[DEBUG] Referans sayfası bulunamadı, işlem yapılmadı.")
        return

    last_ref_page = max(reference_page_indexes)
    print(f"[DEBUG] REFERANS bitiş sayfası: {last_ref_page}")

    
    for page in doc:
        if page.number <= last_ref_page:
            continue

        print(f"[INFO] Sayfa {page.number} → Biyografi bloğu kontrol ediliyor.")

        
        images = page.get_images(full=True)
        for img in images:
            try:
                bbox = page.get_image_bbox(img[0])
                page.add_redact_annot(bbox, fill=(0, 0, 0))
                print(f"[INFO] Görsel sansürlendi → {bbox}")
            except ValueError:
                continue

        
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4].strip()
            rect = fitz.Rect(b[:4])

            if is_biography_related(text):
                page.add_redact_annot(rect, fill=(0, 0, 0))
                print(f"[INFO] Metin bloğu sansürlendi → {text}")

    
    for page in doc:
        page.apply_redactions()

    print("[INFO] Biyografi blok sansürleme tamamlandı.")
    
def is_acknowledgment_text(text):
    """
    Teşekkür paragrafı olup olmadığını kontrol eder.
    """
    patterns = ["this work was supported", "funded by", "acknowledgment", "supported by", "grants no."]
    text_lower = text.lower()
    return any(p in text_lower for p in patterns)

def censor_acknowledgment(doc):
    for page in doc:
        blocks = page.get_text("blocks")
        for b in blocks:
            rect = fitz.Rect(b[:4])
            text = b[4].strip()

            if is_acknowledgment_text(text):
                page.add_redact_annot(rect, fill=(0, 0, 0))
                print(f"[INFO] Teşekkür kısmı sansürlendi → Sayfa {page.number}, Text: {text}")

        page.apply_redactions()

def is_exact_header(text):
    """
    Header olup olmadığını kontrol eder.
    Örnek pattern: 'et al.' + uzun başlık
    """
    return "et al." in text.lower() and "emotion recognition" in text.lower()

def censor_exact_header(doc):
    header_ratio = 0.15  

    for page in doc:
        page_height = page.rect.height
        header_limit = page_height * header_ratio

        blocks = page.get_text("blocks")
        for b in blocks:
            rect = fitz.Rect(b[:4])
            text = b[4].strip()

            if rect.y1 <= header_limit:
                if is_exact_header(text):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    print(f"[INFO] IEEE Access Header sansürlendi → Sayfa {page.number}")

        page.apply_redactions()


