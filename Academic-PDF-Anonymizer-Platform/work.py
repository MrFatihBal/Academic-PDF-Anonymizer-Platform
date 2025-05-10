import io
import re
from collections import defaultdict
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import fitz

AES_KEY = b'ThisIsA16ByteKey'  


def pad(data):
    padding_len = AES.block_size - len(data) % AES.block_size
    return data + bytes([padding_len] * padding_len)

def unpad(data):
    padding_len = data[-1]
    return data[:-padding_len]


def encrypt_pdf_bytes(pdf_bytes):
    iv = get_random_bytes(16)  
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    padded_data = pad(pdf_bytes)
    encrypted_data = cipher.encrypt(padded_data)
    return iv + encrypted_data  


def decrypt_pdf_bytes(encrypted_data):
    iv = encrypted_data[:16]
    encrypted_content = encrypted_data[16:]
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    decrypted_padded = cipher.decrypt(encrypted_content)
    return unpad(decrypted_padded)
def FindTopic(text):
    topics = {
        "Yapay Zeka ve Makine Öğrenimi": [
            "deep learning", "neural network", "machine learning", "AI", 
            "artificial intelligence", "natural language processing", "NLP", 
            "computer vision", "image recognition", "generative AI", "transformer"
        ],
        "İnsan-Bilgisayar Etkileşimi": [
            "brain-computer interface", "BCI", "user experience", "UX", 
            "human-computer interaction", "AR", "VR", "augmented reality", "virtual reality", 
            "interface design"
        ],
        "Büyük Veri ve Veri Analitiği": [
            "big data", "data mining", "data visualization", "Hadoop", "Spark", 
            "data processing", "data analytics", "time series", "forecasting", 
            "ETL", "real-time data"
        ],
        "Siber Güvenlik": [
            "cybersecurity", "encryption", "secure software", "network security", 
            "authentication", "digital forensics", "malware", "firewall", "intrusion detection"
        ],
        "Ağ ve Dağıtık Sistemler": [
            "5G", "network", "cloud computing", "blockchain", 
            "decentralized", "distributed systems", "peer-to-peer", "P2P", 
            "smart contracts", "edge computing"
        ]
    }

    text = text.lower()
    topic_scores = defaultdict(int)

    for topic, keywords in topics.items():
        for keyword in keywords:
            count = len(re.findall(r'\b' + re.escape(keyword.lower()) + r'\b', text))
            topic_scores[topic] += count

    if not topic_scores:
        return "Alan belirlenemedi"

    
    most_relevant_topic = max(topic_scores.items(), key=lambda item: item[1])

    
    if most_relevant_topic[1] == 0:
        return "Alan belirlenemedi"
    
    return most_relevant_topic[0]  
def append_review_page(original_pdf_bytes, review_data):
    import fitz
    import io

    pdf = fitz.open("pdf", original_pdf_bytes)
    page = pdf.new_page()

    review_text = f"""
Hakem Değerlendirmesi

Akicilik: {review_data['fluency']}
Içerik Kalitesi: {review_data['content']}
Özgünlük: {review_data['originality']}
Etki: {review_data['impact']}
Yöntem: {review_data['methodology']}

Açiklama:
{review_data['review_text']}
    """

    
    font = "helv"  
    page.insert_text(
        (50, 50),
        review_text,
        fontname=font,
        fontsize=12,
        encoding=0  
    )

    output = io.BytesIO()
    pdf.save(output)
    pdf.close()
    return output.getvalue()
