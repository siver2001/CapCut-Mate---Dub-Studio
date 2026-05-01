from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


DEFAULT_API_BASES = [
    "http://127.0.0.1/api",
    "http://localhost/api",
    "https://api.douyin.wtf/api",
]


def _api_bases() -> list[str]:
    raw = os.environ.get("DOUYIN_TIKTOK_API_BASE_URL") or os.environ.get("DOUYIN_API_BASE_URL") or ""
    bases = [part.strip().rstrip("/") for part in raw.split(",") if part.strip()]
    bases.extend(DEFAULT_API_BASES)
    result: list[str] = []
    seen: set[str] = set()
    for base in bases:
        if base and base not in seen:
            result.append(base)
            seen.add(base)
    return result


def _safe_filename(value: str, fallback: str = "douyin_video") -> str:
    text = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", str(value or "").strip())
    text = re.sub(r"\s+", " ", text).strip(" .")
    return (text or fallback)[:180]


def _walk_values(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_values(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_values(value)
    else:
        yield obj


def _first_video_url(data: dict) -> str:
    video_data = data.get("video_data") if isinstance(data, dict) else {}
    preferred_keys = [
        "nwm_video_url_HQ",
        "nwm_video_url",
        "no_watermark_video_url",
        "wm_video_url_HQ",
        "wm_video_url",
        "video_url",
        "play_addr",
    ]
    if isinstance(video_data, dict):
        for key in preferred_keys:
            value = video_data.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.startswith(("http://", "https://")):
                        return item
    for value in _walk_values(data):
        if isinstance(value, str) and value.startswith(("http://", "https://")) and (
            ".mp4" in value.lower()
            or "video" in value.lower()
            or "douyinvod" in value.lower()
            or "bytecdn" in value.lower()
        ):
            return value
    raise RuntimeError("API parsed the post, but no downloadable video URL was found.")


def _video_id_from_url(url: str) -> str:
    match = re.search(r"/video/(\d+)", url)
    if match:
        return match.group(1)
    match = re.search(r"(\d{12,})", url)
    return match.group(1) if match else "unknown"


def _request_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/",
        }
    )
    return session


def _parse_with_api(session: requests.Session, base: str, source_url: str, timeout: float) -> dict:
    endpoint = urljoin(base.rstrip("/") + "/", "hybrid/video_data")
    response = session.get(
        endpoint,
        params={"url": source_url, "minimal": "false"},
        timeout=(8, timeout),
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and int(payload.get("code") or 0) == 200:
        data = payload.get("data")
        if isinstance(data, dict):
            return data
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or str(detail)
    else:
        message = str(payload)[:500]
    raise RuntimeError(f"API returned an error: {message}")


def _download_video(session: requests.Session, video_url: str, output_path: Path, timeout: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(video_url, stream=True, timeout=(8, timeout)) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if content_type and "text/html" in content_type.lower():
            raise RuntimeError(f"Video URL returned HTML instead of media: {content_type}")
        temp_path = output_path.with_suffix(output_path.suffix + ".part")
        with temp_path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
        if temp_path.stat().st_size <= 0:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError("Downloaded file is empty.")
        temp_path.replace(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Douyin videos via Douyin_TikTok_Download_API-compatible API.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    session = _request_session()
    errors: list[str] = []
    for base in _api_bases():
        try:
            print(f"[douyin-api] Trying {base}", flush=True)
            data = _parse_with_api(session, base, args.url, args.timeout)
            video_url = _first_video_url(data)
            video_id = str(data.get("video_id") or data.get("aweme_id") or _video_id_from_url(args.url))
            title = (
                data.get("desc")
                or data.get("title")
                or data.get("description")
                or f"douyin_{video_id}"
            )
            output_path = output_dir / f"{_safe_filename(str(title), f'douyin_{video_id}')} [{video_id}].mp4"
            print(f"[douyin-api] Downloading video: {output_path.name}", flush=True)
            _download_video(session, video_url, output_path, args.timeout)
            print(f"[douyin-api] Saved: {output_path}", flush=True)
            return 0
        except Exception as exc:
            errors.append(f"{base}: {exc}")
            print(f"[douyin-api] Failed {base}: {exc}", flush=True)
    print("Douyin API fallback failed.\n" + "\n".join(errors), file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
