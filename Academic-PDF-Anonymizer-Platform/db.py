from pyodbc import Error
from pyodbc import Binary
import pyodbc
from datetime import date
import base64
from datetime import datetime
import work
from work import encrypt_pdf_bytes, decrypt_pdf_bytes


def get_db_connection():
    try:
        conn = pyodbc.connect(
            'Driver={ODBC Driver 18 for SQL Server};'
            'Server=DESKTOP-8MG4EKJ\\SQLEXPRESS;'
            'Database=YeniMakaleSistemi;'
            'Trusted_Connection=yes;'
            'TrustServerCertificate=yes;'
        )
        return conn
    except Error as e:
        print("Bağlantı hatası:", e)
        return None



def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='articles' AND xtype='U')
        CREATE TABLE articles (
            id INT IDENTITY(1,1) PRIMARY KEY,
            email NVARCHAR(255) NOT NULL,
            file_name NVARCHAR(255) NOT NULL,
            tracking_number NVARCHAR(50) NOT NULL UNIQUE,
            status NVARCHAR(50) DEFAULT 'Beklemede'
        )
    """)

    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='messages' AND xtype='U')
        CREATE TABLE messages (
            id INT IDENTITY(1,1) PRIMARY KEY,
            sender_email NVARCHAR(255) NOT NULL,
            receiver_email NVARCHAR(255) NOT NULL,
            message_text NVARCHAR(MAX) NOT NULL,
            sent_at DATETIME DEFAULT GETDATE()
        )
    """)
    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='notifications' AND xtype='U')
        CREATE TABLE notifications (
            id INT IDENTITY(1,1) PRIMARY KEY,
            email NVARCHAR(255) NOT NULL,
            message_text NVARCHAR(MAX) NOT NULL,
            sent_at DATETIME DEFAULT GETDATE()
        )

    """)


    cur.execute("""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='reviews' AND xtype='U')
        CREATE TABLE reviews (
            id INT IDENTITY(1,1) PRIMARY KEY,
            tracking_number NVARCHAR(50) NOT NULL,
            fluency FLOAT NOT NULL,
            content FLOAT NOT NULL,
            originality FLOAT NOT NULL,
            impact FLOAT NOT NULL,
            methodology FLOAT NOT NULL,
            review_text NVARCHAR(MAX) NOT NULL,
            FOREIGN KEY (tracking_number) REFERENCES articles(tracking_number)
        )
    """)

    conn.commit()
    conn.close()

create_tables()






def insert_encrypted_pdf(filename, pdf_bytes):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = "INSERT INTO encrypted_pdfs (filename, data) VALUES (?, ?)"
            encrypted_data = encrypt_pdf_bytes(pdf_bytes)
            cursor.execute(sql, (filename, Binary(encrypted_data)))
            conn.commit()
            print("PDF başarıyla şifrelenip veritabanına kaydedildi.")
        except Error as e:
            print("PDF ekleme hatası:", e)
        finally:
            conn.close()
    else:
        print("Veritabanı bağlantısı kurulamadı.")


def get_decrypted_pdf(pdf_id):
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = "SELECT filename, data FROM encrypted_pdfs WHERE id = ?"
            cursor.execute(sql, (pdf_id,))
            result = cursor.fetchone()
            if result:
                filename, encrypted_data = result
                decrypted_data = decrypt_pdf_bytes(encrypted_data)
                return filename, decrypted_data
            else:
                print("Belirtilen ID ile kayıt bulunamadı.")
                return None, None
        except Error as e:
            print("PDF alma hatası:", e)
            return None, None
        finally:
            conn.close()
    else:
        print("Veritabanı bağlantısı kurulamadı.")
        return None, None


def create_encrypted_pdf_table():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='encrypted_pdfs' and xtype='U')
                CREATE TABLE encrypted_pdfs (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    filename NVARCHAR(255),
                    data VARBINARY(MAX)
                )
            """)
            conn.commit()
            print("Tablo başarıyla oluşturuldu veya zaten mevcut.")
        except Error as e:
            print("Tablo oluşturulurken hata oluştu:", e)
        finally:
            conn.close()
    else:
        print("Veritabanı bağlantısı kurulamadı.")
        
