[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.09

读取和修改单位、技能、物品及玩家资源，支持批量修改、扩展背包与存档提取。

## 下载与使用

从 [个人网站](https://twomengxi.xyz/trainer/) 或 [GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.09) 下载 EXE。先进入地图并选中单位，再打开修改器连接游戏。

本版已内置 **3.0.1.24360** 适配，直接使用 EXE 即可。

批量栏读取已提速，继续保留每个单位的完整可修改字段。

## 适配范围

魔兽 3.0：`3.0.0.24268`、`3.0.1.24323`、`3.0.1.24332`、`3.0.1.24342`、`3.0.1.24360`。

连接时按游戏文件指纹选择配置。未收录构建会尝试自动定位，其结果以各项功能检查为准。

## 从源码构建

环境：Windows 10/11 x64、Git、Python 3.12（含 Tkinter）。在仓库根目录执行：

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_209.py
python tools/build_release_209.py
python tools/build_release_209.py --verify-only
```

准备脚本下载固定哈希的原生模块构建依赖；构建器复用其中已发布的三个 DLL，逐项检查源码和文件哈希。运行修改器无需下载此依赖。

输出：`dist-2.1.09-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.09.exe`。

## 源码与验证

当前源码仅保留 2.1.09 的运行模块、适配数据、原生源码和构建文件。旧版本可在 Git 标签与 Releases 中查看；`profiles/` 中的旧游戏构建配置仍是本版依赖。

已通过 4,908 项离线测试、120 项子测试（29 项跳过），以及五版本性能、包内文件、EXE 离线启动和界面资源检查。24360 另有玩家、选中单位和属性的只读核对；实际游戏修改效果及外机运行尚未验收。

[更新说明](docs/RELEASE_NOTES_v2.1.09-r1.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json)
