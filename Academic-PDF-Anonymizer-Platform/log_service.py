import logging
import datetime

LOG_FILE = "app.log"

# Log formatını sadece bizim loglarımız için ayarla
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="# %(asctime)s - %(message)s",
    encoding="utf-8"
)

def log_action(action, user_role=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"# {timestamp} - {action} (Rol: {user_role})"
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_message + "\n")
