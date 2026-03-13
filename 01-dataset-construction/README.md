# PVTT 数据采集模块

> Product Video Template Transfer (PVTT) — 多平台电商产品视频数据采集
> 目标会议：CVPR 2027
> 最后更新：2026-03-14

## 概述

本模块负责电商产品视频数据的采集、处理和管理，用于 PVTT 项目。目标是从多个电商平台收集大规模的产品展示视频和图片数据，涵盖珠宝、配饰等多个品类。

**目标规模**：1000+ 产品，500+ 视频，覆盖 7 个品类和 5+ 个平台。

## 当前进度（2026-03-14）

### 已采集数据

| 平台 | 产品数 | 图片数 | 视频数 | 数据量 | 状态 |
|------|--------|--------|--------|--------|------|
| **Amazon** | 622+ | 3,432+ | 603+ | 3.8 GB | **进行中**（爬虫运行中，扩展至 800+） |
| **Etsy** | 少量 | 少量 | 0 | ~MB | 已阻断（Datadome CAPTCHA） |
| **TikTok Shop** | - | - | - | - | 计划中 |
| **eBay** | - | - | - | - | 计划中 |
| **淘宝** | - | - | - | - | 计划中 |

### Amazon 数据分类明细

7 个品类：bracelet (133)、earring (144)、handbag (38)、necklace (122)、ring (62)、sunglasses (64)、watch (59)
*（爬虫仍在运行中 — 正在使用更多关键词扩展 handbag、sunglasses、watch、ring 等品类）*

### 服务器处理Pipeline

完整处理Pipeline已测试通过：53 个视频 -> 87 个片段 -> 87 个标准化文件（1280x720, 24fps, H.264）
- 服务器：`wangjieyi@111.17.197.107`（RTX-5090-32G-X8）
- 数据路径：`/data/wangjieyi/pvtt-dataset/amazon_data/`

## 目录结构

完整的目录规划详见 [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md)。

### 当前布局

```
01-dataset-construction/
  README.md                          # 本文件
  DIRECTORY_STRUCTURE.md             # 目录重组规划文档

  # === 运行中的爬虫（请勿移动） ===
  amazon_spider.py                   # Amazon 产品爬虫
  amazon_data/                       # Amazon 采集数据（运行中）

  # === 平台爬虫 ===
  etsy_spider.py                     # Etsy 爬虫（被 Datadome 阻断）
  etsy_data/                         # Etsy 数据

  # === Pipeline 文档 ===
  pipelines/
    tiktok/README.md                 # TikTok Shop Pipeline（计划中，Apify）
    ebay/README.md                   # eBay Pipeline（计划中，Browse API）
    taobao/README.md                 # 淘宝 Pipeline（计划中，第三方服务）

  # === 工具脚本 ===
  pvtt_pipeline.py                   # 主Pipeline编排器（采集 -> 上传 -> 处理 -> 报告 -> 推送）
  upload_to_server.py                # 上传数据至 RTX-5090 服务器
  generate_dataset_report.py         # 生成数据集报告
  generate_charts.py                 # 生成报告图表
  build_notebook.py                  # 构建报告 Notebook

  # === 报告 ===
  platform_analysis_report.md        # 12 个平台分析报告
  pvtt_dataset_report.html           # 数据集报告（HTML）
  pvtt_dataset_report.md             # 数据集报告（Markdown）

  # === 服务器 ===
  server-scripts/                    # 服务器端处理脚本

  # === 历史遗留（待归档） ===
  ecommerce-scraper/                 # 旧版Pipeline
  data_pipeline.py                   # 旧版重复Pipeline脚本
  launch_spider.py                   # 旧版爬虫启动器
```

## 平台策略

### 第一优先级：进行中

| 平台 | 采集方式 | 成本 | 视频率 | 备注 |
|------|----------|------|--------|------|
| **Amazon** | 自研爬虫（requests + 住宅IP） | 免费 | ~40-60% | 必须本地运行（服务器会被 503） |

### 第二优先级：计划中（下一步）

| 平台 | 采集方式 | 成本 | 视频率 | 备注 |
|------|----------|------|--------|------|
| **eBay** | Browse API（官方，免费） | 免费 | ~10-20% | 注册开发者账号，以图片为主 |
| **TikTok Shop** | Apify Scraper | ~$2/1K 产品 | ~90% | 竖屏视频需裁剪/缩放 |
| **Etsy** | Open API v3（仅图片） | 免费 | ~10-15% | 视频被 Datadome 阻断 |

