import os
import threading

from dotenv import load_dotenv
from loguru import logger

if __name__ == "__main__":
    load_dotenv()

    from main import app, q
    from src.workers import audio_send_worker

    threads = [
        threading.Thread(target=audio_send_worker, args=(q,))
        for _ in range(int(os.getenv("WORKERS_COUNT", 1)))
    ]
    for t in threads:
        t.start()

    logger.info("https://t.me/{}".format(app.get_me().username))
    app.polling(True)
    q.join()
    for _ in threads:
        q.put(None)
    for t in threads:
        t.join()
