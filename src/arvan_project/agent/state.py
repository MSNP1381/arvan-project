from __future__ import annotations
from typing import Annotated, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """LangGraph agent state containing messages and RAG control metadata."""

    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    retrieved_context: str
    retry_count: int
    is_relevant: Optional[bool]
