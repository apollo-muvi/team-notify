# Team Notify — 跨機器團隊通知系統

> 專案位置：`~/AI-jobflow/team-notify/`
> GitHub：`apollo-muvi/AI-jobflow`

---

## 1. 概述

跨機器非同步通知系統，解決 Hermes Agent 之間（idea3 ↔ Pi4）無法直接溝通 Telegram 群組訊息（bot 看不到其他 bot 的訊息）的限制。

### 使用場景

- **CEO（idea3local）** → 發送任務給 **小p（Pi4 Hermes-pi4）**
- **小p** → 回覆執行結果或狀態給 **CEO**
- 雙向非同步，不需 Telegram 群組做為 bot-to-bot 溝通媒介

---

## 2. 系統架構

```
┌─────────────────┐       POST /send        ┌──────────────────┐
│   idea3 (CEO)   │ ──────────────────────→  │  Hub (port 8765) │
│  ┌───────────┐  │                          │  ┌────────────┐  │
│  │ client.py │  │  ←──── GET /poll/CEO ──  │  │  SQLite DB │  │
│  └───────────┘  │                          │  └────────────┘  │
└─────────────────┘                          └────────┬─────────┘
                                                       │
                              POST /send               │  GET /poll/小p
                                                       │
                                                   ┌───▼─────────┐
                                                   │  Pi4 (小p)    │
                                                   │  ┌─────────┐ │
                                                   │  │client.py│ │
                                                   │  └─────────┘ │
                                                   └─────────────┘
```

### 元件

| 元件 | 位置 | 語言 | 說明 |
|------|------|------|------|
| **Hub** | idea3:8765 | Python + FastAPI + uvicorn | 通知中心伺服器，儲存與分發訊息 |
| **Client** | 每台機器 | Python | 輪詢 Hub，收發訊息，自動 Ack |
| **DB** | Hub 同目錄 | SQLite | `messages` 表格儲存所有通知 |

---

## 3. Hub API

### `POST /send`

發送通知給指定機器。

**Request：**
```json
{
  "to": "小p",
  "from": "CEO",
  "text": "請執行 deploy"
}
```

**Response：**
```json
{
  "success": true,
  "message": {
    "id": 1,
    "to_machine": "小p",
    "from_who": "CEO",
    "text": "請執行 deploy",
    "created_at": "2026-06-23T22:00:00.000000+00:00",
    "acked": false
  }
}
```

### `GET /poll/{machine_name}`

輪詢該機器所有未讀通知。回傳陣列，每筆包含 `id, to_machine, from_who, text, created_at, acked`。

### `POST /ack/{msg_id}`

標記訊息為已讀。回傳 `{"success": true}`。

### `GET /health`

健康檢查。回傳 `{"status": "ok", "server": "團隊通知中心"}`。

---

## 4. Client 行為

### 啟動流程

1. 載入環境變數 `MACHINE_NAME`（預設 `小p`）和 `HUB_URL`（預設 `http://192.168.20.154:8765`）
2. 發送 🟢 `{機器名} 上線` 給 CEO
3. 進入輪詢迴圈

### 輪詢行為

- 預設間隔：**30 秒**
- 收到訊息時：
  1. 日誌輸出：`[收到] 來自 {from}: {text}`
  2. 自動 **Ack**（標記已讀）
  3. 若來自 CEO → 自動回覆確認 ✅
- 離線處理：30s → 5min → 10min → 30min → 60min → 停止

### 發送訊息

可直接呼叫 API 發送：

```bash
curl -X POST http://localhost:8765/send \
  -H "Content-Type: application/json" \
  -d '{"to": "CEO", "from": "小p", "text": "deploy 完成"}'
```

Client 本身也內建 `send()` 函數供自動回覆使用。

---

## 5. 部署方式

### Hub（idea3 上）

```bash
cd ~/AI-jobflow/team-notify
python3 hub.py &
```

自動監聽 `0.0.0.0:8765`。

### Client（每台機器）

```bash
cd ~/AI-jobflow/team-notify
MACHINE_NAME="小p" nohup python3 client.py > ~/team-notify-client.log 2>&1 &
```

---

## 6. 資料庫結構

```sql
CREATE TABLE messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    to_machine  TEXT    NOT NULL,
    from_who    TEXT    NOT NULL,
    text        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    acked       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_messages_unacked
ON messages(to_machine, acked, id);
```

---

## 7. 測試結果

### 測試 1：CEO→Hub→小p 單向

```
POST /send {to: "小p", from: "CEO", text: "測試訊息"}
→ DB 寫入 id=1, to_machine=小p, acked=0
→ 小p client 輪詢到 → Ack → acked=1 ✅
```

### 測試 2：小p→Hub→CEO 雙向

```
小p client 啟動 → send("CEO", "🟢 小p 上線")
→ DB 寫入 id=2, to_machine=CEO, acked=0
→ CEO 輪詢 /poll/CEO 取得訊息 ✅
```

### 測試 3：完整迴路

```
CEO→小p：POST /send → DB → 小p 輪詢到 → Ack → 自動回覆 CEO ✅
小p→CEO：自動發「✅ 已收到」回 CEO ✅
```

---

## 8. 未來擴充

- [ ] **附件傳輸**：支援檔案/圖片/程式碼區塊
- [ ] **Systemd service**：client.py 註冊為 systemd 服務自動啟動
- [ ] **端到端加密**：敏感訊息加密傳輸
- [ ] **Hermes 整合**：client 收到訊息時自動注入 Hermes 對話
- [ ] **Webhook 模式**：Hub 主動推送，取代 polling
