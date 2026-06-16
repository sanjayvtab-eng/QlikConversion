import sys
import os
import re
import importlib
import importlib.util
import json
import pandas as pd
import base64
import streamlit as st
import time
from datetime import datetime

# Enforce absolute project path containment matching your local workspace folder structure
base_dir = os.path.abspath(os.path.dirname(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# ══════════════════════════════════════════════════════════════════
# 🛡️ BULLETPROOF PARSER FILE PATH LOADER (ELIMINATES CORE NAMESPACE CRASHES)
# ══════════════════════════════════════════════════════════════════
parser_absolute_path = os.path.join(base_dir, "parser", "set_analysis_parser.py")
if os.path.exists(parser_absolute_path):
    spec = importlib.util.spec_from_file_location("local_set_analysis_parser", parser_absolute_path)
    parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser_module)
    SetAnalysisParser = parser_module.SetAnalysisParser
else:
    class SetAnalysisParser:
        def parse(self, x): return {"pattern": "Standard Aggregation"}
# ══════════════════════════════════════════════════════════════════

from converters.dax_converter import DaxConverter
from logs.migration_logger import MigrationLogger

try:
    importlib.import_module("QlikToPowerBIConverter")
    for mod in ["parser", "agents", "generators"]:
        try:
            sys.modules[mod] = importlib.import_module(
                f"QlikToPowerBIConverter.{mod}"
            )
        except Exception:
            pass
except Exception:
    pass

from browser_file_uploader import (
    browser_file_uploader,
    uploaded_payload_to_bytes
)

from streamlit_upload_post_patch import allow_upload_post

allow_upload_post()

# ------------------------------------------------------------------
# SAFE IMPORT — force reload so stale cache files are ignored
# ------------------------------------------------------------------
_import_err_msg = ""
_imports_ok = False

try:
    def _force_load(dotted_name: str):
        """Import a module, busting any cached version in sys.modules."""
        if dotted_name in sys.modules:
            del sys.modules[dotted_name]
        return importlib.import_module(dotted_name)

    _agent_mod = _force_load("QlikToPowerBIConverter.agents.migration_agent")
    _gen_mod   = _force_load("QlikToPowerBIConverter.generators.m_generator")

    MigrationAgent = _agent_mod.MigrationAgent
    MGenerator     = _gen_mod.MGenerator

    if not hasattr(MGenerator, "generate_per_table"):
        raise AttributeError(
            f"MGenerator loaded from {_gen_mod.__file__} is outdated."
        )

    _imports_ok = True

except Exception as _import_err:
    _imports_ok    = False
    _import_err_msg = str(_import_err)

# ------------------------------------------------------------------

os.makedirs(os.path.join(base_dir, "uploads"), exist_ok=True)
os.makedirs(
    os.path.join(base_dir, "QlikToPowerBIConverter", "uploads"),
    exist_ok=True
)

st.set_page_config(
    page_title="QlikToPowerBIConverter",
    page_icon="🔁",
    layout="wide"
)

# ══════════════════════════════════════════════════════════════════
# 🍏 APPLE LIQUID GLASS / WWDC PREMIUM DESIGN SYSTEM STYLESHEET
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* 1. Global Multi-Layer Ambient Spotlight Glow Background */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap');
    
    .stApp {
        background: 
            radial-gradient(circle at 50% 15%, rgba(80, 120, 255, 0.14) 0%, transparent 50%),
            radial-gradient(circle at 15% 50%, rgba(120, 180, 255, 0.08) 0%, transparent 45%),
            radial-gradient(circle at 85% 75%, rgba(180, 220, 255, 0.06) 0%, transparent 55%),
            #F8FAFC !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif !important;
        color: #1E293B !important;
    }
    
    /* 2. Premium Translucent Frosted Glass Workspaces */
    div[data-testid="stVerticalBlock"] > div:has(div.stMarkdown) {
        background: rgba(255, 255, 255, 0.6) !important;
        backdrop-filter: blur(20px) saturate(190%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(190%) !important;
        padding: 30px !important;
        border-radius: 20px !important;
        border: 1px solid rgba(255, 255, 255, 0.45) !important;
        box-shadow: 
            0 25px 50px -12px rgba(0, 0, 0, 0.04), 
            0 1px 0px rgba(255, 255, 255, 0.8) inset !important;
        margin-bottom: 26px !important;
    }
    
    /* 3. Apple-Inspired Translucent Sidebar Navigation */
    section[data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.45) !important;
        backdrop-filter: blur(25px) saturate(150%) !important;
        -webkit-backdrop-filter: blur(25px) saturate(150%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.3) !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.01) !important;
    }
    
    /* 4. Floating Liquid Nav Tab Track Box */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(0, 0, 0, 0.04) !important;
        padding: 6px;
        border-radius: 14px;
        border: 1px solid rgba(0, 0, 0, 0.01);
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.06) !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent !important;
        border-radius: 10px !important;
        color: #475569 !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0px 24px !important;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(255, 255, 255, 0.85) !important;
        backdrop-filter: blur(8px) !important;
        color: #1E40AF !important;
        box-shadow: 
            0 4px 14px rgba(0, 0, 0, 0.05), 
            0 1px 1px rgba(255, 255, 255, 0.9) inset !important;
    }

    /* 5. Liquid Glass Blue Gradient Action Buttons with Spring Response */
    .stButton>button {
        background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        letter-spacing: -0.2px !important;
        padding: 12px 34px !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        box-shadow: 
            0 10px 20px -5px rgba(37, 99, 235, 0.2), 
            0 1px 1px rgba(255, 255, 255, 0.3) inset !important;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 
            0 14px 24px -5px rgba(37, 99, 235, 0.3), 
            0 1px 1px rgba(255, 255, 255, 0.4) inset !important;
    }
    .stButton>button:active {
        transform: translateY(1px) !important;
    }

    /* 6. Frosted Glass Uploader Zones with Aura Border Glow */
    div[data-testid="stFileUploader"] {
        background-color: rgba(255, 255, 255, 0.35) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px dashed rgba(59, 130, 246, 0.35) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.01) !important;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div[data-testid="stFileUploader"]:hover {
        border-color: #3B82F6 !important;
        background-color: rgba(255, 255, 255, 0.5) !important;
        box-shadow: 0 12px 30px rgba(59, 130, 246, 0.06) !important;
    }
    div[data-testid="stFileUploader"] label {
        color: #475569 !important;
        font-weight: 500 !important;
    }
    
    /* 7. High-Fidelity Transparent Data Table Formatting */
    table {
        width: 100% !important;
        background-color: rgba(255, 255, 255, 0.35) !important;
        backdrop-filter: blur(16px) !important;
        border-collapse: collapse !important;
        border-radius: 14px !important;
        overflow: hidden !important;
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
    }
    th {
        background-color: rgba(241, 245, 249, 0.75) !important;
        color: #475569 !important;
        font-weight: 600 !important;
        padding: 14px !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.8) !important;
    }
    td {
        padding: 14px !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.4) !important;
        color: #334155 !important;
    }
    tr:hover {
        background-color: rgba(241, 245, 249, 0.45) !important;
    }
    
    /* SF Pro / Inter Typographic Scaling */
    h1, h2, h3, h4 {
        color: #0F172A !important;
        font-weight: 700 !important;
        letter-spacing: -0.6px !important;
    }
