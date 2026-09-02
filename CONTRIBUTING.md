# Contributing

欢迎提交问题报告、复现记录、新数据域 adapter、新的 reliability evidence 候选和统计协议改进。

## 基本流程

1. 在 issue 中说明数据来源、许可证、研究问题和预期验证方式；
2. 将数据/模型身份、评价单元和参数写入版本化配置；
3. 新增实验不覆盖历史结果，应使用新的产物名称和 trajectory 记录；
4. 同时报告 Coverage/Unsafe 或 Review/Interception，包含负结果和不可达点；
5. 运行 `bash smoke_test.sh`、`bash reproduce_core.sh` 和与修改相关的专项复现。

## 证据准入

新证据进入 Reliability Engine 前，必须提供：

- 自然数据上的 error relevance；
- 在现有证据之上的 incremental value；
- 推理时可见性与 truth-blind 说明；
- 对 holdout、数据重叠和外推范围的降级表述。

详细规则见 `docs/experiments/evidence_admission_rule.md`。

## 发布与合规

请勿提交原始 OBS 数据、预训练权重、密钥、个人路径或无授权第三方资源。
外部数据、代码或模型必须同步更新 `THIRD_PARTY_NOTICES.md`、
`docs/data_and_model_sources.md` 和 SBOM。
