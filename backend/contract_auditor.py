import re
import os
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import settings
from legal_service import legal_service


class RiskSeverity(str, Enum):
    CRITICAL = "critical"    # Đỏ: Vi phạm pháp luật, nguy cơ mất cọc, chế tài 1 chiều
    WARNING = "warning"      # Vàng: Điều khoản bất lợi, mập mờ, thiếu thời hạn
    COMPLIANT = "compliant"  # Xanh: Hợp pháp, an toàn, chuẩn quy định


class ContractClauseAnalysis(BaseModel):
    clause_title: str = Field(..., description="Tiêu đề hoặc vị trí điều khoản (ví dụ: 'Điều 2: Tiền đặt cọc', 'Điều 3: Xử lý phạt cọc')")
    severity: RiskSeverity = Field(..., description="'critical', 'warning', hoặc 'compliant'")
    original_text: str = Field(..., description="Trích đoạn ngắn điều khoản gốc trong hợp đồng")
    risk_assessment: str = Field(..., description="Phân tích rủi ro cụ thể và chỉ ra điểm bất lợi cho người mua")
    legal_reference: str = Field(..., description="Căn cứ pháp luật viện dẫn (ví dụ: 'Khoản 5 Điều 23 Luật Kinh doanh BĐS 2023', 'Điều 328 Bộ luật Dân sự 2015')")
    citation_num: Optional[int] = Field(None, description="Số thứ tự trích dẫn [1], [2] tương ứng căn cứ pháp lý")
    suggested_amendment: Optional[str] = Field(None, description="Câu chữ đề xuất sửa đổi cụ thể để khách hàng đàm phán lại")


class ContractAuditReport(BaseModel):
    is_contract: bool = Field(True, description="True nếu tài liệu/văn bản gửi lên là hợp đồng, thỏa thuận đặt cọc, chuyển nhượng hoặc mua bán/cho thuê BĐS. False nếu là văn bản thông thường, bài viết, tin nhắn, mã code, thơ văn hoặc tài liệu không phải hợp đồng.")
    non_contract_reason: Optional[str] = Field(None, description="Nếu is_contract=False, giải thích ngắn gọn tại sao tài liệu không phải là hợp đồng mua bán/đặt cọc BĐS.")
    contract_type: str = Field(..., description="Phân loại hợp đồng: 'dat_coc_du_an' (dự án/hình thành tương lai), 'dat_coc_ca_nhan' (nhà đất thổ cư cá nhân), 'mua_ban', 'thue_nha', hoặc 'khong_phai_hop_dong'")
    safety_score: int = Field(..., description="Điểm an toàn pháp lý trên thang 100 (0 - 100). Hợp đồng có vi phạm nghiêm trọng thì điểm < 70. Nếu không phải hợp đồng thì để 0.")
    summary: str = Field(..., description="Tóm tắt nhận định tổng quan về hợp đồng hoặc thông báo từ chối thẩm định do không phải hợp đồng.")
    clauses: List[ContractClauseAnalysis] = Field(default_factory=list, description="Danh sách các điều khoản được thẩm định (để trống nếu không phải hợp đồng)")
    action_checklist: List[str] = Field(default_factory=list, description="Các bước khuyến nghị người mua cần làm trước khi đặt bút ký (để trống nếu không phải hợp đồng)")


