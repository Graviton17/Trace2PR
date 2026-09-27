"""Trace2PR backend entrypoint."""
import uvicorn

from trace2pr.config.settings import settings


def main():
    uvicorn.run(
        "trace2pr.app:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
    )


if __name__ == "__main__":
    main()
