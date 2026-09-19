"""
Automated unit tests for core modules in Data Q&A.
"""

import os
import unittest
import pandas as pd
from sqlalchemy import create_engine

from core.ingestion import (
    sanitize_table_name,
    parse_file,
    load_dataframe_to_sqlite,
    get_table_profile,
    drop_table,
)
from core.schema import get_schema_summary
from core.charting import build_chart, build_echarts_html
from core.llm import extract_json, LLMClient
from core.query_engine import (
    execute_query_with_retry,
    format_dataframe_for_llm,
    validate_safe_query,
)


class MockLLMClient(LLMClient):
    """Mock LLM client for testing self-healing query retries."""
    def __init__(self, repaired_sql="SELECT * FROM sales_orders"):
        self.repaired_sql = repaired_sql
        self.repair_called = False

    def generate_sql(self, schema_summary, question, history=None):
        return {
            "sql": "SELECT * FROM sales_orders",
            "needs_chart": True,
            "chart_type": "bar"
        }

    def repair_sql(self, schema_summary, question, broken_sql, error_message):
        self.repair_called = True
        return {
            "sql": self.repaired_sql,
            "needs_chart": True,
            "chart_type": "bar"
        }

    def generate_answer(self, question, df_summary):
        return "This is a plain-English mock answer."


