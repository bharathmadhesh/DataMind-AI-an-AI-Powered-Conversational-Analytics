"""
Query execution engine module for Data Q&A.

Executes SQLite queries against the database using pandas, and implements
an automated self-healing single-retry flow using the LLM client when
errors occur.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection

from core.llm import LLMClient


FORBIDDEN_SQL_KEYWORDS = {
    'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'UPDATE', 'INSERT',
    'REPLACE', 'CREATE', 'ATTACH', 'DETACH', 'PRAGMA', 'REINDEX', 'VACUUM'
}


def validate_safe_query(sql: str) -> Tuple[bool, Optional[str]]:
    """
    Programmatic security guardrail to strictly enforce read-only execution.
    
    Blocks any attempts to DROP, DELETE, ALTER, UPDATE, or modify database
    schemas or data, even if requested via adversarial prompts or prompt injection.
    
    Args:
        sql: The raw SQL string to validate.
        
    Returns:
        Tuple of (is_safe, error_message_if_unsafe).
    """
    if not sql or not sql.strip():
        return False, "Empty SQL query."
        
    # Strip single-line and multi-line comments
    cleaned = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL).strip()
    
    if not cleaned:
        return False, "Query contains only comments."
        
    # Block multi-statement SQL execution (semicolon injection prevention)
    statements = [s.strip() for s in cleaned.split(';') if s.strip()]
    if len(statements) > 1:
        return False, (
            "[Security Guardrail Violation] Multiple SQL statements in a single execution "
            "are strictly prohibited to prevent SQL injection."
        )
        
    main_stmt = statements[0]
    tokens = re.findall(r'\b[A-Za-z_]+\b', main_stmt.upper())
    if not tokens:
        return False, "No recognizable SQL commands found in query."
        
    # Query must begin with read-only keywords
    if tokens[0] not in {'SELECT', 'WITH', 'EXPLAIN'}:
        return False, (
            f"[Security Guardrail Violation] Operation '{tokens[0]}' is blocked. "
            "Data Q&A operates strictly in read-only analytical mode. Only SELECT queries are permitted."
        )
        
    # Check for any forbidden destructive keywords anywhere in tokens
    for token in tokens:
        if token in FORBIDDEN_SQL_KEYWORDS:
            return False, (
                f"[Security Guardrail Violation] Destructive command '{token}' is strictly forbidden. "
                "Database tables, columns, and records cannot be deleted or altered via prompts."
            )
            
    return True, None


@dataclass
class QueryExecutionResult:
    """Represents the outcome of a query execution and optional retry."""
    success: bool
    df: Optional[pd.DataFrame] = None
    sql_used: str = ""
    needs_chart: bool = False
    chart_type: str = "table"
    error: Optional[str] = None
    attempted_sqls: List[str] = field(default_factory=list)
    retry_count: int = 0


def format_dataframe_for_llm(df: pd.DataFrame, max_rows: int = 20) -> str:
    """
    Format a DataFrame as a compact markdown or text table for LLM context.
    
    Truncates to max_rows rows to prevent exceeding token context limits.
    
    Args:
        df: The pandas DataFrame to format.
        max_rows: Maximum rows to include.
        
    Returns:
        Formatted string representation of the data.
    """
    if df.empty:
        return "Query returned 0 rows (empty result set)."
        
    sample_df = df.head(max_rows)
    try:
        table_str = sample_df.to_markdown(index=False)
    except Exception:
        table_str = sample_df.to_string(index=False)
        
    total_rows = len(df)
    if total_rows > max_rows:
        table_str += f"\n\n*(Note: Showing first {max_rows} of {total_rows} total rows)*"
        
    return table_str


def execute_query_with_retry(
    engine: Union[Engine, Connection],
    initial_plan: Dict[str, Any],
    schema_summary: str,
    question: str,
    llm_client: LLMClient
) -> QueryExecutionResult:
    """
    Execute SQL against the SQLite database with automated self-healing retry.
    
    Process:
    1. Validate SQL against security guardrails (blocks DROP, DELETE, ALTER).
    2. Attempt to execute the initial SQL using pandas.read_sql.
    3. If successful, return the DataFrame and plan parameters.
    4. If execution fails, send the error and original SQL back to the LLM
       to repair the query once.
    5. Validate repaired SQL against security guardrails.
    6. Execute the repaired query.
    7. If it succeeds, return the repaired result.
    8. If it fails a second time, return failure details (error message and
       attempted SQL) so the UI can present them transparently.
       
    Args:
        engine: SQLAlchemy Engine or Connection to SQLite.
        initial_plan: Dict with keys 'sql', 'needs_chart', 'chart_type'.
        schema_summary: Text representation of active database schema.
        question: Original user question.
        llm_client: LLMClient instance for query repair.
        
    Returns:
        QueryExecutionResult with success status, DataFrame, or error information.
    """
    current_sql = str(initial_plan.get("sql", "")).strip()
    needs_chart = bool(initial_plan.get("needs_chart", False))
    chart_type = str(initial_plan.get("chart_type", "table")).lower()
    
    attempted_sqls = [current_sql]
    
    if not current_sql:
        return QueryExecutionResult(
            success=False,
            error="No SQL query was provided by the model.",
            attempted_sqls=attempted_sqls
        )

    # Security Guardrail Check 1 (Initial query)
    is_safe, guardrail_err = validate_safe_query(current_sql)
    if not is_safe:
        return QueryExecutionResult(
            success=False,
            error=guardrail_err,
            attempted_sqls=attempted_sqls,
            sql_used=current_sql
        )

    # Attempt 1
    try:
        df = pd.read_sql_query(text(current_sql), con=engine)
        return QueryExecutionResult(
            success=True,
            df=df,
            sql_used=current_sql,
            needs_chart=needs_chart,
            chart_type=chart_type,
            retry_count=0,
            attempted_sqls=attempted_sqls
        )
    except Exception as first_exc:
        first_error_msg = str(first_exc)
        
        # Self-healing attempt: Call LLM once to repair query
        try:
            repair_plan = llm_client.repair_sql(
                schema_summary=schema_summary,
                question=question,
                broken_sql=current_sql,
                error_message=first_error_msg
            )
            repaired_sql = str(repair_plan.get("sql", "")).strip()
            repaired_needs_chart = bool(repair_plan.get("needs_chart", needs_chart))
            repaired_chart_type = str(repair_plan.get("chart_type", chart_type)).lower()
            
            attempted_sqls.append(repaired_sql)
            
            # Security Guardrail Check 2 (Repaired query)
            is_repaired_safe, rep_guardrail_err = validate_safe_query(repaired_sql)
            if not is_repaired_safe:
                return QueryExecutionResult(
                    success=False,
                    error=rep_guardrail_err,
                    attempted_sqls=attempted_sqls,
                    sql_used=repaired_sql,
                    retry_count=1
                )
            
            # Attempt 2
            df_repaired = pd.read_sql_query(text(repaired_sql), con=engine)
            return QueryExecutionResult(
                success=True,
                df=df_repaired,
                sql_used=repaired_sql,
                needs_chart=repaired_needs_chart,
                chart_type=repaired_chart_type,
                retry_count=1,
                attempted_sqls=attempted_sqls
            )
        except Exception as second_exc:
            # Failed twice: Return details transparently
            return QueryExecutionResult(
                success=False,
                error=(
                    f"First Attempt Error: {first_error_msg}\n"
                    f"Second Attempt Error: {str(second_exc)}"
                ),
                attempted_sqls=attempted_sqls,
                retry_count=1
            )
