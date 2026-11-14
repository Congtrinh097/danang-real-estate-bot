import asyncio
import json
import sys
import io
import os
from typing import Optional, Dict, Any, List
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
from langgraph.types import Command
from agent import real_estate_agent, property_agent
from appointment_tools import set_current_user_id
from appointment_service import appointment_service
from qdrant_service import qdrant_service
from legal_service import legal_service
from document_converter import DocumentConverter
from agentops import (
    TraceContext,
    langfuse_manager,
    AgentOpsCallbackHandler,
    cost_reporting_service,
    cost_alert_engine,
    BudgetExceededException
)

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
    user_id: Optional[str] = "default_user"

class HITLDecisionRequest(BaseModel):
    thread_id: str
    user_id: Optional[str] = "default_user"
    decision: str = "approve"  # 'approve', 'reject', 'edit'
    edited_args: Optional[Dict[str, Any]] = None
    reject_message: Optional[str] = None

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

# ==================== PHÂN HỆ BÁO CÁO AGENTOPS ====================
@app.get("/api/agentops/reports/workload")
def get_workload_report():
    """Báo cáo chi phí theo từng loại workload (chat, evaluation,...)"""
    return cost_reporting_service.get_cost_by_workload()

@app.get("/api/agentops/reports/thread")
def get_thread_report(limit: int = 20):
    """Báo cáo chi phí theo từng phiên hội thoại (thread)"""
    return cost_reporting_service.get_cost_by_thread(limit=limit)

@app.get("/api/agentops/thread/{thread_id}/budget")
def get_thread_budget(thread_id: str):
    """Lấy hạn mức và tiến độ chi tiêu của thread cụ thể để hiển thị trên UI"""
    return cost_reporting_service.get_thread_budget_status(thread_id=thread_id)

@app.get("/api/agentops/reports/model")
def get_model_report():
    """Báo cáo chi phí theo từng mô hình LLM"""
    return cost_reporting_service.get_cost_by_model()

@app.get("/api/agentops/reports/summary")
def get_cost_summary():
    """Báo cáo tổng hợp chi tiêu ngày và tỷ lệ sử dụng ngân sách"""
    return cost_reporting_service.get_daily_cost_summary()

