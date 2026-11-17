import asyncio
import json
import sys
import io
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from dotenv import load_dotenv

# Load per-user overrides first; values already exported in the shell win.
backend_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=backend_dir / ".env.local", override=False)
load_dotenv(dotenv_path=backend_dir / ".env", override=False)

# Đảm bảo stdout / stderr hỗ trợ đầy đủ UTF-8 trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from agent import real_estate_agent
from qdrant_service import qdrant_service
from legal_service import legal_service
from document_converter import DocumentConverter
from config import settings
from pii_utils import mask_phone
from tenant_agent import process_tenant_intake
from tenant_models import ApprovalRequest, EmailIntake, TenantIntake
from tenant_store import tenant_ticket_store
from tenant_knowledge import tenant_knowledge_service
from sla_sensor import list_sla_alerts, run_sla_sensor


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await asyncio.to_thread(qdrant_service.ingest_dataset)
    except Exception as exc:
        print(f"[WARN] Ingest Qdrant lỗi hoặc đã nạp: {exc}")
    sensor_task = None
    if settings.SLA_MONITOR_ENABLED:
        sensor_task = asyncio.create_task(
            run_sla_sensor(settings.SLA_MONITOR_INTERVAL_SECONDS),
            name="tenant-sla-sensor",
        )
    yield
    if sensor_task:
        sensor_task.cancel()
        with suppress(asyncio.CancelledError):
            await sensor_task


app = FastAPI(title="Da Nang Real Estate AI Agent API", lifespan=lifespan)

# Cho phép ReactJS gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()],
    allow_credentials=False,
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


def require_admin(x_admin_key: str | None = Header(default=None)):
    """Protect staff APIs when ADMIN_API_KEY is configured; local dev remains frictionless."""
    if settings.ADMIN_API_KEY and x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Admin key không hợp lệ")

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
            # Avoid blocking FastAPI's event loop while the synchronous graph/tools run.
            final_state = await asyncio.to_thread(real_estate_agent.invoke, inputs, config)
            
            # Gửi danh sách BĐS tìm thấy (nếu có) trước để ReactJS render Cards
            properties = final_state.get("found_properties", [])
            if properties:
                yield f"data: {json.dumps({'type': 'properties', 'data': properties})}\n\n"

            # Gửi danh sách căn cứ trích dẫn pháp lý (chỉ gửi khi intent lượt này là legal_consultation và có citations)
            intent = final_state.get("intent")
            citations = final_state.get("citations", []) if intent == "legal_consultation" else []
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"

            # Gửi phản hồi văn bản của Bot
            messages = final_state.get("messages", [])
            if messages:
                bot_text = messages[-1].content
                # Stream giả lập từng cụm từ để frontend có hiệu ứng gõ mượt mà
                chunk_size = 6
                for i in range(0, len(bot_text), chunk_size):
                    chunk = bot_text[i:i+chunk_size]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.015)

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/leads")
def submit_lead(lead: LeadRequest):
    """Endpoint thu thập Lead đặt lịch xem nhà"""
    print(f"[NEW LEAD] phone={mask_phone(lead.phone)} property={lead.property_id}")
    return {
        "success": True,
        "message": "Đã ghi nhận thông tin đặt lịch xem nhà thành công!"
    }


# ==================== TENANT SUPPORT & SLA ASSURANCE ====================

@app.post("/api/tenant/intake")
async def tenant_intake(intake: TenantIntake):
    """Normalize a web/chat intake and run the supervised tenant ticket lifecycle."""
    result = await asyncio.to_thread(process_tenant_intake, intake)
    return {"success": True, "data": result.model_dump(mode="json")}


@app.post("/api/tenant/email")
async def tenant_email_intake(email: EmailIntake):
    """Normalize an email payload into the same tenant intake contract."""
    result = await asyncio.to_thread(process_tenant_intake, email.to_tenant_intake())
    return {"success": True, "data": result.model_dump(mode="json")}


@app.get("/api/tenant/tickets", dependencies=[Depends(require_admin)])
def list_tenant_tickets(limit: int = 100):
    tickets = tenant_ticket_store.list(limit=min(max(limit, 1), 500))
    return {"success": True, "data": [ticket.model_dump(mode="json") for ticket in tickets]}


@app.get("/api/tenant/tickets/{ticket_id}", dependencies=[Depends(require_admin)])
def get_tenant_ticket(ticket_id: str):
    ticket = tenant_ticket_store.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket không tồn tại")
    return {"success": True, "data": ticket.model_dump(mode="json")}


@app.post("/api/tenant/tickets/{ticket_id}/human-action", dependencies=[Depends(require_admin)])
def human_action(ticket_id: str, request: ApprovalRequest):
    ticket = tenant_ticket_store.apply_human_action(ticket_id, request)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket không tồn tại")
    return {"success": True, "data": ticket.model_dump(mode="json")}


