[中文](README.md) | [English](README.en.md)

# 魔兽 3.0 修改器 · 2.2.6

魔兽风格桌面界面，支持单位、技能、物品、资源与批量修改。套装方案可以保存和恢复装备、天赋及 30 格背包物品，支持多英雄一键操作和导入导出。还可补齐地图定义、提取存档、检索与导出自定义地图数据和科技，并将经典火龙菜单写进地图副本，在游戏内独立使用。

## 下载使用

从[个人网站](https://twomengxi.xyz/trainer/)或[GitHub Release](https://github.com/dc114154qq/war3-reforged-trainer/releases/tag/v2.2.6)下载 EXE，直接打开。进入地图并选中单位后连接。

Windows 10/11 x64。无需安装 Python、Node.js 或另行启动前端；微软 WebView2 缺失或过旧时，启动会询问是否联网安装或更新。

遇到空白／黑屏可使用下载 ZIP 中的“兼容显示模式”启动文件。启动失败会弹窗显示原因和日志路径，日志默认保存在 `%LOCALAPPDATA%\War3Trainer\log\desktop-startup-*.log`。若游戏内功能出错，也请附上修改器操作日志。Alt+P 失败后，新的按键操作会重新读取当前目标，不会被旧失败记录锁住。英雄技能目录现包含被遗忘者圣骑士及其四个技能。

火龙脚本注入保留旧图原有对象定义；辅助对象目录读不全时仍可继续注入，具体原因会写入处理日志。

ID 检索与自定义地图数据目录可直接添加物品、技能、生成单位或设置科技。生成单位前有 3 秒准备时间，请将鼠标移到游戏画面内；科技等级默认取目录记载的最高等级，也可自行填写。

切换栏目会保留目录浏览位置、搜索和筛选。全局快捷键设置、常用输入、文件路径和栏目顺序会自动保存。顶部栏目可拖动排序，在系统菜单中可以恢复默认顺序。

## 从源码构建

准备 Windows x64、Python 3.12 和 Node.js 22。构建助手会下载并校验固定版本的原生组件和微软安装程序。

```powershell
python -m pip install -r requirements-build.txt
python tools/prepare_build_baseline_226.py
npm ci --prefix frontend
npm run build --prefix frontend
python tools/build_modern_release_226.py
python tools/build_modern_release_226.py --verify-only
```

输出：`dist-2.2.6-modern-verified/<哈希前缀>/War3ReforgedTrainer-v2.2.6-Web.exe`。

[验证记录](docs/VALIDATION.json)
