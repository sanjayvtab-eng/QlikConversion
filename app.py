import sys
import os
import importlib

# Ensure repository root is on sys.path (some platforms change working dir)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Try to import the package and create top-level module aliases so
# imports like `from parser.qlik_parser import ...` still work if present
try:
    pkg = importlib.import_module("QlikToPowerBIConverter")
    try:
        sys.modules["parser"] = importlib.import_module("QlikToPowerBIConverter.parser")
    except Exception:
        pass
    try:
        sys.modules["agents"] = importlib.import_module("QlikToPowerBIConverter.agents")
    except Exception:
        pass
    try:
        sys.modules["generators"] = importlib.import_module("QlikToPowerBIConverter.generators")
    except Exception:
        pass
except Exception:
    pass

# Execute the Streamlit UI from the package
import json
import streamlit as st

from QlikToPowerBIConverter.agents.migration_agent import MigrationAgent
from QlikToPowerBIConverter.generators.m_generator import MGenerator

# Ensure uploads directories exist (repo root and package) so deployed
# instances (Render) have the folders available for saving files.
base_dir = os.path.abspath(os.path.dirname(__file__))
os.makedirs(os.path.join(base_dir, "uploads"), exist_ok=True)
os.makedirs(os.path.join(base_dir, "QlikToPowerBIConverter", "uploads"), exist_ok=True)


st.set_page_config(page_title="QlikToPowerBIConverter", page_icon="🔁", layout="wide")

st.title("QlikToPowerBIConverter")
st.caption("Upload a Qlik script (.qvs) to analyze ETL logic and generate Power Query M code.")

uploaded_file = st.file_uploader("Upload Qlik script", type=["qvs", "txt"], accept_multiple_files=False)

if uploaded_file is not None:
    raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    st.success(f"Uploaded: {uploaded_file.name}")

    st.subheader("Uploaded script")
    st.code(raw_text, language="text")
    # Save uploaded file to uploads folder and log for debugging on Render
    try:
        upload_path = os.path.join(base_dir, "uploads", uploaded_file.name)
        with open(upload_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        # Also save inside package uploads
        pkg_upload_path = os.path.join(base_dir, "QlikToPowerBIConverter", "uploads", uploaded_file.name)
        with open(pkg_upload_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        print(f"[UPLOAD] Saved file to: {upload_path} ({os.path.getsize(upload_path)} bytes)")
    except Exception as ex:
        print(f"[UPLOAD] Error saving uploaded file: {ex}")

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
