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

try:
    from QlikToPowerBIConverter.agents.migration_agent import MigrationAgent
    from QlikToPowerBIConverter.generators.m_generator import MGenerator

    _imports_ok = True

except Exception as _import_err:
    _imports_ok = False
    _import_err_msg = str(_import_err)

base_dir = os.path.abspath(os.path.dirname(__file__))

os.makedirs(
    os.path.join(base_dir, "uploads"),
    exist_ok=True
)

os.makedirs(
    os.path.join(
        base_dir,
        "QlikToPowerBIConverter",
        "uploads"
    ),
    exist_ok=True
)

st.set_page_config(
    page_title="QlikToPowerBIConverter",
    page_icon="🔁",
    layout="wide"
)

# --------------------------------------------------
# Helper: render migration logs from the logs/ dir
# --------------------------------------------------
def render_migration_logs():
    st.subheader("📋 Migration Logs")
    log_dir = os.path.join(base_dir, "logs")
    if os.path.isdir(log_dir):
        log_files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
    else:
        log_files = []

    if log_files:
        latest_file = sorted(log_files)[-1]
        with open(
            os.path.join(log_dir, latest_file),
            "r",
            encoding="utf-8"
        ) as f:
            st.code(f.read(), language="text")
    else:
        st.info("No migration logs found.")


# --------------------------------------------------
# Header
# --------------------------------------------------
current_hour = datetime.now().hour

if current_hour < 12:
    greeting = "🌅 Good Morning"
elif current_hour < 17:
    greeting = "☀️ Good Afternoon"
elif current_hour < 21:
    greeting = "🌆 Good Evening"
else:
    greeting = "🌙 Good Night"

today_date = datetime.now().strftime("%d-%b-%Y")

logo_path = os.path.join(base_dir, "assets", "logo.jpeg")

col1, col2, col3 = st.columns([1, 4, 1])

with col1:
    st.image(logo_path, width=100)

