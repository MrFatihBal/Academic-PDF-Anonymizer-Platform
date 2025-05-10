from flask import Flask, g, session
from routes import configure_routes
import pyodbc

app = Flask(__name__)

@app.teardown_appcontext
def close_db_connection(exception):
    conn = g.pop('conn', None)
    if conn is not None:
        conn.close()
app.secret_key = "kralgizlisifre"
configure_routes(app)

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000, debug=True)
