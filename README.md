# 魔兽争霸 III 重制版修改器

这是一个面向《魔兽争霸 III：重制版》的本地修改器。当前版本以稳定性优先：资源、选中单位属性、背包物品栏等功能走内存读取/写入；技能栏目前只读展示，不再提供会导致技能消失或游戏崩溃的伪写入。

## 下载和运行

从 GitHub Release 下载 `War3ReforgedTrainer-v0.2.1.exe`，直接双击运行即可。Release 页面里它的显示标签是 `魔兽争霸3重制版修改器.exe`。这是 PyInstaller 打包的单文件 GUI 程序，不会额外弹出终端窗口，也不需要安装 Python。

运行前请先启动《魔兽争霸 III：重制版》，进入地图并选中目标单位。修改器会自动查找正在运行的 `Warcraft III.exe`。

## 兼容版本

- 已实机测试版本：`Warcraft III: Reforged 2.0.4.23745`。
- 其他 `2.0+` 版本没有逐个验证，不能保证一定可用。这个修改器依赖 Reforged 当前进程里的内存布局；如果暴雪更新改了 selected-handle、单位组件或物品栏对象结构，可能需要重新适配。
- 如果游戏以管理员权限运行，修改器也需要用管理员权限运行。

## 可用功能

- 玩家资源：读取多个阵营/玩家资源组，修改金币、木材、人口。
- 当前选中单位：读取并修改 HP、MP、回复、坐标、经验、技能点、三围、护甲、移动速度、攻击相关字段等。非英雄或无背包单位会只显示实际存在的组件字段，缺少英雄/技能/物品栏组件不是读取失败。
- 物品栏：在 `选中单位` 页面的字段表里读取 `物品槽1..6` 和 `物品槽N数量`，通过 `字段目标值` + `写入字段` 修改目标槽。当前实现只修改目标槽对应的 item 对象，不通过交换两个槽位来伪装修改。
- 技能信息：读取英雄技能栏 rawcode、运行时 ability 实例 rawcode、效果类、data vtable、data cache 等诊断信息。

## 当前限制

- 任意技能替换尚未完成。重制版里已学技能的实际效果不由英雄技能栏 rawcode 或缓存 rawcode 单独决定，而是绑定在运行时 ability 实例和数据对象上。
- 本版本不会写入 `skill*_name`、`skill*_cache_rawcode`、`skill*_instance_rawcode`、`skill*_effect_class` 等技能字段。旧的 rawcode/cache 写法会显示变了但实际效果不变，复制 ability payload 还可能导致技能消失或游戏崩溃，所以已经禁用。
- 修改器不会修改游戏文件、存档或地图文件。
- 修改器不使用 OCR 截图识别当前目标；当前选中单位只通过内存中的 selected-handle / selected-unit 槽定位。selected-unit 会动态扫描选择状态区，并按多个地址一致指向同一个 unit 对象投票；新局初始化时会短暂重试。找不到可验证的当前选择槽时会报错，而不会按面板数值或全内存单位指针引用次数猜目标。
- 修改器不再注入 DLL、不创建远程线程、不调用 Warcraft III native handler。之前的实验路径已移除，避免再次导致游戏崩溃。

## 界面说明

- `读取当前选中单位` 和 `刷新字段表` 都会重新读取当前游戏选中的单位，并刷新上方生命/魔法/坐标输入框，避免换过单位后继续显示旧单位数值。
- `写入选中单位` 会按界面字段分别写入当前生命、生命上限、当前魔法、魔法上限、回复率和坐标；当前值高于上限时才会自动抬高上限。
- 装备/物品修改沿用经典修改器的字段表路径：在 `选中单位` 页面的字段表选择 `物品槽N` 或 `物品槽N数量`，填写 `字段目标值` 后点击 `写入字段`。空槽没有可直接改写的 item 对象时会报错。
- 如果本轮没有找到可验证的当前选中单位，界面会清空旧的单位/物品栏读数并报错，不再保留上一个单位的显示值。

## 能否保证别人下载 exe 就能用

可以保证的是：这个 exe 是单文件 GUI 打包，当前构建不依赖本机 Python、PIL、Capstone 或 helper DLL；在本机已完成编译、打包和纯内存选中单位/字段读取验证。

不能绝对保证所有人都能直接用，因为它依赖以下外部条件：

- Windows 64 位环境。
- 正在运行的《魔兽争霸 III：重制版》进程。
- 游戏版本和当前内存布局与本版本探测逻辑兼容；当前只在 `2.0.4.23745` 上实测。
- 修改器权限不低于游戏进程权限；如果游戏以管理员运行，修改器也需要管理员运行。
- 杀毒软件或系统策略没有拦截读取/写入游戏进程内存。

如果这些条件满足，别人拿到 Release 里的 exe 应该可以直接运行。若暴雪更新导致内存布局变化，选中单位或字段地址可能需要重新适配。

## 开发自检

```powershell
python .\war3_reforged_trainer.py --read-selected
python .\war3_reforged_trainer.py --read-selected-fields
python .\war3_reforged_trainer.py --verify-selection-locator
```

这些自检只用于开发时确认进程查找和当前选中单位定位。`--read-selected`、`--read-selected-fields`、`--verify-selection-locator` 是只读操作。Release 里的 exe 是无终端 GUI 版本，不适合作为命令行工具查看输出。

## 开发说明

- 主程序：`war3_reforged_trainer.py`
- 打包配置：`魔兽争霸3重制版修改器.spec`
- 开发用只读探针：`tools/war3_selected_probe.py`
- 开发用只读 native 表反汇编：`tools/war3_disasm_native.py`

打包命令：

```powershell
python -m PyInstaller .\魔兽争霸3重制版修改器.spec --noconfirm
```

打包产物：

```text
dist\魔兽争霸3重制版修改器.exe
```
