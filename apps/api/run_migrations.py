"""Apply Alembic migrations using the installed library.

Do not use `python -m alembic`: apps/api/alembic/ is the migrations folder,
so Python would load that directory instead of the Alembic package.
"""

from alembic.config import main

if __name__ == "__main__":
    main(["upgrade", "head"])
