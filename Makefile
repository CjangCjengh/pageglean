PY ?= $(HOME)/miniconda3/envs/langpipe/bin/python
LP = $(PY) -m langpipe.cli

.PHONY: ingest unpack tokenize freq report validate site-dev site-local

ingest:            ## S0+S1 全部书：登记 + 解包切章
	$(LP) register && $(LP) unpack --workers 8

tokenize:          ## S2 分词（lang=ja|ko|th|vi|all）
	$(LP) tokenize --lang $(or $(lang),all) --workers 16

freq:              ## S3 词频与词汇候选
	$(LP) freq

report:            ## 管线进度报告
	$(LP) report

validate:          ## KB schema 校验
	$(LP) validate

site-dev:          ## 本地预览（公开模式）
	cd site && node scripts/kb-sync.mjs && npm run dev

site-local:        ## 本地完整构建（含阅读器）
	cd site && node scripts/kb-sync.mjs && $(PY) -m langpipe.reader_export && PUBLIC_LOCAL=1 npm run build

canary-gen:        ## 生成版权金丝雀（kb/internal/，不进仓库）
	$(PY) scripts/canary/gen_canary.py

canary-check:      ## 检查构建产物是否泄露原文片段
	$(PY) scripts/canary/check_canary.py site/dist
