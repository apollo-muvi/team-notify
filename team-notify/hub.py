#!/usr/bin/env python3
"""
Hub 通知中心 — FastAPI Server，跑在 Idea3 機器上
POST /send   — 發送通知
GET  /poll/{machine_name} — 輪詢未讀通知
POST /ack/{msg_id}  — 標記已讀
"""
import sys
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn
import db

app = FastAPI(title="團隊通知中心", version="1.0.0")


# --- Request/Response 模型 ---

class SendRequest(BaseModel):
    to: str = Field(..., description="目標機器名稱", min_length=1, max_length=100)
    from_who: str = Field(..., alias="from", description="發送者", min_length=1, max_length=100)
    text: str = Field(..., description="通知內容", min_length=1, max_length=2000)

    class Config:
        populate_by_name = True


class MessageOut(BaseModel):
    id: int
    to_machine: str
    from_who: str
    text: str
    created_at: str
    acked: bool


class SendResponse(BaseModel):
    success: bool
    message: MessageOut


# --- API 路由 ---

@app.post("/send", response_model=SendResponse)
def send_notification(req: SendRequest):
    """發送通知給指定機器"""
    try:
        record = db.send_notification(
            to_machine=req.to,
            from_who=req.from_who,
            text=req.text,
        )
        return SendResponse(
            success=True,
            message=MessageOut(**record),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"儲存失敗: {str(e)}")


@app.get("/poll/{machine_name}", response_model=list[MessageOut])
def poll_messages(machine_name: str):
    """輪詢指定機器的未讀通知"""
    if not machine_name.strip():
        raise HTTPException(status_code=400, detail="機器名稱不得為空")
    try:
        records = db.poll_messages(machine_name.strip())
        return [MessageOut(**r) for r in records]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查詢失敗: {str(e)}")


@app.post("/ack/{msg_id}")
def ack_message(msg_id: int):
    """標記通知為已讀"""
    if msg_id <= 0:
        raise HTTPException(status_code=400, detail="無效的訊息 ID")
    try:
        ok = db.ack_message(msg_id)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail=f"訊息 {msg_id} 不存在或已經已讀",
            )
        return {"success": True, "msg": f"訊息 {msg_id} 已標記為已讀"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"標記失敗: {str(e)}")


@app.get("/health")
def health():
    """健康檢查"""
    return {"status": "ok", "server": "團隊通知中心"}


# --- 啟動 ---

if __name__ == "__main__":
    print("📢 團隊通知中心啟動中...")
    print(f"   DB 位置: {db.DB_PATH}")
    print(f"   監聽埠: 8765")
    print(f"   API 文件: http://localhost:8765/docs")
    sys.stdout.flush()
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
