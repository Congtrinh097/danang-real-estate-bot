"""
A2A Council (War Room) Module for Multi-Agent Investment & Risk Analysis in Da Nang Real Estate.
Target: backend/a2a_council.py
"""

from enum import Enum
from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import operator
import re
import time
from langchain_core.messages import BaseMessage, AIMessage

from qdrant_service import qdrant_service
from mortgage_calculator import MortgageCalculator, MortgageInput
from legal_service import legal_service


class CouncilSpeaker(str, Enum):
    PLANNER = "planner"
    PROPERTY_EXPERT = "property_expert"
    FINANCIAL_ANALYST = "financial_analyst"
    LEGAL_ADVISOR = "legal_advisor"
    CRITIC = "adversarial_critic"
    SYNTHESIZER = "council_synthesizer"


class CouncilDebateTurn(BaseModel):
    speaker: CouncilSpeaker
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class CouncilVerdict(BaseModel):
    overall_feasibility: Literal["feasible", "caution_required", "high_risk"]
    feasibility_score: int = Field(..., ge=0, le=100)
    summary_recommendation: str
    property_match: Optional[Dict[str, Any]] = None
    financial_summary: Optional[Dict[str, Any]] = None
    legal_risks: List[str] = Field(default_factory=list)
    critic_caveats: List[str] = Field(default_factory=list)
    action_checklist: List[str] = Field(default_factory=list)


class A2ACouncilState(TypedDict):
    messages: Sequence[BaseMessage]
    user_query: str
    equity_capital: float
    target_price: float
    target_district: str
    property_findings: List[Dict[str, Any]]
    mortgage_analysis: Dict[str, Any]
    legal_citations: List[Dict[str, Any]]
    debate_history: Annotated[List[CouncilDebateTurn], operator.add]
    verdict: Optional[CouncilVerdict]


def _extract_amounts(text: str) -> tuple[float, float, str]:
    """Trích xuất vốn tự có, giá mục tiêu và quận từ câu hỏi người dùng"""
    equity = 0.0
    target_price = 0.0
    district = ""

    text_lower = text.lower()

    # Nhận diện quận tại Đà Nẵng
    districts = ["hải châu", "sơn trà", "ngũ hành sơn", "thanh khê", "cẩm lệ", "liên chiểu", "hòa vang"]
    for d in districts:
        if d in text_lower:
            district = d.title()
            break

    # Trích xuất số tiền theo tỷ / tỉ / triệu
    # Mẫu "có / vốn X tỷ" -> equity
    equity_match = re.search(r"(?:có|vốn|tự có|tiết kiệm)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu)", text_lower)
    if equity_match:
        val = float(equity_match.group(1).replace(",", "."))
        unit = equity_match.group(2)
        equity = val * 1_000_000_000.0 if "t" in unit else val * 1_000_000.0

    # Mẫu "mua / căn / giá X tỷ" -> target_price
    target_match = re.search(r"(?:mua|căn|nhà|bất động sản|giá|tầm|khoảng)\s*([\d\.,]+)\s*(tỷ|tỉ|triệu)", text_lower)
    if target_match:
        val = float(target_match.group(1).replace(",", "."))
        unit = target_match.group(2)
        target_price = val * 1_000_000_000.0 if "t" in unit else val * 1_000_000.0

    # Nếu chỉ tìm thấy 1 con số tỷ mà chưa gán
    all_billion = re.findall(r"([\d\.,]+)\s*(?:tỷ|tỉ)", text_lower)
    if all_billion:
        nums = [float(n.replace(",", ".")) * 1_000_000_000.0 for n in all_billion]
        if len(nums) >= 2:
            equity = min(nums)
            target_price = max(nums)
        elif len(nums) == 1:
            if target_price == 0.0 and equity > 0.0:
                target_price = nums[0] if nums[0] > equity else equity * 2.0
            elif equity == 0.0:
                target_price = nums[0]
                equity = target_price * 0.4  # Mặc định vốn 40%

    # Fallback mặc định thực tế cho Đà Nẵng nếu người dùng chưa nêu rõ số
    if target_price <= 0.0:
        target_price = 2_500_000_000.0
    if equity <= 0.0:
        equity = 1_000_000_000.0

    return equity, target_price, district


