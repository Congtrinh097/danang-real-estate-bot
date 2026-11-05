from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class MortgageInput(BaseModel):
    property_price: Optional[float] = Field(None, description="Tổng giá trị bất động sản (VNĐ)")
    loan_amount: Optional[float] = Field(None, description="Số tiền vay ngân hàng (VNĐ)")
    loan_ratio: Optional[float] = Field(70.0, description="Tỷ lệ vay vốn theo % (mặc định 70%)")
    tenure_years: int = Field(20, description="Thời hạn vay tính theo năm (ví dụ 10, 15, 20, 25 năm)")
    annual_interest_rate: float = Field(8.5, description="Lãi suất năm (%/năm, ví dụ 8.5)")
    preferential_rate: Optional[float] = Field(None, description="Lãi suất ưu đãi thời gian đầu (%/năm)")
    preferential_months: int = Field(0, description="Số tháng được hưởng lãi suất ưu đãi")
    method: str = Field("reducing_balance", description="'reducing_balance' (dư nợ giảm dần) hoặc 'flat' (trả đều)")


class MortgageResult(BaseModel):
    property_price: float
    loan_amount: float
    own_capital: float
    tenure_years: int
    tenure_months: int
    annual_interest_rate: float
    method: str
    monthly_principal: float
    first_month_payment: float
    last_month_payment: float
    total_interest: float
    total_payment: float
    summary_markdown: str


