"""Country registry. A new country = a `VisaSite` subclass registered here."""

from __future__ import annotations

from ..core.site import VisaSite
from .tanzania import TanzaniaSite

SITES: dict[str, type[VisaSite]] = {
    TanzaniaSite.key: TanzaniaSite,
}


def get_site(key: str, **kwargs) -> VisaSite:
    try:
        return SITES[key.lower()](**kwargs)
    except KeyError:
        raise KeyError(f"unknown country {key!r}; available: {', '.join(sorted(SITES))}") from None
