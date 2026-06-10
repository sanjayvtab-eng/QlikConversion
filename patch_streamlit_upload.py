"""Patch Streamlit's frontend uploader to use POST instead of PUT on Render."""

from pathlib import Path

import streamlit


OLD = 'method:"PUT",data:we,responseType:"text"'
NEW = 'method:"POST",data:we,responseType:"text"'


def main() -> None:
    static_dir = Path(streamlit.__file__).parent / "static" / "static" / "js"
    patched_files = []

    for js_file in static_dir.glob("*.js"):
        text = js_file.read_text(encoding="utf-8")
        if "/_stcore/upload_file" not in text:
            continue
        if NEW in text:
            patched_files.append(js_file)
            continue
        if OLD not in text:
            raise RuntimeError(
                f"Found Streamlit upload endpoint in {js_file}, "
                "but the expected PUT upload call was not present."
            )
        js_file.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
        patched_files.append(js_file)

    if not patched_files:
        raise RuntimeError(
            f"No Streamlit frontend bundle with {OLD!r} was found under {static_dir}."
        )

    for js_file in patched_files:
        print(f"Patched Streamlit uploader method in {js_file}")


if __name__ == "__main__":
    main()
