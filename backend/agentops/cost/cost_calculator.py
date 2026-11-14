from typing import Optional, Tuple
from pydantic import BaseModel
from ..config.pricing_registry import pricing_registry, ModelPricing
from ..config.settings import agentops_settings

class CostCalculationResult(BaseModel):
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    total_tokens: int
    cost_usd: float
    cost_vnd: float
    pricing_applied: ModelPricing

class CostCalculator:
    """
    Tính toán chi phí dựa trên token usage và pricing registry chính thức.
    """
    def __init__(self, usd_to_vnd_rate: Optional[float] = None):
        self.usd_to_vnd_rate = usd_to_vnd_rate or agentops_settings.AGENTOPS_USD_TO_VND_RATE

    def calculate_cost(
        self,
        model_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0
    ) -> CostCalculationResult:
        pricing = pricing_registry.get_pricing(model_name)

        # Tính toán chi phí USD: tokens * price / 1_000_000
        # Lưu ý: Các token đã cache được tính giá ưu đãi nếu có
        normal_input_tokens = max(0, input_tokens - cached_tokens)
        
        input_cost = (normal_input_tokens * pricing.input_price_per_million_usd) / 1_000_000.0
        cached_cost = (cached_tokens * pricing.cached_input_price_per_million_usd) / 1_000_000.0
        output_cost = (output_tokens * pricing.output_price_per_million_usd) / 1_000_000.0
        
        total_cost_usd = input_cost + cached_cost + output_cost
        total_cost_vnd = total_cost_usd * self.usd_to_vnd_rate
        total_tokens = input_tokens + output_tokens + reasoning_tokens

        return CostCalculationResult(
            model_name=model_name,
            provider=pricing.provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            cost_usd=round(total_cost_usd, 6),
            cost_vnd=round(total_cost_vnd, 4),
            pricing_applied=pricing
        )

    def estimate_call_cost_vnd(
        self,
        model_name: str,
        estimated_input_tokens: int = 1500,
        estimated_output_tokens: int = 500
    ) -> float:
        """Ước tính chi phí cuộc gọi sắp tới phục vụ việc giữ chỗ (Reservation)"""
        res = self.calculate_cost(
            model_name=model_name,
            input_tokens=estimated_input_tokens,
            output_tokens=estimated_output_tokens
        )
        return res.cost_vnd

cost_calculator = CostCalculator()
