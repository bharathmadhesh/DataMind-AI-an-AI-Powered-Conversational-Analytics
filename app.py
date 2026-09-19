"""
Data Q&A - Conversational Analytics Web Application

A streamlined, high-tech conversational data exploration interface for CSV and Excel files.
Uploads datasets into an in-memory or file-backed SQLite database, extracts schema context,
generates strict SQLite queries with Groq models, executes queries with self-healing retries,
and visualizes insights with Plotly.
"""

import os
import sys
import time
from typing import Any, Dict, List, Optional
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import streamlit as st

# Load environment variables from .env
load_dotenv()

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.ingestion import (
    drop_table,
    get_table_profile,
    load_dataframe_to_sqlite,
    parse_file,
    sanitize_table_name,
)
from core.schema import get_schema_summary
from core.llm import get_llm_client
from core.query_engine import execute_query_with_retry, format_dataframe_for_llm
from core.charting import build_chart, build_echarts_html
import streamlit.components.v1 as components


# Set Streamlit page configuration
st.set_page_config(
    page_title="DataMind AI - Conversational Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Dark Tech & Glassmorphic interface
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
        letter-spacing: -0.02em;
    }

    code, pre {
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Hero Header */
    .hero-container {
        padding: 6px 0 16px 0;
        margin-bottom: 8px;
    }

    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.18), rgba(236, 72, 153, 0.18));
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-radius: 9999px;
        color: #C7D2FE;
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .hero-title {
        font-family: 'Outfit', sans-serif;
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FFFFFF 0%, #E0E7FF 40%, #A5B4FC 70%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.15;
        margin: 0 0 8px 0;
    }

    .hero-desc {
        font-size: 1.02rem;
        color: #94A3B8;
        line-height: 1.55;
        margin-bottom: 18px;
        max-width: 800px;
    }

    /* Model Selector Bar */
    .model-bar {
        background: rgba(19, 27, 46, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 22px;
        backdrop-filter: blur(12px);
    }

    /* KPI Stat Cards */
    .kpi-card {
        background: rgba(19, 27, 46, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 16px;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }

    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99, 102, 241, 0.4);
    }

    .kpi-label {
        font-size: 0.74rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .kpi-value {
        font-family: 'Outfit', sans-serif;
        font-size: 1.6rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-top: 3px;
    }

    .kpi-sub {
        font-size: 0.73rem;
        color: #64748B;
        margin-top: 2px;
    }

    /* Pulse Dot for status */
    .pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px #10B981;
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* Table Name Badge */
    .table-tag {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(129, 140, 248, 0.15));
        border: 1px solid rgba(99, 102, 241, 0.4);
        color: #A5B4FC;
        padding: 3px 10px;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* Query execution timing badge */
    .meta-chip {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        background: rgba(99, 102, 241, 0.15);
        color: #A5B4FC;
        border: 1px solid rgba(99, 102, 241, 0.25);
        margin-bottom: 8px;
    }

    /* Custom scrollbars */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0B0F19;
    }
    ::-webkit-scrollbar-thumb {
        background: #1E293B;
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #334155;
    }

    /* File uploader styling */
    [data-testid="stFileUploader"] {
        background: rgba(19, 27, 46, 0.4);
        border: 1px dashed rgba(99, 102, 241, 0.35);
        border-radius: 14px;
        padding: 12px;
        transition: border-color 0.2s ease;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(99, 102, 241, 0.7);
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_engine():
    """Initialize and cache the SQLite SQLAlchemy engine."""
    db_path = os.path.join(PROJECT_ROOT, "data_qa.db")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine


@st.cache_data(ttl=600, show_spinner=False)
def fetch_groq_models(api_key: str) -> List[str]:
    """Dynamically fetch active chat completion models from Groq API."""
    if not api_key:
        return []
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        models_data = client.models.list()
        excluded_keywords = ["whisper", "guard", "safeguard", "distil", "embed"]
        valid_models = [
            m.id for m in models_data.data
            if not any(kw in m.id.lower() for kw in excluded_keywords)
        ]
        # Prioritize top general LLMs
        priority_order = [
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "groq/compound",
            "groq/compound-mini",
            "allam-2-7b"
        ]
        sorted_models = []
        for p in priority_order:
            if p in valid_models:
                sorted_models.append(p)
                valid_models.remove(p)
        sorted_models.extend(sorted(valid_models))
        return sorted_models
    except Exception:
        return []


def generate_dynamic_suggestions(tables: Dict[str, Any]) -> List[str]:
    """Dynamically construct query questions based solely on actual columns in loaded tables."""
    if not tables:
        return []
        
    suggestions = []
    for table_name, meta in tables.items():
        profile = meta.get("profile", {})
        columns_info = profile.get("columns", [])
        
        numeric_cols = []
        text_cols = []
        date_cols = []
        
        for col, col_type in columns_info:
            c_low = col.lower()
            t_low = str(col_type).lower()
            if any(k in c_low for k in ["date", "time", "year", "month", "day"]):
                date_cols.append(col)
            elif any(k in t_low for k in ["int", "float", "numeric", "real", "double", "decimal"]):
                numeric_cols.append(col)
            else:
                text_cols.append(col)
                
        if numeric_cols and text_cols:
            suggestions.append(f"What is the total {numeric_cols[0]} by {text_cols[0]} in {table_name}?")
            suggestions.append(f"Show the top 5 {text_cols[0]} with the highest {numeric_cols[-1]} in {table_name}.")
        elif text_cols:
            suggestions.append(f"What is the breakdown of records by {text_cols[0]} in {table_name}?")
        elif numeric_cols:
            suggestions.append(f"What is the average and maximum {numeric_cols[0]} in {table_name}?")
            
        if date_cols and numeric_cols:
            suggestions.append(f"Show the trend of {numeric_cols[0]} over {date_cols[0]} in {table_name}.")
            
        if len(suggestions) >= 4:
            break
            
    return suggestions[:4]


engine = get_db_engine()

# Initialize session state variables
if "tables" not in st.session_state:
    st.session_state.tables = {}
    try:
        from sqlalchemy import inspect as sqla_inspect
        existing_tables = sqla_inspect(engine).get_table_names()
        for t in existing_tables:
            df_preview = pd.read_sql(f'SELECT * FROM "{t}" LIMIT 50', engine)
            st.session_state.tables[t] = {
                "filename": f"{t}.csv",
                "profile": get_table_profile(df_preview)
            }
            st.session_state.processed_files.add(f"{t}.csv")
    except Exception:
        pass

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

if "prompt_to_run" not in st.session_state:
    st.session_state.prompt_to_run = None


# Helper to load sample files
def load_sample_datasets():
    sample_dir = os.path.join(PROJECT_ROOT, "sample_data")
    if not os.path.exists(sample_dir):
        return 0
    count = 0
    for sf in ["sales_orders.csv", "employees.csv", "employees.xlsx"]:
        sp = os.path.join(sample_dir, sf)
        if os.path.exists(sp):
            t_name = sanitize_table_name(sf)
            df_sample = parse_file(sp, sf)
            load_dataframe_to_sqlite(df_sample, t_name, engine)
            prof = get_table_profile(df_sample)
            st.session_state.tables[t_name] = {
                "filename": sf,
                "profile": prof
            }
            st.session_state.processed_files.add(sf)
            count += 1
    return count


# Retrieve API key from environment
api_key = os.getenv("GROQ_API_KEY", "").strip()

# Fetch active models dynamically
dynamic_models = fetch_groq_models(api_key) if api_key else []
if not dynamic_models:
    dynamic_models = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.8-27b",
        "groq/compound",
        "groq/compound-mini"
    ]
