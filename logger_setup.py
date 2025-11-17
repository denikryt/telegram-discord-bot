import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Create the logs folder if it does not exist
    os.makedirs("logs", exist_ok=True)

    # Set log file path
    log_file_path = os.path.join("logs", "app.log")

    # Remove the current app.log file when the program starts
    with open(log_file_path, 'w', encoding='utf-8'):
        pass

    # Set up log rotation
    rotating_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )

    # Set up log formatting
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rotating_handler.setFormatter(formatter)

    # Set up the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Remove any existing handlers
    logger.addHandler(rotating_handler)