try:
    from educelab.hercdb import config
    from educelab.hercdb.db import (
        connect,
        GraphDBConnection,
        DatasetType,
        FlatbedScanType,
        PGSRawType,
        SpectralRawType,
    )

    __all__ = [
        "config",
        "connect",
        "GraphDBConnection",
        "DatasetType",
        "FlatbedScanType",
        "PGSRawType",
        "SpectralRawType",
    ]
except ImportError:
    pass
