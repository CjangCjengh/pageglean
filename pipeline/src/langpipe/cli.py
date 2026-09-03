"""langpipe CLI —— 所有管线阶段的统一入口。"""
from __future__ import annotations

import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import typer
from jinja2 import Template

from .config import CANDIDATES, DATA, FREQ, KB, PROMPTS_DIR, ensure_dirs
from .ledger import Ledger, content_hash

app = typer.Typer(help="拾页 PageGlean 语料管线", no_args_is_help=True)

LANG_NAMES = {"ja": "日语", "ko": "韩语", "th": "泰语", "vi": "越南语"}
LEVEL_SYSTEM = {
    "ja": "JLPT：N5(最易) N4 N3 N2 N1(最难)。轻小说常见语法多落在 N4-N2",
    "ko": "TOPIK：TOPIK1(最易) 至 TOPIK6(最难)",
    "th": "内部级别：L1(最易) 至 L6(最难)，请按语感复杂度与结构复杂度判断",
    "vi": "内部级别：L1(最易) 至 L6(最难)，请按虚词复杂度与句式判断",
}
EXAMPLE_LEVEL = {"ja": "N4", "ko": "TOPIK3", "th": "L2", "vi": "L2"}
LANG_NOTES = {
    "ja": (
        "- 日语语法点：助词用法(は/が/を/に/で/へ/と/も/か…)、动词活用(按学校文法：未然形/連用形/終止形/連体形/仮定形/命令形；"
        "被动/使役/可能按助動詞处理)、复合动词与体貌(〜てしまう/〜ておく/〜始める…)、句末语气(〜よね/〜かな/〜じゃん)、"
        "敬语层位、形式名词(こと/もの/ところ/わけ)\n"
        "- 术语一律用学校文法（連用形而非て形、助動詞而非后缀等）；标题可括注通俗叫法\n"
        "- 注意区分书面语与口语；轻小说口语表达丰富，值得收录的口语语法要标注口语属性"
    ),
    "ko": (
        "- 韩语语法点：终结词尾(-아/어요, -습니다, -ㄴ다)、连接词尾(-고, -지만, -니까, -면서, -는데)、"
        "助词(은/는, 이/가, 을/를, 에, 에서, 에게, (으)로)、依存名词+词尾组合(ㄹ 수 있다, ㄹ게, 기 때문이다)、"
        "补助动词(-아/어 버리다, -아/어 놓다)、敬语阶位"
    ),
    "th": (
        "- 泰语语法点：体貌与语气标记(จะ/ได้/แล้ว/กำลัง/เคย/ต้อง/อาจ)、语序(SVO，修饰语后置)、"
        "量词系统、疑问词与疑问结构(ไหม/หรือเปล่า/อะไร)、句末礼貌助词(ครับ/ค่ะ/นะ/สิ)、"
        "比较结构(กว่า/ที่สุด)、连动式"
    ),
    "vi": (
        "- 越南语语法点：时态虚词(đã/đang/sẽ/rồi/vừa/mới)、分类词/量词(cái/con/chiếc/ông/bà…)、"
        "疑问结构(不/à/ư/吗类: không, phải không, có...không)、比较结构(hơn/nhất)、"
        "话题化结构、被动(被/得: bị/được)、关系从句标记 mà"
    ),
}


def _template_version(name: str) -> str:
    text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
    m = re.match(r"\s*version:\s*(\S+)", text)
    return m.group(1) if m else "0"


def _render(name: str, **ctx) -> str:
    return Template((PROMPTS_DIR / name).read_text(encoding="utf-8")).render(**ctx)


@app.command()
def register():
    """S0 扫描 corpus/ 登记书目。"""
    from .ingest.epub import register_books
    books = register_books(Ledger())
    typer.echo(f"书目共 {len(books)} 本")


