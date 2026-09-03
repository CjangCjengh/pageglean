# 拾页 · PageGlean

面向中文母语者的日/韩/泰/越语言学习网站。从原声轻小说中由 AI 管线提取语法点、词汇与例句，
按难度分级生成中文教程，并在四种语言之间为互通知识点建立互链。

## 架构一览

```
corpus/ (gitignore)   epub 原文
   ↓ pipeline (langpipe)：解包保 ruby → 四语分词 → 词频 → LLM 提取/裁决 → 教程撰写
kb/                   知识库（语法/词汇/教程/跨语言组），站点唯一内容源
   ↓ site/scripts/kb-sync.mjs（同步即脱敏）
site/                 Astro + React + Tailwind，部署于 Cloudflare Pages
```

> ⚠️ **免责声明**：本站教程、讲解与解析均由 AI 自动生成，可能存在错误或不当之处，
> 仅供学习参考；重要用法请以权威词典与教材为准。

## 版权策略

公开站只含每知识点 ≤2 句短例句（标注来源书名）。完整原文阅读器仅在本地构建
（`PUBLIC_LOCAL=1`）时可用，其数据目录被 gitignore 且云端环境变量永不设置。

## 快速上手

```bash
conda activate langpipe
pip install -e pipeline
make ingest tokenize freq     # 语料处理
make report                   # 进度与花费
cd site && npm run dev        # 本地预览（公开模式）
make site-local               # 本地完整构建（含阅读器）
```

详见 `docs/ARCHITECTURE.md`。
