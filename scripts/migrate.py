"""Run database migrations via Alembic."""
import os
import subprocess
import sys


def main():
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "backend"))
    cmd = ["alembic", "upgrade", "head"]
    if len(sys.argv) > 1:
        cmd = ["alembic"] + sys.argv[1:]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