with col2:
    st.markdown(
        f"""
        <h1 style='color:#1565C0;margin-bottom:0;'>
        Qlik To Power BI Converter
        </h1>
        <h4 style='color:#555555;'>
        {greeting}
        </h4>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div style='text-align:right;padding-top:20px;'>
        <h4>📅 {today_date}</h4>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("---")
st.markdown(
    """
    <div style="
        background:#1565C0;
        color:white;
        padding:15px;
        border-radius:10px;
        text-align:center;
        font-size:20px;
        font-weight:bold;">
        AI Powered Qlik To Power BI Migration Platform
    </div>
    """,
    unsafe_allow_html=True
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
        ["Convert Script",
         "DAX Generator"
        ],
        label_visibility="collapsed"
    )

if not _imports_ok:
    st.error(f"Import error: {_import_err_msg}")
    st.stop()

# --------------------------------------------------
# Main Tabs
# --------------------------------------------------
tab_m, tab_dax = st.tabs([
    "⚙️ Power Query M Generator",
    "📊 DAX Generator"
])

# ==================================================
# TAB 1 — Power Query M Generator
# ==================================================
with tab_m:

    st.markdown("### 📂 Source Script")

    uploaded_file = browser_file_uploader(
        "Upload Qlik Script (.qvs or .txt) — Limit 20 MB",
        key="qlik_script"
    )

    # Hint shown inside the tab, right below the uploader
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

        st.success(
            f"Uploaded: {uploaded_name} ({len(file_bytes)/1024:.1f} KB)"
        )
        st.subheader("Qlik Source")
        st.code(raw_text, language="text")

        # ----------------------------------------------
        # Save Uploaded File
        # ----------------------------------------------
        try:
            for path in [
                os.path.join(base_dir, "uploads", uploaded_name),
                os.path.join(
                    base_dir,
                    "QlikToPowerBIConverter",
                    "uploads",
                    uploaded_name
                ),
            ]:
                with open(path, "wb") as f:
                    f.write(file_bytes)
        except Exception as ex:
            print(f"[UPLOAD ERROR] {ex}")

        # ----------------------------------------------
        # Detect Source Files
        # ----------------------------------------------
        st.subheader("Source File Mapping")

        detected_sources = []
        patterns = [
            r'FROM\s+\[?([^\]\n;]+)',
            r'LOAD\s+.*?FROM\s+\[?([^\]\n;]+)'
        ]

        for pattern in patterns:
            matches = re.findall(
                pattern,
                raw_text,
                flags=re.IGNORECASE | re.DOTALL
            )
            detected_sources.extend(matches)

        detected_sources = list(
            dict.fromkeys([x.strip() for x in detected_sources])
        )

        file_mappings = {}

        if detected_sources:
            st.info(f"Detected {len(detected_sources)} source file(s)")

            for source in detected_sources:
                powerbi_path = st.text_input(
                    f"Power BI Path for {source}",
                    placeholder=r"C:\Data\YourFile.xlsx",
                    key=f"path_{source}"
                )
                if powerbi_path:
                    file_mappings[source] = powerbi_path

        else:
            st.warning("No source files detected automatically.")

            manual_count = st.number_input(
                "Number of source files",
                min_value=1,
                value=1,
                key="m_manual_count"
            )

            for i in range(int(manual_count)):
                source_name = st.text_input(
                    f"Source File {i+1}",
                    key=f"src_{i}"
                )
                source_path = st.text_input(
                    f"Power BI Path {i+1}",
                    key=f"dst_{i}"
                )
                if source_name and source_path:
                    file_mappings[source_name] = source_path

        # ----------------------------------------------
        # Generate Power Query M
        # ----------------------------------------------
        if st.button("Generate Power Query M", key="btn_generate_m"):

            logger = MigrationLogger()
            logger.log("INFO", f"Qlik script uploaded: {uploaded_name}")
            logger.log("INFO", "Power Query M generation started")

            try:
                agent = MigrationAgent(base_dir=".")
                generator = MGenerator()

                analysis = agent.analyze(raw_text)

                logger.log("INFO", "Script analysis completed")
                logger.log(
                    "INFO",
                    f"Detected {len(analysis.get('operations', []))} operations"
                )
                logger.log(
                    "INFO",
                    f"Detected {len(analysis.get('metadata', {}).get('tables', []))} tables"
                )

                analysis["file_paths"] = file_mappings
                metadata = analysis.get("metadata", {})

                logger.log("INFO", "Power Query M conversion completed")

                generated_m = generator.generate(analysis)

                logger.log("SUCCESS", "Power Query M generated successfully")

                st.subheader("1. Detected Tables")
                tables = metadata.get("tables", [])
                if tables:
                    st.write(tables)
                else:
                    st.write("No table declarations were found.")

                st.subheader("2. Detected ETL Operations")
                operations = analysis.get("operations", [])
                if operations:
                    st.write("\n".join(f"- {op}" for op in operations))
                else:
                    st.write("No operations detected.")

                st.subheader("3. Source File Mapping")
                st.json(file_mappings)

                st.subheader("4. Parsed Metadata")
                st.json(metadata)

                st.subheader("5. Generated Power Query M Code")

                if isinstance(generated_m, dict):
                    table_queries = generated_m.get("table_queries", {}) or {}
                    final_query = generated_m.get("final_query") or ""

                    for name, text in table_queries.items():
                        st.markdown(f"📁 **{name} M Query**")
                        st.code(text, language="m")
                        st.download_button(
                            label=f"Download {name}.m",
                            data=text,
                            file_name=f"{name}.m",
                            mime="text/plain",
                            key=f"download_{name}"
                        )

                    st.markdown("📁 **Final Combined M Query**")
                    st.code(final_query, language="m")
                    st.download_button(
                        label="Download FinalCombined.m",
                        data=final_query,
                        file_name="FinalCombined.m",
                        mime="text/plain",
                        key="download_final"
                    )
                else:
                    st.code(generated_m, language="m")
                    st.download_button(
                        label="Download M Code",
                        data=generated_m,
                        file_name="GeneratedPowerQuery.m",
                        mime="text/plain"
                    )

                st.subheader("6. Warnings and Unsupported Features")
                warnings = analysis.get("warnings", [])
                if warnings:
                    for warning in warnings:
                        st.warning(warning)
                else:
                    st.success("No unsupported features were flagged.")

                # Migration logs for Power Query M
                render_migration_logs()

            except Exception as e:
                st.error(f"❌ Error processing file: {str(e)}")
                st.exception(e)


# ==================================================
# TAB 2 — DAX Generator
# ==================================================
with tab_dax:

    st.markdown("### 📊 Set Analysis Excel")

    dax_excel = st.file_uploader(
        "Upload Set Analysis Excel",
        type=["xlsx"],
        key="dax_excel"
    )

    if dax_excel is None:
        st.info("👆 Upload a Set Analysis Excel file (.xlsx) to begin.")

    if dax_excel is not None:

        st.success(f"Excel Uploaded: {dax_excel.name}")

        try:
            dax_df = pd.read_excel(dax_excel)

            st.subheader("Set Analysis Preview")
            st.dataframe(dax_df, use_container_width=True)

            st.markdown("---")

            if st.button("Generate DAX", key="btn_generate_dax"):
                logger = MigrationLogger()
                logger.log("INFO", f"Excel uploaded: {dax_excel.name}")

                converter = DaxConverter()
                dax_results = []

                for idx, row in dax_df.iterrows():
                    logger.log("INFO", f"Processing row {idx + 1}")

                    qlik_expression = str(row["SetAnalysis"])
                    start_time = time.time()
                    measure_table = str(
                        row.get("MeasureTable", "FactSales")
                    )

                    dax_code = converter.convert(
                        qlik_expression,
                        measure_table
                    )

                    execution_time_ms = round(
                        (time.time() - start_time) * 1000,
                        2
                    )

                    parsed = converter.parser.parse(qlik_expression)

                    logger.log(
                        "INFO",
                        f"Pattern detected: {parsed.get('pattern')}"
                    )
                    logger.log("SUCCESS", "DAX generated successfully")

                    dax_results.append(
                        {
                            "Qlik Expression": qlik_expression,
                            "DAX Output": dax_code,
                            "Execution Time (ms)": execution_time_ms
                        }
                    )

                logger.log("INFO", "Conversion completed")

                result_df = pd.DataFrame(dax_results)

                st.subheader("Generated DAX")
                st.dataframe(result_df, use_container_width=True)

                csv = result_df.to_csv(index=False)
                st.download_button(
                    label="Download DAX Output",
                    data=csv,
                    file_name="DAX_Output.csv",
                    mime="text/csv"
                )

                # Migration logs for DAX Generator
                render_migration_logs()

        except Exception as e:
            st.error(f"Could not read Excel: {str(e)}")