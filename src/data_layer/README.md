# Data Layer

数据组交付——从原始 OBS 数据到 Trust Engine 四合一输入的完整链路。

## 流程

```bash
# 第 1 步: 下载 OBS 数据 (Zenodo, ~34GB 全量; 可改脚本只下部分 chunk)
python -m src.data_layer.download_obs_dataset

# 第 2 步: 跑核心三 adapter (PhaseNet-geofon / PhaseNet-obs / OBSTransformer)
python src/data_layer/run_models_clean.py --trace 0

# 第 3 步: 产出数据层四合一 JSON (metadata + quality + profiles + predictions)
python src/data_layer/data_layer.py --trace 0 --output result.json

# 第 4 步（正式四模型冻结评价）: 独立批处理 EQTransformer，然后合并到 records_all_v2
python -m src.experiments.run_eqt_batch

# 第 5 步: 喂给 Trust Engine
python -m src.trust_engine.pipeline --input result.json
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `download_obs_dataset.py` | 从 Zenodo 下载 SeisBench OBS 数据集 |
| `run_models_clean.py` | 核心三 adapter 推理（输出统一 JSON） |
| `data_layer.py` | 四合一交付物生成 (推荐使用) |
| `feed_trust_engine.py` | 数据层 → Trust Engine 桥接 |

> 注：“四合一”指 metadata / quality / profiles / predictions 四类信息，不是四个模型。
> 复赛冻结评价使用四套 checkpoint；EQT 由独立批处理路径加入。

## 依赖

- seisbench >= 0.12, obspy, torch
- 模型权重首次运行自动下载 (~几百 MB)
- 数据集 ~34GB (全量) 或按需单个 chunk (~2GB)
