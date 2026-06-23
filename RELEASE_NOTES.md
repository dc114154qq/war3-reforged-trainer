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
