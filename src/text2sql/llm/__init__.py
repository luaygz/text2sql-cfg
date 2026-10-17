"""OpenAI access for the pipeline: one async client with caching, pricing, budget and tracing."""

from text2sql.llm.budget import RunBudget, RunSpend, SpendLedger, SpendReport, spend_report
from text2sql.llm.client import LLMClient, tool_output_item
from text2sql.llm.pricing import PriceTable, load_prices
from text2sql.llm.types import (
    BudgetExceeded,
    CacheMiss,
    CallMeta,
    GrammarCallFailed,
    GrammarRejectedByAPI,
    Message,
    PricingError,
    PromptFlaggedError,
    SqlToolCall,
    Structured,
    StructuredCallFailed,
    Usage,
)

__all__ = [
    "BudgetExceeded",
    "CacheMiss",
    "CallMeta",
    "GrammarCallFailed",
    "GrammarRejectedByAPI",
    "LLMClient",
    "Message",
    "PriceTable",
    "PricingError",
    "PromptFlaggedError",
    "RunBudget",
    "RunSpend",
    "SpendLedger",
    "SpendReport",
    "SqlToolCall",
    "Structured",
    "StructuredCallFailed",
    "Usage",
    "load_prices",
    "spend_report",
    "tool_output_item",
]
