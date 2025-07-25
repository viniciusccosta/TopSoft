#!/usr/bin/env python3
"""
Version bump utility for TopSoft project.

This script provides a wrapper around poetry version commands and automatically
syncs the version across all project files.

Usage:
    python scripts/bump_version.py patch
    python scripts/bump_version.py minor
    python scripts/bump_version.py major
    python scripts/bump_version.py 1.2.3

This will:
1. Run poetry version <level>
2. Update installer.iss
3. Update topsoft.spec
4. Optionally commit changes to git
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Import our version sync script
import sync_version


def run_command(cmd: List[str], cwd: Optional[Path] = None) -> tuple[bool, str]:
    """Run a command and return success status and output"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return True, result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return False, e.stderr.strip()


def bump_version(level: str) -> bool:
    """Bump version using poetry and sync all files"""
    print(f"🚀 Bumping version: {level}")

    # Run poetry version command
    success, output = run_command(["poetry", "version", level])
    if not success:
        print(f"❌ Failed to bump version with poetry: {output}")
        return False

    print(f"✅ Poetry version updated: {output}")

    # Sync versions across all files
    print("\n🔄 Syncing versions across project files...")
    try:
        sync_version.main()
        return True
    except SystemExit:
        return False


def commit_version_bump(version: str) -> bool:
    """Optionally commit version bump to git"""
    print(f"\n📝 Would you like to commit the version bump to git? (y/n): ", end="")
    response = input().strip().lower()

    if response not in ["y", "yes"]:
        print("Skipping git commit.")
        return True

    # Add all version-related files
    files_to_add = ["pyproject.toml", "installer.iss", "topsoft.spec"]

    existing_files = [f for f in files_to_add if Path(f).exists()]

    # Add files to git
    success, output = run_command(["git", "add"] + existing_files)
    if not success:
        print(f"⚠️  Failed to add files to git: {output}")
        return False

    # Commit changes
    commit_msg = f"chore: bump version to {version}"
    success, output = run_command(["git", "commit", "-m", commit_msg])
    if not success:
        print(f"⚠️  Failed to commit: {output}")
        return False

    print(f"✅ Committed version bump: {commit_msg}")

    # Ask about tagging
    print(f"📝 Would you like to create a git tag v{version}? (y/n): ", end="")
    response = input().strip().lower()

    if response in ["y", "yes"]:
        success, output = run_command(["git", "tag", f"v{version}"])
        if success:
            print(f"✅ Created git tag: v{version}")
        else:
            print(f"⚠️  Failed to create tag: {output}")

    return True


def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py <patch|minor|major|version>")
        print("Examples:")
        print("  python scripts/bump_version.py patch")
        print("  python scripts/bump_version.py minor")
        print("  python scripts/bump_version.py major")
        print("  python scripts/bump_version.py 1.2.3")
        sys.exit(1)

    level = sys.argv[1]

    # Validate version level
    valid_levels = ["patch", "minor", "major"]
    if (
        level not in valid_levels
        and not level.replace(".", "").replace("-", "").replace("+", "").isalnum()
    ):
        print(f"❌ Invalid version level: {level}")
        print(
            f"Valid levels: {', '.join(valid_levels)} or a specific version like 1.2.3"
        )
        sys.exit(1)

    # Bump version and sync files
    if not bump_version(level):
        sys.exit(1)

    # Get the current version for git operations
    current_version = sync_version.get_version_from_pyproject()
    if not current_version:
        print("⚠️  Could not get current version, skipping git operations")
        return

    # Optionally commit changes
    commit_version_bump(current_version)

    print(f"\n🎉 Version bump complete! New version: {current_version}")
    print("💡 Next steps:")
    print("   - Run tests to ensure everything works")
    print("   - Build the application: poetry run pyinstaller topsoft.spec")
    print("   - Create installer: Run Inno Setup with installer.iss")
    print("   - Push to git: git push && git push --tags")


if __name__ == "__main__":
    main()
