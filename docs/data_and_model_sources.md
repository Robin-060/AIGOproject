# 公开数据与模型来源登记

## SeisBench OBS 数据

- 用途：噪声鲁棒性实验、STA/LTA 基线、CPU 性能测量。
- 使用范围：官方 `test` split，分块 `201805`，固定选择 20 条含 P/S 标签的四通道波形。
- 仓库策略：下载文件位于 `data/seisbench/`，由 `.gitignore` 排除，不重新分发。
- 可追溯性：下载脚本、样本 ID、版本和 SHA-256 保存在仓库。
- 注意：标签混合人工和自动来源，报告必须披露。
- 数据引用：Bornstein et al. (2023), *PickBlue: Seismic phase picking for ocean bottom seismometers with deep learning*, DOI `10.1029/2023EA003332`。

## 预训练权重

- PhaseNet：SeisBench `geofon` 权重。
- PickBlue：SeisBench `obs` PhaseNet 权重。
- OBSTransformer：SeisBench `obst2024` 权重。
- 仓库策略：权重由 SeisBench 下载到用户缓存，不提交、不重新打包。
- 引用策略：公开报告应引用 SeisBench 以及各数据集、模型权重页面要求的原始论文。
- SeisBench 软件许可证：GPL-3.0；本项目不复制或改写其源码，只通过已安装依赖调用公开 API。
- 引用清单应同时覆盖 SeisBench、模型架构、所用预训练权重说明和训练数据论文；不能只引用工具箱。

## 官方入口

- SeisBench 仓库：<https://github.com/seisbench/seisbench>
- 数据集目录：<https://seisbench.readthedocs.io/en/stable/pages/data/benchmark_datasets.html>
- 官方引用指南：<https://seisbench.readthedocs.io/en/stable/pages/referencing.html>

## 本仓库生成数据

加性高斯噪声、指标汇总表和图表由仓库脚本生成。随机种子由样本 ID 与噪声等级通过 SHA-256 确定；生成物不是新的真实海洋观测数据。

## 未使用的数据

本项目当前未接触南海受限 OBS 数据、未授权台阵数据或实地科考数据。任何未来新增数据必须先完成合法授权和发布范围审查。
