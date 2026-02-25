#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

PYPROJECT = Path('pyproject.toml')
PATTERN = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"$', re.M)


def main():
    parser = argparse.ArgumentParser(description='Bump semantic version in pyproject.toml')
    parser.add_argument('part', choices=['patch', 'minor', 'major'])
    args = parser.parse_args()

    text = PYPROJECT.read_text(encoding='utf-8')
    m = PATTERN.search(text)
    if not m:
        raise SystemExit('Could not find semantic version in pyproject.toml')

    major, minor, patch = map(int, m.groups())
    if args.part == 'patch':
        patch += 1
    elif args.part == 'minor':
        minor += 1
        patch = 0
    else:
        major += 1
        minor = 0
        patch = 0

    new_version = f'{major}.{minor}.{patch}'
    updated = PATTERN.sub(f'version = "{new_version}"', text)
    PYPROJECT.write_text(updated, encoding='utf-8')
    print(new_version)


if __name__ == '__main__':
    main()
