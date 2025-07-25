#!/usr/bin/env python3
"""
Version synchronization script for TopSoft project.

This script reads the version from pyproject.toml and updates:
- installer.iss file
- topsoft.spec file (if it contains version info)

Usage:
    python scripts/sync_version.py
"""

import re
import sys
from pathlib import Path
from typing import Optional


def get_version_from_pyproject() -> Optional[str]:
    """Extract version from pyproject.toml"""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ pyproject.toml not found!")
        return None

    content = pyproject_path.read_text(encoding="utf-8")

    # Look for version = "x.y.z" pattern
    version_match = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE
    )
    if version_match:
        return version_match.group(1)

    print("❌ Could not find version in pyproject.toml")
    return None


def update_installer_iss(version: str) -> bool:
    """Update version in installer.iss file"""
    iss_path = Path("installer.iss")
    if not iss_path.exists():
        print("⚠️  installer.iss not found, skipping...")
        return True

    content = iss_path.read_text(encoding="utf-8")

    # Update version definition
    content = re.sub(
        r'#define MyAppVersion "[^"]*"', f'#define MyAppVersion "{version}"', content
    )

    # Update output filename
    content = re.sub(
        r'#define MyOutputBaseFilename "topsoft_v[^"]*"',
        f'#define MyOutputBaseFilename "topsoft_v{version}_win64"',
        content,
    )

    iss_path.write_text(content, encoding="utf-8")
    print(f"✅ Updated installer.iss to version {version}")
    return True


def update_spec_file(version: str) -> bool:
    """Update version in topsoft.spec file if it contains version info"""
    spec_path = Path("topsoft.spec")
    if not spec_path.exists():
        print("⚠️  topsoft.spec not found, skipping...")
        return True

    content = spec_path.read_text(encoding="utf-8")

    # Check if spec file has version info and update it
    # This is for future use if we add version info to the spec file
    # For now, we'll just add a comment with the version

    if "# Version:" not in content:
        # Add version comment at the top
        lines = content.split("\n")
        lines.insert(0, f"# Version: {version}")
        content = "\n".join(lines)

        spec_path.write_text(content, encoding="utf-8")
        print(f"✅ Added version comment to topsoft.spec: {version}")
    else:
        # Update existing version comment
        content = re.sub(r"# Version: [^\n]*", f"# Version: {version}", content)
        spec_path.write_text(content, encoding="utf-8")
        print(f"✅ Updated version comment in topsoft.spec: {version}")

    return True


def main():
    """Main function to sync versions across all files"""
    print("🔄 Syncing versions across project files...")

    # Get version from pyproject.toml
    version = get_version_from_pyproject()
    if not version:
        sys.exit(1)

    print(f"📦 Current version: {version}")

    # Update all files
    success = True
    success &= update_installer_iss(version)
    success &= update_spec_file(version)

    if success:
        print(f"✅ All files synchronized to version {version}")
    else:
        print("❌ Some files failed to update")
        sys.exit(1)


if __name__ == "__main__":
    main()
