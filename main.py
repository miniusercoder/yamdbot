import math
import os
import queue
import uuid

import requests
import simplejson as json
from telebot import TeleBot, types, apihelper

from src.YandexMusic import YandexMusic

with open("config.json", "r") as _f:
    token = json.load(_f)["token"]

app = TeleBot(os.getenv("BOT_API", ""), num_threads=int(os.getenv("WORKERS_COUNT", 1)))
yandex_music = YandexMusic(token)
q = queue.Queue()


@app.inline_handler(lambda query: True)
def inline_handler(query: types.InlineQuery):
    offset = int(query.offset) if query.offset else 0
    on_page = 30
    message = query.query
    track_list = yandex_music.get_search_results(message, count=on_page, offset=offset)
    if not track_list.count:
        if offset == 0:
            app.answer_inline_query(
                query.id,
                [
                    types.InlineQueryResultAudio(
                        id="0",
                        audio_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        title="Нет результатов",
                        input_message_content=types.InputTextMessageContent(
                            "Нет результатов по запросу"
                        ),
                    )
                ],
            )
            return
        else:
            app.answer_inline_query(query.id, [])
            return
    answer_buttons = []
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Загрузка...", callback_data="loading"))
    for track in track_list.tracks:
        artists = ", ".join(artist.name for artist in track.artists)
        answer_buttons.append(
            types.InlineQueryResultAudio(
                id=f"{track.id}:{track.albums[0].id}",
                audio_url=f"https://helper20sms.ru/wp-content/uploads/2024/04/test.mp3?{str(uuid.uuid4())}",
                title=track.title,
                performer=artists,
                audio_duration=int(track.duration_ms / 1000),
                reply_markup=kb,
            )
        )
    app.answer_inline_query(
        query.id,
        answer_buttons,
        cache_time=1,
        is_personal=True,
        next_offset=str(offset + on_page),
    )


@app.chosen_inline_handler(lambda query: True)
def chosen_inline_handler(query: types.ChosenInlineResult):
    q.put((query.inline_message_id, query.result_id))


@app.callback_query_handler(lambda query: query.data == "loading")
def loading_handler(query: types.CallbackQuery):
    app.answer_callback_query(
        query.id,
        "Пожалуйста, подождите. Ваш трек загружается...",
        cache_time=0,
    )


@app.message_handler(func=lambda message: True)
def search_audio(message: types.Message):
    if message.chat.type != "private":
        return
    on_page = 15
    offset = 0
    track_list = yandex_music.get_search_results(
        message.text, count=on_page, offset=offset
    )
    tracks_count = track_list.total
    if not track_list.count:
        app.send_message(message.chat.id, "Нет результатов по запросу")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for track in track_list.tracks:
        artists = ", ".join(artist.name for artist in track.artists)
        kb.add(
            types.InlineKeyboardButton(
                f"{artists} - {track.title}",
                callback_data=f"track:{track.id}:{track.albums[0].id}",
            )
        )
    buttons = []
    if offset != 0:
        buttons.append(
            types.InlineKeyboardButton(
                "<",
                callback_data=f"list:{offset-1}:{message.text}",
            )
        )
    buttons.append(
        types.InlineKeyboardButton(
            f"[{offset + 1}/{math.ceil(tracks_count / on_page)}]",
            callback_data="no_action",
        )
    )
    if (offset + 1) * on_page < tracks_count:
        buttons.append(
            types.InlineKeyboardButton(
                ">",
                callback_data=f"list:{offset+1}:{message.text}",
            )
        )
    kb.row(*buttons)
    app.send_message(message.chat.id, "Результаты поиска:", reply_markup=kb)


@app.callback_query_handler(lambda query: query.data.startswith("list"))
def list_handler(query: types.CallbackQuery):
    try:
        app.answer_callback_query(query.id)
    except apihelper.ApiTelegramException:
        pass
    offset, message = query.data.split(":")[1:]
    offset = int(offset)
    on_page = 15
    track_list = yandex_music.get_search_results(
        message, count=on_page, offset=offset * on_page
    )
    tracks_count = track_list.total
    kb = types.InlineKeyboardMarkup(row_width=1)
    for track in track_list.tracks:
        artists = ", ".join(artist.name for artist in track.artists)
        kb.add(
            types.InlineKeyboardButton(
                f"{artists} - {track.title}",
                callback_data=f"track:{track.id}:{track.albums[0].id}",
            )
        )
    buttons = []
    if offset != 0:
        buttons.append(
            types.InlineKeyboardButton(
                "<",
                callback_data=f"list:{offset-1}:{message}",
            )
        )
    buttons.append(
        types.InlineKeyboardButton(
            f"[{offset + 1}/{math.ceil(tracks_count / 30)}]",
            callback_data="no_action",
        )
    )
    if (offset + 1) * 30 < tracks_count:
        buttons.append(
            types.InlineKeyboardButton(
                ">",
                callback_data=f"list:{offset+1}:{message}",
            )
        )
    kb.row(*buttons)
    app.edit_message_text(
        "Результаты поиска:",
        query.message.chat.id,
        query.message.message_id,
        reply_markup=kb,
    )


@app.callback_query_handler(lambda query: query.data.startswith("track"))
def track_handler(query: types.CallbackQuery):
    wait_msg = app.send_message(
        query.message.chat.id,
        "Пожалуйста, подождите. Ваш трек загружается...",
    )
    track_id = query.data.split(":")[1]
    track = yandex_music.get_track_info(track_id)
    download_uri = yandex_music.get_track_download_uri(track.id)
    if not download_uri:
        try:
            app.delete_message(wait_msg.chat.id, wait_msg.message_id)
        except apihelper.ApiTelegramException:
            pass
        app.edit_message_text(
            "Ошибка при загрузке трека",
            query.message.chat.id,
            query.message.message_id,
        )
        return
    audio = yandex_music.download_track(download_uri)
    thumbnail = requests.get(track.thumbnail).content if track.thumbnail else None
    app.send_audio(
        query.message.chat.id,
        audio,
        duration=track.duration_ms // 1000,
        performer=", ".join(artist.name for artist in track.artists),
        title=track.title,
        thumb=thumbnail,
    )
    try:
        app.answer_callback_query(query.id)
    except apihelper.ApiTelegramException:
        pass
    try:
        app.delete_message(wait_msg.chat.id, wait_msg.message_id)
    except apihelper.ApiTelegramException:
        pass


@app.message_handler(commands=["token"])
def new_token_handler(message: types.Message):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        return
    app.delete_message(message.chat.id, message.message_id)
    new_token = message.text.split(" ")[1]
    with open("config.json", "w") as f:
        json.dump({"token": new_token}, f)
    yandex_music.token = new_token
    app.send_message(message.chat.id, "Токен обновлён")
