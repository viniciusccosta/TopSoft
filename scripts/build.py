#!/usr/bin/env python3
"""
Unified build script for TopSoft project.

This script consolidates all build operations:
1. Optional version bumping (patch/minor/major)
2. Version synchronization across files
3. Executable building with PyInstaller
4. Installer creation with Inno Setup
5. Git operations (commit and tag)

Usage:
    python scripts/build.py                    # Build only (no version bump)
    python scripts/build.py patch              # Bump patch + build + git operations
    python scripts/build.py minor              # Bump minor + build + git operations
    python scripts/build.py major              # Bump major + build + git operations
    python scripts/build.py --no-git patch     # Bump patch + build (skip git)
    python scripts/build.py --build-only       # Alias for no arguments (build only)
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


class TopSoftBuilder:
    """Unified builder for TopSoft project"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.scripts_dir = self.project_root / "scripts"

    def run_command(self, cmd: list, cwd: Optional[Path] = None) -> Tuple[bool, str]:
        """Run command and return success status and output"""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()

    def get_version_from_pyproject(self) -> Optional[str]:
        """Extract version from pyproject.toml"""
        pyproject_path = self.project_root / "pyproject.toml"
        if not pyproject_path.exists():
            print("❌ pyproject.toml not found!")
            return None

        content = pyproject_path.read_text(encoding="utf-8")
        version_match = re.search(
            r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE
        )
        if version_match:
            return version_match.group(1)

        print("❌ Could not find version in pyproject.toml")
        return None

    def get_current_version(self) -> str:
        """Get current version, fallback to poetry command if needed"""
        version = self.get_version_from_pyproject()
        if version:
            return version

        # Fallback to poetry command
        try:
            success, output = self.run_command(["poetry", "version"])
            if success:
                return output.split()[1]
        except:
            pass

        return "unknown"

    def bump_version(self, bump_type: str) -> Tuple[bool, str]:
        """Bump version using poetry"""
        print(f"📈 Bumping version: {bump_type}")

        success, output = self.run_command(["poetry", "version", bump_type])
        if not success:
            print(f"❌ Failed to bump version: {output}")
            return False, ""

        print(f"✅ Poetry version updated")

        # Get new version
        new_version = self.get_current_version()
        if new_version == "unknown":
            print("❌ Failed to get new version")
            return False, ""

        print(f"📦 New version: {new_version}")
        return True, new_version

    def sync_versions(self, version: str) -> bool:
        """Synchronize version across project files"""
        print("🔄 Syncing versions across project files...")

        success = True
        success &= self._update_installer_iss(version)
        success &= self._update_spec_file(version)

        if success:
            print(f"✅ All files synchronized to version {version}")
        else:
            print("❌ Some files failed to update")

        return success

    def _update_installer_iss(self, version: str) -> bool:
        """Update version in installer.iss file"""
        iss_path = self.project_root / "installer.iss"
        if not iss_path.exists():
            print("⚠️  installer.iss not found, skipping...")
            return True

        content = iss_path.read_text(encoding="utf-8")

        # Update version definition
        content = re.sub(
            r'#define MyAppVersion "[^"]*"',
            f'#define MyAppVersion "{version}"',
            content,
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

    def _update_spec_file(self, version: str) -> bool:
        """Update version in topsoft.spec file"""
        spec_path = self.project_root / "topsoft.spec"
        if not spec_path.exists():
            print("⚠️  topsoft.spec not found, skipping...")
            return True

        content = spec_path.read_text(encoding="utf-8")

        if "# Version:" not in content:
            # Add version comment at the top
            lines = content.split("\n")
            lines.insert(0, f"# Version: {version}")
            content = "\n".join(lines)
        else:
            # Update existing version comment
            content = re.sub(r"# Version: [^\n]*", f"# Version: {version}", content)

        spec_path.write_text(content, encoding="utf-8")
        print(f"✅ Updated topsoft.spec version comment: {version}")
        return True

    def check_prerequisites(self) -> bool:
        """Check if required tools are available"""
        print("🔍 Checking prerequisites...")

        # Check poetry
        success, _ = self.run_command(["poetry", "--version"])
        if success:
            print("✅ Poetry found")
        else:
            print("⚠️  Poetry not found - make sure you're in the right environment")

        # Check PyInstaller
        success, _ = self.run_command(["pyinstaller", "--version"])
        if success:
            print("✅ PyInstaller found")
        else:
            print("❌ PyInstaller not found")
            print("Install with: pip install pyinstaller")
            return False

        # Check main.py
        main_file = self.project_root / "main.py"
        if main_file.exists():
            print("✅ main.py found")
        else:
            print(f"❌ main.py not found at {main_file}")
            return False

        return True

    def build_executable(self) -> bool:
        """Build executable using PyInstaller"""
        print("\n🔨 Building executable with PyInstaller...")

        spec_file = self.project_root / "topsoft.spec"

        if spec_file.exists():
            print(f"📄 Using spec file: {spec_file}")
            success, output = self.run_command(["pyinstaller", str(spec_file)])
        else:
            print("📄 Using direct PyInstaller command...")
            success, output = self.run_command(
                [
                    "pyinstaller",
                    "--onefile",
                    "--noconsole",
                    "--name",
                    "topsoft",
                    "--icon",
                    str(self.project_root / "topsoft.ico"),
                    "--add-data",
                    f"{self.project_root / 'topsoft.ico'};.",
                    str(self.project_root / "main.py"),
                ]
            )

        if not success:
            print(f"❌ Failed to build executable: {output}")
            return False

        print("✅ Executable built successfully!")
        print(f"📦 Output: {self.project_root / 'dist' / 'topsoft.exe'}")
        return True

    def build_installer(self) -> bool:
        """Build installer using Inno Setup"""
        print("\n🔨 Building installer with Inno Setup...")

        # Find Inno Setup
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

        # Check installer script
        iss_file = self.project_root / "installer.iss"
        if not iss_file.exists():
            print(f"❌ installer.iss not found at {iss_file}")
            return False

        print(f"📄 Using installer script: {iss_file}")
        print(f"🛠️  Using ISCC: {iscc_path}")

        success, output = self.run_command([iscc_path, str(iss_file)])

        if not success:
            print(f"❌ Failed to build installer: {output}")
            return False

        print("✅ Installer built successfully!")

        # Show output location
        version = self.get_current_version()
        installer_name = f"topsoft_v{version}_win64.exe"
        installer_path = self.project_root / installer_name

        if installer_path.exists():
            print(f"📦 Output: {installer_path}")
        else:
            print(f"📦 Installer should be in: {self.project_root}")

        return True

    def git_commit_and_tag(self, version: str) -> bool:
        """Commit changes and create git tag"""
        print(f"\n📝 Committing changes and creating tag v{version}...")

        # Check if git is available
        success, _ = self.run_command(["git", "--version"])
        if not success:
            print("⚠️  Git not found, skipping git operations")
            return True

        # Check if we're in a git repository
        success, _ = self.run_command(["git", "status"])
        if not success:
            print("⚠️  Not in a git repository, skipping git operations")
            return True

        # Add all changes
        success, output = self.run_command(["git", "add", "."])
        if not success:
            print(f"❌ Failed to add files: {output}")
            return False

        # Check if there are changes to commit
        success, output = self.run_command(["git", "status", "--porcelain"])
        if success and not output.strip():
            print("ℹ️  No changes to commit")
        else:
            # Commit changes
            commit_message = f"chore: bump version to {version}"
            success, output = self.run_command(["git", "commit", "-m", commit_message])
            if not success:
                print(f"❌ Failed to commit: {output}")
                return False
            print(f"✅ Committed: {commit_message}")

        # Create tag
        tag_name = f"v{version}"
        success, output = self.run_command(["git", "tag", tag_name])
        if not success:
            if "already exists" in output:
                print(f"⚠️  Tag {tag_name} already exists")
            else:
                print(f"❌ Failed to create tag: {output}")
                return False
        else:
            print(f"✅ Created tag: {tag_name}")

        return True

    def build_project(
        self, bump_type: Optional[str] = None, enable_git: bool = True
    ) -> bool:
        """Main build process"""
        print("🚀 TopSoft Unified Build Script")
        print("=" * 50)

        # Get initial version
        current_version = self.get_current_version()
        print(f"📋 Current version: {current_version}")

        # Version bumping phase
        if bump_type:
            success, new_version = self.bump_version(bump_type)
            if not success:
                return False

            # Sync versions across files
            if not self.sync_versions(new_version):
                return False

            current_version = new_version
        else:
            print("ℹ️  Skipping version bump (build-only mode)")

        print("\n" + "=" * 50)

        # Prerequisites check
        if not self.check_prerequisites():
            print("\n❌ Prerequisites check failed!")
            return False

        print("\n" + "=" * 50)

        # Build executable
        if not self.build_executable():
            print("\n❌ Build failed at executable stage!")
            return False

        # Build installer
        if not self.build_installer():
            print("\n❌ Build failed at installer stage!")
            return False

        # Git operations (only if version was bumped)
        if bump_type and enable_git:
            if not self.git_commit_and_tag(current_version):
                print("\n⚠️  Git operations failed, but build succeeded")

        # Success summary
        print("\n" + "=" * 50)
        print("🎉 Build completed successfully!")
        print(f"\n📋 Summary:")
        print(f"   Version: {current_version}")
        print(f"   Executable: dist/topsoft.exe")
        print(f"   Installer: topsoft_v{current_version}_win64.exe")

        if bump_type:
            print(f"   Git tag: v{current_version}")

        print(f"\n💡 Next steps:")
        print(f"   - Test the executable: dist/topsoft.exe")
        print(f"   - Test the installer")
        print(f"   - Distribute the installer file")

        if bump_type and enable_git:
            print(f"   - Push changes: git push && git push --tags")

        return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Unified TopSoft build script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build.py                    # Build only (no version bump)
  python scripts/build.py patch              # Bump patch + full build
  python scripts/build.py minor              # Bump minor + full build
  python scripts/build.py major              # Bump major + full build
  python scripts/build.py --no-git patch     # Bump patch + build (skip git)
  python scripts/build.py --build-only       # Alias for build-only mode
        """,
    )

    parser.add_argument(
        "bump_type",
        nargs="?",
        choices=["patch", "minor", "major"],
        help="Type of version bump (optional)",
    )

    parser.add_argument(
        "--no-git", action="store_true", help="Skip git operations (commit and tag)"
    )

    parser.add_argument(
        "--build-only",
        action="store_true",
        help="Build only, don't bump version (same as no arguments)",
    )

    args = parser.parse_args()

    # Handle --build-only flag
    if args.build_only and args.bump_type:
        print("❌ Cannot use --build-only with version bump type")
        sys.exit(1)

    # Create builder and run
    builder = TopSoftBuilder()

    bump_type = None if args.build_only else args.bump_type
    enable_git = not args.no_git

    success = builder.build_project(bump_type=bump_type, enable_git=enable_git)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
