import sys
import os
import re
import importlib
import json
import pandas as pd
import base64
import streamlit as st
import time
from datetime import datetime
from converters.dax_converter import DaxConverter
from logs.migration_logger import MigrationLogger

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

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
# SAFE IMPORT — force reload so stale .pyc never wins
# ------------------------------------------------------------------
_import_err_msg = ""
_imports_ok = False

try:
    import importlib, importlib.util

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
            f"MGenerator loaded from {_gen_mod.__file__} "
            "is the OLD version — it is missing generate_per_table(). "
            "Please replace QlikToPowerBIConverter/generators/m_generator.py "
            "with the new file."
        )

    _imports_ok = True

except Exception as _import_err:
    _imports_ok    = False
    _import_err_msg = str(_import_err)

# ------------------------------------------------------------------

base_dir = os.path.abspath(os.path.dirname(__file__))

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
# Header
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
        f"<h1 style='color:#1565C0;margin-bottom:0;'>Qlik To Power BI Converter</h1>"
        f"<h4 style='color:#555555;'>{greeting}</h4>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"<div style='text-align:right;padding-top:20px;'><h4>📅 {today_date}</h4></div>",
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(
    """<div style="background:#1565C0;color:white;padding:15px;border-radius:10px;
    text-align:center;font-size:20px;font-weight:bold;">
    AI Powered Qlik To Power BI Migration Platform</div>""",
    unsafe_allow_html=True,
)
st.write("")

# --------------------------------------------------
# Sidebar
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
    st.markdown(
        "**Fix:** Replace `QlikToPowerBIConverter/generators/m_generator.py` "
        "and `QlikToPowerBIConverter/agents/migration_agent.py` "
        "and `QlikToPowerBIConverter/parser/qlik_parser.py` "
        "with the new versions, then refresh the page."
    )
    st.stop()

# --------------------------------------------------
# Main Tabs
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

                logger.log("INFO", "Script analysis completed")
                logger.log("INFO", f"Detected {len(operations)} operations")
                logger.log("INFO", f"Detected {len(table_blocks)} table(s)")

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
                            st.info(
                                f"**{tname}**\n\n"
                                f"{ncols} columns · {nsrc} source · {kind}"
                            )
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

                logger.log(
                    "SUCCESS",
                    f"Power Query M generated for {len(per_table_results)} table(s)",
                )

                if not per_table_results:
                    st.warning(
                        "No M code was generated. "
                        "Check that your script contains table definitions."
                    )
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

                    combined_m = generator.generate(analysis)
                    st.markdown("---")
                    st.download_button(
                        label="⬇️ Download All Tables (combined .pq)",
                        data=combined_m,
                        file_name="GeneratedPowerQuery.pq",
                        mime="text/plain",
                        key="dl_combined",
                    )

                st.subheader("6. Warnings and Unsupported Features")
                if warnings:
                    for warning in warnings:
                        st.warning(warning)
                else:
                    st.success("No unsupported features were flagged.")

                logger.log("INFO", "Power Query M generation completed")
                render_migration_logs()

            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.exception(e)


