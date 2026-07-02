# ruff: noqa
import datetime
import os
import re
import sys
import json
from typing import List, Optional, Any
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, Agent
from google.adk.apps import App
from google.adk.workflow import Workflow, node, JoinNode, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.genai import types

from app.config import config

# Set up Gemini model
model = Gemini(model=config.model)

# Wire MCP Server Tools using Stdio transport (auto-connecting to our local server)
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"],
        )
    )
)

# -----------------------------------------------------------------------------
# LLM Sub-Agents
# -----------------------------------------------------------------------------

competitor_intel_agent = LlmAgent(
    name="competitor_intel_agent",
    model=model,
    instruction="""You are a Competitor Intelligence specialist.
Analyze competitor pricing, promotions, and product releases.
Query the competitor pricing tool for the competitor's details.
Assess threat level and summarize findings.""",
    tools=[mcp_toolset],
    output_key="competitor_intel"
)

customer_health_agent = LlmAgent(
    name="customer_health_agent",
    model=model,
    instruction="""You are a Customer Success Health Specialist.
Analyze customer churn risk based on usage, support tickets, and history.
Use the customer usage tool and the churn scoring tool to obtain health data.
Summarize customer status.""",
    tools=[mcp_toolset],
    output_key="customer_health"
)

revenue_risk_agent = LlmAgent(
    name="revenue_risk_agent",
    model=model,
    instruction="""You are a Financial Risk Analyst.
Read the competitor intelligence ({competitor_intel}) and customer health ({customer_health}).
Use the revenue risk estimation tool to calculate and explain the financial exposure.""",
    tools=[mcp_toolset],
    output_key="revenue_risk"
)

retention_strategy_agent = LlmAgent(
    name="retention_strategy_agent",
    model=model,
    instruction="""You are a Customer Retention Strategist.
Read customer health ({customer_health}) and revenue risk ({revenue_risk}).
Recommend a tailored retention plan (e.g. discount, customer success call, onboarding).
If recommending a discount, specify the discount percentage (e.g., '15%' or '25%').
Use the log retention action tool to record recommended strategies.""",
    tools=[mcp_toolset],
    output_key="retention_strategy"
)

executive_summary_agent = LlmAgent(
    name="executive_summary_agent",
    model=model,
    instruction="""You are the Executive Summary Agent.
Generate a final comprehensive report for the leadership team.
Include:
1. Executive Risk Level (Low/Medium/High)
2. Competitor Intel Summary (based on {competitor_intel})
3. Customer Success Health Status (based on {customer_health})
4. Revenue at Risk (based on {revenue_risk})
5. Final Decision on Retention Actions (status: {approval_status}, approved by: {approved_by})
6. Action Plan (with clear bullet points)""",
    output_key="executive_summary"
)

# Orchestrator / Supervisor Agent
orchestrator = LlmAgent(
    name="orchestrator",
    model=model,
    instruction="""You are the primary supervisor for RevenueGuard.
Your role is to gather intelligence on competitor actions and customer health.
Use competitor_intel_agent and customer_health_agent tools to collect the reports.
Do not formulate the final risk or retention strategies yourself.""",
    tools=[AgentTool(competitor_intel_agent), AgentTool(customer_health_agent)],
    output_key="orchestrator_summary"
)

# -----------------------------------------------------------------------------
# Function Nodes
# -----------------------------------------------------------------------------

