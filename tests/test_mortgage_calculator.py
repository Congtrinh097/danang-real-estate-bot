import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from mortgage_calculator import MortgageCalculator, MortgageInput, MortgageResult


def test_reducing_balance_calculation():
    """
    Kiểm tra tính toán theo phương thức dư nợ giảm dần:
    - BĐS: 2 tỷ, vay 70% = 1.4 tỷ trong 20 năm (240 tháng), lãi suất 8.5%/năm
    - Gốc hàng tháng: 1.4 tỷ / 240 = 5,833,333.33 VNĐ
    - Lãi tháng 1: 1.4 tỷ * (8.5 / 100 / 12) = 9,916,666.67 VNĐ
    - Tổng trả tháng 1: 15,750,000 VNĐ
    - Tháng cuối: số tiền trả phải nhỏ hơn đáng kể tháng đầu
    """
    inp = MortgageInput(
        property_price=2_000_000_000,
        loan_ratio=70.0,
        tenure_years=20,
        annual_interest_rate=8.5,
        method="reducing_balance"
    )
    res = MortgageCalculator.calculate(inp)

    assert res.loan_amount == 1_400_000_000
    assert res.own_capital == 600_000_000
    assert res.tenure_months == 240
    assert pytest.approx(res.monthly_principal, rel=1e-3) == 1_400_000_000 / 240
    assert pytest.approx(res.first_month_payment, rel=1e-3) == 15_750_000
    assert res.last_month_payment < res.first_month_payment
    assert res.total_interest > 0
    assert res.total_payment == res.loan_amount + res.total_interest
    assert "BẢNG TÍNH LÃI VAY NGÂN HÀNG" in res.summary_markdown


def test_flat_rate_calculation():
    """
    Kiểm tra tính toán theo phương thức trả đều hàng tháng (niên kim cố định):
    - Khoản vay 1 tỷ, 10 năm (120 tháng), lãi 10%/năm
    - Số tiền tháng đầu bằng số tiền tháng cuối
    """
    inp = MortgageInput(
        loan_amount=1_000_000_000,
        tenure_years=10,
        annual_interest_rate=10.0,
        method="flat"
    )
    res = MortgageCalculator.calculate(inp)

    assert res.loan_amount == 1_000_000_000
    assert res.tenure_months == 120
    assert pytest.approx(res.first_month_payment, rel=1e-4) == res.last_month_payment
    assert res.first_month_payment > 0
    assert res.total_payment > res.loan_amount


def test_preferential_rate():
    """
    Kiểm tra gói vay có ưu đãi lãi suất trong 12 tháng đầu (ví dụ 6.0%, sau đó 9.5%)
    """
    inp = MortgageInput(
        loan_amount=1_000_000_000,
        tenure_years=10,
        annual_interest_rate=9.5,
        preferential_rate=6.0,
        preferential_months=12,
        method="reducing_balance"
    )
    res = MortgageCalculator.calculate(inp)

    # Tháng 1 tính theo 6.0%: gốc 8,333,333 + lãi 1 tỷ * 6% / 12 (5,000,000) = 13,333,333
    expected_month_1 = (1_000_000_000 / 120) + (1_000_000_000 * 0.06 / 12)
    assert pytest.approx(res.first_month_payment, rel=1e-3) == expected_month_1
    assert "Lãi suất ưu đãi" in res.summary_markdown
