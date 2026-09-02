# 数据、模型与外部资源来源登记

> 状态：复赛披露稿，核对日期 2026-09-02。本文用于事实与发布边界披露，
> 不构成法律意见。“公开可访问”不自动表示所有模型权重均可由本仓库重新分发。

## 1. OBS 数据集

| 字段 | 当前登记 |
|---|---|
| 官方记录 | Zenodo record 10277799，DOI <https://doi.org/10.5281/zenodo.10277799> |
| 官方名称 | *Database of local seismicity registered on ocean bottom seismometers (OBS)* |
| 版本 | v1-12/2023，发布于 2023-12-07 |
| 许可证 | **Creative Commons Attribution 4.0 International（CC BY 4.0）** |
| 关联论文 | Bornstein et al. (2023), *PickBlue: Seismic phase picking for ocean bottom seismometers with deep learning*, DOI <https://doi.org/10.1029/2023EA003332> |
| 本项目主评估范围 | XO 部署相关冻结记录；895 个记录、1306 个 Primary 相位级评估单元（P 657、S 649） |
| 第二域 | `_BLANCO`，来自同一 OBS 数据集的不同台阵，200 条；属于跨台阵而非跨数据集验证 |

许可证信息以 Zenodo API/记录页 `metadata.license.id=cc-by-4.0` 为准。公开使用或
再分发数据及其可识别派生物时，应保留数据作者、标题、版本、DOI、许可证及变更说明。

本仓库不提交约 35 GB 的原始 HDF5 波形；原始数据由复现者通过 Zenodo 或
SeisBench 官方接口自行获取。仓库中的 sample ID、reference-time manifest、冻结预测、
派生质量特征、统计结果与哈希仅用于复赛检查和科学复现，并应连同上述归属信息使用。

## 2. SeisBench 软件

| 字段 | 当前登记 |
|---|---|
| 官方仓库 | <https://github.com/seisbench/seisbench> |
| 许可证 | GNU General Public License v3.0（GPL-3.0） |
| 冻结推理环境 | SeisBench 0.12.3 |
| 干净环境复核 | SeisBench 0.12.5；冻结预测重放结果一致 |
| 使用方式 | 通过安装依赖调用公开 API；仓库未复制或修改 SeisBench 源码 |

`requirements-core.txt` 不包含 SeisBench，可在不下载模型权重的情况下重放冻结预测和
核心统计。完整模型推理与 Docker 环境安装 SeisBench；重新分发包含该依赖的镜像或软件
组合时，应保留 GPL-3.0 许可证与相应源码获取义务。顶层 MIT 许可证不覆盖 SeisBench。

官方引用说明：<https://seisbench.readthedocs.io/en/stable/pages/referencing.html>。

## 3. 预训练模型与 checkpoint

本仓库不打包任何 checkpoint。首次执行完整推理时，权重由 SeisBench 下载到用户缓存；
冻结结果复现只读取已经登记的预测与哈希。

| 冻结列 | 实际模型 / checkpoint | 架构与论文 | 训练域 | 训练—评估重叠状态 |
|---|---|---|---|---|
| PhaseNet | `PhaseNet.from_pretrained("geofon")` | Zhu & Beroza (2019), DOI <https://doi.org/10.1093/gji/ggy423> | GEOFON 陆地区域 | 未发现与 OBS 评估域直接重叠；未完成逐事件正式审计 |
| PickBlue | `PickBlue(base="phasenet")`，实际为 PhaseNet `obs` | PhaseNet 架构；Bornstein et al. (2023) | OBS | **UNKNOWN** |
| OBSTransformer | `OBSTransformer.from_pretrained("obst2024")` | Niksejel & Zhang (2024), DOI <https://doi.org/10.1093/gji/ggae049> | OBS | **UNKNOWN** |
| EQTransformer | `EQTransformer.from_pretrained("obs")` | Mousavi et al. (2020), DOI <https://doi.org/10.1038/s41467-020-17591-w> | OBS | **UNKNOWN** |

PhaseNet、OBSTransformer 和 EQTransformer 原始架构仓库当前均声明 MIT 许可证；
本项目实际通过 GPL-3.0 的 SeisBench 实现调用。架构代码许可证不能自动推定为托管
checkpoint 的专属许可证。由于当前 registry 尚未取得四组权重的完整专属许可证记录，
权重再分发状态统一记为 **UNKNOWN / 不随仓库分发**。

详细模型身份、通道顺序、默认参数及指纹核验见 [`model_registry.md`](model_registry.md)。

## 4. 直接依赖披露

| 依赖 | 主要用途 | 许可证/发布处理 |
|---|---|---|
| NumPy / SciPy / pandas | 数值计算与统计 | BSD-family；按最终安装发行包保留许可证 |
| Matplotlib | 图表 | Matplotlib/PSF-compatible；按发行包保留许可证 |
| PyYAML / pytest | 配置与测试 | MIT |
| Streamlit | Demo | Apache-2.0 |
| ObsPy | MiniSEED/SEG-Y 与信号处理 | LGPL-3.0 |
| PyTorch | 模型运行 | BSD-style；保留上游 LICENSE/NOTICE |
| FastAPI / Uvicorn / python-multipart | Demo 后端 | 以最终安装发行包元数据和 SBOM 为准 |

最终直接依赖以 `requirements-core.txt`、`requirements.txt` 和 Dockerfile 为准；完整
传递依赖及许可证仍应由最终锁定环境生成 SBOM/license report 后归档。

## 5. 未使用与不再分发的资源

- 未使用第三方商业 API、闭源推理服务或付费数据接口。
- 未使用南海受限 OBS 数据、未授权科考数据、个人数据或涉密数据。
- 不在仓库或提交压缩包中分发原始 OBS 波形、模型权重、用户缓存、密钥或 token。
- `_BLANCO` 只可描述为同数据集不同台阵佐证，不可描述为独立跨数据集泛化。

## 6. 许可证边界与当前结论

- 顶层 [`LICENSE`](../LICENSE) 的 MIT 条款只覆盖团队有权许可的原创代码与文档。
- OBS 数据及可识别派生物按 CC BY 4.0 保留归属、DOI、许可证和变更说明。
- SeisBench 保持 GPL-3.0；其他第三方依赖、模型架构和 checkpoint 服从各自条款。
- checkpoint 不随仓库重新分发；其专属许可证未完全核实前，不声明“所有权重均为 MIT”。
- 训练—评估重叠为 UNKNOWN 的模型不得支撑跨数据集或独立泛化主张。

简版第三方声明见仓库顶层 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。
