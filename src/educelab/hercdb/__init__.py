from importlib.metadata import PackageNotFoundError, version as _package_version

try:
    __version__ = _package_version("educelab-hercdb")
except PackageNotFoundError:
    # Running from a source tree with no install; nothing to read metadata from.
    __version__ = "0.0.0+unknown"

try:
    from educelab.hercdb import config
    from educelab.hercdb.db import (
        connect,
        GraphDBConnection,
        DatasetType,
    )

    __all__ = [
        "__version__",
        "config",
        "connect",
        "GraphDBConnection",
        "DatasetType",
    ]
except ImportError:
    pass
