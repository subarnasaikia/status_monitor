from __future__ import annotations

from providers.base import StatusProvider


class ProviderRegistry:
    """Central registry of status-page provider adapters.

    Adding a new provider requires only instantiating it and calling
    ``register()`` -- no changes to the scheduler or core logic.
    """

    def __init__(self) -> None:
        self._providers: list[StatusProvider] = []

    def register(self, provider: StatusProvider) -> None:
        self._providers.append(provider)

    @property
    def providers(self) -> list[StatusProvider]:
        return list(self._providers)
