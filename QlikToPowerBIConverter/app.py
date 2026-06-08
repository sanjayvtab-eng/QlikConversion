import json

import streamlit as st

from agents.migration_agent import MigrationAgent
from generators.m_generator import MGenerator


st.set_page_config(page_title="QlikToPowerBIConverter", page_icon="🔁", layout="wide")

st.title("QlikToPowerBIConverter")
st.caption("Upload a Qlik script (.qvs) to analyze ETL logic and generate Power Query M code.")

uploaded_file = st.file_uploader("Upload Qlik script", type=["qvs", "txt"], accept_multiple_files=False)

if uploaded_file is not None:
    raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    st.success(f"Uploaded: {uploaded_file.name}")

    st.subheader("Uploaded script")
    st.code(raw_text, language="text")

    if st.button("Generate Power Query M"):
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
else:
    st.info("Choose a .qvs or .txt file to begin.")
