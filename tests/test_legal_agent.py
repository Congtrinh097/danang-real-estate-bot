import os
import sys
import pytest

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage
from agent import real_estate_agent
from legal_service import legal_service

@pytest.fixture(scope="module", autouse=True)
def setup_sample_legal_data():
    # Đảm bảo có dữ liệu mẫu được index
    docs = legal_service.list_documents()
    sample_doc = next((d for d in docs if "sample_luat_nha_o" in d["id"]), None)
    if not sample_doc:
        sample_path = os.path.join(backend_dir, "data", "legal_docs", "sample_luat_nha_o.md")
        with open(sample_path, "r", encoding="utf-8") as f:
            content = f.read()
        meta = legal_service.save_document("sample_luat_nha_o.md", content, doc_id="sample_luat_nha_o")
        legal_service.index_document("sample_luat_nha_o")
    elif sample_doc.get("status") != "indexed":
        legal_service.index_document(sample_doc["id"])

def test_legal_consultation_intent_and_citations():
    """
    Test theo TDD:
    Khi người dùng hỏi câu hỏi pháp lý:
    1. Intent phải được phân loại là 'legal_consultation'
    2. Agent gọi legal_advisory_node
    3. State trả về danh sách citations chứa các điều luật liên quan
    4. Phản hồi bot trích dẫn văn bản pháp lý (chứa [1] hoặc viện dẫn luật)
    5. Không kích hoạt tìm kiếm BĐS (found_properties rỗng)
    """
    thread_id = "test_tdd_legal_001"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_legal", thread_id],
    }

    query = "Người nước ngoài có được mua và sở hữu căn hộ chung cư tại Đà Nẵng không?"
    inputs = {"messages": [HumanMessage(content=query)]}

    final_state = real_estate_agent.invoke(inputs, config=config)

    assert final_state["intent"] == "legal_consultation"
    assert final_state.get("found_properties") == []
    
    citations = final_state.get("citations")
    assert citations is not None
    assert len(citations) > 0
    assert any("19" in str(c.get("article", "")) or "nước ngoài" in c.get("content", "").lower() for c in citations)

    bot_message = final_state["messages"][-1]
    assert "[1]" in bot_message.content or "Luật Nhà ở" in bot_message.content
