import sys
from pathlib import Path
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

# Đảm bảo đường dẫn import hoạt động khi chạy độc lập dưới dạng stdio process
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from mortgage_calculator import MortgageCalculator, MortgageInput
from bank_research_service import bank_research_service

# Khởi tạo FastMCP Server cho nghiệp vụ tài chính & tính lãi vay mua BĐS Đà Nẵng
mortgage_mcp_server = FastMCP("danang-real-estate-mortgage-server")


@mortgage_mcp_server.tool(
    name="calculate_mortgage_loan",
    description=(
        "Tool tính lãi suất và kế hoạch thanh toán gốc lãi ngân hàng khi vay mua bất động sản tại Đà Nẵng.\n"
        "Nhận các tham số: giá trị BĐS (property_price), số tiền vay (loan_amount), tỷ lệ vay % (loan_ratio), "
        "thời hạn vay tính theo năm (tenure_years), lãi suất năm % (annual_interest_rate), "
        "lãi suất ưu đãi (preferential_rate), số tháng ưu đãi (preferential_months), "
        "phương thức tính (method: 'reducing_balance' hoặc 'flat')."
    )
)
def calculate_mortgage_loan(
    property_price: Optional[float] = None,
    loan_amount: Optional[float] = None,
    loan_ratio: Optional[float] = 70.0,
    tenure_years: int = 20,
    annual_interest_rate: float = 8.5,
    preferential_rate: Optional[float] = None,
    preferential_months: int = 0,
    method: str = "reducing_balance"
) -> str:
    """Xử lý tính toán lãi vay qua MCP Server và trả về báo cáo Markdown chi tiết."""
    inp = MortgageInput(
        property_price=property_price,
        loan_amount=loan_amount,
        loan_ratio=loan_ratio or 70.0,
        tenure_years=tenure_years or 20,
        annual_interest_rate=annual_interest_rate or 8.5,
        preferential_rate=preferential_rate,
        preferential_months=preferential_months or 0,
        method=method or "reducing_balance"
    )

    res = MortgageCalculator.calculate(inp)
    return res.summary_markdown


@mortgage_mcp_server.tool(
    name="search_bank_mortgage_rates",
    description=(
        "Tool research thị trường lãi suất vay mua BĐS của các ngân hàng lớn tại Việt Nam (Vietcombank, BIDV, VietinBank, Techcombank, MBBank, ACB...) qua Tavily Search.\n"
        "Nhận các tham số: thời hạn vay tính theo năm (tenure_years), tên ngân hàng cần tra cứu nếu có (bank_names), "
        "mục đích vay (loan_purpose: 'mua_nha_o', 'dau_tu_ngan_han', 'toi_uu_dong_tien'), số tiền vay dự kiến (loan_amount).\n"
        "Trả về báo cáo Markdown chi tiết gồm: bảng so sánh lãi suất ưu đãi, lãi thả nổi, lãi bình quân theo số năm vay, "
        "bảng tính dòng tiền tháng đầu và đề xuất gói vay tối ưu chi phí lãi."
    )
)
def search_bank_mortgage_rates(
    tenure_years: int = 20,
    bank_names: Optional[str] = None,
    loan_purpose: Optional[str] = "mua_nha_o",
    loan_amount: Optional[float] = None
) -> str:
    """Xử lý research thị trường lãi suất ngân hàng và so sánh gói vay tối ưu."""
    packages, insights = bank_research_service.research_market(
        tenure_years=tenure_years or 20,
        bank_names=bank_names
    )
    report = bank_research_service.format_comparison_report(
        packages=packages,
        tenure_years=tenure_years or 20,
        loan_amount=loan_amount,
        loan_purpose=loan_purpose or "mua_nha_o"
    )
    if insights:
        report += "\n\n📌 **Dữ liệu & Cập nhật thị trường:**\n" + "\n".join(insights[:2])
    return report


if __name__ == "__main__":
    mortgage_mcp_server.run()
