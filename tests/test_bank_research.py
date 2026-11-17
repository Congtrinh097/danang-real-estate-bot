import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from bank_research_service import (
    BankLoanPackage,
    BankResearchService,
    calculate_effective_rate,
    bank_research_service
)


def test_calculate_effective_rate():
    """
    Kiểm tra công thức tính lãi suất bình quân hàng năm (annual_interest_rate)
    dựa trên số năm vay (tenure_years), thời gian ưu đãi và lãi suất thả nổi.
    """
    # 20 năm vay, 1 năm đầu ưu đãi 6.0%, 19 năm sau thả nổi 10.0%
    # (6.0 * 1 + 10.0 * 19) / 20 = 196.0 / 20 = 9.8%
    rate_20y = calculate_effective_rate(tenure_years=20, pref_rate=6.0, pref_months=12, floating_rate=10.0)
    assert pytest.approx(rate_20y, rel=1e-3) == 9.8

    # 10 năm vay, 2 năm đầu ưu đãi 7.0%, 8 năm sau thả nổi 9.5%
    # (7.0 * 2 + 9.5 * 8) / 10 = (14.0 + 76.0) / 10 = 9.0%
    rate_10y = calculate_effective_rate(tenure_years=10, pref_rate=7.0, pref_months=24, floating_rate=9.5)
    assert pytest.approx(rate_10y, rel=1e-3) == 9.0

    # Nếu số năm vay nhỏ hơn thời gian ưu đãi (ví dụ vay 1 năm, ưu đãi 24 tháng) -> lấy luôn pref_rate
    rate_short = calculate_effective_rate(tenure_years=1, pref_rate=5.5, pref_months=24, floating_rate=10.5)
    assert rate_short == 5.5


def test_benchmark_bank_packages_structure():
    """
    Kiểm tra danh sách các gói vay ngân hàng lớn chuẩn hóa tại Việt Nam
    (Big 4: Vietcombank, BIDV, VietinBank và TMCP: Techcombank, MBBank, ACB).
    """
    packages = bank_research_service.get_bank_packages(tenure_years=15)
    assert len(packages) >= 5

    bank_names = [p.bank_name for p in packages]
    assert "Vietcombank" in bank_names
    assert "BIDV" in bank_names
    assert "Techcombank" in bank_names

    for p in packages:
        assert isinstance(p, BankLoanPackage)
        assert p.preferential_rate > 0
        assert p.preferential_months > 0
        assert p.floating_rate > p.preferential_rate
        assert p.effective_annual_rate > 0
        assert p.early_repayment_fee != ""
        assert p.suitability != ""


def test_filter_bank_packages_by_name():
    """Kiểm tra lọc gói vay theo tên ngân hàng cụ thể."""
    packages = bank_research_service.get_bank_packages(tenure_years=20, bank_names="Vietcombank, BIDV")
    assert len(packages) == 2
    names = {p.bank_name for p in packages}
    assert names == {"Vietcombank", "BIDV"}


def test_format_comparison_report():
    """Kiểm tra sinh báo cáo Markdown so sánh đa ngân hàng và đề xuất tối ưu."""
    packages = bank_research_service.get_bank_packages(tenure_years=20)
    report = bank_research_service.format_comparison_report(
        packages=packages,
        tenure_years=20,
        loan_amount=1_500_000_000,
        loan_purpose="mua_nha_o"
    )

    assert "BẢNG SO SÁNH GÓI VAY CÁC NGÂN HÀNG LỚN" in report
    assert "Vietcombank" in report
    assert "BIDV" in report
    assert "Techcombank" in report
    assert "Lãi suất ưu đãi" in report or "Lãi ưu đãi" in report
    assert "Lãi bình quân" in report
    assert "ĐỀ XUẤT GÓI VAY PHÙ HỢP VÀ TỐI ƯU TIỀN LÃI" in report
    assert "Vay an cư dài hạn" in report or "Vay dài hạn" in report


def test_tavily_search_mock_or_execution(monkeypatch):
    """Kiểm tra khả năng research thông qua Tavily Search kết hợp phân tích thị trường."""
    mock_tavily_results = [
        {
            "title": "Lãi suất vay mua nhà Vietcombank 2026 mới nhất",
            "content": "Vietcombank áp dụng lãi suất vay mua nhà cố định 6.0%/năm trong 12 tháng đầu hoặc 7.0%/năm trong 24 tháng, sau đó thả nổi 9.5%/năm.",
            "url": "https://vietcombank.com.vn/lai-suat-vay"
        }
    ]

    class DummyTavilyClient:
        def search(self, query, **kwargs):
            return {"results": mock_tavily_results}

    service = BankResearchService(tavily_client=DummyTavilyClient())
    packages, insights = service.research_market(tenure_years=20, query="lãi suất vay mua nhà Vietcombank")
    assert len(packages) > 0
    assert any("Vietcombank" in p.bank_name for p in packages)
    assert len(insights) > 0
