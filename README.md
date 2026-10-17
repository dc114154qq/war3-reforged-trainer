[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.10

读取和修改单位、技能、物品及玩家资源，支持批量修改、扩展背包与存档提取。

## 下载与使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.10)下载 EXE。进入地图并选中单位后连接游戏。

**本次新增**：“3.0 扩展”→“读取扩展状态”下方可为 w3n 战役或 w3x 地图补齐背包定义，生成独立副本。完整输出路径可复制。全被动／全光环会记录并跳过已确认清理的单项错误，继续其余技能。

把处理副本放入游戏目录后重新进入地图；旧存档沿用原数据。[使用详情](docs/EXTENSION_DEFINITIONS.md)

## 适配范围

魔兽 3.0：`3.0.0.24268`、`3.0.1.24323`、`3.0.1.24332`、`3.0.1.24342`、`3.0.1.24360`。按游戏文件指纹选择配置，未收录构建会尝试自动定位，以功能检查结果为准。

## 从源码构建

环境：Windows 10/11 x64、Git、Python 3.12（含 Tkinter）。在仓库根目录运行：

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2110.py
python tools/build_release_2110.py
python tools/build_release_2110.py --verify-only
```

准备脚本下载固定哈希的原生构建依赖；构建器同时准备并校验 MPQ 组件。定义数据包已经包含，运行时无需联网下载。

输出：`dist-2.1.10-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.10.exe`。

## 源码与验证

这里只保留构建当前版本所需的源码和数据。历史更新说明、Git 标签及 Releases 保留。

4,953 项离线测试和 120 个子测试通过，29 项跳过；EXE 自检、长路径和界面缩放检查通过。处理后的战役实际游戏效果及外机运行尚未验收。根目录构建说明保留候选阶段的验证记录，当前公开更新说明见下方链接。

[当前更新](docs/RELEASE_NOTES_v2.1.10.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json)
