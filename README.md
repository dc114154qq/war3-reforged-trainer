[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.14

读取和修改单位、技能、物品与资源，支持批量修改、扩展背包与存档提取。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.14)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；缺少微软 WebView2 时，首次启动会询问是否安装，安装需要联网。

本次更新：新版 UI、自定义并保存六件神器、技能字段列表修复、恢复套装保留已装备物品、背包定义补齐修复。

## 从源码构建

Windows 10/11 x64、Python 3.12 和 Node.js 22。首次构建准备固定哈希的已发布原生组件与微软 WebView2 安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2114.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release.py
python tools/build_modern_release.py --verify-only
```

输出位于 `dist-2.1.14-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.14-Web.exe`。

[更新说明](docs/RELEASE_NOTES_v2.1.14.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json)
