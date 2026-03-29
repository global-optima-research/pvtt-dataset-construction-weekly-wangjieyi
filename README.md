# PVTT 数据采集 & FFGO 训练数据集

> Product Video Template Transfer (PVTT) — 电商产品视频数据采集与训练集构建
> 目标会议：CVPR 2027
> 负责人：王洁怡

## 仓库结构

| 目录 | 说明 |
|------|------|
| `scripts/` | 采集代码（Amazon/Shopify 爬虫） |
| `reports/` | 数据质量报告、平台分析报告 |
| `weekly-reports/` | 每周工作周报（Week 03-06） |
| `ffgo-training-dataset/` | FFGO LoRA 训练数据集（200 样本 × 8 文件） |

## 数据集概览

| 指标 | Amazon | Shopify | 合计 |
|------|--------|---------|------|
| 产品数 | 1,155 | 3,181 | 4,336 |
| 视频数 | 1,130 | 5,509 | 6,639 |
| 图片数 | 6,391 | 16,528 | 22,919 |
| 品类 | 7 | 8 | 8 (bracelet/earring/handbag/necklace/ring/sunglasses/watch/cosmetics) |
| 店铺 | 1 | 24 | 25 |

## FFGO 训练数据集

200 个样本，每个包含 8 个文件，用于 Wan2.2 TI2V 5B + FFGO LoRA 微调。

详见 [`ffgo-training-dataset/README.md`](ffgo-training-dataset/README.md)

## 周报

| 周次 | 文件 | 主要内容 |
|------|------|----------|
| Week 03 (03-02~03-08) | [week03_report_wjy.md](weekly-reports/week03_report_wjy.md) | Pipeline 搭建，Amazon 爬虫启动 |
| Week 04 (03-09~03-15) | [week04_report_wjy.ipynb](weekly-reports/week04_report_wjy.ipynb) | Amazon 640+ 产品，12 平台调研 |
| Week 05 (03-16~03-22) | [week05_report_wjy.ipynb](weekly-reports/week05_report_wjy.ipynb) | Shopify 爬虫开发，双平台 2342 产品 |
| Week 06 (03-23~03-29) | [week06_report_wjy.ipynb](weekly-reports/week06_report_wjy.ipynb) | 数据集扩展至 4336 产品，FFGO 训练集 200 样本 |

## 报告

| 文件 | 说明 |
|------|------|
| [pvtt_dataset_report.md](reports/pvtt_dataset_report.md) | 数据集统计报告 |
| [platform_analysis_report.md](reports/platform_analysis_report.md) | 13 个电商平台可行性分析 |

## 采集工具

| 脚本 | 说明 | 运行位置 |
|------|------|----------|
| `amazon_spider.py` | Amazon 产品爬虫（搜索→详情→视频下载） | 本地（住宅 IP） |
| `shopify_spider.py` | Shopify 独立站爬虫（/products.json API） | 本地 |
