"""Patch Streamlit upload XSRF check before Streamlit starts its server."""

# For Streamlit 1.46.x (Tornado-based server):
# xsrf_cookies=is_xsrf_enabled() is evaluated when the Tornado Application
# is created. Patching is_xsrf_enabled here (at Python startup, before any
# Streamlit code runs) ensures it returns False when the server is built.
try:
    from streamlit.web.server import server_util
    server_util.is_xsrf_enabled = lambda: False
except Exception:
    pass

# Render's edge can reject Streamlit's default PUT upload request before it
# reaches the app. Accept POST too; patch_streamlit_upload.py rewrites only
# the frontend upload request.
try:
    from streamlit_upload_post_patch import allow_upload_post

    allow_upload_post()
except Exception:
    pass

# Also set via config as a belt-and-suspenders approach
try:
    from streamlit import config as _st_config
    _st_config.set_option("server.enableXsrfProtection", False)
    _st_config.set_option("server.enableCORS", False)
except Exception:
    pass
