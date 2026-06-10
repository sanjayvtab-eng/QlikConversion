from setuptools import find_packages, setup


setup(
    name="qlikconversion",
    version="0.0.0",
    packages=find_packages(),
    py_modules=[
        "app",
        "patch_streamlit_upload",
        "sitecustomize",
        "streamlit_upload_post_patch",
    ],
)
