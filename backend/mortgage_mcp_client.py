import asyncio
from typing import Optional, Dict, Any, List
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from mortgage_mcp_server import mortgage_mcp_server


class MortgageToolArgs(BaseModel):
    property_price: Optional[float] = Field(None, description="Tổng giá trị bất động sản bằng VNĐ (ví dụ 2 tỷ = 2000000000)")
    loan_amount: Optional[float] = Field(None, description="Số tiền vay cụ thể bằng VNĐ (ví dụ vay 1.4 tỷ = 1400000000)")
    loan_ratio: Optional[float] = Field(70.0, description="Tỷ lệ vay vốn theo % (mặc định 70 nếu nói 'vay 70%')")
    tenure_years: int = Field(20, description="Thời hạn vay tính theo năm (ví dụ 10, 15, 20, 25 năm)")
    annual_interest_rate: float = Field(8.5, description="Lãi suất năm % (mặc định 8.5%/năm)")
    preferential_rate: Optional[float] = Field(None, description="Lãi suất ưu đãi %/năm trong thời gian đầu nếu có")
    preferential_months: int = Field(0, description="Số tháng được hưởng lãi suất ưu đãi")
    method: str = Field("reducing_balance", description="'reducing_balance' (dư nợ giảm dần) hoặc 'flat' (trả đều)")


class MortgageMCPClient:
    """MCP Client kết nối tới Mortgage MCP Server và điều phối thực thi Tool cho LLM."""

    def __init__(self, server=None):
        self.server = server or mortgage_mcp_server

    async def a_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Gọi thực thi Tool bất đồng bộ trên MCP Server theo giao thức MCP."""
        call_result = await self.server.call_tool(tool_name, arguments)
        if call_result.content:
            texts = [c.text for c in call_result.content if hasattr(c, "text")]
            return "\n".join(texts)
        return ""

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Gọi thực thi Tool đồng bộ cho LangChain Tool execution."""
        try:
            return asyncio.run(self.a_call_tool(tool_name, arguments))
        except RuntimeError:
            import concurrent.futures

            def _run() -> str:
                return asyncio.run(self.a_call_tool(tool_name, arguments))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(_run).result()

    def get_langchain_tool(self) -> StructuredTool:
        """Chuyển đổi MCP Tool thành LangChain StructuredTool để LLM bind và gọi."""
        def _execute_tool(
            property_price: Optional[float] = None,
            loan_amount: Optional[float] = None,
            loan_ratio: Optional[float] = 70.0,
            tenure_years: int = 20,
            annual_interest_rate: float = 8.5,
            preferential_rate: Optional[float] = None,
            preferential_months: int = 0,
            method: str = "reducing_balance"
        ) -> str:
            args = {
                "property_price": property_price,
                "loan_amount": loan_amount,
                "loan_ratio": loan_ratio,
                "tenure_years": tenure_years,
                "annual_interest_rate": annual_interest_rate,
                "preferential_rate": preferential_rate,
                "preferential_months": preferential_months,
                "method": method
            }
            return self.call_tool("calculate_mortgage_loan", args)

        return StructuredTool.from_function(
            func=_execute_tool,
            name="calculate_mortgage_loan",
            description=(
                "Công cụ tính lãi suất vay ngân hàng mua nhà đất tại Đà Nẵng qua MCP Client.\n"
                "Sử dụng khi người dùng hỏi mua nhà trả góp, vay ngân hàng bao nhiêu tiền mỗi tháng, "
                "bảng tính dư nợ giảm dần hoặc trả đều."
            ),
            args_schema=MortgageToolArgs
        )


# Singleton instance MCP Client
mortgage_mcp_client = MortgageMCPClient()
mortgage_langchain_tool = mortgage_mcp_client.get_langchain_tool()
