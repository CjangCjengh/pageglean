# 拾页 PageGlean 架构文档

## 总体数据流

```
corpus/{ja,ko,th,vi}/*.epub        （gitignore，永不进仓库）
  │ S0 register   书目登记（sha256 稳定 id）→ kb/meta/books.yaml
  │ S1 unpack     ebooklib 解包，spine 顺序切章，<ruby> 保真为 基底[读音]
  │               → data/raw/{book_id}/chapters/ch*.json
  │ S2 tokenize   ja fugashi(书内ruby优先) / ko kiwi / th pythainlp / vi underthesea
  │               → data/tokens/{book_id}/ch*.jsonl
  │ S3 freq       词频与词汇候选 → data/freq/{lang}.tsv
  │ S4a 富集      本地 vLLM Qwen：批量释义/翻译/预分类（M2）
  │ S4b extract   claude -p（禁工具，纯 JSON 输出）：语法点识别
  │ S5 merge      pydantic 校验 + 精确/嵌入去重 + Claude 裁决（M4）
  │ S6 author     claude -p：中文教程撰写/修补
  │ S7 xlink      bge-m3 聚类 + Claude 确认：跨语言互链组（M5）
  ▼
kb/                                 （进仓库，站点唯一内容源）
  grammar/{lang}/*.yaml   词汇 vocab/   教程 tutorials/*.md   互链 links/
  ▼ site/scripts/kb-sync.mjs（同步即脱敏）
site/  Astro + React + Tailwind  →  Cloudflare Pages
```

全程由 `data/ledger/pipeline.db`（SQLite）记录任务状态，支持 `--resume` 断点续跑。

## 关键设计决策

### 1. 版权四层防御（最高优先级）
1. `corpus/`、`data/` 不进仓库，CI runner 上不存在原文。
2. 入库硬约束（`langpipe/validate/models.py`）：每条目 ≤2 例句、单句 ≤120 字符，超限拒收。
3. `kb-sync.mjs` 同步时二次脱敏：剥离 `examples[].pointer` 段落指针、再次截断。
4. canary 检查（M6 入 CI）：每本书取一句特征长句，构建产物 grep 命中即红灯。

原文阅读器是**本地构建专属**：`PUBLIC_LOCAL=1` + `site/public/_local/`（gitignore）+
Cloudflare 永不设该环境变量。公开与本地构建共用同一套页面代码，差异仅在数据注入。

### 2. ruby 是免费资产
日语轻小说 epub 自带 `<ruby><rb>/<rt>` 振假名。S1 将其结构化为 `財布[サイフ]` 标注文本，
S2 分词时：若 ruby 基底被分词为单一 token，读音直接采信书内注音（`rs:"book"`，
覆盖专有名词与作者特殊读法）；否则回落 unidic 读音并标记 `rs:"dict"`。

### 3. LLM 分工：贵算力只花在判断上
| 任务 | 执行者 | 模型 |
|---|---|---|
| 词汇释义/例句翻译/难度预分类 | 本地 vLLM | Qwen3-8B 或 Qwen2.5-14B 起步，质检不过升级 |
| 质检裁判（5% 抽样） | MaaS API | qwen3.7-max / deepseek-v3.2 |
| 语法识别 / 教程撰写 / 去重裁决 | `claude -p` | 提取禁用工具，输出走 JSON Schema 校验 |
| 嵌入（去重/互链） | 本地 | bge-m3（M4 才下载） |

MaaS 并发上限 3-5，客户端信号量 3 + tenacity 退避 + 熔断；只做补位不做主力。

### 4. KB 是唯一内容源
站点页面、搜索索引、SRS 卡片、测验题全部由 `kb/` 派生，不允许站点侧手改内容。
pydantic 模型是 schema 唯一事实源（导出 JSON Schema 供提取输出校验），
Astro content collections 用 zod 再校一层。

### 5. 级别归一化
日语映 JLPT N5-N1，韩语映 TOPIK 1-6 级，泰语/越南语用内部 L1-L6。
统一 `level_rank` 数值键驱动全站的排序、筛选与出题；展示层保留原生标签。
注意：级别只用于难度分级；**语法分析术语一律用目标语本国的学校语法**
（日语学校文法：連用形/助動詞/用言体言；韩语 학교문법：어미/품사），
不用外国人教材体系（"て形/ます形"类命名）。提取与教程模板均已写入此要求。

## 目录布局

```
pipeline/        langpipe 包（ingest/tok/freq/extract/merge/author/link/validate）
                 prompts/ 版本化 Jinja2 模板；langdata/stopwords/ 停用词
kb/              grammar vocab tutorials links meta（进仓库）；internal/ 不公开
site/            Astro 站；scripts/{kb-sync,gen-quiz,check-links}.mjs
corpus/ data/    gitignore：epub 原件、中间产物、ledger
scripts/         gpu_lock.sh（共享 GPU 门控）、serve_*.sh、canary/
```

## 运行环境备忘

- conda env `langpipe`（python 3.11）；本机 conda libmamba solver 损坏，
  建环境需 `CONDA_SOLVER=classic`。
- 本地实际有权重的模型（2026-09 核对）：Qwen2.5-14B/7B/0.5B-Instruct、Qwen3-8B。
  Qwen3.5-9B/Qwen3.6-27B 缓存只剩引用无快照，用前需重新下载或改用现有模型。
- pip 已全局清华源；npm 需代理 `127.0.0.1:6890`（mihomo）。
- GPU 8×A6000 共享：起任何推理服务前先 `gpustat`，经 `scripts/gpu_lock.sh` 分配。
- 泰语 epub 含大量零宽空格（U+200B），分词层已过滤。
- 严禁宽匹配 `pkill`（会误杀线上服务）。

## 里程碑

| # | 内容 | 状态 |
|---|---|---|
| M0 | 脚手架：仓库/管线包/站点骨架 | ✅ 本次完成 |
| M1 | 摄取与分词：71 本全量 | ✅ 本次完成（S0-S3） |
| M2 | 本地批量富集（起 9B：释义/翻译/预分类） | 待做 |
| M3 | Claude 提取试点（每语 2-3 本，定成本模型）★预算决策点 | 试点中 |
| M4 | 去重合并（先日语；下载 bge-m3） | 待做 |
| M5 | 教程流水线 + 跨语言互链 | 待做 |
| M6 | 站点 v1 上线（搜索/浏览/概念页/CI/首次部署） | 待做 |
| M7 | SRS + 测验 | 待做 |
| M8 | 本地阅读器（竖排 + 点词 + 门控验证） | 待做 |
| M9 | 71 本全量跑批（韩泰越先、日语最后） | 待做 |
| M10 | 增量入库 SOP | 待做 |
