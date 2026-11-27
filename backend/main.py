import asyncio
import json
import sys
import io
import os
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load per-user overrides first; values already exported in the shell win.
backend_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=backend_dir / ".env.local", override=False)
load_dotenv(dotenv_path=backend_dir / ".env", override=False)

# Đảm bảo stdout / stderr hỗ trợ đầy đủ UTF-8 trên Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File, Response
from fastapi.encoders import jsonable_encoder
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
from config import settings
from pii_utils import mask_phone
from tenant_agent import process_tenant_intake
from tenant_models import ApprovalRequest, EmailIntake, TenantIntake
from tenant_store import tenant_ticket_store
from tenant_knowledge import tenant_knowledge_service
from sla_sensor import list_sla_alerts, run_sla_sensor
from agentops import (
    TraceContext,
    langfuse_manager,
    AgentOpsCallbackHandler,
    cost_reporting_service,
    cost_alert_engine,
    BudgetExceededException
)
from agentops.cost.user_wallet_service import user_wallet_service
from pydantic.fields import FieldInfo
from due_diligence_agent import DueDiligenceRequest, DueDiligenceDossier, FinancialFeasibilityAssessment
from due_diligence_service import due_diligence_task_manager

if "loan_amount_vnd" not in FinancialFeasibilityAssessment.model_fields:
    FinancialFeasibilityAssessment.__annotations__["loan_amount_vnd"] = Optional[float]
    FinancialFeasibilityAssessment.model_fields["loan_amount_vnd"] = FieldInfo.from_annotation(Optional[float])
    FinancialFeasibilityAssessment.model_fields["loan_amount_vnd"].default = 0.0
    FinancialFeasibilityAssessment.model_rebuild(force=True)
    DueDiligenceDossier.model_rebuild(force=True)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Tự động khởi tạo bảng AgentOps / Wallet / Groups nếu chưa có trên DB (Supabase/Postgres)
    try:
        from agentops.migrations.init_agentops_schema import init_agentops_database
        from agentops.migrations.add_user_wallet_tables import run_user_wallet_migrations
        from agentops.migrations.add_user_groups_table import run_user_groups_migrations
        init_agentops_database()
        run_user_wallet_migrations()
        run_user_groups_migrations()
    except Exception as exc:
        print(f"[WARN] Init AgentOps/Wallet schema lỗi hoặc đã tồn tại: {exc}")

    try:
        await asyncio.to_thread(qdrant_service.ingest_dataset, clear_existing=False)
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

class BudgetUpdateRequest(BaseModel):
    workload_type: str
    turn_limit_vnd: float
    thread_limit_vnd: float
    daily_limit_vnd: float

def require_admin(x_admin_key: str | None = Header(default=None)):
    """Protect staff APIs when ADMIN_API_KEY is configured; local dev remains frictionless."""
    if settings.ADMIN_API_KEY and x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Admin key không hợp lệ")


class TopupRequest(BaseModel):
    user_id: str
    amount_vnd: float
    description: Optional[str] = None

class UserFreeLimitUpdateRequest(BaseModel):
    user_id: str
    daily_free_limit_vnd: float

class UserGroupRequest(BaseModel):
    group_code: str
    group_name: str
    daily_free_limit_vnd: float
    description: Optional[str] = ""
    is_default: Optional[bool] = False

class SetUserGroupRequest(BaseModel):
    user_id: str
    group_code: str


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "city": "Đà Nẵng",
        "service": "danang-real-estate-bot",
        "version": "1.0.0"
    }

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

@app.get("/api/agentops/alerts/history")
def get_alert_history(limit: int = 20):
    """Lấy lịch sử các cảnh báo chi phí và vận hành đã ghi nhận"""
    return cost_alert_engine.get_alert_history(limit=limit)

@app.get("/api/agentops/budgets")
def get_budgets():
    """Lấy danh sách cấu hình hạn mức chi phí (agentops_budgets)"""
    return {"success": True, "budgets": cost_reporting_service.get_all_budgets()}