class MortgageCalculator:
    """Công cụ tính toán lãi suất vay ngân hàng mua Bất Động Sản tại Việt Nam."""

    @staticmethod
    def calculate(params: MortgageInput) -> MortgageResult:
        tenure_years = max(1, params.tenure_years)
        tenure_months = tenure_years * 12

        # Xác định số tiền vay và vốn tự có
        if params.loan_amount and params.loan_amount > 0:
            loan_amount = float(params.loan_amount)
            property_price = float(params.property_price) if params.property_price else loan_amount
            own_capital = max(0.0, property_price - loan_amount)
        elif params.property_price and params.property_price > 0:
            property_price = float(params.property_price)
            ratio = params.loan_ratio / 100.0 if params.loan_ratio > 1 else params.loan_ratio
            ratio = min(max(ratio, 0.05), 0.9)  # Giới hạn 5% - 90%
            loan_amount = property_price * ratio
            own_capital = property_price - loan_amount
        else:
            # Mặc định giả định gói vay 1 tỷ nếu không cung cấp số tiền
            property_price = 2_000_000_000.0
            loan_amount = 1_400_000_000.0  # 70% của 2 tỷ
            own_capital = 600_000_000.0

        if params.method == "flat":
            return MortgageCalculator._calculate_flat(
                property_price=property_price,
                loan_amount=loan_amount,
                own_capital=own_capital,
                tenure_years=tenure_years,
                tenure_months=tenure_months,
                annual_rate=params.annual_interest_rate
            )
        else:
            return MortgageCalculator._calculate_reducing_balance(
                property_price=property_price,
                loan_amount=loan_amount,
                own_capital=own_capital,
                tenure_years=tenure_years,
                tenure_months=tenure_months,
                annual_rate=params.annual_interest_rate,
                pref_rate=params.preferential_rate,
                pref_months=params.preferential_months
            )

    @staticmethod
    def _calculate_reducing_balance(
        property_price: float,
        loan_amount: float,
        own_capital: float,
        tenure_years: int,
        tenure_months: int,
        annual_rate: float,
        pref_rate: Optional[float] = None,
        pref_months: int = 0
    ) -> MortgageResult:
        monthly_principal = loan_amount / tenure_months
        remaining = loan_amount
        total_interest = 0.0
        first_month_payment = 0.0
        last_month_payment = 0.0

        for month in range(1, tenure_months + 1):
            if pref_rate is not None and month <= pref_months:
                current_annual_rate = pref_rate
            else:
                current_annual_rate = annual_rate

            monthly_interest = remaining * (current_annual_rate / 100.0 / 12.0)
            total_interest += monthly_interest
            total_monthly_pay = monthly_principal + monthly_interest

            if month == 1:
                first_month_payment = total_monthly_pay
            if month == tenure_months:
                last_month_payment = total_monthly_pay

            remaining = max(0.0, remaining - monthly_principal)

        total_payment = loan_amount + total_interest

        summary_md = MortgageCalculator._format_summary(
            property_price=property_price,
            loan_amount=loan_amount,
            own_capital=own_capital,
            tenure_years=tenure_years,
            annual_rate=annual_rate,
            method_name="Dư nợ giảm dần",
            monthly_principal=monthly_principal,
            first_pay=first_month_payment,
            last_pay=last_month_payment,
            total_interest=total_interest,
            total_payment=total_payment,
            pref_rate=pref_rate,
            pref_months=pref_months
        )

        return MortgageResult(
            property_price=property_price,
            loan_amount=loan_amount,
            own_capital=own_capital,
            tenure_years=tenure_years,
            tenure_months=tenure_months,
            annual_interest_rate=annual_rate,
            method="reducing_balance",
            monthly_principal=monthly_principal,
            first_month_payment=first_month_payment,
            last_month_payment=last_month_payment,
            total_interest=total_interest,
            total_payment=total_payment,
            summary_markdown=summary_md
        )

    @staticmethod
    def _calculate_flat(
        property_price: float,
        loan_amount: float,
        own_capital: float,
        tenure_years: int,
        tenure_months: int,
        annual_rate: float
    ) -> MortgageResult:
        r = annual_rate / 100.0 / 12.0
        if r > 0:
            monthly_payment = loan_amount * (r * ((1 + r) ** tenure_months)) / (((1 + r) ** tenure_months) - 1)
        else:
            monthly_payment = loan_amount / tenure_months

        total_payment = monthly_payment * tenure_months
        total_interest = total_payment - loan_amount
        monthly_principal = loan_amount / tenure_months

        summary_md = MortgageCalculator._format_summary(
            property_price=property_price,
            loan_amount=loan_amount,
            own_capital=own_capital,
            tenure_years=tenure_years,
            annual_rate=annual_rate,
            method_name="Trả đều hàng tháng (Niên kim cố định)",
            monthly_principal=monthly_principal,
            first_pay=monthly_payment,
            last_pay=monthly_payment,
            total_interest=total_interest,
            total_payment=total_payment
        )

        return MortgageResult(
            property_price=property_price,
            loan_amount=loan_amount,
            own_capital=own_capital,
            tenure_years=tenure_years,
            tenure_months=tenure_months,
            annual_interest_rate=annual_rate,
            method="flat",
            monthly_principal=monthly_principal,
            first_month_payment=monthly_payment,
            last_month_payment=monthly_payment,
            total_interest=total_interest,
            total_payment=total_payment,
            summary_markdown=summary_md
        )

    @staticmethod
    def _format_summary(
        property_price: float,
        loan_amount: float,
        own_capital: float,
        tenure_years: int,
        annual_rate: float,
        method_name: str,
        monthly_principal: float,
        first_pay: float,
        last_pay: float,
        total_interest: float,
        total_payment: float,
        pref_rate: Optional[float] = None,
        pref_months: int = 0
    ) -> str:
        ratio = (loan_amount / property_price * 100.0) if property_price > 0 else 70.0
        pref_info = f"\n- **Lãi suất ưu đãi**: {pref_rate}%/năm trong {pref_months} tháng đầu" if pref_rate else ""
        
        return (
            f"### 📊 BẢNG TÍNH LÃI VAY NGÂN HÀNG MUA NHÀ\n\n"
            f"**1. Thông tin khoản vay:**\n"
            f"- **Giá trị BĐS**: {property_price:,.0f} VNĐ\n"
            f"- **Số tiền vay ({ratio:.0f}%)**: {loan_amount:,.0f} VNĐ\n"
            f"- **Vốn tự có cần chuẩn bị**: {own_capital:,.0f} VNĐ\n"
            f"- **Thời hạn vay**: {tenure_years} năm ({tenure_years * 12} tháng)\n"
            f"- **Lãi suất áp dụng**: {annual_rate}%/năm{pref_info}\n"
            f"- **Phương thức trả**: {method_name}\n\n"
            f"**2. Kế hoạch thanh toán hàng tháng:**\n"
            f"- **Tiền gốc cố định hàng tháng**: {monthly_principal:,.0f} VNĐ\n"
            f"- **Tháng đầu tiên trả (cao nhất)**: **{first_pay:,.0f} VNĐ** (gồm {monthly_principal:,.0f} gốc + {first_pay - monthly_principal:,.0f} lãi)\n"
            f"- **Tháng cuối cùng trả (thấp nhất)**: **{last_pay:,.0f} VNĐ**\n"
            f"- *(Số tiền phải trả sẽ giảm dần đều qua từng tháng theo dư nợ thực tế)*\n\n"
            f"**3. Tổng kết sau {tenure_years} năm:**\n"
            f"- **Tổng tiền lãi phải trả**: {total_interest:,.0f} VNĐ\n"
            f"- **Tổng số tiền cả gốc và lãi**: **{total_payment:,.0f} VNĐ**\n\n"
            f"> 💡 *Lưu ý: Bảng tính mang tính tham khảo dựa trên quy chuẩn ngân hàng phổ biến (Vietcombank, BIDV, Techcombank, MB...). Chi tiết lãi suất thực tế sẽ phụ thuộc vào gói vay và điểm tín dụng của anh/chị tại thời điểm nộp hồ sơ.*"
        )
