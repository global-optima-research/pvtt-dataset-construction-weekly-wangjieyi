# TikTok Shop Pipeline

> PVTT 数据采集 — TikTok Shop 数据收集

## 平台概览

| 字段 | 详情 |
|------|------|
| **平台** | TikTok Shop |
| **状态** | 计划中 |
| **采集方式** | Apify TikTok Shop Scraper（第三方服务） |
| **优先级** | P1（低成本，高视频覆盖率） |
| **预估成本** | ~$2/1000 产品（Apify 免费额度可覆盖 ~2500 产品） |

## 采集方式

### 首选：Apify TikTok Shop Scraper

- **服务**：[Apify TikTok Shop Scraper](https://apify.com/store)
- **定价**：$2/1000 条结果（按量付费）或 $20/月包月
- **替代方案**：sovereigntaylor 版本，$1.80/1000 产品
- **免费额度**：$5/月（约 2500 产品）
- **数据字段**：标题、价格、折扣、销量、评分、图片、规格、卖家信息

### 替代方案

1. **TikTok Research API**（学术通道）
   - 美国/欧盟非营利高校免费
   - 需要导师推荐信
   - 支持查询 TikTok Shop 产品和店铺信息
   - 申请地址：https://developers.tiktok.com/products/research-api/
   - 注意：有研究者反映数据交付不完整/不一致（SAGE 2025）

2. **Bright Data TikTok Scraper**：$2.50/1000 请求（更稳定，内置反爬绕过）

3. **直接爬取**（不推荐）
   - 加密请求头需要逆向工程
   - 实时反欺诈评分系统检测自动化
   - 必须使用美国住宅代理
   - 签名算法频繁更新

## 反爬机制

| 机制 | 严重程度 | 说明 |
|------|----------|------|
| 加密请求头 | 高 | 自定义加密，需逆向工程 |
| 行为检测 | 高 | 实时反欺诈评分 |
| IP 限制 | 高 | 数据中心 IP 被封，需美国住宅代理 |
| 地区限制 | 中 | TikTok Shop 美国站需美国 IP |

**结论**：自行爬取不可行。推荐使用 Apify 或 Bright Data。

## 数据格式

输出必须符合 PVTT 统一数据格式：

```
tiktok_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # 产品元数据
    media/
      images/
        {PRODUCT_ID}_01.jpg
        {PRODUCT_ID}_02.jpg
        ...
      videos/
        {PRODUCT_ID}.mp4
```

### 元数据 JSON

```json
{
  "product_id": "TT_XXXXXXXX",
  "platform": "tiktok",
  "title": "Product Title",
  "category": "bracelet",
  "price": "19.99",
  "currency": "USD",
  "brand": "Seller Name",
  "rating": 4.7,
  "review_count": 456,
  "url": "https://shop.tiktok.com/...",
  "images": ["media/images/TT_XXXXXXXX_01.jpg"],
  "videos": ["media/videos/TT_XXXXXXXX.mp4"],
  "has_video": true,
  "scrape_date": "2026-03-14",
  "metadata": {
    "sold_count": 1200,
    "discount_percentage": 30,
    "shop_name": "Shop Name",
    "shop_rating": 4.8
  }
}
```

## 预估数据量

| 品类 | 预估产品数 | 预估视频数 | 备注 |
|------|-----------|-----------|------|
| bracelet | 50+ | 45+ | TikTok Shop 热门品类 |
| earring | 50+ | 45+ | 互动率高 |
| handbag | 40+ | 35+ | 时尚品类 |
| necklace | 50+ | 45+ | 热门品类 |
| ring | 40+ | 35+ | 增长中品类 |
| sunglasses | 40+ | 35+ | 有季节性高峰 |
| watch | 30+ | 25+ | 中等体量 |
| **合计** | **300+** | **265+** | |

**视频覆盖率**：~90%+（TikTok 是原生视频平台）
**视频质量**：720p-1080p，短视频风格（9:16 竖屏）
**视频时长**：15-60 秒

## 重要说明

- TikTok 视频以 **竖屏（9:16）** 为主 -- 用于 PVTT 需要后期裁剪/缩放处理
- 视频风格偏向达人带货/种草内容，而非传统产品展示
- 珠宝是 TikTok Shop 热门品类（2025 年 GMV 达 $1.2B，同比增长 94%）
- 2026 年更新：美国 TikTok 运营已转交 USDS 合资企业（Oracle 管理），数据访问政策可能变化

## 法律合规

- 在美国，公开数据爬取通常合法（hiQ v. LinkedIn 判例）
- TikTok 服务条款禁止未授权的自动化访问
- 使用 Apify（第三方服务）降低直接法律风险
- 学术研究目的提供额外保护
- 建议申请 TikTok Research API 以确保完全合规

## 下一步计划

1. 注册 Apify 免费账号
2. 使用免费额度测试 TikTok Shop Scraper（50-100 产品）
3. 验证视频质量和与 PVTT 的相关性
4. 如测试成功，扩展至 300+ 产品覆盖所有品类
5. 开发竖屏转横屏的后处理脚本
