# eBay Pipeline

> PVTT 数据采集 — eBay 数据收集

## 平台概览

| 字段 | 详情 |
|------|------|
| **平台** | eBay |
| **状态** | 计划中 |
| **采集方式** | eBay Browse API（官方，免费） |
| **优先级** | P1（免费 API，可立即使用） |
| **预估成本** | $0（完全免费的 API） |

## 采集方式

### 首选：eBay Browse API

- **文档**：https://developer.ebay.com/api-docs/buy/browse/overview.html
- **成本**：完全免费
- **注册**：免费注册 eBay Developer Program 账号
- **认证**：OAuth 2.0（Client Credentials Grant，用于公开数据）
- **速率限制**：
  - 默认：5,000 请求/天
  - 通过 Application Growth Check（免费）后：最高 150 万请求/天
  - 无明确 QPS 限制（但需保持合理间隔）

### 主要 API 端点

| 端点 | 用途 | 说明 |
|------|------|------|
| `search` | 按关键词/品类搜索商品 | 主要发现端点 |
| `searchByImage` | 以图搜图 | 查找相似产品 |
| `getItem` | 获取商品详情 | 完整产品信息 |
| `getItemsByItemGroup` | 获取商品变体 | 分组商品 |

### API 可获取的数据

- 标题、描述、价格、品类、商品状态
- 图片：`imageUrl` 含 `height`/`width`（完整分辨率）
- 卖家信息、评分、评价数
- 商品属性（品牌、材质等）
- 使用 `fieldGroups` 参数（COMPACT/PRODUCT）控制响应详细程度

### 视频限制

- Browse API **不直接返回视频 URL**
- 视频需从商品描述 HTML 中解析
- eBay Media API 存在，但主要用于 **卖家端** 上传/管理，非买家端批量下载
- 变通方案：解析 `getItem` 的 description 字段中嵌入的视频元素

### 替代方案

- **curl_cffi**：可从网页直接获取部分数据
- **Playwright**：搜索结果页面需要（JS 渲染）
- **Bright Data**：$1.50/1000 请求（有免费 API 则无需使用）

## 反爬机制

| 机制 | 严重程度 | 说明 |
|------|----------|------|
| JavaScript 渲染 | 中 | 搜索页面需要 JS 执行 |
| 速率限制 | 低 | 高频访问会被临时封禁 |
| CAPTCHA | 无 | 没有强验证码（无 Datadome/Akamai） |

**结论**：eBay 反爬较弱。官方 Browse API 是最佳方案 -- 免费、稳定、完全受支持。

## 数据格式

输出必须符合 PVTT 统一数据格式：

```
ebay_data/
  {category}/                        # bracelet, earring, handbag, necklace, ring, sunglasses, watch
    {PRODUCT_ID}.json                # 产品元数据
    media/
      images/
        {PRODUCT_ID}_01.jpg
        {PRODUCT_ID}_02.jpg
        ...
      videos/
        {PRODUCT_ID}.mp4             # 如有（珠宝类较少见）
```

### 元数据 JSON

```json
{
  "product_id": "EBAY_XXXXXXXXXXXX",
  "platform": "ebay",
  "title": "Product Title",
  "category": "bracelet",
  "price": "34.99",
  "currency": "USD",
  "brand": "Brand Name",
  "rating": null,
  "review_count": null,
  "url": "https://www.ebay.com/itm/XXXXXXXXXXXX",
  "images": ["media/images/EBAY_XXXXXXXXXXXX_01.jpg"],
  "videos": [],
  "has_video": false,
  "scrape_date": "2026-03-14",
  "metadata": {
    "condition": "New",
    "seller": "seller_username",
    "seller_feedback_score": 9876,
    "item_specifics": {
      "Material": "Sterling Silver",
      "Style": "Chain"
    }
  }
}
```

## 预估数据量

| 品类 | 预估产品数 | 预估视频数 | 备注 |
|------|-----------|-----------|------|
| bracelet | 30+ | 3-5 | 珠宝类视频率低 |
| earring | 30+ | 2-4 | 多为个人卖家 |
| handbag | 30+ | 5-8 | 视频略多 |
| necklace | 30+ | 3-5 | |
| ring | 30+ | 2-4 | |
| sunglasses | 25+ | 3-5 | 品牌商品可能有视频 |
| watch | 25+ | 5-8 | 手表卖家更倾向添加视频 |
| **合计** | **200+** | **23-39** | |

**视频覆盖率**：整体 ~10-20%，珠宝类 ~5-10%
**视频质量**：不一（卖家上传，非标准化）
**图片质量**：中等（卖家上传，一致性差）

## 重要说明

- eBay 珠宝商品以 **二手/古董/收藏品** 为主 -- 与 Amazon 新品零售不同
- 珠宝品类视频率很低
- **主要价值在于作为图片数据补充**，而非视频来源
- 图片质量在不同卖家之间差异显著
- Browse API 是性价比最高的切入点（完全免费）
- 5,000 请求/天足以采集数百个产品；通过 Growth Check 可提升至 150 万/天

## 法律合规

- eBay API License Agreement 明确允许开发者通过 API 访问数据
- API 使用 **完全合规**
- 直接网页爬取应遵守 robots.txt
- 学术研究用途法律风险极低
- 需遵守数据保护法规（欧盟商品需符合 GDPR）

## 下一步计划

1. 注册 eBay Developer Program 账号（免费）：https://developer.ebay.com/
2. 创建应用并获取 API 密钥
3. 申请 Application Growth Check（免费）以提升速率限制
4. 构建面向珠宝品类的 Browse API 客户端
5. 实现符合统一数据格式的图片下载Pipeline
6. 解析商品描述中嵌入的视频（如有）
