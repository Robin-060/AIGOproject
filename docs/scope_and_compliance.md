# 项目范围、证据边界与合规说明

## 1. 当前可验证范围

本项目在固定 OBS 数据、冻结模型输出和统一相位级评价协议下，研究多模型可靠性证据能否：

1. 对有限人工复核资源进行错误风险排序；
2. 形成可测量的自动处理 Coverage / Unsafe 权衡；
3. 在严格策略产生 policy ceiling 后，通过 truth-blind、failure-driven 的决策策略改进恢复部分自动处理能力。

主评估为 1306 个 Primary 相位级单元；holdout Primary 子集为 260 个单元。
358 是原始 manifest 中全部 holdout 行数，排除非 Primary 行后正式分母为 260。
该 holdout 用于方向一致性佐证，不是独立 locked test。

## 2. 当前能够陈述的结果

- EXP16：固定复核预算下，Trust 风险排序优于 Random、ModelConf 和 Disagreement；
  全量 50% 预算错误截获率为 83.6%，holdout Primary 子集为 80.1%。
- v1.5.1：严格策略的自动 Coverage 天花板为 45.64%；50% 声明点 NOT_EVALUABLE；
  S 相在自身天花板处显著差于 Voting。该负结果继续保留。
- EXP17-A：Coverage 恢复至 54.13%，Unsafe 5.51%，50% 复核预算错误截获率
  94.26%；c1/c3/c4 通过。
- EXP17-A 相对 Voting@50 的 ΔUnsafe 点估计为 +0.92pp，但配对 station-cluster
  bootstrap 单侧 95% 上界为 +2.24pp，高于 +2.0pp 最终裁决界值，故 c2 为
  **NOT ESTABLISHED**。
- 最终统一表述：**Coverage recovery supported; safety non-inferiority inconclusive.**
- R1 PASS 只表示显式使用 P=0.34s / S=0.51s 重跑可复现 EXP17-A 冻结结果，
  不表示 EXP17 总体安全 Gate PASS。

## 3. 实验身份与探索性质

- EXP01–15 是结果可见的开放探索轨迹，不构成严格预注册的独立盲测。
- v1.5.1 是历史冻结基线；EXP17 不覆盖或改写其原始结果。
- EXP17 是在观察到 policy ceiling 后开展的 post-hoc、failure-driven refinement。
- EXP17 的数据、模型、评价单元和 truth-blind 边界保持冻结；最终 c2 的
  Voting@50 配对 bootstrap 口径在探索过程中修订，并保留版本记录。
- ROUTE invalid-pick 属 implementation bugfix；EXP17-A Consensus Route 属算法策略改进，
  两者分轨记录，bugfix 不计为算法贡献。

## 4. No-Go：不得形成的主张

1. 不写 EXP17 “总体通过”“安全非劣成立”或已成为部署策略。
2. 不写 Unsafe 与 Voting “持平”；只能写点估计接近、CI 级非劣未确认。
3. 不把 R1 robustness PASS 解释为 c2 或总体 Gate PASS。
4. 不把 post-hoc EXP17 描述为原始预声明实验或严格预注册确证。
5. 不把 holdout 描述为独立 locked test，也不据此声称跨数据集普适泛化。
6. 不把 risk score 描述为已校准的错误概率。
7. 不把“达到相同错误截获时 review coverage 更低”直接等价为实际劳动成本下降；
   当前没有人工时间、成本或用户研究实验。
8. 不声称 production deployment、南海真实任务验证、自主科研 Agent 或全面安全自动化。
9. 不声称四个模型完全独立；PhaseNet geofon 与 PhaseNet obs 共享架构，多个 OBS
   checkpoint 的训练—评估重叠仍为 UNKNOWN。
10. 不把合成故障注入、构造案例或早期 20 条噪声实验扩大为主数据上的普遍因果结论。

## 5. 数据与发布边界

- OBS 数据为 Zenodo 公开记录，许可证为 CC BY 4.0；使用与派生物发布需保留归属。
- 项目不提交约 35 GB 原始波形，不打包任何 checkpoint。
- 顶层 MIT 仅覆盖团队有权许可的原创代码和文档；SeisBench、外部数据、模型权重和
  其他依赖不因本仓库许可证而改变。
- 未使用商业 API、闭源模型服务、受限数据或涉密数据。
- 完整来源与许可证说明见 [`data_and_model_sources.md`](data_and_model_sources.md) 和
  [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。

## 6. 后续验证条件

后续研究需要更大 station-cluster 样本确认 +2.0pp 非劣界，并在独立数据集、明确训练
重叠状态和人工复核时间/成本实验下验证可推广性。任何受限数据、现场部署或新模型引入，
均应建立新的数据授权、参数冻结、评价协议与发布审查记录，不沿用本次复赛结论。
