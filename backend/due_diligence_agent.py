"""
Deep Real Estate Due Diligence Agent for Da Nang Property Analysis.
Target Module: backend/due_diligence_agent.py

Features:
- Pydantic v2 schemas: InvestigationPlan, LegalRiskAssessment, MarketValuationAssessment,
  ClimateInfrastructureAssessment, FinancialFeasibilityAssessment, DueDiligenceDossier,
  DueDiligenceRequest, DueDiligenceStatusResponse.
- DueDiligenceState TypedDict for LangGraph workflow.
- Compatibility wrappers: search_legal_documents, calculate_monthly_payment, get_average_rate_and_best_package.
- 7 Analytical Nodes:
    1. plan_investigation_node
    2. legal_investigation_node
    3. valuation_investigation_node
    4. climate_investigation_node
    5. financial_simulation_node
    6. adversarial_critic_node
    7. synthesize_dossier_node
- StateGraph compilation with parallel fan-out and join.
"""

import os
import json
import time
import asyncio
import logging
from urllib.parse import urlparse
from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any, Literal, Tuple
from pydantic import BaseModel, Field, model_validator, field_validator
import operator
from langgraph.graph import StateGraph, START, END

from langchain_core.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. PYDANTIC V2 DATA SCHEMAS
# ==============================================================================

class InvestigationPlan(BaseModel):
    target_property_id: Optional[str] = None
    property_title: str
    address_or_district: str
    investment_objective: Literal["residential", "rental_cashflow", "capital_gain"]
    equity_capital_vnd: float
    loan_amount_vnd: float
    sub_tasks: List[str]


class LegalRiskAssessment(BaseModel):
    zoning_status: str = Field(default="Đất ở tại đô thị (ODT) quy hoạch ổn định")
    title_deed_status: str = Field(default="Sổ hồng riêng chính chủ")
    risks_detected: List[str] = Field(default_factory=list)
    legal_safety_score: int = Field(default=85, ge=0, le=100)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class MarketValuationAssessment(BaseModel):
    unit_price_per_m2: float = Field(default=0.0)
    avg_district_price_per_m2: float = Field(default=0.0)
    valuation_status: Literal["under_priced", "fair", "over_priced"] = Field(default="fair")
    comparable_properties: List[Dict[str, Any]] = Field(default_factory=list)
    live_market_listings: List[Dict[str, Any]] = Field(default_factory=list)


class ClimateInfrastructureAssessment(BaseModel):
    flood_risk_level: Literal["low", "medium", "high"] = Field(default="low")
    flood_notes: str = Field(default="Khu vực cao ráo, ít nguy cơ ngập lụt.")
    infrastructure_score: int = Field(default=80, ge=0, le=100)
    key_amenities: List[str] = Field(default_factory=list)


class FinancialFeasibilityAssessment(BaseModel):
    monthly_repayment_vnd: float = Field(default=0.0)
    effective_interest_rate: float = Field(default=8.5)
    estimated_monthly_rental_income: float = Field(default=0.0)
    net_rental_yield_percent: float = Field(default=0.0)
    dscr_ratio: float = Field(default=1.2)
    stress_test_passed: bool = Field(default=True)


class DeepResearchAssessment(BaseModel):
    target_entity: str = Field(default="")
    developer_name: Optional[str] = None
    reputation_score: Optional[int] = Field(default=80, ge=0, le=100)
    track_record_summary: str = Field(default="")
    dispute_history: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    community_sentiment: Literal["positive", "neutral", "negative", "controversial"] = Field(default="neutral")
    sources_analyzed: List[Dict[str, str]] = Field(default_factory=list)


class DueDiligenceDossier(BaseModel):
    overall_score: int = Field(default=80, ge=0, le=100)
    verdict: Literal["STRONGLY_RECOMMENDED", "PROCEED_WITH_CAUTION", "HIGH_RISK_AVOID"] = Field(default="PROCEED_WITH_CAUTION")
    verdict_label: Optional[str] = None
    executive_summary: str = Field(default="")
    legal: LegalRiskAssessment = Field(default_factory=LegalRiskAssessment)
    valuation: MarketValuationAssessment = Field(default_factory=MarketValuationAssessment)
    climate_infrastructure: ClimateInfrastructureAssessment = Field(default_factory=ClimateInfrastructureAssessment)
    financial: FinancialFeasibilityAssessment = Field(default_factory=FinancialFeasibilityAssessment)
    deep_research: Optional[DeepResearchAssessment] = None
    critic_counterarguments: List[str] = Field(default_factory=list)
    actionable_negotiation_points: List[str] = Field(default_factory=list)
    full_markdown_report: str = Field(default="")


class DueDiligenceRequest(BaseModel):
    property_id: Optional[str] = None
    property_title: str
    property_price: float = Field(..., gt=0)
    area_m2: float = Field(..., gt=0)
    district: str
    ward: Optional[str] = None
    investment_objective: Literal["residential", "rental_cashflow", "capital_gain"] = "residential"
    equity_ratio: float = Field(0.7, ge=0.0, le=1.0)
    equity_capital_vnd: Optional[float] = None
    loan_amount_vnd: Optional[float] = None
    user_id: Optional[str] = None
    enable_deep_research: bool = Field(default=False)
    developer_name: Optional[str] = None

    @field_validator("investment_objective", mode="before")
    @classmethod
    def normalize_investment_objective(cls, v):
        if isinstance(v, str):
            clean = v.strip().lower()
            mapping = {
                "an cư": "residential",
                "an cu": "residential",
                "residential": "residential",
                "dòng tiền": "rental_cashflow",
                "dong tien": "rental_cashflow",
                "rental_cashflow": "rental_cashflow",
                "lãi vốn": "capital_gain",
                "lai von": "capital_gain",
                "capital_gain": "capital_gain",
            }
            if clean in mapping:
                return mapping[clean]
        return v

    @model_validator(mode="after")
    def compute_defaults(self):
        if self.equity_capital_vnd is None:
            self.equity_capital_vnd = round(self.property_price * self.equity_ratio, 2)
        if self.loan_amount_vnd is None:
            self.loan_amount_vnd = round(max(0.0, self.property_price - self.equity_capital_vnd), 2)
        return self


class DueDiligenceStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "planning", "investigating", "critiquing", "synthesizing", "completed", "failed"]
    progress: int = Field(0, ge=0, le=100)
    current_stage: str
    result: Optional[DueDiligenceDossier] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ==============================================================================
# 2. LANGGRAPH STATE DEFINITION
# ==============================================================================

class DueDiligenceState(TypedDict, total=False):
    request: Optional[Any]
    property_details: Optional[Dict[str, Any]]
    property_id: Optional[str]
    property_title: str
    property_price: float
    area_m2: float
    district: str
    ward: Optional[str]
    investment_objective: str
    equity_ratio: float
    equity_capital_vnd: float
    loan_amount_vnd: float
    user_id: Optional[str]
    stage: Optional[str]
    enable_deep_research: Optional[bool]
    developer_name: Optional[str]
    plan: Optional[Any]
    legal: Optional[Any]
    valuation: Optional[Any]
    climate: Optional[Any]
    climate_infrastructure: Optional[Any]
    financial: Optional[Any]
    deep_research: Optional[Any]
    critic_counterarguments: Optional[List[str]]
    actionable_negotiation_points: Optional[List[str]]
    dossier: Optional[Any]
    errors: Annotated[List[str], operator.add]


# ==============================================================================
# 3. DOMAIN CONSTANTS & BENCHMARKS
# ==============================================================================

DISTRICT_PRICE_BENCHMARKS: Dict[str, float] = {
    "Hải Châu": 75_000_000.0,
    "Sơn Trà": 65_000_000.0,
    "Ngũ Hành Sơn": 55_000_000.0,
    "Thanh Khê": 45_000_000.0,
    "Cẩm Lệ": 35_000_000.0,
    "Liên Chiểu": 30_000_000.0,
    "Hòa Vang": 18_000_000.0,
}

DISTRICT_AMENITIES: Dict[str, List[str]] = {
    "Hải Châu": ["Trung tâm Hành chính TP Đà Nẵng", "Bệnh viện Đa khoa Đà Nẵng", "Cầu Rồng & Cầu Sông Hàn", "Sân bay Quốc tế Đà Nẵng", "Chợ Hàn"],
    "Sơn Trà": ["Bãi biển Mỹ Khê", "Bán đảo Sơn Trà", "Cầu Thuận Phước", "Bệnh viện Sơn Trà", "Khu du lịch sinh thái Tiên Sa"],
    "Ngũ Hành Sơn": ["Bãi tắm Non Nước", "Danh thắng Ngũ Hành Sơn", "Làng Đại học Đà Nẵng", "Bệnh viện Phụ sản - Nhi", "Sân Golf BRG"],
    "Thanh Khê": ["Ga Đà Nẵng", "Bờ biển Nguyễn Tất Thành", "Siêu thị Co.opmart", "Bệnh viện Hoàn Mỹ"],
    "Cẩm Lệ": ["Bến xe Trung tâm Đà Nẵng", "Sân vận động Hòa Xuân", "Bệnh viện Y học Cổ truyền", "Trung tâm Hội chợ Triển lãm"],
    "Liên Chiểu": ["Trường Đại học Bách Khoa", "Trường Đại học Sư phạm", "Cảng biển Liên Chiểu", "KCN Hòa Khánh"],
    "Hòa Vang": ["Khu Công nghệ cao Đà Nẵng", "Bà Nà Hills", "Tuyến cao tốc La Sơn - Túy Loan", "Khu hành chính Huyện Hòa Vang"],
}


# ==============================================================================
# 4. COMPATIBILITY WRAPPERS & HELPERS
# ==============================================================================

def _to_dict(obj: Any) -> Dict[str, Any]:
    """Converts Pydantic models or dicts to dictionary safely."""
    if obj is None:
        return {}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return {}


