[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.1.16

读取和修改单位、技能、物品与资源，支持批量修改、扩展背包、装备套装和存档提取。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.1.16)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；缺少微软 WebView2 时，首次启动会询问是否联网安装。

本次在“玩家资源”页新增金矿剩余金币修改，支持当前选中和全图批量操作，逐座显示修改前后金额和结果。

## 从源码构建

准备 Windows x64、Python 3.12 和 Node.js 22。构建助手会下载并校验固定版本的原生组件和微软安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_2116.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release.py
python tools/build_modern_release.py --verify-only
```

输出：`dist-2.1.16-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.1.16-Web.exe`。

[更新说明](docs/RELEASE_NOTES_v2.1.16.zh.md) · [历史更新](docs/HISTORY.md) · [验证记录](docs/VALIDATION.json)
