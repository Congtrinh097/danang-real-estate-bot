"""
A2A Council (War Room) Module for Multi-Agent Investment & Risk Analysis in Da Nang Real Estate.
Target: backend/a2a_council.py
"""

from enum import Enum
from typing import Annotated, Sequence, TypedDict, Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
import operator
import time
from langchain_core.messages import BaseMessage


class CouncilSpeaker(str, Enum):
    PLANNER = "planner"
    PROPERTY_EXPERT = "property_expert"
    FINANCIAL_ANALYST = "financial_analyst"
    LEGAL_ADVISOR = "legal_advisor"
    CRITIC = "adversarial_critic"
    SYNTHESIZER = "council_synthesizer"


class CouncilDebateTurn(BaseModel):
    speaker: CouncilSpeaker
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class CouncilVerdict(BaseModel):
    overall_feasibility: Literal["feasible", "caution_required", "high_risk"]
    feasibility_score: int = Field(..., ge=0, le=100)
    summary_recommendation: str
    property_match: Optional[Dict[str, Any]] = None
    financial_summary: Optional[Dict[str, Any]] = None
    legal_risks: List[str] = Field(default_factory=list)
    critic_caveats: List[str] = Field(default_factory=list)
    action_checklist: List[str] = Field(default_factory=list)


class A2ACouncilState(TypedDict):
    messages: Sequence[BaseMessage]
    user_query: str
    equity_capital: float
    target_price: float
    target_district: str
    property_findings: List[Dict[str, Any]]
    mortgage_analysis: Dict[str, Any]
    legal_citations: List[Dict[str, Any]]
    debate_history: Annotated[List[CouncilDebateTurn], operator.add]
    verdict: Optional[CouncilVerdict]