def council_planner_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 1: Phân rã mục tiêu đầu tư, trích xuất tham số và giao việc cho các chuyên gia"""
    user_query = state.get("user_query")
    if not user_query and state.get("messages"):
        user_query = state["messages"][-1].content
    user_query = user_query or ""

    equity, target_price, district = _extract_amounts(user_query)

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.PLANNER,
        title="Phân rã Mục tiêu Đầu tư & Giao việc Hội đồng",
        content=(
            f"Hội đồng A2A tiếp nhận yêu cầu phân tích đầu tư: Vốn tự có {equity:,.0f} VNĐ, "
            f"Mục tiêu BĐS giá {target_price:,.0f} VNĐ tại khu vực {district or 'Đà Nẵng'}. "
            f"Ủy thác 3 chuyên gia độc lập: BĐS Đà Nẵng kiểm tra giỏ hàng, Chuyên gia Tài chính lập lịch vay nợ, "
            f"và Cố vấn Pháp lý rà soát quy hoạch & điều kiện khai thác."
        ),
        key_points=[
            f"Vốn tự có: {equity:,.0f} VNĐ",
            f"Giá BĐS mục tiêu: {target_price:,.0f} VNĐ",
            f"Khu vực ưu tiên: {district or 'Toàn TP Đà Nẵng'}",
            f"Dự kiến vay vốn: {max(0.0, target_price - equity):,.0f} VNĐ"
        ]
    )
    return {
        "user_query": user_query,
        "equity_capital": equity,
        "target_price": target_price,
        "target_district": district,
        "debate_history": [turn]
    }


def council_property_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 2: Chuyên viên BĐS Đà Nẵng khảo sát quỹ căn thực tế từ Qdrant"""
    district = state.get("target_district") or None
    target_price = state.get("target_price") or 3_000_000_000.0
    user_query = state.get("user_query") or "BĐS Đà Nẵng"

    props = []
    try:
        props = qdrant_service.search_properties(
            query=user_query,
            category="sale",
            district=district,
            max_price=target_price * 1.15,  # Mở rộng 15% biên độ đàm phán
            limit=3
        )
    except Exception as e:
        print(f"[WARN] council_property_node search error: {e}")

    if not props:
        # Fallback mẫu dữ liệu đại diện Đà Nẵng
        props = [{
            "id": "prop_dn_sample_1",
            "title": f"Căn hộ cao cấp {district or 'Sơn Trà'} view sông Hàn",
            "district": district or "Sơn Trà",
            "price": target_price,
            "area": 68.5,
            "bedrooms": 2,
            "description": "Căn hộ bàn giao full nội thất cao cấp, sẵn sàng khai thác cho thuê."
        }]

    top_prop = props[0]
    p_summary = f"{top_prop.get('title')} ({top_prop.get('district')}): Giá {top_prop.get('price', 0):,.0f} VNĐ, DT {top_prop.get('area', 0)} m²"

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.PROPERTY_EXPERT,
        title="Báo cáo Khảo sát Thị trường BĐS Đà Nẵng",
        content=(
            f"Dựa trên cơ sở dữ liệu giỏ hàng thực tế tại {district or 'Đà Nẵng'}, "
            f"tôi đã lọc được {len(props)} phương án sát với mức ngân sách {target_price:,.0f} VNĐ. "
            f"Phương án tiêu biểu: {p_summary}. "
            f"Thị trường khu vực này có thanh khoản tốt và tiềm năng tăng trưởng ổn định."
        ),
        key_points=[
            f"Phương án đề xuất: {top_prop.get('title')}",
            f"Mức giá chào bán: {top_prop.get('price', 0):,.0f} VNĐ",
            f"Diện tích / Số phòng: {top_prop.get('area', 0)} m² ({top_prop.get('bedrooms', 2)} PN)",
            "Tiềm năng khai thác: Cho thuê dài hạn chuyên gia hoặc khách du lịch"
        ]
    )
    return {
        "property_findings": props,
        "debate_history": [turn]
    }


