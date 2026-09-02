# ADR-001 托管与版权策略

日期：2026-09-02　状态：已接受

## 决定
- 源码托管 GitHub（公开仓库），部署 Cloudflare Pages（免费、国内访问快、可升级 Workers）。
- 公开站只含每知识点 ≤2 句短例句（标注来源书名），不含整段原文。
- 完整原文阅读器仅本地构建可见：`PUBLIC_LOCAL=1` 环境变量 + `site/public/_local/`
  数据目录（.gitignore）+ Cloudflare 侧永不配置该变量。三重门控缺一不可。

## 理由
- 原文受版权保护，整段公开有下架与法律风险；短例句用于教学示例，风险最低。
- GitHub Pages 国内访问不稳定，Cloudflare Pages 免费且更快，保留未来加
  无服务器函数（云端进度同步）的升级路径。

## 后果
- 入库、同步、CI 三处都要维持脱敏逻辑（见 docs/ARCHITECTURE.md 版权四层防御）。
- M6 需实现 canary 检查并纳入 CI，构建产物出现整段原文即红灯。
