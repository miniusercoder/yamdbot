import os
import threading

from dotenv import load_dotenv
from loguru import logger
from telebot import apihelper

if __name__ == "__main__":
    load_dotenv()

    if os.getenv("TELEGRAM_API_URL"):
        logger.debug(
            f"Setting up custom telegram API_URL: {os.getenv('TELEGRAM_API_URL')}"
        )
        apihelper.API_URL = os.getenv("TELEGRAM_API_URL")

    from main import app, q
    from src.workers import audio_send_worker

    threads = [
        threading.Thread(target=audio_send_worker, args=(q,))
        for _ in range(int(os.getenv("WORKERS_COUNT", 1)))
    ]
    for t in threads:
        t.start()

    logger.info(f"https://t.me/{app.get_me().username}")
    app.infinity_polling()
    q.join()
    for _ in threads:
        q.put(None)
    for t in threads:
        t.join()
