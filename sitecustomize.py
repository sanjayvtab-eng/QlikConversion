"""Patch Streamlit upload XSRF check before Streamlit starts its server."""

try:
    from streamlit.web.server import server_util
    from streamlit.web.server.starlette import starlette_routes

    server_util.is_xsrf_enabled = lambda: False
    starlette_routes.is_xsrf_enabled = lambda: False
except Exception:
    pass