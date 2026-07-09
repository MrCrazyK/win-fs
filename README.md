# win-fs
windows系统内用codex、opencode和claude读写文件操作时经常报错或者中文乱码，每次还总是重新写脚本一直重试，蠢得一笔。这个用来给他们一个标准脚本来读写，优先用utf8（no BOM），节省时间也节省token。

## 最近暴露的问题

- PowerShell / 默认 Windows 控制台读中文、符号、emoji 时会出现乱码、警告或 `UnicodeEncodeError`。
- 直接用 `Get-Content` / `Select-String` 查文件时，遇到 GBK、UTF-8 BOM、特殊符号、中文路径会不稳定。
- 搜索大仓库时容易扫进 `.git`、`node_modules`、`target`、`dist` 等目录，输出噪音大，还可能碰到 `nul`、二进制文件或权限问题。
- 脚本自身如果带 UTF-8 BOM，会影响某些解释器、YAML/front matter 解析和补丁匹配。
- 只有说明没有测试时，后续改动很容易重新引入编码和搜索噪音问题。

## 本轮已迭代

- `scripts/file_util.py` 已去掉 UTF-8 BOM。
- CLI 启动时会把 stdout/stderr 调整为 UTF-8，避免 GBK 控制台打印中文和特殊符号时崩掉。
- `search` 默认跳过二进制文件。
- `search` 默认排除 `.git`、`.hg`、`.svn`、`.idea`、`.vscode`、`node_modules`、`dist`、`build`、`target`、`tmp`、`__pycache__`；确实需要时可加 `--include-noise-dirs`。
- 增加 `tests/test_file_util.py`，覆盖 BOM、GBK stdout、二进制搜索、默认排除噪音目录。

## 后续迭代任务

1. 增加 `read --start-line --end-line`，避免大文件只能从头读 N 行。
2. 增加 `search --exclude-dir` / `--include-dir`，让调用方能按项目临时调整目录过滤。
3. 增加 `search --max-file-size`，跳过超大日志、压缩包、构建产物。
4. 增加 `write --atomic` 和可选 `--backup`，降低写文件中断导致内容损坏的风险。
5. 增加 `replace --backup`，让批量替换前后可回滚。
6. 增加 `info` 的 BOM 字段、换行符字段和 sha256 字段，便于排查“文件看着一样但工具报错”的问题。
7. 增加 JSONL 输出模式，搜索结果很大时方便流式消费，避免一次性输出过大。
8. 增加发布前自检脚本，检查所有 `.py`、`.md`、`.yaml` 是否 UTF-8 no BOM，并跑完整测试。