@app.command()
def unpack(lang: str = "all", book: str | None = None, workers: int = 8):
    """S1 解包切章。"""
    from .ingest.epub import load_books, save_books, unpack_book
    ensure_dirs()
    books = load_books()
    targets = [b for b in books
               if lang in ("all", b["language"])
               and (book is None or b["book_id"] == book)
               and b.get("status") != "unpacked"]
    if not targets:
        typer.echo("没有需要解包的书")
        return
    if workers <= 1 or len(targets) == 1:
        results = []
        for b in targets:
            try:
                results.append(unpack_book(b))
                typer.echo(f"[S1] {b['book_id']} ✓ {b['chapter_count']}章 {b['total_chars']}字")
            except Exception as e:  # noqa: BLE001
                typer.echo(f"[S1] {b['book_id']} ✗ {e}")
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(unpack_book, b): b for b in targets}
            results = []
            for fut in as_completed(futs):
                b = futs[fut]
                try:
                    nb = fut.result()
                    results.append(nb)
                    typer.echo(f"[S1] {b['book_id']} ✓ {nb['chapter_count']}章 {nb['total_chars']}字")
                except Exception as e:  # noqa: BLE001
                    typer.echo(f"[S1] {b['book_id']} ✗ {e}")
    # 合并回 books.yaml
    by_id = {b["book_id"]: b for b in books}
    for nb in results:
        by_id[nb["book_id"]].update(nb)
    save_books(books)


def _tokenize_one(book_id: str, lang: str) -> dict:
    from .tok import ja, ko, th, vi
    from .tok.common import tokenize_book
    fn = {"ja": ja.tokenize_para, "ko": ko.tokenize_para,
          "th": th.tokenize_para, "vi": vi.tokenize_para}[lang]
    return tokenize_book(book_id, lang, fn)


@app.command()
def tokenize(lang: str = "all", workers: int = 16, book: str | None = None):
    """S2 分词。"""
    from .ingest.epub import load_books
    from .tok.common import TOKENS
    books = [b for b in load_books()
             if lang in ("all", b["language"]) and b.get("status") == "unpacked"
             and (book is None or b["book_id"] == book)]
    todo = [b for b in books if not (TOKENS / b["book_id"]).exists()]
    typer.echo(f"待分词 {len(todo)}/{len(books)} 本")
    if not todo:
        return
    if workers <= 1:
        for b in todo:
            r = _tokenize_one(b["book_id"], b["language"])
            typer.echo(f"[S2] {r['book_id']} {r['tokens']} tokens")
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_tokenize_one, b["book_id"], b["language"]): b for b in todo}
            for fut in as_completed(futs):
                try:
                    r = fut.result()
                    typer.echo(f"[S2] {r['book_id']} {r['tokens']} tokens")
                except Exception as e:  # noqa: BLE001
                    typer.echo(f"[S2] {futs[fut]['book_id']} ✗ {e}")


@app.command()
def freq(lang: str = "all"):
    """S3 词频与词汇候选。"""
    from .freq import build_freq
    langs = ["ja", "ko", "th", "vi"] if lang == "all" else [lang]
    for lg in langs:
        r = build_freq(lg)
        typer.echo(f"[S3] {lg}: {r['types']} 词型, 候选 {r['candidates']}")


@app.command()
def chunk(book: str, target: int = 2000):
    """为 S4b 提取切块。"""
    from .extract.chunk import chunk_book
    chs = chunk_book(book, target=target)
    typer.echo(f"{book}: {len(chs)} 个提取块")


