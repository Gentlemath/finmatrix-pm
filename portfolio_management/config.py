"""Load configuration from a local ``.env`` file, if present.

The data loaders read credentials (API keys, tokens, WRDS username) from
environment variables. Calling :func:`load_env` on package import lets those
variables live in a project ``.env`` file instead of being exported by hand.

Real environment variables always take precedence over ``.env`` values (i.e.
an already-set variable is not overwritten unless ``override=True``).
"""

from typing import Optional


def load_env(override: bool = False) -> Optional[str]:
    """Load variables from the nearest ``.env`` file (searching up from cwd).

    Args:
        override: If True, ``.env`` values overwrite existing environment
            variables. Defaults to False so the real environment wins.

    Returns:
        The path of the ``.env`` file that was loaded, or ``None`` if
        python-dotenv is not installed or no ``.env`` file was found.
    """
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return None

    path = find_dotenv(usecwd=True)
    if not path:
        return None
    load_dotenv(path, override=override)
    return path
