# AIGO OBS Trust Engine

## P3 Demo

SeisBench 0.12 需要 Python 3.10 或更高版本。安装依赖并启动：

```bash
python3 -m pip install -r requirements.txt
streamlit run src/web/app.py
```

页面打开后上传数据组产出的 `result.json`。Demo 会在本地调用 Trust Engine，展示每个模型的状态、P/S 最终决策、四证据风险分解和实验图表。

如同时上传对应的 `.csv`、MiniSEED 或 SEG-Y 波形，页面还会展示原始与预处理后波形、模型 P/S 拾取竖线和经典 STA/LTA 触发结果。CSV 可使用 `time_s,Z,N,E,H` 列；MiniSEED 和 SEG-Y 由 ObsPy 读取。

也可以使用启动脚本：

```bash
sh scripts/run_demo.sh
```

下载最小 OBS 分块并运行正式噪声实验：

```bash
sh scripts/download_obs_201805.sh
python3 -m src.experiments.seisbench_noise
```

实验固定使用官方测试集中的 20 条四通道 P/S 标注波形，运行 PhaseNet/geofon、PickBlue/obs-phasenet 和 OBSTransformer/obst2024。下载的数据约 353 MiB，位于 `data/seisbench/`，不会进入 Git。

`src.experiments.noise_robustness` 保留为不下载模型和数据时的 Demo 基准生成器，不用于正式性能结论。

数据已下载并完成真实模型推理后，可重建公开数据评测表、STA/LTA 基线和 CPU 工程基准：

```bash
sh scripts/run_public_evaluation.sh
```

严格指标同时报告整体准确率、覆盖率、选择性准确率、拒绝率、不安全输出率、P/S MAE 和 95% 置信区间。安全处置率不能单独解释为拾取准确率。

## 当前项目边界

本仓库不接触南海受限或涉密 OBS 数据，不进行海上采集，也不声称已经完成真实用户工作量验证。事件分流目前是透明规则，不是训练好的分类模型；模型已验证可在本机 CPU 运行，但尚未量化或剪枝。详细说明见 `docs/scope_and_compliance.md`。

公开数据与模型来源登记见 `docs/data_and_model_sources.md`，实验记录可使用 `docs/experiment_log_template.md`。

运行测试：

```bash
python3 -m pytest -q
```
