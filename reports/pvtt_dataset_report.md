# PVTT 数据集报告

**Product Video Template Transfer** — 多平台采集数据 — 2026-03-21

## 数据概览

| 指标 | Amazon | Shopify | 合计 |
|------|--------|---------|------|
| 产品数 | 865 | 1,477 | 2,342 |
| 视频数 | 863 | 133 | 996 |
| 图片数 | 4,926 | 7,296 | 12,222 |
| 总大小 | 5,530 MB | 1,392 MB | 6,922 MB |
| 类别数 | 7 | 6 | 7 |

## 数据来源

### Amazon (主数据源)
- 爬虫: `scripts/amazon_spider.py` (需本地运行，住宅IP)
- 7 类别, 865 产品, 863 视频
- 服务器已标准化处理: 5,258 片段 (1280x720, 24fps, H.264)

### Shopify 独立站 (第二数据源)
- 爬虫: `scripts/shopify_spider.py`
- 4 个店铺:

| 店铺 | 产品数 | 类别 | 视频 |
|------|--------|------|------|
| gorjana.com | 587 | bracelet, earring, necklace, ring, handbag | 27 |
| missoma.com | 446 | bracelet, earring, necklace, ring | 33 |
| goodr.com | 297 | sunglasses, earring, ring | 0 |
| dagnedover.com | 146 | handbag, necklace, ring | 0 |

## 各类别统计

### Amazon

| 类别 | 产品数 | 图片数 | 视频数 |
|------|--------|--------|--------|
| Bracelet | 168 | 864 | 165 |
| Earring | 157 | 973 | 144 |
| Handbag | 131 | 739 | 198 |
| Necklace | 149 | 924 | 130 |
| Ring | 62 | 436 | 62 |
| Sunglasses | 64 | 376 | 103 |
| Watch | 134 | 614 | 61 |
| **合计** | **865** | **4,926** | **863** |

### Shopify

| 类别 | 产品数 | 图片数 | 视频数 |
|------|--------|--------|--------|
| Bracelet | 98 | 511 | 11 |
| Earring | 392 | 1,903 | 53 |
| Handbag | 133 | 819 | 0 |
| Necklace | 462 | 2,108 | 61 |
| Ring | 116 | 575 | 8 |
| Sunglasses | 276 | 1,380 | 0 |
| **合计** | **1,477** | **7,296** | **133** |

## 视频统计 (Amazon, 服务器标准化后)

| 指标 | 数值 |
|------|------|
| 原始视频 | 863 |
| 标准化片段 | 5,258 |
| 标准化大小 | 3.4 GB |
| 标准化规格 | 1280x720, 24fps, H.264 |
| 平均时长 | 33.0s |
| 时长范围 | 5.2s – 267.0s |

## 样本展示

### Bracelet

**Highergo 469 Pcs Bangles Bracelet Making Kit Link Chain Bracelet Charms with OT Toggle Clasp DIY**
- ASIN: `B08ZS4QK5Y` | Price: 19,240 | Keyword: _charm bracelet_
- Media: 8 images, 6 videos
- ![B08ZS4QK5Y](amazon_data/bracelet/media/images/B08ZS4QK5Y_00.jpg) ![B08ZS4QK5Y](amazon_data/bracelet/media/images/B08ZS4QK5Y_01.jpg) ![B08ZS4QK5Y](amazon_data/bracelet/media/images/B08ZS4QK5Y_02.jpg)
- Video: [B08ZS4QK5Y.mp4](amazon_data/bracelet/media/videos/B08ZS4QK5Y.mp4) (30.1s, 5.3MB)
- Video: [B08ZS4QK5Y_v01.mp4](amazon_data/bracelet/media/videos/B08ZS4QK5Y_v01.mp4) (75.5s, 20.7MB)

**PAVOI 14K Gold Plated 3mm Cubic Zirconia Classic Tennis Bracelet | Gold Bracelets for Women | Size 6.5-7.5 Inch**
- ASIN: `B07TBN9JRJ` | Price: 29,748 | Keyword: _tennis bracelet_
- Media: 8 images, 5 videos
- ![B07TBN9JRJ](amazon_data/bracelet/media/images/B07TBN9JRJ_00.jpg) ![B07TBN9JRJ](amazon_data/bracelet/media/images/B07TBN9JRJ_01.jpg) ![B07TBN9JRJ](amazon_data/bracelet/media/images/B07TBN9JRJ_02.jpg)
- Video: [B07TBN9JRJ.mp4](amazon_data/bracelet/media/videos/B07TBN9JRJ.mp4) (28.6s, 6.2MB)
- Video: [B07TBN9JRJ_v01.mp4](amazon_data/bracelet/media/videos/B07TBN9JRJ_v01.mp4) (16.1s, 3.4MB)

### Earring

**Big Simulated Pearl Earrings for Women - Oversized Classic Faux Round Large Ear Studs, Hypoallergenic and Safe for Sensitive Ears**
- ASIN: `B07GNT1PPH` | Price: 25,185 | Keyword: _pearl earrings_
- Media: 8 images, 5 videos
- ![B07GNT1PPH](amazon_data/earring/media/images/B07GNT1PPH_00.jpg) ![B07GNT1PPH](amazon_data/earring/media/images/B07GNT1PPH_01.jpg) ![B07GNT1PPH](amazon_data/earring/media/images/B07GNT1PPH_02.jpg)
- Video: [B07GNT1PPH.mp4](amazon_data/earring/media/videos/B07GNT1PPH.mp4) (17.5s, 1.9MB)
- Video: [B07GNT1PPH_v01.mp4](amazon_data/earring/media/videos/B07GNT1PPH_v01.mp4) (17.8s, 2.1MB)

