try:
    from educelab.hercdb import config
    from educelab.hercdb.db import (
        connect,
        GraphDBConnection,
        DatasetType,
    )

    __all__ = [
        "config",
        "connect",
        "GraphDBConnection",
        "DatasetType",
    ]
except ImportError:
    pass
