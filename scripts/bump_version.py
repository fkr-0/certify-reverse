#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
PACKAGE_INIT = Path("src/certify_reverse/__init__.py")
PROJECT_PATTERN = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"$', re.M)
INIT_PATTERN = re.compile(r'^__version__ = "\d+\.\d+\.\d+"$', re.M)


def bump_version(
    part: str,
    pyproject_path: Path = PYPROJECT,
    package_init_path: Path = PACKAGE_INIT,
) -> str:
    """Bump and synchronize the project and importable package versions."""
    text = pyproject_path.read_text(encoding="utf-8")
    m = PROJECT_PATTERN.search(text)
    if not m:
        raise ValueError(f"Could not find semantic version in {pyproject_path}")

    major, minor, patch = map(int, m.groups())
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"Unsupported semantic-version part: {part}")

    new_version = f"{major}.{minor}.{patch}"
    updated = PROJECT_PATTERN.sub(f'version = "{new_version}"', text, count=1)
    pyproject_path.write_text(updated, encoding="utf-8")

    init_text = package_init_path.read_text(encoding="utf-8")
    if not INIT_PATTERN.search(init_text):
        raise ValueError(f"Could not find __version__ in {package_init_path}")
    init_updated = INIT_PATTERN.sub(f'__version__ = "{new_version}"', init_text, count=1)
    package_init_path.write_text(init_updated, encoding="utf-8")
    return new_version


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump synchronized semantic versions")
    parser.add_argument("part", choices=["patch", "minor", "major"])
    args = parser.parse_args()

    try:
        new_version = bump_version(args.part)
    except (OSError, ValueError) as e:
        raise SystemExit(str(e)) from e
    print(new_version)


if __name__ == "__main__":
    main()
