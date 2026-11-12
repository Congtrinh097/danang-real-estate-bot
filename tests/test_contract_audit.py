import os
import sys
import pytest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage
from main import app
from contract_auditor import contract_auditor, ContractAuditReport, RiskSeverity
from agent import real_estate_agent

client = TestClient(app)

SAMPLE_RISKY_CONTRACT = """
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

THỎA THUẬN ĐẶT CỌC MUA BÁN CĂN HỘ CHUNG CƯ HÌNH THÀNH TRONG TƯƠNG LAI
Hôm nay, ngày 10 tháng 10 năm 2024, tại quận Sơn Trà, TP. Đà Nẵng, các bên gồm:
- Bên A (Bên Bán): Công ty Cổ phần Đầu tư Bất động sản XYZ (Chủ đầu tư dự án căn hộ The Ocean View Đà Nẵng).
- Bên B (Bên Mua): Ông Nguyễn Văn A, CCCD số 04809000xxxx.

Hai bên thống nhất ký thỏa thuận đặt cọc với các điều khoản sau:
Điều 1: Tài sản giao dịch
Căn hộ số A12-05 tại dự án The Ocean View, đường Võ Nguyên Giáp, quận Sơn Trà, TP. Đà Nẵng. Dự án đang trong giai đoạn hoàn thiện móng cọc.
Giá bán căn hộ: 2.000.000.000 VNĐ (Hai tỷ đồng).

Điều 2: Tiền đặt cọc
Bên B đồng ý đặt cọc cho Bên A số tiền là 300.000.000 VNĐ (Ba trăm triệu đồng, tương đương 15% tổng giá trị căn hộ) ngay sau khi ký thỏa thuận này.

Điều 3: Xử lý tiền đặt cọc và phạt vi phạm
- Nếu Bên B (Bên mua) không tiếp tục ký Hợp đồng mua bán đúng thời hạn thì Bên B sẽ mất toàn bộ số tiền đặt cọc 300.000.000 VNĐ cho Bên A.
- Nếu Bên A (Bên bán) không tiếp tục bán căn hộ cho Bên B thì Bên A chỉ có trách nhiệm hoàn trả lại số tiền đặt cọc gốc 300.000.000 VNĐ cho Bên B trong vòng 30 ngày mà không phải chịu bất kỳ khoản phạt cọc hay bồi thường nào khác.

Điều 4: Nghĩa vụ tài chính và Thuế phí
Mọi khoản thuế thu nhập cá nhân, lệ phí trước bạ và phí cấp Giấy chứng nhận quyền sở hữu căn hộ sẽ do Bên B (Bên mua) tự chịu chi phí khi làm thủ tục sau này.
"""

def test_contract_auditor_detects_5_percent_deposit_limit():
    """
    Test theo TDD:
    Kiểm tra ContractAuditor phát hiện bẫy cọc 15% (300 triệu / 2 tỷ) đối với nhà ở dự án hình thành tương lai:
    1. Phải gắn nhãn mức độ rủi ro CRITICAL (Nghiêm trọng).
    2. Viện dẫn đúng căn cứ Luật Kinh doanh Bất động sản 2023 (trần 5%).
    3. Đưa ra câu chữ sửa đổi (đề xuất hạ cọc về mức <= 5%, tức tối đa 100 triệu).
    """
    report = contract_auditor.audit_contract_structured(SAMPLE_RISKY_CONTRACT)
    assert isinstance(report, ContractAuditReport)
    assert report.safety_score < 70  # Hợp đồng nhiều bẫy phải có điểm an toàn thấp

    deposit_clauses = [c for c in report.clauses if "cọc" in c.clause_title.lower() or "tỷ lệ" in c.clause_title.lower()]
    assert len(deposit_clauses) > 0

    critical_clauses = [c for c in report.clauses if c.severity == RiskSeverity.CRITICAL or c.severity == "critical"]
    assert len(critical_clauses) >= 1

    # Kiểm tra có điều khoản cảnh báo trần 5% hoặc luật kinh doanh BĐS
    has_5pct_warning = any("5%" in c.risk_assessment or "kinh doanh bất động sản" in c.legal_reference.lower() for c in report.clauses)
    assert has_5pct_warning, "Không tìm thấy cảnh báo về trần đặt cọc 5% theo Luật Kinh doanh BĐS 2023"

def test_contract_auditor_detects_unilateral_penalty():
    """
    Test theo TDD:
    Kiểm tra ContractAuditor phát hiện điều khoản phạt cọc một chiều:
    Bên bán hủy cọc chỉ trả lại tiền cọc gốc mà không chịu phạt cọc.
    1. Phải gắn nhãn CRITICAL (Nghiêm trọng) hoặc WARNING.
    2. Viện dẫn Điều 328 Bộ luật Dân sự 2015.
    3. Đề xuất sửa đổi điều khoản phạt cọc bình đẳng (bên bán hủy phải phạt cọc tương đương).
    """
    report = contract_auditor.audit_contract_structured(SAMPLE_RISKY_CONTRACT)
    has_unilateral_penalty = any(
        "328" in c.legal_reference or "phạt cọc" in c.clause_title.lower() or "một chiều" in c.risk_assessment.lower()
        for c in report.clauses
    )
    assert has_unilateral_penalty, "Không phát hiện bẫy phạt cọc một chiều vi phạm Điều 328 BLDS"

def test_router_classifies_contract_audit_intent():
    """
    Test theo TDD:
    Kiểm tra Router Node phân loại chính xác câu hỏi thẩm định hợp đồng sang intent 'contract_audit'.
    """
    thread_id = "test_tdd_audit_router_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_audit", thread_id]
    }
    query = "Nhờ bot kiểm tra giúp tôi hợp đồng đặt cọc này xem có bẫy phạt cọc hay vi phạm luật không: Bên bán bắt cọc 20% và nếu hủy bên bán chỉ trả lại tiền gốc."
    final_state = real_estate_agent.invoke({"messages": [HumanMessage(content=query)]}, config=config)

    assert final_state["intent"] == "contract_audit"
    bot_msg = final_state["messages"][-1].content
    assert "thẩm định" in bot_msg.lower() or "an toàn" in bot_msg.lower() or "rủi ro" in bot_msg.lower() or "điểm" in bot_msg.lower()

def test_contract_upload_api_endpoint():
    """
    Test theo TDD:
    Endpoint POST /api/contract/upload nhận file hợp đồng dạng text và trả về nội dung markdown.
    """
    file_content = b"# HOP DONG DAT COC NHA DAT\nDieu 1: Gia ban 2 ty, tien coc 100 trieu."
    response = client.post(
        "/api/contract/upload",
        files={"file": ("test_contract.txt", file_content, "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "HOP DONG DAT COC" in data["content"]
    assert data["filename"] == "test_contract.txt"
