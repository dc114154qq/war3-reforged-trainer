[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.2.3

魔兽风格桌面界面，支持单位、技能、物品、资源与批量修改，新增单位字段编辑。支持扩展背包，装备与天赋方案保存、恢复及导入导出（含同层多个天赋）。还可补齐地图定义、提取存档、检索与导出自定义地图数据和科技，并将经典火龙菜单写进地图副本，在游戏内独立使用。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.3)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；微软 WebView2 缺失或过旧时，启动会询问是否联网安装或更新。

遇到空白／黑屏可使用下载 ZIP 中的“兼容显示模式”启动文件。启动失败会弹窗显示原因和日志路径，日志默认保存在 `%LOCALAPPDATA%\War3Trainer\log\desktop-startup-*.log`。若游戏内功能出错，也请附上修改器操作日志。Alt+P 失败后，新的按键操作会重新读取当前目标，不会被旧失败记录锁住。英雄技能目录现包含被遗忘者圣骑士及其四个技能。

火龙脚本注入保留旧图原有对象定义；辅助对象目录读不全时仍可继续注入，具体原因会写入处理日志。

## 从源码构建

准备 Windows x64、Python 3.12 和 Node.js 22。构建助手会下载并校验固定版本的原生组件和微软安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_223.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release_223.py
python tools/build_modern_release_223.py --verify-only
```

输出：`dist-2.2.3-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.2.3-Web.exe`。

[验证记录](docs/VALIDATION.json)
