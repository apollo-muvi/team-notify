#!/usr/bin/env python3
"""
Team Notify Client — 雙向通知客戶端
跑在每台機器上，負責輪詢 hub 訊息 + 發送訊息給其他機器

用法：
  MACHINE_NAME="小p" python3 client.py [--hub http://<host>:8765]

當收到訊息時自動回覆確認，形成完整雙向迴路。
"""
import subprocess, json, time, os, sys, argparse
from urllib.parse import quote

# ── 預設值 ──────────────────────────────────────────────
DEFAULT_HUB = os.environ.get("HUB_URL", "http://192.168.20.154:8765")
DEFAULT_MACHINE = os.environ.get("MACHINE_NAME", "unknown")

# 離線降頻策略（秒）
INTERVALS = [30, 300, 600, 1800, 3600]
MAX_FAIL = len(INTERVALS)

fail_count = 0


def log(msg: str):
    """帶時間戳的日誌，flush 確保即時寫入檔案"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    sys.stdout.flush()


def api_get(path: str) -> dict | list | None:
    """GET 請求 hub API"""
    try:
        r = subprocess.run(
            ["curl", "-s", f"{HUB}{path}"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        return json.loads(r.stdout)
    except Exception as e:
        log(f"[錯誤] GET {path} 失敗: {e}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    """POST JSON 到 hub API"""
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST", f"{HUB}{path}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload, ensure_ascii=False)],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        return json.loads(r.stdout)
    except Exception as e:
        log(f"[錯誤] POST {path} 失敗: {e}")
        return None


def send(to: str, text: str) -> bool:
    """發送訊息給指定機器"""
    result = api_post("/send", {"to": to, "from": MACHINE, "text": text})
    if result and result.get("success"):
        log(f"[送出] → {to}: {text[:80]}")
        return True
    log(f"[送出失敗] → {to}: {result}")
    return False


def poll():
    """主輪詢迴圈"""
    global fail_count
    while True:
        msgs = api_get(f"/poll/{quote(MACHINE, safe='')}")
        if msgs is None:
            # 連線失敗
            fail_count += 1
            if fail_count >= MAX_FAIL:
                log(f"[停止] 機器 {MACHINE} 持續離線，停止輪詢")
                return
            interval = INTERVALS[fail_count - 1]
            log(f"[離線] 無法連線（第{fail_count}次），{interval}秒後重試")
            time.sleep(interval)
            continue

        # 連線成功 → 重置失敗計數
        fail_count = 0

        if msgs:
            for m in msgs:
                msg_id = m["id"]
                sender = m["from_who"]
                text = m["text"]
                log(f"[收到] 來自 {sender}: {text[:120]}")

                # 自動 Ack
                api_post(f"/ack/{msg_id}", {})

                # 自動回覆確認（避免無窮回覆：只回覆 CEO 的訊息）
                if sender.upper() == "CEO":
                    send("CEO", f"✅ 小p 已收到：{text[:80]}")

        time.sleep(INTERVALS[0])


def online_notify():
    """啟動時發送上線通知"""
    send("CEO", f"🟢 {MACHINE} 上線")


# ── 入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Team Notify Client")
    parser.add_argument("--hub", default=DEFAULT_HUB)
    args = parser.parse_args()

    HUB = args.hub.rstrip("/")
    MACHINE = DEFAULT_MACHINE

    log(f"🤖 Team Notify Client: {MACHINE}")
    log(f"   Hub: {HUB}")
    log(f"   輪詢間隔: {INTERVALS[0]}s")

    online_notify()
    poll()
    log(f"[結束] Client 已停止")
