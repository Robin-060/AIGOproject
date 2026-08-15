# Data Layer

数据组交付——从原始 OBS 数据到 Trust Engine 四合一输入的完整链路。

## 流程

```bash
# 第 1 步: 下载 OBS 数据 (Zenodo, ~34GB 全量; 可改脚本只下部分 chunk)
python -m src.data_layer.download_obs_dataset

# 第 2 步: 跑三模型推理 (PhaseNet / PickBlue / OBSTransformer)
python src/data_layer/run_models_clean.py --trace 0

# 第 3 步: 产出四合一 JSON (metadata + quality + profiles + predictions)
python src/data_layer/data_layer.py --trace 0 --output result.json

# 第 4 步: 喂给 Trust Engine
python -m src.trust_engine.pipeline --input result.json
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `download_obs_dataset.py` | 从 Zenodo 下载 SeisBench OBS 数据集 |
| `run_models_clean.py` | 三模型推理 (原始版, 输出统一 JSON) |
| `data_layer.py` | 四合一交付物生成 (推荐使用) |
| `feed_trust_engine.py` | 数据层 → Trust Engine 桥接 |

## 依赖

- seisbench >= 0.12, obspy, torch
- 模型权重首次运行自动下载 (~几百 MB)
- 数据集 ~34GB (全量) 或按需单个 chunk (~2GB)
