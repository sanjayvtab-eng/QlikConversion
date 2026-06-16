from datetime import datetime
import os


class MigrationLogger:

    def __init__(self):

        os.makedirs(
            "logs",
            exist_ok=True
        )

        self.log_file = os.path.join(
            "logs",
            f"migration_{datetime.now().strftime('%Y%m%d')}.log"
        )

    def log(
        self,
        level,
        message
    ):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log_line = (
            f"{timestamp} "
            f"[{level}] "
            f"{message}"
        )

        with open(
            self.log_file,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                log_line + "\n"
            )