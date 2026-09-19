"""
Data ingestion module for Data Q&A.

Handles parsing CSV and XLSX files, table name sanitization, loading data
into a shared SQLite database, generating table profiles, and table removal.
"""

import os
import re
from typing import Any, Dict, List, Tuple, Union
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection


def sanitize_table_name(filename: str) -> str:
    """
    Derive a clean, safe SQLite table name from an uploaded file name.
    
    Transformation steps:
    1. Strip file extension.
    2. Convert to lowercase.
    3. Replace whitespace and hyphens with underscores.
    4. Remove any characters that are not alphanumeric or underscores.
    5. Ensure the table name starts with a letter or underscore (prepend 't_' if starting with a digit).
    6. Provide a fallback if string becomes empty.
    
    Args:
        filename: Original file name (e.g. 'Sales Report 2024.xlsx').
        
    Returns:
        A sanitized table name suitable for SQLite queries.
    """
    # Strip known extensions explicitly (handling cases like '.csv')
    base_name = re.sub(r'\.(csv|xlsx|xls)$', '', filename, flags=re.IGNORECASE)
    if not base_name:
        return "uploaded_table"
    base_name, _ = os.path.splitext(base_name)
    # Lowercase
    cleaned = base_name.lower().strip()
    # Replace spaces and hyphens with underscores
    cleaned = re.sub(r'[\s\-]+', '_', cleaned)
    # Remove characters other than a-z, 0-9, and _
    cleaned = re.sub(r'[^a-z0-9_]', '', cleaned)
    # Collapse multiple underscores
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    
    # Fallback if empty or single reserved word
    if not cleaned:
        cleaned = "uploaded_table"
        
    # If starts with a digit, prefix with 't_'
    if cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
        
    return cleaned


def parse_file(file_source: Any, filename: str) -> pd.DataFrame:
    """
    Parse an uploaded file or file path into a pandas DataFrame.
    
    Supports .csv and .xlsx files. Uses openpyxl for Excel files.
    
    Args:
        file_source: A file-like buffer (from Streamlit st.file_uploader) or a string file path.
        filename: Name of the file, used to determine format.
        
    Returns:
        pd.DataFrame containing the parsed tabular data.
        
    Raises:
        ValueError: If file format is unsupported or parsing fails.
    """
    lower_name = filename.lower()
    try:
        if lower_name.endswith('.csv'):
            df = pd.read_csv(file_source)
        elif lower_name.endswith('.xlsx') or lower_name.endswith('.xls'):
            df = pd.read_excel(file_source, engine='openpyxl')
        else:
            raise ValueError(f"Unsupported file format: {filename}. Please upload a .csv or .xlsx file.")
            
        # Clean column names by stripping trailing/leading whitespace
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as exc:
        raise ValueError(f"Error parsing file '{filename}': {str(exc)}") from exc


def load_dataframe_to_sqlite(
    df: pd.DataFrame,
    table_name: str,
    engine: Union[Engine, Connection]
) -> None:
    """
    Load a pandas DataFrame into a shared SQLite database table.
    
    If the table already exists, it is replaced with the new data.
    
    Args:
        df: The pandas DataFrame to write.
        table_name: Sanitized SQLite table name.
        engine: SQLAlchemy Engine or Connection object.
    """
    df.to_sql(name=table_name, con=engine, if_exists="replace", index=False)


def get_table_profile(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate a concise profile dictionary for a DataFrame.
    
    Includes row count, column count, list of columns with their data types,
    and a 5-row preview.
    
    Args:
        df: The pandas DataFrame to profile.
        
    Returns:
        A dictionary with keys: 'row_count', 'col_count', 'columns', 'preview'.
    """
    columns_info: List[Tuple[str, str]] = [
        (str(col), str(dtype)) for col, dtype in zip(df.columns, df.dtypes)
    ]
    return {
        "row_count": int(len(df)),
        "col_count": int(len(df.columns)),
        "columns": columns_info,
        "preview": df.head(5)
    }


def drop_table(table_name: str, engine: Union[Engine, Connection]) -> None:
    """
    Safely drop a table from the SQLite database.
    
    Args:
        table_name: Table name to remove.
        engine: SQLAlchemy Engine or Connection.
    """
    # Sanitize again to prevent injection
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '', table_name)
    if not safe_name:
        return
        
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS "{safe_name}"'))
