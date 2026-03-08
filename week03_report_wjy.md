# PVTT 周报 - 第三周 (2026-03-08)

**项目：** Product Video Template Transfer (PVTT)
**负责人：** 王洁怡 (wangjieyi)
**周期：** 2026-03-02 ~ 2026-03-08

---

## 一、数据采集 Pipeline 现状

### 1.1 Pipeline 架构

已搭建并端到端测试通过的四阶段自动化流水线：

| 阶段 | 脚本 | 说明 |
|------|------|------|
| 阶段1：爬取（本地） | `amazon_spider.py` | 搜索 + 爬取 Amazon 产品页 |
| 阶段2：上传 | `data_pipeline.py` | SFTP 同步本地数据至 GPU 服务器 |
| 阶段3：处理（服务器） | `pvtt_pipeline.py` | 镜头检测 + 视频标准化 |
| 阶段4：报告 | `generate_report.py` | 生成 HTML 质量报告（含缩略图） |

- 爬取阶段在本地运行（需要住宅 IP 以绕过 Amazon 反爬检测）。
- 服务器处理阶段通过 SSH/paramiko 在 RTX-5090-x8 集群上执行。
- Pipeline 支持增量执行：已爬取的产品会自动跳过。

### 1.2 爬取配置

| 参数 | 值 |
|------|------|
| 数据来源平台 | Amazon (amazon.com) |
| 目标类别 | 7 类（necklace, bracelet, earring, watch, sunglasses, handbag, ring） |
| 每类关键词数 | 3 |
| 每关键词最大产品数 | 20 |
| 目标规模 | 420 个产品 |
| 媒体提取 | 产品图片（每产品最多 8 张）+ HLS 视频流 |

### 1.3 当前爬取进度

批量爬取于 2026-03-08 启动，目前仍在进行中。

| 类别 | 产品数 | 图片数 | 视频数 | 数据量 | 状态 |
|------|--------|--------|--------|--------|------|
| necklace | 61 | 364 | 51 | 215 MB | **已完成**（3/3 关键词） |
| bracelet | 60 | 192 | 33 | 261 MB | **已完成**（3/3 关键词） |
| earring | 62 | 216 | 41 | 223 MB | **已完成**（3/3 关键词） |
| watch | 48 | 64 | 6 | 65 MB | 进行中（第3个关键词） |
| sunglasses | 5 | 32 | 1 | 8 MB | 待续（仅完成 1/3 测试轮） |
| handbag | 0 | 0 | 0 | — | 未开始 |
| ring | 0 | 0 | 0 | — | 未开始 |
| **合计** | **236** | **868** | **132** | **~770 MB** | |

---

## 二、数据质量指标

### 2.1 视频统计

| 指标 | 值 |
|------|------|
| 已采集视频总数 | 132 |
| 含视频的产品比例 | 约 52% |
| 视频格式 | MP4（HLS 流转封装） |
| 视频大小范围 | 0.68 ~ 24.07 MB |
| 平均视频大小 | 约 4.5 MB |
| 目标分辨率 | 720p（HLS 最高可用质量） |

### 2.2 图片统计

| 指标 | 值 |
|------|------|
| 已采集图片总数 | 868 |
| 平均每产品图片数 | 约 6.2 张 |
| 每产品图片上限 | 8 张 |
| 图片格式 | JPEG |
| 平均图片大小 | 约 10.9 KB |

### 2.3 已知问题

1. **图片分辨率偏低** —— 部分图片为中等分辨率缩略图（约 10 KB）。从 Amazon 页面 `colorImages` JSON 提取 `hiRes` URL 的方法对部分产品有效，但当 Amazon 返回 CAPTCHA 页面时会失败（约 30% 产品提取到 0 张图片）。
2. **HLS DRM 加密视频** —— 少量 watch 类别视频存在 DRM 加密，无法下载。
3. **频率限制** —— 持续爬取后 Amazon 返回 HTTP 500/503，导致部分产品无法提取媒体。爬虫使用 UA 轮换和退避策略，但未使用代理。

### 2.4 服务器端处理（评估数据集）

在本次爬取之前，服务器端 Pipeline 已在 PVTT 评估数据集上验证通过：

| 指标 | 值 |
|------|------|
| 原始视频数 | 53 |
| 镜头分割后片段数 | 87 |
| 标准化片段数 | 87（1280x720, 24fps, H.264） |
| 时长范围 | 1.1s ~ 8.8s（平均 3.8s） |
| 覆盖类别 | 8 类（bracelet, earring, handbag, handfan, necklace, purse, sunglasses, watch） |

---

## 三、下一步计划

### P0 — 本周待完成

- [ ] 完成剩余类别的批量爬取（watch, sunglasses, handbag, ring）
- [ ] 将所有爬取数据上传至 GPU 服务器（`python data_pipeline.py upload`）
- [ ] 在服务器上运行标准化处理（`python data_pipeline.py process`）
- [ ] 生成最终 HTML 质量报告并推送至 GitHub

### P1 — 下一阶段

- [ ] **修复高清图片提取** —— 调查 Amazon 当前 `colorImages` 结构，改进正则匹配
- [ ] **多平台 API 调研** —— 评估 Pexels API、Pixabay API、Shopify 产品源等补充数据来源
- [ ] **扩大规模至 1000+ 产品** —— 添加代理轮换或无头浏览器（Playwright）以绕过限流
- [ ] **启动视频质量过滤** —— 在服务器上实现自动化质量检查（分辨率、时长、运动评分）

### P2 — 待排期

- [ ] 集成 TransNetV2 实现更精确的镜头边界检测
- [ ] 搭建 Grounded-SAM2 管线用于产品分割
- [ ] 设计交叉配对策略（模板视频 x 产品图像）生成训练数据

---

## 四、关键文件索引

| 文件 | 说明 |
|------|------|
| `01-dataset-construction/amazon_spider.py` | Amazon 产品爬虫 |
| `01-dataset-construction/data_pipeline.py` | Pipeline 编排（爬取/上传/处理/报告） |
| `01-dataset-construction/generate_report.py` | HTML 质量报告生成器 |
| `01-dataset-construction/launch_spider.py` | SSH 启动器（服务器端执行） |
| `01-dataset-construction/server-scripts/pvtt_pipeline.py` | 服务器端镜头检测 + 视频标准化 |

---

*报告生成日期：2026-03-08*
