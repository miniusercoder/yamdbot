import os

import requests
from loguru import logger
from telebot import types, apihelper

from main import yandex_music, app


def audio_send_worker(q):
    while True:
        task: tuple[str, str] | None = q.get()
        if task is None:
            return
        inline_message_id, track_id = task
        track = yandex_music.get_track_info(track_id)
        download_uri = yandex_music.get_track_download_uri(track.id)
        if not download_uri:
            app.edit_message_caption(
                "Ошибка при загрузке трека",
                inline_message_id=inline_message_id,
            )
            q.task_done()
            return
        audio = yandex_music.download_track(download_uri)
        thumbnail = requests.get(track.thumbnail).content if track.thumbnail else None
        msg = app.send_audio(
            int(os.getenv("FILES_CHANNEL")),
            audio,
            duration=track.duration_ms // 1000,
            performer=", ".join(artist.name for artist in track.artists),
            title=track.title,
            thumbnail=thumbnail,
        )
        audio = types.InputMediaAudio(
            media=msg.audio.file_id,
        )
        try:
            app.edit_message_media(media=audio, inline_message_id=inline_message_id)
        except apihelper.ApiTelegramException:
            logger.exception("Failed to edit message")
        del audio, thumbnail
        try:
            app.delete_message(msg.chat.id, msg.message_id)
        except apihelper.ApiTelegramException:
            pass
        q.task_done()