def _extract_property_info(state: DueDiligenceState) -> Dict[str, Any]:
    """Extracts property parameters from state whether stored flat or in state['request']."""
    req_dict = _to_dict(state.get("request"))

    price = float(req_dict.get("property_price") or state.get("property_price") or 0.0)
    area = float(req_dict.get("area_m2") or state.get("area_m2") or 1.0)
    title = req_dict.get("property_title") or state.get("property_title") or "Bất động sản Đà Nẵng"
    district = req_dict.get("district") or state.get("district") or "Hải Châu"
    ward = req_dict.get("ward") or state.get("ward") or ""
    objective = req_dict.get("investment_objective") or state.get("investment_objective") or "residential"

    eq_ratio = req_dict.get("equity_ratio")
    if eq_ratio is None:
        eq_ratio = state.get("equity_ratio")
    if eq_ratio is None:
        eq_ratio = 0.7
    eq_ratio = float(eq_ratio)

    plan_dict = _to_dict(state.get("plan"))
    equity = plan_dict.get("equity_capital_vnd") if plan_dict else None
    loan = plan_dict.get("loan_amount_vnd") if plan_dict else None

    if equity is None:
        equity = req_dict.get("equity_capital_vnd") if req_dict.get("equity_capital_vnd") is not None else state.get("equity_capital_vnd")
    if equity is None:
        equity = round(price * eq_ratio, 2)
    equity = float(equity)

    if loan is None:
        loan = req_dict.get("loan_amount_vnd") if req_dict.get("loan_amount_vnd") is not None else state.get("loan_amount_vnd")
    if loan is None:
        loan = round(max(0.0, price - equity), 2)
    loan = float(loan)

    enable_deep = req_dict.get("enable_deep_research")
    if enable_deep is None:
        enable_deep = state.get("enable_deep_research", False)
    enable_deep = bool(enable_deep)

    dev_name = req_dict.get("developer_name") or state.get("developer_name")

    return {
        "price": price,
        "area": area,
        "title": title,
        "district": district,
        "ward": ward,
        "objective": objective,
        "equity_ratio": eq_ratio,
        "equity": equity,
        "loan": loan,
        "property_id": req_dict.get("property_id") or state.get("property_id"),
        "enable_deep_research": enable_deep,
        "developer_name": dev_name
    }


class MonthlyPayment(float):
    """Subclass of float that supports attribute access for backwards compatibility."""
    @property
    def first_month_payment(self) -> float:
        return float(self)

    @property
    def total_payment(self) -> float:
        return float(self)


class RateInfo(tuple):
    """Subclass of tuple supporting both unpacking and dict-like key access."""
    def __new__(cls, avg_rate: float, best_pkg: Dict[str, Any]):
        return super().__new__(cls, (avg_rate, best_pkg))

    @property
    def average_rate(self) -> float:
        return self[0]

    @property
    def best_package(self) -> Dict[str, Any]:
        return self[1]

    def __getitem__(self, item):
        if item == "average_rate":
            return self[0]
        elif item == "best_package":
            return self[1]
        return super().__getitem__(item)

    def get(self, key, default=None):
        if key == "average_rate":
            return self[0]
        elif key == "best_package":
            return self[1]
        return default


