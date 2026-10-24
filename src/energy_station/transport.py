"""A future serial transport must implement this bounded exchange interface."""
from typing import Protocol


class Transport(Protocol):
    def exchange(self, request: bytes, timeout_s: float) -> bytes:
        """Return one complete response or raise TimeoutError before the deadline."""


class SimulatorTransport:
    def __init__(self, controller):
        self.controller = controller

    def exchange(self, request: bytes, timeout_s: float) -> bytes:
        if timeout_s <= 0:
            raise TimeoutError("Deadline expired")
        return self.controller.handle(request)
