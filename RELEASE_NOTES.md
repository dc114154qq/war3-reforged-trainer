# 发布说明

## v0.2.4

本版本修复 selected-handle 槽长期失效后，“切换目标也读不出来，候选表里没有真实英雄/物品栏单位”的问题。

### 变更

- 候选单位表新增慢速全局扫描：从 unit owner 索引和组件 tag 索引枚举实际存在的单位，不依赖 selected-handle / selected-unit 状态槽仍然有效。
- 全局扫描候选显示为 `扫描`，并展示 HP/MP、坐标、组件、物品槽、handle/owner/unit。英雄/物品栏单位会排在 500/500 等弱 selected-state 候选前面。
- 字段读取的组件识别也接入全局组件 tag fallback，修复全局候选能看到 `hero/inventory`，但读入字段表时装备栏缺失的问题。
- `读取当前选中单位` / `刷新字段表` 自动定位失败时，会尝试填充候选表，并提示用户选择候选后点击 `读取所选候选`。
- 全局候选扫描做了两阶段优化：先快速建 owner->组件索引并排序，只对靠前候选补物品细节，避免逐单位大范围盲扫。

### 已验证

- 当前 selected-handle 失败场景下，`python .\war3_reforged_trainer.py --list-selection-candidates` 能在约 46-50 秒返回 80 个候选。
- 候选前列包含 `扫描` 的 `attack,hero,inventory,move` 英雄；带 6 个物品槽的目标显示为 `inventory=1:ofir,2:I61V,3:I61D,4:brag,5:rde1,6:rat9`。
- `python .\war3_reforged_trainer.py --unit-identity 0xa82800007d5f,0x202e3f23ea0,0x7ff4edd42728 --read-selected-fields` 能读到完整 6 个物品槽。
- `python .\war3_reforged_trainer.py --unit-identity 0xa82800007d5f,0x202e3f23ea0,0x7ff4edd42728 --set-unit-field inventory_slot_5=rde1` 同值写入成功，未交换其他槽位。

## v0.2.3

本版本修复 v0.2.2 中“修改装备后 selected-handle 槽临时失效，导致自动读取失败且候选表缺少刚才那个英雄”的问题。

### 变更

- 字段表写入、上方生命/魔法/坐标写入和字段锁定现在优先固定到当前字段表对应的 handle/owner/unit，而不是写完后重新自动猜当前选择槽。
- GUI 保留 `last_verified_unit_identity`。自动定位失败时不会丢掉这个恢复线索，候选表会把上一次已验证单位列为 `已验证` 候选。
- 候选列表新增 remembered identity 合并路径；即使 selected-unit 指针组里只剩 500/500 等弱候选，也能通过已验证身份重新读回英雄和完整物品栏。
- CLI 的 `--list-selection-candidates` 在同时提供 `--unit-identity HANDLE,OWNER,UNIT` 时，会把该单位列为第一行 `已验证` 候选，便于复现 GUI 兜底路径。

### 已验证

- `python -m py_compile .\war3_reforged_trainer.py`
- 自动定位当前失败场景下，`python .\war3_reforged_trainer.py --list-selection-candidates` 不再被当作成功依据，只显示弱候选。
- `python .\war3_reforged_trainer.py --unit-identity 0xa81400006f34,0x202baf6e618,0x202ace2e430 --list-selection-candidates` 将英雄列为第 1 行 `已验证`，并显示完整 `hero,inventory` 组件和 6 个物品槽。
- `python .\war3_reforged_trainer.py --unit-identity 0xa81400006f34,0x202baf6e618,0x202ace2e430 --set-unit-field inventory_slot_5=brag`
- `python .\war3_reforged_trainer.py --unit-identity 0xa81400006f34,0x202baf6e618,0x202ace2e430 --read-selected-fields`

## v0.2.2

本版本用于发布当前稳定状态：除任意技能替换外，资源、当前选中单位字段、候选单位读取和物品栏功能按现有实现保留。

### 变更

- 当前选中单位定位改为纯内存 selected-handle / selected-unit 路径，不再使用 OCR 截图识别面板数值，也不再用全内存单位指针引用数猜目标。
- selected-unit 定位新增选择状态区动态扫描、多地址一致性投票和短重试；弱证据结果不再自动采用，避免把历史目标、临时对象或 500/500 旁路单位当成当前选择。
- `选中单位` 页新增候选单位表，展示 HP/MP、坐标、refs/known、组件、物品槽、handle/owner/unit。自动定位证据不足时，用户可以选择候选并固定读取/写入这个单位。
- 命令行新增 `--list-selection-candidates` 和 `--unit-identity HANDLE,OWNER,UNIT`，便于复现 GUI 候选读取和按候选身份写入字段。
- 选中单位字段表按实际组件动态显示；非英雄、无技能或无物品栏单位不会因为缺少这些组件而被当成无效目标。
- 移除公开 native handler 验证入口，打包产物不再携带 `war3_native_helper.dll`。
- 去掉远程线程、DLL 注入、native 调用实验路径。
- 技能栏 rawcode/cache/ability 实例相关字段改为只读诊断信息，避免无效写入和崩溃。
- 物品栏写入保持目标槽 item 对象修改，并验证不影响其他槽位。
- 装备/物品栏回到 `选中单位` 字段表里的经典路径：选择 `物品槽N` 或 `物品槽N数量`，用 `字段目标值` + `写入字段` 修改。
- 修复换单位后 `刷新字段表` 只刷新下方表格、上方生命/魔法/坐标输入框仍残留旧单位数值的问题。
- 选中单位定位改为优先新扫描当前选择状态，找不到可验证当前选中单位时清空旧 UI 读数，避免继续显示上一个单位。
- 修复当前英雄组件可能挂在 owner 前方导致技能、英雄属性、攻击、移动、物品栏字段缺失的问题。
- 修正 `写入选中单位` 的生命/魔法上限处理：当前值和上限分开写入，避免把上限错误写成目标当前值。
- Release exe 改为无终端 GUI 版本，双击只打开修改器窗口。
- 打包产物从约 28 MB 降至约 11 MB，因为不再包含 OCR/PIL/numpy 相关依赖。

### 已验证

- `python -m py_compile .\war3_reforged_trainer.py .\tools\war3_selected_probe.py .\tools\war3_disasm_native.py`
- `python -m py_compile .\war3_reforged_trainer.py`
- `python -m PyInstaller .\魔兽争霸3重制版修改器.spec --noconfirm`
- `dist\魔兽争霸3重制版修改器.exe` PE 子系统为 Windows GUI，文件大小约 11.2 MB
- 打包 exe 启动烟测：进程启动并响应，测试后关闭
- `python .\war3_reforged_trainer.py --verify-selection-locator`
- `python .\war3_reforged_trainer.py --read-selected-fields`
- `python .\war3_reforged_trainer.py --list-selection-candidates`
- `python .\war3_reforged_trainer.py --unit-identity 0xa81400006f34,0x202baf6e618,0x202ace2e430 --read-selected-fields`
- `python .\war3_reforged_trainer.py --unit-identity 0xa81400006f34,0x202baf6e618,0x202ace2e430 --set-unit-field inventory_slot_1=ofir`

### 未完成

- 任意替换英雄技能栏技能并让实际技能效果变化。重制版需要走游戏自身 ability 创建/移除/刷新流程，不能只改 rawcode/cache，也不能复制运行时 ability payload。
