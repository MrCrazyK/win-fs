import sys, os, shutil, re, json, codecs, argparse
from pathlib import Path

def _has_bom(data):
    if data.startswith(codecs.BOM_UTF8): return 'utf-8-sig'
    if data.startswith(codecs.BOM_UTF16_LE): return 'utf-16-le'
    if data.startswith(codecs.BOM_UTF16_BE): return 'utf-16-be'
    return None

def _try_decode(data, encodings):
    for enc in encodings:
        try: return data.decode(enc), enc
        except (UnicodeDecodeError, LookupError): continue
    return None

def detect_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read(100000)
    bom = _has_bom(raw)
    if bom: return bom
    result = _try_decode(raw, ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1'])
    return result[1] if result else 'utf-8'

def read_file(filepath, encoding=None, max_lines=None):
    enc = encoding or detect_encoding(filepath)
    with open(filepath, 'r', encoding=enc, errors='replace') as f:
        if max_lines is not None:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines: break
                lines.append(line)
            return ''.join(lines)
        return f.read()

def write_file(filepath, content, append=False, encoding='utf-8'):
    mode = 'a' if append else 'w'
    d = os.path.dirname(os.path.abspath(filepath))
    if d: os.makedirs(d, exist_ok=True)
    with open(filepath, mode, encoding=encoding, newline='') as f:
        f.write(content)

def file_info(filepath):
    p = Path(filepath)
    if not p.exists():
        return {'exists': False, 'path': str(p.absolute())}
    stat = p.stat()
    info = {
        'exists': True, 'path': str(p.absolute()),
        'size': stat.st_size, 'is_file': p.is_file(), 'is_dir': p.is_dir()
    }
    if p.is_file():
        try: info['encoding'] = detect_encoding(str(p))
        except Exception: info['encoding'] = 'unknown'
        try:
            with open(p, 'rb') as f:
                info['lines'] = sum(1 for _ in f)
        except Exception: info['lines'] = 0
    return info

def list_dir(directory, pattern='*', file_type=None):
    p = Path(directory)
    if not p.is_dir():
        print(f'[ERROR] Not a directory: {directory}', file=sys.stderr)
        sys.exit(1)
    results = []
    for item in sorted(p.glob(pattern)):
        if file_type == 'f' and not item.is_file(): continue
        if file_type == 'd' and not item.is_dir(): continue
        results.append(str(item.absolute()))
    return results

def search_files(directory, pattern, file_glob='*', case_sensitive=False, context_lines=0):
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)
    results = []
    for fpath in Path(directory).rglob(file_glob):
        if not fpath.is_file(): continue
        try:
            enc = detect_encoding(str(fpath))
            with open(fpath, 'r', encoding=enc, errors='replace') as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if regex.search(line):
                    entry = {'file': str(fpath.absolute()), 'line': i + 1, 'content': line.rstrip('\n\r')}
                    if context_lines > 0:
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        entry['context'] = [{'line': j + 1, 'content': lines[j].rstrip('\n\r')} for j in range(start, end)]
                    results.append(entry)
        except Exception as e:
            results.append({'file': str(fpath.absolute()), 'error': str(e)})
    return results

def replace_in_file(filepath, old, new, use_regex=False, dry_run=False):
    enc = detect_encoding(filepath)
    with open(filepath, 'r', encoding=enc, errors='replace') as f:
        content = f.read()
    if use_regex:
        new_content, count = re.subn(old, new, content)
    else:
        count = content.count(old)
        new_content = content.replace(old, new)
    if count == 0:
        print(f'[INFO] No matches found in {filepath}')
        return
    if dry_run:
        print(f'[DRY-RUN] Would replace {count} occurrence(s) in {filepath}')
        return
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print(f'[OK] Replaced {count} occurrence(s) in {filepath}')

def main():
    parser = argparse.ArgumentParser(description='win-fs: Windows filesystem toolkit')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('read'); p.add_argument('path'); p.add_argument('--lines', type=int); p.add_argument('--encoding')
    p = sub.add_parser('write'); p.add_argument('path'); p.add_argument('--content'); p.add_argument('--stdin', action='store_true'); p.add_argument('--append', action='store_true'); p.add_argument('--encoding', default='utf-8')
    p = sub.add_parser('info'); p.add_argument('path')
    p = sub.add_parser('list'); p.add_argument('dir'); p.add_argument('--pattern', default='*'); p.add_argument('--type', choices=['f','d'])
    p = sub.add_parser('search'); p.add_argument('dir'); p.add_argument('pattern'); p.add_argument('--file-glob', default='*'); p.add_argument('--case-sensitive', action='store_true'); p.add_argument('--context', type=int, default=0)
    p = sub.add_parser('replace'); p.add_argument('path'); p.add_argument('old'); p.add_argument('new'); p.add_argument('--regex', action='store_true'); p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('mkdir'); p.add_argument('path')
    p = sub.add_parser('copy'); p.add_argument('src'); p.add_argument('dst'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('move'); p.add_argument('src'); p.add_argument('dst'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('delete'); p.add_argument('path'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('exists'); p.add_argument('path')
    p = sub.add_parser('detect-encoding'); p.add_argument('path')
    args = parser.parse_args()
    try:
        match args.cmd:
            case 'read': print(read_file(args.path, args.encoding, args.lines))
            case 'write':
                if args.stdin: content = sys.stdin.read()
                elif args.content is not None: content = args.content
                else: print('[ERROR] Need --content or --stdin', file=sys.stderr); sys.exit(1)
                write_file(args.path, content, args.append, args.encoding)
                print(f'[OK] Written to {args.path}')
            case 'info': print(json.dumps(file_info(args.path), ensure_ascii=False, indent=2))
            case 'list':
                for item in list_dir(args.dir, args.pattern, args.type): print(item)
            case 'search':
                print(json.dumps(search_files(args.dir, args.pattern, args.file_glob, args.case_sensitive, args.context), ensure_ascii=False, indent=2))
            case 'replace': replace_in_file(args.path, args.old, args.new, args.regex, args.dry_run)
            case 'mkdir': Path(args.path).mkdir(parents=True, exist_ok=True); print(f'[OK] Created directory: {args.path}')
            case 'copy':
                src, dst = Path(args.src), Path(args.dst)
                if not src.exists(): print(f'[ERROR] Source not found: {args.src}', file=sys.stderr); sys.exit(1)
                if dst.exists() and not args.force: print(f'[ERROR] Destination exists. Use --force.', file=sys.stderr); sys.exit(1)
                if src.is_dir():
                    if dst.exists() and args.force: shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                print(f'[OK] Copied to {args.dst}')
            case 'move':
                src, dst = Path(args.src), Path(args.dst)
                if not src.exists(): print(f'[ERROR] Source not found: {args.src}', file=sys.stderr); sys.exit(1)
                if dst.exists() and not args.force: print(f'[ERROR] Destination exists. Use --force.', file=sys.stderr); sys.exit(1)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                print(f'[OK] Moved to {args.dst}')
            case 'delete':
                p = Path(args.path)
                if not p.exists(): print(f'[INFO] Path does not exist: {args.path}'); return
                if p.is_dir() and not args.force: print(f'[ERROR] Is a directory. Use --force.', file=sys.stderr); sys.exit(1)
                if p.is_dir(): shutil.rmtree(p)
                else: p.unlink()
                print(f'[OK] Deleted: {args.path}')
            case 'exists':
                exists = Path(args.path).exists()
                print('true' if exists else 'false')
                sys.exit(0 if exists else 1)
            case 'detect-encoding': print(detect_encoding(args.path))
    except Exception as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