model_options = dynamic_models + ["Custom..."]


# ==============================================================================
# SIDEBAR CONFIGURATION
# ==============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Database & Actions")
    
    # Status indicator
    if api_key:
        st.markdown("""
        <div style='background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 12px; margin-bottom: 16px;'>
            <span class='pulse-dot'></span> <strong style='color: #10B981; font-size: 0.85rem;'>Groq API Connected</strong>
            <div style='color: #94A3B8; font-size: 0.72rem; margin-top: 2px;'>Key loaded securely from .env</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ No GROQ_API_KEY found in .env")

    # Manage Loaded Tables
    st.markdown(f"#### 🗄️ Database Tables ({len(st.session_state.tables)})")
    if not st.session_state.tables:
        st.caption("No tables loaded yet.")
    else:
        for tbl_name, tbl_meta in list(st.session_state.tables.items()):
            col_info, col_del = st.columns([4, 1])
            with col_info:
                row_cnt = tbl_meta["profile"]["row_count"]
                st.markdown(f"**`{tbl_name}`**  \n<small style='color:#94A3B8'>{row_cnt:,} rows</small>", unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_{tbl_name}", help=f"Remove table {tbl_name}"):
                    drop_table(tbl_name, engine)
                    del st.session_state.tables[tbl_name]
                    fn = tbl_meta.get("filename")
                    if fn in st.session_state.processed_files:
                        st.session_state.processed_files.remove(fn)
                    st.rerun()

    st.markdown("---")
    
    # Quick sample loader button in sidebar
    if st.button("📥 Load Sample Datasets", key="load_samples_btn", use_container_width=True, help="Load sales orders and employee records"):
        loaded = load_sample_datasets()
        if loaded > 0:
            st.toast(f"Successfully loaded {loaded} sample datasets!", icon="🚀")
            st.rerun()

    if st.session_state.tables:
        if st.button("🗑️ Drop All Tables", key="drop_all_btn", use_container_width=True, help="Clear all database tables"):
            for t in list(st.session_state.tables.keys()):
                drop_table(t, engine)
            st.session_state.tables = {}
            st.session_state.processed_files = set()
            st.toast("Cleared all database tables.", icon="🧹")
            st.rerun()

    if st.session_state.chat_history:
        if st.button("🧹 Clear Chat History", key="clear_chat_btn", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    st.markdown("---")
    st.markdown("#### 🎨 Visualization Engine")
    visual_engine = st.radio(
        "Chart Engine",
        ["✨ Apache ECharts (GPT Style)", "📊 Plotly Modern Dark"],
        index=0,
        key="visual_engine_select",
        help="Apache ECharts provides magnetic cursor snapping, rich glowing hovercards, smooth entrance animations, and gradient cards."
    )


# ==============================================================================
# HERO SECTION
# ==============================================================================
st.markdown("""
<div class="hero-container">
    <div class="hero-badge">✨ AI-Powered Analytics</div>
    <div class="hero-title">DataMind AI Studio</div>
    <div class="hero-desc">
        Conversational data intelligence with automated SQLite execution, self-healing retries,
        and interactive visual insights.
    </div>
</div>
""", unsafe_allow_html=True)


# ==============================================================================
# MODEL SELECTION BAR (Main Landing Page)
# ==============================================================================
model_col1, model_col2 = st.columns([3, 2])
with model_col1:
    env_default_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    default_idx = model_options.index(env_default_model) if env_default_model in model_options else 0
    selected_model = st.selectbox(
        "⚡ Select Groq Model",
        options=model_options,
        index=default_idx,
        help="Choose any active Groq model. Powered by your stored Groq API key."
    )
    if selected_model == "Custom...":
        model_name = st.text_input("Custom Model Name", value=env_default_model)
    else:
        model_name = selected_model

with model_col2:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    st.caption(f"Active Model: **`{model_name}`** | Provider: **Groq Cloud**")


# Compute live KPIs
num_tables = len(st.session_state.tables)
total_rows = sum(m["profile"]["row_count"] for m in st.session_state.tables.values()) if num_tables > 0 else 0
total_cols = sum(m["profile"]["col_count"] for m in st.session_state.tables.values()) if num_tables > 0 else 0

# KPI Stat Banner
kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
with kpi_col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">📁 Datasets</div>
        <div class="kpi-value">{num_tables}</div>
        <div class="kpi-sub">Active SQLite tables</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">📊 Total Records</div>
        <div class="kpi-value">{total_rows:,}</div>
        <div class="kpi-sub">Ingested data rows</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">🏷️ Attributes</div>
        <div class="kpi-value">{total_cols}</div>
        <div class="kpi-sub">Indexed columns</div>
    </div>
    """, unsafe_allow_html=True)

