# Warcraft III 工具发布站

静态版本归档站。首页提供修改器和独立改键软件两个入口。服务器每 10 分钟读取 GitHub Releases，镜像缺失的 `.exe` 文件，并更新版本说明、文件大小与 SHA256。

- `/trainer/`：修改器版本页，使用 `releases.json`。
- `/hotkeys/`：改键软件版本页，使用 `hotkey-releases.json`。
- `hotkeys-*` 标签归入改键软件，其余 Release 标签归入修改器。

## 本地预览

`releases.json` 生成后，在仓库根目录运行：

```powershell
python -m http.server 8765 --directory website
```

然后访问 `http://127.0.0.1:8765`。

## 同步

服务器目录：

- 网站：`/srv/war3-releases`
- 同步脚本：`/opt/war3-releases/sync_github_releases.py`
- 定时任务：`war3-release-sync.timer`

后续发布新版本时，只需在 GitHub 仓库创建 Release 并上传 `.exe`。改键软件使用 `hotkeys-vX.Y.Z` 标签，修改器沿用 `vX.Y.Z`。同步任务会自动把版本加入对应页面。`manual-releases.json` 仅用于尚未发布到 GitHub 的修改器本地版本；相同标签出现在 GitHub 后，以 GitHub Release 为准。

## 发布与网站部署规则

- 正式版和测试版均按发布时间进入版本历史和首页最新下载。`latest` 指最新发布，包含测试版；`latest_stable` 单独记录最新正式版。测试版在首页及版本卡片明确标注，不能因其是预发布而继续把旧版当作最新版。
- 发布前核对线上文件和当前工作树的差异。网站与修改器可在不同分支开发，不能用旧工作树整页覆盖线上内容；保留反馈日志公告、游戏版本公告、订阅表单及其他工具页面。
- 页面、共享脚本和翻译字典必须配套部署，并更新资源版本号。保留原公告正文；缺失翻译时保留 HTML 文案，不能向用户显示翻译键。
- 部署采用备份和原子替换。先本地检查，再更新线上索引，检查中英文、最新版本、测试版标记、公告、订阅区域、历史搜索和下载链接。共享脚本改动同时检查改键与头像修复器页面。
- 检查线上下载的 EXE 大小和 SHA256 与发布产物一致。网站修复不重建或替换已经发布的 EXE；测试证据与问题机实测分别记录。

正式域名为 `twomengxi.xyz`。Caddy 会在 DNS 生效后自动申请并续期 HTTPS 证书；服务器 IP 入口保留为 DNS 传播期间的临时访问地址。