@app.post("/api/agentops/budgets")
def update_budget(req: BudgetUpdateRequest):
    """Cập nhật hạn mức chi phí cho workload (chat, evaluation,...)"""
    updated = cost_reporting_service.update_budget(
        workload_type=req.workload_type,
        turn_limit_vnd=req.turn_limit_vnd,
        thread_limit_vnd=req.thread_limit_vnd,
        daily_limit_vnd=req.daily_limit_vnd
    )
    return {"success": True, "budget": updated}

@app.get("/api/agentops/reports/recent-events")
def get_recent_usage_events(limit: int = 25):
    """Lấy danh sách các cuộc gọi LLM chi tiết gần đây"""
    return cost_reporting_service.get_recent_usage_events(limit=limit)

# ==================== PHÂN HỆ VÍ & HẠN MỨC NGƯỜI DÙNG ====================
@app.get("/api/user/wallet")
def get_user_wallet(user_id: str = "default_user"):
    """Lấy thông tin ví và hạn mức ngày 5.000đ của người dùng"""
    return user_wallet_service.get_or_create_wallet(user_id=user_id)

@app.get("/api/wallet/{user_id}")
def get_user_wallet_by_path(user_id: str):
    """Alias endpoint hỗ trợ lấy thông tin ví người dùng qua đường dẫn /api/wallet/{user_id}"""
    return user_wallet_service.get_or_create_wallet(user_id=user_id)

@app.post("/api/user/wallet/topup")
def topup_user_wallet(req: TopupRequest):
    """Nạp thêm tiền vào ví người dùng (hỗ trợ các gói 5k, 10k, 20k, 50k, 100k...)"""
    wallet = user_wallet_service.topup_wallet(
        user_id=req.user_id,
        amount_vnd=req.amount_vnd,
        description=req.description or ""
    )
    return {"success": True, "wallet": wallet}

@app.get("/api/user/wallet/transactions")
def get_user_wallet_transactions(user_id: str = "default_user", limit: int = 20):
    """Lấy lịch sử giao dịch nạp và khấu trừ của ví người dùng"""
    return user_wallet_service.get_user_transactions(user_id=user_id, limit=limit)

# ==================== PHÂN HỆ QUẢN LÝ NHÓM NGƯỜI DÙNG & HẠN MỨC FREE ====================
@app.get("/api/user/groups")
def get_user_groups():
    """Lấy danh sách các nhóm người dùng và hạn mức miễn phí mỗi ngày"""
    return {"success": True, "groups": user_wallet_service.get_all_user_groups()}

@app.post("/api/user/groups")
def save_user_group(req: UserGroupRequest):
    """Tạo mới hoặc cập nhật một nhóm người dùng (ví dụ: standard, vip, pro...)"""
    try:
        group = user_wallet_service.save_user_group(
            group_code=req.group_code,
            group_name=req.group_name,
            daily_free_limit_vnd=req.daily_free_limit_vnd,
            description=req.description or "",
            is_default=bool(req.is_default)
        )
        return {"success": True, "group": group}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/user/groups/{group_code}")