with kpi_col4:
    st.markdown("""
    <div class="kpi-card">
        <div class="kpi-label">⚡ Database Engine</div>
        <div class="kpi-value"><span class="pulse-dot"></span> Ready</div>
        <div class="kpi-sub">SQLite In-Process</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 18px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# DATA INGESTION & DATASET PROFILES
# ==============================================================================
# Clean file uploader
with st.expander("📤 Ingest Datasets (CSV or Excel)", expanded=(num_tables == 0)):
    uploaded_files = st.file_uploader(
        "Choose CSV or Excel (.xlsx) files to load into SQLite",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        help="Files are parsed and stored as individual SQLite tables."
    )
    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.processed_files:
                try:
                    table_name = sanitize_table_name(uploaded_file.name)
                    df = parse_file(uploaded_file, uploaded_file.name)
                    load_dataframe_to_sqlite(df, table_name, engine)
                    profile = get_table_profile(df)
                    
                    st.session_state.tables[table_name] = {
                        "filename": uploaded_file.name,
                        "profile": profile
                    }
                    st.session_state.processed_files.add(uploaded_file.name)
                    st.toast(f"Loaded '{uploaded_file.name}' as `{table_name}` ({profile['row_count']:,} rows)", icon="✅")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Failed to load '{uploaded_file.name}': {str(ex)}")

# Display active dataset cards
if num_tables > 0:
    st.markdown("### 📋 Active Datasets")
    table_items = list(st.session_state.tables.items())
    grid_cols = st.columns(min(len(table_items), 3))
    
    for idx, (t_name, meta) in enumerate(table_items):
        col = grid_cols[idx % 3]
        prof = meta["profile"]
        with col:
            with st.container():
                st.markdown(f"""
                <div style="background: rgba(19, 27, 46, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span class="table-tag">{t_name}</span>
                        <span style="font-size: 0.75rem; color: #94A3B8;">{meta['filename']}</span>
                    </div>
                    <div style="display: flex; gap: 14px; font-size: 0.85rem; color: #E2E8F0;">
                        <span><strong>{prof['row_count']:,}</strong> rows</span>
                        <span><strong>{prof['col_count']}</strong> columns</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"🔍 Inspect `{t_name}` Columns & Preview", expanded=False):
                    dtypes_df = pd.DataFrame(prof["columns"], columns=["Column", "Type"])
                    st.dataframe(dtypes_df, use_container_width=True, height=130)
                    st.caption("First 5 rows preview:")
                    st.dataframe(prof["preview"], use_container_width=True)

