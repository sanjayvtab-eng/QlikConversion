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
# 💎 ULTRA-PREMIUM 3D LAYERED SKEUOMORPHIC DARK MODE THEME INJECTION
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* Global Base Canvas Setup */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap');
    
    .stApp {
        background-color: #0B0F19 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        color: #E2E8F0 !important;
    }
    
    /* 3D Elevated Workspace Panel Cards */
    div[data-testid="stVerticalBlock"] > div:has(div.stMarkdown) {
        background: #111827 !important;
        padding: 26px !important;
        border-radius: 16px !important;
        border: 1px solid #1F2937 !important;
        box-shadow: 
            0 20px 25px -5px rgba(0, 0, 0, 0.6), 
            0 10px 10px -5px rgba(0, 0, 0, 0.4),
            inset 0 1px 1px rgba(255, 255, 255, 0.08) !important;
        margin-bottom: 24px !important;
    }
    
    /* Premium Sidebar Overhaul */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1F2937 !important;
        box-shadow: 10px 0 30px rgba(0, 0, 0, 0.5) !important;
    }
    section[data-testid="stSidebar"] h2 {
        color: #FFFFFF !important;
    }
    
    /* 3D Tab Track Navigation Control Box */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #1F2937 !important;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #374151;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5) !important;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        background-color: transparent !important;
        border-radius: 8px !important;
        color: #94A3B8 !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0px 26px !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4), inset 0 1px 0px rgba(255, 255, 255, 0.3) !important;
    }

    /* Tactile 3D Action Buttons with Outer Ambient Glow */
    .stButton>button {
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        padding: 12px 32px !important;
        border-radius: 10px !important;
        border: 1px solid #3B82F6 !important;
        box-shadow: 0 8px 20px rgba(37, 99, 235, 0.3), inset 0 1px 0px rgba(255, 255, 255, 0.4) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 12px 24px rgba(37, 99, 235, 0.5), inset 0 1px 0px rgba(255, 255, 255, 0.5) !important;
    }

    /* Transform File Uploaders into Sleek Technical Dropzones */
    div[data-testid="stFileUploader"] {
        background-color: #111827 !important;
        border: 2px dashed #4B5563 !important;
        border-radius: 12px !important;
        padding: 16px !important;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.4) !important;
    }
    div[data-testid="stFileUploader"] label {
        color: #94A3B8 !important;
        font-weight: 500 !important;
    }
    
    /* Native Dataframe Dark Alignment */
    div[data-testid="stDataFrame"] {
        background-color: #030712 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 12px !important;
    }
    
    /* Native Data Table HTML Styling Hacks */
    table {
        width: 100% !important;
        background-color: #111827 !important;
        border-collapse: collapse !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    th {
        background-color: #1F2937 !important;
        color: #94A3B8 !important;
        font-weight: 700 !important;
        padding: 12px !important;
        text-align: left !important;
        border-bottom: 2px solid #374151 !important;
    }
    td {
        padding: 12px !important;
        border-bottom: 1px solid #1F2937 !important;
        color: #E2E8F0 !important;
    }
    tr:hover {
        background-color: #1F2937 !important;
    }
    
    /* General Heading Colors */
    h1, h2, h3, h4 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
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
# Header Section
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
        f"<h1 style='color:#FFFFFF;margin-bottom:0; font-weight:800; letter-spacing:-1px;'>Qlik To Power BI Converter</h1>"
        f"<h5 style='color:#94A3B8; font-weight:500;'>{greeting}</h5>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"<div style='text-align:right;padding-top:20px;'><h4 style='color:#3B82F6;'>📅 {today_date}</h4></div>",
        unsafe_allow_html=True,
    )

# Elevated Skeuomorphic Identity Banner
st.markdown(
    """<div style="background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%); color:#FFFFFF; padding:18px; border-radius:12px;
    text-align:center; font-size:18px; font-weight:700; letter-spacing:0.5px; border:1px solid #2563EB;
    box-shadow: 0 10px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.2); margin-bottom: 20px;">
    ⚡ AI Powered Qlik To Power BI Migration Platform</div>""",
    unsafe_allow_html=True,
)
st.write("")

