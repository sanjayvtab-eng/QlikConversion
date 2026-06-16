import os

import streamlit.components.v1 as components


_COMPONENT_PATH = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "browser_uploader_component"
)
_browser_file_uploader = components.declare_component(
    "browser_file_uploader", path=_COMPONENT_PATH
)


def browser_file_uploader(label: str, *, key: str) -> dict | None:
    return _browser_file_uploader(label=label, default=None, key=key)


def uploaded_payload_to_bytes(payload: dict) -> tuple[str, bytes, str]:
    file_name = str(payload.get("name") or "uploaded.qvs")
    raw_text = str(payload.get("content") or "")
    return file_name, raw_text.encode("utf-8"), raw_text
