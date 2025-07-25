#!/usr/bin/env python3
"""
Complete build script for TopSoft project.

This script does everything in one go:
1. Bump version using poetry
2. Sync version across all files
3. Build executable with PyInstaller
4. Build installer with Inno Setup

Usage:
    python scripts/build_all.py patch
    python scripts/build_all.py minor
    python scripts/build_all.py major
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run command and return success status"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def bump_and_sync_version(bump_type):
    """Bump version with poetry and sync all files"""
    print(f"🚀 Bumping version: {bump_type}")

    # Run poetry version
    success, output = run_command(["poetry", "version", bump_type])
    if not success:
        print(f"❌ Failed to bump version: {output}")
        return False, None

    print(f"✅ Poetry version updated: {output}")

    # Get new version
    success, output = run_command(["poetry", "version"])
    if not success:
        print(f"❌ Failed to get version: {output}")
        return False, None

    new_version = output.strip().split()[1]

    # Sync version across files
    print("🔄 Syncing versions across project files...")
    import sync_version

    try:
        sync_version.main()
        print(f"✅ All files synced to version {new_version}")
        return True, new_version
    except Exception as e:
        print(f"❌ Failed to sync versions: {e}")
        return False, None


def build_executable():
    """Build executable using PyInstaller"""
    print("\n🔨 Building executable with PyInstaller...")

    project_root = Path(__file__).parent.parent
    spec_file = project_root / "topsoft.spec"

    if spec_file.exists():
        print(f"📄 Using spec file: {spec_file}")
        success, output = run_command(["pyinstaller", str(spec_file)], cwd=project_root)
    else:
        print("📄 Using direct PyInstaller command...")
        success, output = run_command(
            [
                "pyinstaller",
                "--onefile",
                "--noconsole",
                "--name",
                "topsoft",
                "--icon",
                str(project_root / "topsoft.ico"),
                "--add-data",
                f"{project_root / 'topsoft.ico'};.",
                str(project_root / "main.py"),
            ],
            cwd=project_root,
        )

    if not success:
        print(f"❌ Failed to build executable: {output}")
        return False

    print("✅ Executable built successfully!")
    return True


def build_installer():
    """Build installer using Inno Setup"""
    print("\n🔨 Building installer with Inno Setup...")

    project_root = Path(__file__).parent.parent

    # Find Inno Setup
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]

    iscc_path = None
    for path in iscc_paths:
        if Path(path).exists():
            iscc_path = path
            break

    if not iscc_path:
        print("❌ Inno Setup not found!")
        return False

    # Build installer
    iss_file = project_root / "installer.iss"
    if not iss_file.exists():
        print(f"❌ installer.iss not found!")
        return False

    success, output = run_command([iscc_path, str(iss_file)], cwd=project_root)

    if not success:
        print(f"❌ Failed to build installer: {output}")
        return False

    print("✅ Installer built successfully!")
    return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Complete build script: bump + build + install"
    )
    parser.add_argument(
        "bump_type", choices=["patch", "minor", "major"], help="Type of version bump"
    )
    args = parser.parse_args()

    print("🚀 TopSoft Complete Build Script")
    print("=" * 40)

    # Step 1: Bump and sync version
    success, version = bump_and_sync_version(args.bump_type)
    if not success:
        sys.exit(1)

    # Step 2: Build executable
    if not build_executable():
        sys.exit(1)

    # Step 3: Build installer
    if not build_installer():
        sys.exit(1)

    # Success
    print("\n" + "=" * 40)
    print("🎉 Build completed successfully!")
    print(f"📋 Version: {version}")
    print("📦 Files created:")
    print(f"   - dist/topsoft.exe")
    print(f"   - topsoft_v{version}_win64.exe")


if __name__ == "__main__":
    main()
