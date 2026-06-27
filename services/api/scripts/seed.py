"""CLI: python scripts/seed.py  (idempotent — see app/seed.py)."""
import logging
import pathlib
import sys

# make the services/api dir importable regardless of where this is run from
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.seed import seed  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = seed()
    print("\nSeed summary:")
    for k, v in result.items():
        print(f"  {k:16} {v}")
