#!/usr/bin/env python3
"""
Poetry wrapper that automatically syncs versions after poetry version commands.

Usage (replace 'poetry version' with this):
    python scripts/poetry_wrapper.py version patch
    python scripts/poetry_wrapper.py version minor
    python scripts/poetry_wrapper.py version major
    python scripts/poetry_wrapper.py install  # normal poetry commands pass through
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Main wrapper function"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/poetry_wrapper.py <poetry_command> [args...]")
        sys.exit(1)

    # Get the poetry command and arguments
    poetry_args = sys.argv[1:]

    # Run the poetry command
    print(f"🚀 Running: poetry {' '.join(poetry_args)}")
    result = subprocess.run(["poetry"] + poetry_args)

    # If this was a version command and it succeeded, sync versions
    if (
        len(poetry_args) >= 2
        and poetry_args[0] == "version"
        and result.returncode == 0
        and poetry_args[1] in ["patch", "minor", "major"]
        or poetry_args[1].replace(".", "").replace("-", "").isalnum()
    ):

        print("\n🔄 Auto-syncing versions across project files...")
        try:
            # Import and run sync
            import sync_version

            sync_version.main()
            print("✅ Version sync complete!")
        except Exception as e:
            print(f"⚠️  Version sync failed: {e}")

    # Exit with the same code as poetry
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
