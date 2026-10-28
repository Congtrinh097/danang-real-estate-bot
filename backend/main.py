import json
import sys
import io

# Đảm bảo stdout / stderr hỗ trợ đầy đủ UTF-8 trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import real_estate_agent
from qdrant_service import qdrant_service

app = FastAPI(title="Da Nang Real Estate AI Agent API")

# Cho phép ReactJS gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_user_session"

class LeadRequest(BaseModel):
    name: str
    phone: str
    property_id: str
    note: str = ""

@app.on_event("startup")
async def startup_event():
    # Tự động nạp dữ liệu mẫu vào Qdrant khi backend khởi động
    try:
        qdrant_service.ingest_dataset()
    except Exception as e:
        print(f"[WARN] Ingest Qdrant lỗi hoặc đã nạp: {e}")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "city": "Đà Nẵng"}

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming endpoint gửi phản hồi từng token và danh sách BĐS cho ReactJS"""
    config = {"configurable": {"thread_id": req.thread_id}}
    inputs = {"messages": [HumanMessage(content=req.message)]}

    async def event_generator():
        try:
            # 1. Chạy Graph
            final_state = real_estate_agent.invoke(inputs, config=config)
            
            # Gửi danh sách BĐS tìm thấy (nếu có) trước để ReactJS render Cards
            properties = final_state.get("found_properties", [])
            if properties:
                yield f"data: {json.dumps({'type': 'properties', 'data': properties})}\n\n"

            # Gửi phản hồi văn bản của Bot
            messages = final_state.get("messages", [])
            if messages:
                bot_text = messages[-1].content
                # Stream giả lập từng cụm từ để frontend có hiệu ứng gõ mượt mà
                chunk_size = 15
                for i in range(0, len(bot_text), chunk_size):
                    chunk = bot_text[i:i+chunk_size]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/leads")
def submit_lead(lead: LeadRequest):
    """Endpoint thu thập Lead đặt lịch xem nhà"""
    print(f"🔥 [NEW LEAD ĐÀ NẴNG] Khách: {lead.name} | SĐT: {lead.phone} | BĐS: {lead.property_id}")
    return {
        "success": True,
        "message": "Đã ghi nhận thông tin đặt lịch xem nhà thành công!"
    }

if __name__ == "__main__":
    import uvicorn
    # Tắt reload để tránh tạo 2 process tranh chấp file Qdrant local
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
