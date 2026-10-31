# 修改器前端

React 19 + TypeScript + Vite + Motion，跑在 pywebview（WebView2）里。重做方案见仓库外的 `output/frontend-rebuild-plan-20261028/前端重做方案.md`。

**当前进度：阶段 4 验收完成。** 6 个章节、17 个页面全部在新前端上，功能对齐 2.1.22（提交 `39ddabe`）。对照旧实现可用 `git show 39ddabe:frontend/src/lib/components/UnitPanel.svelte`。

## 命令

需要 Node 22 以上和 Python 3.12。只有重新生成字体子集时才需要 `pip install -r requirements-fonts.txt` 和 `npm run fonts:fetch`。

```powershell
npm ci
npm run build              # 检查（类型、对比度、英文覆盖、字体覆盖）后打包到 dist/
npm run assets             # 改了界面文字或图标清单后：重新生成图标模块和字体子集
npm run build:styleguide   # 设计系统样式指南，输出到 dist-styleguide/（不进程序）
npm run dev                # 开发服务器；浏览器打开 http://localhost:5173/?mock 用假后端
node scripts/shoot-app.mjs <目录>      # 用本机 Edge 和假后端截取外壳的几个场景
node scripts/shoot-pages.mjs <目录>    # 截取全部 17 页（先 npm run build）
```

`shoot-pages.mjs` 的环境变量：`SHOT_SIZE=800x480` 设窗口大小，`SHOT_QUERY=&lang=en` 追加地址参数（英文界面），`SHOT_NO_ACT=1` 只截默认状态。默认每页再做一次典型操作，截一张 `-b` 图。

图标模块和字体子集是生成文件，但要提交进仓库：发布构建只跑 `npm run build`，不需要字体工具。`npm run check` 会在源码出现字体子集没有的字时报错，提示先跑 `npm run assets`。`src/app/dev/` 里的假后端不计入字体子集。

从仓库根目录验证真实窗口：

```powershell
python war3_web_gui.py --offline --ui-check ui-check.json
```

它会打开窗口，逐个点开 6 个章节和 17 个页面（等每页的分包渲染完），检查 68 个全局快捷键都在、页面没有横向滚动条、每一页都有控件，结果写进 json。

## 目录

```
src/app/            外壳和页面
  main.tsx          入口；带 ?mock 且没有真后端时加载假后端
  App.tsx           顶带、舞台、操作台三行布局
  routes.ts         6 个章节、17 个页面 ID（和 --ui-check 约定，不能改）
  state/            zustand 状态：system 连接与语言、unit 选中单位、resources 金木人口、
                    locks 锁定、commands 命令卡、catalog ID 目录名称、params 大象参数、
                    notices 错误、nav 当前页面、mapIssues 地图目录原因；sync.ts 负责轮询和事件
  shell/            顶带、昼夜钟、系统菜单、舞台、操作台、聊天框、错误对话框
  pages/            页面，按章节分目录，每页一个分包；registry.ts 是完整的页面表
    common/         PageBody/Section/Status/usePending、DataTable、FieldTable、
                    文件任务（轮询、路径输入、进度、逐文件结果）、背包定义对话框
    battle/         玩家资源、选中单位、批量修改、锁定列表
    fields/         单位字段、技能字段、物品字段、3.0 扩展
    elephant/       经典功能、全局快捷键
    codex/          ID 检索、科技目录、地图数据、3.0 装备、3.0 英雄技能（列表加羊皮纸详情）
    huolong/        脚本注入
    archive/        代码提取
  i18n/             t() 和 fill()：中文原文作键，查 en/*.ts、2.1.22 的 UI_EN 和后端翻译表
  dev/mockBridge.ts 假后端，只在 ?mock 时加载，程序正常运行不会请求它
src/lib/            api.ts、types.ts、ui_text.ts：2.1.22 原样保留，和后端的约定
src/ds/             设计系统：变量、边框、字体、图标、组件、动效
src/styleguide/     样式指南页
scripts/            字体、图标、对比度、英文覆盖检查，截图
```

## 页面约定

