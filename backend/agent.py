from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from config import settings
from qdrant_service import qdrant_service

# 1. Định nghĩa Schema bóc tách tiêu chí BĐS (Slot Extraction)
class PropertyCriteria(BaseModel):
    category: Optional[str] = Field(None, description="Loại giao dịch: 'rent' (thuê) hoặc 'sale' (mua bán)")
    property_type: Optional[str] = Field(None, description="'apartment' (căn hộ), 'house' (nhà phố), 'land' (đất), 'villa' (biệt thự)")
    district: Optional[str] = Field(None, description="Quận tại Đà Nẵng: 'Hải Châu', 'Sơn Trà', 'Ngũ Hành Sơn', 'Thanh Khê', 'Cẩm Lệ', 'Liên Chiểu', 'Hòa Vang'")
    max_price: Optional[float] = Field(None, description="Mức giá tối đa (VNĐ)")
    min_bedrooms: Optional[int] = Field(None, description="Số phòng ngủ tối thiểu")
    keywords: Optional[str] = Field(None, description="Từ khóa mô tả: ví dụ 'gần biển', 'view sông Hàn', 'kiệt ô tô'")
    needs_clarification: bool = Field(False, description="True nếu thông tin người dùng quá mơ hồ cần hỏi thêm")
    customer_phone: Optional[str] = Field(None, description="Số điện thoại hoặc Zalo nếu khách hàng muốn để lại liên hệ")

# Hàm merge tiêu chí giữa các turns trong cùng thread
def merge_criteria(existing: Optional[Dict[str, Any]], update: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = dict(existing or {})
    if update:
        for k, v in update.items():
            if v is not None:
                merged[k] = v
    return merged

# 2. Định nghĩa State của Agent sử dụng add_messages reducer để không bị ghi đè lịch sử
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    criteria: Optional[Dict[str, Any]]
    found_properties: List[Dict[str, Any]]

# Khởi tạo LLM
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL_NAME,
    api_key=settings.OPENAI_API_KEY or "dummy_key_mock",
    temperature=0.2
)

# 3. Node 1: Phân tích Ý định & Bóc tách Tiêu chí (NLU / Slot Extraction có ngữ cảnh lịch sử)
def extract_criteria_node(state: AgentState) -> Dict[str, Any]:
    all_messages = state.get("messages", [])
    last_user_message = all_messages[-1].content if all_messages else ""
    current_criteria = state.get("criteria") or {}
    
    # Prompt bóc tách
    system_prompt = (
        "Bạn là chuyên gia tư vấn Bất động sản tại thành phố Đà Nẵng. "
        "Hãy phân tích lịch sử hội thoại và trích xuất các tiêu chí tìm kiếm mới nhất theo JSON schema được cung cấp. "
        "Các quận hợp lệ tại Đà Nẵng: Hải Châu, Thanh Khê, Sơn Trà, Ngũ Hành Sơn, Cẩm Lệ, Liên Chiểu, Hòa Vang. "
        "Nếu người dùng bổ sung thêm tiêu chí (ví dụ: giá, số phòng), hãy trích xuất tiêu chí mới mà không làm mất thông tin cũ."
    )
    
    try:
        extractor = llm.with_structured_output(PropertyCriteria)
        # Truyền cả ngữ cảnh lịch sử hội thoại vào extractor
        context_messages = [SystemMessage(content=system_prompt)]
        for m in all_messages[-6:]:  # 6 tin nhắn gần nhất
            context_messages.append(m)
            
        criteria_obj = extractor.invoke(context_messages)
        new_criteria = criteria_obj.dict()
    except Exception:
        # Fallback phân tích cơ bản bằng rule nếu OpenAI API không khả dụng
        new_criteria = {
            "category": "rent" if "thuê" in last_user_message.lower() else ("sale" if "mua" in last_user_message.lower() else None),
            "district": "Sơn Trà" if "sơn trà" in last_user_message.lower() else ("hải châu" if "hải châu" in last_user_message.lower() else ("liên chiểu" if "liên chiểu" in last_user_message.lower() else None)),
            "max_price": 15000000.0 if "15 triệu" in last_user_message.lower() or "15000000" in last_user_message else None,
            "min_bedrooms": None,
            "keywords": last_user_message,
            "needs_clarification": False,
            "customer_phone": None
        }

    # Merge tiêu chí cũ và mới để duy trì context
    updated_criteria = merge_criteria(current_criteria, new_criteria)
    return {"criteria": updated_criteria}

