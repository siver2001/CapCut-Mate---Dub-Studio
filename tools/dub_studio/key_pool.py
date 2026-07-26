from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .config import DEFAULT_CLOUD_MODEL


_PACIFIC = ZoneInfo("America/Los_Angeles")
_POOL_LOCK = threading.RLock()
_POOL_SINGLETON: "GeminiKeyPool | None" = None


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    value = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return value, buffer


def protect_secret(secret: str) -> str:
    raw = secret.encode("utf-8")
    if os.name != "nt":
        raise RuntimeError("Kho API key an toàn hiện chỉ hỗ trợ Windows DPAPI.")
    source, source_buffer = _blob(raw)
    encrypted = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "CapCut Mate Gemini key",
        None,
        None,
        None,
        0,
        ctypes.byref(encrypted),
    ):
        raise ctypes.WinError()
    try:
        data = ctypes.string_at(encrypted.pbData, encrypted.cbData)
        return base64.b64encode(data).decode("ascii")
    finally:
        kernel32.LocalFree(encrypted.pbData)
        del source_buffer


def unprotect_secret(encrypted_secret: str) -> str:
    raw = base64.b64decode(encrypted_secret.encode("ascii"))
    if os.name != "nt":
        raise RuntimeError("Kho API key an toàn hiện chỉ hỗ trợ Windows DPAPI.")
    source, source_buffer = _blob(raw)
    decrypted = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(decrypted),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(decrypted.pbData, decrypted.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(decrypted.pbData)
        del source_buffer


def mask_key(secret: str) -> str:
    value = str(secret or "").strip()
    if len(value) <= 10:
        return "••••••"
    return f"{value[:5]}…{value[-4:]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _usage_day() -> str:
    return _utc_now().astimezone(_PACIFIC).date().isoformat()


def _next_pacific_midnight() -> datetime:
    now_pt = _utc_now().astimezone(_PACIFIC)
    next_day = now_pt.date() + timedelta(days=1)
    return datetime.combine(next_day, datetime.min.time(), tzinfo=_PACIFIC).astimezone(
        timezone.utc
    )


def _parse_retry_seconds(error_payload: Any, fallback: int = 60) -> int:
    texts = [json.dumps(error_payload, ensure_ascii=False) if error_payload else ""]
    for text in texts:
        match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', text)
        if match:
            return max(int(float(match.group(1))) + 1, 1)
        match = re.search(r'"retryAfter"\s*:\s*"(\d+(?:\.\d+)?)"', text)
        if match:
            return max(int(float(match.group(1))) + 1, 1)
        match = re.search(r"retry\s+(?:in|after)\s+(\d+)", text, re.IGNORECASE)
        if match:
            return max(int(match.group(1)), 1)
    return fallback


def _is_daily_quota(error_payload: Any) -> bool:
    text = json.dumps(error_payload, ensure_ascii=False).casefold()
    return any(
        marker in text
        for marker in (
            "per_day",
            "perday",
            "requests per day",
            "request per day",
            "rpd",
        )
    )


@dataclass(frozen=True)
class KeyCandidate:
    key_id: str
    name: str
    secret: str
    priority: int
    project_group: str


class GeminiKeyPool:
    schema_version = 1

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (
            Path.home() / ".capcut_mate" / "gemini_key_pool.json"
        )
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "activeKeyId": "",
            "keys": [],
        }
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return
            except Exception:
                return
            if isinstance(payload, dict) and isinstance(payload.get("keys"), list):
                self._data = payload
                self._reset_daily_usage_locked()

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, self.path)

    def save(self) -> None:
        with self._lock:
            self._save_locked()

    def _reset_daily_usage_locked(self) -> None:
        today = _usage_day()
        changed = False
        for item in self._data["keys"]:
            if item.get("usageDay") != today:
                item["usageDay"] = today
                item["requestsToday"] = 0
                item["tokensToday"] = 0
                if item.get("status") == "daily_exhausted":
                    item["status"] = "ready"
                    item["cooldownUntil"] = ""
                changed = True
        if changed and self.path.exists():
            self._save_locked()

    def migrate_legacy_key(self, secret: str, *, name: str = "Key chính") -> str:
        value = str(secret or "").strip()
        if not value:
            return ""
        with self._lock:
            for item in self._data["keys"]:
                try:
                    if unprotect_secret(item["encryptedKey"]) == value:
                        return str(item["id"])
                except Exception:
                    continue
            return self.add_key(name=name, secret=value, priority=1)

    def add_key(
        self,
        *,
        name: str,
        secret: str,
        priority: int | None = None,
        daily_request_limit: int | None = None,
        project_group: str = "",
    ) -> str:
        clean_secret = str(secret or "").strip()
        if not clean_secret:
            raise ValueError("API key không được để trống.")
        with self._lock:
            existing_ids = {str(item.get("id") or "") for item in self._data["keys"]}
            key_id = str(uuid.uuid4())
            while key_id in existing_ids:
                key_id = str(uuid.uuid4())
            if priority is None:
                priority = len(self._data["keys"]) + 1
            item = {
                "id": key_id,
                "name": str(name or f"Gemini key {priority}").strip(),
                "encryptedKey": protect_secret(clean_secret),
                "maskedKey": mask_key(clean_secret),
                "priority": max(int(priority), 1),
                "enabled": True,
                "status": "ready",
                "cooldownUntil": "",
                "lastError": "",
                "lastUsedAt": "",
                "usageDay": _usage_day(),
                "requestsToday": 0,
                "tokensToday": 0,
                "dailyRequestLimit": (
                    max(int(daily_request_limit), 1)
                    if daily_request_limit
                    else None
                ),
                "projectGroup": project_group or key_id,
                "model": DEFAULT_CLOUD_MODEL,
            }
            self._data["keys"].append(item)
            self._sort_locked()
            if not self._data.get("activeKeyId"):
                self._data["activeKeyId"] = key_id
            self._save_locked()
            return key_id

    def update_key(
        self,
        key_id: str,
        *,
        name: str | None = None,
        secret: str | None = None,
        priority: int | None = None,
        daily_request_limit: int | None = None,
    ) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            if name is not None:
                item["name"] = str(name).strip() or item["name"]
            if secret is not None and str(secret).strip():
                item["encryptedKey"] = protect_secret(str(secret).strip())
                item["maskedKey"] = mask_key(str(secret).strip())
                item["status"] = "ready"
                item["cooldownUntil"] = ""
                item["lastError"] = ""
            if priority is not None:
                item["priority"] = max(int(priority), 1)
            item["dailyRequestLimit"] = (
                max(int(daily_request_limit), 1)
                if daily_request_limit
                else None
            )
            self._sort_locked()
            self._save_locked()

    def delete_key(self, key_id: str) -> None:
        with self._lock:
            before = len(self._data["keys"])
            self._data["keys"] = [
                item for item in self._data["keys"] if item.get("id") != key_id
            ]
            if len(self._data["keys"]) == before:
                raise KeyError(key_id)
            if self._data.get("activeKeyId") == key_id:
                self._data["activeKeyId"] = ""
            self._save_locked()

    def set_enabled(self, key_id: str, enabled: bool) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            item["enabled"] = bool(enabled)
            item["status"] = "ready" if enabled else "disabled"
            item["cooldownUntil"] = ""
            self._save_locked()

    def _sort_locked(self) -> None:
        self._data["keys"].sort(
            key=lambda item: (
                int(item.get("priority") or 9999),
                str(item.get("name") or "").casefold(),
            )
        )

    def _find_locked(self, key_id: str) -> dict[str, Any]:
        for item in self._data["keys"]:
            if item.get("id") == key_id:
                return item
        raise KeyError(key_id)

    def candidates(self) -> list[KeyCandidate]:
        with self._lock:
            self._reset_daily_usage_locked()
            now = _utc_now()
            result: list[KeyCandidate] = []
            for item in self._data["keys"]:
                if not item.get("enabled", True):
                    continue
                cooldown_raw = str(item.get("cooldownUntil") or "")
                if cooldown_raw:
                    try:
                        cooldown = datetime.fromisoformat(cooldown_raw)
                    except ValueError:
                        cooldown = now
                    if cooldown > now:
                        continue
                    item["cooldownUntil"] = ""
                    if item.get("status") in {"cooldown", "daily_exhausted"}:
                        item["status"] = "ready"
                if item.get("status") in {"invalid", "disabled"}:
                    continue
                try:
                    secret = unprotect_secret(item["encryptedKey"])
                except Exception:
                    item["status"] = "invalid"
                    item["lastError"] = "Không giải mã được API key."
                    continue
                result.append(
                    KeyCandidate(
                        key_id=str(item["id"]),
                        name=str(item.get("name") or "Gemini key"),
                        secret=secret,
                        priority=int(item.get("priority") or 9999),
                        project_group=str(item.get("projectGroup") or item["id"]),
                    )
                )
            self._sort_locked()
            self._save_locked()
            return result

    def candidate(self, key_id: str) -> KeyCandidate:
        with self._lock:
            item = self._find_locked(key_id)
            return KeyCandidate(
                key_id=str(item["id"]),
                name=str(item.get("name") or "Gemini key"),
                secret=unprotect_secret(item["encryptedKey"]),
                priority=int(item.get("priority") or 9999),
                project_group=str(item.get("projectGroup") or item["id"]),
            )

    def record_verified(self, key_id: str) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            item["status"] = "ready"
            item["cooldownUntil"] = ""
            item["lastError"] = ""
            self._save_locked()

    def record_attempt(self, key_id: str) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            self._reset_daily_usage_locked()
            item["lastUsedAt"] = _utc_now().isoformat()
            item["requestsToday"] = int(item.get("requestsToday") or 0) + 1
            self._save_locked()

    def record_success(self, key_id: str, usage: dict[str, Any] | None = None) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            self._reset_daily_usage_locked()
            tokens = int(
                (usage or {}).get("totalTokenCount")
                or (usage or {}).get("totalTokens")
                or 0
            )
            item["status"] = "ready"
            item["lastError"] = ""
            item["lastUsedAt"] = _utc_now().isoformat()
            item["tokensToday"] = int(item.get("tokensToday") or 0) + tokens
            self._data["activeKeyId"] = key_id
            self._save_locked()

    def record_quota_failure(self, key_id: str, error_payload: Any) -> str:
        with self._lock:
            item = self._find_locked(key_id)
            now = _utc_now()
            if _is_daily_quota(error_payload):
                until = _next_pacific_midnight()
                status = "daily_exhausted"
            else:
                until = now + timedelta(
                    seconds=_parse_retry_seconds(error_payload)
                )
                status = "cooldown"
            item["status"] = status
            item["cooldownUntil"] = until.isoformat()
            item["lastError"] = "Gemini quota/rate limit (429)"
            self._save_locked()
            return status

    def record_invalid(self, key_id: str, message: str) -> None:
        with self._lock:
            item = self._find_locked(key_id)
            item["status"] = "invalid"
            item["lastError"] = str(message or "API key không hợp lệ")[:240]
            self._save_locked()

    def rows(self) -> list[dict[str, Any]]:
        with self._lock:
            self._reset_daily_usage_locked()
            now = _utc_now()
            rows: list[dict[str, Any]] = []
            for item in self._data["keys"]:
                status = str(item.get("status") or "ready")
                cooldown_raw = str(item.get("cooldownUntil") or "")
                if cooldown_raw:
                    try:
                        remaining = max(
                            int(
                                (
                                    datetime.fromisoformat(cooldown_raw) - now
                                ).total_seconds()
                            ),
                            0,
                        )
                    except ValueError:
                        remaining = 0
                    if remaining and status == "cooldown":
                        status_label = f"Chờ {remaining}s"
                    elif remaining and status == "daily_exhausted":
                        status_label = "Hết quota ngày"
                    else:
                        status_label = "Sẵn sàng"
                else:
                    status_label = {
                        "ready": "Sẵn sàng",
                        "invalid": "Key lỗi",
                        "disabled": "Đã tắt",
                    }.get(status, status)
                limit = item.get("dailyRequestLimit")
                requests = int(item.get("requestsToday") or 0)
                quota_percent = (
                    max(0.0, min(100.0, (1.0 - requests / int(limit)) * 100.0))
                    if limit
                    else (0.0 if status == "daily_exhausted" else None)
                )
                rows.append(
                    {
                        "id": str(item["id"]),
                        "name": str(item.get("name") or "Gemini key"),
                        "maskedKey": str(item.get("maskedKey") or "••••••"),
                        "priority": int(item.get("priority") or 9999),
                        "status": status,
                        "statusLabel": status_label,
                        "quotaPercent": quota_percent,
                        "quotaLabel": (
                            f"~{quota_percent:.0f}%"
                            if quota_percent is not None
                            else "Không rõ"
                        ),
                        "requestsToday": requests,
                        "tokensToday": int(item.get("tokensToday") or 0),
                        "enabled": bool(item.get("enabled", True)),
                        "dailyRequestLimit": limit,
                        "active": self._data.get("activeKeyId") == item.get("id"),
                    }
                )
            return rows

    def has_keys(self) -> bool:
        with self._lock:
            return bool(self._data["keys"])


def get_gemini_key_pool(*, reload: bool = False) -> GeminiKeyPool:
    global _POOL_SINGLETON
    with _POOL_LOCK:
        if reload or _POOL_SINGLETON is None:
            _POOL_SINGLETON = GeminiKeyPool()
        return _POOL_SINGLETON


def get_primary_gemini_api_key() -> str:
    """Compatibility bridge for optional integrations that accept one key only."""
    if os.getenv(
        "DUB_CLOUD_KEY_POOL_ENABLED",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}:
        candidates = get_gemini_key_pool().candidates()
        return candidates[0].secret if candidates else ""
    return os.getenv("DUB_CLOUD_API_KEY", "").strip()


def reset_gemini_key_pool_for_tests() -> None:
    global _POOL_SINGLETON
    with _POOL_LOCK:
        _POOL_SINGLETON = None
