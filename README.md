[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.2.0

魔兽风格桌面界面，支持单位、技能、物品、资源与批量修改，新增单位字段编辑。还可使用扩展背包、装备套装、补齐地图定义和存档提取。可检索与导出地图自定义数据和科技，并将经典火龙菜单写进地图副本，在游戏内独立使用。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.0)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；缺少微软 WebView2 时，首次启动会询问是否联网安装。

## 从源码构建

准备 Windows x64、Python 3.12 和 Node.js 22。构建助手会下载并校验固定版本的原生组件和微软安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_220.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release.py
python tools/build_modern_release.py --verify-only
```

输出：`dist-2.2.0-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.2.0-Web.exe`。

[验证记录](docs/VALIDATION.json)
