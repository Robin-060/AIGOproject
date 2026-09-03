# 开源发布与复赛冻结计划

公开仓库：<https://github.com/Robin-060/AIGOproject>。

## 1. 许可证状态

仓库顶层 [`LICENSE`](../LICENSE) 已采用 MIT License，仅覆盖团队有权许可的原创代码
与文档。第三方软件、OBS 数据、预训练模型权重、论文和商标继续服从各自条款；简版声明
见 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)，完整登记见
[`data_and_model_sources.md`](data_and_model_sources.md)。

## 2. 计划发布内容

- Trust Engine、数据适配、波形 I/O、预处理、STA/LTA 基线和评测脚本；
- Streamlit Demo、后端接口、Docker 和 CI 配置；
- 冻结配置、测试、实验日志、reference-frame/baseline 设计与复现说明；
- 可依法发布的 manifest、冻结预测、派生质量、统计结果、图表与证据哈希；
- 数据、模型、依赖、许可证及 Scientific Claim 边界说明。

## 3. 不随仓库或提交压缩包发布

- 原始 OBS HDF5 波形、SeisBench 数据缓存；
- PhaseNet、PickBlue、OBSTransformer、EQTransformer checkpoint；
- 虚拟环境、模型缓存、临时文件和本机绝对路径；
- API key、token、密码、个人数据或任何受限/未授权数据；
- 许可证或来源无法确认的第三方代码副本。

## 4. 最终发布门禁

1. **证据一致性**：README、最终报告、C 文档、PPT、Demo 与 evidence manifest 的核心数字一致。
2. **历史保护**：v1.5.1 archive、EXP17 失败分支与原始负结果不被覆盖。
3. **复现检查**：核心重放、EXP17-A/paired bootstrap、全部测试和 Demo HTTP 健康检查通过。
4. **许可检查**：OBS 数据 CC BY 4.0 归属完整；SeisBench GPL-3.0、架构许可证和
   checkpoint 不再分发边界明确。
5. **发布检查**：生成最终依赖清单/SBOM，完成 secret、大文件、个人路径和压缩包扫描。
6. **版本冻结**：区分实验冻结锚点 `e5ff41c` 与最终发布 commit；所有检查通过后创建
   不可变 release tag，不以“最新提交”替代证据验收。

## 5. 维护规则

- Scientific Claim 的任何变化必须同步更新原始结果、汇总表、图、报告和 manifest。
- 新模型、阈值或 routing 规则必须创建新实验版本，不改写历史冻结语义。
- Coverage、Unsafe、Error Interception 与 Review Burden 必须成对报告。
- `R1 PASS` 必须始终带范围说明，不得作为 EXP17 总体安全 PASS 展示。
- 外部贡献不得包含无授权数据、权重或未披露来源的第三方代码。