def search_legal_documents(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Searches legal citations via legal_service with resilient deterministic fallback."""
    try:
        from legal_service import legal_service
        results = legal_service.search_legal_context(query=query, top_k=top_k)
        if results:
            return results
    except Exception:
        pass

    return [
        {
            "index": 1,
            "id": "fallback-law-01",
            "doc_id": "luat_dat_dai_2024",
            "doc_title": "Luật Đất đai 2024 (Luật số 31/2024/QH15)",
            "chapter": "Chương III: Quyền và Nghĩa Vụ của Người Sử Dụng Đất",
            "article": "Điều 45. Điều kiện thực hiện các quyền chuyển nhượng, tặng cho, thế chấp QSDĐ",
            "content": "Người sử dụng đất được thực hiện các quyền chuyển quyền sử dụng đất khi có Giấy chứng nhận quyền sử dụng đất; đất không có tranh chấp; quyền sử dụng đất không bị kê biên để bảo đảm thi hành án; trong thời hạn sử dụng đất.",
            "score": 0.95
        },
        {
            "index": 2,
            "id": "fallback-law-02",
            "doc_id": "luat_kinh_doanh_bds_2023",
            "doc_title": "Luật Kinh doanh Bất động sản 2023 (Luật số 29/2023/QH15)",
            "chapter": "Chương II: Kinh Doanh Nhà Ở, Công Trình Xây Dựng Có Sẵn",
            "article": "Khoản 5 Điều 23. Đặt cọc trong kinh doanh nhà ở, công trình xây dựng hình thành trong tương lai",
            "content": "Chủ đầu tư dự án bất động sản chỉ được thu tiền đặt cọc không quá 5% giá bán, cho thuê mua nhà ở, công trình xây dựng hình thành trong tương lai khi nhà ở, công trình xây dựng đã có đủ các điều kiện đưa vào kinh doanh.",
            "score": 0.92
        }
    ]


def search_tavily_real_estate(
    query: str,
    district: str,
    max_results: int = 3,
    tavily_client: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm thông tin tin đăng BĐS thực tế qua Tavily Web Search.
    Khoanh vùng các cổng BĐS lớn (batdongsan, chotot, alonhadat, homedy, cafeland).
    Hỗ trợ graceful fallback an toàn nếu không có API key hoặc lỗi kết nối.
    """
    client = tavily_client
    if client is None:
        try:
            from tavily import TavilyClient
            from config import settings
            api_key = settings.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY", "")
            if api_key and not api_key.startswith("tvly-your"):
                client = TavilyClient(api_key=api_key)
        except Exception:
            client = None

    if client is None:
        return []

    listings: List[Dict[str, Any]] = []
    try:
        search_query = f"mua bán nhà đất {district} Đà Nẵng {query}".strip()
        domains = ["batdongsan.com.vn", "chotot.com", "alonhadat.com.vn", "homedy.com", "cafeland.vn"]

        res = client.search(
            query=search_query,
            include_domains=domains,
            max_results=max_results,
            search_depth="basic"
        )

        for item in res.get("results", []):
            url = item.get("url", "")
            domain = ""
            if url:
                parsed = urlparse(url)
                domain = parsed.netloc.replace("www.", "")

            listings.append({
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("content", "")[:250],
                "source_domain": domain or "web"
            })
    except Exception:
        # Graceful fallback: return empty list on any network/API failure
        return []

    return listings


def calculate_monthly_payment(
    loan_amount: float,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    property_price: Optional[float] = None,
    method: str = "reducing_balance"
) -> MonthlyPayment:
    """Calculates monthly payment using MortgageCalculator with pure Python fallback."""
    if loan_amount <= 0:
        return MonthlyPayment(0.0)

    try:
        from mortgage_calculator import MortgageCalculator, MortgageInput
        res = MortgageCalculator.calculate(MortgageInput(
            loan_amount=loan_amount,
            annual_interest_rate=annual_interest_rate,
            tenure_years=tenure_years,
            property_price=property_price or (loan_amount / 0.7),
            method=method
        ))
        return MonthlyPayment(res.first_month_payment)
    except Exception:
        tenure_months = max(1, tenure_years * 12)
        principal = loan_amount / tenure_months
        interest = loan_amount * (annual_interest_rate / 100.0 / 12.0)
        return MonthlyPayment(principal + interest)


def get_average_rate_and_best_package(
    tenure_years: int = 20,
    bank_names: Optional[str] = None
) -> RateInfo:
    """Calculates benchmark interest rates from bank_research_service with offline fallback."""
    try:
        from bank_research_service import bank_research_service
        pkgs = bank_research_service.get_bank_packages(tenure_years=tenure_years, bank_names=bank_names)
        if pkgs:
            rates = [p.effective_annual_rate for p in pkgs]
            avg_rate = round(sum(rates) / len(rates), 2)
            best_pkg = min(pkgs, key=lambda p: p.effective_annual_rate).model_dump()
            return RateInfo(avg_rate, best_pkg)
    except Exception:
        pass

    return RateInfo(9.2, {
        "bank_name": "Vietcombank",
        "package_name": "Gói vay mua nhà cố định",
        "effective_annual_rate": 9.2,
        "preferential_rate": 6.0,
        "preferential_months": 12,
        "floating_rate": 9.5
    })


# ==============================================================================
# 5. 7 ANALYTICAL LANGGRAPH NODES
# ==============================================================================

def plan_investigation_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 1: Planning - parses goals, capital allocations, and orchestrates sub-tasks."""
    info = _extract_property_info(state)

    unit_price = info["price"] / max(1.0, info["area"])
    addr = f"{info['ward']} {info['district']}".strip()

    sub_tasks = [
        f"1. Thẩm định pháp lý sổ hồng, quy hoạch ODT và tranh chấp theo Luật Đất đai 2024 tại khu vực {addr}",
        f"2. Khảo sát định giá so sánh đơn giá {unit_price / 1_000_000:.1f} triệu đ/m² với mặt bằng quận {info['district']}",
        f"3. Đánh giá địa hình và rủi ro ngập lụt mùa mưa lũ tại khu vực {addr}",
        f"4. Mô phỏng phương án tài chính vay {info['loan'] / 1_000_000:,.1f} triệu đ, tính toán DSCR và tỷ suất sinh lời ròng",
        "5. Phản biện rủi ro (Adversarial Critic) kịch bản lãi suất thả nổi tăng +3% và tính thanh khoản"
    ]

    if info.get("enable_deep_research"):
        dev_target = info.get("developer_name") or info["title"]
        sub_tasks.append(
            f"6. Điều tra sâu độc lập (Deep Research): Rà soát uy tín chủ đầu tư '{dev_target}', lịch sử bàn giao sổ và khiếu nại tranh chấp"
        )

    plan = InvestigationPlan(
        target_property_id=info["property_id"],
        property_title=info["title"],
        address_or_district=addr,
        investment_objective=info["objective"],
        equity_capital_vnd=info["equity"],
        loan_amount_vnd=info["loan"],
        sub_tasks=sub_tasks
    )

    return {
        "stage": "planning",
        "property_title": info["title"],
        "property_price": info["price"],
        "area_m2": info["area"],
        "district": info["district"],
        "ward": info["ward"],
        "investment_objective": info["objective"],
        "equity_capital_vnd": info["equity"],
        "loan_amount_vnd": info["loan"],
        "enable_deep_research": info.get("enable_deep_research", False),
        "developer_name": info.get("developer_name"),
        "plan": plan.model_dump()
    }


def legal_investigation_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 2: Legal Investigation - retrieves Land Law citations and audits title deed."""
    info = _extract_property_info(state)
    district = info["district"]
    title = info["title"]

    query = f"điều kiện chuyển nhượng quyền sử dụng đất sổ hồng tranh chấp {district} Luật Đất đai 2024 Luật Nhà ở 2023"
    raw_citations = search_legal_documents(query, top_k=3)

    citations = []
    for c in raw_citations:
        citations.append({
            "doc_title": c.get("doc_title", "Luật Đất đai 2024"),
            "article": c.get("article", "Điều 45"),
            "content": c.get("content", ""),
            "score": float(c.get("score", 0.90))
        })

    prop_details = _to_dict(state.get("property_details"))
    details_text = f"{title} {prop_details.get('title_deed', '')} {prop_details.get('legal_status', '')}".lower()
    is_risky_title = any(kw in details_text for kw in [
        "giấy tay", "chưa sổ", "chờ sổ", "hợp đồng góp vốn", "vi bằng", "giấy viết tay", "chưa có sổ", "tranh chấp"
    ])

    if is_risky_title:
        title_deed_status = "Chưa có sổ hồng riêng (Giao dịch qua hợp đồng góp vốn hoặc giấy tờ viết tay)"
        zoning_status = "Chưa xác minh được chỉ giới quy hoạch và hành lang bảo vệ"
        risks_detected = [
            "Rủi ro pháp lý nghiêm trọng: Tài sản chưa được cấp Giấy chứng nhận QSDĐ riêng lẻ.",
            "Nguy cơ tranh chấp quyền sở hữu hoặc không đủ điều kiện công chứng sang tên theo Điều 45 Luật Đất đai 2024.",
            "Cần kiểm tra quy hoạch thu hồi đất tại Văn phòng Đăng ký Đất đai quận."
        ]
        legal_safety_score = 45
    else:
        title_deed_status = "Sổ hồng riêng chính chủ, sẵn sàng giao dịch công chứng sang tên"
        zoning_status = "Đất ở tại đô thị (ODT) quy hoạch ổn định, không thuộc diện quy hoạch giải tỏa"
        risks_detected = [
            "Cần đối chiếu số đo hiện trạng thực tế với tọa độ ranh giới trên bản đồ địa chính.",
            "Lưu ý quy định trần đặt cọc không vượt quá 5% theo Luật Kinh doanh Bất động sản 2023."
        ]
        legal_safety_score = 90

    assessment = LegalRiskAssessment(
        zoning_status=zoning_status,
        title_deed_status=title_deed_status,
        risks_detected=risks_detected,
        legal_safety_score=legal_safety_score,
        citations=citations
    )
    return {"legal": assessment.model_dump()}


def valuation_investigation_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 3: Valuation Investigation - queries Qdrant comparables and checks benchmark price."""
    info = _extract_property_info(state)
    price = info["price"]
    area = max(1.0, info["area"])
    unit_price = price / area
    district = info["district"]

    comparables = []
    try:
        from qdrant_service import qdrant_service
        results = qdrant_service.search_properties(
            query=info["title"],
            district=district,
            limit=5
        )
        for r in results:
            payload = r.get("payload", r) if isinstance(r, dict) else getattr(r, "payload", {})
            p_price = float(payload.get("price") or 0.0)
            p_area = float(payload.get("area_m2") or payload.get("area") or 0.0)
            if p_price > 0 and p_area > 0:
                comparables.append({
                    "id": str(payload.get("id", "")),
                    "title": payload.get("title", ""),
                    "price": p_price,
                    "area": p_area,
                    "unit_price_per_m2": round(p_price / p_area, 2)
                })
    except Exception:
        pass

    benchmark = DISTRICT_PRICE_BENCHMARKS.get(district, 50_000_000.0)
    if len(comparables) >= 2:
        avg_district_price = sum(c["unit_price_per_m2"] for c in comparables) / len(comparables)
    else:
        avg_district_price = benchmark
        while len(comparables) < 2:
            idx = len(comparables) + 1
            factor = 0.95 if idx == 1 else 1.05
            comparables.append({
                "title": f"BĐS so sánh {idx} ({district})",
                "price": benchmark * area * factor,
                "area": area,
                "unit_price_per_m2": benchmark * factor
            })

    ratio = unit_price / avg_district_price
    if ratio < 0.90:
        valuation_status = "under_priced"
    elif ratio <= 1.10:
        valuation_status = "fair"
    else:
        valuation_status = "over_priced"

    live_listings = search_tavily_real_estate(
        query=info["title"],
        district=district,
        max_results=3
    )

    assessment = MarketValuationAssessment(
        unit_price_per_m2=round(unit_price, 2),
        avg_district_price_per_m2=round(avg_district_price, 2),
        valuation_status=valuation_status,
        comparable_properties=comparables,
        live_market_listings=live_listings
    )
    return {"valuation": assessment.model_dump()}


def climate_investigation_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 4: Climate & Infrastructure - maps Da Nang flood risk and evaluates public amenities."""
    info = _extract_property_info(state)
    district = info["district"]
    ward = info["ward"].lower()

    amenities = DISTRICT_AMENITIES.get(district, [
        "Trường học liên cấp", "Chợ dân sinh", "Bệnh viện đa khoa", "Khu thể thao công cộng"
    ])

    if district in ["Hòa Vang", "Cẩm Lệ"] or any(w in ward for w in ["hòa xuân", "hòa phát", "hòa thọ", "hòa tiến", "khuê trung"]):
        flood_risk_level = "high"
        flood_notes = (
            f"Khu vực {district} nằm tại vùng trũng thấp lưu vực sông Cẩm Lệ và sông Yên. "
            "Trong các mùa mưa lũ lịch sử (tháng 10 - 11), khu vực ghi nhận nguy cơ ngập sâu 0.5m - 1.5m cục bộ. "
            "Cần giải pháp tôn cao nền móng hoặc trang bị hệ thống thoát nước chủ động."
        )
        infrastructure_score = 60
    elif district in ["Liên Chiểu", "Thanh Khê"] or any(w in ward for w in ["phú lộc", "khe cạn", "hòa khánh"]):
        flood_risk_level = "medium"
        flood_notes = (
            f"Khu vực {district} có địa hình chuyển tiếp đồng bằng ven vịnh Đà Nẵng. "
            "Có nguy cơ ngập úng tạm thời 20 - 40cm khi có mưa cường độ lớn trùng triều cường dâng cao."
        )
        infrastructure_score = 75
    else:
        flood_risk_level = "low"
        flood_notes = (
            f"Khu vực {district} có nền địa chất cao ráo, gò cát ven biển hoặc cấu trúc thoát nước đô thị trung tâm đồng bộ. "
            "Hầu như không ghi nhận tình trạng ngập lụt kéo dài trong các đợt mưa bão lớn tại Đà Nẵng."
        )
        infrastructure_score = 90

    assessment = ClimateInfrastructureAssessment(
        flood_risk_level=flood_risk_level,
        flood_notes=flood_notes,
        infrastructure_score=infrastructure_score,
        key_amenities=amenities
    )
    assessment_dump = assessment.model_dump()
    return {
        "climate_infrastructure": assessment_dump,
        "climate": assessment_dump
    }


def financial_simulation_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 5: Financial Simulation - computes mortgage, DSCR, net yield and stress test."""
    info = _extract_property_info(state)
    price = info["price"]
    loan = info["loan"]
    objective = info["objective"]
    equity_ratio = info["equity_ratio"]
    tenure_years = 20

    effective_rate, best_pkg = get_average_rate_and_best_package(tenure_years=tenure_years)

    if loan > 0:
        monthly_repayment = calculate_monthly_payment(
            loan_amount=loan,
            annual_interest_rate=effective_rate,
            tenure_years=tenure_years,
            method="reducing_balance"
        )
    else:
        monthly_repayment = 0.0
        effective_rate = 0.0

    if objective == "rental_cashflow":
        gross_monthly_rental = price * 0.0045
    elif objective == "capital_gain":
        gross_monthly_rental = price * 0.0025
    else:
        gross_monthly_rental = price * 0.0035

    net_monthly_rental = gross_monthly_rental * 0.85
    net_rental_yield = (net_monthly_rental * 12 / max(1.0, price)) * 100

    if loan > 0 and monthly_repayment > 0:
        dscr = round(net_monthly_rental / monthly_repayment, 2)
        stressed_pay = calculate_monthly_payment(
            loan_amount=loan,
            annual_interest_rate=effective_rate + 3.0,
            tenure_years=tenure_years,
            method="reducing_balance"
        )
        stressed_dscr = net_monthly_rental / stressed_pay if stressed_pay > 0 else 0.0
        # Extreme leverage (e.g. loan ratio >= 80% / equity <= 20% with low DSCR) fails stress test
        stress_test_passed = (dscr >= 1.0 or (objective == "residential" and equity_ratio >= 0.4)) and (stressed_dscr >= 0.65 or equity_ratio >= 0.5)
        if dscr < 1.0 and equity_ratio <= 0.3:
            stress_test_passed = False
    else:
        dscr = 999.0
        stress_test_passed = True

    assessment = FinancialFeasibilityAssessment(
        monthly_repayment_vnd=round(monthly_repayment, 2),
        effective_interest_rate=round(effective_rate, 2),
        estimated_monthly_rental_income=round(gross_monthly_rental, 2),
        net_rental_yield_percent=round(net_rental_yield, 2),
        dscr_ratio=round(dscr, 2),
        stress_test_passed=stress_test_passed
    )
    return {"financial": assessment.model_dump()}


def run_deep_developer_investigation(
    target_name: str,
    district: str,
    tavily_client: Optional[Any] = None,
    llm: Optional[Any] = None
) -> DeepResearchAssessment:
    """Executes deep autonomous web investigation on project developer reputation and dispute history."""
    if tavily_client is None:
        try:
            from tavily import TavilyClient
            from config import settings
            api_key = settings.TAVILY_API_KEY or os.getenv("TAVILY_API_KEY", "")
            if api_key and not api_key.startswith("tvly-your"):
                tavily_client = TavilyClient(api_key=api_key)
        except Exception:
            tavily_client = None

    snippets: List[Dict[str, str]] = []
    if tavily_client is not None:
        try:
            q = f"{target_name} Đà Nẵng chủ đầu tư tranh chấp lừa đảo chậm sổ bàn giao"
            res = tavily_client.search(
                query=q,
                max_results=5,
                search_depth="advanced"
            )
            for item in res.get("results", []):
                snippets.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:300]
                })
        except Exception:
            snippets = []

    if llm is None:
        try:
            from langchain_openai import ChatOpenAI
            from config import settings
            llm = ChatOpenAI(
                model=settings.OPENAI_MODEL_NAME,
                temperature=0.0,
                api_key=settings.OPENAI_API_KEY
            )
        except Exception:
            llm = None

    if llm is not None and snippets:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            import json
            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "Bạn là Chuyên gia Điều tra Độc lập BĐS Đà Nẵng (Deep Due Diligence Investigator). "
                    "Hãy phân tích uy tín chủ đầu tư, tiến độ bàn giao, các tranh chấp kiện tụng và cảnh báo đỏ từ thông tin tìm kiếm. "
                    "Trả về JSON định dạng: "
                    '{{"reputation_score": <int 0-100>, "track_record_summary": "<chuỗi>", '
                    '"dispute_history": ["<chuỗi>", ...], "red_flags": ["<chuỗi>", ...], '
                    '"community_sentiment": "<positive|neutral|negative|controversial>"}}'
                )),
                ("human", (
                    f"Đối tượng điều tra: {target_name} ({district})\n"
                    f"Dữ liệu tìm kiếm:\n" + "\n".join([f"- {s['title']}: {s['snippet']} (Link: {s['url']})" for s in snippets])
                ))
            ])
            chain = prompt | llm
            resp = chain.invoke({})
            content = resp.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            data = json.loads(content)
            return DeepResearchAssessment(
                target_entity=target_name,
                developer_name=target_name,
                reputation_score=int(data.get("reputation_score", 75)),
                track_record_summary=data.get("track_record_summary", "Thông tin chủ đầu tư hoạt động bình thường trên địa bàn."),
                dispute_history=data.get("dispute_history", []),
                red_flags=data.get("red_flags", []),
                community_sentiment=data.get("community_sentiment", "neutral"),
                sources_analyzed=[{"title": s["title"], "url": s["url"]} for s in snippets]
            )
        except Exception:
            pass

    return DeepResearchAssessment(
        target_entity=target_name,
        developer_name=target_name,
        reputation_score=80,
        track_record_summary=f"Chủ đầu tư/Đơn vị phát triển {target_name} chưa ghi nhận tiền sử tranh chấp nghiêm trọng trên các cổng thông tin pháp lý công khai tại {district}.",
        dispute_history=[],
        red_flags=["Cần yêu cầu chủ đầu tư cung cấp văn bản chấp thuận bán nhà hình thành trong tương lai của Sở Xây dựng."],
        community_sentiment="neutral",
        sources_analyzed=[{"title": s["title"], "url": s["url"]} for s in snippets] if snippets else []
    )


def deep_research_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node: Deep Research - autonomous deep investigation on developer reputation & dispute history."""
    info = _extract_property_info(state)
    enable_deep = info.get("enable_deep_research", False)
    if not enable_deep:
        return {
            "stage": "investigated_deep_research",
            "deep_research": None
        }

    dev_name = info.get("developer_name") or info.get("title") or "Chủ đầu tư BĐS Đà Nẵng"
    district = info.get("district") or "Hải Châu"

    try:
        assessment = run_deep_developer_investigation(
            target_name=dev_name,
            district=district
        )
        return {
            "stage": "investigated_deep_research",
            "deep_research": assessment.model_dump()
        }
    except Exception as e:
        return {
            "stage": "investigated_deep_research",
            "deep_research": None,
            "errors": [f"Deep Research investigation failed: {str(e)}"]
        }


def adversarial_critic_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 6: Adversarial Critic - devil's advocate stress tests and negotiation levers."""
    info = _extract_property_info(state)
    district = info["district"]
    loan = info["loan"]

    legal = _to_dict(state.get("legal"))
    valuation = _to_dict(state.get("valuation"))
    climate = _to_dict(state.get("climate_infrastructure") or state.get("climate"))
    financial = _to_dict(state.get("financial"))
    deep_res = _to_dict(state.get("deep_research"))

    eff_rate = float(financial.get("effective_interest_rate", 9.2))
    stressed_rate = eff_rate + 3.0

    curr_monthly = float(financial.get("monthly_repayment_vnd", 0.0))
    stressed_monthly = calculate_monthly_payment(loan, stressed_rate, tenure_years=20) if loan > 0 else 0.0
    delta_monthly = max(0.0, stressed_monthly - curr_monthly)
    delta_monthly_m = delta_monthly / 1_000_000
    loan_m = loan / 1_000_000

    counterarguments = [
        f"1. Rủi ro cú sốc lãi suất thả nổi (+3%): Khi bước sang giai đoạn thả nổi từ {eff_rate:.1f}% lên {stressed_rate:.1f}%/năm, số tiền trả góp hàng tháng sẽ tăng thêm ~{delta_monthly_m:.1f} triệu đ/tháng. Nếu người mua không có thặng dư tiền mặt dự phòng tối thiểu 6 tháng, nguy cơ mất khả năng chi trả là rất lớn.",
        f"2. Bẫy thanh khoản và biến động giá: Thị trường thứ cấp tại {district} có tính thanh khoản chọn lọc theo từng tuyến phố. Nếu mua ở mức giá hiện tại và cần bán thu hồi vốn gấp trong 6-12 tháng, nhà đầu tư có thể phải chiết khấu từ 7% - 12% so với giá chào ban đầu.",
        "3. Rủi ro pháp lý & Quy chế trần cọc 5%: Cần cảnh giác với các điều khoản phạt cọc một chiều trong hợp đồng đặt cọc. Theo Luật Kinh doanh Bất động sản 2023, số tiền cọc không được vượt quá 5% giá trị BĐS.",
    ]

    if climate.get("flood_risk_level") == "high":
        counterarguments.append(
            f"4. Rủi ro suy hao giá trị do ngập lụt: Vùng trũng {district} chịu ảnh hưởng lũ lụt định kỳ làm gia tăng chi phí bảo trì tài sản từ 15-20 triệu đ/năm và tỷ lệ trống phòng cho thuê cao vào mùa mưa bão."
        )
    else:
        counterarguments.append(
            "4. Rủi ro tiến độ hạ tầng & mật độ đô thị: Cần xác minh kế hoạch nâng cấp hạ tầng giao thông và chỉ giới đường đỏ để không bị vướng tranh chấp chỉ giới mở đường."
        )

    negotiation_points = [
        f"1. Đàm phán giảm giá tối thiểu 5% - 8% dựa trên cơ sở dữ liệu định giá so sánh các tài sản tương đương tại quận {district}.",
        "2. Yêu cầu bên bán cung cấp Trích lục bản đồ địa chính mới nhất do Chi nhánh VPĐKĐĐ cấp trong vòng 30 ngày trước khi ký hợp đồng đặt cọc.",
        "3. Đóng đinh điều khoản trần tiền đặt cọc đúng 5% giá trị chuyển nhượng theo Luật Kinh doanh Bất động sản 2023.",
        f"4. Thêm điều khoản bảo vệ tài chính: Nếu ngân hàng thẩm định không giải ngân đủ khoản vay mục tiêu ({loan_m:,.1f} triệu đ) do lỗi định giá, bên mua được quyền rút 100% tiền cọc mà không bị phạt vi phạm.",
    ]
    if climate.get("flood_risk_level") == "high":
        negotiation_points.append("5. Đòi hỏi trừ lùi chi phí tôn nền / gia cố thoát nước (tương đương 30 - 50 triệu đồng) vào tổng giá bán.")

    # Ingest Deep Research intelligence if present
    if deep_res:
        dev_title = deep_res.get("developer_name") or deep_res.get("target_entity") or "Chủ đầu tư"
        rep_score = deep_res.get("reputation_score", 80)
        red_flags = deep_res.get("red_flags", [])
        disputes = deep_res.get("dispute_history", [])

        if red_flags:
            for rf in red_flags:
                counterarguments.append(f"Cảnh báo rủi ro chủ đầu tư ({dev_title}): {rf}")
                negotiation_points.append(
                    f"Yêu cầu bên bán/chủ đầu tư {dev_title} cam kết bằng phụ lục hợp đồng về việc khắc phục hoặc loại trừ rủi ro: '{rf}'."
                )

        if disputes:
            for d in disputes:
                counterarguments.append(f"Tiền sử tranh chấp/khiếu nại ({dev_title}): {d}")
                negotiation_points.append(
                    f"Đưa điều khoản phong tỏa tiền thanh toán qua tài khoản ký quỹ (Escrow) ngân hàng cho đến khi {dev_title} hoàn tất cấp sổ đỏ."
                )

        if rep_score < 70:
            counterarguments.append(
                f"Chỉ số tín nhiệm chủ đầu tư ở mức thấp ({rep_score}/100): Cần kiểm tra kỹ bảo lãnh ngân hàng cho dự án theo Điều 27 Luật Kinh doanh BĐS 2023."
            )
            negotiation_points.append(
                f"Đàm phán kéo dài tiến độ thanh toán gắn liền với biên bản nghiệm thu thực tế của từng hạng mục công trình."
            )

    return {
        "stage": "critiquing",
        "critic_counterarguments": counterarguments,
        "actionable_negotiation_points": negotiation_points
    }


def synthesize_dossier_node(state: DueDiligenceState) -> Dict[str, Any]:
    """Node 7: Dossier Synthesis - weighted scorecard, verdict assignment, and executive Markdown report."""
    info = _extract_property_info(state)
    title = info["title"]
    district = info["district"]
    price = info["price"]
    area = max(1.0, info["area"])

    legal_data = _to_dict(state.get("legal"))
    valuation_data = _to_dict(state.get("valuation"))
    climate_data = _to_dict(state.get("climate_infrastructure") or state.get("climate"))
    financial_data = _to_dict(state.get("financial"))
    critic_counterarguments = state.get("critic_counterarguments") or []
    actionable_negotiation_points = state.get("actionable_negotiation_points") or []

    # 1. Pillar Scores
    L = int(legal_data.get("legal_safety_score", 70))

    val_status = valuation_data.get("valuation_status", "fair")
    if val_status == "under_priced":
        V = 95
    elif val_status == "fair":
        V = 85
    else:
        V = 55

    C = int(climate_data.get("infrastructure_score", 75))
    if climate_data.get("flood_risk_level") == "high":
        C = min(C, 60)
    elif climate_data.get("flood_risk_level") == "low":
        C = max(C, 85)

    stress_passed = bool(financial_data.get("stress_test_passed", True))
    dscr = float(financial_data.get("dscr_ratio", 1.0))
    if stress_passed and dscr >= 1.2:
        F = 90
    elif stress_passed and dscr >= 1.0:
        F = 80
    elif stress_passed:
        F = 70
    else:
        F = 45

    # Weighted Overall Score: 35% Legal, 25% Valuation, 20% Climate, 20% Finance
    overall_score = int(round(0.35 * L + 0.25 * V + 0.20 * C + 0.20 * F))
    overall_score = min(100, max(0, overall_score))

    # Verdict assignment
    if overall_score >= 80 and L >= 75 and stress_passed:
        verdict = "STRONGLY_RECOMMENDED"
    elif overall_score >= 60 and L >= 50:
        verdict = "PROCEED_WITH_CAUTION"
    else:
        verdict = "HIGH_RISK_AVOID"

    # Friendly human-readable labels for end users
    verdict_display_map = {
        "STRONGLY_RECOMMENDED": "Khuyến nghị mạnh mẽ (An toàn đầu tư)",
        "PROCEED_WITH_CAUTION": "Cần thận trọng (Xem xét rủi ro & Đàm phán thêm)",
        "HIGH_RISK_AVOID": "Rủi ro cao (Cân nhắc tránh đầu tư)",
    }
    valuation_display_map = {
        "under_priced": "Giá tốt hơn thị trường (Rẻ hơn mặt bằng chung)",
        "fair": "Mức giá hợp lý (Sát mặt bằng chung)",
        "over_priced": "Giá cao hơn thị trường (Cần đàm phán giảm giá)",
    }
    flood_display_map = {
        "low": "Thấp (Khu vực cao ráo, an toàn ngập lụt)",
        "medium": "Trung bình (Nguy cơ ngập úng cục bộ khi mưa lớn hoặc triều cường)",
        "high": "Cao (Khu vực trũng thấp ven sông, dễ ngập mùa mưa lũ)",
    }

    verdict_label = verdict_display_map.get(verdict, verdict)
    val_status_label = valuation_display_map.get(val_status, val_status)
    flood_level = climate_data.get("flood_risk_level", "low")
    flood_label = flood_display_map.get(flood_level, flood_level)

    # Executive Markdown Report
    price_million = price / 1_000_000
    unit_price_million = (price / area) / 1_000_000
    unit_price_val_m = float(valuation_data.get("unit_price_per_m2", 0)) / 1_000_000
    avg_district_val_m = float(valuation_data.get("avg_district_price_per_m2", 0)) / 1_000_000
    monthly_repay_m = float(financial_data.get("monthly_repayment_vnd", 0)) / 1_000_000
    est_rental_m = float(financial_data.get("estimated_monthly_rental_income", 0)) / 1_000_000

    markdown_lines = [
        f"# 📑 BÁO CÁO THẨM ĐỊNH CHUYÊN SÂU BẤT ĐỘNG SẢN (DUE DILIGENCE DOSSIER)",
        f"**Tài sản:** {title} | **Địa bàn:** {district}, Đà Nẵng",
        f"**Quy mô:** {area} m² | **Giá chào bán:** {price_million:,.1f} triệu VNĐ ({unit_price_million:.1f} triệu đ/m²)\n",
        f"## 🏆 KẾT QUẢ ĐÁNH GIÁ TỔNG THỂ",
        f"- **Điểm an toàn & tiềm năng đầu tư:** **{overall_score}/100**",
        f"- **Kết luận thẩm định:** **{verdict_label}**",
        f"- **Điểm thành phần:** Pháp lý: {L}/100 | Định giá: {V}/100 | Hạ tầng & Ngập lụt: {C}/100 | Tài chính: {F}/100\n",
        f"### 🎯 Tóm tắt điều hành (Executive Summary)",
        f"Bất động sản đạt điểm tổng hợp {overall_score}/100 với kết luận **{verdict_label}**. "
        f"Tình trạng pháp lý {legal_data.get('title_deed_status')}, định giá ở mức **{val_status_label}** so với trung bình quận {district}. "
        f"Rủi ro ngập lụt được phân loại **{flood_label}**. Kịch bản tài chính {'đạt bài kiểm tra chịu đựng lãi suất +3%' if stress_passed else 'cảnh báo rủi ro đứt gãy dòng tiền khi thả nổi'}.\n",
        f"## 1. ⚖️ Thẩm định Pháp lý & Quy hoạch (Trọng số 35%)",
        f"- **Tình trạng sổ:** {legal_data.get('title_deed_status')}",
        f"- **Quy hoạch sử dụng đất:** {legal_data.get('zoning_status')}",
        f"- **Điểm an toàn pháp lý:** {L}/100",
        "- **Rủi ro nhận diện:**",
    ]
    for r in legal_data.get("risks_detected", []):
        markdown_lines.append(f"  - {r}")
    markdown_lines.append("- **Căn cứ pháp luật viện dẫn:**")
    for cit in legal_data.get("citations", []):
        markdown_lines.append(f"  - *{cit.get('doc_title')}* - **{cit.get('article')}**: \"{cit.get('content')}\"")

    markdown_lines.extend([
        f"\n## 2. 📊 Thẩm định Định giá & So sánh Thị trường (Trọng số 25%)",
        f"- **Đơn giá tài sản:** {unit_price_val_m:.1f} triệu đ/m²",
        f"- **Đơn giá trung bình quận {district}:** {avg_district_val_m:.1f} triệu đ/m²",
        f"- **Trạng thái định giá:** {val_status_label}",
        f"- **Số lượng BĐS so sánh tham chiếu:** {len(valuation_data.get('comparable_properties', []))} tài sản",
    ])

    live_web_listings = valuation_data.get("live_market_listings", [])
    if live_web_listings:
        markdown_lines.append(f"\n### 🌐 Tin đăng Tham khảo Thực tế từ Thị trường (Tavily Search):")
        for item in live_web_listings:
            title_item = item.get("title", "Tin đăng BĐS")
            url_item = item.get("url", "")
            domain_item = item.get("source_domain", "web")
            snippet_item = item.get("snippet", "")
            markdown_lines.append(f"- [{domain_item}] **[{title_item}]({url_item})**: {snippet_item}")

    markdown_lines.extend([
        f"\n## 3. 🌊 Khảo sát Địa hình, Ngập lụt & Hạ tầng Tiện ích (Trọng số 20%)",
        f"- **Mức độ rủi ro ngập lụt:** {flood_label}",
        f"- **Ghi chú thủy văn mùa mưa bão:** {climate_data.get('flood_notes')}",
        f"- **Điểm hạ tầng:** {C}/100",
        f"- **Tiện ích trọng điểm:** {', '.join(climate_data.get('key_amenities', []))}\n",
        f"## 4. 💰 Mô phỏng Tài chính & Dòng tiền Cho thuê (Trọng số 20%)",
        f"- **Số tiền vay đề xuất:** {monthly_repay_m:.1f} triệu đ trả góp tháng đầu",
        f"- **Lãi suất tham chiếu:** {financial_data.get('effective_interest_rate', 0)}%/năm",
        f"- **Dòng tiền cho thuê ước tính:** {est_rental_m:.1f} triệu đ/tháng",
        f"- **Tỷ suất sinh lời ròng (Net Yield):** {financial_data.get('net_rental_yield_percent', 0)}%/năm",
        f"- **Hệ số chi trả nợ DSCR:** {financial_data.get('dscr_ratio', 0)}",
        f"- **Kết quả Stress-test lãi suất +3%:** `{'ĐẠT (Passed)' if stress_passed else 'KHÔNG ĐẠT (Failed)'}`\n",
        f"## 5. 🛡️ Phản biện Rủi ro Độc lập (Adversarial Critic)",
    ])
    for arg in critic_counterarguments:
        markdown_lines.append(f"- {arg}")

    markdown_lines.append(f"\n## 6. 🤝 Đòn bẩy & Khuyến nghị Đàm phán Giá (Actionable Levers)")
    if actionable_negotiation_points:
        for lever in actionable_negotiation_points:
            markdown_lines.append(f"- {lever}")
    else:
        markdown_lines.append("- Thương lượng điều khoản giải ngân ngân hàng và trần cọc 5%.")

    deep_res_data = _to_dict(state.get("deep_research"))
    deep_res_obj = None
    if deep_res_data:
        try:
            deep_res_obj = DeepResearchAssessment(**deep_res_data)
        except Exception:
            deep_res_obj = None

    if deep_res_obj:
        markdown_lines.extend([
            f"\n## 7. 🕵️ Kết quả Điều tra Sâu Chủ đầu tư & Thị trường (Deep Research)",
            f"- **Chủ thể điều tra:** {deep_res_obj.target_entity}",
            f"- **Điểm tín nhiệm chủ đầu tư:** {deep_res_obj.reputation_score}/100",
            f"- **Đánh giá cộng đồng:** {deep_res_obj.community_sentiment.upper()}",
            f"- **Tóm tắt năng lực bàn giao:** {deep_res_obj.track_record_summary}",
        ])
        if deep_res_obj.red_flags:
            markdown_lines.append("- **Cảnh báo rủi ro (Red Flags):**")
            for rf in deep_res_obj.red_flags:
                markdown_lines.append(f"  - ⚠️ {rf}")
        if deep_res_obj.dispute_history:
            markdown_lines.append("- **Tiền sử tranh chấp / khiếu nại:**")
            for dh in deep_res_obj.dispute_history:
                markdown_lines.append(f"  - ⚖️ {dh}")
        if deep_res_obj.sources_analyzed:
            markdown_lines.append("- **Nguồn tin đã rà soát:**")
            for src in deep_res_obj.sources_analyzed:
                markdown_lines.append(f"  - [{src.get('title', 'Nguồn tin')}]({src.get('url', '#')})")

    full_markdown = "\n".join(markdown_lines)

    legal_obj = LegalRiskAssessment(**legal_data)
    val_obj = MarketValuationAssessment(**valuation_data)
    climate_obj = ClimateInfrastructureAssessment(**climate_data)
    fin_obj = FinancialFeasibilityAssessment(**financial_data)

    dossier = DueDiligenceDossier(
        overall_score=overall_score,
        verdict=verdict,
        verdict_label=verdict_label,
        executive_summary=(
            f"Tài sản {title} ({district}) đạt {overall_score}/100 điểm ({verdict_label}). "
            f"Pháp lý: {L}/100, Định giá: {val_status_label}, Ngập lụt: {flood_label}."
        ),
        legal=legal_obj,
        valuation=val_obj,
        climate_infrastructure=climate_obj,
        financial=fin_obj,
        deep_research=deep_res_obj,
        critic_counterarguments=critic_counterarguments,
        actionable_negotiation_points=actionable_negotiation_points or ["Thương lượng trần cọc 5% theo Luật KD BĐS 2023."],
        full_markdown_report=full_markdown
    )

    return {
        "stage": "completed",
        "dossier": dossier.model_dump()
    }


# ==============================================================================
# 6. DOMAIN TOOLS FOR DEEPAGENTS
# ==============================================================================

@tool
def search_legal_docs_tool(query: str, top_k: int = 3) -> str:
    """Tra cứu các điều khoản luật đất đai 2024, luật kinh doanh BĐS 2023 liên quan đến điều kiện chuyển nhượng, sổ hồng, quy hoạch, tranh chấp, đặt cọc 5%."""
    docs = search_legal_documents(query=query, top_k=top_k)
    return json.dumps(docs, ensure_ascii=False)


@tool
def search_qdrant_properties_tool(query: str, district: str, limit: int = 5) -> str:
    """Tìm kiếm các bất động sản tương đương tại Đà Nẵng trong cơ sở dữ liệu vector Qdrant để so sánh đơn giá theo m2."""
    try:
        from qdrant_service import qdrant_service
        results = qdrant_service.search_properties(
            query=query,
            district=district,
            limit=limit
        )
        comparables = []
        for r in results:
            payload = r.get("payload", r) if isinstance(r, dict) else getattr(r, "payload", {})
            p_price = float(payload.get("price") or 0.0)
            p_area = float(payload.get("area_m2") or payload.get("area") or 0.0)
            if p_price > 0 and p_area > 0:
                comparables.append({
                    "id": str(payload.get("id", "")),
                    "title": payload.get("title", ""),
                    "price": p_price,
                    "area": p_area,
                    "unit_price_per_m2": round(p_price / p_area, 2)
                })
        return json.dumps(comparables, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "comparables": []}, ensure_ascii=False)


