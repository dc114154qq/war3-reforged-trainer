# 魔兽争霸 III 重制版修改器 v2.2.2 — 建筑专属单位模板（实验版）

这份源码在用户提供的 `war3-reforged-trainer-main` v2.2.2 基础上加入“建筑专属单位模板”。

## 已加入的功能

1. **保存当前选中单位为模板**
   - 先用原有“单位字段”页面把单位改成想要的样子，例如把步兵攻击类型 `ua1t` 改为 `4（魔法）`、修改基础伤害、攻击间隔、护甲、移动速度、HP/MP 等。
   - 回到“大象经典”页，在“建筑专属单位模板”中填写模板名，点击“保存当前单位为模板”。
   - 可额外填写 1 个技能 rawcode 和等级，作为模板附加技能。

2. **把模板绑定到当前选中的具体建筑**
   - 选中一座建筑，只能选一个。
   - 点击“绑定当前选中建筑”。
   - 后端先验证 `UNIT_BF_IS_A_BUILDING`，不是建筑会拒绝。
   - 使用 Warcraft native `AddUnitToStock` 把模板单位 rawcode 加到这座建筑的生产列表。

3. **只给这座建筑后续产出的同 rawcode 单位套模板**
   - 绑定时先记录建筑附近已有的同类单位，避免把旧单位误改。
   - 后台约每 300ms 枚举该建筑所属玩家的单位，按“绑定建筑 + rawcode + 出生半径 + 新句柄”判定新单位。
   - 新单位只改实例字段，不修改全局 `hfoo` / 对象定义，所以其他兵营生产的同 ID 单位不会被全局改掉。
   - 后台扫描与修改器其它游戏写操作共用 dispatch lock，避免并发调用桥。

## 当前模板保存的字段

当前版本保存一组经过原项目原生字段接口验证的常用战斗/状态字段，包括：

- 防御类型、装甲类型
- 生命/魔法恢复
- 当前护甲、移动速度、最大 HP/MP、主动攻击范围
- 攻击 1 伤害骰子、基础伤害、骰子面数
- 攻击 1 最大目标数、攻击类型、武器声音、AOE/目标允许
- 攻击 1 动画回复点、伤害点、攻击间隔及若干伤害参数
- 可选附加技能 rawcode + 等级

`ua1r`（攻击范围）暂不进入模板，因为原项目对该 native 有专门的补偿/验证路径，直接批量回放会带来额外风险。

## 使用示例：魔法步兵专属兵营

1. 游戏里选中一个步兵 `hfoo`。
2. 在修改器“单位字段”中把 `攻击 1 - 攻击类型 (ua1t)` 改成 `4`。
3. 回“大象经典” → “建筑专属单位模板”。
4. 模板名填 `魔法步兵`，点击“保存当前单位为模板”。
5. 游戏里选中你想绑定的那一座兵营。
6. 出生判定半径默认 `420`，点击“绑定当前选中建筑”。
7. 以后这座兵营附近新出现的 `hfoo` 会自动套用“魔法步兵”；其他兵营的 `hfoo` 保持原样。

## 必须知道的边界

Warcraft III 的公开 native 没有一个可以在单位出生后直接查询“这个单位具体由哪一个训练建筑生产”的接口。因此第一版采用建筑实例、单位 rawcode、新句柄和出生距离联合判定。

这意味着：如果另一个来源恰好在绑定建筑的判定半径内生成了同 rawcode 的新单位，它也可能被认为是该建筑产物。正常兵营生产场景下这个判定很实用，但它不是引擎级训练来源事件。

“停止模板监控”只停止后续自动套模板，不会自动调用 `RemoveUnitFromStock`，因为模板单位可能本来就是该建筑的原生生产项（例如兵营的步兵）；自动移除会把原本的生产按钮一起删掉。

## 构建说明

新增功能依赖新的 C bridge 导出 `BridgeProductionTemplateQuery`，所以**不能只把 Python/前端文件塞进旧 EXE**，必须在 Windows x64 构建环境重新编译 `war3_bridge_24268.dll` 并重新打包应用。

项目原有构建要求仍适用：Windows x64、Python 3.12、Node 22、clang（Windows MSVC target）。核心桥构建脚本为：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_engine_bridge.ps1
```

前端：

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

再按项目原有 2.2.2 release 流程，用新生成的 `war3_bridge_24268.dll` 作为 bridge image 打包。

## 本环境已完成的检查

- 新 Python 文件及被修改 Python 文件：`py_compile` 通过。
- 全源码 Python `compileall` 通过。
- production-template 协议的 BIND / SCAN / APPLY 三类请求构造通过。
- Python `ctypes` 复核 C work struct：大小 `2672`，关键偏移与协议完全一致。
- native field 签名与原项目 `war3_unit_field_protocol.py` 对照一致。
- `GetUnitX/GetUnitY` 已按原 bridge 的 32-bit real 位模式 ABI 处理。

未完成：本 Linux 容器没有 Windows SDK/MSVC target 头文件/库，无法在这里编译并运行新的 Windows bridge DLL，也无法进入 Warcraft III 做实机验证。因此此包标记为“实验源码版”，不声称已经实机通过。
