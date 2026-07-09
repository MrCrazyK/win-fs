import sys, os, shutil, re, json, codecs, argparse, hashlib
from pathlib import Path

DEFAULT_EXCLUDES = {
    '.git', '.hg', '.svn', '.idea', '.vscode',
    'node_modules', 'dist', 'build', 'target', 'tmp', '__pycache__',
}
BINARY_SAMPLE_SIZE = 8192

def _configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

def _has_bom(data):
    if data.startswith(codecs.BOM_UTF8): return 'utf-8'
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
    if bom == 'utf-8': return 'utf-8-sig'
    if bom: return bom
    result = _try_decode(raw, ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1'])
    return result[1] if result else 'utf-8'

def is_binary_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            sample = f.read(BINARY_SAMPLE_SIZE)
    except OSError:
        return False
    if not sample:
        return False
    return b'\x00' in sample

def read_file(filepath, encoding=None, max_lines=None, start_line=None, end_line=None):
    if start_line is not None and start_line < 1:
        raise ValueError('--start-line must be >= 1')
    if end_line is not None and end_line < 1:
        raise ValueError('--end-line must be >= 1')
    if start_line is not None and end_line is not None and start_line > end_line:
        raise ValueError('--start-line cannot be greater than --end-line')
    enc = encoding or detect_encoding(filepath)
    with open(filepath, 'r', encoding=enc, errors='replace') as f:
        if max_lines is not None:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines: break
                lines.append(line)
            return ''.join(lines)
        if start_line is not None or end_line is not None:
            start = start_line or 1
            lines = []
            for i, line in enumerate(f, start=1):
                if i < start: continue
                if end_line is not None and i > end_line: break
                lines.append(line)
            return ''.join(lines)
        return f.read()

def backup_file(filepath):
    src = Path(filepath)
    if src.exists():
        backup = src.with_name(src.name + '.bak')
        shutil.copy2(src, backup)
        return str(backup)
    return None

def write_file(filepath, content, append=False, encoding='utf-8', atomic=False, backup=False):
    path = Path(filepath)
    d = path.parent.absolute()
    if d: d.mkdir(parents=True, exist_ok=True)
    if backup:
        backup_file(path)
    if atomic:
        if append and path.exists():
            content = read_file(str(path), encoding) + content
        tmp = path.with_name(f'{path.name}.tmp.{os.getpid()}')
        with open(tmp, 'w', encoding=encoding, newline='') as f:
            f.write(content)
        try:
            os.replace(tmp, path)
        except PermissionError:
            shutil.copyfile(tmp, path)
            try:
                tmp.unlink()
            except OSError:
                pass
        return
    mode = 'a' if append else 'w'
    with open(path, mode, encoding=encoding, newline='') as f:
        f.write(content)

def detect_newline(raw):
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    cr = raw.count(b'\r') - crlf
    kinds = []
    if crlf: kinds.append('crlf')
    if lf: kinds.append('lf')
    if cr: kinds.append('cr')
    if not kinds: return 'none'
    if len(kinds) == 1: return kinds[0]
    return 'mixed'

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
        raw = b''
        try: raw = p.read_bytes()
        except Exception: raw = b''
        try: info['encoding'] = detect_encoding(str(p))
        except Exception: info['encoding'] = 'unknown'
        info['bom'] = _has_bom(raw)
        info['newline'] = detect_newline(raw)
        info['sha256'] = hashlib.sha256(raw).hexdigest()
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

def _iter_search_files(directory, file_glob, exclude_dirs, include_dirs):
    root = Path(directory)
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        if include_dirs and Path(current_root) == root:
            dirnames[:] = [d for d in dirnames if d in include_dirs]
        current = Path(current_root)
        for name in filenames:
            fpath = current / name
            if fpath.match(file_glob):
                yield fpath

def search_files(directory, pattern, file_glob='*', case_sensitive=False, context_lines=0, exclude_dirs=None, include_dirs=None, max_file_size=None):
    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)
    exclude_dirs = set(DEFAULT_EXCLUDES if exclude_dirs is None else exclude_dirs)
    include_dirs = set(include_dirs or [])
    results = []
    for fpath in _iter_search_files(directory, file_glob, exclude_dirs, include_dirs):
        if not fpath.is_file(): continue
        if max_file_size is not None and fpath.stat().st_size > max_file_size: continue
        if is_binary_file(str(fpath)): continue
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