# 4. Node 2: Tìm kiếm trong Qdrant
def search_properties_node(state: AgentState) -> Dict[str, Any]:
    criteria = state.get("criteria", {}) or {}
    all_messages = state.get("messages", [])
    last_msg = all_messages[-1].content if all_messages else ""
    query_text = criteria.get("keywords") or last_msg
    
    properties = qdrant_service.search_properties(
        query=query_text,
        category=criteria.get("category"),
        district=criteria.get("district"),
        max_price=criteria.get("max_price"),
        min_bedrooms=criteria.get("min_bedrooms"),
        limit=3
    )
    return {"found_properties": properties}

# 5. Node 3: Sinh phản hồi trả về cho khách (Generator có nhớ ngữ cảnh)
def generate_response_node(state: AgentState) -> Dict[str, Any]:
    properties = state.get("found_properties", [])
    all_messages = state.get("messages", [])
    criteria = state.get("criteria", {}) or {}

    if criteria.get("customer_phone"):
        reply_text = f"Dạ em đã nhận được thông tin số điện thoại {criteria['customer_phone']}. Chuyên viên tư vấn khu vực Đà Nẵng sẽ liên hệ lại qua Zalo/Điện thoại với anh/chị ngay ạ!"
        return {"messages": [AIMessage(content=reply_text)]}

    if not properties:
        reply_text = "Hiện tại em chưa tìm thấy bất động sản nào khớp hoàn toàn với yêu cầu trên. Anh/chị có thể nới lỏng ngân sách hoặc mở rộng sang các quận lân cận không ạ?"
        return {"messages": [AIMessage(content=reply_text)]}

    # Tạo prompt tổng hợp
    context_desc = "\n".join([
        f"- {p['title']} ({p['district']}): {p['price']:,} VNĐ. {p['description']}"
        for p in properties
    ])
    
    system_prompt = f"""Bạn là tư vấn viên BĐS chuyên nghiệp tại Đà Nẵng.
Dưới đây là các căn nhà phù hợp nhất được tìm thấy từ hệ thống:
{context_desc}

Hãy đọc toàn bộ lịch sử trao đổi của khách hàng, viết phản hồi ngắn gọn, thân thiện, giải đáp đúng trọng tâm câu hỏi mới nhất, làm nổi bật ưu điểm của các căn và chủ động gợi ý khách đặt lịch xem nhà."""

    # Chuẩn bị tin nhắn gửi cho LLM bao gồm cả lịch sử
    chat_prompt: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    for m in all_messages[-6:]:
        chat_prompt.append(m)

    try:
        response = llm.invoke(chat_prompt)
        reply = AIMessage(content=response.content)
    except Exception:
        reply = AIMessage(content=f"Dạ em xin gửi anh/chị {len(properties)} bất động sản phù hợp nhất tại Đà Nẵng theo yêu cầu. Anh/chị có muốn em hỗ trợ đặt lịch đi xem thực tế căn nào không ạ?")

    # Trả về AIMessage; nhờ add_messages reducer nó sẽ tự động nối vào lịch sử của thread
    return {"messages": [reply]}

# 6. Thiết lập LangGraph Workflow
workflow = StateGraph(AgentState)
workflow.add_node("extract_criteria", extract_criteria_node)
workflow.add_node("search_properties", search_properties_node)
workflow.add_node("generate_response", generate_response_node)

workflow.set_entry_point("extract_criteria")
workflow.add_edge("extract_criteria", "search_properties")
workflow.add_edge("search_properties", "generate_response")
workflow.add_edge("generate_response", END)

# Checkpointer lưu state bộ nhớ cho từng thread_id
memory = MemorySaver()
real_estate_agent = workflow.compile(checkpointer=memory)
