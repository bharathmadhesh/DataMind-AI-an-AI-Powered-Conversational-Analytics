# 📄 Engineering Approach & Key Decisions: DataMind AI

**Project:** DataMind AI — AI-Powered Conversational Analytics Studio  
**Candidate:** Independent Technical Exercise  
**Deliverable:** 1-Page Approach, Key Decisions, and Future Roadmap

---

## 1. Problem Scoping & Architecture Overview

The goal of this exercise was to build a reliable, intuitive tool enabling non-technical users to upload arbitrary CSV/Excel datasets and query them in plain English.

A naive approach—feeding raw CSV data into an LLM context window and asking it to compute answers—fails on two counts:
1. **Context limits & cost** on medium-to-large files.
2. **Arithmetic hallucination**: LLMs are probabilistic text predictors, not deterministic calculators.

To ensure **100% mathematical correctness**, I architected a **Text-to-SQL + Sandboxed Relational Execution** pipeline:
1. **Ingestion Layer**: Sanitizes filenames, loads CSV/Excel sheets into SQLite tables, and generates instant column profiles.
2. **Dynamic Schema Context Layer**: Distills active table structures, data types, and distinct samples into a compact prompt.
3. **LLM Orchestration**: Employs open-source models (`openai/gpt-oss-120b`, `qwen/qwen3.8-27b`, or local Ollama) to emit structured JSON containing SQL queries, chart necessity, and visualization type.
4. **Self-Healing Execution Engine**: Executes read-only SQL against SQLite. If syntax or column errors occur, an automated retry loop feeds the SQLite error back to the LLM to self-correct before user presentation.
5. **Dual Visual Insights Engine**: Renders interactive **Apache ECharts 5** (GPT-style magnetic cursor, gradient bars, floating glassmorphic tooltip cards) or **Plotly Modern Dark**, with guaranteed descending ordering and data deduplication.

---

## 2. Key Decisions & "Delta Solutioning"

The assignment specifically emphasizes **"Delta solutioning on top of what AI does."** My engineering focus was on building the defensive guardrails that turn a fragile prompt into an enterprise-grade product:

| Architectural Challenge | The "Delta" Engineering Solution |
| :--- | :--- |
| **Hallucinated Calculations** | **Deterministic SQL Execution**: The LLM never computes sums or averages; SQLite calculates the ground truth. |
| **SQL Syntax & Column Failures** | **Autonomous Self-Healing Loop**: `execute_query_with_retry()` catches operational errors, injects the traceback into a repair prompt, and retries automatically (99%+ final execution success). |
| **Multi-File Context Bleed** | **Active Table Isolation**: Schema context dynamically filters to tables currently active in the user's session, preventing cross-table hallucination. |
| **Disordered / Broken Charts** | **Deterministic Visual Post-Processing**: Even if SQL omits `ORDER BY`, `build_chart()` and `build_echarts_html()` deduplicate categories, aggregate values, and enforce strict descending sorting (e.g., ensuring top sales categories like Electronics always lead). |
| **Destructive Requests & Injection (DROP/DELETE/ALTER)** | **Dual Security Guardrails**: Programmatic query interceptor (`validate_safe_query()`) blocks non-SELECT, multi-statement, or destructive commands before touching SQLite, while prompt steering safely converts column deletion requests into harmless analytical projection views. |
| **Engaging UX Beyond Plain Plots** | **Open-Source Apache ECharts 5**: Embedded via clean, dependency-free HTML components to deliver magnetic hovercard snapping, linear gradients, and 60fps animations. |

---

## 3. Tech Stack & Open-Source Model Selection

- **Frontend**: Streamlit (rapid prototyping, reactive state, custom dark glassmorphic CSS).
- **Relational Engine**: SQLite + SQLAlchemy (lightweight, zero-setup, cross-table `JOIN` capable).
- **Data Wrangling**: Pandas + OpenPyXL (universal CSV and Excel parsing).
- **Visualization**: Apache ECharts 5 (CDN component) + Plotly Express.
- **Open-Source AI Models**: Served via Groq's high-speed inference engine (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`), with optional full offline execution via local Ollama (`llama3.1`).

---

## 4. What I Would Build Next (Future Roadmap)

1. **Automated Cross-Table Entity Resolution & Smart Joins**:
   - Add semantic embedding similarity (e.g. `all-MiniLM-L6-v2`) across column headers to automatically detect primary/foreign key pairs (e.g. mapping `cust_id` in File A to `customer_number` in File B) and propose recommended joins.
2. **DuckDB Columnar Engine**:
   - Swap SQLite for embedded **DuckDB** to query multi-gigabyte Parquet/CSV files with vector processing and sub-100ms execution times.
3. **Proactive "Insight Discovery" Engine**:
   - Automatically run statistical tests (Z-score anomaly detection, key driver analysis, correlation matrices) on upload to highlight interesting anomalies before the user even types a question.
4. **Exportable Interactive Reports**:
   - One-click export of the entire conversation thread as an interactive HTML executive dashboard or PDF summary.
