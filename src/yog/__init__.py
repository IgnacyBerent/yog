from __future__ import annotations

__version__ = "0.1.0"


def main() -> None:
    from yog.cli import app

    app()


def __getattr__(name: str):
    if name == "Client":
        from yog.client import Client

        return Client
    raise AttributeError(name)


__all__ = ["Client", "__version__", "main"]
