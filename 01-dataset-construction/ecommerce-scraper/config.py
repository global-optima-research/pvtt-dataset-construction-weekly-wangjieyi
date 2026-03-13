"""
电商平台媒体采集配置文件
使用前请填写你的 API Keys
"""

# ============================================
# API Keys - 从各平台控制台获取后填入
# ============================================
TMAPI_TOKEN = ""           # tmapi.top -> console.tmapi.io (set via environment variable or .env)

APIFY_TOKEN = ""           # apify.com -> Settings -> Integrations (set via environment variable or .env)

SCRAPECREATORS_KEY = ""         # app.scrapecreators.com (set via environment variable or .env)

# ============================================
# 采集目标品类关键词
# ============================================
CATEGORIES = {
    "手表":    {"zh": "手表 腕表",          "en": "watch wristwatch"},
    "珠宝":    {"zh": "珠宝 项链 戒指",      "en": "jewelry necklace ring"},
    "箱包":    {"zh": "手提包 单肩包",        "en": "handbag shoulder bag"},
    "化妆品":  {"zh": "口红 粉底 眼影",       "en": "lipstick foundation eyeshadow"},
}

# ============================================
# 每品类每平台目标采集数量
# ============================================
TARGET_PER_CATEGORY_PER_PLATFORM = 500   # 4品类 × 5平台 × 500 = 10000条

# ============================================
# 文件存储路径
# ============================================
OUTPUT_BASE = "./data"    # 本地存储根目录

# ============================================
# 并发控制（避免触发限流）
# ============================================
MAX_CONCURRENT_REQUESTS = 5
DELAY_BETWEEN_REQUESTS = 1.0   # 秒
