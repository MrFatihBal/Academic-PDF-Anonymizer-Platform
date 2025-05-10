import os

SECRET_KEY = "super_secret_key"
UPLOAD_FOLDER = "uploads"
ANONYMIZED_FOLDER = "anonymous"

MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = "seninmail@gmail.com"
MAIL_PASSWORD = "sifren"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ANONYMIZED_FOLDER, exist_ok=True)
