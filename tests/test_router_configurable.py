import pytest
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import settings
from agent import create_router_llm, set_router_model, router_llm


def test_router_llm_decoupled_from_primary_settings():
    """
    Test Task 1: Kiểm tra mô hình Decision / Router được tách biệt khỏi cấu hình chính
    - Mặc định khi chưa đặt ROUTER_MODEL_NAME thì fallback về OPENAI_MODEL_NAME
    - Cho phép khởi tạo router LLM với model bất kỳ
    """
    default_router = create_router_llm()
    assert default_router.model_name in [settings.OPENAI_MODEL_NAME, settings.ROUTER_MODEL_NAME or settings.OPENAI_MODEL_NAME]
    assert default_router.temperature == 0.0  # Temperature 0 tối ưu cho decision routing

    # Thử khởi tạo với custom model bất kỳ (ví dụ: Qwen2.5-7B hoặc gpt-4o hoặc llama-3)
    custom_router = create_router_llm(
        model_name="qwen2.5-7b-instruct",
        base_url="http://localhost:11434/v1",
        api_key="ollama_mock_key"
    )
    assert custom_router.model_name == "qwen2.5-7b-instruct"
    assert str(custom_router.openai_api_base).rstrip("/") == "http://localhost:11434/v1"


def test_set_router_model_dynamically():
    """
    Test Task 1: Kiểm tra hoán đổi mô hình Decision trong lúc chạy (runtime swap)
    """
    original_model = settings.OPENAI_MODEL_NAME
    # Đổi sang decision model khác
    set_router_model("gpt-4o-mini-decision")
    from agent import router_llm as active_llm
    assert active_llm.model_name == "gpt-4o-mini-decision"

    # Trả lại model ban đầu
    set_router_model(original_model)
    from agent import router_llm as restored_llm
    assert restored_llm.model_name == original_model
