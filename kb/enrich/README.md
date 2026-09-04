# kb/enrich —— M2 词汇释义草稿（待人工审阅）

来源：`langpipe gloss`（MaaS qwen3.8-max，每批 20 词）。
每种语言跑完后由 scripts/push_enrich.py 拷入并推送，供用户抽检质量。
抽检通过后才会被 ingest 成正式 vocab 条目（M7 前置）。
ko/vi 条目含 hanja/hantu 汉字词源字段（用于汉字 ruby 开关）。