@node
async def security_checkpoint(ctx: Context, node_input: types.Content):
    text_input = ""
    if isinstance(node_input, types.Content):
        for part in node_input.parts:
            if part.text:
                text_input += part.text
    elif isinstance(node_input, str):
        text_input = node_input

    # 1. PII Scrubbing
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    acc_pattern = r'\bACC-\d+\b'
    scrubbed = re.sub(email_pattern, "[REDACTED_EMAIL]", text_input)
    scrubbed = re.sub(acc_pattern, "[REDACTED_ACCOUNT_ID]", scrubbed)

    # Extract IDs to state
    cust_match = re.search(r'\bACC-\d+\b', text_input)
    comp_match = re.search(r'\bCOMP-\w+\b', text_input)
    if cust_match:
        ctx.state["customer_id"] = cust_match.group(0)
    if comp_match:
        ctx.state["competitor_id"] = comp_match.group(0)

    # 2. Prompt Injection Detection
    injection_keywords = [
        "ignore previous instructions",
        "ignore system instructions",
        "system prompt",
        "override instructions",
        "you are now a"
    ]
    detected_injection = False
    for kw in injection_keywords:
        if kw in text_input.lower():
            detected_injection = True
            break

    audit_entry = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "input_length": len(text_input),
        "pii_redacted": text_input != scrubbed,
        "injection_detected": detected_injection,
    }

    if detected_injection:
        audit_entry["severity"] = "CRITICAL"
        audit_entry["message"] = "Potential prompt injection attempt detected."
        if "audit_log" not in ctx.state:
            ctx.state["audit_log"] = []
        ctx.state["audit_log"].append(audit_entry)
        print(f"SECURITY AUDIT: {json.dumps(audit_entry)}")
        yield Event(output="Security Breach Blocked", route="security_event")
        return

    # 3. Domain Specific Rules / Verification
    if not cust_match:
        audit_entry["severity"] = "WARNING"
        audit_entry["message"] = "No valid customer Account ID (ACC-XXXX) found in request."
    else:
        audit_entry["severity"] = "INFO"
        audit_entry["message"] = "Request successfully validated."

    if "audit_log" not in ctx.state:
        ctx.state["audit_log"] = []
    ctx.state["audit_log"].append(audit_entry)
    print(f"SECURITY AUDIT: {json.dumps(audit_entry)}")

    ctx.state["scrubbed_query"] = scrubbed
    yield Event(output=scrubbed, route="pass")

@node
def security_breach_handler(node_input: str):
    yield Event(
        content=types.Content(
            role='model',
            parts=[types.Part.from_text(text="⚠️ SECURITY ALERT: The request was blocked by the security checkpoint due to potential policy violations or unsafe content.")]
        )
    )
    yield Event(output="Security Blocked")

@node
async def hitl_approval_checkpoint(ctx: Context, node_input: Any):
    retention_strategy = ctx.state.get("retention_strategy", "")
    discount_match = re.search(r'(\d+(?:\.\d+)?)\s*%', retention_strategy)
    discount = float(discount_match.group(1)) if discount_match else 0.0
    ctx.state["discount_percentage"] = discount

    if discount > 20.0:
        if not ctx.resume_inputs or "approval" not in ctx.resume_inputs:
            yield RequestInput(
                interrupt_id="approval",
                message=f"High discount of {discount}% proposed for customer {ctx.state.get('customer_id')}. Please approve or deny (type 'approve' or 'deny'):"
            )
            return

        user_response = ctx.resume_inputs["approval"].strip().lower()
        if "approve" in user_response:
            ctx.state["approval_status"] = "approved"
            ctx.state["approved_by"] = "human_user"
        else:
            ctx.state["approval_status"] = "denied"
            ctx.state["approved_by"] = "human_user"
    else:
        ctx.state["approval_status"] = "auto_approved"
        ctx.state["approved_by"] = "system"

    yield Event(output=ctx.state["approval_status"])

# -----------------------------------------------------------------------------
# Workflow Definition
# -----------------------------------------------------------------------------

root_agent = Workflow(
    name="revenueguard_workflow",
    edges=[
        ('START', security_checkpoint),
        (security_checkpoint, {
            "security_event": security_breach_handler,
            "pass": orchestrator
        }),
        (orchestrator, revenue_risk_agent),
        (revenue_risk_agent, retention_strategy_agent),
        (retention_strategy_agent, hitl_approval_checkpoint),
        (hitl_approval_checkpoint, executive_summary_agent),
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)