### Handbag

**LOVEVOOK Laptop Tote Bag for Women, 15.6 Inch Large Capacity Vintage Leather Work Computer Bag, Business Casual Shoulder Handbag, Dark Brown**
- ASIN: `B0BYS7VHMN` | Price: 59,458 | Keyword: _women tote handbag_
- Media: 8 images, 7 videos
- ![B0BYS7VHMN](amazon_data/handbag/media/images/B0BYS7VHMN_00.jpg) ![B0BYS7VHMN](amazon_data/handbag/media/images/B0BYS7VHMN_01.jpg) ![B0BYS7VHMN](amazon_data/handbag/media/images/B0BYS7VHMN_02.jpg)
- Video: [B0BYS7VHMN.mp4](amazon_data/handbag/media/videos/B0BYS7VHMN.mp4) (28.2s, 4.8MB)

### Necklace

**BERISO 14K Gold/Silver Plated Choker Necklace for Women Shining Dots Station Gold Chain Necklace Beads Sparkle Chain Necklace Link Chain Exquisite Jewelry for women**
- ASIN: `B09YR3194D` | Price: 19,370 | Keyword: _choker necklace_
- Media: 8 images, 5 videos
- ![B09YR3194D](amazon_data/necklace/media/images/B09YR3194D_00.jpg) ![B09YR3194D](amazon_data/necklace/media/images/B09YR3194D_01.jpg) ![B09YR3194D](amazon_data/necklace/media/images/B09YR3194D_02.jpg)
- Video: [B09YR3194D.mp4](amazon_data/necklace/media/videos/B09YR3194D.mp4) (75.8s, 17.9MB)

### Ring

**925 Sterling Silver Shiny Full Diamond Ring Cubic Zirconia Cocktail Rings CZ Eternity Engagement Wedding Band Ring for Women (US Code 7)**
- ASIN: `B098KWTXDJ` | Price: 22,044 | Keyword: _engagement ring_
- Media: 8 images, 4 videos
- ![B098KWTXDJ](amazon_data/ring/media/images/B098KWTXDJ_00.jpg) ![B098KWTXDJ](amazon_data/ring/media/images/B098KWTXDJ_01.jpg) ![B098KWTXDJ](amazon_data/ring/media/images/B098KWTXDJ_02.jpg)
- Video: [B098KWTXDJ.mp4](amazon_data/ring/media/videos/B098KWTXDJ.mp4) (18.4s, 1.7MB)

### Sunglasses

**Polarized Sports Sunglasses for Men Women Unbreakable Frame Cycling Fishing Wrap Around Sunglasses UV400 Protection**
- ASIN: `B0C13T4WVL` | Price: 28,133 | Keyword: _polarized sunglasses_
- Media: 8 images, 9 videos
- ![B0C13T4WVL](amazon_data/sunglasses/media/images/B0C13T4WVL_00.jpg) ![B0C13T4WVL](amazon_data/sunglasses/media/images/B0C13T4WVL_01.jpg) ![B0C13T4WVL](amazon_data/sunglasses/media/images/B0C13T4WVL_02.jpg)
- Video: [B0C13T4WVL.mp4](amazon_data/sunglasses/media/videos/B0C13T4WVL.mp4) (96.6s, 21.3MB)

### Watch

**Mens Digital Watch Sports Military Watches Waterproof Outdoor Chronograph Wrist Watches for Men with LED Back Ligh/Alarm/Date**
- ASIN: `B089NGH82D` | Price: 22,733 | Keyword: _sport digital watch_
- Media: 8 images, 3 videos
- ![B089NGH82D](amazon_data/watch/media/images/B089NGH82D_00.jpg) ![B089NGH82D](amazon_data/watch/media/images/B089NGH82D_01.jpg) ![B089NGH82D](amazon_data/watch/media/images/B089NGH82D_02.jpg)
- Video: [B089NGH82D.mp4](amazon_data/watch/media/videos/B089NGH82D.mp4) (37.9s, 4.8MB)

## 目录结构

```
amazon_data/                    # Amazon 主数据源 (5.5 GB)
  bracelet/   168 products, 864 images, 165 videos
  earring/    157 products, 973 images, 144 videos
  handbag/    131 products, 739 images, 198 videos
  necklace/   149 products, 924 images, 130 videos
  ring/        62 products, 436 images,  62 videos
  sunglasses/  64 products, 376 images, 103 videos
  watch/      134 products, 614 images,  61 videos

shopify_data/                   # Shopify 独立站 (1.4 GB)
  bracelet/    98 products, 511 images, 11 videos
  earring/    392 products, 1903 images, 53 videos
  handbag/    133 products, 819 images,  0 videos
  necklace/   462 products, 2108 images, 61 videos
  ring/       116 products, 575 images,  8 videos
  sunglasses/ 276 products, 1380 images, 0 videos
  store_discovery.json
```

## 放弃的平台

| 平台 | 原因 |
|------|------|
| Etsy | Datadome CAPTCHA 封锁 |
| AliExpress | Akamai slider CAPTCHA 封锁 |
| eBay | Browse API 免费但视频率低 |
| TikTok Shop | API 限制 |
| 淘宝 | 需第三方服务 (¥100-250) |
| 小红书 | 法律风险高 |
| 8个Shopify店 | API不可用或无视频 |

详见 `reports/platform_analysis_report.md`

---
*PVTT 数据集报告 — Product Video Template Transfer (CVPR 2027)*
