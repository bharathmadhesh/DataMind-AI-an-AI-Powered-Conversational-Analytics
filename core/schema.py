"""
Database schema summarization module for Data Q&A.

Extracts table names, column names, column data types, and concise sample values
from the shared SQLite database to construct compact LLM context.
"""

from typing import List, Optional, Union
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine, Connection


def get_schema_summary(
    engine: Union[Engine, Connection],
    max_sample_values: int = 10,
    active_tables: Optional[List[str]] = None
) -> str:
    """
    Produce a compact, structured text representation of the loaded SQLite database.
    
    Args:
        engine: SQLAlchemy Engine or Connection.
        max_sample_values: Number of sample values to include per column.
        active_tables: Optional list of table names to restrict inspection to.
        
    Returns:
        A compact string suitable for injection into an LLM prompt.
    """
    inspector = inspect(engine)
    all_tables: List[str] = inspector.get_table_names()
    
    if active_tables is not None:
        table_names = [t for t in all_tables if t in active_tables]
    else:
        table_names = all_tables
    
    if not table_names:
        return "No tables are currently loaded in the database."
        
    summary_lines = [
        "### Available SQLite Database Schema",
        "Use ONLY the tables and column names listed below. DO NOT invent tables or columns.",
        "Note: Column sample values are for type guidance only. Always query the database with SELECT DISTINCT to fetch all actual values."
    ]
    
    with engine.connect() as conn:
        for table in table_names:
            # Get row count
            try:
                count_res = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                row_count_str = f"{count_res} rows"
            except Exception:
                row_count_str = "unknown rows"
                
            summary_lines.append(f"\nTable: `{table}` ({row_count_str})")
            summary_lines.append("Columns:")
            
            columns = inspector.get_columns(table)
            for col in columns:
                col_name = col["name"]
                col_type = str(col["type"])
                
                # Fetch non-null sample values for context
                samples_str = ""
                try:
                    query = text(
                        f'SELECT DISTINCT "{col_name}" FROM "{table}" '
                        f'WHERE "{col_name}" IS NOT NULL LIMIT {max_sample_values}'
                    )
                    samples = [row[0] for row in conn.execute(query).fetchall()]
                    if samples:
                        formatted_samples = []
                        for s in samples:
                            if isinstance(s, str):
                                # Truncate long strings
                                clean_s = s[:25] + "..." if len(s) > 25 else s
                                formatted_samples.append(f"'{clean_s}'")
                            else:
                                formatted_samples.append(str(s))
                        samples_str = f" | Samples: [{', '.join(formatted_samples)}]"
                except Exception:
                    samples_str = ""
                    
                summary_lines.append(f"  - `{col_name}` ({col_type}){samples_str}")
                
    summary_lines.append("\n### SQLite Query Guidelines:")
    summary_lines.append("- Output must be standard, valid SQLite syntax.")
    summary_lines.append("- String comparisons in SQLite: use LIKE for case-insensitive matching if appropriate.")
    summary_lines.append("- For dates formatted as 'YYYY-MM-DD', SQLite date/strftime functions can be used (e.g., strftime('%Y-%m', col)).")
    summary_lines.append("- Use double quotes for table or column identifiers if they contain spaces or special names.")
    
    return "\n".join(summary_lines)
