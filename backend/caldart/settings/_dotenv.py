"""Load the repository's ``.env`` into the process environment.

Importing this module reads ``.env`` from the repository root, so a bare
checkout runs with no exported variables at all.  Real environment variables
win over the file.

Only ``dev.py`` and ``test.py`` import it, and they do so before ``base``.
Production configuration comes from the environment alone: a server that is
missing a variable must fail at start-up rather than quietly take a
developer's value from a file that happens to sit beside the code.
"""

from pathlib import Path

import environ

# backend/caldart/settings/_dotenv.py -> repo root
DOTENV_PATH = Path(__file__).resolve().parents[3] / ".env"

environ.Env.read_env(DOTENV_PATH)
