# 构建 2.1.08 / Build 2.1.08

本版只更改 Python 功能和界面，使用线上 2.1.07 的三个原生 DLL。它们从已验证的旧 EXE 中提取，逐个核对 SHA256。游戏适配包和原生源文件也与该发布基线逐项比较。

在 Windows x64、Python 3.12 和 main/master/release 对应检出中执行：

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_208.py
python tools/build_release_208.py
python tools/build_release_208.py --verify-only
```

基线下载地址及哈希固定在准备脚本和 docs/BUILD_BASELINE_v2.1.07.json；已有下载也会校验。验证失败会停止构建。运行时不执行此下载。

This Python feature reuses the exact published 2.1.07 native DLLs. The preparation script downloads one immutable baseline EXE and verifies its SHA256. The builder verifies each native image and all native/profile inputs before packaging. The trainer does not download this build dependency at runtime.

离线批量功能及界面回归：安装 pytest 后执行 `python -m pytest -q tests/test_batch_edit.py test_ui_i18n.py`。完整验证结果见 docs/VALIDATION_v2.1.08.json。夹具验证与实际游戏效果分别记录。
