from typing import Dict, Any, Optional
from pydantic import BaseModel
from .settings import agentops_settings

class ModelPricing(BaseModel):
    provider: str
    model_name: str
    input_price_per_million_usd: float
    output_price_per_million_usd: float
    cached_input_price_per_million_usd: float = 0.0
    reasoning_price_per_million_usd: Optional[float] = None
    currency: str = "USD"
    effective_date: str = "2026-01-01"

class PricingRegistry:
    """
    Bảng tra cứu giá niêm yết chính thức của các mô hình LLM.
    Đơn vị chuẩn hóa: USD / 1 Triệu Tokens.
    """
    def __init__(self):
        self._pricing: Dict[str, ModelPricing] = {
            # OpenAI Models chính thức
            "gpt-4o-mini": ModelPricing(
                provider="openai",
                model_name="gpt-4o-mini",
                input_price_per_million_usd=0.15,
                output_price_per_million_usd=0.60,
                cached_input_price_per_million_usd=0.075
            ),
            "gpt-4o": ModelPricing(
                provider="openai",
                model_name="gpt-4o",
                input_price_per_million_usd=2.50,
                output_price_per_million_usd=10.00,
                cached_input_price_per_million_usd=1.25
            ),
            "gpt-4o-2024-08-06": ModelPricing(
                provider="openai",
                model_name="gpt-4o-2024-08-06",
                input_price_per_million_usd=2.50,
                output_price_per_million_usd=10.00,
                cached_input_price_per_million_usd=1.25
            ),
            "text-embedding-3-small": ModelPricing(
                provider="openai",
                model_name="text-embedding-3-small",
                input_price_per_million_usd=0.02,
                output_price_per_million_usd=0.0,
                cached_input_price_per_million_usd=0.0
            ),
            "text-embedding-3-large": ModelPricing(
                provider="openai",
                model_name="text-embedding-3-large",
                input_price_per_million_usd=0.13,
                output_price_per_million_usd=0.0,
                cached_input_price_per_million_usd=0.0
            ),
            # Model Judge Model
            "gpt-6-luna": ModelPricing(
                provider="openai",
                model_name="gpt-6-luna",
                input_price_per_million_usd=0.50,
                output_price_per_million_usd=1.50,
                cached_input_price_per_million_usd=0.25
            ),
            "openai/gpt-4o-mini": ModelPricing(
                provider="openrouter",
                model_name="openai/gpt-4o-mini",
                input_price_per_million_usd=0.15,
                output_price_per_million_usd=0.60,
                cached_input_price_per_million_usd=0.075
            ),
            "typesafe/jev-1.14": ModelPricing(
                provider="openrouter",
                model_name="typesafe/jev-1.14",
                input_price_per_million_usd=0.20,
                output_price_per_million_usd=0.80,
                cached_input_price_per_million_usd=0.10
            ),
        }
        # Safe fallback pricing (giá dự phòng an toàn cho mô hình lạ)
        self._default_fallback_pricing = ModelPricing(
            provider="unknown",
            model_name="default_fallback",
            input_price_per_million_usd=0.50,
            output_price_per_million_usd=2.00,
            cached_input_price_per_million_usd=0.25
        )

    def get_pricing(self, model_name: str) -> ModelPricing:
        """Tra cứu giá theo model name, tự động chuẩn hóa chuỗi"""
        if not model_name:
            return self._default_fallback_pricing

        key = model_name.strip().lower()
        if key in self._pricing:
            return self._pricing[key]
        
        # Thử tìm partial match (ví dụ: gpt-4o-mini-2024-07-18 -> gpt-4o-mini)
        for name, pricing in self._pricing.items():
            if name in key:
                return pricing
                
        return self._default_fallback_pricing

    def register_pricing(self, pricing: ModelPricing):
        self._pricing[pricing.model_name.strip().lower()] = pricing

pricing_registry = PricingRegistry()