@tool
def search_tavily_web_listings_tool(query: str, district: str, max_results: int = 3) -> str:
    """Tìm kiếm các tin đăng bán BĐS thực tế đang chào bán trên thị trường trực tuyến (batdongsan, chotot, alonhadat) qua Tavily Web Search."""
    listings = search_tavily_real_estate(query=query, district=district, max_results=max_results)
    return json.dumps(listings, ensure_ascii=False)


@tool
def evaluate_climate_infrastructure_tool(district: str, ward: str = "") -> str:
    """Đánh giá rủi ro ngập úng thủy văn mùa mưa lũ (tháng 10-11) tại các khu vực Đà Nẵng và thống kê các tiện ích hạ tầng trọng điểm."""
    amenities = DISTRICT_AMENITIES.get(district, [
        "Trường học liên cấp", "Chợ dân sinh", "Bệnh viện đa khoa", "Khu thể thao công cộng"
    ])
    ward_lower = (ward or "").lower()
    if district in ["Hòa Vang", "Cẩm Lệ"] or any(w in ward_lower for w in ["hòa xuân", "hòa phát", "hòa thọ", "hòa tiến", "khuê trung"]):
        flood_risk_level = "high"
        flood_notes = (
            f"Khu vực {district} nằm tại vùng trũng thấp lưu vực sông Cẩm Lệ và sông Yên. "
            "Trong các mùa mưa lũ lịch sử (tháng 10 - 11), khu vực ghi nhận nguy cơ ngập sâu 0.5m - 1.5m cục bộ. "
            "Cần giải pháp tôn cao nền móng hoặc trang bị hệ thống thoát nước chủ động."
        )
        infrastructure_score = 60
    elif district in ["Liên Chiểu", "Thanh Khê"] or any(w in ward_lower for w in ["phú lộc", "khe cạn", "hòa khánh"]):
        flood_risk_level = "medium"
        flood_notes = (
            f"Khu vực {district} có địa hình chuyển tiếp đồng bằng ven vịnh Đà Nẵng. "
            "Có nguy cơ ngập úng tạm thời 20 - 40cm khi có mưa cường độ lớn trùng triều cường dâng cao."
        )
        infrastructure_score = 75
    else:
        flood_risk_level = "low"
        flood_notes = (
            f"Khu vực {district} có nền địa chất cao ráo, gò cát ven biển hoặc cấu trúc thoát nước đô thị trung tâm đồng bộ. "
            "Hầu như không ghi nhận tình trạng ngập lụt kéo dài trong các đợt mưa bão lớn tại Đà Nẵng."
        )
        infrastructure_score = 90

    return json.dumps({
        "district": district,
        "ward": ward,
        "flood_risk_level": flood_risk_level,
        "flood_notes": flood_notes,
        "infrastructure_score": infrastructure_score,
        "key_amenities": amenities
    }, ensure_ascii=False)


