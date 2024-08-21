import base64
import hashlib
import hmac
import os
import time
import uuid

import requests
import simplejson as json
from loguru import logger

from .models import *


class YandexMusic:
    __slots__ = ("__token", "__session")
    __token: str
    __session: requests.Session

    def __init__(self, token: str):
        self.__token = token
        self.__session = requests.session()
        self.__session.headers.update(
            {
                "X-Yandex-Music-Client": "YandexMusicDesktopAppWindows/5.13.2",
                "X-Yandex-Music-Frontend": "new",
                "Accept-Language": "ru",
                "Authorization": f"OAuth {self.__token}",
                "X-Yandex-Music-Without-Invocation-Info": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "YandexMusic/5.13.2 Chrome/118.0.5993.129 Electron/27.0.4 Safari/537.36",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Accept": "*/*",
                "Origin": "music-application://desktop",
            }
        )

    @property
    def token(self):
        return self.__token

    @token.setter
    def token(self, token: str):
        self.__token = token
        self.__session.headers.update({"Authorization": f"OAuth {self.__token}"})

    def get_search_results(
        self, query: str, count: int = 10, offset: int = 0
    ) -> TrackList:
        link = "https://api.music.yandex.net/search/instant/mixed"
        params = {
            "text": query,
            "type": "album,artist,playlist,track,wave,podcast,podcast_episode",
            "page": offset // count,
            "filter": "track",
            "pageSize": count,
            "withLikesCount": "true",
        }
        self.__session.headers.update({"X-Request-Id": str(uuid.uuid4())})
        response = self.__session.get(link, params=params)
        try:
            response = response.json(cls=json.JSONDecoder)
        except json.JSONDecodeError:
            logger.exception("Failed to parse response")
            return TrackList()
        if not isinstance(response, dict) or not response.get("results"):
            logger.error("Failed to get search results")
            logger.debug(json.dumps(response, indent=2, ensure_ascii=False))
            return TrackList()
        tracks = response["results"]
        tracks = filter(lambda track: track.get("type") == "track", tracks)
        tracks = map(lambda track: track.get("track"), tracks)
        try:
            tracks = [Track(**track) for track in tracks]
        except TypeError:
            logger.exception("Failed to parse tracks")
            return TrackList()
        for track in tracks:
            if track.thumbnail:
                track.thumbnail = "https://" + track.thumbnail.replace("%%", "200x200")
        track_list = TrackList(
            tracks=tracks, count=len(tracks), total=response["total"]
        )
        return track_list

    def get_track_info(self, track_id: str) -> Track:
        link = "https://api.music.yandex.net/tracks"
        params = {
            "trackIds": track_id,
            "removeDuplicates": "false",
            "withProgress": "true",
        }
        self.__session.headers.update({"X-Request-Id": str(uuid.uuid4())})
        response = self.__session.get(link, params=params)
        try:
            response = response.json(cls=json.JSONDecoder)
        except json.JSONDecodeError:
            logger.exception("Failed to parse response")
            return Track()
        if not isinstance(response, list) or len(response) == 0:
            logger.error("Failed to get track info")
            logger.debug(json.dumps(response, indent=2, ensure_ascii=False))
            return Track()
        track = response[0]
        try:
            track = Track(**track)
        except TypeError:
            logger.exception("Failed to parse track")
            return Track()
        if track.thumbnail:
            track.thumbnail = "https://" + track.thumbnail.replace("%%", "200x200")
        return track

    def get_track_download_uri(self, track_id: int) -> str | None:
        full_timestamp = int(time.time() * 1000)
        timestamp = full_timestamp // 1000
        link = f"https://api.music.yandex.net/tracks/{track_id}/download-info"
        secret_key = os.getenv("YANDEX_SECRET_KEY")
        sign = hmac.new(
            secret_key.encode(), f"{timestamp}{track_id}".encode(), hashlib.sha256
        )
        sign = base64.b64encode(sign.digest()).decode()[:-1]
        params = {
            "preview": "false",
            "direct": "false",
            "isAliceRequester": "false",
            "requireMp3Link": "false",
            "canUseStreaming": "false",
            "ts": timestamp,
            "sign": sign,
        }
        self.__session.headers.update({"X-Request-Id": str(uuid.uuid4())})
        response = self.__session.get(link, params=params)
        try:
            response = response.json(cls=json.JSONDecoder)
        except json.JSONDecodeError:
            logger.exception("Failed to parse response")
            return None
        if not isinstance(response, list) or len(response) == 0:
            logger.error("Failed to get download uri")
            logger.debug(json.dumps(response, indent=2, ensure_ascii=False))
            return None
        logger.debug(json.dumps(response, indent=2, ensure_ascii=False))
        max_bitrate = 0
        max_bitrate_link = None
        for link in response:
            if link["bitrateInKbps"] > max_bitrate:
                max_bitrate = link["bitrateInKbps"]
                max_bitrate_link = link["downloadInfoUrl"]
        max_bitrate_link = (
            f"{max_bitrate_link}&format=json&__t={full_timestamp}&external-domain=next.music.yandex.ru"
            f"&overembed=false"
        )
        response = self.__session.get(max_bitrate_link)
        try:
            response = response.json(cls=json.JSONDecoder)
        except json.JSONDecodeError:
            logger.exception("Failed to parse response")
            return None
        if (
            not isinstance(response, dict)
            or not response.get("path")
            or not response.get("host")
        ):
            logger.error("Failed to get download uri")
            logger.debug(json.dumps(response, indent=2, ensure_ascii=False))
            return None
        link_hash = hashlib.md5(
            f"{os.getenv('YANDEX_SECRET_KEY')}{response['path'][1:]}{response['s']}".encode()
        )
        return (
            f"https://{response['host']}/get-mp3/{link_hash.hexdigest()}/"
            f"{response['ts']}{response['path']}?track-id={track_id}&play=false"
        )

    def download_track(self, link: str) -> bytes:
        self.__session.headers.update({"Range": "bytes=0-"})
        self.__session.headers.pop("X-Request-Id")
        return self.__session.get(link).content