@app.command()
def extract(book: str, max_chunks: int = 5, start: int = 0, target: int = 2000):
    """S4b 试点：claude -p 提取语法点（禁用工具，纯 JSON 输出）。"""
    from .extract.chunk import chunk_book
    from .extract.claude_runner import run_claude
    from .ingest.epub import load_books
    led = Ledger()
    b = next((x for x in load_books() if x["book_id"] == book), None)
    if not b:
        raise typer.Exit(f"未找到 {book}")
    lang = b["language"]
    chunks = chunk_book(book, target=target)
    tpl = "extract_grammar.md.j2"
    tver = _template_version(tpl)
    out_dir = CANDIDATES / lang / "grammar"
    out_dir.mkdir(parents=True, exist_ok=True)
    for ch in chunks[start:start + max_chunks]:
        task_id = f"s4b_extract:{book}:{content_hash(tver, ch['chunk_idx'], ch['text'][:200])}"
        out = out_dir / f"{book}_k{ch['chunk_idx']:04d}.json"
        if led.is_done(task_id):
            typer.echo(f"[S4b] k{ch['chunk_idx']} 已完成，跳过")
            continue
        prompt = _render(
            tpl, lang=lang, lang_name=LANG_NAMES[lang], notes=LANG_NOTES[lang],
            level_system=LEVEL_SYSTEM[lang], example_level=EXAMPLE_LEVEL[lang],
            has_ruby=b.get("has_ruby", False), chunk=ch["text"])
        led.enqueue(task_id, "s4b_extract", book_id=book, item_key=str(ch["chunk_idx"]))
        led.claim(task_id)
        try:
            res = run_claude(prompt)
            payload = {
                "book_id": book,
                "chunk_idx": ch["chunk_idx"],
                "chunk_text": ch["text"],  # 供 adopt 阶段反幻觉核对
                "result": res["data"],
            }
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(out)
            led.complete(task_id, output_path=str(out),
                         prompt_tokens=res["usage"].get("input_tokens"),
                         completion_tokens=res["usage"].get("output_tokens"),
                         executor="claude-code")
            n = len(res["data"].get("grammar_points", []))
            typer.echo(f"[S4b] k{ch['chunk_idx']} ✓ 语法点 {n} 个")
        except Exception as e:  # noqa: BLE001
            led.fail(task_id, str(e))
            typer.echo(f"[S4b] k{ch['chunk_idx']} ✗ {e}")


@app.command()
def adopt(file: Path, lang: str, book: str = ""):
    """把提取候选采纳入 kb/（draft）。"""
    from .merge.adopt import adopt_file
    ids = adopt_file(file, lang, book)
    typer.echo(f"入库 {len(ids)} 条: {', '.join(ids) if ids else '（无）'}")


@app.command()
def author(entry_id: str):
    """S6 试点：为一条语法点生成教程（claude -p，只读工具）。"""
    from .extract.claude_runner import run_claude
    from .validate.models import load_entry
    path = next(KB.glob(f"grammar/*/{entry_id}.yaml"))
    entry = load_entry(path)
    import yaml as _yaml
    prompt = _render("author_new.md.j2",
                     lang_name=LANG_NAMES[entry.language],
                     entry_yaml=_yaml.safe_dump(entry.model_dump(mode="json"),
                                                allow_unicode=True, sort_keys=False),
                     entry_title=entry.title)
    res = run_claude(prompt, allowed_tools="", timeout=600, parse_json=False)
    md = res["raw"].strip()
    if md.startswith("```"):
        md = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", md)
    out = KB / "tutorials" / entry.language / f"{entry_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (f"---\nid: {entry_id}\nlevel: {entry.level}\nstatus: draft\n---\n\n")
    tmp = out.with_suffix(".md.tmp")
    tmp.write_text(header + md + "\n", encoding="utf-8")
    tmp.replace(out)
    typer.echo(f"教程已写: {out}")


