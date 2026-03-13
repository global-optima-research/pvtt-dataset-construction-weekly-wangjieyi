# PVTT 数据采集周报仓库

> Product Video Template Transfer (PVTT) — 电商产品视频数据采集
> 目标会议：CVPR 2027
> 负责人：王洁怡

## 仓库结构

| 目录 | 说明 |
|------|------|
| `01-dataset-construction/` | 数据采集Pipeline、爬虫代码、数据报告 |
| `02-teacher-model-training/` | Teacher模型训练（待开展） |
| `03-dmd-distillation/` | DMD蒸馏（待开展） |
| `docs/` | 文献综述与技术调研 |

## 周报

| 周次 | 文件 | 主要内容 |
|------|------|----------|
| Week 03 (03-08 ~ 03-14) | [`week03_dataset_report.ipynb`](week03_dataset_report.ipynb) | Amazon数据扩展至600+，多平台调研，Pipeline完善 |

## 当前进度

- Amazon数据：622+ 产品，3432张图片，603个视频，3.8GB
- 爬虫仍在运行中，目标800+产品
- 详见 [`01-dataset-construction/README.md`](01-dataset-construction/README.md)
