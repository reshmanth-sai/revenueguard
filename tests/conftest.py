import pytest
from unittest.mock import MagicMock
import google.auth
import google.cloud.logging

# Mock google.auth.default and google.cloud.logging.Client before any imports
google.auth.default = lambda *args, **kwargs: (MagicMock(), "mock-project-id")

# Create a mock logger
mock_logger = MagicMock()
mock_client = MagicMock()
mock_client.logger.return_value = mock_logger
google.cloud.logging.Client = lambda *args, **kwargs: mock_client

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_response import LlmResponse
from google.genai import types

@pytest.fixture(autouse=True)
def mock_gemini_calls(monkeypatch):
    async def mock_generate_content_async(self, llm_request, stream=False):
        prompt_text = ""
        if llm_request.contents:
            for content in llm_request.contents:
                if content.parts:
                    for part in content.parts:
                        if part.text:
                            prompt_text += part.text
        
        text = "Mocked Response"
        if "Competitor" in self.model or "competitor" in prompt_text.lower():
            text = "Competitor COMP-A dropped pricing to $85. Threat level: High."
        elif "Health" in self.model or "churn" in prompt_text.lower() or "usage" in prompt_text.lower():
            text = '{"churn_risk_score": 0.7, "confidence": 0.85, "usage_trend": "Declining"}'
        elif "Financial" in self.model or "risk" in prompt_text.lower() or "exposure" in prompt_text.lower():
            text = "Annualized revenue at risk is estimated at $48,000.00."
        elif "Retention" in self.model or "discount" in prompt_text.lower() or "strategy" in prompt_text.lower():
            text = "Recommend a 25% discount to keep the customer."
        elif "Executive" in self.model or "report" in prompt_text.lower():
            text = "### Executive Risk Level: 🔴 High Churn Risk\n- Customer ID: ACC-101\n- Proposed Discount: 25%\n- Status: Approved"
            
        yield LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part.from_text(text=text)]
            )
        )

    monkeypatch.setattr(Gemini, "generate_content_async", mock_generate_content_async)
