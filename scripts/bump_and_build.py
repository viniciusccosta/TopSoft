import argparse
import os
import subprocess

# Import our version management utilities
import sync_version


def bump_poetry_version(bump_type):
    """Bump version using poetry and sync all files"""
    subprocess.run(["poetry", "version", bump_type], check=True)

    # Sync versions across all files
    print("🔄 Syncing versions across project files...")
    sync_version.main()


def get_poetry_version():
    """Get current version from pyproject.toml"""
    version = sync_version.get_version_from_pyproject()
    if not version:
        # Fallback to poetry command
        result = subprocess.run(["poetry", "version"], capture_output=True, text=True)
        version = result.stdout.split()[1]
    return version


def build_exe():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    result = subprocess.run(
        [
            "pyinstaller",
            "--onefile",
            "--noconsole",
            "--name",
            "topsoft",
            "--icon",
            os.path.join(script_dir, "../topsoft.ico"),
            "--add-data",
            f"{os.path.join(script_dir, '../topsoft.ico')};.",
            os.path.join(script_dir, "../main.py"),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Error building executable:", result.stderr)
    else:
        print("Executable built successfully.")


def build_installer():
    script_dir = os.path.dirname(os.path.abspath(__file__))

    result = subprocess.run(
        [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            os.path.join(script_dir, "../installer.iss"),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Error building installer:", result.stderr)
    else:
        print("Installer built successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bump version and build application.")
    parser.add_argument(
        "bump_type",
        choices=["patch", "minor", "major"],
        help="Type of version bump",
    )
    args = parser.parse_args()

    bump_poetry_version(args.bump_type)
    current_version = get_poetry_version()
    print(f"✅ Version bumped to {current_version} and all files updated.")

    build_exe()
    build_installer()
