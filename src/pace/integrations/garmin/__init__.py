"""Garmin Connect integration boundary for Pace."""

from pace.integrations.garmin.client import (
    GarminAuthenticationRequiredError,
    GarminConnectClient,
    GarminIntegrationError,
    GarminRateLimitError,
)

__all__ = [
    "GarminAuthenticationRequiredError",
    "GarminConnectClient",
    "GarminIntegrationError",
    "GarminRateLimitError",
]
