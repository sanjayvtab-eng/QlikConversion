"""Allow Streamlit's upload endpoint to receive POST requests."""


def allow_upload_post() -> None:
    """Patch Streamlit 1.46.x's upload handler to accept POST as PUT."""
    try:
        from streamlit.web.server.upload_file_request_handler import (
            UploadFileRequestHandler,
        )

        UploadFileRequestHandler.post = UploadFileRequestHandler.put

        if getattr(UploadFileRequestHandler, "_qlik_post_headers_patch", False):
            return

        set_default_headers = UploadFileRequestHandler.set_default_headers

        def set_upload_headers(self):
            set_default_headers(self)
            self.set_header(
                "Access-Control-Allow-Methods", "POST, PUT, OPTIONS, DELETE"
            )

        UploadFileRequestHandler.set_default_headers = set_upload_headers
        UploadFileRequestHandler._qlik_post_headers_patch = True
    except Exception:
        pass
