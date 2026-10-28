from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from config import settings
from qdrant_service import qdrant_service

# 1. Định nghĩa Schema phân loại ý định (Router Agent)
class IntentClassification(BaseModel):
    intent: Literal["general_chat", "search_property"] = Field(
        ...,
        description=(
            "'search_property': người dùng có nhu cầu tìm kiếm, thuê, mua, hỏi giá, tư vấn căn hộ, nhà phố, đất đai cụ thể tại Đà Nẵng.\n"
            "'general_chat': người dùng chào hỏi, giao tiếp thông thường, hỏi thông tin chung/pháp lý/văn hóa mà không có nhu cầu tìm BĐS cụ thể."
        )
    )
    reason: Optional[str] = Field(None, description="Lý do phân loại ý định")

# Schema bóc tách tiêu chí BĐS (Slot Extraction)
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

# 2. Định nghĩa State của Agent
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    intent: Optional[str]
    criteria: Optional[Dict[str, Any]]
    found_properties: List[Dict[str, Any]]

# Khởi tạo LLM
llm = ChatOpenAI(
    model=settings.OPENAI_MODEL_NAME,
    api_key=settings.OPENAI_API_KEY or "dummy_key_mock",
    temperature=0.2
)

# 3. Node 0: Router Agent điều phối ý định
def route_intent_node(state: AgentState) -> Dict[str, Any]:
    all_messages = state.get("messages", [])
    last_user_message = all_messages[-1].content if all_messages else ""

    system_prompt = (
        "Bạn là chuyên gia điều phối luồng trò chuyện cho trợ lý ảo Bất động sản Đà Nẵng.\n"
        "Nhiệm vụ: Phân loại ý định của người dùng dựa trên tin nhắn gần nhất và lịch sử hội thoại thành 1 trong 2 loại:\n"
        "1. 'search_property': người dùng muốn tìm kiếm, xem, hỏi thuê/mua nhà, căn hộ, đất đai, villa cụ thể.\n"
        "2. 'general_chat': người dùng chào hỏi, cảm ơn, hỏi thời tiết, hỏi bạn là ai, hỏi thủ tục/kiến thức chung không kèm nhu cầu tra cứu BĐS cụ thể."
    )

    try:
        classifier = llm.with_structured_output(IntentClassification)
        context_messages = [SystemMessage(content=system_prompt)]
        for m in all_messages[-4:]:
            context_messages.append(m)
        result = classifier.invoke(context_messages)
        intent = result.intent
    except Exception:
        # Heuristic fallback an toàn
        text_lower = last_user_message.lower()
        search_keywords = ["thuê", "mua", "bán", "căn hộ", "chung cư", "nhà phố", "phòng ngủ", "triệu", "tỷ", "sơn trà", "hải châu", "ngũ hành sơn", "thanh khê", "cẩm lệ", "liên chiểu", "tìm"]
        if any(kw in text_lower for kw in search_keywords):
            intent = "search_property"
        else:
            intent = "general_chat"

    return {"intent": intent}

# Conditional Edge router function
def decide_route(state: AgentState) -> str:
    if state.get("intent") == "general_chat":
        return "general_chat_response"
    return "extract_criteria"

# 4. Node General Chat Response (suy luận trả lời trực tiếp, không search Qdrant)
def general_chat_response_node(state: AgentState) -> Dict[str, Any]:
    all_messages = state.get("messages", [])
    
    system_prompt = (
        "Bạn là trợ lý AI chuyên gia tư vấn Bất động sản và am hiểu đời sống, du lịch, pháp lý tại TP. Đà Nẵng.\n"
        "Hãy phản hồi người dùng một cách thân thiện, lịch sự, giải đáp tự nhiên câu hỏi hoặc lời chào của họ. "
        "Nếu phù hợp, hãy khéo léo giới thiệu bạn có thể hỗ trợ tra cứu, tìm kiếm căn hộ, nhà phố hoặc biệt thự lý tưởng tại Đà Nẵng."
    )

    chat_prompt: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    for m in all_messages[-6:]:
        chat_prompt.append(m)

    try:
        response = llm.invoke(chat_prompt)
        reply = AIMessage(content=response.content)
    except Exception:
        reply = AIMessage(content="Xin chào anh/chị! Em là trợ lý AI tư vấn Bất động sản tại thành phố Đà Nẵng. Em có thể hỗ trợ anh/chị tìm thuê hoặc mua căn hộ, nhà phố, đất nền theo ngân sách và vị trí mong muốn ạ!")

    return {
        "messages": [reply],
        "found_properties": []
    }