### 第三优先级：未来（视预算而定）

| 平台 | 采集方式 | 成本 | 视频率 | 备注 |
|------|----------|------|--------|------|
| **淘宝/天猫** | 第三方数据服务 | ¥100-250 | ~70-80% | 质量最高，横屏视频 |
| **京东** | 第三方（可与淘宝捆绑） | ¥50-100 | ~50-60% | 品牌旗舰店视频 |

### 不推荐

| 平台 | 原因 |
|------|------|
| AliExpress | Akamai Bot Manager，成本高 |
| 小红书 | 法律合规风险（中国数据法律） |
| 拼多多 | 视频质量低，低价产品为主 |
| Shopee | 珠宝品类不强 |
| Walmart/Target | 品牌官方视频（非佩戴演示） |

完整的 12 平台深度分析详见 [platform_analysis_report.md](platform_analysis_report.md)。

## 统一数据格式

所有平台Pipeline必须按以下标准化格式输出数据：

```
{platform}_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # 产品元数据（JSON）
    media/
      images/
        {PRODUCT_ID}_01.jpg          # 产品图片
        {PRODUCT_ID}_02.jpg
      videos/
        {PRODUCT_ID}.mp4             # 产品视频（如有）
```

JSON Schema 详见 [DIRECTORY_STRUCTURE.md](DIRECTORY_STRUCTURE.md)。

## 主要脚本

| 脚本 | 功能 |
|------|------|
| `amazon_spider.py` | Amazon 产品爬虫（品类、图片、视频、元数据） |
| `etsy_spider.py` | Etsy 产品爬虫（被 Datadome 阻断） |
| `pvtt_pipeline.py` | 主Pipeline编排器：采集 -> 上传 -> 处理 -> 报告 -> 推送 |
| `upload_to_server.py` | 通过 SSH 上传采集数据至 RTX-5090 服务器 |
| `generate_dataset_report.py` | 生成数据集统计和报告 |
| `generate_charts.py` | 生成可视化图表 |
| `build_notebook.py` | 构建 Jupyter 风格的报告 Notebook |

## 执行计划

### 第一阶段：Amazon 扩展（当前）
- 将 Amazon 数据扩展至 600+ 产品，覆盖 7 个品类
- 每个品类使用更多关键词以增加多样性
- 爬虫后台运行中 -- 请勿中断

### 第二阶段：免费平台 API（下一步）
- 注册 eBay Developer Program，构建 Browse API 客户端
- 注册 Etsy 开发者账号，通过 API v3 采集图片
- 注册 Apify 免费账号，测试 TikTok Shop Scraper

### 第三阶段：付费数据源（未来）
- 联系中国本地数据服务商获取淘宝/京东报价
- 如预算批准，购买 500+ 产品数据
- 申请 TikTok Research API（需导师推荐信）

## 服务器上传

数据上传至服务器进行 GPU 加速处理：

```bash
# 上传命令（本地运行）
python upload_to_server.py
# 目标路径：/data/wangjieyi/pvtt-dataset/amazon_data/
```

服务器处理Pipeline：镜头分割 -> 标准化（1280x720, 24fps, H.264）

## GitHub 仓库

- 仓库：`global-optima-research/pvtt-dataset-construction-weekly-wangjieyi`
- 分支：`main`
- 推送：`git push origin main`（如被拒绝需先 pull）

## 技术调研

原始技术调研涵盖 PVTT 数据集构建Pipeline（视频预处理、分割、修复、合成、质量过滤），保留供参考。内容包括：

1. 视频预处理与场景分割（PySceneDetect, TransNetV2, AutoShot）
2. 视频对象分割（SAM2, Grounded-SAM2）
3. 视频修复与背景恢复（VideoPainter, ProPainter）
4. 视频对象合成（VideoAnyDoor, InsertAnywhere, GenCompositor）
5. 数据质量评估与过滤（CLIP-I, DINO-I, MUSIQ, DOVER, VBench）
6. 电商视频数据集（VACE, InsViE-1M, OpenVE-3M, VIVID-10M）
7. 推荐Pipeline配置

完整技术调研详见本 README 的 git 历史版本（2026-03-14 之前的版本）。

---

*文档版本：2.0（2026-03-14）*
*上一版本：1.0（2026-02-11）— 完整技术调研*
