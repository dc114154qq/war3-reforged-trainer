[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.2.1

魔兽风格桌面界面，支持单位、技能、物品、资源与批量修改，新增单位字段编辑。支持扩展背包，装备与天赋方案保存、恢复及导入导出（含同层多个天赋）。还可补齐地图定义、提取存档、检索与导出自定义地图数据和科技，并将经典火龙菜单写进地图副本，在游戏内独立使用。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.1)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；微软 WebView2 缺失或过旧时，启动会询问是否联网安装或更新。

遇到空白／黑屏可使用下载 ZIP 中的“兼容显示模式”启动文件。启动失败会弹窗显示原因和日志路径，日志默认保存在 `%LOCALAPPDATA%\War3Trainer\log\desktop-startup-*.log`。日志包含修改器版本、文件校验值、WebView2 版本和界面错误，反馈问题时发送对应日志即可。

## 从源码构建

准备 Windows x64、Python 3.12 和 Node.js 22。构建助手会下载并校验固定版本的原生组件和微软安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_221.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release.py
python tools/build_modern_release.py --verify-only
```

输出：`dist-2.2.1-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.2.1-Web.exe`。

[验证记录](docs/VALIDATION.json)
