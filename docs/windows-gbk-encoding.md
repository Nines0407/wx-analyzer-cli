# Windows 控制台 GBK 编码兼容问题

## 问题描述

在 Windows 环境下运行 `wx-analyzer`，Rich 库输出 emoji 字符（如 ✅）时，控制台默认使用 GBK 编码，导致抛出异常：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2705' in position 0:
illegal multibyte sequence
```

## 原因

Windows 中文版系统默认控制台代码页为 GBK（936），无法编码 Unicode emoji。
Rich 库通过 `sys.stdout` 输出格式化文本，而 `sys.stdout` 继承控制台编码。

## 解决方案

在 `main.py` 顶部强制将 `sys.stdout` 重新包装为 UTF-8 编码：

```python
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
```

- `encoding="utf-8"` — 确保 emoji 可正常输出
- `errors="replace"` — 当终端字体不支持某字符时，显示为占位符而非崩溃

## 适用版本

- wx-analyzer-cli v0.1.0
- Python 3.10+ on Windows (zh-CN)