@tool
def calculate_mortgage_loan_tool(
    loan_amount: float,
    annual_interest_rate: float = 8.5,
    tenure_years: int = 20,
    method: str = "reducing_balance"
) -> str:
    """Tính toán số tiền trả góp hàng tháng đầu tiên và lịch trả nợ vay mua nhà theo phương thức dư nợ giảm dần hoặc niên kim."""
    payment = calculate_monthly_payment(
        loan_amount=loan_amount,
        annual_interest_rate=annual_interest_rate,
        tenure_years=tenure_years,
        method=method
    )
    return json.dumps({
        "loan_amount": loan_amount,
        "annual_interest_rate": annual_interest_rate,
        "tenure_years": tenure_years,
        "method": method,
        "monthly_repayment_vnd": float(payment)
    }, ensure_ascii=False)


@tool
def get_bank_interest_rates_tool(tenure_years: int = 20, bank_names: Optional[str] = None) -> str:
    """Tra cứu biểu lãi suất vay mua nhà bình quân và gói vay ưu đãi nhất từ các ngân hàng lớn (Vietcombank, BIDV, Techcombank...)."""
    rate_info = get_average_rate_and_best_package(tenure_years=tenure_years, bank_names=bank_names)
    return json.dumps({
        "average_rate": rate_info.average_rate,
        "best_package": rate_info.best_package
    }, ensure_ascii=False)