# Prompt phân tích và bóc tách rủi ro hợp đồng chuyên sâu
audit_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Bạn là chuyên gia thẩm định pháp lý hợp đồng bất động sản hàng đầu tại Việt Nam và TP. Đà Nẵng.\n"
     "Nhiệm vụ của bạn là rà soát, phát hiện toàn bộ các 'bẫy pháp lý', điều khoản bất lợi và nguy cơ mất cọc trong bản hợp đồng/thỏa thuận đặt cọc của người dùng.\n\n"
     "QUY TẮC TIÊN QUYẾT - XÁC THỰC TÀI LIỆU CÓ PHẢI HỢP ĐỒNG KHÔNG:\n"
     "Trước khi thẩm định, bạn PHẢI kiểm tra xem văn bản được gửi có đúng là hợp đồng, thỏa thuận đặt cọc, chuyển nhượng, mua bán hoặc cho thuê bất động sản không.\n"
     "- Nếu văn bản KHÔNG PHẢI là hợp đồng (ví dụ: là bài thơ, đoạn chat thông thường, bài báo, tài liệu mô tả kỹ thuật, code lập trình, tài liệu quy phạm pháp luật thuần túy, tin tức chung...):\n"
     "  -> Đặt `is_contract = False`\n"
     "  -> Đặt `contract_type = 'khong_phai_hop_dong'`\n"
     "  -> Đặt `safety_score = 0`\n"
     "  -> Đặt `summary = 'Tài liệu được cung cấp không phải là hợp đồng mua bán, đặt cọc hoặc chuyển nhượng bất động sản. Vui lòng tải lên hoặc cung cấp văn bản hợp đồng/thỏa thuận hợp lệ để hệ thống tiến hành thẩm định.'`\n"
     "  -> Đặt `non_contract_reason` giải thích rõ nội dung tài liệu này thực chất là gì.\n"
     "  -> Đặt `clauses = []` và `action_checklist = []`.\n"
     "- Nếu văn bản ĐÚNG LÀ HỢP ĐỒNG BĐS: Đặt `is_contract = True`, phân tích chi tiết theo các tiêu chí bên dưới.\n\n"
     "CĂN CỨ PHÁP LÝ TỪ HỆ THỐNG:\n"
     "{context_str}\n\n"
     "CÁC TIÊU CHÍ BẮT BUỘC PHẢI SOI XÉT VÀ CẢNH BÁO (KHI LÀ HỢP ĐỒNG):\n"
     "1. TRẦN TIỀN ĐẶT CỌC 5%: Khoản 5 Điều 23 Luật Kinh doanh BĐS 2023 quy định chủ đầu tư chỉ được thu tiền đặt cọc KHÔNG QUÁ 5% giá bán nhà ở hình thành trong tương lai khi đủ điều kiện. Nếu hợp đồng thu trên 5% (ví dụ: 10%, 15%, 20%, 30%) -> BẮT BUỘC gắn nhãn CRITICAL (Nghiêm trọng), cảnh báo vi phạm điều cấm của luật.\n"
     "2. PHẠT CỌC MỘT CHIỀU: Điều 328 Bộ luật Dân sự 2015 quy định nếu bên nhận cọc từ chối giao kết phải trả lại cọc và một khoản tiền tương đương (phạt cọc gấp đôi). Nếu hợp đồng quy định bên bán hủy chỉ trả lại cọc gốc mà không chịu phạt cọc -> BẮT BUỘC gắn nhãn CRITICAL (Nghiêm trọng).\n"
     "3. TÌNH TRẠNG PHÁP LÝ TÀI SẢN: Kiểm tra giấy tờ chứng nhận, giấy phép mở bán, cam kết giải chấp ngân hàng (Điều 160 Luật Nhà ở 2023). Nếu không cam kết hoặc miễn trừ trách nhiệm -> gắn nhãn CRITICAL hoặc WARNING.\n"
     "4. THỜI HẠN VÀ TIẾN ĐỘ: Thời hạn ký hợp đồng mua bán, công chứng sang tên nếu ghi mơ hồ ('khi đủ điều kiện', không có ngày cụ thể) -> gắn nhãn WARNING.\n"
     "5. THUẾ PHÍ: Thuế TNCN (2% bên bán), Lệ phí trước bạ (0.5% bên mua). Nếu đẩy toàn bộ cho bên mua chịu mà không giảm giá -> gắn nhãn WARNING.\n"
     "6. ĐIỂM AN TOÀN (safety_score): Nếu có vi phạm CRITICAL thì điểm tối đa là 60/100. Càng nhiều vi phạm điểm càng thấp (30 - 55). Hợp đồng an toàn chỉ khi đạt từ 80 - 100 điểm.\n"
     "7. ĐỀ XUẤT SỬA ĐỔI (suggested_amendment): Luôn viết sẵn câu chữ hoàn chỉnh, chuẩn mực pháp lý để người mua copy đàm phán lại."
    ),
    ("user",
     "Dưới đây là nội dung hợp đồng cần thẩm định:\n\n{contract_text}"
    )
])


