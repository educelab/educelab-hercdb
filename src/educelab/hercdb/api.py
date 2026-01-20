"""Backward compatibility shim - use educelab.hercdb.db instead."""

# Re-export everything from db module for backward compatibility
from educelab.hercdb.db import (
    GraphDBConnection,
    connect,
    DatasetType,
    FlatbedScanType,
    PGSRawType,
    SpectralRawType,
)

__all__ = [
    "GraphDBConnection",
    "connect",
    "DatasetType",
    "FlatbedScanType",
    "PGSRawType",
    "SpectralRawType",
]