class TestDataQA(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        self.sample_df = pd.DataFrame({
            "order_id": [1, 2, 3],
            "product": ["Chair", "Desk", "Lamp"],
            "amount": [150.0, 300.0, 50.0],
            "order_date": ["2024-01-01", "2024-01-02", "2024-01-03"]
        })

    def test_sanitize_table_name(self):
        self.assertEqual(sanitize_table_name("Sales Orders 2024.csv"), "sales_orders_2024")
        self.assertEqual(sanitize_table_name("123-data.xlsx"), "t_123_data")
        self.assertEqual(sanitize_table_name("My Special %$ Data!.csv"), "my_special_data")
        self.assertEqual(sanitize_table_name(".csv"), "uploaded_table")

    def test_parse_and_load(self):
        # Test loading DataFrame to SQLite in-memory
        load_dataframe_to_sqlite(self.sample_df, "sales_orders", self.engine)
        profile = get_table_profile(self.sample_df)
        self.assertEqual(profile["row_count"], 3)
        self.assertEqual(profile["col_count"], 4)
        self.assertEqual(len(profile["columns"]), 4)

        # Verify reading back
        df_back = pd.read_sql_query("SELECT * FROM sales_orders", con=self.engine)
        self.assertEqual(len(df_back), 3)

    def test_parse_sample_files(self):
        csv_path = os.path.join("sample_data", "sales_orders.csv")
        if os.path.exists(csv_path):
            df_csv = parse_file(csv_path, "sales_orders.csv")
            self.assertGreater(len(df_csv), 0)

        xlsx_path = os.path.join("sample_data", "employees.xlsx")
        if os.path.exists(xlsx_path):
            df_xlsx = parse_file(xlsx_path, "employees.xlsx")
            self.assertGreater(len(df_xlsx), 0)

    def test_schema_summary(self):
        load_dataframe_to_sqlite(self.sample_df, "sales_orders", self.engine)
        summary = get_schema_summary(self.engine)
        self.assertIn("Table: `sales_orders`", summary)
        self.assertIn("order_id", summary)
        self.assertIn("amount", summary)

    def test_drop_table(self):
        load_dataframe_to_sqlite(self.sample_df, "to_delete", self.engine)
        summary_before = get_schema_summary(self.engine)
        self.assertIn("to_delete", summary_before)

        drop_table("to_delete", self.engine)
        summary_after = get_schema_summary(self.engine)
        self.assertNotIn("to_delete", summary_after)

    def test_extract_json(self):
        # Clean JSON
        j1 = extract_json('{"sql": "SELECT 1", "needs_chart": false, "chart_type": "table"}')
        self.assertEqual(j1["sql"], "SELECT 1")

        # Markdown wrapped JSON
        j2 = extract_json('Here is your query:\n```json\n{"sql": "SELECT 2", "needs_chart": true, "chart_type": "bar"}\n```')
        self.assertEqual(j2["sql"], "SELECT 2")
        self.assertTrue(j2["needs_chart"])

        # Embedded JSON with text
        j3 = extract_json('Sure! {"sql": "SELECT 3", "needs_chart": false, "chart_type": "table"} hope this helps!')
        self.assertEqual(j3["sql"], "SELECT 3")

    def test_query_engine_successful(self):
        load_dataframe_to_sqlite(self.sample_df, "sales_orders", self.engine)
        mock_llm = MockLLMClient()
        plan = {"sql": "SELECT product, amount FROM sales_orders", "needs_chart": True, "chart_type": "bar"}
        res = execute_query_with_retry(
            engine=self.engine,
            initial_plan=plan,
            schema_summary="Table: sales_orders",
            question="What are the products and amounts?",
            llm_client=mock_llm
        )
        self.assertTrue(res.success)
        self.assertEqual(len(res.df), 3)
        self.assertEqual(res.retry_count, 0)
        self.assertFalse(mock_llm.repair_called)

    def test_query_engine_self_healing_retry(self):
        load_dataframe_to_sqlite(self.sample_df, "sales_orders", self.engine)
        mock_llm = MockLLMClient(repaired_sql="SELECT product, amount FROM sales_orders")
        # Broken query (syntax error)
        plan = {"sql": "SELECT non_existing_col FROM invalid_table", "needs_chart": True, "chart_type": "bar"}
        res = execute_query_with_retry(
            engine=self.engine,
            initial_plan=plan,
            schema_summary="Table: sales_orders",
            question="Get products",
            llm_client=mock_llm
        )
        self.assertTrue(res.success)
        self.assertEqual(res.retry_count, 1)
        self.assertTrue(mock_llm.repair_called)
        self.assertEqual(res.sql_used, "SELECT product, amount FROM sales_orders")

    def test_query_engine_double_failure(self):
        load_dataframe_to_sqlite(self.sample_df, "sales_orders", self.engine)
        # Mock that repairs with an equally invalid query
        mock_llm = MockLLMClient(repaired_sql="SELECT still_broken FROM nonexistent")
        plan = {"sql": "SELECT non_existing_col FROM invalid_table", "needs_chart": False, "chart_type": "table"}
        res = execute_query_with_retry(
            engine=self.engine,
            initial_plan=plan,
            schema_summary="Table: sales_orders",
            question="Get products",
            llm_client=mock_llm
        )
        self.assertFalse(res.success)
        self.assertEqual(res.retry_count, 1)
        self.assertIsNotNone(res.error)
        self.assertEqual(len(res.attempted_sqls), 2)
        self.assertIn("First Attempt Error", res.error)
        self.assertIn("Second Attempt Error", res.error)

    def test_multi_table_join_query(self):
        # Load second table
        emp_df = pd.DataFrame({
            "emp_id": [1, 2],
            "name": ["Alice", "Bob"]
        })
        load_dataframe_to_sqlite(self.sample_df, "orders", self.engine)
        load_dataframe_to_sqlite(emp_df, "employees", self.engine)

        mock_llm = MockLLMClient()
        plan = {
            "sql": "SELECT e.name, COUNT(o.order_id) as total_orders FROM employees e LEFT JOIN orders o ON e.emp_id = o.order_id GROUP BY e.name",
            "needs_chart": True,
            "chart_type": "bar"
        }
        res = execute_query_with_retry(
            engine=self.engine,
            initial_plan=plan,
            schema_summary="Tables: orders, employees",
            question="Orders per employee",
            llm_client=mock_llm
        )
        self.assertTrue(res.success)
        self.assertEqual(len(res.df), 2)

    def test_format_dataframe_for_llm(self):
        # Test empty dataframe
        empty_res = format_dataframe_for_llm(pd.DataFrame())
        self.assertIn("0 rows", empty_res)

        # Test truncation
        large_df = pd.DataFrame({"val": range(50)})
        summary = format_dataframe_for_llm(large_df, max_rows=10)
        self.assertIn("Showing first 10 of 50 total rows", summary)

    def test_charting(self):
        # Bar chart
        fig_bar = build_chart(self.sample_df, "bar", "Bar Test")
        self.assertIsNotNone(fig_bar)

        # Verify bar chart sorting descending
        test_df = pd.DataFrame({
            "category": ["A", "B", "C"],
            "sales": [100, 500, 300]
        })
        sorted_fig = build_chart(test_df, "bar")
        self.assertEqual(list(sorted_fig.data[0].x), ["B", "C", "A"])
        self.assertEqual(list(sorted_fig.data[0].y), [500, 300, 100])

        # Line chart
        fig_line = build_chart(self.sample_df, "line", "Line Test")
        self.assertIsNotNone(fig_line)

        # Scatter chart
        fig_scatter = build_chart(self.sample_df, "scatter", "Scatter Test")
        self.assertIsNotNone(fig_scatter)

        # Table
        fig_table = build_chart(self.sample_df, "table", "Table Test")
        self.assertIsNotNone(fig_table)

        # ECharts generation
        echarts_html = build_echarts_html(test_df, "bar", "ECharts Bar Test")
        self.assertIsNotNone(echarts_html)
        self.assertIn("echarts.min.js", echarts_html)
        self.assertIn("ECharts Bar Test", echarts_html)

        # None/Empty df
        self.assertIsNone(build_chart(pd.DataFrame(), "bar"))
        self.assertIsNone(build_echarts_html(pd.DataFrame(), "bar"))

    def test_security_guardrails(self):
        # Safe queries should pass
        ok, err = validate_safe_query("SELECT * FROM sales_orders")
        self.assertTrue(ok)
        self.assertIsNone(err)

        ok, err = validate_safe_query("WITH t AS (SELECT * FROM sales_orders) SELECT * FROM t")
        self.assertTrue(ok)
        self.assertIsNone(err)

        # Destructive operations should be strictly blocked
        destructive_queries = [
            "DROP TABLE sales_orders",
            "ALTER TABLE sales_orders DROP COLUMN total_amount",
            "DELETE FROM sales_orders WHERE id = 1",
            "UPDATE sales_orders SET total_amount = 0",
            "TRUNCATE TABLE sales_orders",
            "INSERT INTO sales_orders VALUES (1, 2, 3)",
            "SELECT * FROM sales_orders; DROP TABLE sales_orders;",
            "PRAGMA table_info(sales_orders)",
        ]
        for query in destructive_queries:
            is_safe, error_msg = validate_safe_query(query)
            self.assertFalse(is_safe, f"Expected query '{query}' to be blocked by guardrails")
            self.assertIn("Security Guardrail", error_msg)

        # Test execute_query_with_retry blocks destructive query
        plan = {"sql": "DROP TABLE sales_orders", "needs_chart": False}
        res = execute_query_with_retry(
            self.engine,
            plan,
            schema_summary="",
            question="delete table",
            llm_client=MockLLMClient()
        )
        self.assertFalse(res.success)
        self.assertIn("Security Guardrail", res.error)


if __name__ == "__main__":
    unittest.main()
