import logging
import os
import sys
from functools import lru_cache
from getpass import getpass, GetPassWarning
from pathlib import Path

from prompt_toolkit import prompt


logger = logging.getLogger('educelab.hercdb')

# ~/.educedb holds the Neo4j settings in its first section, whatever it is
# called ([database] in the docs, [hercdb] on some machines) or, in a TOML file
# without sections, as top-level keys. The release settings have their own
# section (#81). Any other section is reported, not read.
RELEASE_SECTION = 'release'


def _read_toml(path: Path) -> dict:
    """``{section: {key: value}}`` from a TOML file; top-level keys under ''."""
    import tomllib
    with path.open('rb') as f:
        data = tomllib.load(f)
    top = {k: v for k, v in data.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in data.items() if isinstance(v, dict)}
    return ({'': top} if top else {}) | tables


def _read_ini(path: Path) -> dict:
    """``{section: {key: value}}`` with configparser (Python 3.10, which has no
    tomllib). Every value is a string, quotes and brackets included."""
    import configparser
    cfg = configparser.ConfigParser()
    with path.open('r') as f:
        cfg.read_file(f)
    return {s: dict(cfg.items(s)) for s in cfg.sections()}


def _database_section(sections: dict) -> str | None:
    """The name of the section holding the Neo4j settings, or None."""
    return next((name for name in sections if name != RELEASE_SECTION), None)


def _where(section: str) -> str:
    return f"[{section}]" if section else "the top level"


def _warn_unread(path: Path, sections: dict) -> None:
    """Log the sections of ~/.educedb that nothing reads, so they aren't
    ignored silently."""
    database = _database_section(sections)
    for name in sections:
        if name not in (database, RELEASE_SECTION):
            logger.warning(
                f"{path}: section [{name}] is not read. The Neo4j settings come from "
                f"{_where(database)} and the release settings from [{RELEASE_SECTION}].")


@lru_cache(maxsize=2)
def _load_sections() -> dict | None:
    """Every section of ~/.educedb, as ``{name: {key: value}}``, or None if
    there is no file. Read once per process, so a change needs a restart."""
    cfg_path = Path.home() / '.educedb'
    if not cfg_path.exists():
        return None
    if sys.version_info < (3, 11):
        logger.debug('config backend: configparser')
        sections = _read_ini(cfg_path)
    else:
        logger.debug('config backend: tomllib')
        sections = _read_toml(cfg_path)
    _warn_unread(cfg_path, sections)
    return sections


def _load_config():
    """The Neo4j settings from ~/.educedb (see ``_database_section``), ``{}``
    if it holds none, or None if there is no file."""
    sections = _load_sections()
    if sections is None:
        return None
    database = _database_section(sections)
    return dict(sections[database]) if database is not None else {}


def _get_cfg_val(env_key, config_key):
    """Return a Neo4j setting from the environment or config file."""
    # Prefer env val
    val = os.getenv(env_key, None)
    if val is not None:
        return val

    # Load config
    cfg = _load_config()
    if cfg is None:
        # Look again next time, in case the file has been created since.
        _load_sections.cache_clear()
        return None

    return cfg.get(config_key, None)


def _get_release_val(env_key, key):
    """Return a release setting from the environment or ~/.educedb's
    [release] section."""
    val = os.getenv(env_key, None)
    if val is not None:
        return val
    sections = _load_sections()
    if sections is None:
        _load_sections.cache_clear()
        return None
    return sections.get(RELEASE_SECTION, {}).get(key)


def __getattr__(name):
    """Stub to avoid attribute errors on this module"""
    pass


# Default properties #
uri = _get_cfg_val('EDUCEDB_URI', 'uri')
username = _get_cfg_val('EDUCEDB_USER', 'username')
password = _get_cfg_val('EDUCEDB_PASSWORD', 'password')


def request_required():
    """Prompt the user to provide required configuration information."""
    global uri, username, password
    if uri is None:
        uri = prompt('Enter URI: ')

    if username is None:
        username = prompt('Enter username: ')

    if password is None:
        try:
            password = getpass('Enter password: ')
        except GetPassWarning:
            pass


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _names(value) -> set[str]:
    """Names from a TOML list, or from a string: "a, b" (the environment
    variable) or '["a", "b"]' (a list as configparser reads it)."""
    if isinstance(value, list):
        names = value
    else:
        names = str(value).strip().removeprefix('[').removesuffix(']').split(',')
    return {n for n in (str(n).strip().strip('"\'').strip() for n in names) if n}


def release_default() -> bool:
    """Whether a newly created dataset starts out released (published).

    ``HERCDB_RELEASE_DEFAULT``, or ``default`` under [release] in ~/.educedb;
    true when unset, for the first pass over the data. Set it false to make
    every new dataset wait for review.
    """
    value = _get_release_val('HERCDB_RELEASE_DEFAULT', 'default')
    return True if value is None else _as_bool(value)


def release_writers() -> set[str]:
    """Token users (from ~/.tokens) allowed to change a dataset's release flag.

    ``HERCDB_RELEASE_WRITERS`` (comma-separated), or ``writers`` (a list) under
    [release] in ~/.educedb. Empty when unset, so nobody can until it is
    configured.
    """
    value = _get_release_val('HERCDB_RELEASE_WRITERS', 'writers')
    return set() if value is None else _names(value)
