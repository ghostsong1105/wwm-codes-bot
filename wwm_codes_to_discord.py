"""
codes.yar.gg 새 코드 -> 디스코드 웹후크 자동 전송 (API 버전)

설치:
    pip install requests

환경변수:
    DISCORD_WEBHOOK_URL  (필수, --dry-run 제외) 디스코드 웹후크 주소

사용:
    python wwm_codes_to_discord.py --dry-run   # 디스코드로 안 보내고 결과만 확인
    python wwm_codes_to_discord.py             # 실제 실행 (새 코드만 전송)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_URL = "https://codes-backend.wwmcodes.workers.dev/v1/codes"
SITE = "https://codes.yar.gg/"
STATE_FILE = Path("seen_codes.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


KST = timezone(timedelta(hours=9))


WEEKDAYS = "월화수목금토일"


def fmt_date(iso: str) -> str:
    """'2026-10-19T06:00:00Z' -> 'KST : 10/19(월) 오후 3시' (한국 시간 기준)"""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)
        ampm = "오전" if dt.hour < 12 else "오후"
        hour12 = dt.hour % 12 or 12
        return f"KST : {dt.month}/{dt.day}({WEEKDAYS[dt.weekday()]}) {ampm} {hour12}시"
    except Exception:
        return ""


def fetch_active() -> dict:
    """활성 코드를 {코드: 등록시각} 형태로 반환 (오래된 것부터)."""
    r = requests.get(API_URL, timeout=20, headers={"User-Agent": "wwm-codes-discord-bot"})
    r.raise_for_status()
    items = r.json().get("active", [])
    items.sort(key=lambda x: x.get("addedAt", ""))
    return {i["code"].strip(): i.get("addedAt", "") for i in items if i.get("code")}


def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return None  # 파일 자체가 없음 = 첫 실행


def save_seen(codes: set) -> None:
    STATE_FILE.write_text(
        json.dumps(sorted(codes), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def send_discord(code: str, added_at: str = "") -> None:
    date = fmt_date(added_at)
    title = f"새 WWM 코드 ( {date} 추가 )" if date else "새 WWM 코드"
    payload = {
        "content": f"🎁 **{title}**\n```\n{code}\n```{SITE}",
        "flags": 4,  # SUPPRESS_EMBEDS: 링크는 보이되 미리보기 카드는 숨김
    }
    for _ in range(3):
        r = requests.post(WEBHOOK, json=payload, timeout=20)
        if r.status_code == 429:  # 속도 제한이면 잠깐 기다렸다 재시도
            time.sleep(float(r.json().get("retry_after", 2)))
            continue
        r.raise_for_status()
        return
    raise RuntimeError("디스코드 전송 실패 (속도 제한)")


def main():
    dry = "--dry-run" in sys.argv
    active = fetch_active()
    print(f"활성 코드 {len(active)}개")

    seen = load_seen()
    if seen is None:
        print("첫 실행: 기존 코드는 전송하지 않고 저장만 합니다.")
        if not dry:
            save_seen(set(active))
        return

    new = [c for c in active if c not in seen]
    print(f"새 코드 {len(new)}개: {new}")
    if dry or not new:
        return

    for code in new:
        send_discord(code, active[code])
        # 전송에 성공한 코드만 기록 (실패 시 다음 실행에서 재시도)
        seen.add(code)
        save_seen(seen)
        time.sleep(1)  # 웹후크 속도 제한 방지


if __name__ == "__main__":
    if not WEBHOOK and "--dry-run" not in sys.argv:
        sys.exit("DISCORD_WEBHOOK_URL 환경변수를 설정하세요.")
    main()