- 每页通过 `useCommandCard([...])` 把自己的命令放进操作台的命令卡，一页只调用一次。按键 Q W E R / A S D F / Z X C V 在游戏式的 4×3 格子里。
- 后端调用用 `usePending().run(key, fn)` 包起来：同一个键正在执行时不会再发，按钮和命令卡格子据此显示冷却。
- 写入成功后从改动的格子飘出“+N”（`bounty`），短提示走操作台上方的黄字（`announce`），需要解释的失败进错误对话框。
- `api.ts` 遇到 `success: false` 会先显示原因再抛出异常（带 `reports` 的金矿和批量结果除外），所以页面里 `if (result.success) … else …` 的 else 永远走不到。页面只在 catch 里更新自己的状态行或清掉过期数据，原因不用再报一遍。
- 返回结构以 `war3_desktop_bridge.py` 为准：表格行来自 `VirtualTree.to_list_of_dicts()`，行 ID 和后端一致（单位字段的 ID 就是字段键，锁定 ID 是 `unit:<字段键>`、`resource:<资源组 ID>:<种类>`），数字列可能是数字而不是字符串。假后端 `src/app/dev/mockBridge.ts` 按同样的结构造数据。
- 危险操作（销毁、结束游戏、重置天赋等）用 `HoldToConfirm` 长按确认，不弹确认框。
- 页面表是 `Record<PageId, …>`：漏掉一页会编译失败。

## 数据层

- 等 `pywebviewready` 后读一次状态、单位快照、资源快照、大象参数，然后状态每 2.5 秒、通知每 0.5 秒轮询，和 2.1.22 相同。10 秒还没有后端就报“桌面通信尚未就绪”。
- `api.ts` 原样保留：失败时它照旧广播 `war3-error`，参数变化广播 `war3-elephant-parameters`，`sync.ts` 监听后放进对应的状态。
- 通知按 `kind` 分流：`unit_read` 进单位状态，`parameters` 进大象参数，其他进错误队列。
- 错误：带日志路径、细节或标题的进对话框；短的纯文字原因只显示操作台上方的黄字。
- 刚连上游戏时会再读一次单位快照和资源快照（只读后端已有数据，不读游戏内存）。资源只轮询快照，不会自己读游戏内存，免得进菜单时反复弹错误。
- 背包定义、地图数据、脚本注入是后端的后台任务：页面打开时先查一次进度，能接上关窗前还在跑的任务。
- 窗口失焦时 CSS 动画暂停；轮询照常，数据不受影响。

## 英文

`t('中文原文')` 查表顺序：`src/app/i18n/en/*.ts`（新前端，按章节分文件，构建时合并）、`src/lib/ui_text.ts` 的 `UI_EN`（2.1.22 原有）、后端 `set_ui_language` 返回的翻译、`translateDynamic`。带数字的句子写成模板：`fill(t('第 {n} 格'), { n })`，各语言保留自己的语序，不要拼句子碎片。`npm run check` 会扫描所有 `t('…')` 字面量，缺英文、或同一个键在两个文件里译法不同都会失败。从游戏读出的名字不翻译，单位名用 ID 目录里的英文名。

## 规则

- 设计系统的规则见样式指南最后一节。
- 指令和文案只描述修改器实际做的事。不借用游戏原版秘籍的名字（如 `greedisgood`），不写“秘籍生效”“作弊”：修改器是直接改内存，借用秘籍的说法会误导用户。
- 包住整页的 `AnimatePresence` 不写 `initial={false}`。

## 署名

思源宋体：SIL Open Font License 1.1。部分图标来自 game-icons.net，CC BY 3.0。两者都显示在系统菜单底部。火龙脚本来自 HkeW3mModifier 2.06 附带的原版 HKE 1.25B，原作者火龙 / WuHansen。

本地增量验证（2026-10-31）：以 `4d2aafb` 为界面基线，批量栏增加搜索、分类、只看已填写、可折叠的单位和结果，以及独立滚动的紧凑字段区。字段章节新增单位字段；使用独立 RPC 和服务，沿用现有设计系统。桌面交互与构建记录见 `build/unit-fields-next-20261031/`。
