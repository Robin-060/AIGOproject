# 复赛高风险问答卡

## 1. 为什么 EXP17-A 不能说“通过”？

因为四项判据中 c2 未建立。ΔUnsafe 点估计 +0.92pp 在内部工程绿灯内，但配对 station-cluster
bootstrap 的单侧 95% 上界为 +2.24pp，高于最终裁决的 +2.0pp 非劣界。正确结论是 Coverage
recovery supported；safety non-inferiority inconclusive，而不是“非劣成立”或“算法显著劣化”。

## 2. 这个 Gate 是不是原始预注册？

不是。EXP17 是看到 v1.5.1 policy ceiling 后开展的 post-hoc、failure-driven refinement。
数据、模型、评价单元和 truth-blind 边界保持冻结；判据版本和修订均留痕，但 c2 的 Voting@50
配对 bootstrap 口径是在探索过程中完成最终对齐，因此不作严格预注册确证表述。

## 3. 事后看到 312/89 个“全对”是否泄漏真值？

没有进入规则。312/487 与 89/112 只用于 failure decomposition，回答“天花板为何出现”；
EXP17 routing 只使用共识结构、幸存模型数、spread、校准置信度、模型适用性、相位和历史可靠性。
当前 evaluation truth、当前样本是否正确均被禁止作为输入。

## 4. R1 显示 PASS，为什么 c2 仍未通过？

两者对象不同。R1 PASS 只证明显式使用 P=0.34s / S=0.51s 重跑与冻结 EXP17-A 完全一致，
排除了 legacy 0.30/0.50 常量影响；c2 评价的是相对 Voting 的安全非劣，仍为 NOT ESTABLISHED。

## 5. 54.13% 的提升是否包含修 bug 的贡献？

不包含混报。v1.5.1-bugfix 只修复 ROUTE 候选没有目标相位有效 prediction 的实现问题，7 个
invalid-pick action 被单独审计；EXP17-A 是在 bugfix baseline 上评估的算法 refinement。两条轨道
有独立提交和结果，bugfix 不计为算法贡献。

## 6. holdout 为什么既有 358 又有 260？

358 是原始 manifest 中全部 holdout 行；正式 Primary 相位级评价排除非 Primary 行后为 260，
其中错误 161。所有 Error Interception 的 holdout 分母均使用 260。由于风险权重拟合包含 holdout
记录，该结果只作方向一致性佐证，不称为独立 locked test。

## 7. 为什么 Trust 的 review 排序有价值？

它改变的是有限人工注意力的分配，而不是宣称替代专家。在相同 50% 复核预算下，Trust 截获
83.6% 错误，Random 为 50.0%，且对 ModelConf、Disagreement 也有优势。它支持“提高单位复核
预算的错误截获效率”，不支持“人工成本下降 X%”。

## 8. 为什么不用最高置信度或简单 Voting？

置信度不等于跨模型可比的正确概率，多数一致也会系统性犯错。冻结反例中，FUSE 的 S 相为
142.61s，而 EQT 在 44.84s 正确。Voting 是安全比较器之一，但不能替代对数据质量、适用性、
共识结构和流程一致性的显式证据审计。

## 9. 能否推广到其他数据集或生产部署？

当前不能。第二域 `_BLANCO` 与主域属于同一 OBS 数据集的不同台阵；若干 OBS checkpoint 的
训练—评估重叠仍为 UNKNOWN。项目未做跨数据集泛化、专家工时、下游 catalog 影响或生产安全
实验，因此这些均列入 No-Go。

## 10. 如何复现最关键结果？

运行 `bash reproduce_core.sh` 和 `bash reproduce_exp17.sh`。后者执行 v1.5.1 逐单元对账、
EXP17-A、配对 bootstrap、R1 核验和只读证据终检；预期输出为 54.13% / 5.51% / 94.26% /
Δ+0.92pp / upper95 +2.24pp，且 v1.5.1 对账差异为 0。
