"""Entry point for `python -m cortex`."""

import uvicorn

from cortex.entrypoints.app import create_app
from cortex.settings import Settings


def main() -> None:
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