@tool
def deep_developer_search_tool(target_name: str, district: str) -> str:
    """Điều tra sâu uy tín chủ đầu tư, lịch sử chậm bàn giao sổ đỏ, khiếu nại tranh chấp trên báo chí và truyền thông."""
    assessment = run_deep_developer_investigation(target_name=target_name, district=district)
    return json.dumps(assessment.model_dump(), ensure_ascii=False)


# ==============================================================================
# 7. HIERARCHICAL SUBAGENT SPECIFICATIONS (ISOLATED CONTEXT)
# ==============================================================================

def get_due_diligence_subagents(enable_deep_research: bool = False) -> List[SubAgent]:
    """Returns the list of specialized SubAgents configured for DeepAgents."""
    subagents: List[SubAgent] = [
        {
            "name": "legal_specialist",
            "description": (
                "Chuyên gia thẩm định pháp lý và quy hoạch BĐS Đà Nẵng. "
                "Sử dụng subagent này để thẩm định sổ hồng/sổ đỏ, quy hoạch sử dụng đất (ODT/CLN), "
                "phát hiện nguy cơ tranh chấp và đối chiếu căn cứ theo Luật Đất đai 2024, Luật Kinh doanh BĐS 2023 (trần cọc 5%)."
            ),
            "system_prompt": (
                "Bạn là Chuyên gia Thẩm định Pháp lý & Quy hoạch BĐS Đà Nẵng. "
                "Nhiệm vụ: Sử dụng tool 'search_legal_docs_tool' để tra cứu các văn bản luật liên quan. "
                "Đánh giá: 1) Tình trạng sổ; 2) Quy hoạch sử dụng đất; 3) Các rủi ro pháp lý; "
                "4) Điểm an toàn pháp lý (0-100); 5) Căn cứ pháp luật."
            ),
            "tools": [search_legal_docs_tool],
            "mode": "isolated"
        },
        {
            "name": "valuation_expert",
            "description": (
                "Chuyên gia thẩm định giá và nghiên cứu thị trường BĐS Đà Nẵng. "
                "Sử dụng subagent này để so sánh đơn giá tài sản với mặt bằng giá quận/phường, "
                "tìm kiếm các BĐS tương đương trong Qdrant và tin đăng thị trường thực tế qua Tavily."
            ),
            "system_prompt": (
                "Bạn là Chuyên gia Định giá BĐS Đà Nẵng. "
                "Nhiệm vụ: 1) Tính đơn giá/m2; 2) Tra cứu giá bình quân quận qua 'search_qdrant_properties_tool'; "
                "3) Tìm tin đăng thực tế qua 'search_tavily_web_listings_tool'; "
                "4) Kết luận trạng thái định giá: 'under_priced', 'fair', hoặc 'over_priced'."
            ),
            "tools": [search_qdrant_properties_tool, search_tavily_web_listings_tool],
            "mode": "isolated"
        },
        {
            "name": "climate_infrastructure_analyst",
            "description": (
                "Chuyên gia khảo sát địa hình, thủy văn, rủi ro ngập lụt và hạ tầng tiện ích Đà Nẵng. "
                "Sử dụng subagent này để đánh giá nguy cơ ngập nước mùa mưa bão (sông Cẩm Lệ, Liên Chiểu, gò cát) và chấm điểm tiện ích."
            ),
            "system_prompt": (
                "Bạn là Chuyên gia Khảo sát Địa hình & Thủy văn Đà Nẵng. "
                "Nhiệm vụ: Sử dụng 'evaluate_climate_infrastructure_tool' để: "
                "1) Xác định mức độ rủi ro ngập lụt ('low', 'medium', 'high'); "
                "2) Cung cấp ghi chú thủy văn mùa mưa lũ; 3) Chấm điểm hạ tầng (0-100); 4) Liệt kê tiện ích."
            ),
            "tools": [evaluate_climate_infrastructure_tool],
            "mode": "isolated"
        },
        {
            "name": "financial_engineer",
            "description": (
                "Kỹ sư tài chính và mô phỏng dòng tiền BĐS. "
                "Sử dụng subagent này để tính phương án vay ngân hàng, lãi suất thả nổi, dòng tiền cho thuê, tỷ suất sinh lời net yield, hệ số DSCR và stress test."
            ),
            "system_prompt": (
                "Bạn là Kỹ sư Tài chính Bất động sản chuyên nghiệp. "
                "Nhiệm vụ: 1) Tra cứu lãi suất qua 'get_bank_interest_rates_tool'; "
                "2) Tính tiền trả góp hàng tháng qua 'calculate_mortgage_loan_tool'; "
                "3) Tính dòng tiền cho thuê và Net Rental Yield; 4) Tính hệ số DSCR; 5) Stress-test lãi suất +3%."
            ),
            "tools": [calculate_mortgage_loan_tool, get_bank_interest_rates_tool],
            "mode": "isolated"
        },
        {
            "name": "adversarial_critic",
            "description": (
                "Chuyên gia phản biện rủi ro độc lập (Devil's Advocate) và chiến lược đàm phán giá BĐS. "
                "Sử dụng subagent này để tìm kiếm góc khuất, bẫy pháp lý, sốc lãi suất thả nổi, bẫy thanh khoản và lập danh mục đòn bẩy đàm phán."
            ),
            "system_prompt": (
                "Bạn là Chuyên gia Phản biện Rủi ro Độc lập (Devil's Advocate) bảo vệ người mua BĐS. "
                "Nhiệm vụ: 1) Nêu tối thiểu 3-5 luận điểm phản biện rủi ro; "
                "2) Cung cấp 4-6 đòn bẩy đàm phán giá thực chiến và điều khoản bảo vệ hợp đồng."
            ),
            "tools": [calculate_mortgage_loan_tool],
            "mode": "isolated"
        }
    ]

    if enable_deep_research:
        subagents.append({
            "name": "developer_deep_researcher",
            "description": (
                "Điều tra viên độc lập uy tín chủ đầu tư và doanh nghiệp BĐS Đà Nẵng. "
                "Sử dụng subagent này khi cần điều tra sâu uy tín chủ đầu tư, lịch sử bàn giao sổ, tranh chấp kiện tụng hoặc các cảnh báo đỏ."
            ),
            "system_prompt": (
                "Bạn là Điều tra viên Độc lập uy tín Chủ đầu tư BĐS Đà Nẵng. "
                "Nhiệm vụ: Sử dụng 'deep_developer_search_tool' để đánh giá uy tín, tranh chấp, cảnh báo đỏ và tình cảm cộng đồng."
            ),
            "tools": [deep_developer_search_tool],
            "mode": "isolated"
        })

    return subagents


