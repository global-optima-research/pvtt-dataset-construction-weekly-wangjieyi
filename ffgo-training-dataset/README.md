# FFGO Training Dataset

> **PVTT 项目** — Wan2.2 TI2V 5B + FFGO LoRA 微调训练数据集
> 200 个候选样本，目标精选 150 个

## 数据集结构

```
ffgo-training-dataset/
├── scripts/                    # 处理脚本
│   ├── step1_fix_first_frame_raw.py    # ✅ 已执行 - 去除padding
│   ├── step2_product_extraction.py     # GPU服务器运行 - GroundingDINO+SAM2
│   ├── step3_gemini_caption.py         # 本地运行 - Gemini API生成caption
│   ├── step4_gemini_background.py      # 本地运行 - Gemini API移除产品
│   ├── step5_compose_first_frame.py    # 本地运行 - 拼合首帧
│   └── step6_validate.py              # 验证数据完整性
├── sample_000/
│   ├── video.mp4               # ✅ 832×480, 81帧, 16fps, H.264
│   ├── first_frame_raw.png     # ✅ 有效内容区域（已去padding）
│   ├── metadata.json           # ✅ 元信息
│   ├── product_rgba.png        # ⬜ 待生成 - Step 2
│   ├── product_mask.png        # ⬜ 待生成 - Step 2
│   ├── background.png          # ⬜ 待生成 - Step 4
│   ├── caption.txt             # ⬜ 待生成 - Step 3
│   └── first_frame.png         # ⬜ 待生成 - Step 5
├── sample_001/
│   └── ...
└── sample_199/
    └── ...
```

## 执行步骤

### Step 1: 首帧去 padding ✅ 已完成

```bash
python scripts/step1_fix_first_frame_raw.py
```

### Step 2: 产品提取（需要 GPU 服务器）

在服务器上安装 GroundingDINO + SAM2，然后运行：
```bash
# 服务器: 111.17.197.107
conda activate datapipeline
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install groundingdino-py segment-anything-2

python step2_product_extraction.py
```

**fallback**: 如果 GroundingDINO 安装失败，脚本会自动用 `rembg` 作为替代方案。

### Step 3: Caption 生成（需要 Gemini API）

```bash
# 本地运行，需要网络
python scripts/step3_gemini_caption.py
```

- 使用 Gemini 2.5 Flash（免费额度 10次/分钟）
- 预计耗时：~20 分钟
- 自动跳过已生成的 caption

### Step 4: 背景提取（需要 Gemini API）⚠️ 卡点

```bash
python scripts/step4_gemini_background.py
```

- 使用 Gemini 的图像编辑能力移除产品
- 预计耗时：~20 分钟
- **如果 Gemini 效果不好**，可在服务器上试 LaMa：
  ```bash
  pip install simple-lama-inpainting
  # 然后修改 step4 脚本使用 LaMa
  ```

### Step 5: 首帧拼合

```bash
python scripts/step5_compose_first_frame.py
```

- 需要 product_rgba.png + background.png 都就绪
- 白色画布 832×480，左 1/3 产品，右 2/3 背景

### Step 6: 验证

```bash
python scripts/step6_validate.py
```

## Gemini API 使用

```python
# 安装
pip install google-genai

# API Key（免费额度）
# Key: AIzaSyBqeyc9S84WlBzzbPxg1QS3iaay3u8CBxA
# 获取新 key: https://aistudio.google.com/apikey

# 免费额度限制:
#   gemini-2.5-pro:   5 RPM
#   gemini-2.5-flash: 10 RPM (推荐，速度快)
```

## 数据规格

| 文件 | 格式 | 分辨率 | 说明 |
|------|------|--------|------|
| video.mp4 | H.264, 16fps, CRF18 | 832×480 | 训练目标视频 |
| first_frame_raw.png | RGB PNG | 有效内容区域 | 原始首帧（无 padding） |
| product_rgba.png | RGBA PNG | 有效内容区域 | 产品透明背景抠图 |
| product_mask.png | 灰度 PNG | 有效内容区域 | 255=产品, 0=背景 |
| background.png | RGB PNG | 有效内容区域 | 移除产品后的背景 |
| caption.txt | UTF-8 | - | "ad23r2 the camera view suddenly changes " + 描述 |
| first_frame.png | RGB PNG | 832×480 | 白色画布拼合图 |
| metadata.json | JSON | - | 元信息 |

## 数据来源

200 个样本从 PVTT 数据集（6639 个视频）中筛选：
- Amazon: 98 个, Shopify: 102 个
- 8 品类均匀分布（bracelet/earring/handbag/necklace/ring/sunglasses/watch/cosmetics 各 25 个）

详细计划见：`D:/00_aPhD/IP/dataset_construction_plan.md`