# 5. Node 1: Phân tích Ý định & Bóc tách Tiêu chí (NLU / Slot Extraction)
def extract_criteria_node(state: AgentState) -> Dict[str, Any]:
    all_messages = state.get("messages", [])
    last_user_message = all_messages[-1].content if all_messages else ""
    current_criteria = state.get("criteria") or {}
    
    system_prompt = (
        "Bạn là chuyên gia tư vấn Bất động sản tại thành phố Đà Nẵng. "
        "Hãy phân tích lịch sử hội thoại và trích xuất các tiêu chí tìm kiếm mới nhất theo JSON schema được cung cấp. "
        "Các quận hợp lệ tại Đà Nẵng: Hải Châu, Thanh Khê, Sơn Trà, Ngũ Hành Sơn, Cẩm Lệ, Liên Chiểu, Hòa Vang. "
        "Nếu người dùng bổ sung thêm tiêu chí (ví dụ: giá, số phòng), hãy trích xuất tiêu chí mới mà không làm mất thông tin cũ."
    )
    
    try:
        extractor = llm.with_structured_output(PropertyCriteria)
        context_messages = [SystemMessage(content=system_prompt)]
        for m in all_messages[-6:]:
            context_messages.append(m)
            
        criteria_obj = extractor.invoke(context_messages)
        new_criteria = criteria_obj.dict()
    except Exception:
        new_criteria = {
            "category": "rent" if "thuê" in last_user_message.lower() else ("sale" if "mua" in last_user_message.lower() else None),
            "district": "Sơn Trà" if "sơn trà" in last_user_message.lower() else ("hải châu" if "hải châu" in last_user_message.lower() else ("liên chiểu" if "liên chiểu" in last_user_message.lower() else None)),
            "max_price": 15000000.0 if "15 triệu" in last_user_message.lower() or "15000000" in last_user_message else None,
            "min_bedrooms": 2 if "2 phòng ngủ" in last_user_message.lower() or "2pn" in last_user_message.lower() else None,
            "keywords": last_user_message,
            "needs_clarification": False,
            "customer_phone": None
        }

    updated_criteria = merge_criteria(current_criteria, new_criteria)
    return {"criteria": updated_criteria}

# 6. Node 2: Tìm kiếm trong Qdrant
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

# 7. Node 3: Sinh phản hồi tư vấn BĐS
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

    context_desc = "\n".join([
        f"- {p['title']} ({p['district']}): {p['price']:,} VNĐ. {p['description']}"
        for p in properties
    ])
    
    system_prompt = f"""Bạn là tư vấn viên BĐS chuyên nghiệp tại Đà Nẵng.
Dưới đây là các căn nhà phù hợp nhất được tìm thấy từ hệ thống:
{context_desc}

Hãy đọc toàn bộ lịch sử trao đổi của khách hàng, viết phản hồi ngắn gọn, thân thiện, giải đáp đúng trọng tâm câu hỏi mới nhất, làm nổi bật ưu điểm của các căn và chủ động gợi ý khách đặt lịch xem nhà."""

    chat_prompt: List[BaseMessage] = [SystemMessage(content=system_prompt)]
    for m in all_messages[-6:]:
        chat_prompt.append(m)

    try:
        response = llm.invoke(chat_prompt)
        reply = AIMessage(content=response.content)
    except Exception:
        reply = AIMessage(content=f"Dạ em xin gửi anh/chị {len(properties)} bất động sản phù hợp nhất tại Đà Nẵng theo yêu cầu. Anh/chị có muốn em hỗ trợ đặt lịch đi xem thực tế căn nào không ạ?")

    return {"messages": [reply]}

# 8. Thiết lập LangGraph Workflow với Router Dispatcher
workflow = StateGraph(AgentState)
workflow.add_node("route_intent", route_intent_node)
workflow.add_node("general_chat_response", general_chat_response_node)
workflow.add_node("extract_criteria", extract_criteria_node)
workflow.add_node("search_properties", search_properties_node)
workflow.add_node("generate_response", generate_response_node)

# Entry point vào Router Agent
workflow.set_entry_point("route_intent")

# Rẽ nhánh có điều kiện
workflow.add_conditional_edges(
    "route_intent",
    decide_route,
    {
        "general_chat_response": "general_chat_response",
        "extract_criteria": "extract_criteria"
    }
)

workflow.add_edge("general_chat_response", END)
workflow.add_edge("extract_criteria", "search_properties")
workflow.add_edge("search_properties", "generate_response")
workflow.add_edge("generate_response", END)

# Checkpointer lưu state bộ nhớ cho từng thread_id
memory = MemorySaver()
real_estate_agent = workflow.compile(checkpointer=memory)
