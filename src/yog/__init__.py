from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yog.client import Client

__version__ = "0.2.0"


def main() -> None:
    from yog.cli import app

    app()


def __getattr__(name: str) -> object:
    if name == "Client":
        from yog.client import Client

        return Client
    raise AttributeError(name)


__all__ = ["Client", "__version__", "main"]
