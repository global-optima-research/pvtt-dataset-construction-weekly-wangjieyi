# PVTT 数据采集 — 目录结构规划

> 状态：已规划（尚未重组）
> 日期：2026-03-14
> 注意：Amazon 爬虫运行期间请勿重组目录。

## 当前结构（截至 2026-03-14）

```
01-dataset-construction/
  README.md                          # 项目概述和Pipeline文档
  DIRECTORY_STRUCTURE.md             # 本文件（目录重组规划）

  # 运行中的爬虫和数据（请勿移动）
  amazon_spider.py                   # Amazon 产品爬虫（运行中）
  amazon_data/                       # Amazon 采集数据（运行中，爬虫正在写入）

  # 平台爬虫
  etsy_spider.py                     # Etsy 爬虫（被 Datadome 阻断）
  etsy_data/                         # Etsy 数据（少量，已阻断）

  # 工具脚本
  pvtt_pipeline.py                   # 主Pipeline编排器
  upload_to_server.py                # 上传数据至服务器
  generate_dataset_report.py         # 报告生成器
  generate_charts.py                 # 图表生成器
  build_notebook.py                  # Notebook/报告构建器

  # 报告
  platform_analysis_report.md        # 多平台分析报告（12 个平台）
  pvtt_dataset_report.html           # 数据集报告（HTML）
  pvtt_dataset_report.md             # 数据集报告（Markdown）

  # 服务器
  server-scripts/                    # 服务器端处理脚本

  # 历史遗留
  ecommerce-scraper/                 # 旧版Pipeline（已弃用）
  data_pipeline.py                   # 旧版/重复Pipeline脚本
  launch_spider.py                   # 旧版爬虫启动器
  __pycache__/                       # Python 缓存
```

## 规划结构（重组后）

```
01-dataset-construction/
  README.md                          # 更新后的项目概述
  DIRECTORY_STRUCTURE.md             # 本文件

  pipelines/                         # 各平台采集Pipeline
    amazon/
      amazon_spider.py               # Amazon 产品爬虫
      README.md                      # Amazon Pipeline 文档
    etsy/
      etsy_spider.py                 # Etsy 爬虫（被 Datadome 阻断）
      README.md                      # Etsy Pipeline 文档
    tiktok/
      README.md                      # TikTok Shop Pipeline（计划中，Apify）
    ebay/
      README.md                      # eBay Pipeline（计划中，Browse API）
    taobao/
      README.md                      # 淘宝 Pipeline（计划中，第三方服务）

  data/                              # 所有采集数据
    amazon/                          # Amazon 数据（从 amazon_data/ 迁移）
    etsy/                            # Etsy 数据（从 etsy_data/ 迁移）
    tiktok/                          # TikTok Shop 数据（计划中）
    ebay/                            # eBay 数据（计划中）
    taobao/                          # 淘宝数据（计划中）

  tools/                             # 共享Pipeline工具
    pvtt_pipeline.py                 # 主编排器
    upload_to_server.py              # 服务器上传工具
    generate_dataset_report.py       # 报告生成器
    generate_charts.py               # 图表生成器
    build_notebook.py                # Notebook 构建器

  reports/                           # 所有生成的报告
    platform_analysis_report.md      # 平台分析报告
    pvtt_dataset_report.html         # 数据集报告（HTML）
    pvtt_dataset_report.md           # 数据集报告（Markdown）

  server-scripts/                    # 服务器端脚本（不变）

  _archive/                          # 已弃用的文件
    ecommerce-scraper/               # 旧版Pipeline
    data_pipeline.py                 # 旧版重复Pipeline
    launch_spider.py                 # 旧版启动器
```

## 统一数据格式

所有平台Pipeline应按以下统一格式输出数据：

```
{platform}_data/
  {category}/                        # 如：bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # 产品元数据（JSON）
    media/
      images/
        {PRODUCT_ID}_01.jpg          # 产品图片 1
        {PRODUCT_ID}_02.jpg          # 产品图片 2
        ...
      videos/
        {PRODUCT_ID}.mp4             # 产品视频
```

### 元数据 JSON Schema

每个 `{PRODUCT_ID}.json` 应包含以下字段：

```json
{
  "product_id": "B0XXXXXX",
  "platform": "amazon",
  "title": "Product Title",
  "category": "bracelet",
  "price": "29.99",
  "currency": "USD",
  "brand": "Brand Name",
  "rating": 4.5,
  "review_count": 123,
  "url": "https://www.amazon.com/dp/B0XXXXXX",
  "images": [
    "media/images/B0XXXXXX_01.jpg",
    "media/images/B0XXXXXX_02.jpg"
  ],
  "videos": [
    "media/videos/B0XXXXXX.mp4"
  ],
  "has_video": true,
  "scrape_date": "2026-03-14",
  "metadata": {}
}
```

## 迁移步骤

当 Amazon 爬虫运行结束后：

1. 创建新的目录结构（`pipelines/`、`data/`、`tools/`、`reports/`、`_archive/`）
2. 将 `amazon_spider.py` 移至 `pipelines/amazon/`
3. 将 `amazon_data/` 移至 `data/amazon/`
4. 将 `etsy_spider.py` 移至 `pipelines/etsy/`
5. 将 `etsy_data/` 移至 `data/etsy/`
6. 将工具脚本移至 `tools/`
7. 将报告文件移至 `reports/`
8. 将已弃用文件移至 `_archive/`
9. 更新所有脚本中的 import 路径和文件引用
10. 更新 `pvtt_pipeline.py` 中的路径
11. 测试所有脚本在新路径下是否正常工作
12. 删除 `__pycache__/`

## 各平台Pipeline状态

| 平台 | 状态 | 采集方式 | Pipeline文件 | 数据目录 |
|------|------|----------|-------------|----------|
| Amazon | **进行中** | 自研爬虫（requests + 住宅IP） | `amazon_spider.py` | `amazon_data/` |
| Etsy | **已阻断** | 被 Datadome CAPTCHA 阻断 | `etsy_spider.py` | `etsy_data/` |
| TikTok Shop | **计划中** | Apify TikTok Shop Scraper ($2/1K) | - | - |
| eBay | **计划中** | eBay Browse API（免费） | - | - |
| 淘宝 | **计划中** | 第三方数据服务 | - | - |
