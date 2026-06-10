import sys
import os
import importlib

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    importlib.import_module("QlikToPowerBIConverter")
    for mod in ["parser", "agents", "generators"]:
        try:
            sys.modules[mod] = importlib.import_module(f"QlikToPowerBIConverter.{mod}")
        except Exception:
            pass
except Exception:
    pass

import json
import base64
import streamlit as st
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
os.makedirs(os.path.join(base_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(base_dir, "QlikToPowerBIConverter", "uploads"), exist_ok=True)

st.set_page_config(page_title="QlikToPowerBIConverter", page_icon="🔁", layout="wide")
st.title("QlikToPowerBIConverter")
st.caption("Upload a Qlik script (.qvs) to analyze ETL logic and generate Power Query M code.")

if not _imports_ok:
    st.error(f"Import error: {_import_err_msg}")
    st.stop()

uploaded_file = st.file_uploader(
    "Upload Qlik script",
    type=["qvs", "txt"],
    accept_multiple_files=False
)

if uploaded_file is not None:
    # Read bytes immediately from in-memory buffer before any PUT occurs
    try:
        file_bytes = uploaded_file.getvalue()
        raw_text = file_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    st.success(f"✅ Uploaded: {uploaded_file.name} ({len(file_bytes)/1024:.1f} KB)")
    st.subheader("Uploaded script")
    st.code(raw_text, language="text")

    try:
        for path in [
            os.path.join(base_dir, "uploads", uploaded_file.name),
            os.path.join(base_dir, "QlikToPowerBIConverter", "uploads", uploaded_file.name),
        ]:
            with open(path, "wb") as f:
                f.write(file_bytes)
    except Exception as ex:
        print(f"[UPLOAD] Error saving: {ex}")

    if st.button("Generate Power Query M"):
        try:
            agent = MigrationAgent(base_dir=".")
            generator = MGenerator()
            analysis = agent.analyze(raw_text)
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
            warnings = analysis.get("warnings", [])
            if warnings:
                for w in warnings:
                    st.warning(w)
            else:
                st.success("No unsupported features were flagged by the current rule set.")
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.exception(e)
else:
    st.info("Choose a .qvs or .txt file to begin.")