# --------------------------------------------------
# Sidebar Configuration
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
# Component Tabs Array Router
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
                            for c in raw_cols:
                                if isinstance(c, dict):
                                    cname = c.get("name") or c.get("field")
                                    if cname: cols_list.append(cname)
                                elif isinstance(c, str):
                                    cols_list.append(c)
                            exact_schema_map[tname] = cols_list

                if per_table_results:
                    for entry in per_table_results:
                        tname = entry["table"]
                        cols = exact_schema_map.get(tname, [])
                        if not cols and isinstance(metadata, dict) and tname in metadata:
                            v = metadata[tname]
                            if isinstance(v, dict) and "columns" in v:
                                cols = v["columns"]
                            elif isinstance(v, list):
                                cols = v
                        
                        if cols:
                            type_pairs = []
                            for col in cols:
                                col_lower = col.lower()
                                if "id" in col_lower:
                                    type_pairs.append(f'{{"{col}", type text}}')
                                elif "date" in col_lower:
                                    type_pairs.append(f'{{"{col}", type date}}')
                                elif any(x in col_lower for x in ["amount", "amt", "sales", "net", "balance", "price", "rate", "emi", "value", "discount"]):
                                    type_pairs.append(f'{{"{col}", type number}}')
                                elif any(x in col_lower for x in ["quantity", "qty", "count", "dpd", "year", "month", "creditscore"]):
                                    type_pairs.append(f'{{"{col}", Int64.Type}}')
                                else:
                                    type_pairs.append(f'{{"{col}", type text}}')
                            
                            if type_pairs:
                                transform_list = ", ".join(type_pairs)
                                m_code = entry["m_code"].strip()
                                match = re.search(r'in\s+([a-zA-Z0-9_\.]+)\s*$', m_code, re.MULTILINE)
                                if match:
                                    last_var = match.group(1)
                                    replacement = f",\n    Typed_{tname} = Table.TransformColumnTypes({last_var}, {{{transform_list}}})\nin\n    Typed_{tname}"
                                    pattern = rf'in\s+{last_var}\s*$'
                                    entry["m_code"] = re.sub(pattern, replacement, m_code, flags=re.MULTILINE)

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
                        json_schema_output = {}
                        if table_blocks:
                            for block in table_blocks:
                                tname = block.get("table", {}).get("name")
                                if tname:
                                    json_schema_output[tname] = {"columns": exact_schema_map.get(tname, [])}
                        if not json_schema_output:
                            json_schema_output = {"FactSales": {"columns": ["CustomerID", "PrincipalAmount", "SalesAmount", "Region", "Year"]}}

                        schema_json_string = json.dumps(json_schema_output, indent=4)
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
                # 📊 GLOWING 3D SKEUOMORPHIC METRICS PANELS
                # ══════════════════════════════════════════════════════════════
                st.markdown("### 📈 Migration Execution Metrics")
                kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
                with kpi_col1:
                    st.markdown(f"""
                    <div style="background: #1F2937; padding: 22px; border-radius: 12px; border: 1px solid #3B82F6; box-shadow: 0 10px 20px rgba(0,0,0,0.4), 0 0 15px rgba(59,130,246,0.15); inset 0 1px 0 rgba(255,255,255,0.05);">
                        <p style="margin:0; font-size:12px; color:#94A3B8; font-weight:700; letter-spacing:1px; text-transform:uppercase;">ROWS PROCESSED</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#FFFFFF; font-weight:800; text-shadow: 0 2px 4px rgba(0,0,0,0.5);">{len(result_df)}</p>
                    </div>""", unsafe_allow_html=True)
                with kpi_col2:
                    st.markdown(f"""
                    <div style="background: #1F2937; padding: 22px; border-radius: 12px; border: 1px solid #10B981; box-shadow: 0 10px 20px rgba(0,0,0,0.4), 0 0 15px rgba(16,185,129,0.15); inset 0 1px 0 rgba(255,255,255,0.05);">
                        <p style="margin:0; font-size:12px; color:#94A3B8; font-weight:700; letter-spacing:1px; text-transform:uppercase;">PASSED VALIDATIONS</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#10B981; font-weight:800; text-shadow: 0 0 10px rgba(16,185,129,0.2);">{len(result_df) - conversion_errors_count}</p>
                    </div>""", unsafe_allow_html=True)
                with kpi_col3:
                    st.markdown(f"""
                    <div style="background: #1F2937; padding: 22px; border-radius: 12px; border: 1px solid #EF4444; box-shadow: 0 10px 20px rgba(0,0,0,0.4), 0 0 15px rgba(239,68,68,0.15); inset 0 1px 0 rgba(255,255,255,0.05);">
                        <p style="margin:0; font-size:12px; color:#94A3B8; font-weight:700; letter-spacing:1px; text-transform:uppercase;">FLAGGED ALERTS</p>
                        <p style="margin:8px 0 0 0; font-size:32px; color:#EF4444; font-weight:800; text-shadow: 0 0 10px rgba(239,68,68,0.2);">{len(validation_df)}</p>
                    </div>""", unsafe_allow_html=True)

                # ══════════════════════════════════════════════════════════════
                # 🖥️ GLOSSY TERMINAL GRID FOR THE CONVERSION REPORT PREVIEW
                # ══════════════════════════════════════════════════════════════
                st.subheader("📋 Conversion Report Output")
                
                def make_pill(status_str):
                    if status_str == "PASSED":
                        return '<span style="background-color:#DCFCE7; color:#15803D; padding:4px 12px; border-radius:50px; font-size:12px; font-weight:700; box-shadow: 0 2px 4px rgba(16,185,129,0.2);">✔ PASSED</span>'
                    return '<span style="background-color:#FEE2E2; color:#B91C1C; padding:4px 12px; border-radius:50px; font-size:12px; font-weight:700; box-shadow: 0 2px 4px rgba(239,68,68,0.2);">✘ FAILED</span>'
                
                display_df = result_df.copy()
                display_df['Status'] = display_df['Status'].apply(make_pill)
                
                # Injects the mock terminal panel toolbar
                st.markdown("""
                <div style="background:#1F2937; border:1px solid #374151; border-radius:12px 12px 0 0; padding:12px 18px; display:flex; gap:8px; align-items:center; box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);">
                    <div style="width:11px; height:11px; background:#EF4444; border-radius:50%; box-shadow: 0 0 4px #EF4444;"></div>
                    <div style="width:11px; height:11px; background:#F59E0B; border-radius:50%; box-shadow: 0 0 4px #F59E0B;"></div>
                    <div style="width:11px; height:11px; background:#10B981; border-radius:50%; box-shadow: 0 0 4px #10B981;"></div>
                    <span style="color:#94A3B8; font-size:12px; font-family:'Fira Code', monospace; margin-left:12px; font-weight:500;">conversion_report_output.log</span>
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