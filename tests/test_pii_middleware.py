import sys
import os
import pytest
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents.middleware import (
    PIIMiddleware,
    PIIDetectionError,
    HumanInTheLoopMiddleware
)
from agent import (
    pii_middlewares,
    sanitize_messages_pii,
    route_intent_node,
    property_agent
)


def test_pii_email_redaction():
    """Kiểm tra email trong tin nhắn người dùng được tự động redact thành [REDACTED_EMAIL]"""
    email_middleware = PIIMiddleware("email", strategy="redact", apply_to_input=True)
    state = {
        "messages": [
            HumanMessage(content="Tôi quan tâm căn hộ Monarchy, hãy gửi bảng giá qua email contact@danangrealestate.vn nhé")
        ]
    }
    result = email_middleware.before_model(state, None)
    assert result is not None
    updated_msg = result["messages"][0]
    assert "contact@danangrealestate.vn" not in updated_msg.content
    assert "[REDACTED_EMAIL]" in updated_msg.content


def test_pii_credit_card_masking():
    """Kiểm tra số thẻ tín dụng hợp lệ được che bằng ký tự * chỉ để lại 4 số cuối"""
    card_middleware = PIIMiddleware("credit_card", strategy="mask", apply_to_input=True)
    # 4532015112830366 là số thẻ Visa hợp lệ theo thuật toán Luhn
    state = {
        "messages": [
            HumanMessage(content="Tôi muốn đặt cọc giữ chỗ 50 triệu qua thẻ tín dụng 4532015112830366 ngay hôm nay")
        ]
    }
    result = card_middleware.before_model(state, None)
    assert result is not None
    updated_msg = result["messages"][0]
    assert "4532015112830366" not in updated_msg.content
    assert "************0366" in updated_msg.content


def test_pii_api_key_blocking():
    """Kiểm tra phát hiện OpenAI API key dạng sk-... và kích hoạt PIIDetectionError"""
    key_middleware = PIIMiddleware(
        "api_key",
        detector=r"sk-[a-zA-Z0-9]{32}",
        strategy="block",
        apply_to_input=True
    )
    fake_key = "sk-12345678901234567890123456789012"
    state = {
        "messages": [
            HumanMessage(content=f"Dùng khóa bí mật này để cấu hình: {fake_key}")
        ]
    }
    with pytest.raises(PIIDetectionError) as exc_info:
        key_middleware.before_model(state, None)
    assert "api_key" in str(exc_info.value)


def test_sanitize_messages_pii_combined():
    """Kiểm tra hàm helper sanitize_messages_pii xử lý kết hợp email + card và chặn API key"""
    msg = HumanMessage(
        content="Khách hàng email: customer@example.com muốn thanh toán qua thẻ 4532015112830366"
    )
    sanitized = sanitize_messages_pii([msg])
    assert len(sanitized) == 1
    content = sanitized[0].content
    assert "[REDACTED_EMAIL]" in content
    assert "************0366" in content
    assert "customer@example.com" not in content
    assert "4532015112830366" not in content

    # Chặn API key
    bad_msg = HumanMessage(content="Khóa của tôi: sk-99998888777766665555444433332222")
    with pytest.raises(PIIDetectionError):
        sanitize_messages_pii([bad_msg])


def test_route_intent_node_blocks_api_key():
    """Kiểm tra router node tự động bắt PIIDetectionError và trả về rule_violation cùng cảnh báo bảo mật"""
    state = {
        "messages": [
            HumanMessage(content="Kiểm tra hệ thống với key sk-abcdef1234567890abcdef1234567890")
        ]
    }
    output = route_intent_node(state)
    assert output["intent"] == "rule_violation"
    assert "messages" in output
    assert len(output["messages"]) == 1
    assert "⚠️ [Cảnh báo An toàn & Bảo mật]" in output["messages"][0].content


def test_route_intent_node_redacts_and_masks_for_property_search():
    """Kiểm tra router node tự động sanitize email và thẻ trong tin nhắn tìm BĐS"""
    state = {
        "messages": [
            HumanMessage(
                content="Tôi muốn thuê căn hộ 2 phòng ngủ Sơn Trà, gửi báo giá về test@domain.com, số thẻ đặt cọc 4532015112830366"
            )
        ]
    }
    output = route_intent_node(state)
    assert output["intent"] == "search_property"
    assert "messages" in output
    updated_content = output["messages"][0].content
    assert "[REDACTED_EMAIL]" in updated_content
    assert "************0366" in updated_content
    assert "test@domain.com" not in updated_content
    assert "4532015112830366" not in updated_content
