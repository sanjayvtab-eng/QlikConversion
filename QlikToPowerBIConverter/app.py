import json
import os
import re

import streamlit as st
from browser_file_uploader import browser_file_uploader, uploaded_payload_to_bytes
from streamlit_upload_post_patch import allow_upload_post

from agents.migration_agent import MigrationAgent
from generators.m_generator import MGenerator

allow_upload_post()

def disable_streamlit_upload_xsrf_check() -> None:
    """Avoid Render-hosted upload 403s from Streamlit's internal upload route."""
    try:
        from streamlit.web.server import server_util
        from streamlit.web.server.starlette import starlette_routes

        server_util.is_xsrf_enabled = lambda: False
        starlette_routes.is_xsrf_enabled = lambda: False
    except Exception:
        pass


disable_streamlit_upload_xsrf_check()

st.set_page_config(page_title="QlikToPowerBIConverter", page_icon="🔁", layout="wide")

st.title("QlikToPowerBIConverter")
st.caption("Upload a Qlik script (.qvs) to analyze ETL logic and generate Power Query M code.")

uploaded_file = browser_file_uploader("Upload Qlik script", key="qlik_script")

if uploaded_file is not None:
    uploaded_name, file_bytes, raw_text = uploaded_payload_to_bytes(uploaded_file)
    st.success(f"Uploaded: {uploaded_name}")

    st.subheader("Uploaded script")
    st.code(raw_text, language="text")
    # Save uploaded file to uploads folder and log for debugging on Render
    try:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        upload_path = os.path.join(base_dir, "uploads", uploaded_name)
        with open(upload_path, "wb") as f:
            f.write(file_bytes)
        print(f"[UPLOAD] Saved file to: {upload_path} ({os.path.getsize(upload_path)} bytes)")
    except Exception as ex:
        print(f"[UPLOAD] Error saving uploaded file: {ex}")

    st.subheader("Source File Mapping")
    detected_sources = []

    patterns = [
        r'FROM\s+\[?([^\]\n;]+)',
        r'LOAD\s+.*?FROM\s+\[?([^\]\n;]+)'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, raw_text, flags=re.IGNORECASE | re.DOTALL)
        detected_sources.extend(matches)

    detected_sources = list(dict.fromkeys([x.strip().strip("'\"[]") for x in detected_sources if x.strip()]))
    file_mappings = {}

    if detected_sources:
        st.info(f"Detected {len(detected_sources)} source file(s)")
        for idx, source in enumerate(detected_sources, start=1):
            powerbi_path = st.text_input(
                f"Power BI Path for {source}",
                placeholder=r"C:\\Data\\YourFile.xlsx",
                key=f"path_{idx}_{source}"
            )
            if powerbi_path:
                file_mappings[source] = powerbi_path
    else:
        st.warning("No source files detected automatically.")
        manual_count = st.number_input(
            "Number of source files",
            min_value=1,
            value=1
        )
        for i in range(manual_count):
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

    if st.button("Generate Power Query M"):
        try:
            agent = MigrationAgent(base_dir=".")
            generator = MGenerator()

            analysis = agent.analyze(raw_text)
            analysis["file_paths"] = file_mappings
            metadata = analysis.get("metadata", {})
            generated_m = generator.generate(analysis)

            st.subheader("1. Detected Tables")
            tables = metadata.get("tables", [])
            st.write(tables if tables else "No table declarations were found.")

            st.subheader("2. Detected ETL Operations")
            st.write("\n".join(f"- {item}" for item in analysis.get("operations", [])))

            st.subheader("3. Parsed Metadata (JSON)")
            st.json(metadata)

            st.subheader("4. Generated Power Query M Code")
            st.code(generated_m, language="m")

            st.subheader("5. Warnings and Unsupported Features")
            if analysis.get("warnings", []):
                for warning in analysis.get("warnings", []):
                    st.warning(warning)
            else:
                st.success("No unsupported features were flagged by the current rule set.")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.exception(e)
else:
    st.info("Choose a .qvs or .txt file to begin.")
