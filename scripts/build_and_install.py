#!/usr/bin/env python3
"""
Build and install script for TopSoft project.

This script builds the executable and installer without bumping the version.

Usage:
    python scripts/build_and_install.py

This will:
1. Build the executable using PyInstaller
2. Build the installer using Inno Setup
"""

import os
import subprocess
import sys
from pathlib import Path


def get_current_version():
    """Get current version from pyproject.toml"""
    try:
        import sync_version

        return sync_version.get_version_from_pyproject()
    except:
        # Fallback to poetry command
        try:
            result = subprocess.run(
                ["poetry", "version"], capture_output=True, text=True, check=True
            )
            return result.stdout.split()[1]
        except:
            return "unknown"


def build_exe():
    """Build executable using PyInstaller"""
    print("🔨 Building executable with PyInstaller...")

    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Use the existing topsoft.spec file
    spec_file = project_root / "topsoft.spec"

    if spec_file.exists():
        print(f"📄 Using spec file: {spec_file}")
        result = subprocess.run(
            ["pyinstaller", str(spec_file)],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    else:
        print("📄 No spec file found, using direct PyInstaller command...")
        result = subprocess.run(
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
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        print("❌ Error building executable:")
        print(result.stderr)
        return False
    else:
        print("✅ Executable built successfully!")
        print(f"📦 Output: {project_root / 'dist' / 'topsoft.exe'}")
        return True


def build_installer():
    """Build installer using Inno Setup"""
    print("\n🔨 Building installer with Inno Setup...")

    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Check for Inno Setup
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        "iscc.exe",  # If in PATH
    ]

    iscc_path = None
    for path in iscc_paths:
        if Path(path).exists() or path == "iscc.exe":
            iscc_path = path
            break

    if not iscc_path:
        print("❌ Inno Setup not found!")
        print("Please install Inno Setup or add it to your PATH")
        print("Download from: https://jrsoftware.org/isinfo.php")
        return False

    # Check if installer.iss exists
    iss_file = project_root / "installer.iss"
    if not iss_file.exists():
        print(f"❌ installer.iss not found at {iss_file}")
        return False

    print(f"📄 Using installer script: {iss_file}")
    print(f"🛠️  Using ISCC: {iscc_path}")

    result = subprocess.run(
        [iscc_path, str(iss_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("❌ Error building installer:")
        print(result.stderr)
        return False
    else:
        print("✅ Installer built successfully!")

        # Try to find the output installer file
        version = get_current_version()
        installer_name = f"topsoft_v{version}_win64.exe"
        installer_path = project_root / installer_name

        if installer_path.exists():
            print(f"📦 Output: {installer_path}")
        else:
            print(f"📦 Installer should be in: {project_root}")

        return True


def check_prerequisites():
    """Check if required tools are available"""
    print("🔍 Checking prerequisites...")

    # Check if we're in a poetry environment
    try:
        subprocess.run(["poetry", "--version"], capture_output=True, check=True)
        print("✅ Poetry found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Poetry not found - make sure you're in the right environment")

    # Check for PyInstaller
    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
        print("✅ PyInstaller found")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller not found")
        print("Install with: pip install pyinstaller")
        return False

    # Check for main.py
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    main_file = project_root / "main.py"

    if main_file.exists():
        print("✅ main.py found")
    else:
        print(f"❌ main.py not found at {main_file}")
        return False

    return True


def main():
    """Main function"""
    print("🚀 TopSoft Build and Install Script")
    print("=" * 40)

    current_version = get_current_version()
    print(f"📋 Current version: {current_version}")
    print()

    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed!")
        sys.exit(1)

    print("\n" + "=" * 40)

    # Build executable
    if not build_exe():
        print("\n❌ Build failed at executable stage!")
        sys.exit(1)

    # Build installer
    if not build_installer():
        print("\n❌ Build failed at installer stage!")
        sys.exit(1)

    print("\n" + "=" * 40)
    print("🎉 Build completed successfully!")
    print("\n📋 Summary:")
    print(f"   Version: {current_version}")
    print(f"   Executable: dist/topsoft.exe")
    print(f"   Installer: topsoft_v{current_version}_win64.exe")
    print("\n💡 Next steps:")
    print("   - Test the executable: dist/topsoft.exe")
    print("   - Test the installer")
    print("   - Distribute the installer file")


if __name__ == "__main__":
    main()
