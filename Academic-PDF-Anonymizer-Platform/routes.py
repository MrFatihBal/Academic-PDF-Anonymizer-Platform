from datetime import datetime
import os
import re
import uuid
import io
import traceback
import logging
import fitz
from flask import redirect, render_template, request, jsonify, send_from_directory, send_file, session, url_for
from werkzeug.utils import secure_filename
from db import get_db_connection, insert_encrypted_pdf
from auth import generate_token, verify_token
from log_service import log_action
from anonymizer import anonymize_pdf
from config import UPLOAD_FOLDER, ANONYMIZED_FOLDER
from censorship import censor_pdf_bytes
import work
from work import append_review_page, decrypt_pdf_bytes, encrypt_pdf_bytes, FindTopic


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
OUTPUT_FOLDER = "outputs"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
def configure_routes(app):

    log = logging.getLogger('werkzeug')
    log.disabled = True  

    
    
    @app.route("/status_result", methods=["POST"])
    @app.route("/status_result", methods=["GET", "POST"])
    def status_result():
        if request.method == "POST":
            tracking_number = request.form.get("tracking_number")

            if not tracking_number:
                return render_template("status_result.html", error="Takip numarası gerekli")

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT status FROM articles WHERE tracking_number = ?", (tracking_number,))
            row = cur.fetchone()
            conn.close()

            if row:
                return render_template("status_result.html", status=row[0], tracking_number=tracking_number)
            else:
                return render_template("status_result.html", error="Makale bulunamadı")

        return render_template("status.html")


    
    @app.route("/editor/message", methods=["GET", "POST"])
    def editor_message():
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == "POST":
            author_email = request.form.get("author_email")
            message_text = request.form.get("message_text")

            if not author_email or not message_text:
                conn.close()
                return render_template("notifi.html", message="❗️ Bilgiler eksik!", redirect_url="/editor")

            cur.execute("""
                INSERT INTO messages (sender_email, receiver_email, message_text)
                VALUES (?, ?, ?)
            """, ("editor@example.com", author_email, message_text))
            conn.commit()

            
            log_action(f"Editör, {author_email} yazara mesaj gönderdi: \"{message_text}\"", user_role="Editör")

            conn.close()
            return render_template("notifi.html", message="✅ Mesaj yazara başarıyla gönderildi!", redirect_url="/editor")

        
        cur.execute("SELECT DISTINCT email FROM articles")
        authors = cur.fetchall()

        cur.execute("""
            SELECT receiver_email, message_text, sent_at 
            FROM messages 
            WHERE sender_email = 'editor@example.com'
            ORDER BY sent_at DESC
        """)
        messages = cur.fetchall()
        conn.close()

        return render_template("editor_message.html", authors=authors, messages=messages)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/uploads/<filename>")
    def uploaded_file(filename):
        return send_from_directory(UPLOAD_FOLDER, filename)

    @app.route('/upload', methods=['GET', 'POST'])
    def upload_article():
        if request.method == 'GET':
            return render_template('upload.html')

        try:
            email = request.form.get('email')
            file = request.files.get('file')
            is_revize = request.form.get('is_revision')  
            tracking_number = request.form.get('tracking_number')

            if not email or not file:
                return jsonify({"error": "E-posta ve dosya gereklidir!"}), 400

            if file.filename == '':
                return jsonify({"error": "Dosya seçilmedi!"}), 400

            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)

                
                with open(filepath, 'rb') as pdf_file:
                    pdf_bytes = pdf_file.read()

                pdf_document = fitz.open("pdf", io.BytesIO(pdf_bytes))
                text = ""
                for page in pdf_document:
                    text += page.get_text()

                censored_pdf_bytes = censor_pdf_bytes(pdf_bytes)
                topic = work.FindTopic(text)

                insert_encrypted_pdf(filename, censored_pdf_bytes)

                conn = get_db_connection()
                cur = conn.cursor()

                if is_revize:  
                    cur.execute("""
                        SELECT id FROM articles WHERE email = ? AND tracking_number = ?
                    """, (email, tracking_number))
                    row = cur.fetchone()

                    if row:
                        cur.execute("""
                            UPDATE articles 
                            SET file_name = ?, status = 'Revize Edildi', topic = ?
                            WHERE email = ? AND tracking_number = ?
                        """, (filename, topic, email, tracking_number))

                        cur.execute("""
                            INSERT INTO notifications (email, message_text)
                            VALUES (?, ?)
                        """, (email, "Makaleniz revize edildi. Değerlendirme için tekrar sıraya alındı."))

                        conn.commit()
                        conn.close()
                        log_action(f"Makale {tracking_number} revize edildi ve tekrar değerlendirme için sıraya alındı.", user_role="Editör")


                        return f"{tracking_number} numaralı makaleniz başarıyla revize edildi ✅"

                    else:
                        conn.close()
                        return "Revize için verilen takip numarası ve e-posta eşleşmiyor!", 404

                else:  
                    new_tracking = str(uuid.uuid4())[:8]
                    cur.execute("""
                        INSERT INTO articles (email, file_name, tracking_number, status, topic)
                        VALUES (?, ?, ?, ?, ?)
                    """, (email, filename, new_tracking, 'Makale yüklendi', topic))

                    cur.execute("""
                        INSERT INTO notifications (email, message_text)
                        VALUES (?, ?)
                    """, (email, "Makaleniz başarıyla yüklendi. Değerlendirme için sıraya alındı."))

                    conn.commit()
                    conn.close()

                    log_action(f"Makale {new_tracking}, {email} tarafından yüklendi.", user_role="Yazar")
                    return render_template("result.html", text=text, topic=topic, tracking_number=new_tracking)

            else:
                return jsonify({"error": "Sadece PDF dosyaları yüklenebilir!"}), 400

        except Exception as e:
            return jsonify({"error": "Makale yüklenirken hata oluştu", "details": str(e)}), 500

    
    @app.route("/status", methods=["GET"])
    def check_status():
        try:
            tracking_number = request.args.get("tracking_number")
            if not tracking_number:
                return jsonify({"error": "Takip numarası gerekli"}), 400

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT status FROM articles WHERE tracking_number = ?", (tracking_number,))
            article = cur.fetchone()
            conn.close()

            if article:
                return jsonify({"status": article[0]})
            else:
                return jsonify({"error": "Makale bulunamadı"}), 404

        except Exception as e:
            return jsonify({"error": "Makale durumu sorgulanırken hata oluştu", "details": str(e)}), 500

    @app.route("/status_page", methods=["GET"])
    def status_page():
        return render_template("status.html")

    @app.route("/message", methods=["GET"])
    def message_page():
        return render_template("message.html")

    @app.route("/notifications", methods=["GET"])
    def notifications_page():
        return render_template("notification.html")

    @app.route("/send_message", methods=["POST"])
    def send_message():
        try:
            sender_email = request.form.get("sender_email")
            receiver_email = "editor@example.com"
            message_text = request.form.get("message_text")

            if not sender_email or not message_text:
                return render_template("notifi.html", message="❌ Eksik bilgi. Lütfen tüm alanları doldurun.", redirect_url="/message")

            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO messages (sender_email, receiver_email, message_text) 
                VALUES (?, ?, ?)
            """, (sender_email, receiver_email, message_text))
            conn.commit()
            conn.close()

            log_action(f"{sender_email} kullanıcısı {receiver_email} kullanıcısına mesaj gönderdi.", user_role="Kullanıcı")

            return render_template("notifi.html", message="✅ Mesaj yazara başarıyla gönderildi!", redirect_url="/editor")

        except Exception as e:
            return render_template("notifi.html", message=f"❌ Mesaj gönderilirken hata oluştu: {str(e)}", redirect_url="/message")


    @app.route("/get_notifications", methods=["GET"])
    def get_notifications():
        try:
            user_email = request.args.get("email")
            if not user_email:
                return jsonify({"error": "E-posta adresi gerekli"}), 400

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT 'Sistem' AS sender, message_text, sent_at 
                FROM notifications 
                WHERE email = ?
                UNION ALL
                SELECT sender_email AS sender, message_text, sent_at 
                FROM messages 
                WHERE receiver_email = ?
                ORDER BY sent_at DESC;
            """, (user_email, user_email))
            notifications = cur.fetchall()
            conn.close()

            if not notifications:
                return jsonify({"notifications": []})

            response = [
                {
                    "from": notif[0],
                    "message": notif[1],
                    "sent_at": notif[2].strftime("%Y-%m-%d %H:%M:%S")
                }
                for notif in notifications
            ]

            return jsonify({"notifications": response})

        except Exception as e:
            return jsonify({"error": "Bildirimler alınırken hata oluştu", "details": str(e)}), 500


    @app.route("/anonymize", methods=["GET", "POST"])
    def anonymize():
        if request.method == "POST":
            selected_tracking = request.form.get("selected_tracking")

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT file_name, id, email FROM articles WHERE tracking_number = ?", (selected_tracking,))
            article_row = cursor.fetchone()

            if not article_row:
                conn.close()
                return f"Hata: {selected_tracking} için eşleşen makale bulunamadı."

            file_name, original_article_id, author_email = article_row
            pdf_path = os.path.join(UPLOAD_FOLDER, file_name)
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            
            pdf_bytes = censor_pdf_bytes(pdf_bytes)

            encrypted_pdf = encrypt_pdf_bytes(pdf_bytes)

            original_name_without_ext = os.path.splitext(file_name)[0]
            output_filename = f"anon_{original_name_without_ext}.pdf.enc"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            with open(output_path, "wb") as out_file:
                out_file.write(encrypted_pdf)

            try:
                cursor.execute("""
                INSERT INTO anonymous_articles (tracking_number, original_article_id, anonymous_pdf, assigned_reviewer, uploaded_at)
                VALUES (?, ?, ?, NULL, ?)
                """, (
                    selected_tracking,
                    original_article_id,
                    output_filename,
                    datetime.now()
                ))
                cursor.execute("""
                    UPDATE articles 
                    SET status = 'Anonimleştirildi'
                    WHERE tracking_number = ?
                """, (selected_tracking,))
                cursor.execute("""
                    INSERT INTO notifications (email, message_text) 
                    VALUES (?, ?)
                """, (
                    author_email,
                    f"Makaleniz anonimleştirildi ve sistemde işlem görmeye hazır."
                ))

                conn.commit()
                conn.close()

                log_action(f"Makale {selected_tracking} anonimleştirildi ve veritabanına eklendi.", user_role="Editör")

                return render_template("notifi.html", message=f"{file_name} başarıyla anonimleştirildi ve veritabanına eklendi ✅")

            except Exception as e:
                conn.rollback()
                conn.close()
                return f"Hata oluştu: {str(e)}"


        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT tracking_number FROM articles 
        WHERE status IN ('Makale yüklendi', 'Revize Edildi')
        """)
        articles = cursor.fetchall()
        conn.close()

        return render_template("anonymize.html", articles=articles)

     
    @app.route("/all_articles", methods=["GET"])
    def all_articles():
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT tracking_number, email, file_name, status FROM articles")
            articles = cur.fetchall()
            conn.close()
            

            return render_template("all_articles.html", articles=articles)

        except Exception as e:
            return jsonify({"error": "Makaleler alınırken hata oluştu", "details": str(e)}), 500

    
    @app.route("/logs", methods=["GET"])
    def view_logs():
        try:
            log_file_path = "app.log"
            logs = []

            with open(log_file_path, "r", encoding="utf-8", errors="replace") as log_file:
                logs = [line.strip() for line in log_file.readlines() if line.startswith("#")]

            if not logs:
                logs = ["Henüz kayıtlı bir işlem bulunmamaktadır."]

            return render_template("logs.html", logs=logs)

        except Exception as e:
            return jsonify({"error": "Loglar alınırken hata oluştu", "details": str(e)}), 500
        
        
    @app.route("/assign_reviewers", methods=["GET", "POST"])
    def assign_reviewer():
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == "GET":
            cur.execute("""
                SELECT aa.tracking_number, a.file_name 
                FROM anonymous_articles aa
                JOIN articles a ON aa.tracking_number = a.tracking_number
                WHERE a.status = 'Anonimleştirildi'
            """)
            articles = cur.fetchall()
            cur.execute("""
        SELECT first_name, last_name, email 
        FROM reviewers 
        WHERE available = 1
    """)
            reviewers = cur.fetchall()
            conn.close()
            return render_template("assign_reviewers.html", reviewers=reviewers, articles=articles)

        if request.method == "POST":
            tracking_number = request.form.get("tracking_number")
            reviewer_email = request.form.get("reviewer_email")

            if not tracking_number or not reviewer_email:
                conn.close()
                return jsonify({"error": "Eksik bilgiler"}), 400

            try:
                
                cur.execute("SELECT email FROM reviewers WHERE email = ?", (reviewer_email,))
                if not cur.fetchone():
                    raise Exception("Hakem bulunamadı.")

                
                cur.execute("SELECT tracking_number FROM anonymous_articles WHERE tracking_number = ?", (tracking_number,))
                if not cur.fetchone():
                    raise Exception("Anonim makale bulunamadı.")

                
                cur.execute("UPDATE reviewers SET available = 0 WHERE email = ?", (reviewer_email,))
                cur.execute("UPDATE anonymous_articles SET assigned_reviewer = ? WHERE tracking_number = ?", (reviewer_email, tracking_number))

                
                cur.execute("SELECT email FROM articles WHERE tracking_number = ?", (tracking_number,))
                author_email = cur.fetchone()
                if author_email:
                    cur.execute("INSERT INTO notifications (email, message_text) VALUES (?, ?)", 
                                (author_email[0], f"Makaleniz ({tracking_number}) bir hakeme atandı."))

                conn.commit()
                conn.close()
                log_action(f"Makale {tracking_number}, {reviewer_email} hakemine atandı.", user_role="Editör")


                return jsonify({"message": f"{reviewer_email} hakemine başarıyla atandı."})

            except Exception as e:
                conn.close()
                return jsonify({"error": "Bir hata oluştu", "details": str(e)}), 500


    @app.route("/get_reviewers")
    def get_reviewers():
        tracking_number = request.args.get("tracking_number")
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT topic FROM articles WHERE tracking_number = ?", (tracking_number,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({"reviewers": []})

        topic = row[0]

        cur.execute("SELECT first_name, last_name, email FROM reviewers WHERE available = 1 AND expertise = ?", (topic,))
        reviewers = cur.fetchall()
        conn.close()

        reviewer_list = [
            {"first_name": r[0], "last_name": r[1], "email": r[2]}
            for r in reviewers
        ]

        return jsonify({"reviewers": reviewer_list})
    @app.route('/review/pdf/<tracking_number>')
    def review_pdf(tracking_number):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            
            cursor.execute("""
                SELECT anonymous_pdf FROM anonymous_articles 
                WHERE tracking_number = ?
            """, (tracking_number,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return "Hata: Anonim dosya bulunamadı."

            encrypted_filename = row[0]
            path = os.path.join("outputs", encrypted_filename)

            if not os.path.exists(path):
                return "Anonim PDF dosyası bulunamadı."

            with open(path, "rb") as f:
                encrypted_data = f.read()

            decrypted_pdf = decrypt_pdf_bytes(encrypted_data)

            
            cleaned_name = encrypted_filename.replace(".enc", "")

            return send_file(
                io.BytesIO(decrypted_pdf),
                mimetype='application/pdf',
                as_attachment=False,
                download_name=cleaned_name
            )
        except Exception as e:
            return f"Hata oluştu: {str(e)}"



    @app.route("/hakem_giris", methods=["GET"])
    def hakem_giris():
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT email, first_name + ' ' + last_name FROM reviewers")
        reviewers = cur.fetchall()
        conn.close()

        return render_template("hakem_giris.html", reviewers=reviewers)


    @app.route("/hakem_paneli", methods=["POST"])
    def hakem_paneli():
        email = request.form.get("email")
        session["hakem_email"] = email  

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT tracking_number 
           FROM anonymous_articles 
          WHERE assigned_reviewer = ?
        """, (email,))
        result = cur.fetchone()

        if not result:
           return "Bu hakeme atanmış makale yok!"

        tracking_number = result[0] 

        return redirect(url_for("hakem"))
    
    @app.route("/hakem", methods=["GET"])
    def hakem():
        email = session.get("hakem_email")

        if not email:
            return redirect("/hakem_giris")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
          SELECT tracking_number 
          FROM anonymous_articles 
          WHERE assigned_reviewer = ?
        """, (email,))
        result = cur.fetchone()
        conn.close()

        if not result:
            return "Bu hakeme atanmış makale bulunamadı."

        tracking_number = result[0]

        return render_template("hakem.html", tracking_number=tracking_number)
    @app.route("/review", methods=["POST"])
    def review_submit():
        email = session.get("hakem_email")
        tracking_number = request.form.get("tracking_number")

        if not email or not tracking_number:
            return "Eksik bilgi gönderildi.", 400

        conn = get_db_connection()
        cur = conn.cursor()

        
        cur.execute("""
            SELECT id FROM anonymous_articles 
            WHERE tracking_number = ? AND assigned_reviewer = ?
        """, (tracking_number, email))
        row = cur.fetchone()

        if not row:
            conn.close()
            return "Bu makale size atanmadı, işlem yapılamaz!", 403

        
        fluency = request.form.get("fluency")
        content = request.form.get("content")
        originality = request.form.get("originality")
        impact = request.form.get("impact")
        methodology = request.form.get("methodology")
        review_text = request.form.get("review")

        
        if not all([fluency, content, originality, impact, methodology, review_text]):
            conn.close()
            return "Tüm alanlar doldurulmalı!", 400

        
        cur.execute("""
            INSERT INTO reviews (tracking_number, fluency, content, originality, impact, methodology, review_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tracking_number, fluency, content, originality, impact, methodology, review_text))

        
        cur.execute("""
            UPDATE articles
            SET status = 'Değerlendirildi'
            WHERE tracking_number = ?
        """, (tracking_number,))

        
        cur.execute("""
            SELECT email FROM articles WHERE tracking_number = ?
        """, (tracking_number,))
        row = cur.fetchone()
        if row:
            user_email = row[0]
            cur.execute("""
                INSERT INTO notifications (email, message_text) VALUES (?, ?)
            """, (user_email, "Makaleniz hakem tarafından değerlendirildi. Editör onayı bekliyor."))

        
        cur.execute("""
            SELECT assigned_reviewer FROM anonymous_articles WHERE tracking_number = ?
        """, (tracking_number,))
        row = cur.fetchone()
        reviewer_email = row[0] if row else "Bilinmiyor"
        log_action(f"Hakem {reviewer_email} tarafından Makale {tracking_number} değerlendirildi.", user_role="Hakem")

        conn.commit()
        conn.close()

        
        return render_template("notifi.html", message="✅ Değerlendirme başarıyla kaydedildi!", redirect_url="/")

        
    @app.route("/editor/final_pdf/<tracking_number>")
    def final_pdf_with_review(tracking_number):
        conn = get_db_connection()
        cur = conn.cursor()

    
        cur.execute("""
            SELECT original_article_id 
            FROM anonymous_articles 
            WHERE tracking_number = ?
        """, (tracking_number,))
        row = cur.fetchone()

        if not row:
            return "Anonim kayıt bulunamadı."

        original_article_id = row[0]

    
        cur.execute("""
            SELECT file_name 
            FROM articles 
            WHERE id = ?
        """, (original_article_id,))
        row2 = cur.fetchone()

        if not row2:
           return "Orijinal makale bulunamadı."

        filename = row2[0]
        filepath = os.path.join("uploads", filename)

        if not os.path.exists(filepath):
            return f"Dosya bulunamadı: {filepath}"

    
        cur.execute("""
            SELECT fluency, content, originality, impact, methodology, review_text 
            FROM reviews 
            WHERE tracking_number = ?
        """, (tracking_number,))
        review_row = cur.fetchone()
        conn.close()

        if not review_row:
            return "Değerlendirme bulunamadı."

        review_data = {
            "fluency": review_row[0],
            "content": review_row[1],
            "originality": review_row[2],
            "impact": review_row[3],
            "methodology": review_row[4],
            "review_text": review_row[5]
        }
    
        with open(filepath, "rb") as f:
            original_pdf = f.read()

        final_pdf = append_review_page(original_pdf, review_data)

        return send_file(
            io.BytesIO(final_pdf),
            mimetype='application/pdf',
            download_name=f"final_{filename}"
        )
    @app.route("/editor/review", methods=["GET", "POST"])
    def editor_review_panel():
        conn = get_db_connection()
        cur = conn.cursor()

        if request.method == "POST":
            tracking_number = request.form.get("tracking_number")
            action = request.form.get("action")

            if not tracking_number:
                conn.close()
                return "Tracking Number eksik!", 400

            if action == "show":
                conn.close()
                return redirect(url_for('final_pdf_with_review', tracking_number=tracking_number))

            if action == "approve":
                
                cur.execute("SELECT email FROM articles WHERE tracking_number = ?", (tracking_number,))
                row = cur.fetchone()
                if not row:
                    conn.close()
                    return "Makale bulunamadı!", 404

                user_email = row[0]

                
                cur.execute("""
                SELECT assigned_reviewer FROM anonymous_articles 
                WHERE tracking_number = ?
                """, (tracking_number,))
                reviewer_row = cur.fetchone()

                if reviewer_row and reviewer_row[0]:
                    reviewer_email = reviewer_row[0]
                    
                    cur.execute("""
                    UPDATE reviewers 
                    SET available = 1 
                    WHERE email = ?
                    """, (reviewer_email,))

                
                cur.execute("""
                    UPDATE articles 
                    SET status = 'Yazara Gönderildi'
                    WHERE tracking_number = ?
                """, (tracking_number,))

                
                cur.execute("""
                    INSERT INTO notifications (email, message_text) 
                    VALUES (?, ?)
                """, (user_email, f"Makaleniz ({tracking_number}) editör tarafından onaylandı ve yazara yönlendirildi."))

                conn.commit()
                conn.close()

                log_action(f"Makale {tracking_number} editör tarafından onaylandı ve yazara yönlendirildi.", user_role="Editör")

                
                return render_template(
                    "notifi.html",
                    message="✅ Makale başarıyla onaylandı ve yazara yönlendirildi!",
                    redirect_url="/"
                )

        
        cur.execute("""
            SELECT tracking_number 
            FROM articles 
            WHERE status = 'Değerlendirildi'
        """)
        rows = cur.fetchall()
        conn.close()

        tracking_numbers = [row[0] for row in rows]

        return render_template("editor_review.html", tracking_numbers=tracking_numbers)

    @app.route("/yazar_sonuc", methods=["GET", "POST"])
    def yazar_sonuc():
        if request.method == "POST":
            tracking_number = request.form.get("tracking_number")

            conn = get_db_connection()
            cur = conn.cursor()

        
            cur.execute("""
            SELECT a.status 
            FROM articles a
            JOIN anonymous_articles aa ON a.tracking_number = aa.tracking_number
            WHERE aa.tracking_number = ?

            """, (tracking_number,))
            row = cur.fetchone()
            conn.close()

            if not row:
                return render_template("yazar_sonuc.html", error="Takip numarasına ait makale bulunamadı.")

            status = row[0]
            if status == "Yazara Gönderildi":
                return render_template("yazar_sonuc.html", show_pdf=True, tracking_number=tracking_number)
            else:
                return render_template("yazar_sonuc.html", error="Makale henüz değerlendirilmedi veya onaylanmadı.")

        return render_template("yazar_sonuc.html")
    @app.route("/yazar")
    def yazar_page():
        return render_template("yazar.html")

    @app.route("/editor")
    def editor_page():
        return render_template("editor.html")
    
    
