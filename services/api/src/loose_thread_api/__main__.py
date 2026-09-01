import uvicorn

from loose_thread_api.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "loose_thread_api.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