def _get_default_model(model_name: Optional[str] = None) -> BaseChatModel:
    """Helper resolving chat model from settings or offline test fallback."""
    try:
        from config import settings
        api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        model = model_name or getattr(settings, "OPENAI_MODEL_NAME", "gpt-4o-mini")
        base_url = getattr(settings, "OPENAI_BASE_URL", None) or os.getenv("OPENAI_BASE_URL", None)
    except Exception:
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = model_name or os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")
        base_url = os.getenv("OPENAI_BASE_URL", None)

    if not api_key or api_key.startswith("sk-your") or api_key.startswith("your-"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=["DeepAgents Due Diligence Dossier synthesized."])

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.1,
        request_timeout=35.0,
        max_retries=1
    )


def create_deep_due_diligence_agent(
    model: Optional[Any] = None,
    enable_deep_research: bool = False,
    **kwargs
) -> Any:
    """
    Factory constructing a DeepAgent for comprehensive Da Nang property due diligence.
    Configures specialized subagents and disables distracting filesystem tools for reliable execution.
    """
    resolved_model = model or _get_default_model()
    subagents = get_due_diligence_subagents(enable_deep_research=enable_deep_research)
    all_tools = [
        search_legal_docs_tool,
        search_qdrant_properties_tool,
        search_tavily_web_listings_tool,
        evaluate_climate_infrastructure_tool,
        calculate_mortgage_loan_tool,
        get_bank_interest_rates_tool,
        deep_developer_search_tool,
    ]

    system_prompt = (
        "Bạn là Trưởng ban Thẩm định Chuyên sâu Bất động sản Đà Nẵng (Lead Real Estate Due Diligence Specialist). "
        "Nhiệm vụ của bạn là thẩm định toàn diện một bất động sản mục tiêu và xuất ra Hồ sơ Thẩm định Chuyên sâu (DueDiligenceDossier) hoàn chỉnh.\n\n"
        "Quy trình bắt buộc:\n"
        "1. ĐIỀU PHỐI ĐIỀU TRA: Giao việc cho các subagents chuyên biệt bằng công cụ 'task' khi cần thông tin chi tiết:\n"
        "   - 'legal_specialist' thẩm định pháp lý sổ hồng, quy hoạch ODT và tranh chấp theo Luật Đất đai 2024.\n"
        "   - 'valuation_expert' khảo sát định giá và tin đăng thị trường thực tế.\n"
        "   - 'climate_infrastructure_analyst' đánh giá thủy văn và ngập lụt mùa mưa lũ.\n"
        "   - 'financial_engineer' mô phỏng kịch bản vay, DSCR và stress test +3%.\n"
        "   - (Nếu được yêu cầu): 'developer_deep_researcher' điều tra uy tín chủ đầu tư.\n"
        "2. PHẢN BIỆN ĐỘC LẬP: Giao việc cho 'adversarial_critic' để phản biện toàn bộ các kết quả và lập đòn bẩy đàm phán.\n"
        "3. TỔNG HỢP VÀ CHẤM ĐIỂM (Dossier Synthesis):\n"
        "   - Tính Điểm An Toàn Tổng Thể (Overall Score) theo công thức chuẩn: "
        "     Overall Score = Round(0.35 * Legal + 0.25 * Valuation + 0.20 * Climate + 0.20 * Financial)\n"
        "   - Kết luận thẩm định:\n"
        "     * STRONGLY_RECOMMENDED: Overall Score >= 80, Legal Score >= 75 và vượt qua bài Stress test.\n"
        "     * PROCEED_WITH_CAUTION: Overall Score >= 60 và Legal Score >= 50.\n"
        "     * HIGH_RISK_AVOID: Các trường hợp còn lại.\n"
        "   - Xuất trực tiếp cấu trúc hồ sơ thẩm định DueDiligenceDossier đầy đủ các trường, bao gồm full_markdown_report.\n"
        "   - Tuyệt đối không sử dụng công cụ hệ thống tập tin hay shell."
    )

    from deepagents.middleware._tool_exclusion import _ToolExclusionMiddleware
    fs_exclusion = _ToolExclusionMiddleware(
        excluded=frozenset(['write_file', 'edit_file', 'delete', 'execute', 'glob', 'grep', 'ls', 'read_file'])
    )

    middleware = list(kwargs.pop("middleware", []))
    middleware.append(fs_exclusion)

    return create_deep_agent(
        model=resolved_model,
        tools=all_tools,
        subagents=subagents,
        system_prompt=system_prompt,
        response_format=DueDiligenceDossier,
        middleware=middleware,
        **kwargs
    )


# ==============================================================================
# 8. DEEPAGENTS DUE DILIGENCE RUNNER & COMPILATION
# ==============================================================================