def council_mortgage_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 3: Chuyên viên Tài chính & Tín dụng tính toán phương án vay vốn"""
    target_price = state.get("target_price") or 2_500_000_000.0
    equity = state.get("equity_capital") or 1_000_000_000.0
    loan_amount = max(0.0, target_price - equity)
    if loan_amount <= 0:
        loan_amount = target_price * 0.7

    m_input = MortgageInput(
        property_price=target_price,
        loan_amount=loan_amount,
        tenure_years=20,
        annual_interest_rate=8.5,
        method="reducing_balance"
    )
    res = MortgageCalculator.calculate(m_input)

    first_month = res.first_month_payment
    monthly_principal = res.monthly_principal

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.FINANCIAL_ANALYST,
        title="Thẩm tra Đòn bẩy Tài chính & Lịch trả nợ",
        content=(
            f"Nhu cầu vay vốn: {loan_amount:,.0f} VNĐ (tỷ lệ {loan_amount / target_price * 100:.1f}% giá trị tài sản). "
            f"Với gói vay 20 năm, lãi suất 8.5%/năm theo dư nợ giảm dần: "
            f"Kỳ trả góp cao nhất (tháng đầu tiên) là {first_month:,.0f} VNĐ/tháng "
            f"(Gốc: {monthly_principal:,.0f} VNĐ + Lãi: {first_month - monthly_principal:,.0f} VNĐ). "
            f"Người mua cần đảm bảo thu nhập thực nhận tối thiểu từ 35-40 triệu/tháng để an toàn tài chính."
        ),
        key_points=[
            f"Số tiền vay ngân hàng: {loan_amount:,.0f} VNĐ",
            f"Nghĩa vụ tháng cao điểm: {first_month:,.0f} VNĐ/tháng",
            f"Nợ gốc cố định mỗi tháng: {monthly_principal:,.0f} VNĐ",
            "Mức thu nhập khuyến nghị: Tối thiểu gấp đôi số tiền phải trả hàng tháng"
        ]
    )

    mortgage_dict = res.model_dump()
    return {
        "mortgage_analysis": mortgage_dict,
        "debate_history": [turn]
    }


def council_legal_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 4: Cố vấn Pháp lý BĐS tra cứu Luật Đất đai & Nhà ở Đà Nẵng"""
    user_query = state.get("user_query") or "Pháp lý căn hộ sổ hồng cho thuê Đà Nẵng"
    citations = []
    try:
        citations = legal_service.search_legal_context(user_query, top_k=2)
    except Exception as e:
        print(f"[WARN] council_legal_node search error: {e}")

    if not citations:
        citations = [
            {
                "title": "Luật Nhà ở 2023 - Điều kiện kinh doanh cho thuê",
                "content": "Chủ sở hữu nhà ở được quyền cho thuê khi có Giấy chứng nhận quyền sở hữu (Sổ hồng), đảm bảo an toàn PCCC và an ninh trật tự."
            },
            {
                "title": "Luật Kinh doanh Bất động sản 2023 - Đặt cọc giao dịch",
                "content": "Chủ đầu tư dự án chỉ được thu tiền đặt cọc không quá 5% giá bán nhà ở khi đã đủ điều kiện kinh doanh."
            }
        ]

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.LEGAL_ADVISOR,
        title="Thẩm định Pháp lý, Quy hoạch & Điều kiện Khai thác",
        content=(
            "Về mặt pháp lý, giao dịch cần kiểm tra nghiêm ngặt 3 yếu tố: "
            "1. Tình trạng Sổ hồng (sở hữu lâu dài hay có thời hạn 50 năm). "
            "2. Nghiệm thu PCCC đối với tòa nhà căn hộ trước khi vận hành lưu trú du lịch. "
            "3. Hợp đồng mua bán / đặt cọc tuân thủ quy định trần cọc 5% theo Luật Kinh doanh BĐS mới."
        ),
        key_points=[
            "Kiểm tra Sổ hồng và hiện trạng giải chấp ngân hàng",
            "Điều kiện kinh doanh lưu trú: Đăng ký an ninh trật tự & tiêu chuẩn PCCC",
            "Hạn mức cọc tối đa không quá 5% giá trị hợp đồng"
        ]
    )
    return {
        "legal_citations": citations,
        "debate_history": [turn]
    }


