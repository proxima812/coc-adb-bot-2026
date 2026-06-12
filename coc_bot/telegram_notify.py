from __future__ import annotations

import json
import os
import secrets
import urllib.parse
import urllib.request
from pathlib import Path

from loguru import logger


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


class TelegramNotifier:
    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    def send(self, text: str) -> bool:
        if not self.token:
            logger.warning("Telegram bot token is not configured")
            return False

        chat_id = self.chat_id or self._latest_chat_id()
        if not chat_id:
            logger.warning("Telegram chat id is not configured; send a message to the bot or set TELEGRAM_CHAT_ID")
            return False

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        try:
            with urllib.request.urlopen(self._api_url("sendMessage"), data=payload, timeout=10) as response:
                raw = response.read()
        except Exception as exc:
            logger.warning("Telegram send failed: {}", exc)
            return False

        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Telegram send returned invalid JSON")
            return False

        if not data.get("ok"):
            logger.warning("Telegram send failed: {}", data)
            return False
        self.chat_id = str(chat_id)
        return True

    def send_photo(self, photo: bytes, caption: str = "", filename: str = "screenshot.png") -> bool:
        if not self.token:
            logger.warning("Telegram bot token is not configured")
            return False
        if not photo:
            logger.warning("Telegram send_photo called with empty photo")
            return False

        chat_id = self.chat_id or self._latest_chat_id()
        if not chat_id:
            logger.warning("Telegram chat id is not configured; send a message to the bot or set TELEGRAM_CHAT_ID")
            return False

        boundary = f"----coc-bot-{secrets.token_hex(8)}"
        body = self._build_multipart(boundary, chat_id, caption, photo, filename)
        request = urllib.request.Request(
            self._api_url("sendPhoto"),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
        except Exception as exc:
            logger.warning("Telegram send_photo failed: {}", exc)
            return False

        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Telegram send_photo returned invalid JSON")
            return False

        if not data.get("ok"):
            logger.warning("Telegram send_photo failed: {}", data)
            return False
        self.chat_id = str(chat_id)
        return True

    @staticmethod
    def _build_multipart(boundary: str, chat_id: str, caption: str, photo: bytes, filename: str) -> bytes:
        lines: list[bytes] = []
        delim = f"--{boundary}".encode("utf-8")
        lines.append(delim)
        lines.append(b'Content-Disposition: form-data; name="chat_id"')
        lines.append(b"")
        lines.append(str(chat_id).encode("utf-8"))
        if caption:
            lines.append(delim)
            lines.append(b'Content-Disposition: form-data; name="caption"')
            lines.append(b"")
            lines.append(caption.encode("utf-8"))
        lines.append(delim)
        lines.append(f'Content-Disposition: form-data; name="photo"; filename="{filename}"'.encode("utf-8"))
        lines.append(b"Content-Type: image/png")
        lines.append(b"")
        lines.append(photo)
        lines.append(f"--{boundary}--".encode("utf-8"))
        lines.append(b"")
        return b"\r\n".join(lines)

    def _latest_chat_id(self) -> str:
        try:
            with urllib.request.urlopen(self._api_url("getUpdates"), timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Telegram getUpdates failed: {}", exc)
            return ""

        if not data.get("ok"):
            logger.warning("Telegram getUpdates failed: {}", data)
            return ""

        for update in reversed(data.get("result", [])):
            message = update.get("message") or update.get("edited_message")
            if not message:
                continue
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id is not None:
                return str(chat_id)
        return ""

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"
