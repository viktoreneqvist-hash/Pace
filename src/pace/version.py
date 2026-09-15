"""Installed Pace package version."""

from importlib.metadata import PackageNotFoundError, version


try:
    __version__ = version("pace")
except PackageNotFoundError:  # pragma: no cover - only for an unpackaged source tree
    __version__ = "0+unknown"
