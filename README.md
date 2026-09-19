# ⚡ DataMind AI: AI-Powered Conversational Analytics

**DataMind AI** is an AI-powered conversational data exploration and analytics web application built with **Streamlit**, **Pandas**, **SQLAlchemy**, and **Apache ECharts / Plotly**. Upload your CSV and Excel datasets, load them directly into an in-memory or file-backed SQLite database, and ask questions in plain English. The app generates accurate SQLite queries, executes them with self-healing retries, synthesizes clear answers, and visualizes insights using interactive charts.

---

## 🌟 Key Features

- **Multi-File Ingestion**: Upload multiple `.csv` and `.xlsx` files simultaneously. Table names are automatically derived and sanitized.
- **Dataset Profiling**: Displays instant profile cards for each loaded table including row count, columns, data types, and a 5-row preview.
- **Dynamic Schema Context**: Generates a compact, structured representation of all active tables, columns, data types, and sample values to steer LLM SQL queries.
- **Swappable LLM Providers**:
  - **Local Models via Ollama**: Run models like `llama3.1`, `qwen2.5-coder`, `mistral`, or `phi3` entirely offline.
  - **Hosted Cloud via Groq**: Fast inference using `llama-3.3-70b-versatile` or other models with JSON mode.
- **Self-Healing SQL Query Engine**: If SQLite throws a syntax or column error, the system automatically feeds the error back to the LLM once to repair the query before presenting results.
- **Transparent Reasoning**: Expandable "Show SQL used" section and preview of raw result tables.
- **Interactive Visualizations**: Automatically determines if questions require a chart and renders interactive Plotly bar, line, scatter, or table figures.
- **Session State Persistence**: Retains multi-turn conversation context and active tables across reruns.
- **Table Management**: Sidebar allows individual removal of tables with one click.

---

## 🛠️ Tech Stack

- **Frontend / Framework**: [Streamlit](https://streamlit.io/)
- **Data Manipulation & Querying**: [Pandas](https://pandas.pydata.org/), [OpenPyXL](https://openpyxl.readthedocs.io/)
- **Database**: [SQLite](https://sqlite.org/) via [SQLAlchemy](https://www.sqlalchemy.org/)
- **Charting & Data Visualization**: [Plotly Express](https://plotly.com/python/)
- **LLM Integrations**: [Groq Python SDK](https://github.com/groq/groq-python), [Ollama](https://ollama.com/)
- **Configuration**: [python-dotenv](https://github.com/theskumar/python-dotenv)

---

## 🚀 Getting Started

### 1. Clone or Open the Project
Ensure you are in the project root directory:
```bash
cd data-qa
```

### 2. Set Up a Python Virtual Environment
Create and activate a virtual environment:

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
Install all required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## 🔑 LLM Provider Configuration

Data Q&A supports both local models (via Ollama) and cloud inference (via Groq). You can select your provider dynamically in the sidebar.

### Option A: Using Groq (Cloud Inference)
1. Get an API key at [Groq Console](https://console.groq.com/keys).
2. Set your API key in `.env`:
   ```ini
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=openai/gpt-oss-120b
   DEFAULT_PROVIDER=Groq
   ```
   *(Alternatively, your key in `.env` is loaded automatically on startup).*

### Option B: Using Ollama (Local Inference)
1. Download and install Ollama from [ollama.com](https://ollama.com/).
2. Pull your preferred open-source model:
   ```bash
   ollama pull llama3.1
   # or
   ollama pull qwen2.5-coder
   ```
3. Start the Ollama server:
   ```bash
   ollama serve
   ```
4. Select **Ollama** in the Streamlit sidebar.

---

## 🏃 Running the Application

Launch the Streamlit app:
```powershell
# Using the virtual environment
.\.venv\Scripts\python.exe -m streamlit run app.py

# Or if the environment is activated
streamlit run app.py
```

The application will open in your default browser at `http://localhost:8501`.

---

## 📁 Project Structure

```
data-qa/
├── app.py                  # Streamlit entrypoint (UI layout, sidebar, chat loop, ECharts integration)
├── APPROACH.md             # 1-Page Engineering write-up on key decisions, delta solutioning & roadmap
├── core/
│   ├── __init__.py
│   ├── ingestion.py        # Multi-file parsing (.csv/.xlsx), sanitization, SQLite loading, table profiling
│   ├── schema.py           # Database schema inspection with active-table context isolation
│   ├── llm.py              # Swappable open-source LLM clients (Groq & Ollama), JSON extraction
│   ├── query_engine.py     # SQL execution with automated 2-retry self-healing error recovery
│   └── charting.py         # Visual engine: Apache ECharts 5 & upgraded Plotly with smart heuristics
├── sample_data/
│   ├── sales_orders.csv    # Sample e-commerce sales dataset
│   ├── employees.csv       # Sample company employees dataset
│   └── employees.xlsx      # Sample company employees Excel dataset
├── tests/
│   └── test_core.py        # Automated test suite (12 tests) covering ingestion, schema, LLM, queries & charts
├── requirements.txt        # Pinned Python package dependencies
├── .env                    # Active local environment variables
├── .env.example            # Sample environment variable template
└── README.md               # Documentation and setup guide
```

---

## 🧪 Testing with Sample Data

Click the **"📥 Load Sample Datasets"** button in the sidebar or upload files manually from `sample_data/`.

**Example Questions to Ask:**
- *"What is the total revenue by product category?"*
- *"Show me monthly sales trends over time as a line chart."*
- *"Which region generated the highest sales volume?"*
- *"Join the sales and employee tables to find total sales made by each employee."*
- *"Who are the top 3 highest earning employees and what are their departments?"*