def delete_user_group(group_code: str):
    """Xóa nhóm người dùng tùy chỉnh"""
    try:
        user_wallet_service.delete_user_group(group_code=group_code)
        return {"success": True, "message": f"Đã xóa nhóm '{group_code}' thành công"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/user/wallet/set-group")
def set_user_group(req: SetUserGroupRequest):
    """Gán nhóm người dùng cho một user (ví dụ: chuyển user sang nhóm VIP)"""
    try:
        wallet = user_wallet_service.set_user_group(user_id=req.user_id, group_code=req.group_code)
        return {"success": True, "wallet": wallet}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/user-wallets")
def get_admin_user_wallets():
    """Lấy danh sách tất cả ví người dùng và hạn mức free (dành cho Admin)"""
    return {"success": True, "users": user_wallet_service.get_all_user_wallets()}

@app.post("/api/admin/user-wallets/free-limit")
def update_user_free_limit(req: UserFreeLimitUpdateRequest):
    """Admin điều chỉnh hạn mức miễn phí hàng ngày (daily_free_limit_vnd) cho user cụ thể"""
    try:
        updated = user_wallet_service.update_user_daily_free_limit(
            user_id=req.user_id,
            new_limit_vnd=req.daily_free_limit_vnd
        )
        return {"success": True, "wallet": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
        "recursion_limit": 50,
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
        # 1. Kiểm tra trước ngân sách cá nhân của user: 5.000đ miễn phí / ngày + số dư ví nạp
        effective_user_id = req.user_id or "default_user"
        try:
            can_chat, user_budget_msg, user_wallet = user_wallet_service.check_user_can_chat(
                user_id=effective_user_id,
                estimated_cost_vnd=50.0
            )
            if not can_chat:
                yield f"data: {json.dumps({'type': 'user_budget_exceeded', 'message': user_budget_msg, 'wallet': user_wallet})}\n\n"
                yield f"data: {json.dumps({'type': 'token', 'content': user_budget_msg})}\n\n"
                yield "data: [DONE]\n\n"
                return
        except Exception as u_err:
            print(f"[WARN] Pre-check user wallet budget failed: {u_err}")

        # 2. Kiểm tra trước hạn mức thread: nếu đã hết ngân sách thì chặn ngay từ đầu
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
                            "a2a_council": "🏛️ Đang triệu tập Hội đồng A2A War Room (BĐS, Tài chính, Pháp lý, Phản biện)...",
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
                    elif node_name == "a2a_council":
                        yield f"data: {json.dumps({'type': 'status', 'stage': 'a2a_completed', 'message': 'Hội đồng A2A đã thống nhất nghị quyết'})}\n\n"
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

            # Gửi sự kiện A2A Council Debate và Verdict nếu có
            a2a_debate = final_state.get("a2a_debate")
            if a2a_debate:
                yield f"data: {json.dumps({'type': 'a2a_debate', 'data': a2a_debate})}\n\n"

            a2a_verdict = final_state.get("a2a_verdict")
            if a2a_verdict:
                yield f"data: {json.dumps({'type': 'a2a_verdict', 'data': a2a_verdict})}\n\n"

            # Gửi phản hồi văn bản của Bot (nếu không có hitl_interrupt hiển thị thẻ xác nhận)
            messages = final_state.get("messages", [])
            if messages and not hitl_interrupt:
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

            # Khấu trừ chi phí vào ví user (ưu tiên 5.000đ free quota, vượt quá trừ balance)
            try:
                updated_wallet = user_wallet_service.deduct_request_cost(
                    user_id=effective_user_id,
                    request_id=request_id
                )
                yield f"data: {json.dumps({'type': 'wallet_update', 'data': updated_wallet})}\n\n"
            except Exception as w_err:
                print(f"[WARN] Failed to deduct user wallet cost: {w_err}")

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

    sub_config = {
        "configurable": {"thread_id": f"prop_sub_{req.thread_id}"},
        "recursion_limit": 50
    }

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

            # Kiểm tra trạng thái sub_state để xác định xem có interrupt chờ duyệt hay không
            sub_state = property_agent.get_state(sub_config)
            has_interrupt = False
            pending_args = {}
            if sub_state and sub_state.tasks:
                for task in sub_state.tasks:
                    interrupts = getattr(task, "interrupts", ())
                    if interrupts:
                        has_interrupt = True
                        for intr in interrupts:
                            intr_val = getattr(intr, "value", {})
                            reqs = intr_val.get("action_requests", [])
                            if reqs and reqs[0].get("args"):
                                pending_args = reqs[0]["args"]
                        break

            reply_text = ""
            if has_interrupt:
                # Có interrupt đang chờ -> Resume qua Command
                cmd = Command(resume={"decisions": [decision_payload]})
                agent_result = await asyncio.to_thread(property_agent.invoke, cmd, config=sub_config)
                agent_messages = agent_result.get("messages", [])
                if agent_messages:
                    reply_text = agent_messages[-1].content
                else:
                    reply_text = "Đã xử lý xong phản hồi của bạn."
            else:
                # Không còn interrupt trong bộ nhớ (ví dụ: phiên cũ sau khi restart backend hoặc bấm duyệt lại)
                # Xử lý trực tiếp để tránh lỗi GraphRecursionError
                effective_args = req.edited_args or pending_args
                if req.decision == "reject":
                    reply_text = "Dạ em đã ghi nhận và hủy yêu cầu đặt lịch xem nhà theo mong muốn của anh/chị ạ. Nếu anh/chị cần hỗ trợ thêm thông tin bất động sản nào khác tại Đà Nẵng, cứ nhắn em nhé!"
                elif req.decision in ["approve", "edit"] and (effective_args.get("name") or effective_args.get("phone")):
                    appt = appointment_service.create_appointment(
                        user_id=req.user_id or "default_user",
                        customer_name=effective_args.get("name", "Khách hàng"),
                        customer_phone=effective_args.get("phone", ""),
                        viewing_time=effective_args.get("viewing_time", "Theo thỏa thuận"),
                        property_title=effective_args.get("property_title", ""),
                        note=effective_args.get("note", "")
                    )
                    reply_text = (
                        f"✅ ĐÃ ĐẶT LỊCH HẸN THÀNH CÔNG!\n"
                        f"- Mã lịch hẹn: #{appt['id']}\n"
                        f"- Khách hàng: {appt['customer_name']}\n"
                        f"- Số điện thoại: {appt['customer_phone']}\n"
                        f"- Thời gian xem nhà: {appt['viewing_time']}\n"
                        f"- Bất động sản: {appt['property_title'] or 'Theo tư vấn trong chat'}\n"
                        f"- Ghi chú: {appt['note'] or 'Không có'}\n"
                        f"- Trạng thái: Đã xác nhận\n\n"
                        f"Chuyên viên tư vấn sẽ liên hệ lại với anh/chị trước giờ hẹn để đón tiếp chu đáo nhất ạ!"
                    )
                else:
                    reply_text = "Yêu cầu đặt lịch hẹn này đã được ghi nhận trước đó. Anh/chị có thể kiểm tra danh sách trong tab Lịch hẹn hoặc gửi tin nhắn mới để em hỗ trợ nhé!"

            chunk_size = 6
            for i in range(0, len(reply_text), chunk_size):
                chunk = reply_text[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.015)

            yield "data: [DONE]\n\n"
        except Exception as e:
            error_msg = str(e)
            if "Recursion limit" in error_msg:
                friendly_msg = (
                    "Yêu cầu đặt lịch hẹn của anh/chị đã được ghi nhận hoặc phiên làm việc trước đó đã hoàn tất. "
                    "Anh/chị có thể kiểm tra lịch hẹn đã lưu trong mục Quản lý lịch hẹn hoặc gửi tin nhắn mới để em hỗ trợ ạ."
                )
                yield f"data: {json.dumps({'type': 'token', 'content': friendly_msg})}\n\n"
            else:
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
    print(f"[NEW LEAD] phone={mask_phone(lead.phone)} property={lead.property_id}")
    return {
        "success": True,
        "message": "Đã ghi nhận thông tin đặt lịch xem nhà thành công!"
    }


# ==================== TENANT SUPPORT & SLA ASSURANCE ====================

@app.post("/api/tenant/intake")
async def tenant_intake(intake: TenantIntake):
    result = await asyncio.to_thread(process_tenant_intake, intake)
    return {"success": True, "data": result.model_dump(mode="json")}


@app.post("/api/tenant/email")
async def tenant_email_intake(email: EmailIntake):
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


@app.get("/api/tenant/tickets/{ticket_id}/history", dependencies=[Depends(require_admin)])
def get_tenant_handoff_history(ticket_id: str):
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Cần cấu hình khóa quản trị để xem lịch sử tenant.")
    ticket = tenant_ticket_store.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket không tồn tại")
    history = tenant_ticket_store.list_thread(ticket.thread_id, limit=51)
    return {
        "success": True,
        "data": {
            "has_earlier": len(history) > 50,
            "turns": [
                {
                    "ticket_id": turn.id,
                    "channel": turn.channel,
                    "created_at": turn.created_at,
                    "subject": turn.subject,
                    "message": turn.description,
                    "assistant_reply": turn.assistant_reply,
                    "status": turn.status,
                    "urgency": turn.urgency,
                }
                for turn in history[-50:]
            ],
        },
    }


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

# ==================== PHÂN HỆ THẨM ĐỊNH BĐS CHUYÊN SÂU (DEEP DUE DILIGENCE) ====================

class DueDiligenceSettingsRequest(BaseModel):
    cache_enabled: Optional[bool] = True
    cache_ttl_hours: Optional[int] = 48
    cache_hit_cost_vnd: Optional[float] = 0.0
    allow_force_refresh: Optional[bool] = True

class DueDiligenceCacheClearRequest(BaseModel):
    property_id: Optional[str] = None


@app.post("/api/due-diligence")
async def submit_due_diligence(req: DueDiligenceRequest):
    """
    Tiếp nhận yêu cầu thẩm định BĐS chuyên sâu Đà Nẵng:
    - Thiết lập AgentOps TraceContext với workload_type='due_diligence'
    - Kiểm tra Cache 48h; nếu Cache Hit -> miễn phí/áp dụng phí ưu đãi và trả về ngay
    - Nếu Cache Miss -> Kiểm tra hạn mức / số dư ví và khởi chạy multi-agent workflow
    - Trả về task_id để client theo dõi tiến độ qua SSE hoặc Polling
    """
    effective_user_id = req.user_id or "default_user"
    req_id = f"dd_req_{uuid.uuid4().hex[:8]}"
    thread_id = f"dd_thread_{effective_user_id}"
    TraceContext.set_context(request_id=req_id, thread_id=thread_id, workload_type="due_diligence")

    req_dict = req.model_dump() if hasattr(req, "model_dump") else dict(req)
    cached_record = due_diligence_task_manager.find_cached_dossier(req_dict)
    settings = due_diligence_task_manager.get_settings()
    is_cached_hit = bool(cached_record and cached_record.get("dossier_data"))
    estimated_cost = float(settings.get("cache_hit_cost_vnd", 0.0)) if is_cached_hit else 150.0

    if estimated_cost > 0:
        # Pre-flight check ngân sách người dùng nếu có tính phí
        try:
            can_proceed, budget_msg, wallet = user_wallet_service.check_user_can_chat(
                user_id=effective_user_id,
                estimated_cost_vnd=estimated_cost
            )
            if not can_proceed:
                raise HTTPException(
                    status_code=402,
                    detail="Ngân sách tài khoản không đủ để thực hiện thẩm định chuyên sâu. Vui lòng nạp thêm tiền vào ví."
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[WARN] Pre-flight budget check error: {e}")

    task_id = await due_diligence_task_manager.submit_task(req, user_id=effective_user_id)

    # Nếu có phí cache hit > 0, trừ tiền ví
    if is_cached_hit and estimated_cost > 0:
        try:
            user_wallet_service.deduct_user_cost(user_id=effective_user_id, cost_vnd=estimated_cost)
        except Exception as err:
            print(f"[WARN] Failed to deduct cache hit cost: {err}")

    return {
        "success": True,
        "task_id": task_id,
        "status": "completed" if is_cached_hit else "pending",
        "is_cached": is_cached_hit
    }


@app.get("/api/due-diligence/settings")
def get_due_diligence_settings():
    """Lấy cài đặt Admin cho phân hệ Thẩm định & Cache BĐS"""
    st = due_diligence_task_manager.get_settings()
    return {"success": True, "settings": st}


@app.post("/api/due-diligence/settings")
def update_due_diligence_settings(req: DueDiligenceSettingsRequest):
    """Admin cập nhật cài đặt cho phân hệ Thẩm định & Cache BĐS"""
    updates = req.model_dump(exclude_unset=True)
    updated = due_diligence_task_manager.update_settings(updates)
    return {"success": True, "settings": updated}


@app.post("/api/due-diligence/cache/clear")
def clear_due_diligence_cache(req: DueDiligenceCacheClearRequest):
    """Admin xóa/vô hiệu hóa cache thẩm định toàn bộ hoặc theo property_id"""
    count = due_diligence_task_manager.clear_cache(property_id=req.property_id)
    return {"success": True, "cleared_count": count, "property_id": req.property_id}


@app.get("/api/due-diligence/history")
def get_due_diligence_history(
    user_id: Optional[str] = None,
    scope: str = "user",
    limit: int = 50,
    offset: int = 0
):
    """Lấy danh sách lịch sử các hồ sơ thẩm định BĐS đã thực hiện"""
    history = due_diligence_task_manager.get_history(
        user_id=user_id,
        limit=limit,
        offset=offset,
        scope=scope
    )
    return {"success": True, "history": history, "total": len(history)}


@app.get("/api/due-diligence/history/{task_id}")
def get_due_diligence_history_detail(task_id: str):
    """Lấy chi tiết đầy đủ hồ sơ thẩm định cũ từ PostgreSQL"""
    record = due_diligence_task_manager.get_dossier_by_task_id(task_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy hồ sơ thẩm định cho mã {task_id}")
    return {"success": True, "task": record}


@app.delete("/api/due-diligence/history/{task_id}")
def delete_due_diligence_history_item(task_id: str):
    """Xóa một bản ghi hồ sơ thẩm định khỏi lịch sử"""
    success = due_diligence_task_manager.delete_record(task_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy bản ghi {task_id} hoặc xóa không thành công")
    return {"success": True, "message": f"Đã xóa thành công bản ghi thẩm định {task_id}", "task_id": task_id}


@app.delete("/api/due-diligence/history")
@app.post("/api/due-diligence/history/clear")
def clear_due_diligence_history_api(
    scope: str = "test",
    user_id: Optional[str] = None
):
    """
    Xóa lịch sử thẩm định:
    - scope='test': chỉ xóa các bản ghi thử nghiệm (test)
    - scope='user': xóa các bản ghi của user_id
    - scope='all': xóa toàn bộ
    """
    test_only = (scope == "test")
    count = due_diligence_task_manager.clear_history(
        test_only=test_only,
        user_id=user_id if scope == "user" else None
    )
    return {"success": True, "cleared_count": count, "scope": scope}


@app.get("/api/due-diligence/{task_id}")
async def get_due_diligence_status(task_id: str):
    """
    Polling endpoint truy vấn trạng thái tiến độ và kết quả Dossier thẩm định BĐS.
    """
    status_data = await due_diligence_task_manager.get_task_status(task_id)
    if not status_data:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy tác vụ thẩm định hoặc tác vụ đã hết hạn."
        )
    if isinstance(status_data, dict) and "dossier" in status_data and isinstance(status_data["dossier"], dict):
        fin = status_data["dossier"].get("financial")
        if isinstance(fin, dict) and "loan_amount_vnd" not in fin:
            fin["loan_amount_vnd"] = 0.0
    return Response(
        content=json.dumps(jsonable_encoder(status_data), ensure_ascii=False, default=str),
        media_type="application/json"
    )


@app.get("/api/due-diligence/{task_id}/stream")
async def stream_due_diligence_progress(task_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint phát trực tiếp tiến độ 4 giai đoạn
    (Planning -> Evidence Retrieval -> Adversarial Critic -> Dossier Synthesis)
    và kết quả báo cáo thẩm định.
    """
    bg_task = due_diligence_task_manager._background_tasks.get(task_id)
    if bg_task is None or bg_task.done():
        status_info = await due_diligence_task_manager.get_task_status(task_id)
        if status_info and status_info.get("status") not in ["completed", "failed"]:
            req_data = status_info.get("request") or {}
            user_id = status_info.get("user_id") or "default_user"
            new_bg = asyncio.create_task(due_diligence_task_manager._execute_task_workflow(task_id, req_data, user_id))
            due_diligence_task_manager._background_tasks[task_id] = new_bg
            new_bg.add_done_callback(lambda _: due_diligence_task_manager._background_tasks.pop(task_id, None))

    return StreamingResponse(
        due_diligence_task_manager.stream_progress(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

if __name__ == "__main__":
    import uvicorn
    # Tắt reload để tránh tạo 2 process tranh chấp file Qdrant local
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
