#!/usr/bin/env python3
"""
Fetch real stickers from CapCut Mate cloud API and save to config/sticker.json.
Usage: python tools/fetch_stickers.py
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
import sys
from pathlib import Path

CAPCUT_MATE_API = "https://capcut-mate.jcaigc.cn"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "config" / "sticker.json"

# Keywords to search - cover popular categories
KEYWORDS = [
    # Core emojis & emotions
    "爱心", "星星", "大哭", "大笑", "点赞", "OK", "比心", "鼓掌", "害羞",
    "无语", "震惊", "生气", "开心", "难过", "得意", "调皮", "委屈",
    # Popular categories
    "箭头", "标签", "进度条", "序号", "对话框", "气泡", "重点", "高亮",
    "皇冠", "钻石", "宝石", "烟花", "爱心雨", "花瓣", "蝴蝶", "天使",
    "恶魔", "幽灵", "南瓜", "圣诞", "新年", "生日", "婚礼", "毕业",
    "粽子", "月饼", "灯笼", "红包", "福字", "春联", "樱花", "枫叶",
    "彩虹", "白云", "太阳", "月亮", "乌云", "下雨", "下雪", "闪电",
    "热恋", "心动", "告白", "情侣", "单身", "闺蜜", "兄弟", "家人",
    "美食", "蛋糕", "冰淇淋", "咖啡", "奶茶", "披萨", "汉堡", "寿司",
    "猫咪", "狗狗", "小熊", "兔子", "熊猫", "狐狸", "小鸟", "小鱼",
    "气球", "礼物", "奖杯", "奖牌", "奖状", "证书", "金牌", "银牌",
    "vip", "hot", "new", "free", "sale", "推荐", "热门", "必买",
    "爱心", "星星", "大哭", "大笑", "点赞", "OK", "圣诞", "生日",
    "心心", "箭头", "emoji", "动物", "植物", "食物",
    "搞笑", "可爱", "酷", "呆萌", "帅气", "甜美", "霸气", "小清新",
    "国潮", "复古", "ins", "简约", "梦幻", "唯美", "治愈", "暗黑",
    "手绘", "卡通", "3D", "像素", "水彩", "水墨", "涂鸦",
]


def repair_mojibake(text: str) -> str:
    """Try to fix mojibake in Chinese text."""
    if text.isascii():
        return text
    for src_enc, dst_enc in [
        ("gbk", "utf-8"),
        ("gb2312", "utf-8"),
        ("gb18030", "utf-8"),
    ]:
        try:
            repaired = text.encode(src_enc).decode(dst_enc)
            if repaired.isascii():
                continue
            # Check if repaired looks more reasonable (has Chinese chars)
            if any("一" <= c <= "鿿" for c in repaired):
                return repaired
        except Exception:
            pass
    return text


def fetch_stickers(keyword: str) -> list[dict]:
    """Fetch stickers for a keyword from CapCut Mate cloud API."""
    url = f"{CAPCUT_MATE_API}/openapi/capcut-mate/v1/search_sticker"
    payload = json.dumps({"keyword": keyword}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        req = urllib.request.Request(
            url=url, data=payload, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        code = result.get("code", 0)
        if code != 0:
            print(f"  API error: {result.get('message', 'unknown')}")
            return []

        raw_data = result.get("data", [])
        stickers = []
        for item in raw_data:
            sticker_info = item.get("sticker", {})
            sticker_id = str(item.get("sticker_id", ""))
            title = repair_mojibake(str(item.get("title", "")))
            large_image = sticker_info.get("large_image", {})
            image_url = str(large_image.get("image_url", ""))
            package = sticker_info.get("sticker_package", {})
            stickers.append({
                "sticker_id": sticker_id,
                "title": title,
                "image_url": image_url,
                "width": package.get("width_per_frame", 0),
                "height": package.get("height_per_frame", 0),
                "size": package.get("size", 0),
                "sticker_type": sticker_info.get("sticker_type", 1),
            })
        return stickers

    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:100]}")
        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_stickers: list[dict] = []
    seen: set[str] = set()

    total = len(KEYWORDS)
    for i, kw in enumerate(KEYWORDS, 1):
        print(f"[{i}/{total}] Searching '{kw}'...", end=" ", flush=True)
        stickers = fetch_stickers(kw)
        new_count = 0
        for s in stickers:
            sid = s["sticker_id"]
            if sid and sid not in seen:
                seen.add(sid)
                all_stickers.append(s)
                new_count += 1
        print(f"got {len(stickers)}, {new_count} new, total: {len(seen)}")

    # Sort by sticker_id for consistent output
    all_stickers.sort(key=lambda x: x["sticker_id"])

    OUTPUT_FILE.write_text(
        json.dumps(all_stickers, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved {len(all_stickers)} stickers to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