def replace_in_file(filepath, old, new, use_regex=False, dry_run=False, backup=False):
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
    if backup:
        backup_file(filepath)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    print(f'[OK] Replaced {count} occurrence(s) in {filepath}')

def main():
    _configure_stdio()
    parser = argparse.ArgumentParser(description='win-fs: Windows filesystem toolkit')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('read'); p.add_argument('path'); p.add_argument('--lines', type=int); p.add_argument('--start-line', type=int); p.add_argument('--end-line', type=int); p.add_argument('--encoding')
    p = sub.add_parser('write'); p.add_argument('path'); p.add_argument('--content'); p.add_argument('--stdin', action='store_true'); p.add_argument('--append', action='store_true'); p.add_argument('--encoding', default='utf-8'); p.add_argument('--atomic', action='store_true'); p.add_argument('--backup', action='store_true')
    p = sub.add_parser('info'); p.add_argument('path')
    p = sub.add_parser('list'); p.add_argument('dir'); p.add_argument('--pattern', default='*'); p.add_argument('--type', choices=['f','d'])
    p = sub.add_parser('search'); p.add_argument('dir'); p.add_argument('pattern'); p.add_argument('--file-glob', default='*'); p.add_argument('--case-sensitive', action='store_true'); p.add_argument('--context', type=int, default=0); p.add_argument('--include-noise-dirs', action='store_true'); p.add_argument('--exclude-dir', action='append', default=[]); p.add_argument('--include-dir', action='append', default=[]); p.add_argument('--max-file-size', type=int); p.add_argument('--jsonl', action='store_true')
    p = sub.add_parser('replace'); p.add_argument('path'); p.add_argument('old'); p.add_argument('new'); p.add_argument('--regex', action='store_true'); p.add_argument('--dry-run', action='store_true'); p.add_argument('--backup', action='store_true')
    p = sub.add_parser('mkdir'); p.add_argument('path')
    p = sub.add_parser('copy'); p.add_argument('src'); p.add_argument('dst'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('move'); p.add_argument('src'); p.add_argument('dst'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('delete'); p.add_argument('path'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('exists'); p.add_argument('path')
    p = sub.add_parser('detect-encoding'); p.add_argument('path')
    args = parser.parse_args()
    try:
        match args.cmd:
            case 'read': print(read_file(args.path, args.encoding, args.lines, args.start_line, args.end_line))
            case 'write':
                if args.stdin: content = sys.stdin.read()
                elif args.content is not None: content = args.content
                else: print('[ERROR] Need --content or --stdin', file=sys.stderr); sys.exit(1)
                write_file(args.path, content, args.append, args.encoding, args.atomic, args.backup)
                print(f'[OK] Written to {args.path}')
            case 'info': print(json.dumps(file_info(args.path), ensure_ascii=False, indent=2))
            case 'list':
                for item in list_dir(args.dir, args.pattern, args.type): print(item)
            case 'search':
                exclude_dirs = set(args.exclude_dir) if args.include_noise_dirs else set(DEFAULT_EXCLUDES).union(args.exclude_dir)
                results = search_files(args.dir, args.pattern, args.file_glob, args.case_sensitive, args.context, exclude_dirs, args.include_dir, args.max_file_size)
                if args.jsonl:
                    for item in results:
                        print(json.dumps(item, ensure_ascii=False))
                else:
                    print(json.dumps(results, ensure_ascii=False, indent=2))
            case 'replace': replace_in_file(args.path, args.old, args.new, args.regex, args.dry_run, args.backup)
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