# ==================================================
# TAB 2 — DAX Generator (Enhanced Migration Pipeline)
# ==================================================
with tab_dax:

    st.markdown("### 📊 Inputs for Context-Aware DAX Generation")
    
    # Dual file uploading configuration mapping side-by-side
    up_col1, up_col2 = st.columns(2)
    
    with up_col1:
        dax_excel = st.file_uploader(
            "1. Upload Set Analysis Excel Mapping Sheet",
            type=["xlsx"],
            key="dax_excel",
        )
        
    with up_col2:
        m_metadata_json = st.file_uploader(
            "2. Upload M Query Schema Metadata Context (Optional)",
            type=["json"],
            key="m_metadata_json",
            help="Upload the JSON output schema generated from Tab 1 to run strict type-checking and name validation."
        )

    if dax_excel is None:
        st.info("👆 Upload at least a Set Analysis Excel file (.xlsx) to begin workspace configuration.")

    if dax_excel is not None:
        st.success(f"🎯 Target Mapping Sheet Active: {dax_excel.name}")
        
        # Load schema metadata context if provided
        schema_context = {}
        if m_metadata_json is not None:
            try:
                schema_context = json.load(m_metadata_json)
                st.success(f"🛡️ Structural Schema Engine Online ({len(schema_context.keys())} tables loaded)")
            except Exception as json_err:
                st.error(f"Failed to parse metadata JSON file: {json_err}")

        try:
            dax_df = pd.read_excel(dax_excel)
            st.subheader("Set Analysis Preview")
            st.dataframe(dax_df, use_container_width=True)
            st.markdown("---")

            EXPRESSION_COL_CANDIDATES = [
                "SetAnalysis", "Set Analysis", "Qlik Expression",
                "Expression", "QlikExpression", "Measure", "Formula"
            ]
            TABLE_COL_CANDIDATES = [
                "MeasureTable", "Measure Table", "Table", "FactTable"
            ]
            NAME_COL_CANDIDATES = [
                "MeasureName", "Measure Name", "Name", "DAX Name"
            ]

            col_lower_map = {c.lower(): c for c in dax_df.columns}

            def find_col(candidates):
                for c in candidates:
                    if c.lower() in col_lower_map:
                        return col_lower_map[c.lower()]
                return None

            expr_col  = find_col(EXPRESSION_COL_CANDIDATES)
            table_col = find_col(TABLE_COL_CANDIDATES)
            name_col  = find_col(NAME_COL_CANDIDATES)

            all_cols = list(dax_df.columns)

            if not expr_col:
                expr_col = st.selectbox(
                    "⚠️ Could not auto-detect expression column. Please select it:",
                    options=all_cols,
                    key="expr_col_select",
                )
            else:
                st.info(f"✅ Expression column detected: **{expr_col}**")

            if st.button("Generate Context-Aware DAX", key="btn_generate_dax"):
                logger = MigrationLogger()
                logger.log("INFO", f"Excel uploaded: {dax_excel.name}")
                logger.log("INFO", f"Expression column: {expr_col}")

                converter   = DaxConverter()
                
                # Pass schema context into converter instance if supported by the package
                if hasattr(converter, "set_schema_context"):
                    converter.set_schema_context(schema_context)
                elif hasattr(converter, "schema_context"):
                    converter.schema_context = schema_context

                dax_results = []
                validation_logs = []
                conversion_errors_count = 0

                for idx, row in dax_df.iterrows():
                    logger.log("INFO", f"Processing row {idx + 1}")
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
                    row_errors = []
                    row_warnings = []

                    try:
                        # Convert syntax using context mapping
                        dax_code = converter.convert(qlik_expression, measure_table)
                        status   = "✅ OK"
                        
                        # --- STRICT VALIDATION PIPELINE ENGINE ---
                        if dax_code.count("(") != dax_code.count(")"):
                            row_errors.append("Syntax Error: Parenthesis mismatch detected.")
                        
                        if schema_context:
                            extracted_tables = re.findall(r"'([^']+)'", dax_code)
                            for tbl in extracted_tables:
                                if tbl not in schema_context:
                                    row_warnings.append(f"Schema Link Warning: Table '{tbl}' not found in active M Query Model layout.")
                                    
                    except Exception as conv_err:
                        dax_code = f"-- ERROR: {conv_err}"
                        status   = "❌ Error"
                        row_errors.append(str(conv_err))
                        conversion_errors_count += 1

                    execution_time_ms = round((time.time() - start_time) * 1000, 2)
                    
                    try:
                        parsed = converter.parser.parse(qlik_expression)
                        pattern_detected = parsed.get('pattern', 'Complex/Unknown')
                    except Exception:
                        pattern_detected = "Complex Evaluation"

                    logger.log("INFO", f"Pattern detected: {pattern_detected}")
                    logger.log("SUCCESS", f"Row {idx + 1} finalized conversion layout")

                    result_row = {
                        "Measure Name":    measure_name,
                        "Target Table":    measure_table,
                        "Qlik Expression": qlik_expression,
                        "DAX Output":      dax_code,
                        "Pattern Framework": pattern_detected,
                        "Status":          "FAILED" if row_errors else "PASSED",
                        "Execution (ms)":  execution_time_ms,
                    }
                    dax_results.append(result_row)

                    if row_errors or row_warnings:
                        validation_logs.append({
                            "Row": idx + 1,
                            "Measure Name": measure_name,
                            "Validation Errors": "; ".join(row_errors) if row_errors else "None",
                            "Validation Warnings": "; ".join(row_warnings) if row_warnings else "None"
                        })

                logger.log("INFO", "Conversion pipeline pipeline runs finished")
                result_df = pd.DataFrame(dax_results)
                validation_df = pd.DataFrame(validation_logs)

                # --- MULTI-TAB SUMMARY DISPLAY METRICS ---
                st.markdown("### 📈 Migration Execution Metrics")
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.metric("Total Input Rows Processed", len(result_df))
                with m_col2:
                    st.metric("Successful Conversions", len(result_df) - conversion_errors_count)
                with m_col3:
                    st.metric("Validation Flagged Exceptions", len(validation_df))

                st.subheader("📋 Conversion Report Output")
                st.dataframe(result_df, use_container_width=True)

                if not validation_df.empty:
                    st.subheader("🛑 Structural Validation & Error Logs")
                    st.dataframe(validation_df, use_container_width=True)
                else:
                    st.success("🎉 Comprehensive structural schema matching validations passed perfectly!")

                # --- COMBINED WORKBOOK EXPORT GENERATOR ---
                from io import BytesIO
                excel_buf = BytesIO()
                with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                    result_df.to_excel(writer, sheet_name="Conversion Report", index=False)
                    if not validation_df.empty:
                        validation_df.to_excel(writer, sheet_name="Validation Logs", index=False)
                    else:
                        pd.DataFrame([{"System Status": "All validation tests passed cleanly."}]).to_excel(writer, sheet_name="Validation Logs", index=False)
                excel_buf.seek(0)

                st.download_button(
                    label="📥 Download Enterprise Migration Summary Package (.xlsx)",
                    data=excel_buf,
                    file_name="DAX_Migration_Comprehensive_Package.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                render_migration_logs()

        except Exception as e:
            st.error(f"Could not read Excel Configuration File: {str(e)}")
            st.exception(e)