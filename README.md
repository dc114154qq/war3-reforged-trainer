[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.13

读取和修改单位、技能、物品与资源，支持批量修改、扩展背包和存档提取。

## 下载与使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.13)下载 EXE。进入地图、选中单位后连接。

本次补齐 **3.0.1.24371** 的详细属性、迷雾恢复、备用玩家索引和技能升级尾部处理，并修复最近两次更新的自动状态解码。

内置七份配置：24268、24323、24332、24342、24360、24365、24371。不同构建以各自配置为准；后续未知版本的高级功能仍可能需要适配。

## 从源码构建

Windows 10/11 x64、Git、Python 3.12（含 Tkinter）、Visual Studio 2022 Community 的 C++ 工具和 Windows SDK、LLVM clang-cl。构建器使用 VS 默认安装路径。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2113.py
python tools/build_release_2113.py
python tools/build_release_2113.py --verify-only
```

准备脚本下载固定哈希的已发布 2.1.12 作为依赖基线；已有相同文件可加 `--from-file 路径`。本版桥接重新编译，其余原生组件和运行库经校验复用。运行 EXE 无需联网下载适配文件。

输出：`dist-2.1.13-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.13.exe`。

## 验证与记录

分批 5,052 项独立测试、120 个子测试通过，29 项跳过；七配置性能比较、包内核对和启动自检通过。当前游戏只读查询通过；实际修改效果、备用模式、传送落点和外机运行尚未验收。

[当前更新](docs/RELEASE_NOTES_v2.1.13.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json) · [背包定义](docs/EXTENSION_DEFINITIONS.md)
