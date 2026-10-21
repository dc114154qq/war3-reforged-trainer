"""Application/view boundary. This module has no Tk or game dependencies."""
from typing import Any, Protocol


class ViewPort(Protocol):
    def value(self, name: str) -> Any:
        """Resolve a declared input, output, scheduler or dialog port."""
        ...


class ViewControl(Protocol):
    def state(self, states): ...