class ContractAuditor:
    def __init__(self):
        llm_kwargs = {
            "model": settings.OPENAI_MODEL_NAME,
            "api_key": settings.OPENAI_API_KEY or "dummy_key_mock",
            "temperature": 0.1
        }
        if settings.OPENAI_BASE_URL:
            llm_kwargs["base_url"] = settings.OPENAI_BASE_URL
            if "openrouter.ai" in settings.OPENAI_BASE_URL:
                llm_kwargs["default_headers"] = {
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Da Nang Real Estate Bot (Contract Auditor)"
                }
        self.llm = ChatOpenAI(**llm_kwargs)
        self.structured_chain = audit_prompt | self.llm.with_structured_output(ContractAuditReport)

    def search_legal_grounding(self, contract_text: str) -> List[Dict[str, Any]]:
        """Tìm kiếm các điều khoản luật liên quan trong Qdrant legal docs"""
        query = "quy định đặt cọc trần 5% phạt cọc điều 328 hợp đồng mua bán chuyển nhượng điều kiện giao dịch"
        # Trích một vài từ khóa từ hợp đồng
        if "hình thành trong tương lai" in contract_text.lower() or "dự án" in contract_text.lower():
            query += " nhà ở hình thành trong tương lai chủ đầu tư"
        if "phạt" in contract_text.lower() or "hủy" in contract_text.lower():
            query += " xử lý tiền đặt cọc bồi thường thiệt hại"

        return legal_service.search_legal_context(query, top_k=4)

    def audit_contract_structured(self, contract_text: str) -> ContractAuditReport:
        """Phân tích cấu trúc hợp đồng bằng LLM với cơ chế fallback heuristic an toàn"""
        # 1. Tiền kiểm tra heuristic nhanh: nếu văn bản quá ngắn hoặc hoàn toàn không có bất kỳ từ khóa hợp đồng nào
        text_lower = contract_text.lower()
        contract_signatures = [
            "hợp đồng", "thỏa thuận", "đặt cọc", "mua bán", "chuyển nhượng", "cho thuê",
            "bên a", "bên b", "bên bán", "bên mua", "bên đặt cọc", "bên nhận cọc",
            "chế tài", "phạt cọc", "bàn giao căn hộ", "quyền sử dụng đất", "giấy chứng nhận",
            "thực hiện hợp đồng", "chấm dứt hợp đồng"
        ]
        matching_signatures = [sig for sig in contract_signatures if sig in text_lower]
        
        # Nếu hoàn toàn không có bất kỳ từ khóa pháp lý hợp đồng nào hoặc văn bản không đủ căn cứ hợp đồng
        if len(matching_signatures) == 0:
            return ContractAuditReport(
                is_contract=False,
                non_contract_reason="Văn bản không chứa các thuật ngữ hoặc thành phần cơ bản của hợp đồng/thỏa thuận giao dịch (như Bên A, Bên B, thỏa thuận đặt cọc, chuyển nhượng hoặc mua bán).",
                contract_type="khong_phai_hop_dong",
                safety_score=0,
                summary="Tài liệu bạn cung cấp không phải là hợp đồng mua bán, đặt cọc hoặc chuyển nhượng bất động sản.",
                clauses=[],
                action_checklist=[]
            )

        legal_context = self.search_legal_grounding(contract_text)
        context_str = "\n\n".join([
            f"[{item['index']}] {item['doc_title']} - {item['article']}:\n{item['content']}"
            for item in legal_context
        ])

        try:
            report = self.structured_chain.invoke({
                "context_str": context_str,
                "contract_text": contract_text
            })
            # Nếu LLM xác định không phải hợp đồng
            if not report.is_contract or report.contract_type == "khong_phai_hop_dong":
                report.is_contract = False
                report.contract_type = "khong_phai_hop_dong"
                report.safety_score = 0
                report.clauses = []
                report.action_checklist = []
                return report

            # Gán citation_num nếu điều khoản khớp với context
            for clause in report.clauses:
                ref_lower = clause.legal_reference.lower()
                for ctx in legal_context:
                    art_lower = ctx.get("article", "").lower()
                    if ("328" in ref_lower and "328" in art_lower) or \
                       ("23" in ref_lower and "23" in art_lower) or \
                       ("160" in ref_lower and "160" in art_lower) or \
                       ("45" in ref_lower and "45" in art_lower):
                        clause.citation_num = ctx.get("index")
                        break
            return report
        except Exception as e:
            # Fallback heuristic thông minh nếu LLM gặp sự cố
            return self._heuristic_audit_fallback(contract_text, legal_context)

    def _heuristic_audit_fallback(self, contract_text: str, legal_context: List[Dict[str, Any]]) -> ContractAuditReport:
        """Phân tích heuristic dựa trên quy tắc khi offline hoặc lỗi API"""
        text_lower = contract_text.lower()

        # Kiểm tra tiền điều kiện: tài liệu có dấu hiệu của hợp đồng / thỏa thuận pháp lý BĐS hay không
        contract_signatures = [
            "hợp đồng", "thỏa thuận", "đặt cọc", "mua bán", "chuyển nhượng", "cho thuê",
            "bên a", "bên b", "bên bán", "bên mua", "bên đặt cọc", "bên nhận cọc",
            "điều 1", "điều 2", "điều khoản", "tài sản giao dịch", "giá chuyển nhượng"
        ]
        matching_signatures = [sig for sig in contract_signatures if sig in text_lower]

        # Nếu không có đủ các dấu hiệu cơ bản của hợp đồng (ít nhất 2 dấu hiệu như 'bên a'/'bên b' hoặc 'hợp đồng'/'đặt cọc')
        is_likely_contract = len(matching_signatures) >= 2 or (
            ("hợp đồng" in text_lower or "đặt cọc" in text_lower or "thỏa thuận" in text_lower) and
            ("bên a" in text_lower or "bên b" in text_lower or "điều" in text_lower)
        )

        if not is_likely_contract:
            return ContractAuditReport(
                is_contract=False,
                non_contract_reason="Văn bản không chứa các yếu tố cơ bản của một hợp đồng hay thỏa thuận giao dịch bất động sản (như thông tin các bên Bên A/Bên B, điều khoản, tài sản giao dịch, quyền và nghĩa vụ).",
                contract_type="khong_phai_hop_dong",
                safety_score=0,
                summary="Tài liệu bạn cung cấp không phải là hợp đồng mua bán, đặt cọc hoặc chuyển nhượng bất động sản. Hệ thống chỉ thực hiện rà soát và thẩm định rủi ro pháp lý đối với các văn bản hợp đồng / thỏa thuận giao dịch BĐS.",
                clauses=[],
                action_checklist=[]
            )

        clauses = []
        score = 85

        # 1. Kiểm tra trần cọc 5%
        has_future_project = "hình thành trong tương lai" in text_lower or "dự án" in text_lower
        # Kiểm tra tỷ lệ cọc %
        pct_match = re.search(r"(\d+)\s*%", text_lower)
        if pct_match:
            pct_val = int(pct_match.group(1))
            if has_future_project and pct_val > 5:
                score -= 35
                clauses.append(ContractClauseAnalysis(
                    clause_title=f"Tiền đặt cọc ({pct_val}% giá trị căn hộ)",
                    severity=RiskSeverity.CRITICAL,
                    original_text=f"Thu tiền đặt cọc tương đương {pct_val}% giá trị hợp đồng.",
                    risk_assessment=f"Theo Khoản 5 Điều 23 Luật Kinh doanh BĐS 2023, chủ đầu tư chỉ được thu tiền đặt cọc tối đa không quá 5% giá bán nhà ở hình thành trong tương lai. Mức thu {pct_val}% là vi phạm điều cấm của pháp luật, tiềm ẩn rủi ro chiếm dụng vốn và mất trắng tiền cọc khi dự án chậm tiến độ.",
                    legal_reference="Khoản 5 Điều 23 Luật Kinh doanh Bất động sản 2023",
                    citation_num=1,
                    suggested_amendment=f"Đề xuất sửa đổi: 'Bên B đặt cọc cho Bên A số tiền tương ứng tối đa không quá 5% tổng giá trị hợp đồng theo đúng quy định tại Khoản 5 Điều 23 Luật Kinh doanh Bất động sản 2023.'"
                ))
            elif not has_future_project and pct_val > 20:
                score -= 15
                clauses.append(ContractClauseAnalysis(
                    clause_title=f"Tỷ lệ tiền đặt cọc cao ({pct_val}%)",
                    severity=RiskSeverity.WARNING,
                    original_text=f"Tiền đặt cọc chiếm {pct_val}% tổng giá trị BĐS.",
                    risk_assessment=f"Tỷ lệ đặt cọc {pct_val}% là mức rất cao đối với giao dịch nhà đất thổ cư riêng lẻ (thông thường chỉ từ 5% - 10%). Nếu xảy ra tranh chấp hoặc quy hoạch, bên mua sẽ chịu rủi ro giữ vốn rất lớn.",
                    legal_reference="Tập quán giao dịch BĐS và Điều 328 Bộ luật Dân sự 2015",
                    suggested_amendment="Đề xuất hạ mức tiền đặt cọc xuống còn 5% - 10% giá trị giao dịch."
                ))

        # 2. Kiểm tra phạt cọc một chiều
        if ("chỉ" in text_lower and "hoàn trả" in text_lower and "không" in text_lower and "phạt" in text_lower) or \
           ("hoàn lại tiền cọc gốc" in text_lower):
            score -= 30
            clauses.append(ContractClauseAnalysis(
                clause_title="Chế tài phạt vi phạm cọc một chiều",
                severity=RiskSeverity.CRITICAL,
                original_text="Nếu Bên Bán không tiếp tục bán thì chỉ hoàn trả lại tiền cọc gốc mà không chịu phạt cọc.",
                risk_assessment="Điều khoản này hoàn toàn bất bình đẳng và vi phạm nguyên tắc đặt cọc tại Điều 328 Bộ luật Dân sự 2015. Bên mua nếu hủy thì mất 100% tiền cọc, trong khi bên bán nếu hủy chỉ trả lại tiền gốc mà không phải bồi thường hay chịu phạt cọc gấp đôi. Bên bán có thể dễ dàng 'bẻ cọc' bán cho người khác trả giá cao hơn.",
                legal_reference="Khoản 2 Điều 328 Bộ luật Dân sự 2015",
                citation_num=2,
                suggested_amendment="Đề xuất sửa đổi: 'Nếu Bên A từ chối việc giao kết hoặc thực hiện hợp đồng mua bán thì phải hoàn trả cho Bên B toàn bộ số tiền đặt cọc đã nhận và thanh toán thêm một khoản tiền phạt cọc tương đương đúng bằng 100% số tiền đặt cọc.'"
            ))

        # 3. Kiểm tra nghĩa vụ thuế phí
        if "bên mua" in text_lower and ("tự chịu" in text_lower or "toàn bộ" in text_lower) and "thuế" in text_lower:
            score -= 10
            clauses.append(ContractClauseAnalysis(
                clause_title="Thỏa thuận nghĩa vụ thuế thu nhập cá nhân",
                severity=RiskSeverity.WARNING,
                original_text="Bên mua tự chịu toàn bộ thuế thu nhập cá nhân và lệ phí trước bạ.",
                risk_assessment="Theo Luật Thuế Thu nhập cá nhân, Thuế TNCN (2%) là nghĩa vụ tài chính của bên chuyển nhượng (bên bán). Nếu hợp đồng bắt bên mua chịu thay thì bên mua phải cộng thêm khoản chi phí này vào tổng giá mua thực tế.",
                legal_reference="Quy định về Thuế Thu nhập cá nhân và Lệ phí trước bạ",
                suggested_amendment="Đề xuất thỏa thuận rõ: Bên bán chịu Thuế TNCN 2%, Bên mua chịu Lệ phí trước bạ 0.5% theo đúng bản chất nghĩa vụ luật định."
            ))

        if not clauses:
            clauses.append(ContractClauseAnalysis(
                clause_title="Điều khoản cơ bản",
                severity=RiskSeverity.COMPLIANT,
                original_text="Hợp đồng ghi nhận thông tin tài sản và đặt cọc cơ bản.",
                risk_assessment="Hợp đồng không chứa các dấu hiệu vi phạm điều cấm rõ ràng.",
                legal_reference="Bộ luật Dân sự 2015",
                suggested_amendment=None
            ))

        score = max(min(score, 100), 20)
        return ContractAuditReport(
            contract_type="dat_coc_du_an" if has_future_project else "dat_coc_ca_nhan",
            safety_score=score,
            summary="Hợp đồng chứa các bẫy pháp lý bất lợi nghiêm trọng về tiền cọc và chế tài phạt cọc một chiều cần được đàm phán sửa đổi trước khi ký." if score < 70 else "Hợp đồng cơ bản đáp ứng các quy định pháp luật.",
            clauses=clauses,
            action_checklist=[
                "Yêu cầu bên bán ký Phụ lục sửa đổi điều khoản phạt cọc theo Điều 328 BLDS.",
                "Yêu cầu kiểm tra hồ sơ pháp lý dự án và bảo lãnh ngân hàng trước khi chuyển tiền.",
                "Thực hiện chuyển khoản qua tài khoản ngân hàng chính thức có ghi rõ nội dung cọc."
            ]
        )

    def format_report_to_markdown(self, report: ContractAuditReport, citations: List[Dict[str, Any]]) -> str:
        """Định dạng báo cáo thẩm định sang Markdown phong phú, chuẩn UI có badge, trích dẫn [1], [2]"""
        # Nếu tài liệu không phải hợp đồng mua bán / đặt cọc BĐS
        if not report.is_contract or report.contract_type == "khong_phai_hop_dong":
            reason_text = f"\n> **Chi tiết:** {report.non_contract_reason}\n" if report.non_contract_reason else ""
            return (
                "### ⚠️ KẾT QUẢ XÁC THỰC TÀI LIỆU\n\n"
                "> 🚫 **Thông báo:** **Văn bản này không phải là hợp đồng mua bán hoặc thỏa thuận đặt cọc bất động sản.**\n"
                f"{reason_text}\n"
                f"**Nhận định của hệ thống:** {report.summary}\n\n"
                "---\n"
                "💡 **Khuyến nghị:** Hệ thống chỉ thực hiện rà soát rủi ro pháp lý và bẫy phạt cọc đối với các tài liệu giao dịch bất động sản hợp lệ như:\n"
                "- Hợp đồng đặt cọc mua bán / chuyển nhượng nhà đất, căn hộ chung cư.\n"
                "- Văn bản thỏa thuận giữ chỗ, đăng ký nguyện vọng dự án hình thành trong tương lai.\n"
                "- Hợp đồng mua bán, chuyển nhượng quyền sử dụng đất và tài sản gắn liền với đất.\n"
                "- Hợp đồng thuê nhà ở / căn hộ.\n\n"
                "Vui lòng kiểm tra lại và đính kèm đúng tệp hợp đồng giao dịch để được thẩm định chuyên sâu!"
            )

        # Xác định biểu tượng và nhãn điểm số
        if report.safety_score >= 80:
            score_badge = f"🟢 **{report.safety_score}/100 - HỢP ĐỒNG AN TOÀN**"
        elif report.safety_score >= 50:
            score_badge = f"🟡 **{report.safety_score}/100 - RỦI RO TRUNG BÌNH (CẦN ĐÀM PHÁN LẠI)**"
        else:
            score_badge = f"🔴 **{report.safety_score}/100 - CẢNH BÁO: RỦI RO PHÁP LÝ CAO**"

        lines = [
            "### 📋 BÁO CÁO THẨM ĐỊNH PHÁP LÝ HỢP ĐỒNG",
            f"> 🛡️ **Điểm Đánh Giá An Toàn:** {score_badge}\n",
            f"**Nhận định tổng quan:** {report.summary}\n",
            "---",
            "#### 🔍 CHI TIẾT THẨM ĐỊNH CÁC ĐIỀU KHOẢN:"
        ]

        # Phân loại điều khoản
        critical_items = [c for c in report.clauses if c.severity == RiskSeverity.CRITICAL or c.severity == "critical"]
        warning_items = [c for c in report.clauses if c.severity == RiskSeverity.WARNING or c.severity == "warning"]
        compliant_items = [c for c in report.clauses if c.severity == RiskSeverity.COMPLIANT or c.severity == "compliant"]

        def render_clause_block(clause: ContractClauseAnalysis, icon: str, level_name: str):
            cit_str = f" [{clause.citation_num}]" if clause.citation_num else ""
            block = [
                f"\n##### {icon} {clause.clause_title} *({level_name})*",
                f"- **Trích đoạn hợp đồng:** *\"{clause.original_text}\"*",
                f"- **Phân tích rủi ro:** {clause.risk_assessment}",
                f"- **Căn cứ pháp luật:** {clause.legal_reference}{cit_str}"
            ]
            if clause.suggested_amendment:
                block.append(f"- ✍️ **Đề xuất câu chữ sửa đổi:**\n  > *\"{clause.suggested_amendment}\"*")
            return "\n".join(block)

        if critical_items:
            lines.append("\n**🚨 CÁC ĐIỀU KHOẢN NGUY HIỂM / VI PHẠM PHÁP LUẬT:**")
            for c in critical_items:
                lines.append(render_clause_block(c, "🔴", "Rủi ro nghiêm trọng"))

        if warning_items:
            lines.append("\n**⚠️ CÁC ĐIỀU KHOẢN BẤT LỢI CẦN THƯƠNG LƯỢNG LẠI:**")
            for c in warning_items:
                lines.append(render_clause_block(c, "🟡", "Cần lưu ý"))

        if compliant_items:
            lines.append("\n**✅ CÁC ĐIỀU KHOẢN HỢP LỆ & AN TOÀN:**")
            for c in compliant_items:
                lines.append(render_clause_block(c, "🟢", "Hợp lệ"))

        if report.action_checklist:
            lines.append("\n---\n#### 📝 CHECKLIST HÀNH ĐỘNG KHUYẾN NGHỊ TRƯỚC KHI KÝ:")
            for idx, act in enumerate(report.action_checklist, 1):
                lines.append(f"{idx}. {act}")

        lines.append("\n💡 *Anh/chị có thể bấm vào các số trích dẫn pháp lý `[1]`, `[2]` để đối chiếu toàn văn quy định của Luật Đất đai, Luật Nhà ở và Luật Kinh doanh BĐS tại bảng tra cứu bên phải ạ.*")

        return "\n".join(lines)


contract_auditor = ContractAuditor()
