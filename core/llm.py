"""
Swappable LLM client module for Data Q&A.

Supports local models via Ollama (e.g., llama3.1, qwen2.5-coder) and hosted
models via Groq (e.g., llama-3.3-70b-versatile). Provides structured JSON
generation for SQLite queries, query repair, and natural language synthesis.
"""

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


def extract_json(response_text: str) -> Dict[str, Any]:
    """
    Robustly extract and parse a JSON object from model output text.
    
    Handles markdown code blocks (```json ... ```) as well as unformatted text.
    
    Args:
        response_text: Raw string output from the LLM.
        
    Returns:
        Parsed JSON dictionary.
        
    Raises:
        ValueError: If no valid JSON object can be extracted or parsed.
    """
    clean_text = response_text.strip()
    
    # Check for markdown code blocks
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', clean_text, re.IGNORECASE)
    if match:
        clean_text = match.group(1).strip()
        
    # Attempt direct parse
    try:
        data = json.loads(clean_text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
        
    # Attempt to locate the outer braces { ... }
    first_brace = clean_text.find('{')
    last_brace = clean_text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = clean_text[first_brace:last_brace + 1]
        try:
            data = json.loads(json_candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as err:
            raise ValueError(f"Could not parse JSON from model response: {err}\nResponse text: {clean_text}") from err
            
    raise ValueError(f"No JSON object found in response:\n{response_text}")


class LLMClient(ABC):
    """Abstract base class for swappable LLM clients."""
    
    @abstractmethod
    def generate_sql(
        self,
        schema_summary: str,
        question: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a strict JSON SQL query plan for a user question.
        
        Expected JSON format:
        {
            "sql": "SELECT ...",
            "needs_chart": true,
            "chart_type": "bar|line|scatter|table"
        }
        """
        pass

    @abstractmethod
    def repair_sql(
        self,
        schema_summary: str,
        question: str,
        broken_sql: str,
        error_message: str
    ) -> Dict[str, Any]:
        """
        Repair a failed SQL query using the SQLite error message.
        """
        pass

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        df_summary: str
    ) -> str:
        """
        Generate a 2-3 sentence plain-English explanation grounded in the data.
        """
        pass


def _build_sql_prompt(
    schema_summary: str,
    question: str,
    history: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Build system and user instructions for text-to-SQL generation."""
    prompt_parts = [
        "You are an expert SQLite data analyst.",
        "Your task is to generate a single valid SQLite query that answers the user's question, "
        "and determine whether a visualization chart is appropriate.",
        "",
        "DATABASE SCHEMA:",
        schema_summary,
        "",
        "RULES:",
        "1. Reference ONLY the exact table and column names in the schema above. NEVER invent columns or tables.",
        "2. The query MUST be valid SQLite syntax.",
        "3. STRICT READ-ONLY GUARDRAIL: The database is strictly immutable. Only SELECT and WITH queries are permitted. Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or PRAGMA.",
        "4. DELETION & EXCLUSION REQUESTS: If the user asks to 'delete', 'remove', or 'drop' a column, table, or rows (e.g. 'delete the unit_cost column', 'remove furniture'), NEVER generate DROP, DELETE, or ALTER statements. Instead, generate a safe analytical SELECT query that projects the view excluding that element (e.g., SELECT all columns EXCEPT the specified column, or filter WHERE category != 'Furniture') so the user's analytical goal is achieved safely without modifying the database.",
        "5. Choose 'needs_chart': true if the data is best visualized as a trend, comparison, or correlation.",
        "   Valid chart_type values: 'bar', 'line', 'scatter', 'table'.",
        "   If the answer is a single scalar value, count, or complex raw rows, set 'needs_chart': false and 'chart_type': 'table'.",
        "6. TABLE MATCHING: Choose the specific table that directly matches the user's question (e.g., if user mentions 'product', 'product file', or 'products', query the 'products' table).",
        "7. COMPLETE DATA RETRIEVAL: When asked to list, show, or count categories, distinct items, or groups, ALWAYS generate a query like `SELECT DISTINCT col FROM table` or `SELECT col, COUNT(*) FROM table GROUP BY col` to fetch all real values. Never guess or rely on sample values in the schema.",
        "8. BEST-SELLING, SALES & REVENUE RANKINGS: When asked for 'best selling', 'top selling', 'sales', 'highest revenue', or rankings, if there is no explicit 'sales' column in the table, calculate total sales from price (e.g. `SUM(unit_price)` or `SUM(unit_price * quantity)` if quantity exists). Always `GROUP BY` the categorical dimension, and ALWAYS include `ORDER BY total_sales DESC` so the top performer appears first.",
        "9. ORDERING & GROUPING: Whenever ranking items (highest, lowest, top N, best, worst), always include an explicit `ORDER BY <metric> DESC` (or `ASC` for lowest). Never return unaggregated individual product rows when asked about categories or overall rankings.",
        "10. You MUST return ONLY a strict JSON object with no preamble or commentary.",
        "",
        "REQUIRED JSON OUTPUT FORMAT:",
        '{\n  "sql": "SELECT ...",\n  "needs_chart": true,\n  "chart_type": "bar"\n}'
    ]
    
    if history:
        prompt_parts.append("\nRECENT CONVERSATION HISTORY (last turns):")
        # Keep up to 3 turns of history
        for turn in history[-3:]:
            role = turn.get("role", "user")
            content = turn.get("content") or turn.get("question") or turn.get("answer", "")
            sql = turn.get("sql", "")
            if sql:
                prompt_parts.append(f"{role.capitalize()}: {content} (SQL used: {sql})")
            else:
                prompt_parts.append(f"{role.capitalize()}: {content}")
                
    prompt_parts.append(f"\nCURRENT USER QUESTION:\n{question}")
    return "\n".join(prompt_parts)


def _build_repair_prompt(
    schema_summary: str,
    question: str,
    broken_sql: str,
    error_message: str
) -> str:
    """Build instructions for repairing a failed SQLite query."""
    return f"""You are an expert SQLite data analyst.
A previously generated SQLite query produced an error during execution.
Fix the query so that it is valid SQLite syntax and correctly answers the user's question.

DATABASE SCHEMA:
{schema_summary}

USER QUESTION:
{question}

ATTEMPTED SQL:
{broken_sql}

SQLITE ERROR MESSAGE:
{error_message}

RULES:
1. Fix the error by strictly referencing valid tables and columns from the schema.
2. Maintain valid SQLite syntax.
3. Return STRICT JSON ONLY with the exact format below:
{{
  "sql": "SELECT ...",
  "needs_chart": true,
  "chart_type": "bar"
}}"""


def _build_answer_prompt(question: str, df_summary: str) -> str:
    """Build instructions for summarizing the query result in plain English."""
    return f"""You are a helpful and precise data analyst assistant.
Based SOLELY on the query result table provided below, write a clear, accurate, plain-English answer to the user's question.
List all items, categories, or records that appear in the query result table completely and accurately.
Never omit values that are present in the table, and NEVER invent or mention values not present in the table.
If the table is empty, state clearly that no records matched the query.

USER QUESTION:
{question}

QUERY RESULT TABLE:
{df_summary}

YOUR PLAIN-ENGLISH ANSWER:"""


class OllamaClient(LLMClient):
    """LLM client for local Ollama instances."""
    
    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        
    def _call_ollama(self, system_prompt: str, user_prompt: str, json_format: bool = False) -> str:
        try:
            import ollama
            client = ollama.Client(host=self.base_url)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = client.chat(
                model=self.model,
                messages=messages,
                format="json" if json_format else ""
            )
            return response["message"]["content"]
        except ImportError:
            # Fallback to direct HTTP request using urllib if ollama library is not present
            import urllib.request
            import urllib.error
            url = f"{self.base_url}/api/chat"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "stream": False
            }
            if json_format:
                payload["format"] = "json"
                
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["message"]["content"]
            except urllib.error.URLError as e:
                raise ConnectionError(
                    f"Could not connect to Ollama at {self.base_url}. "
                    f"Make sure Ollama is running (`ollama serve`). Details: {e}"
                ) from e
        except Exception as e:
            raise RuntimeError(f"Ollama execution failed: {e}") from e

    def generate_sql(
        self,
        schema_summary: str,
        question: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        prompt = _build_sql_prompt(schema_summary, question, history)
        resp = self._call_ollama(
            system_prompt="You generate strict JSON containing SQLite queries and chart specifications.",
            user_prompt=prompt,
            json_format=True
        )
        return extract_json(resp)

    def repair_sql(
        self,
        schema_summary: str,
        question: str,
        broken_sql: str,
        error_message: str
    ) -> Dict[str, Any]:
        prompt = _build_repair_prompt(schema_summary, question, broken_sql, error_message)
        resp = self._call_ollama(
            system_prompt="You are an expert SQL debugger. Output strict JSON only.",
            user_prompt=prompt,
            json_format=True
        )
        return extract_json(resp)

    def generate_answer(self, question: str, df_summary: str) -> str:
        prompt = _build_answer_prompt(question, df_summary)
        return self._call_ollama(
            system_prompt="You provide concise 2-3 sentence answers grounded strictly in tabular data.",
            user_prompt=prompt,
            json_format=False
        ).strip()


class GroqClient(LLMClient):
    """LLM client for Groq's hosted models (e.g. llama-3.3-70b-versatile)."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b"
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        
        if not self.api_key:
            raise ValueError(
                "Groq API Key is missing. Please set GROQ_API_KEY in .env or enter it in the sidebar."
            )
            
    def _call_groq(self, messages: List[Dict[str, str]], json_format: bool = False) -> str:
        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
            }
            if json_format:
                kwargs["response_format"] = {"type": "json_object"}
                
            completion = client.chat.completions.create(**kwargs)
            return completion.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e)
            if "model_not_found" in err_str or "does not exist" in err_str:
                raise RuntimeError(
                    f"Groq API call failed: Model '{self.model}' does not exist or has been deprecated. "
                    f"Please switch to an active model such as 'llama-3.3-70b-versatile' in the sidebar."
                ) from e
            raise RuntimeError(f"Groq API call failed: {e}") from e

    def generate_sql(
        self,
        schema_summary: str,
        question: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        prompt = _build_sql_prompt(schema_summary, question, history)
        messages = [
            {"role": "system", "content": "You are a precise SQLite data analyst that returns strict JSON only."},
            {"role": "user", "content": prompt}
        ]
        resp = self._call_groq(messages, json_format=True)
        return extract_json(resp)

    def repair_sql(
        self,
        schema_summary: str,
        question: str,
        broken_sql: str,
        error_message: str
    ) -> Dict[str, Any]:
        prompt = _build_repair_prompt(schema_summary, question, broken_sql, error_message)
        messages = [
            {"role": "system", "content": "You are an expert SQL debugger that returns strict JSON only."},
            {"role": "user", "content": prompt}
        ]
        resp = self._call_groq(messages, json_format=True)
        return extract_json(resp)

    def generate_answer(self, question: str, df_summary: str) -> str:
        prompt = _build_answer_prompt(question, df_summary)
        messages = [
            {"role": "system", "content": "You provide factual, 2-3 sentence answers grounded strictly in provided tables."},
            {"role": "user", "content": prompt}
        ]
        return self._call_groq(messages, json_format=False).strip()


def get_llm_client(
    provider: str,
    model_name: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None
) -> LLMClient:
    """
    Factory function to instantiate the selected LLM client.
    
    Args:
        provider: 'Ollama' or 'Groq'.
        model_name: Target model identifier.
        api_key: API key for hosted providers like Groq.
        base_url: Base URL for self-hosted providers like Ollama.
        
    Returns:
        Configured LLMClient instance.
    """
    provider_clean = provider.strip().lower()
    if provider_clean == "groq":
        return GroqClient(api_key=api_key, model=model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    elif provider_clean == "ollama":
        return OllamaClient(
            model=model_name or "llama3.1",
            base_url=base_url or "http://localhost:11434"
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Expected 'Ollama' or 'Groq'.")
