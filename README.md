<p align="right"><strong>中文</strong> | <a href="README_EN.md">English</a></p>

# 魔兽争霸 III 重制版修改器

Warcraft III: Reforged trainer 的源码、版本适配数据、测试夹具和发布说明。

## 当前版本

- **最新源代码**：`main` 与 `master` 指向同一份当前维护代码。
- **最新发布**：2.1.0 测试版，标签为 `v2.1.0-beta`。
- **稳定发布**：2.0.9，标签为 `v2.0.9`。
- **测试版适配**：尝试支持 Warcraft III `3.0.0.24268` 和 `3.0.1.24323`，连接时根据实际 PE 构建指纹选择对应适配数据。

测试版发布说明会明确列出已验证范围和未执行的实机验证。配置、夹具和本机 Windows 传输测试不能替代问题外机或新游戏构建的实际运行结果。

## 仓库结构

- `main`、`master`：当前维护代码的两个同步入口。
- `release/<tag>`：与已发布 Git 标签对应的只读历史源码分支，例如 `release/v2.0.9`、`release/v2.1.0-beta`。
- `v*`、`hotkeys-v*`：不可变发布标签，是每个版本的准确源码锚点。
- `profiles/`：按游戏 PE 构建组织的版本适配数据。
- `war3_services/`、`war3_game_session.py`、`war3_engine_transport.py`：功能服务、统一会话和传输后端。
- `tools/`：源码、构建脚本和验证工具；临时编译结果放在本地 `build/`。
- `website/`：个人网站页面、翻译和 GitHub Release 同步脚本。

## 发布与构建

发布 EXE 只作为 GitHub Release 和个人网站的下载资产，不提交到源码仓库的 `dist/` 或 `build/` 目录。发布前必须完成：

1. 识别游戏构建并核对 `GameProfile`、RVA、对象布局、TLS、Native 注册表和调用约定。
2. 验证公共会话、对象解析、桥协议、进程重启、换图、窗口线程变化和对象销毁后的缓存失效。
3. 按资源/单位、技能/物品、扩展背包/装备、天赋/图标依次验证，并区分命令送达、状态读回和实际游戏效果。
4. 运行与发布版本对应的构建清单和 EXE 自检，再发布适配包。
5. 部署网站前比对线上文件，保留公告、订阅区域和其他工具页面；验证中英文页面及下载文件 SHA256。

2.1.0 测试版使用专用构建器：

```powershell
python tools/build_release_210.py
python tools/build_release_210.py --verify-only
```

已发布版本的完整说明见 [GitHub Releases](https://github.com/dc114154qq/war3-reforged-trainer/releases)，下载页见 [个人网站](https://twomengxi.xyz/trainer/)。

## 2.0.8／2.0.9 外机修复来源

当前架构线以 2.0.7 为基础，并在提交 `129c389` 中迁入 2.0.8／2.0.9 的加载、备用安装、私有回调退出和资源清理修复。后续版本适配不得恢复旧传输链路；详细边界和验证结果见 [ARCHITECTURE.md](ARCHITECTURE.md) 与 [AGENTS.md](AGENTS.md)。

## 许可与说明

源码中的版本适配和原生执行逻辑仅针对明确匹配的游戏构建启用。未知构建先生成只读诊断，不沿用旧偏移执行写入。第三方 MinHook 许可见 `third_party/minhook/LICENSE.txt`。