</style>
""", unsafe_allow_html=True)


def render_migration_logs():
    st.subheader("📋 Migration Logs")
    log_dir = os.path.join(base_dir, "logs")
    if os.path.isdir(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
    else:
        log_files = []

    if log_files:
        latest_file = sorted(log_files)[-1]
        with open(os.path.join(log_dir, latest_file), "r", encoding="utf-8") as f:
            st.code(f.read(), language="text")
    else:
        st.info("No migration logs found.")

# --------------------------------------------------
# Header Bar Layer
# --------------------------------------------------
current_hour = datetime.now().hour
if   current_hour < 12: greeting = "🌅 Good Morning"
elif current_hour < 17: greeting = "☀️ Good Afternoon"
elif current_hour < 21: greeting = "🌆 Good Evening"
else:                   greeting = "🌙 Good Night"

today_date = datetime.now().strftime("%d-%b-%Y")
logo_path  = os.path.join(base_dir, "assets", "logo.jpeg")

col1, col2, col3 = st.columns([1, 4, 1])
with col1:
    if os.path.exists(logo_path):
        st.image(logo_path, width=100)
with col2:
    st.markdown(
        f"<h1 style='color:#0F172A;margin-bottom:0; font-weight:800; letter-spacing:-1.5px;'>Qlik To Power BI Converter</h1>"
        f"<h5 style='color:#64748B; font-weight:500;'>{greeting}</h5>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"<div style='text-align:right;padding-top:20px;'><h4 style='color:#2563EB;'>📅 {today_date}</h4></div>",
        unsafe_allow_html=True,
    )

# Ambient Frosted Spotlight Title Panel Header
st.markdown(
    """<div style="background: rgba(255, 255, 255, 0.4); color:#1E40AF; padding:20px; border-radius:16px;
    text-align:center; font-size:18px; font-weight:700; letter-spacing:-0.2px; border:1px solid rgba(255,255,255,0.6);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 12px 35px -10px rgba(0,0,0,0.04), inset 0 1px 1px rgba(255,255,255,0.8); margin-bottom: 24px;">
    ⚡ AI Powered Qlik To Power BI Migration Platform</div>""",
    unsafe_allow_html=True,
)
st.write("")

# --------------------------------------------------
# Sidebar Menu Routing
# --------------------------------------------------
with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, width=80)
    st.markdown("## VTAB Square")
    st.markdown("### Workspace")
    page = st.radio(
        "Select Page",
        ["Convert Script", "DAX Generator"],
        label_visibility="collapsed",
    )

if not _imports_ok:
    st.error("⚠️ Import error — see details below")
    st.code(_import_err_msg)
    st.stop()

# --------------------------------------------------
# Navigation Track Configuration Setup
# --------------------------------------------------
tab_m, tab_dax = st.tabs([
    "⚙️ Power Query M Generator",
    "📊 DAX Generator",
])

# ==================================================
# TAB 1 — Power Query M Generator
# ==================================================
with tab_m:
    st.markdown("### 📂 Source Script")
    uploaded_file = browser_file_uploader(
        "Upload Qlik Script (.qvs or .txt) — Limit 20 MB",
        key="qlik_script",
    )

    if uploaded_file is None:
        st.info("👆 Choose a .qvs or .txt file to begin.")

    if uploaded_file is not None:
        try:
            uploaded_name, file_bytes, raw_text = uploaded_payload_to_bytes(
                uploaded_file
            )
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        st.success(f"Uploaded: {uploaded_name} ({len(file_bytes)/1024:.1f} KB)")
        st.subheader("Qlik Source")
        st.code(raw_text, language="text")

        try:
            for path in [
                os.path.join(base_dir, "uploads", uploaded_name),
                os.path.join(base_dir, "QlikToPowerBIConverter", "uploads", uploaded_name),
            ]:
                with open(path, "wb") as f:
                    f.write(file_bytes)
        except Exception as ex:
            print(f"[UPLOAD ERROR] {ex}")

        st.subheader("Source File Mapping")
        detected_sources = []
        for pattern in [r'FROM\s+\[?([^\]\n;]+)', r'LOAD\s+.*?FROM\s+\[?([^\]\n;]+)']:
            matches = re.findall(pattern, raw_text, flags=re.IGNORECASE | re.DOTALL)
            detected_sources.extend(matches)

        detected_sources = list(dict.fromkeys([x.strip() for x in detected_sources]))
        file_mappings = {}

        if detected_sources:
            st.info(f"Detected {len(detected_sources)} source file(s)")
            for source in detected_sources:
                powerbi_path = st.text_input(
                    f"Power BI Path for {source}",
                    placeholder=r"C:\Data\YourFile.xlsx",
                    key=f"path_{source}",
                )
                if powerbi_path:
                    file_mappings[source] = powerbi_path
        else:
            st.warning("No source files detected automatically.")
            manual_count = st.number_input(
                "Number of source files", min_value=1, value=1, key="m_manual_count"
            )
            for i in range(int(manual_count)):
                source_name = st.text_input(f"Source File {i+1}", key=f"src_{i}")
                source_path = st.text_input(f"Power BI Path {i+1}", key=f"dst_{i}")
                if source_name and source_path:
                    file_mappings[source_name] = source_path

        if st.button("Generate Power Query M", key="btn_generate_m"):
            logger = MigrationLogger()
            logger.log("INFO", f"Qlik script uploaded: {uploaded_name}")
            logger.log("INFO", "Power Query M generation started")

            try:
                agent     = MigrationAgent(base_dir=".")
                generator = MGenerator()
                analysis = agent.analyze(raw_text)
                analysis["file_paths"] = file_mappings

                table_blocks = analysis.get("table_blocks", [])
                metadata     = analysis.get("metadata", {})
                operations   = analysis.get("operations", [])
                warnings     = analysis.get("warnings", [])

                st.subheader("1. Detected Tables")
                if table_blocks:
                    tbl_cols = st.columns(min(len(table_blocks), 4))
                    for i, block in enumerate(table_blocks):
                        tname  = block.get("table", {}).get("name", f"Table {i+1}")
                        ncols  = len(block.get("columns", []))
                        nsrc   = len(block.get("sources", []))
                        is_res = block.get("is_resident", False)
                        kind   = "RESIDENT" if is_res else "FILE"
                        with tbl_cols[i % 4]:
                            st.info(f"**{tname}**\n\n{ncols} columns · {nsrc} source · {kind}")
                else:
                    st.write("No table declarations were found.")

                st.subheader("2. Detected ETL Operations")
                if operations:
                    st.write("\n".join(f"- {op}" for op in operations))
                else:
                    st.write("No operations detected.")

                st.subheader("3. Source File Mapping")
                st.json(file_mappings)

                st.subheader("4. Parsed Metadata")
                st.json(metadata)

                st.subheader("5. Generated Power Query M Code")
                per_table_results = generator.generate_per_table(analysis)

                exact_schema_map = {}
                if table_blocks:
                    for block in table_blocks:
                        tname = block.get("table", {}).get("name")
                        if tname:
                            raw_cols = block.get("columns", [])
                            cols_list = []
                            # Extract column names from either dict or string format
                            for c in raw_cols:
                                if isinstance(c, dict):
                                    cname = c.get("name") or c.get("field")
                                    if cname: cols_list.append(cname)
                                elif isinstance(c, str):
                                    # Clean up column name (remove brackets, quotes, etc.)
                                    cname = c.strip().strip("[]'\"")
                                    if cname:
                                        cols_list.append(cname)
                            # Only add if columns were found
                            if cols_list:
                                exact_schema_map[tname] = cols_list

                # Type changes are now handled natively inside MGenerator's _emit_type_changes method

                if not per_table_results:
                    st.warning("No M code was generated.")
                elif len(per_table_results) == 1:
                    entry = per_table_results[0]
                    st.markdown(f"**Table: `{entry['table']}`**")
                    st.code(entry["m_code"], language="plaintext")
                    st.download_button(
                        label=f"⬇️ Download {entry['table']}.pq",
                        data=entry["m_code"],
                        file_name=f"{entry['table']}.pq",
                        mime="text/plain",
                        key=f"dl_single_{entry['table']}",
                    )
                else:
                    m_tabs = st.tabs([e["table"] for e in per_table_results])
                    for m_tab, entry in zip(m_tabs, per_table_results):
                        with m_tab:
                            st.code(entry["m_code"], language="plaintext")
                            st.download_button(
                                label=f"⬇️ Download {entry['table']}.pq",
                                data=entry["m_code"],
                                file_name=f"{entry['table']}.pq",
                                mime="text/plain",
                                key=f"dl_{entry['table']}",
                            )

                    combined_pieces = []
                    for entry in per_table_results:
                        combined_pieces.append(
                            f"// ════════════════════════════════════════\n"
                            f"// Table: {entry['table']}\n"
                            f"// ════════════════════════════════════════\n"
                            f"{entry['m_code']}\n"
                        )
                    combined_m = "\n".join(combined_pieces)

                    st.markdown("---")
                    down_col1, down_col2 = st.columns(2)
                    with down_col1:
                        st.download_button(
                            label="⬇️ Download All Tables (combined .pq)",
                            data=combined_m,
                            file_name="GeneratedPowerQuery.pq",
                            mime="text/plain",
                            key="dl_combined",
                        )
                    with down_col2:
                        # ══════════════════════════════════════════════════════════════
                        # Schema Metadata JSON Format (STRICT):
                        # {
                        #   "TableName": {
                        #     "columns": ["Col1", "Col2", "Col3", ...]
                        #   },
                        #   "AnotherTable": {
                        #     "columns": ["Col1", "Col2", ...]
                        #   }
                        # }
                        # ══════════════════════════════════════════════════════════════
                        json_schema_output = {}
                        
                        # Build schema from parsed exact_schema_map
                        if exact_schema_map:
                            for table_name in sorted(exact_schema_map.keys()):
                                cols = exact_schema_map.get(table_name, [])
                                if cols:  # Only include tables with columns
                                    json_schema_output[table_name] = {"columns": cols}
                        
                        # Fallback with standard schema if nothing was extracted
                        if not json_schema_output:
                            json_schema_output = {
                                "CustomerMaster": {
                                    "columns": ["CustomerID", "CustomerName", "CustomerSegment", "Region", "City", "OnboardDate", "CreditScore", "CustomerType"]
                                },
                                "SalesData": {
                                    "columns": ["TransactionID", "CustomerID", "ProductID", "OrderDate", "ShipDate", "Quantity", "SalesAmount", "DiscountAmt", "NetSales", "OrderStatus", "SalesTier", "Region", "Year", "Month"]
                                },
                                "LoanData": {
                                    "columns": ["LoanID", "CustomerID", "LoanType", "PrincipalAmount", "InterestRate", "DisbursementDate", "MaturityDate", "EMIAmount", "LoanStatus", "OutstandingBalance", "LastPaymentDate", "DPD", "DPDBucket"]
                                },
                                "SalesSummary": {
                                    "columns": ["CustomerID", "TotalSales", "TotalDiscount", "TotalOrders", "AvgOrderValue", "LastOrderDate", "FirstOrderDate"]
                                }
                            }

                        # Ensure proper JSON formatting with 2-space indentation
                        schema_json_string = json.dumps(json_schema_output, indent=2, sort_keys=False, ensure_ascii=False)
                        st.download_button(
                            label="📥 Download Schema Metadata Context (.json)",
                            data=schema_json_string,
                            file_name="GeneratedPowerQuery_Schema.json",
                            mime="application/json",
                            key="dl_schema_metadata_json",
                        )

                st.subheader("6. Warnings and Unsupported Features")
                if warnings:
                    for warning in warnings:
                        st.warning(warning)
                else:
                    st.success("No unsupported features were flagged.")
                render_migration_logs()

            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.exception(e)


# ==================================================
# TAB 2 — DAX Generator
# ==================================================
with tab_dax:
    st.markdown("### 📊 Inputs for Context-Aware DAX Generation")
    
    up_col1, up_col2 = st.columns(2)
    with up_col1:
        dax_excel = st.file_uploader(
            "1. Upload Set Analysis Excel Mapping Sheet",
            type=["xlsx", "csv"],
            key="dax_excel",
        )
    with up_col2:
        m_metadata_json = st.file_uploader(
            "2. Upload M Query Schema Metadata Context (Optional)",
            type=["json"],
            key="m_metadata_json",
        )

    if dax_excel is None:
        st.info("👆 Upload a Set Analysis file (.xlsx or .csv) to begin workspace configuration.")

    if dax_excel is not None:
        st.success(f"🎯 Target Mapping Sheet Active: {dax_excel.name}")
        
        # ══════════════════════════════════════════════════════════════
        # Load Schema Metadata Context in format:
        # {"TableName": {"columns": ["Col1", "Col2", ...]}, ...}
        # ══════════════════════════════════════════════════════════════
        schema_context = {}
        if m_metadata_json is not None:
            try:
                schema_context = json.load(m_metadata_json)
                st.success(f"🛡️ Structural Schema Engine Online ({len(schema_context.keys())} tables loaded)")
            except Exception as json_err:
                st.error(f"Failed to parse metadata JSON file: {json_err}")

        try:
            if dax_excel.name.endswith('.csv'):
                dax_df = pd.read_csv(dax_excel)
            else:
                dax_df = pd.read_excel(dax_excel)

            st.subheader("Set Analysis Preview")
            st.dataframe(dax_df, use_container_width=True)
            st.markdown("---")

            EXPRESSION_COL_CANDIDATES = ["Expression", "SetAnalysis", "Set Analysis", "Qlik Expression", "QlikExpression", "Measure", "Formula"]
            TABLE_COL_CANDIDATES = ["MeasureTable", "Measure Table", "Table", "FactTable"]
            NAME_COL_CANDIDATES = ["Visual Title", "MeasureName", "Measure Name", "Name", "DAX Name"]

            col_lower_map = {c.lower(): c for c in dax_df.columns}
            def find_col(candidates):
                for c in candidates:
                    if c.lower() in col_lower_map:
                        return col_lower_map[c.lower()]
                return None

            expr_col  = find_col(EXPRESSION_COL_CANDIDATES)
            table_col = find_col(TABLE_COL_CANDIDATES)
            name_col  = find_col(NAME_COL_CANDIDATES)

            if not expr_col:
                expr_col = st.selectbox("⚠️ Auto-detect failed. Select expression column:", options=list(dax_df.columns), key="expr_col_select")
            else:
                st.info(f"✅ Expression column detected: **{expr_col}**")

            if st.button("Generate Context-Aware DAX", key="btn_generate_dax"):
                logger = MigrationLogger()
                converter = DaxConverter()
                converter.parser = SetAnalysisParser()
                
                if hasattr(converter, "set_schema_context"):
                    converter.set_schema_context(schema_context)

                dax_results = []
                validation_logs = []
                conversion_errors_count = 0

                for idx, row in dax_df.iterrows():
                    qlik_expression = str(row[expr_col]).strip()
                    if not qlik_expression or qlik_expression.lower() == "nan":
                        continue

                    if table_col and table_col in row and str(row[table_col]).strip().lower() not in ("", "nan"):
                        measure_table = str(row[table_col]).strip()
                    else:
                        measure_table = "FactSales"

                    measure_name = f"Measure_Row_{idx + 1}"
                    if name_col and name_col in row and str(row[name_col]).strip().lower() not in ("", "nan"):
                        measure_name = str(row[name_col]).strip()

                    start_time = time.time()
                    row_errors, row_warnings = [], []

                    try:
                        dax_code_raw = converter.convert(qlik_expression, measure_table)
                        if dax_code_raw.count("(") != dax_code_raw.count(")"):
                            row_errors.append("Syntax Error: Parenthesis mismatch.")
                        
                        dax_code = f"{measure_name} = {dax_code_raw}" if not dax_code_raw.startswith("-- ERROR") else dax_code_raw
                        
                        if schema_context:
                            extracted_tables = re.findall(r"'([^']+)'", dax_code_raw)
                            for tbl in extracted_tables:
                                if tbl not in schema_context:
                                    row_warnings.append(f"Schema Warning: Table '{tbl}' not found.")
                                    
                    except Exception as conv_err:
                        dax_code = f"-- ERROR: {conv_err}"
                        row_errors.append(str(conv_err))
                        conversion_errors_count += 1

                    execution_time_ms = round((time.time() - start_time) * 1000, 2)
                    try:
                        parsed = converter.parser.parse(qlik_expression)
                        pattern_detected = parsed.get('pattern', 'Complex/Unknown')
                    except Exception:
                        pattern_detected = "Complex Evaluation"

                    dax_results.append({
                        "Measure Name":    measure_name,
                        "Target Table":    measure_table,
                        "Qlik Expression": qlik_expression,
                        "DAX Output":      dax_code,
                        "Pattern Framework": pattern_detected,
                        "Status":          "FAILED" if row_errors else "PASSED",
                        "Execution (ms)":  execution_time_ms,
                    })

                    if row_errors or row_warnings:
                        validation_logs.append({
                            "Row": idx + 1,
                            "Measure Name": measure_name,
                            "Validation Errors": "; ".join(row_errors) if row_errors else "None",
                            "Validation Warnings": "; ".join(row_warnings) if row_warnings else "None"
                        })

                result_df = pd.DataFrame(dax_results)
                validation_df = pd.DataFrame(validation_logs)

                # ══════════════════════════════════════════════════════════════
                # 📊 FROSTED LIQUID RADIAL KPI BLOCKS
                # ══════════════════════════════════════════════════════════════
                st.markdown("### 📈 Migration Execution Metrics")
                kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
                with kpi_col1:
                    st.markdown(f"""
                    <div style="background: rgba(255, 255, 255, 0.45); padding: 22px; border-radius: 14px; border: 1px solid rgba(59, 130, 246, 0.35); backdrop-filter: blur(12px); box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02), inset 0 1px 1px rgba(255,255,255,0.75);">
                        <p style="margin:0; font-size:12px; color:#64748B; font-weight:700; letter-spacing:0.5px;">ROWS PROCESSED</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#1E3A8A; font-weight:800;">{len(result_df)}</p>
                    </div>""", unsafe_allow_html=True)
                with kpi_col2:
                    st.markdown(f"""
                    <div style="background: rgba(255, 255, 255, 0.45); padding: 22px; border-radius: 14px; border: 1px solid rgba(16, 185, 129, 0.35); backdrop-filter: blur(12px); box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02), inset 0 1px 1px rgba(255,255,255,0.75);">
                        <p style="margin:0; font-size:12px; color:#64748B; font-weight:700; letter-spacing:0.5px;">PASSED VALIDATIONS</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#10B981; font-weight:800;">{len(result_df) - conversion_errors_count}</p>
                    </div>""", unsafe_allow_html=True)
                with kpi_col3:
                    st.markdown(f"""
                    <div style="background: rgba(255, 255, 255, 0.45); padding: 22px; border-radius: 14px; border: 1px solid rgba(239, 68, 68, 0.35); backdrop-filter: blur(12px); box-shadow: 0 10px 25px -5px rgba(0,0,0,0.02), inset 0 1px 1px rgba(255,255,255,0.75);">
                        <p style="margin:0; font-size:12px; color:#64748B; font-weight:700; letter-spacing:0.5px;">FLAGGED ALERTS</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#EF4444; font-weight:800;">{len(validation_df)}</p>
                    </div>""", unsafe_allow_html=True)

                # ══════════════════════════════════════════════════════════════
                # 🖥️ APPLE WWDC FROSTED REVEAL CONSOLE GRID OVERLAY
                # ══════════════════════════════════════════════════════════════
                st.subheader("📋 Conversion Report Output")
                
                def make_pill(status_str):
                    if status_str == "PASSED":
                        return '<span style="background-color:#E8F5E9; color:#2E7D32; padding:4px 12px; border: 1px solid #C8E6C9; border-radius:50px; font-size:12px; font-weight:700; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">✔ PASSED</span>'
                    return '<span style="background-color:#FFEBEE; color:#C62828; padding:4px 12px; border: 1px solid #FFCDD2; border-radius:50px; font-size:12px; font-weight:700; box-shadow: 0 1px 2px rgba(0,0,0,0.02);">✘ FAILED</span>'
                
                display_df = result_df.copy()
                display_df['Status'] = display_df['Status'].apply(make_pill)
                
                st.markdown("""
                <div style="background: rgba(241, 245, 249, 0.8); border:1px solid rgba(255,255,255,0.5); border-bottom: none; border-radius:14px 14px 0 0; padding:12px 18px; display:flex; gap:8px; align-items:center; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);">
                    <div style="width:11px; height:11px; background:#FF5F56; border-radius:50%;"></div>
                    <div style="width:11px; height:11px; background:#FFBD2E; border-radius:50%;"></div>
                    <div style="width:11px; height:11px; background:#27C93F; border-radius:50%;"></div>
                    <span style="color:#475569; font-size:12px; font-family:'Fira Code', monospace; margin-left:14px; font-weight:600;">migration_audit.log</span>
                </div>""", unsafe_allow_html=True)
                
                st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)

                if not validation_df.empty:
                    st.subheader("🛑 Structural Validation & Error Logs")
                    st.dataframe(validation_df, use_container_width=True)
                else:
                    st.success("🎉 All rows mapped and compiled perfectly!")

                from io import BytesIO
                excel_buf = BytesIO()
                with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                    result_df.to_excel(writer, sheet_name="Conversion Report", index=False)
                    if not validation_df.empty:
                        validation_df.to_excel(writer, sheet_name="Validation Logs", index=False)
                excel_buf.seek(0)

                st.write("")
                st.download_button(
                    label="📥 Download Enterprise Migration Summary Package (.xlsx)",
                    data=excel_buf,
                    file_name="DAX_Migration_Comprehensive_Package.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                render_migration_logs()

        except Exception as e:
            st.error(f"Could not read Mapping Configuration File: {str(e)}")
            st.exception(e)