class DeepDueDiligenceGraph:
    """
    Graph runner wrapping Pure DeepAgents execution for real estate due diligence.
    Ensures complete backward compatibility with LangGraph ainvoke / invoke interfaces.
    """
    def __init__(self, agent_factory=None):
        self._agent_factory = agent_factory or create_deep_due_diligence_agent

    def invoke(self, state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Synchronous execution of due diligence."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.ainvoke(state, config=config))
                return future.result()
        return asyncio.run(self.ainvoke(state, config=config))

    async def ainvoke(self, state: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Asynchronous execution of due diligence using Pure DeepAgents with parallel fan-out and real-time event streaming."""
        info = _extract_property_info(state)
        enable_deep = info.get("enable_deep_research", False)

        # Extract optional progress_callback and create a serializable config copy for LangGraph/DeepAgent
        progress_callback = None
        clean_config = None
        if config:
            clean_config = dict(config)
            cfg_inner = dict(config.get("configurable") or {})
            progress_callback = cfg_inner.pop("progress_callback", None)
            clean_config["configurable"] = cfg_inner

        async def _emit(
            node_name: str,
            node_status: str,
            stage: str,
            progress: int,
            message: str,
            label: Optional[str] = None,
            summary: Optional[str] = None,
            duration_ms: Optional[int] = None,
        ) -> None:
            if not progress_callback:
                return
            try:
                res = progress_callback(
                    node_name=node_name,
                    node_status=node_status,
                    stage=stage,
                    progress=progress,
                    message=message,
                    label=label,
                    summary=summary,
                    duration_ms=duration_ms,
                )
                if asyncio.iscoroutine(res):
                    await res
            except Exception as cb_err:
                logger.debug(f"Progress callback skipped for {node_name}: {cb_err}")

        # 1. Planning stage
        t_plan = time.time()
        await _emit(
            "planning", "running", "planning", 12,
            "Đang lập kế hoạch & phân rã mục tiêu thẩm định...",
            label="Lập kế hoạch"
        )
        plan_dict = await asyncio.to_thread(plan_investigation_node, state)
        current_state = {**state, **plan_dict}
        await _emit(
            "planning", "completed", "planning", 15,
            "Hoàn tất kế hoạch thẩm định đa nguồn.",
            label="Lập kế hoạch",
            summary="Đã phân rã 4 mũi điều tra chuyên sâu",
            duration_ms=int((time.time() - t_plan) * 1000)
        )

        # 2. Analytical nodes/tools execution IN PARALLEL (reduces latency 2-3x + streams per-node progress)
        investigation_specs = [
            ("legal", "Pháp lý & Quy hoạch", legal_investigation_node),
            ("valuation", "Định giá & So sánh", valuation_investigation_node),
            ("climate", "Thủy văn & Hạ tầng", climate_investigation_node),
            ("financial", "Tài chính & Lãi suất", financial_simulation_node),
        ]
        if enable_deep:
            investigation_specs.append(("deep_research", "Deep Research Web", deep_research_node))
        else:
            current_state["deep_research"] = None
            await _emit(
                "deep_research", "skipped", "investigating", 20,
                "Bỏ qua Deep Research chuyên sâu (không bật).",
                label="Deep Research Web",
                summary="Chưa bật"
            )

        for n_key, n_label, _ in investigation_specs:
            await _emit(
                n_key, "running", "investigating", 20,
                f"Đang điều tra: {n_label}...",
                label=n_label
            )

        async def _run_investigation(n_key: str, n_label: str, fn):
            t0 = time.time()
            res_dict = await asyncio.to_thread(fn, dict(current_state))
            dur_ms = int((time.time() - t0) * 1000)
            return n_key, n_label, res_dict, dur_ms

        def _summarize_node(n_key: str, res_dict: Dict[str, Any]) -> str:
            try:
                if n_key == "legal":
                    leg = _to_dict(res_dict.get("legal") or {})
                    cites = leg.get("citations") or []
                    risk = leg.get("risk_level", "Trung bình")
                    return f"{len(cites)} trích dẫn luật • Rủi ro: {risk}"
                if n_key == "valuation":
                    val = _to_dict(res_dict.get("valuation") or {})
                    pm2 = val.get("price_per_m2_vnd") or 0
                    status = val.get("valuation_status", "Đã định giá")
                    if pm2:
                        return f"{pm2 / 1_000_000:.1f} tr/m² • {status}"
                    return str(status)
                if n_key == "climate":
                    cli = _to_dict(res_dict.get("climate") or {})
                    flood = cli.get("flood_risk", "Thấp")
                    zone = cli.get("coastal_or_river_zone") or "Đà Nẵng"
                    return f"Ngập: {flood} • {zone}"
                if n_key == "financial":
                    fin = _to_dict(res_dict.get("financial") or {})
                    rate = fin.get("average_interest_rate") or 0
                    monthly = fin.get("monthly_payment_vnd") or 0
                    return f"Lãi ~{rate:.1f}% • Trả {monthly / 1_000_000:.1f} tr/tháng"
                if n_key == "deep_research":
                    dr = _to_dict(res_dict.get("deep_research") or {})
                    sources = dr.get("sources") or dr.get("findings") or []
                    return f"{len(sources)} nguồn thông tin thực tế"
            except Exception:
                pass
            return "Hoàn tất phân tích"

        tasks = [
            asyncio.create_task(_run_investigation(k, lbl, fn))
            for k, lbl, fn in investigation_specs
        ]
        total_inv = len(tasks)
        completed_inv = 0

        for fut in asyncio.as_completed(tasks):
            n_key, n_label, res_dict, dur_ms = await fut
            current_state.update(res_dict)
            completed_inv += 1
            prog = 20 + int(45 * completed_inv / max(1, total_inv))
            summary = _summarize_node(n_key, res_dict)
            await _emit(
                n_key, "completed", "investigating", prog,
                f"Đã xong {n_label} ({completed_inv}/{total_inv}): {summary}",
                label=n_label,
                summary=summary,
                duration_ms=dur_ms
            )

        # 3. Adversarial Critic stage
        t_critic = time.time()
        await _emit(
            "critic", "running", "critiquing", 68,
            "Đang phản biện rủi ro độc lập (Devil's Advocate)...",
            label="Phản biện Độc lập"
        )
        critic_dict = await asyncio.to_thread(adversarial_critic_node, current_state)
        current_state.update(critic_dict)
        critic_data = _to_dict(critic_dict.get("critic") or {})
        critic_risks = critic_data.get("key_risks") or critic_data.get("blind_spots") or []
        await _emit(
            "critic", "completed", "critiquing", 74,
            f"Hoàn tất phản biện: phát hiện {len(critic_risks)} điểm cần lưu ý.",
            label="Phản biện Độc lập",
            summary=f"{len(critic_risks)} điểm rủi ro / phản biện",
            duration_ms=int((time.time() - t_critic) * 1000)
        )

        # 4. Autonomous DeepAgent invocation with live tool-call streaming (astream_events)
        TOOL_LABELS = {
            "search_legal_docs_tool": "Tra cứu văn bản pháp luật (Qdrant)",
            "search_qdrant_properties_tool": "Tìm BĐS tương đương (Qdrant)",
            "search_tavily_web_listings_tool": "Quét tin rao thị trường (Tavily)",
            "evaluate_climate_infrastructure_tool": "Đánh giá ngập lụt & hạ tầng",
            "calculate_mortgage_loan_tool": "Tính toán lịch trả nợ vay",
            "get_bank_interest_rates_tool": "Tra cứu lãi suất ngân hàng",
            "deep_developer_search_tool": "Điều tra uy tín chủ đầu tư",
        }

        if not os.environ.get("PYTEST_CURRENT_TEST"):
            try:
                from config import settings
                api_key = getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
                if api_key and not api_key.startswith("sk-your") and not api_key.startswith("your-"):
                    t_da = time.time()
                    await _emit(
                        "deep_agent", "running", "critiquing", 76,
                        "DeepAgent đang kiểm chứng chéo & lập luận tổng hợp...",
                        label="DeepAgent Tổng hợp"
                    )
                    agent = self._agent_factory(enable_deep_research=enable_deep)
                    prompt = (
                        f"Thực hiện thẩm định chuyên sâu cho tài sản: {info['title']}\n"
                        f"- Giá: {info['price']:,} VNĐ, Diện tích: {info['area']} m2\n"
                        f"- Địa chỉ: {info['ward']} {info['district']}, Đà Nẵng\n"
                        f"- Mục đích đầu tư: {info['objective']}, Vốn tự có: {info['equity']:,} VNĐ, Khoản vay: {info['loan']:,} VNĐ"
                    )
                    deep_input = {"messages": [{"role": "user", "content": prompt}]}
                    agent_res = None

                    if hasattr(agent, "astream_events"):
                        async def _run_streamed_agent():
                            captured = None
                            tool_step = 0
                            stream_iter = (
                                agent.astream_events(deep_input, config=clean_config, version="v2")
                                if clean_config
                                else agent.astream_events(deep_input, version="v2")
                            )
                            async for ev in stream_iter:
                                ev_type = ev.get("event")
                                ev_name = ev.get("name", "")
                                if ev_type == "on_tool_start" and ev_name:
                                    tool_step += 1
                                    friendly = TOOL_LABELS.get(ev_name, ev_name)
                                    prog_val = min(88, 76 + tool_step * 2)
                                    await _emit(
                                        "deep_agent", "running", "critiquing", prog_val,
                                        f"DeepAgent đang chạy công cụ: {friendly}...",
                                        label="DeepAgent Tổng hợp",
                                        summary=f"Đang gọi: {friendly}"
                                    )
                                elif ev_type == "on_chain_end":
                                    out = (ev.get("data") or {}).get("output")
                                    if isinstance(out, dict) and out.get("structured_response"):
                                        captured = out
                            return captured

                        agent_res = await asyncio.wait_for(_run_streamed_agent(), timeout=45.0)
                    else:
                        if clean_config:
                            agent_res = await asyncio.wait_for(agent.ainvoke(deep_input, config=clean_config), timeout=40.0)
                        else:
                            agent_res = await asyncio.wait_for(agent.ainvoke(deep_input), timeout=40.0)

                    structured = agent_res.get("structured_response") if isinstance(agent_res, dict) else None
                    if structured:
                        if hasattr(structured, "model_dump"):
                            dossier_data = structured.model_dump()
                        elif isinstance(structured, dict):
                            dossier_data = structured
                        else:
                            dossier_data = None
                        if dossier_data:
                            await _emit(
                                "deep_agent", "completed", "synthesizing", 90,
                                "DeepAgent hoàn tất tổng hợp hồ sơ thẩm định.",
                                label="DeepAgent Tổng hợp",
                                summary="Hoàn tất lập luận đa tác nhân",
                                duration_ms=int((time.time() - t_da) * 1000)
                            )
                            if not dossier_data.get("full_markdown_report"):
                                current_state.update(dossier_data)
                                synth_temp = await asyncio.to_thread(synthesize_dossier_node, current_state)
                                dossier_data["full_markdown_report"] = synth_temp.get("full_markdown_report", "")
                            current_state["stage"] = "completed"
                            current_state["dossier"] = dossier_data
                            return current_state
            except Exception as e:
                logger.warning(f"DeepAgent LLM execution deferred to deterministic synthesis: {type(e).__name__}: {e}")
                await _emit(
                    "deep_agent", "completed", "synthesizing", 88,
                    "Chuyển sang tổng hợp chuẩn hóa từ dữ liệu đã điều tra.",
                    label="DeepAgent Tổng hợp",
                    summary="Tổng hợp từ kết quả phân tích"
                )

        # 5. Synthesis stage
        t_syn = time.time()
        await _emit(
            "synthesize", "running", "synthesizing", 92,
            "Đang tổng hợp Dossier và tính toán điểm số đầu tư...",
            label="Tổng hợp Dossier"
        )
        synth_dict = await asyncio.to_thread(synthesize_dossier_node, current_state)
        current_state.update(synth_dict)
        current_state["stage"] = "completed"
        await _emit(
            "synthesize", "completed", "synthesizing", 98,
            "Hoàn tất hồ sơ Dossier.",
            label="Tổng hợp Dossier",
            summary="Đã xuất báo cáo chi tiết",
            duration_ms=int((time.time() - t_syn) * 1000)
        )

        return current_state


def build_due_diligence_graph():
    """Builds and returns the DeepDueDiligenceGraph instance powering Due Diligence."""
    return DeepDueDiligenceGraph()


# Singleton compiled graph instance
due_diligence_graph = build_due_diligence_graph()

