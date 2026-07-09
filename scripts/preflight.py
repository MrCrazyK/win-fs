import argparse
import codecs
import subprocess
import sys
from pathlib import Path


CHECK_EXTENSIONS = {'.py', '.md', '.yaml', '.yml'}
SKIP_DIRS = {'.git', '.idea', '.vscode', 'tmp', '__pycache__'}


def iter_checked_files(root):
    for path in root.rglob('*'):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix.lower() in CHECK_EXTENSIONS:
            yield path


def check_no_bom(root):
    offenders = []
    for path in iter_checked_files(root):
        if path.read_bytes().startswith(codecs.BOM_UTF8):
            offenders.append(path)
    return offenders


def main():
    parser = argparse.ArgumentParser(description='win-fs preflight checks')
    parser.add_argument('--skip-tests', action='store_true')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    offenders = check_no_bom(root)
    if offenders:
        print('[ERROR] UTF-8 BOM found:', file=sys.stderr)
        for path in offenders:
            print(path, file=sys.stderr)
        return 1
    print('BOM check passed')

    if not args.skip_tests:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'], cwd=root)
        if result.returncode != 0:
            return result.returncode
        print('Test check passed')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
