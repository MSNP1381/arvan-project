from __future__ import annotations
import os
from typing import Literal, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from arvan_project.config import settings
from arvan_project.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    GRADER_SYSTEM_PROMPT,
    REWRITER_SYSTEM_PROMPT,
)
from arvan_project.agent.state import AgentState
from arvan_project.agent.tools import get_all_tools


def get_llm(model_name: Optional[str] = None):
    """Initializes Google GenAI Chat model with resilient fallback."""
    api_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")
    model = model_name or settings.llm_model
    primary = ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key or "dummy_key_for_initialization",
        temperature=0.2,
        max_retries=1,
    )
    if model != "gemini-2.5-flash":
        fallback = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key or "dummy_key_for_initialization",
            temperature=0.2,
            max_retries=2,
        )
        return primary.with_fallbacks([fallback])
    return primary


def create_agent_graph(llm_instance: Optional[ChatGoogleGenerativeAI] = None):
    """Builds and compiles the LangGraph Agentic RAG graph."""
    tools = get_all_tools()
    llm = llm_instance or get_llm()
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        """Reasoning node that decides whether to call tools or respond."""
        messages = state.get("messages", [])
        # Ensure system prompt is present at the beginning
        if not messages or not isinstance(messages[0], SystemMessage):
            full_messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + list(messages)
        else:
            full_messages = list(messages)

        response = llm_with_tools.invoke(full_messages)

        # Normalize content to string if returned as list of chunks by langchain-google-genai
        # to ensure LangGraph Studio and other UIs render the full response rather than truncating at the first part.
        if isinstance(response.content, list):
            text_parts = []
            for part in response.content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    text_parts.append(str(part["text"]))
                elif hasattr(part, "text"):
                    text_parts.append(str(part.text))
                else:
                    text_parts.append(str(part))
            response.content = "".join(text_parts)

        return {"messages": [response]}

    tool_node = ToolNode(tools)

    # Build StateGraph
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    # Edge from START to agent
    builder.add_edge(START, "agent")

    # Conditional routing after agent: tool call or finish
    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    # Cycle back to agent after tools execute
    builder.add_edge("tools", "agent")

    return builder.compile()


# Export compiled graph for LangGraph CLI and LangGraph Studio
graph = create_agent_graph()
