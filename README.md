[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.12

读取和修改单位、技能、物品及玩家资源，支持批量修改、扩展背包和存档提取。

## 下载与使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.12)下载 EXE。进入地图、选中单位后连接游戏。

本次内置 **3.0.1.24371** 专门适配，合并 Ctrl+X 地形落点计算修复，并修正自动定位的一处对象身份确认问题。

## 适配范围

内置七份游戏配置：`3.0.0.24268`、`3.0.1.24323`、`3.0.1.24332`、`3.0.1.24342`、`3.0.1.24360`、`3.0.1.24365`、`3.0.1.24371`。

24371 的 **3.0 详细属性、迷雾操作和备用本地玩家模式暂未启用**。其他构建以各自配置为准。后续未知版本的完整自动适配仍待完善。

## 从源码构建

Windows 10/11 x64、Git、Python 3.12（含 Tkinter），在仓库根目录执行：

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2112.py
python tools/build_release_2112.py
python tools/build_release_2112.py --verify-only
```

准备脚本从本站下载固定哈希的本版 EXE，提取与已验证 2.1.11 相同的原生组件和运行库；已有该文件时可加 `--from-file 路径`。构建器校验原生输入和全部七份配置的定位依据。程序运行时无需下载适配文件。

输出：`dist-2.1.12-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.12.exe`。

## 验证与记录

分批合计 5,013 项独立测试、120 个子测试通过，29 项跳过；包内核对及 EXE 启动自检通过。当前游戏只读查询通过；实际修改效果、传送落点和外机运行待核对。完整进程的一项既有 Tk 初始化错误在独立进程通过，详细记录保留。

源码只包含当前构建所需文件及历史更新说明。根目录说明保留本地候选时的记录，正式说明见下方。

[当前更新](docs/RELEASE_NOTES_v2.1.12.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json) · [背包定义使用说明](docs/EXTENSION_DEFINITIONS.md)
