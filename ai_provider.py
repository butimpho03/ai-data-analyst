"""
ai_provider.py — a swappable interface for AI text generation.

WHY THIS FILE EXISTS (the "modular AI provider" requirement from the brief):
Today this project uses Groq's free API. Tomorrow you might want to try a
different provider. Because every other part of this app talks to "an
AIProvider" instead of directly to Groq's specific API, swapping providers
later means changing only this one file — nothing in app.py,
analysis_engine.py, or nl_planner.py needs to change.

WHAT THE AI IS USED FOR (and is NEVER used for):
Per the project's core rule, the AI never performs calculations — pandas
already did that in analysis_engine.py. The AI only turns an
already-computed result into a plain-English explanation. If the AI is
ever unavailable (no key, network issue, rate limit), the rest of the app
keeps working exactly as before — you just don't get the extra written
explanation, and still see the real calculated numbers.

HOW TO ADD ANOTHER PROVIDER LATER:
Write a new class that inherits from AIProvider and implements
generate_text() and is_available(), then update get_ai_provider() below to
build that class instead (or based on a setting). Nothing else changes.
"""

from abc import ABC, abstractmethod
import os


class AIProvider(ABC):
    """
    The interface every AI provider must implement. Any future provider
    (a different hosted API, or a local model) just needs a class shaped
    like this one.
    """

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        """Takes a prompt, returns the AI's text response."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is configured and ready to use right now."""
        raise NotImplementedError


class GroqProvider(AIProvider):
    """
    Talks to Groq's free hosted API (an OpenAI-compatible Chat Completions
    endpoint). Requires a GROQ_API_KEY — read from Streamlit secrets or an
    environment variable, never hard-coded in this file.
    """

    MODEL = "llama-3.3-70b-versatile"

    SYSTEM_PROMPT = (
        "You are a professional data analyst assistant writing for a "
        "business manager audience. You will be given a question, the "
        "calculation method used, and the already-computed result. Explain "
        "the result clearly and professionally in 2-3 sentences. Never "
        "invent, adjust, or recalculate any number — only explain the "
        "numbers you are given exactly as given."
    )

    def __init__(self, api_key=None):
        self.api_key = api_key
        self._client = None
        if self.api_key:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
            except Exception:
                # WHY WE SWALLOW THIS ERROR:
                # If the groq package isn't installed, or the key is
                # malformed, we don't want the whole app to crash — we
                # just mark this provider as unavailable and let the rest
                # of the app keep working without AI explanations.
                self._client = None

    def is_available(self):
        return self._client is not None

    def generate_text(self, prompt: str) -> str:
        if not self.is_available():
            raise RuntimeError("Groq provider is not configured (missing or invalid API key).")
        response = self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_completion_tokens=300,
        )
        return response.choices[0].message.content.strip()


def get_ai_provider():
    """
    Factory function: builds and returns the configured AI provider, or
    None if no API key is set up anywhere.

    WHY A FACTORY FUNCTION:
    app.py just calls get_ai_provider() once and doesn't need to know HOW
    the key is found or which provider class gets built — that lookup
    logic lives here, in one place.

    WHERE IT LOOKS FOR THE KEY (in order):
    1. Streamlit Cloud's secrets manager (st.secrets) — the secure,
       recommended place for a deployed app.
    2. A GROQ_API_KEY environment variable — useful for local testing.
    """
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass

    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return None

    provider = GroqProvider(api_key=api_key)
    return provider if provider.is_available() else None


def build_explanation_prompt(question, method, result):
    """
    Builds a small, safe prompt describing an already-computed result.

    WHY THIS FUNCTION EXISTS (the "don't send the whole dataset" security
    rule): this only sends the question, the method description, and the
    final computed numbers — never the raw uploaded data. The AI explains
    a summary, not your original spreadsheet.
    """
    lines = [f"Question: {question}", f"Method used: {method}"]

    if result.get("error"):
        lines.append(f"Outcome: This could not be calculated. Reason: {result['error']}")
    elif result.get("result_value") is not None:
        lines.append(f"Result: {result['result_value']}")
    elif result.get("result_table") is not None:
        # Only send a small preview of the table (max 10 rows), not the
        # full uploaded dataset, keeping the request small and private.
        table_preview = result["result_table"].head(10).to_string(index=False)
        lines.append(f"Result table (showing up to 10 rows):\n{table_preview}")

    if result.get("change") is not None:
        lines.append(f"Change between the two groups: {result['change']}")
    if result.get("pct_change") is not None:
        lines.append(f"Percentage change: {result['pct_change']:.1f}%")

    lines.append("Write a short, professional explanation of this result for a manager.")
    return "\n".join(lines)
