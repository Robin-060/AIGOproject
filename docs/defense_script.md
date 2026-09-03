# 复赛 3 分钟陈述稿

> 对应 PPT 主线第 1–9 页；目标时长 2 分 50 秒至 3 分钟。第 10–16 页为问答附录，
> 不在主陈述中逐页播放。所有数字以最终提交包内 `PACKAGE_IDENTITY.json`
> 记录的不可变 release tag / commit 及冻结证据为准。

## 0:00–0:15｜第 1 页：一句话成果

我们的项目是 OBS Trust Layer。它不替代地震相拾取模型，而是回答一个更接近科研工作流的
问题：哪些 AI 输出可以自动进入后续流程，哪些应优先交给专家复核？最终形成两项能力和一条
边界：有限预算下优先截获错误、恢复部分自动覆盖率，同时如实保留安全非劣尚未统计确认的结论。

## 0:15–0:35｜第 2 页：科研问题

只比较模型平均准确率，无法决定单次结果是否值得自动放行。我们把问题拆成两个可测量任务：
自动执行必须同时报告 Coverage 与 Unsafe；人工复核必须同时报告 Review Burden 与 Error
Interception。v1.5.1 暴露的 Coverage ceiling，又派生出 RQ2：能否只使用推理时可见证据恢复
覆盖率，同时守住安全与排序边界？

## 0:35–0:50｜第 3 页：三项成果总览

第一，Trust 在 50% 复核预算下截获 83.6% 错误。第二，failure-driven refinement 把 Coverage
从 45.64% 恢复到 54.13%。第三，Unsafe 点估计差异为加 0.92 个百分点，但配对 bootstrap
单侧上界为加 2.24，超过 2.0 的裁决界，因此安全非劣只能写“接近、未确认”。

## 0:50–1:20｜第 4 页：Review Efficiency 主结果

这是本项目最明确的正结果。横轴是人工复核预算，纵轴是截获的全部错误比例。Trust 在每个预算
点都高于 Random；50% 预算时为 83.6%，Random 为 50.0%，差 33.6 个百分点，台站聚类
bootstrap 区间为加 19.0 到加 35.65。反查曲线显示，截获 80% 错误时 Trust 约需复核 47%，
但我们不把它改写为真实劳动成本下降，因为没有做专家工时实验。

## 1:20–1:38｜第 5 页：Holdout 佐证

在 holdout Primary 子集的 260 个相位单元、161 个错误上，Trust 在 50% 预算下仍截获 80.1%，
高于 Random、ModelConf 和 Disagreement。这里严格称为方向一致性佐证，不称为独立 locked
test；原始 manifest 有 358 个 holdout 行，排除非 Primary 后正式分母才是 260。

## 1:38–2:00｜第 6 页：Policy Ceiling 诊断

v1.5.1 只有 45.64% 自动 Coverage。703 个未自动 action 中，487 个停在证据不足，112 个
有共识却无法融合；距离 50% 只差 57 个真实 selected pick。事后真值显示其中很多候选实际正确，
这支持“瓶颈主要来自 policy 保守”，但这些真值只用于诊断，绝不进入 EXP17 routing rule。

## 2:00–2:30｜第 7 页：EXP17 结果与安全边界

EXP17-A 是 post-hoc、failure-driven refinement。它只使用共识结构、幸存模型、spread、校准
置信度等推理时可见证据，将 Coverage 恢复到 54.13%，Unsafe 为 5.51%，50% 预算错误截获率
为 94.26%。c1、c3、c4 通过；c2 未建立：相对 Voting@50 的 ΔUnsafe 点估计为加 0.92，
单侧 95% 上界为加 2.24，高于加 2.0 的最终裁决界 0.24 个百分点。因此 A 只保留为最佳候选
refinement，不视为已通过安全非劣 Gate 的部署策略。

## 2:30–2:48｜第 8 页：Scientific Claim

我们的最终主张不是“系统已经安全上线”，而是：组合风险证据可用于人工复核优先级排序，并在
holdout Primary 中保持方向一致；严格策略存在可诊断的 policy ceiling；truth-blind refinement
能够恢复 Coverage，但 CI 级安全非劣尚未确认。统一裁决是：Coverage recovery supported;
safety non-inferiority inconclusive。

## 2:48–3:00｜第 9 页：贡献与收束

贡献有三点：可靠性证据准入、有限预算的 review prioritization、以及 failure-driven policy
refinement。更重要的是，负结果、bugfix、算法改进和最终裁决分轨留痕。Trust Layer 的价值不是
让 AI 更敢自动，而是让自动化边界和人工注意力分配都可测、可控、可复现。

## 转入 1 分钟 Demo

“下面用一分钟展示：这些数字来自冻结证据，参数变化调用真实 Trust Engine，并且失败与 c2
未确认会在界面中直接显示。”随后按 [`demo_runbook.md`](demo_runbook.md) 执行。
