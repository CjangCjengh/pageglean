# ADR-002 Cloudflare Pages 部署配置

日期：2026-09-03　状态：已接受

## 决定
- 项目 `pageglean` 连接 GitHub 仓库 `CjangCjengh/pageglean`，main 分支 → 生产，
  PR → 预览（含 PR 评论），自动部署。
- 构建：`cd site && npm ci && npm run build`（kb-sync + astro build），
  输出 `site/dist`，NODE_VERSION=22（生产与预览均设置）。
- 生产域名：https://pageglean.pages.dev

## 理由
- Cloudflare Pages 免费、国内访问快，Git 集成实现 push 即部署；
  PR 预览方便审校教程内容后再合并。
- 公开构建不含原文（见 ADR-001）：CI runner 上无 corpus，kb-sync 二次脱敏。

## 后果
- `site/package-lock.json` 必须入库（npm ci 依赖）。
- 后续若加 Pages Functions（如云端学习进度），在同一项目内扩展。
