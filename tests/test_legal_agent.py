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

    # Kiểm tra số lượng citations trả về khớp với các số trích dẫn xuất hiện trong bot message
    import re
    cited_nums = set(int(n) for n in re.findall(r"\[(\d+)\]", bot_message.content))
    if cited_nums:
        assert len(citations) == len(cited_nums)
        for c in citations:
            assert c["index"] in cited_nums

def test_subsequent_non_legal_message_clears_citations():
    """
    Kiểm tra multi-turn:
    Sau khi hỏi câu hỏi pháp lý và nhận citations, lượt tiếp theo nếu người dùng
    hỏi câu hỏi thông thường (general_chat) hoặc tìm BĐS, state citations phải được reset về rỗng ([])
    để không hiển thị nhầm nút căn cứ pháp lý trên UI.
    """
    thread_id = "test_tdd_multi_turn_citations_002"
    config = {
        "configurable": {"thread_id": thread_id},
        "tags": ["test_legal", thread_id],
    }

    # Lượt 1: Hỏi câu pháp lý
    legal_query = "Người nước ngoài có được mua căn hộ chung cư ở Đà Nẵng không?"
    state_turn1 = real_estate_agent.invoke({"messages": [HumanMessage(content=legal_query)]}, config=config)
    assert state_turn1["intent"] == "legal_consultation"
    assert len(state_turn1.get("citations", [])) > 0

    # Lượt 2: Người dùng cảm ơn hoặc chào hỏi thông thường
    chat_query = "Dạ em cảm ơn anh/chị nhiều nhé!"
    state_turn2 = real_estate_agent.invoke({"messages": [HumanMessage(content=chat_query)]}, config=config)
    assert state_turn2["intent"] == "general_chat"
    assert state_turn2.get("citations") == []
