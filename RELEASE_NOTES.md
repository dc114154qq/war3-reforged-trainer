# 发布说明

## v0.2.0

本版本用于发布当前稳定状态：除任意技能替换外，资源、当前选中单位字段和物品栏功能按现有实现保留。

### 变更

- 当前选中单位定位改为纯内存 selected-handle/单位指针路径，不再使用 OCR 截图识别面板数值。
- 移除公开 native handler 验证入口，打包产物不再携带 `war3_native_helper.dll`。
- 去掉远程线程、DLL 注入、native 调用实验路径。
- 技能栏 rawcode/cache/ability 实例相关字段改为只读诊断信息，避免无效写入和崩溃。
- 物品栏写入保持目标槽 item 对象修改，并验证不影响其他槽位。
- Release exe 改为无终端 GUI 版本，双击只打开修改器窗口。
- 打包产物从约 28 MB 降至约 11 MB，因为不再包含 OCR/PIL/numpy 相关依赖。

### 已验证

- `python -m py_compile .\war3_reforged_trainer.py .\tools\war3_selected_probe.py .\tools\war3_disasm_native.py`
- `python -m PyInstaller .\魔兽争霸3重制版修改器.spec --noconfirm`
- `dist\魔兽争霸3重制版修改器.exe` PE 子系统为 Windows GUI
- `python .\war3_reforged_trainer.py --verify-selection-locator`
- `python .\war3_reforged_trainer.py --read-selected-fields`

### 未完成

- 任意替换英雄技能栏技能并让实际技能效果变化。重制版需要走游戏自身 ability 创建/移除/刷新流程，不能只改 rawcode/cache，也不能复制运行时 ability payload。
