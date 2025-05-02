import argparse
import os
import re
import subprocess


def bump_poetry_version(bump_type):
    subprocess.run(["poetry", "version", bump_type], check=True)


def get_poetry_version():
    result = subprocess.run(["poetry", "version"], capture_output=True, text=True)
    version = result.stdout.split()[1]
    return version


def update_iss_file(version):
    iss_file_path = "installer.iss"
    with open(iss_file_path, "r") as file:
        content = file.read()

    # Update MyAppVersion
    content = re.sub(
        r'#define MyAppVersion ".*"',
        f'#define MyAppVersion "{version}"',
        content,
    )

    # Update OutputBaseFilename
    content = re.sub(
        r'#define MyOutputBaseFilename "topsoft_v.*_win64"',
        f'#define MyOutputBaseFilename "topsoft_v{version}_win64"',
        content,
    )

    with open(iss_file_path, "w") as file:
        file.write(content)


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
    parser = argparse.ArgumentParser(description="Bump version and update .iss file.")
    parser.add_argument(
        "bump_type",
        choices=["patch", "minor", "major"],
        help="Type of version bump",
    )
    args = parser.parse_args()

    bump_poetry_version(args.bump_type)
    current_version = get_poetry_version()
    update_iss_file(current_version)
    print(f"Version bumped to {current_version} and .iss file updated.")

    build_exe()
    build_installer()