@app.get("/api/agentops/alerts")
def get_alerts():
    """Kiểm tra và kích hoạt cảnh báo ngân sách"""
    return cost_alert_engine.evaluate_and_record_alerts()

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming endpoint gửi phản hồi từng token và danh sách BĐS cho ReactJS"""
    # Thiết lập TraceContext cho AgentOps và gắn user_id vào context
    set_current_user_id(req.user_id or "default_user")
    request_id = f"req_{int(asyncio.get_event_loop().time() * 1000)}"
    TraceContext.set_context(request_id=request_id, thread_id=req.thread_id, workload_type="chat")

    callbacks = [AgentOpsCallbackHandler(agent_name="DaNangRealEstateBot")]
    lf_cb = langfuse_manager.get_callback_handler(request_id=request_id, thread_id=req.thread_id)
    if lf_cb:
        callbacks.append(lf_cb)

    config = {
        "configurable": {"thread_id": req.thread_id},
        "callbacks": callbacks,
        "metadata": {
            "thread_id": req.thread_id,
            "request_id": request_id,
            "session_type": "user_chat",
        },
        "tags": ["da-nang-real-estate", req.thread_id],
        "run_name": f"ChatStream-{req.thread_id}"
    }
    inputs = {"messages": [HumanMessage(content=req.message)]}

    async def event_generator():
        # Kiểm tra trước hạn mức thread: nếu đã hết ngân sách thì chặn ngay từ đầu
        try:
            budget_status = cost_reporting_service.get_thread_budget_status(thread_id=req.thread_id)
            if budget_status.get("is_exceeded"):
                err_msg = (
                    f"⚠️ [Thông báo Ngân sách] Phiên hội thoại này đã đạt hạn mức chi phí "
                    f"({budget_status['spent_vnd']:,.0f}đ / {budget_status['thread_limit_vnd']:,.0f}đ). "
                    f"Vui lòng bấm 'Tạo đoạn chat mới' để tiếp tục trò chuyện."
                )
                yield f"data: {json.dumps({'type': 'budget_update', 'data': budget_status})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': err_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return
        except Exception as check_err:
            print(f"[WARN] Pre-check thread budget failed: {check_err}")

        try:
            # Thông báo trạng thái bắt đầu
            yield f"data: {json.dumps({'type': 'status', 'stage': 'routing', 'message': 'Đang phân tích yêu cầu của bạn...'})}\n\n"
            await asyncio.sleep(0.01)

            final_state = {}
            intent_identified = None

            # Stream theo updates của từng node trong LangGraph
            async for step_update in real_estate_agent.astream(inputs, config=config, stream_mode="updates"):
                for node_name, node_output in step_update.items():
                    if isinstance(node_output, dict):
                        final_state.update(node_output)

                    # Khi node route_intent hoàn thành, phát hiện ý định và cập nhật trạng thái chi tiết cho người dùng
                    if node_name == "route_intent":
                        intent_identified = node_output.get("intent") if isinstance(node_output, dict) else None
                        status_map = {
                            "search_property": "Đang tìm kiếm bất động sản phù hợp tại Đà Nẵng...",
                            "legal_consultation": "Đang tra cứu cơ sở dữ liệu Luật Đất Đai & Nhà Ở...",
                            "mortgage_calculation": "Đang kết nối công cụ tính toán lãi suất & gói vay...",
                            "contract_audit": "Đang rà soát điều khoản hợp đồng & kiểm tra bẫy pháp lý...",
                            "general_chat": "Đang soạn nội dung phản hồi...",
                            "out_of_scope": "Đang kiểm tra phạm vi hỗ trợ...",
                            "rule_violation": "Đang kiểm tra tiêu chuẩn an toàn..."
                        }
                        msg = status_map.get(intent_identified, "Đang xử lý thông tin...")
                        yield f"data: {json.dumps({'type': 'status', 'stage': intent_identified or 'processing', 'message': msg})}\n\n"
                        await asyncio.sleep(0.01)

                    elif node_name == "property_agent":
                        yield f"data: {json.dumps({'type': 'status', 'stage': 'property_completed', 'message': 'Đã hoàn tất tìm kiếm BĐS'})}\n\n"
                    elif node_name == "legal_advisory":
                        yield f"data: {json.dumps({'type': 'status', 'stage': 'legal_completed', 'message': 'Đã tổng hợp căn cứ pháp lý'})}\n\n"
                    elif node_name == "mortgage_calc":
                        yield f"data: {json.dumps({'type': 'status', 'stage': 'mortgage_completed', 'message': 'Đã hoàn tất tính toán phương án vay'})}\n\n"
                    elif node_name == "contract_audit":
                        yield f"data: {json.dumps({'type': 'status', 'stage': 'contract_completed', 'message': 'Đã hoàn thành thẩm định hợp đồng'})}\n\n"
            
            # Gửi danh sách BĐS tìm thấy (nếu có) trước để ReactJS render Cards
            properties = final_state.get("found_properties", [])
            if properties:
                yield f"data: {json.dumps({'type': 'properties', 'data': properties})}\n\n"

            # Gửi danh sách căn cứ trích dẫn pháp lý (chỉ gửi khi intent lượt này là legal_consultation và có citations)
            intent = final_state.get("intent") or intent_identified
            citations = final_state.get("citations", []) if intent == "legal_consultation" else []
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"

            # Gửi sự kiện HITL interrupt nếu có yêu cầu duyệt đặt lịch hẹn
            hitl_interrupt = final_state.get("hitl_interrupt")
            if hitl_interrupt:
                yield f"data: {json.dumps({'type': 'hitl_approval_request', 'data': hitl_interrupt})}\n\n"

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

            # Gửi cập nhật ngân sách thread sau khi kết thúc turn
            try:
                budget_status = cost_reporting_service.get_thread_budget_status(thread_id=req.thread_id)
                yield f"data: {json.dumps({'type': 'budget_update', 'data': budget_status})}\n\n"
            except Exception as b_err:
                print(f"[WARN] Failed to send budget_update event: {b_err}")

            yield "data: [DONE]\n\n"
        except BudgetExceededException as be:
            err_msg = (
                f"⚠️ [Thông báo Ngân sách] Phiên hội thoại này đã đạt hạn mức chi phí. "
                f"Vui lòng bấm 'Tạo đoạn chat mới' để tiếp tục trò chuyện."
            )
            try:
                budget_status = cost_reporting_service.get_thread_budget_status(thread_id=req.thread_id)
                yield f"data: {json.dumps({'type': 'budget_update', 'data': budget_status})}\n\n"
            except Exception:
                pass
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/chat/hitl-decision")
async def hitl_decision_stream(req: HITLDecisionRequest):
    """Tiếp nhận quyết định của người dùng (Approve / Reject / Edit) sau khi bị ngắt bởi HumanInTheLoopMiddleware và stream kết quả hoàn thành"""
    set_current_user_id(req.user_id or "default_user")
    request_id = f"req_hitl_{int(asyncio.get_event_loop().time() * 1000)}"
    TraceContext.set_context(request_id=request_id, thread_id=req.thread_id, workload_type="chat")

    sub_config = {"configurable": {"thread_id": f"prop_sub_{req.thread_id}"}}

    # Xây dựng decision payload theo cấu trúc của HumanInTheLoopMiddleware
    decision_payload = {"type": req.decision}
    if req.decision == "reject":
        decision_payload["message"] = req.reject_message or "Khách hàng đã hủy yêu cầu đặt lịch xem nhà này."
    elif req.decision == "edit" and req.edited_args:
        decision_payload["edited_action"] = {
            "name": "book_viewing_appointment",
            "args": req.edited_args
        }

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'status', 'stage': 'hitl_resuming', 'message': 'Đang ghi nhận quyết định và hoàn tất thủ tục...'})}\n\n"
            await asyncio.sleep(0.01)

            # Resume property_agent với Command
            cmd = Command(resume={"decisions": [decision_payload]})
            agent_result = await asyncio.to_thread(property_agent.invoke, cmd, config=sub_config)
            agent_messages = agent_result.get("messages", [])

            reply_text = ""
            if agent_messages:
                reply_text = agent_messages[-1].content
            else:
                reply_text = "Đã xử lý xong phản hồi của bạn."

            chunk_size = 6
            for i in range(0, len(reply_text), chunk_size):
                chunk = reply_text[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.015)

            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/appointments")
def get_user_appointments_api(user_id: str, status: Optional[str] = None):
    """API lấy danh sách lịch hẹn của user"""
    return {
        "success": True,
        "data": appointment_service.get_user_appointments(user_id=user_id, status=status)
    }

@app.post("/api/leads")
def submit_lead(lead: LeadRequest):
    """Endpoint thu thập Lead đặt lịch xem nhà"""
    print(f"🔥 [NEW LEAD ĐÀ NẴNG] Khách: {lead.name} | SĐT: {lead.phone} | BĐS: {lead.property_id}")
    return {
        "success": True,
        "message": "Đã ghi nhận thông tin đặt lịch xem nhà thành công!"
    }

# ==================== PHÂN HỆ THẨM ĐỊNH HỢP ĐỒNG BĐS ====================

@app.post("/api/contract/upload")
async def upload_contract_for_chat(file: UploadFile = File(...)):
    """Upload file hợp đồng (.pdf, .docx, .txt, .md) trong chat -> chuyển đổi sang Markdown bằng DocumentConverter"""
    try:
        file_bytes = await file.read()
        md_text = await asyncio.to_thread(
            DocumentConverter.convert_to_markdown, file_bytes, file.filename
        )

        # Kiểm tra sơ bộ nội dung tệp có dấu hiệu hợp đồng hay không
        text_lower = md_text.lower()
        contract_signatures = [
            "hợp đồng", "thỏa thuận", "đặt cọc", "mua bán", "chuyển nhượng", "cho thuê",
            "bên a", "bên b", "bên bán", "bên mua", "bên đặt cọc", "bên nhận cọc",
            "tiền cọc", "phạt cọc", "quyền sử dụng đất", "tài sản giao dịch"
        ]
        is_contract = any(sig in text_lower for sig in contract_signatures)

        return {
            "success": True,
            "filename": file.filename,
            "char_count": len(md_text),
            "content": md_text,
            "is_contract": is_contract,
            "warning": None if is_contract else "Tệp tải lên có thể không phải là văn bản hợp đồng hoặc thỏa thuận giao dịch bất động sản."
        }
    except TimeoutError as te:
        raise HTTPException(status_code=408, detail=str(te))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể đọc file hợp đồng: {str(e)}")

# ==================== PHÂN HỆ QUẢN TRỊ TÀI LIỆU PHÁP LÝ ====================

@app.post("/api/legal/upload")
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

@app.delete("/api/legal/documents/{doc_id}")
def delete_legal_document(doc_id: str):
    """Xóa tài liệu và toàn bộ vector liên quan"""
    try:
        success = legal_service.delete_document(doc_id)
        return {"success": success, "message": "Đã xóa tài liệu và vector liên quan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PHÂN HỆ ĐÁNH GIÁ RAGAS ====================

@app.get("/api/rag/evaluate")
async def evaluate_rag(node: Optional[str] = "all"):
    """
    Endpoint kích hoạt Ragas benchmark cho các node RAG.
    node: 'legal' (tư vấn pháp lý), 'contract_audit' (thẩm định hợp đồng), 'all' (tất cả)
    """
    try:
        from rag_evaluator import RAGEvaluator
        evaluator = RAGEvaluator()
        
        results = {}
        if node in ["legal", "all"]:
            ds_legal = await asyncio.to_thread(evaluator.prepare_dataset_from_legal_rag)
            results["legal"] = await asyncio.to_thread(evaluator.evaluate_legal_rag, ds_legal)
        
        if node in ["contract_audit", "all"]:
            ds_audit = await asyncio.to_thread(evaluator.prepare_dataset_from_contract_audit)
            results["contract_audit"] = await asyncio.to_thread(evaluator.evaluate_contract_audit_rag, ds_audit)
            
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Tắt reload để tránh tạo 2 process tranh chấp file Qdrant local
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