# Contextual questions strictly derived from the user's actual uploaded data
dynamic_suggestions = generate_dynamic_suggestions(st.session_state.tables)
if dynamic_suggestions:
    st.markdown("<div style='font-size: 0.83rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em; margin: 16px 0 8px 0;'>💡 Suggested Questions (from your data)</div>", unsafe_allow_html=True)
    chip_cols = st.columns(len(dynamic_suggestions))
    for i, suggestion in enumerate(dynamic_suggestions):
        with chip_cols[i]:
            if st.button(f"🔍 {suggestion}", key=f"dyn_sug_{i}", use_container_width=True):
                st.session_state.prompt_to_run = suggestion
                st.rerun()

st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;'>", unsafe_allow_html=True)


# ==============================================================================
# CHAT CONVERSATION
# ==============================================================================
st.markdown("### 💬 Conversational Analysis")

# Render conversation history
for msg in st.session_state.chat_history:
    role = msg.get("role", "user")
    with st.chat_message(role, avatar="🧑‍💻" if role == "user" else "🤖"):
        if role == "user":
            st.markdown(f"<div style='font-size: 1.05rem; font-weight: 500; color: #F8FAFC;'>{msg.get('content', '')}</div>", unsafe_allow_html=True)
        else:
            if msg.get("error"):
                st.error(f"❌ **Query Execution Error:**\n\n{msg['error']}")
                with st.expander("Attempted SQL"):
                    for i, s in enumerate(msg.get("attempted_sqls", [msg.get("sql", "")])):
                        st.code(s, language="sql")
            else:
                retry_text = f" • Repaired (retry {msg['retry_count']})" if msg.get("retry_count", 0) > 0 else ""
                exec_time = f" • {msg.get('exec_time', 0):.2f}s" if msg.get('exec_time') else ""
                st.markdown(f"<div class='meta-chip'>⚡ SQLite • {msg.get('model_used', model_name)}{retry_text}{exec_time}</div>", unsafe_allow_html=True)
                
                st.markdown(msg.get("answer", ""))
                
                # Render Chart if requested and built
                fig = msg.get("fig")
                echarts_html = msg.get("echarts_html")
                if msg.get("needs_chart"):
                    if visual_engine.startswith("✨") and echarts_html:
                        components.html(echarts_html, height=410)
                    elif fig is not None:
                        st.plotly_chart(fig, use_container_width=True)
                    elif echarts_html:
                        components.html(echarts_html, height=410)
                    
                # Show SQL used expander
                sql_used = msg.get("sql", "")
                if sql_used:
                    with st.expander("🔍 Show SQL Query", expanded=False):
                        st.code(sql_used, language="sql")
                        if msg.get("retry_count", 0) > 0:
                            st.caption(f"ℹ️ *Query was automatically repaired and succeeded on retry {msg['retry_count']}.*")
                            
                # Show Result Preview expander with CSV download button
                preview_df = msg.get("df_preview")
                if preview_df is not None and not preview_df.empty:
                    with st.expander("📋 View Data Results", expanded=False):
                        st.dataframe(preview_df, use_container_width=True)
                        csv_data = preview_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Results as CSV",
                            data=csv_data,
                            file_name="query_results.csv",
                            mime="text/csv",
                            key=f"dl_{id(msg)}"
                        )


