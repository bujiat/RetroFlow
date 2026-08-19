"""Apply Alembic migrations using the installed library.

`python /app/run_migrations.py` puts `/app` first on sys.path. This project
also has `/app/alembic/` (migration scripts), so `import alembic` would load
that folder and fail with `No module named 'alembic.config'`. Import the
installed package first, then put `/app` back so `env.py` can import `app`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _is_app_root(entry: str) -> bool:
    if entry in ("", "."):
        return True
    try:
        return Path(entry).resolve() == ROOT
    except OSError:
        return False


def main() -> None:
    # 1. Hide ./alembic/ so the next import is site-packages Alembic.
    sys.path = [p for p in sys.path if not _is_app_root(p)]
    from alembic import command
    from alembic.config import Config

    # 2. env.py needs `from app.core.config import settings`.
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    try:
        from app.core.config import settings
    except Exception as exc:
        print(f"Failed to load Settings: {exc}", file=sys.stderr)
        print(
            "Check Railway Variables: DATABASE_URL, APP_ENV, JWT_SECRET, CORS_ORIGINS.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    driver = settings.database_url.split("://", 1)[0]
    if driver != "postgresql+psycopg":
        print(
            f"DATABASE_URL driver is {driver!r}; need postgresql+psycopg://",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Alembic is already in sys.modules, so env.py's `from alembic import context`
    # will not pick up the local migrations folder.
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


if __name__ == "__main__":
    main()