@app.get("/api/tenant/sla/metrics", dependencies=[Depends(require_admin)])
def tenant_sla_metrics():
    return {"success": True, "data": tenant_ticket_store.sla_metrics()}


@app.get("/api/tenant/sla/alerts", dependencies=[Depends(require_admin)])
def tenant_sla_alerts():
    return {"success": True, "data": list_sla_alerts()}


@app.get("/api/tenant/rag/evaluate", dependencies=[Depends(require_admin)])
@app.post("/api/tenant/rag/evaluate", dependencies=[Depends(require_admin)])
async def evaluate_tenant_rag():
    from tenant_rag_evaluator import TenantRAGEvaluator

    report = await asyncio.to_thread(TenantRAGEvaluator().evaluate)
    if report["status"] == "error":
        raise HTTPException(status_code=503, detail=report)
    return {"success": True, "report": report}


@app.post("/api/tenant/documents/index", dependencies=[Depends(require_admin)])
async def index_tenant_document(file: UploadFile = File(...)):
    """Deep-document intake for lease/payment policies into the tenant knowledge index."""
    try:
        file_bytes = await file.read()
        markdown = await asyncio.to_thread(DocumentConverter.convert_to_markdown, file_bytes, file.filename)
        chunks = await asyncio.to_thread(tenant_knowledge_service.index_markdown, file.filename, markdown)
        if chunks == 0:
            raise HTTPException(status_code=400, detail="Tài liệu không có nội dung đủ dài để index")
        return {"success": True, "data": {"filename": file.filename, "chunks_count": chunks}}
    except HTTPException:
        raise
    except (TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

# ==================== PHÂN HỆ QUẢN TRỊ TÀI LIỆU PHÁP LÝ ====================

@app.post("/api/legal/upload", dependencies=[Depends(require_admin)])
async def upload_legal_document(file: UploadFile = File(...)):
    """Upload tài liệu (.pdf, .docx, .md) -> tự động convert sang Markdown và lưu bản thảo (chạy trong worker thread tránh block event loop)"""
    try:
        file_bytes = await file.read()
        md_content = await asyncio.to_thread(
            DocumentConverter.convert_to_markdown, file_bytes, file.filename
        )
        doc_meta = await asyncio.to_thread(
            legal_service.save_document, file.filename, md_content
        )
        return {"success": True, "data": doc_meta}
    except TimeoutError as te:
        raise HTTPException(status_code=408, detail=str(te))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file: {str(e)}")

@app.get("/api/legal/documents", dependencies=[Depends(require_admin)])
def get_legal_documents():
    """Lấy danh sách siêu dữ liệu các tài liệu pháp lý"""
    return {"success": True, "data": legal_service.list_documents()}

@app.get("/api/legal/documents/{doc_id}/preview", dependencies=[Depends(require_admin)])
def get_legal_document_preview(doc_id: str):
    """Xem trước toàn văn nội dung Markdown của tài liệu"""
    try:
        content = legal_service.get_document_preview(doc_id)
        return {"success": True, "data": {"id": doc_id, "content": content}}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/legal/documents/{doc_id}/index", dependencies=[Depends(require_admin)])
async def index_legal_document(doc_id: str):
    """Cắt chunk theo cấu trúc Điều/Khoản và nạp vector vào Qdrant (chạy trong worker thread)"""
    try:
        chunks_count = await asyncio.to_thread(legal_service.index_document, doc_id)
        return {
            "success": True,
            "chunks_count": chunks_count,
            "message": f"Đã nạp thành công {chunks_count} đoạn luật vào Qdrant"
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/legal/documents/{doc_id}", dependencies=[Depends(require_admin)])
def delete_legal_document(doc_id: str):
    """Xóa tài liệu và toàn bộ vector liên quan"""
    try:
        success = legal_service.delete_document(doc_id)
        return {"success": success, "message": "Đã xóa tài liệu và vector liên quan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PHÂN HỆ ĐÁNH GIÁ RAGAS ====================

@app.get("/api/rag/evaluate", dependencies=[Depends(require_admin)])
@app.post("/api/rag/evaluate", dependencies=[Depends(require_admin)])
async def evaluate_rag():
    """Endpoint kích hoạt Ragas benchmark cho các node RAG (chạy trong worker thread tránh block event loop)"""
    try:
        from rag_evaluator import RAGEvaluator
        evaluator = RAGEvaluator()
        report = await asyncio.to_thread(evaluator.evaluate_legal_rag)
        return {"success": True, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Tắt reload để tránh tạo 2 process tranh chấp file Qdrant local
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