# Chat input & Question handling
user_input = st.chat_input("Ask any question about your data (e.g. 'Show summary breakdown by category')...")

# Check if a suggestion chip was clicked
active_question = None
if user_input:
    active_question = user_input
elif st.session_state.prompt_to_run:
    active_question = st.session_state.prompt_to_run
    st.session_state.prompt_to_run = None

if active_question:
    if num_tables == 0:
        st.warning("⚠️ Please upload at least one CSV or Excel dataset first before asking questions.")
    elif not api_key:
        st.error("🔑 Groq API key is missing. Please ensure GROQ_API_KEY is defined in .env.")
    else:
        # Append user turn
        st.session_state.chat_history.append({
            "role": "user",
            "content": active_question
        })
        
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(f"<div style='font-size: 1.05rem; font-weight: 500; color: #F8FAFC;'>{active_question}</div>", unsafe_allow_html=True)
            
        with st.chat_message("assistant", avatar="🤖"):
            try:
                start_time = time.time()
                
                # 1. Prepare LLM Client and Schema Summary
                llm_client = get_llm_client(
                    provider="Groq",
                    model_name=model_name,
                    api_key=api_key,
                    base_url=None
                )
                active_tbls = list(st.session_state.tables.keys())
                schema_summary = get_schema_summary(engine, active_tables=active_tbls)
                
                # 2. Generate SQL plan with history
                with st.spinner(f"🧠 Formulating SQL using {model_name}..."):
                    sql_plan = llm_client.generate_sql(
                        schema_summary=schema_summary,
                        question=active_question,
                        history=st.session_state.chat_history[:-1]
                    )
                    
                # 3. Execute SQL with automated retry
                with st.spinner("⚡ Executing SQLite query..."):
                    query_result = execute_query_with_retry(
                        engine=engine,
                        initial_plan=sql_plan,
                        schema_summary=schema_summary,
                        question=active_question,
                        llm_client=llm_client
                    )
                    
                elapsed_time = time.time() - start_time
                
                # 4. Handle Execution Failure
                if not query_result.success:
                    st.error(f"❌ **Query Execution Error:**\n\n{query_result.error}")
                    with st.expander("Attempted SQL"):
                        for i, s in enumerate(query_result.attempted_sqls):
                            st.code(s, language="sql")
                            
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "error": query_result.error,
                        "attempted_sqls": query_result.attempted_sqls,
                        "sql": query_result.sql_used,
                        "exec_time": elapsed_time,
                        "model_used": model_name
                    })
                else:
                    # 5. Handle Execution Success
                    df_res = query_result.df
                    df_summary_str = format_dataframe_for_llm(df_res, max_rows=50)
                    
                    with st.spinner("✍️ Synthesizing answer..."):
                        plain_english_answer = llm_client.generate_answer(
                            question=active_question,
                            df_summary=df_summary_str
                        )
                        
                    # Build interactive visual charts (ECharts & Plotly)
                    fig = None
                    echarts_html = None
                    if query_result.needs_chart and df_res is not None and not df_res.empty:
                        fig = build_chart(df_res, query_result.chart_type)
                        echarts_html = build_echarts_html(df_res, query_result.chart_type)
                        
                    # Metadata tag
                    retry_text = f" • Repaired (retry {query_result.retry_count})" if query_result.retry_count > 0 else ""
                    st.markdown(f"<div class='meta-chip'>⚡ SQLite • {model_name}{retry_text} • {elapsed_time:.2f}s</div>", unsafe_allow_html=True)
                    
                    # Render outputs to current view
                    st.markdown(plain_english_answer)
                    if query_result.needs_chart:
                        if visual_engine.startswith("✨") and echarts_html:
                            components.html(echarts_html, height=410)
                        elif fig is not None:
                            st.plotly_chart(fig, use_container_width=True)
                        elif echarts_html:
                            components.html(echarts_html, height=410)
                        
                    with st.expander("🔍 Show SQL Query", expanded=False):
                        st.code(query_result.sql_used, language="sql")
                        if query_result.retry_count > 0:
                            st.caption(f"ℹ️ *Query was automatically repaired and succeeded on retry {query_result.retry_count}.*")
                            
                    if df_res is not None and not df_res.empty:
                        with st.expander("📋 View Data Results", expanded=False):
                            st.dataframe(df_res.head(20), use_container_width=True)
                            csv_data = df_res.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download Results as CSV",
                                data=csv_data,
                                file_name="query_results.csv",
                                mime="text/csv",
                                key=f"dl_live_{int(time.time()*1000)}"
                            )
                            
                    # Save to session state
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "answer": plain_english_answer,
                        "sql": query_result.sql_used,
                        "needs_chart": query_result.needs_chart,
                        "chart_type": query_result.chart_type,
                        "fig": fig,
                        "echarts_html": echarts_html,
                        "df_preview": df_res.head(20) if df_res is not None else None,
                        "retry_count": query_result.retry_count,
                        "exec_time": elapsed_time,
                        "model_used": model_name
                    })
            except Exception as app_err:
                err_msg = str(app_err)
                st.error(f"⚠️ Error: {err_msg}")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "error": err_msg,
                    "attempted_sqls": [],
                    "model_used": model_name
                })
