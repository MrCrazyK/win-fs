---
name: win-fs
description: Windows filesystem toolkit for AI coding agents. Provides reliable file read, write, search, and info operations via Python, avoiding PowerShell encoding issues, Chinese garbled text, and path separator problems. Use when Codex needs to read files, write files, search file contents, list directories, get file info, replace text, copy/move/delete files, or check file existence on Windows. ALWAYS use this instead of PowerShell Get-Content/Set-Content/Select-String for any file content operation.
---

# Windows File System Toolkit

Use the bundled scripts/file_util.py for ALL file content operations on Windows.
This avoids PowerShell encoding bugs, Chinese text corruption, and path escaping issues.

## Quick reference

| Need | Command |
|------|---------|
| Read a file | python <skill_dir>/scripts/file_util.py read <path> |
| Read first N lines | python <skill_dir>/scripts/file_util.py read <path> --lines N |
| Read with encoding | python <skill_dir>/scripts/file_util.py read <path> --encoding gbk |
| Write a file | python <skill_dir>/scripts/file_util.py write <path> --content "..." |
| Write from stdin | ... | python <skill_dir>/scripts/file_util.py write <path> --stdin |
| Append to file | python <skill_dir>/scripts/file_util.py write <path> --content "..." --append |
| Get file info | python <skill_dir>/scripts/file_util.py info <path> |
| List directory | python <skill_dir>/scripts/file_util.py list <dir> --pattern "*.py" |
| List files only | python <skill_dir>/scripts/file_util.py list <dir> --type f |
| List dirs only | python <skill_dir>/scripts/file_util.py list <dir> --type d |
| Search files | python <skill_dir>/scripts/file_util.py search <dir> <regex> |
| Search with context | python <skill_dir>/scripts/file_util.py search <dir> <regex> --context 2 |
| Search specific files | python <skill_dir>/scripts/file_util.py search <dir> <regex> --file-glob "*.js" |
| Case-sensitive search | python <skill_dir>/scripts/file_util.py search <dir> <regex> --case-sensitive |
| Replace text | python <skill_dir>/scripts/file_util.py replace <path> <old> <new> |
| Replace regex | python <skill_dir>/scripts/file_util.py replace <path> <old> <new> --regex |
| Dry-run replace | python <skill_dir>/scripts/file_util.py replace <path> <old> <new> --dry-run |
| Detect encoding | python <skill_dir>/scripts/file_util.py detect-encoding <path> |
| Check existence | python <skill_dir>/scripts/file_util.py exists <path> |
| Create directory | python <skill_dir>/scripts/file_util.py mkdir <path> |
| Copy file/dir | python <skill_dir>/scripts/file_util.py copy <src> <dst> |
| Move file/dir | python <skill_dir>/scripts/file_util.py move <src> <dst> |
| Delete file | python <skill_dir>/scripts/file_util.py delete <path> |
| Delete dir | python <skill_dir>/scripts/file_util.py delete <path> --force |

## Key behaviors

- **Encoding**: Auto-detects file encoding (UTF-8, GBK, GB2312, GB18030, UTF-16, Latin-1). Writes always use UTF-8.
- **Paths**: Works with any Windows path (absolute, relative, UNC, spaces, Chinese chars).
- **Search output**: JSON array with file, line number, content, and optional context.
- **Info output**: JSON with exists, path, size, is_file, is_dir, encoding, lines.
- **Replace**: Detects source encoding, writes back UTF-8. Use --dry-run first to preview.

## When NOT to use

- Git operations (use git commands directly)
- Running compilers, linters, test runners (use their native CLIs)
- Simple mkdir without content concerns (PowerShell New-Item -ItemType Directory is fine)
- Network/HTTP operations
