import sys
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

from mortgage_calculator import MortgageCalculator, MortgageInput

# Thư mục gốc backend & đường dẫn tới mortgage_mcp_server.py
backend_dir = Path(__file__).resolve().parent
server_script_path = str(backend_dir / "mortgage_mcp_server.py")


class MortgageToolArgs(BaseModel):
    property_price: Optional[float] = Field(None, description="Tổng giá trị bất động sản bằng VNĐ (ví dụ 2 tỷ = 2000000000)")
    loan_amount: Optional[float] = Field(None, description="Số tiền vay cụ thể bằng VNĐ (ví dụ vay 1.4 tỷ = 1400000000)")
    loan_ratio: Optional[float] = Field(70.0, description="Tỷ lệ vay vốn theo % (mặc định 70 nếu nói 'vay 70%')")
    tenure_years: int = Field(20, description="Thời hạn vay tính theo năm (ví dụ 10, 15, 20, 25 năm)")
    annual_interest_rate: float = Field(8.5, description="Lãi suất năm % (mặc định 8.5%/năm)")
    preferential_rate: Optional[float] = Field(None, description="Lãi suất ưu đãi %/năm trong thời gian đầu nếu có")
    preferential_months: int = Field(0, description="Số tháng được hưởng lãi suất ưu đãi")
    method: str = Field("reducing_balance", description="'reducing_balance' (dư nợ giảm dần) hoặc 'flat' (trả đều)")


# ==================== MCP CLIENT ADAPTER ====================
_MCP_CLIENT: Optional[MultiServerMCPClient] = None
_CACHED_MCP_TOOLS: Optional[List[BaseTool]] = None


def get_mcp_client() -> MultiServerMCPClient:
    """Khởi tạo hoặc lấy instance MultiServerMCPClient kết nối tới Mortgage MCP Server qua stdio transport."""
    global _MCP_CLIENT
    if _MCP_CLIENT is None:
        _MCP_CLIENT = MultiServerMCPClient({
            "mortgage": {
                "transport": "stdio",
                "command": sys.executable,
                "args": [server_script_path],
            }
        })
    return _MCP_CLIENT


def _wrap_tool_for_sync(tool: BaseTool) -> BaseTool:
    """Hỗ trợ cả gọi đồng bộ (.invoke) và bất đồng bộ (.ainvoke) cho LangChain Tool tạo từ MCP Adapter."""
    if hasattr(tool, "coroutine") and tool.coroutine and not getattr(tool, "func", None):
        def _sync_func(*args, **kwargs):
            tool_input = kwargs if kwargs else (args[0] if args else {})
            def _call():
                return asyncio.run(tool.coroutine(**tool_input))
            try:
                res = _call()
            except RuntimeError:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    res = pool.submit(_call).result()

            if getattr(tool, "response_format", None) == "content_and_artifact":
                return (res, res)
            return res

        tool.func = _sync_func
    return tool


async def a_get_mortgage_mcp_tools() -> List[BaseTool]:
    """Lấy danh sách LangChain Tools từ Mortgage MCP Server bất đồng bộ thông qua langchain-mcp-adapters."""
    global _CACHED_MCP_TOOLS
    if _CACHED_MCP_TOOLS is None:
        client = get_mcp_client()
        raw_tools = await client.get_tools()
        _CACHED_MCP_TOOLS = [_wrap_tool_for_sync(t) for t in raw_tools]
    return _CACHED_MCP_TOOLS


def get_mortgage_mcp_tools() -> List[BaseTool]:
    """Lấy danh sách LangChain Tools từ Mortgage MCP Server đồng bộ."""
    global _CACHED_MCP_TOOLS
    if _CACHED_MCP_TOOLS is not None:
        return _CACHED_MCP_TOOLS
    try:
        return asyncio.run(a_get_mortgage_mcp_tools())
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(a_get_mortgage_mcp_tools())).result()


# ==================== CREATE AGENT BẰNG CREATE_AGENT ====================
def create_mortgage_agent(model=None):
    """
    Khởi tạo Agent chuyên trách tính toán tài chính & lãi suất ngân hàng mua BĐS Đà Nẵng
    sử dụng `create_agent` chuẩn của LangChain kết hợp Tool Call từ MCP Adapter.
    """
    tools = get_mortgage_mcp_tools()

    system_prompt = (
        "Bạn là chuyên viên tài chính và ngân hàng cấp cao chuyên tư vấn vay vốn mua bất động sản tại TP. Đà Nẵng.\n"
        "Nhiệm vụ trọng tâm: Khi khách hàng hỏi về vay mua nhà, tính lãi suất, số tiền trả góp hàng tháng, hoặc phương án vay vốn ngân hàng, "
        "bạn BẮT BUỘC phải gọi tool 'calculate_mortgage_loan' được cung cấp qua MCP Client Adapter để có bảng tính toán chính xác.\n"
        "Quy đổi tiền tệ sang VNĐ chính xác: '2 tỷ' -> 2000000000, '1.5 tỷ' -> 1500000000, '800 triệu' -> 800000000.\n"
        "Sau khi nhận kết quả từ tool, bạn hãy:\n"
        "1. Trình bày số tiền gốc và lãi tháng đầu khách hàng cần trả rõ ràng.\n"
        "2. Đưa ra lời khuyên tài chính cá nhân hóa (ví dụ: tỷ lệ an toàn nợ trên thu nhập DTI không vượt quá 40-50%, "
        "chuẩn bị tối thiểu 30% vốn tự có, lưu ý lãi suất thả nổi sau thời gian ưu đãi).\n"
        "Thái độ giao tiếp luôn nhã nhặn, chuyên nghiệp và tận tâm hỗ trợ khách hàng."
    )

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt
    )


# ==================== BACKWARD COMPATIBILITY ====================
class MortgageMCPClientLegacy:
    """Wrapper tương thích ngược cho code cũ khi cần gọi trực tiếp call_tool."""
    def __init__(self, server=None):
        self.server = server

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        inp = MortgageInput(
            property_price=arguments.get("property_price"),
            loan_amount=arguments.get("loan_amount"),
            loan_ratio=arguments.get("loan_ratio", 70.0) or 70.0,
            tenure_years=arguments.get("tenure_years", 20) or 20,
            annual_interest_rate=arguments.get("annual_interest_rate", 8.5) or 8.5,
            preferential_rate=arguments.get("preferential_rate"),
            preferential_months=arguments.get("preferential_months", 0) or 0,
            method=arguments.get("method", "reducing_balance") or "reducing_balance"
        )
        return MortgageCalculator.calculate(inp).summary_markdown


MortgageMCPClient = MortgageMCPClientLegacy
mortgage_mcp_client = MortgageMCPClientLegacy()
mortgage_tools_list = get_mortgage_mcp_tools()
mortgage_langchain_tool = mortgage_tools_list[0] if mortgage_tools_list else None