@app.command()
def restyle(lang: str = "ja", limit: int = 0, workers: int = 3):
    """把语法条目改写为学校语法术语（claude -p 原地更新）。"""
    import concurrent.futures as cf

    import yaml as _yaml

    from .extract.claude_runner import run_claude
    led = Ledger()
    tpl = "restyle_school.md.j2"
    tver = _template_version(tpl)
    files = sorted((KB / "grammar" / lang).glob(f"{lang}-grm-*.yaml"))
    if limit:
        files = files[:limit]

    def _one(f: Path) -> str:
        data = _yaml.safe_load(f.read_text(encoding="utf-8"))
        task_id = f"s6_restyle:{data['id']}:{content_hash(tver, data['id'])}"
        if led.is_done(task_id):
            return f"[restyle] {data['id']} 已完成，跳过"
        led.enqueue(task_id, "s6_restyle", item_key=data["id"])
        led.claim(task_id)
        slim = {k: data.get(k) for k in
                ("id", "title", "level", "structure", "structure_pattern",
                 "explanation_zh", "tags", "examples")}
        prompt = _render(tpl, lang=lang, lang_name=LANG_NAMES[lang],
                         entry_yaml=_yaml.safe_dump(slim, allow_unicode=True, sort_keys=False))
        try:
            res = run_claude(prompt)
            new = res["data"]
            for k in ("title", "structure", "structure_pattern", "explanation_zh"):
                if new.get(k):
                    data[k] = str(new[k]).strip()
            if isinstance(new.get("tags"), list) and new["tags"]:
                data["tags"] = [str(t) for t in new["tags"]][:5]
            data["review_note"] = "学校语法自动改写（prompt v%s）" % tver
            tmp = f.with_suffix(".yaml.tmp")
            tmp.write_text(_yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
            tmp.replace(f)
            led.complete(task_id, output_path=str(f),
                         prompt_tokens=res["usage"].get("input_tokens"),
                         completion_tokens=res["usage"].get("output_tokens"),
                         executor="claude-code")
            return f"[restyle] {data['id']} ✓"
        except Exception as e:  # noqa: BLE001
            led.fail(task_id, str(e))
            return f"[restyle] {data['id']} ✗ {str(e)[:120]}"

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for msg in ex.map(_one, files):
            typer.echo(msg)


@app.command()
def annotate(lang: str = "ja", workers: int = 3):
    """LLM 为例句标注振假名（替代词典注音；书内注音作参考）。"""
    import concurrent.futures as cf

    import yaml as _yaml

    from .extract.claude_runner import run_claude
    from .merge.adopt import annot_for_example, valid_annot
    led = Ledger()
    tpl = "annotate_reading.md.j2"
    tver = _template_version(tpl)

    # 源块标注文本（书内注音来源）
    chunks: list[str] = []
    for f in sorted(CANDIDATES.rglob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
            if payload.get("chunk_text"):
                chunks.append(payload["chunk_text"])
        except Exception:  # noqa: BLE001
            continue

    files = sorted((KB / "grammar" / lang).glob(f"{lang}-grm-*.yaml"))

    def _one(f: Path) -> str:
        data = _yaml.safe_load(f.read_text(encoding="utf-8"))
        examples = data.get("examples", [])
        if not examples:
            return f"[annotate] {data['id']} 无例句，跳过"
        task_id = f"s6_annotate:{data['id']}:{content_hash(tver, data['id'])}"
        if led.is_done(task_id):
            return f"[annotate] {data['id']} 已完成，跳过"
        led.enqueue(task_id, "s6_annotate", item_key=data["id"])
        led.claim(task_id)
        items = []
        for i, ex in enumerate(examples):
            book = ""
            for ctk in chunks:
                a = annot_for_example(ex.get("text", ""), ctk)
                if "[" in a:
                    book = a
                    break
            items.append({"i": i, "text": ex.get("text", ""), "book_annot": book})
        prompt = _render(tpl, lang=lang, lang_name=LANG_NAMES[lang], items=items)
        try:
            res = run_claude(prompt)
            got = {it["i"]: it.get("annot", "") for it in
                   res["data"].get("items", []) if isinstance(it, dict)}
            n_ok = 0
            for i, ex in enumerate(examples):
                a = (got.get(i) or "").strip()
                if valid_annot(a, ex.get("text", "")):
                    ex["annot"] = a
                    n_ok += 1
            if n_ok == 0:
                led.fail(task_id, "无有效标注输出")
                return f"[annotate] {data['id']} ✗ 无有效标注"
            tmp = f.with_suffix(".yaml.tmp")
            tmp.write_text(_yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
            tmp.replace(f)
            led.complete(task_id, output_path=str(f),
                         prompt_tokens=res["usage"].get("input_tokens"),
                         completion_tokens=res["usage"].get("output_tokens"),
                         executor="claude-code")
            return f"[annotate] {data['id']} ✓ {n_ok}/{len(examples)}"
        except Exception as e:  # noqa: BLE001
            led.fail(task_id, str(e))
            return f"[annotate] {data['id']} ✗ {str(e)[:120]}"

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for msg in ex.map(_one, files):
            typer.echo(msg)


@app.command()
def gloss(lang: str = "all", workers: int = 3, model: str = "qwen3.8-max",
          batch_size: int = 20, limit: int = 0):
    """M2：MaaS 强模型批量释义词汇候选（ko/vi 顺带汉字词源）。"""
    import asyncio

    from .extract.claude_runner import extract_json
    from .llm.clients import MaasClient

    tpl = "gloss_batch.md.j2"
    tver = _template_version(tpl)
    langs = ["ja", "ko", "th", "vi"] if lang == "all" else [lang]
    led = Ledger()
    client = MaasClient(model=model, concurrency=workers)

    def _batches(lg: str) -> list[tuple[int, list[str]]]:
        tsv = CANDIDATES / lg / "vocab_candidates.tsv"
        rows = tsv.read_text(encoding="utf-8").strip().splitlines()[1:]
        words = [r.split("\t")[1] for r in rows if r]
        if limit:
            words = words[:limit]
        return [(i, words[i:i + batch_size]) for i in range(0, len(words), batch_size)]

    async def _one(lg: str, k: int, words: list[str]) -> str:
        task_id = f"s4a_gloss:{lg}:{k}:{content_hash(tver, model, '|'.join(words))}"
        if led.is_done(task_id):
            return f"[gloss] {lg}#{k} 跳过"
        led.enqueue(task_id, "s4a_gloss", item_key=f"{lg}#{k}")
        led.claim(task_id)
        prompt = _render(tpl, lang=lg, lang_name=LANG_NAMES[lg], items=words)
        try:
            raw = await client.chat(
                [{"role": "user", "content": prompt}], max_tokens=2048, timeout=120)
            data = extract_json(raw)
            out_dir = DATA / "enrich" / lg
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"gloss_{k:04d}.json"
            tmp = out.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"words": words, "gloss": data},
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(out)
            led.complete(task_id, output_path=str(out), executor=f"maas-{model}")
            return f"[gloss] {lg}#{k} ✓ {len(data)}"
        except Exception as e:  # noqa: BLE001
            led.fail(task_id, str(e))
            return f"[gloss] {lg}#{k} ✗ {str(e)[:100]}"

    async def _main() -> None:
        for lg in langs:
            bs = _batches(lg)
            typer.echo(f"[gloss] {lg}: {len(bs)} 批（{sum(len(w) for _, w in bs)} 词）")
            # 并发由 MaasClient 信号量节流（默认 3）
            futs = [asyncio.create_task(_one(lg, k, w)) for k, w in bs]
            for fut in asyncio.as_completed(futs):
                typer.echo(await fut)

    asyncio.run(_main())


@app.command()
def validate():
    """校验整个知识库。"""
    from .validate.models import validate_kb
    errs = validate_kb()
    if errs:
        for e in errs[:50]:
            typer.echo(f"✗ {e}")
        raise typer.Exit(1)
    typer.echo("✓ KB 校验通过")


@app.command()
def schemas():
    """导出 JSON Schema（供 claude 输出校验）。"""
    from .validate.models import export_schemas
    export_schemas()
    typer.echo("已写入 pipeline/schemas/")


@app.command()
def report():
    """管线进度报告。"""
    from .ingest.epub import load_books
    books = load_books()
    by_status: dict[str, int] = {}
    for b in books:
        by_status[b.get("status", "?")] = by_status.get(b.get("status", "?"), 0) + 1
    typer.echo(f"书目 {len(books)} 本：{by_status}")
    for row in Ledger().report():
        typer.echo(
            f"任务 {row['stage']:<14} {row['status']:<8} {row['n']:>4}  "
            f"in={row['prompt_tokens']} out={row['completion_tokens']}")
    for lg in ("ja", "ko", "th", "vi"):
        f = FREQ / f"{lg}.tsv"
        c = CANDIDATES / lg / "vocab_candidates.tsv"
        typer.echo(f"{lg}: freq={'✓' if f.exists() else '-'} "
                   f"candidates={'✓' if c.exists() else '-'}")


if __name__ == "__main__":
    app()