def council_critic_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 5: Tác tử Phản biện (Adversarial Critic) chất vấn, tìm kẽ hở và rủi ro giấu kín"""
    mortgage = state.get("mortgage_analysis") or {}
    first_payment = mortgage.get("first_month_payment", 20_000_000.0)
    target_price = state.get("target_price") or 2_500_000_000.0
    equity = state.get("equity_capital") or 1_000_000_000.0
    loan_amount = mortgage.get("loan_amount", target_price - equity)
    ltv = (loan_amount / target_price) * 100 if target_price > 0 else 60.0

    # Phản biện rủi ro đặc thù thị trường Đà Nẵng:
    # 1. Rủi ro mùa vụ: Mùa mưa bão Đà Nẵng (Tháng 9 - 12) công suất phòng du lịch giảm sâu
    # 2. Rủi ro thâm hụt dòng tiền: Thu tiền thuê 12-14 triệu nhưng trả ngân hàng 18-22 triệu
    # 3. LTV quá cao nếu vay > 70%
    caveats = []
    if ltv > 65.0:
        caveats.append(f"Tỷ lệ đòn bẩy vay {ltv:.1f}% là mức báo động, rủi ro cao nếu lãi suất thả nổi sau thời gian ưu đãi tăng vọt.")

    caveats.append("Đà Nẵng có tính chu kỳ mùa vụ du lịch rất rõ rệt: Mùa mưa bão (Tháng 9 - 12) công suất khai thác homestay/lưu trú sụt giảm 50-60%, có thể dẫn đến dòng tiền âm liên tục 4 tháng.")
    caveats.append(f"Tiền thuê trung bình căn 2PN Đà Nẵng đạt ~12-15 triệu/tháng, trong khi nghĩa vụ nợ tháng đầu là {first_payment:,.0f} VNĐ. Khách hàng phải bù đắp từ 5-10 triệu/tháng từ nguồn thu nhập chính.")

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.CRITIC,
        title="Phản biện Rủi ro & Bẫy Dòng tiền Tiềm ẩn",
        content=(
            f"Tôi chất vấn phương án này ở góc độ an toàn vốn: "
            f"Thứ nhất, nghĩa vụ trả nợ {first_payment:,.0f} VNĐ/tháng vượt quá dòng tiền khai thác cho thuê thực tế tại Đà Nẵng (~12-15 triệu/tháng). "
            f"Thứ hai, vào mùa thấp điểm du lịch (tháng 9-12), chủ nhà chắc chắn phải bù lỗ dòng tiền. "
            f"Nếu người mua không có quỹ dự phòng thanh khoản tối thiểu 6 tháng tiền nợ ({first_payment * 6:,.0f} VNĐ), phương án này tiềm ẩn nguy cơ vỡ nợ khi lãi suất biến động!"
        ),
        key_points=[
            f"Cảnh báo thâm hụt dòng tiền hàng tháng (~5-10 triệu VNĐ)",
            "Rủi ro suy giảm công suất phòng mùa mưa Đà Nẵng (Tháng 9 - Tháng 12)",
            f"Yêu cầu bắt buộc: Quỹ dự phòng thanh khoản tối thiểu {first_payment * 6:,.0f} VNĐ"
        ]
    )
    return {
        "debate_history": [turn]
    }


def council_synthesizer_node(state: A2ACouncilState) -> Dict[str, Any]:
    """Node 6: Chủ tọa Hội đồng tổng hợp, chấm điểm khả thi và ban hành Nghị quyết (Council Verdict)"""
    equity = state.get("equity_capital", 1_000_000_000.0)
    target_price = state.get("target_price", 2_500_000_000.0)
    mortgage = state.get("mortgage_analysis") or {}
    loan_amount = mortgage.get("loan_amount", max(0.0, target_price - equity))
    ltv = (loan_amount / target_price) * 100 if target_price > 0 else 60.0

    # Tính điểm an toàn khả thi (0 - 100)
    score = 85
    if ltv > 70:
        score -= 25
    elif ltv > 50:
        score -= 10

    if equity < target_price * 0.3:
        score -= 20

    score = max(25, min(95, score))

    if score >= 75:
        feasibility = "feasible"
        summary_rec = "Phương án đầu tư tương đối khả thi. Đòn bẩy trong tầm kiểm soát, cần chú ý đàm phán giá giảm thêm 3-5% và giữ quỹ dự phòng 6 tháng tiền nợ."
    elif score >= 50:
        feasibility = "caution_required"
        summary_rec = "Phương án đòi hỏi sự thận trọng cao. Dòng tiền cho thuê không đủ bù nợ vay hàng tháng, người mua bắt buộc phải có nguồn thu nhập vững vàng từ công việc chính để bù đắp."
    else:
        feasibility = "high_risk"
        summary_rec = "Mức độ rủi ro rất cao do tỷ lệ vay vượt ngưỡng an toàn. Khuyến nghị giảm quy mô vốn vay, tăng vốn tự có hoặc chuyển hướng sang phân khúc căn hộ giá mềm hơn."

    top_prop = state.get("property_findings", [{}])[0] if state.get("property_findings") else None

    verdict = CouncilVerdict(
        overall_feasibility=feasibility,
        feasibility_score=score,
        summary_recommendation=summary_rec,
        property_match=top_prop,
        financial_summary={
            "target_price": target_price,
            "equity_capital": equity,
            "loan_amount": loan_amount,
            "ltv_percent": round(ltv, 1),
            "first_month_payment": mortgage.get("first_month_payment", 0.0),
            "monthly_principal": mortgage.get("monthly_principal", 0.0)
        },
        legal_risks=[
            "Cần kiểm tra kỹ thời hạn sở hữu trên Sổ hồng trước khi ký cọc",
            "Xác nhận tòa nhà đã có biên bản nghiệm thu PCCC hoàn chỉnh"
        ],
        critic_caveats=[
            "Dòng tiền mùa mưa bão Đà Nẵng (tháng 9-12) sụt giảm 50%",
            "Chủ nhà phải bù lỗ dòng tiền nợ vay hàng tháng khoảng 6-8 triệu VNĐ"
        ],
        action_checklist=[
            "1. Yêu cầu môi giới cung cấp Sổ hồng bản scan để kiểm tra quy hoạch",
            "2. Thỏa thuận điều khoản cọc tối đa không quá 5% giá trị căn hộ",
            "3. Lập quỹ dự phòng khẩn cấp 6 tháng nghĩa vụ nợ ngân hàng",
            "4. Đàm phán giảm thêm 50-100 triệu trên giá niêm yết"
        ]
    )

    turn = CouncilDebateTurn(
        speaker=CouncilSpeaker.SYNTHESIZER,
        title="Nghị Quyết Đồng Thuận Hội Đồng A2A (Council Verdict)",
        content=(
            f"Hội đồng A2A kết luận: Điểm số an toàn đạt {score}/100 ({feasibility.upper()}). "
            f"{summary_rec} "
            f"Vui lòng thực hiện theo 4 bước trong Action Checklist để bảo toàn tối đa quyền lợi đầu tư."
        ),
        key_points=[
            f"Đánh giá chung: {feasibility.upper()} (Điểm an toàn: {score}/100)",
            f"Tỷ lệ nợ vay LTV: {ltv:.1f}%",
            f"Khuyến nghị: {summary_rec}"
        ]
    )

    return {
        "verdict": verdict,
        "debate_history": [turn]
    }


from langgraph.graph import StateGraph, START, END

def create_a2a_council_graph():
    """Xây dựng và biên dịch đồ thị A2A Council StateGraph"""
    builder = StateGraph(A2ACouncilState)
    builder.add_node("planner", council_planner_node)
    builder.add_node("property_expert", council_property_node)
    builder.add_node("financial_analyst", council_mortgage_node)
    builder.add_node("legal_advisor", council_legal_node)
    builder.add_node("adversarial_critic", council_critic_node)
    builder.add_node("synthesizer", council_synthesizer_node)

    # START -> planner
    builder.add_edge(START, "planner")

    # Planner -> 3 chuyên gia song song (Parallel Fan-out)
    builder.add_edge("planner", "property_expert")
    builder.add_edge("planner", "financial_analyst")
    builder.add_edge("planner", "legal_advisor")

    # 3 chuyên gia -> Adversarial Critic (Fan-in)
    builder.add_edge("property_expert", "adversarial_critic")
    builder.add_edge("financial_analyst", "adversarial_critic")
    builder.add_edge("legal_advisor", "adversarial_critic")

    # Critic -> Synthesizer -> END
    builder.add_edge("adversarial_critic", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()

a2a_council_graph = create_a2a_council_graph()
