import json
import sys
import io
import os
from dotenv import load_dotenv

# Tự động nạp biến môi trường (.env) cho LangSmith
load_dotenv()

# Đảm bảo stdout / stderr hỗ trợ đầy đủ UTF-8 trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import real_estate_agent
from qdrant_service import qdrant_service
from legal_service import legal_service
from document_converter import DocumentConverter

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
    config = {
        "configurable": {"thread_id": req.thread_id},
        "metadata": {
            "thread_id": req.thread_id,
            "session_type": "user_chat",
        },
        "tags": ["da-nang-real-estate", req.thread_id],
        "run_name": f"ChatStream-{req.thread_id}"
    }
    inputs = {"messages": [HumanMessage(content=req.message)]}

    async def event_generator():
        try:
            # 1. Chạy Graph
            final_state = real_estate_agent.invoke(inputs, config=config)
            
            # Gửi danh sách BĐS tìm thấy (nếu có) trước để ReactJS render Cards
            properties = final_state.get("found_properties", [])
            if properties:
                yield f"data: {json.dumps({'type': 'properties', 'data': properties})}\n\n"

            # Gửi danh sách căn cứ trích dẫn pháp lý (nếu có) để ReactJS render badges / drawer
            citations = final_state.get("citations", [])
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"

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

# ==================== PHÂN HỆ QUẢN TRỊ TÀI LIỆU PHÁP LÝ ====================

@app.post("/api/legal/upload")
async def upload_legal_document(file: UploadFile = File(...)):
    """Upload tài liệu (.pdf, .docx, .md) -> tự động convert sang Markdown và lưu bản thảo"""
    try:
        file_bytes = await file.read()
        md_content = DocumentConverter.convert_to_markdown(file_bytes, file.filename)
        doc_meta = legal_service.save_document(file.filename, md_content)
        return {"success": True, "data": doc_meta}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file: {str(e)}")

@app.get("/api/legal/documents")
def get_legal_documents():
    """Lấy danh sách siêu dữ liệu các tài liệu pháp lý"""
    return {"success": True, "data": legal_service.list_documents()}

@app.get("/api/legal/documents/{doc_id}/preview")
def get_legal_document_preview(doc_id: str):
    """Xem trước toàn văn nội dung Markdown của tài liệu"""
    try:
        content = legal_service.get_document_preview(doc_id)
        return {"success": True, "data": {"id": doc_id, "content": content}}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/legal/documents/{doc_id}/index")
def index_legal_document(doc_id: str):
    """Cắt chunk theo cấu trúc Điều/Khoản và nạp vector vào Qdrant"""
    try:
        chunks_count = legal_service.index_document(doc_id)
        return {
            "success": True,
            "chunks_count": chunks_count,
            "message": f"Đã nạp thành công {chunks_count} đoạn luật vào Qdrant"
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/legal/documents/{doc_id}")
def delete_legal_document(doc_id: str):
    """Xóa tài liệu và toàn bộ vector liên quan"""
    try:
        success = legal_service.delete_document(doc_id)
        return {"success": success, "message": "Đã xóa tài liệu và vector liên quan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Tắt reload để tránh tạo 2 process tranh chấp file Qdrant local
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
