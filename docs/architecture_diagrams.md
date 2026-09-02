# OBS Trust Layer — 系统架构与流程图示

> 本文件所有模块名、步骤名、reason code、参数取值均与仓库代码一致
> (config `semifinal_v1.5.1-bugfix` / `9727570d…`，冻结于 EXP17 最终裁决)。
> GitHub 可直接渲染 Mermaid；导出 PNG 用于答辩见文末说明。

---

## 图 1 · 系统业务流程图（端到端科研工作流）

```mermaid
flowchart TD
    subgraph S1["① 数据与模型（冻结，sha256 校验）"]
        A1["公开 OBS 波形<br>XO 台阵 · 895 records<br>60 stations"] --> A2["统一预处理<br>signal/preprocessing.py"]
        A2 --> A3["四模型 Adapter 推理<br>PhaseNet · PickBlue<br>OBSTransformer · EQTransformer"]
        A3 --> A4[("冻结预测缓存<br>records_all_v2.json")]
    end

    subgraph S2["② Trust Engine（逐相位决策）"]
        A4 --> B1["四证据层风险合成<br>数据≤30 · 单模型≤24<br>多模型≤37 · 物理≤40"]
        B1 --> B2["6 步路由<br>policy_router.py"]
        B2 -->|"放行"| C1["自动输出<br>ACCEPT / FUSE / ROUTE"]
        B2 -->|"证据不足/高风险"| C2["ABSTAIN + reason codes<br>进入人工复核队列"]
    end

    subgraph S3["③ 下游与人工"]
        C1 --> D1["进入科研后续流程<br>事件关联 → 定位 → 目录构建"]
        C2 --> D2["复核队列按 Trust risk<br>降序排序（风险优先）"]
        D2 --> D3{"专家复核"}
        D3 -->|"修正 / 采纳"| D1
        D3 -.->|"标注回流再校准<br>（Future Research）"| A4
    end

    subgraph S4["④ 评估闭环（冻结协议）"]
        C1 --> E1["Coverage 与 Unsafe<br>永远成对报告"]
        C2 --> E2["Error Interception 与<br>Review Burden 成对报告"]
        E1 --> E3["Equal-Coverage 协议<br>+ 配对 station-cluster bootstrap"]
    end
```

---

## 图 2 · Trust Engine 决策流程图（核心算法，6+1 步路由）

```mermaid
flowchart TD
    S0(["输入：单个相位单元<br>suitability / consensus<br>fusion_candidate / evidence<br>phase_risk（四证据合成）"]) --> Q0{"第 0 步 可比性<br>存在 eligible 模型？"}
    Q0 -- 否 --> R0["ABSTAIN<br>NO_ELIGIBLE_MODELS"]
    Q0 -- 是 --> Q1{"第 1 步 幸存者<br>survivors 非空？"}
    Q1 -- 否 --> R1["ABSTAIN<br>NO_SURVIVING_MODELS"]
    Q1 -- 是 --> Q2{"第 2 步 可融合？<br>fusion_allowed 且<br>contributors 全部幸存"}
    Q2 -- 是 --> Q2R{"risk 超自动阈值？"}
    Q2R -- 否 --> R2["FUSE<br>FUSE_CONSENSUS_CLUSTER"]
    Q2R -- 是 --> R2X["ABSTAIN<br>FUSE_RISK_ABOVE_AUTO_THRESHOLD"]
    Q2 -- 否 --> Q3{"第 3 步 单一幸存者？<br>（EXP17-B：唯一有 pick 的幸存者）"}
    Q3 -- 是 --> Q3P{"选中模型有<br>该相位有效 pick？"}
    Q3P -- 否 --> R3X["ABSTAIN<br>ONLY_SURVIVOR_{m}_NO_VALID_PICK<br>（v1.5.1-bugfix 新增）"]
    Q3P -- 是 --> Q3R{"risk 超自动阈值？"}
    Q3R -- 否 --> R3["ACCEPT / ROUTE<br>ONLY_SURVIVOR_{m}"]
    Q3R -- 是 --> R3Y["ABSTAIN<br>ONLY_SURVIVOR_{m}_RISK_ABOVE_THRESHOLD"]
    Q3 -- 否 --> Q4{"第 4 步 严重分歧？<br>consensus = DISAGREEMENT"}
    Q4 -- 是 --> R4["ABSTAIN<br>NO_DECISIVE_EVIDENCE_BETWEEN_MODELS"]
    Q4 -- 否 --> Q45{"第 4.5 步 共识但无<br>可准入融合候选？"}
    Q45 -- 是 --> Q45A{"EXP17-A 开启且<br>共识簇内有校准置信度候选？"}
    Q45A -- 是 --> Q45R{"risk 超自动阈值？"}
    Q45R -- 否 --> R45["ACCEPT / ROUTE<br>CONSENSUS_ROUTE_BEST_INLIER<br>（校准置信度最高者）"]
    Q45R -- 是 --> R45B["ABSTAIN<br>CONSENSUS_WITHOUT_ADMISSIBLE_FUSION"]
    Q45A -- 否 --> R45B
    Q45 -- 否 --> R5["第 5 步 其他证据？<br>（无验证档案）→ ABSTAIN<br>INSUFFICIENT_EVIDENCE_FOR_SELECTION"]

    style S0 fill:#f0f4ff,stroke:#2b5bdb
    style R2 fill:#e7f6ec,stroke:#1e7d43
    style R3 fill:#e7f6ec,stroke:#1e7d43
    style R45 fill:#e7f6ec,stroke:#1e7d43
    style R0 fill:#fdecec,stroke:#c0392b
    style R1 fill:#fdecec,stroke:#c0392b
    style R2X fill:#fdecec,stroke:#c0392b
    style R3X fill:#fdecec,stroke:#c0392b
    style R3Y fill:#fdecec,stroke:#c0392b
    style R4 fill:#fdecec,stroke:#c0392b
    style R45B fill:#fdecec,stroke:#c0392b
    style R5 fill:#fdecec,stroke:#c0392b
```

> 口径说明：正式实验以 `ranking_mode` 运行（automatic_risk_threshold 由 10 覆盖为
> 100），即 risk 分只用于排序、不直接拦截；自动放行的门禁是第 0–4.5 步的
> **证据准入**（truth-blind，规则只读推理时可见证据，绝不读 evaluation truth）。

---

## 图 3 · 四证据层结构（风险合成）

```mermaid
flowchart LR
    subgraph P1["P1 数据证据 ≤ 30 分"]
        D1["quality_manifest<br>SNR / 缺失通道 / 削波 / gap"]
    end
    subgraph P2["P2 单模型证据 ≤ 24 分"]
        D2["各模型自身证据<br>置信度 · 适配状态"]
    end
    subgraph P3["P3 多模型证据 ≤ 37 分"]
        D3["共识 / 分歧结构<br>DISAGREEMENT 严重=37<br>轻微=18.5 · 离群罚分"]
    end
    subgraph P4["P4 物理证据 ≤ 40 分"]
        D4["OBS 特有物理检查<br>倾斜噪声 · 洋流噪声<br>时钟漂移（逻辑回归校准 n=895）"]
    end

    D1 --> R["phase_risk = min(总和, 100)"]
    D2 --> R
    D3 --> R
    D4 --> R
    R --> L{"risk level"}
    L -->|"≤10"| L1["LOW"]
    L -->|"≤30"| L2["MEDIUM"]
    L -->|"大于30"| L3["HIGH"]
    L1 & L2 & L3 --> U["用途① 复核队列排序（EXP16 风险排序）<br>用途② 分箱单调性验证（risk bins）"]
```

---

## 图 4 · 模块结构及上层调用关系图

```mermaid
flowchart TD
    CFG[("configs/semifinal_main.yaml<br>单源冻结配置")] --> CL["config_loader.py<br>FrozenExperimentConfig"]
    CL -->|"trust_config(ranking_mode=True)<br>config_hash 写入所有结果行"| TE
    CL -->|"model_profiles()"| TE

    subgraph DL["数据底座"]
        DL1["data_layer/<br>download_obs_dataset<br>quality_manifest_builder<br>run_models_clean"]
        SG["signal/<br>preprocessing · io · triage<br>stalta"]
        CAL["calibrate/<br>batch_calibration<br>data_weight_calibration<br>tolerance_calibration"]
        DL1 --> PDS[("data/ 冻结输入<br>records_all_v2.json<br>quality_manifest.csv")]
        SG --> PDS
        CAL --> PDS
    end

    PDS --> TE

    subgraph TE["src/trust_engine/（算法核心）"]
        SC["schema.py<br>PhaseDecision · TrustConfig<br>Action · 证据类型"]
        REL["reliability.py<br>四证据风险合成"]
        E1["data_evidence.py"]
        E2["single_model.py"]
        E3["multi_model.py + fusion.py"]
        E4["physics.py + model_suitability.py"]
        CC["confidence_calibration.py<br>Platt 校准（P=0.34s / S=0.51s）"]
        PR["policy_router.py<br>6 步路由 + EXP17 开关"]
        PL["pipeline.py<br>端到端串联"]
        REL --> E1 & E2 & E3 & E4
        E1 & E2 & E3 & E4 --> REL
        REL --> PR
        CC --> PR
        SC -.->|"类型/常量"| REL & PR
        PL --> REL --> PR
    end

    subgraph EXP["src/experiments/（实验与评估）"]
        PE["phase_evaluation.py<br>1306 相位单元 · 容差判定"]
        RB["run_baselines.py<br>8 策略基线"]
        RM["run_main_experiment.py<br>冻结主实验"]
        RV["review_budget_curve.py<br>review_budget_ci.py"]
        EX17["exp17_policy_refinement.py<br>+ paired_bootstrap.py"]
        DIAG["policy_diagnosis.py<br>failure decomposition"]
        REP["reproduce_main.py<br>9 步复现入口"]
        REP --> PE & RB & RM & RV & EX17
        PE --> RB & RM & RV & EX17
        RM --> TE
        EX17 --> TE
    end

    EXP --> RES[("results/ 冻结产物<br>main_results.csv · paired_bootstrap_A.json<br>review_budget_* · exp17_summary_*")]

    subgraph WEB["演示环境（B）"]
        BE["demo_backend/app.py<br>FastAPI :8000"]
        FE["web/app.py<br>Streamlit :8501"]
        FE -->|"HTTP API"| BE
        BE -->|"只读消费"| RES
        BE --> TE
    end
```

---

## 图 5 · 复现链（reproduce_main 九步 + 复现报告）

```mermaid
flowchart LR
    Z1["1 冻结工件校验<br>sha256"] --> Z2["2 基线对比<br>8 策略"]
    Z2 --> Z3["3 主实验<br>冻结 profile"]
    Z3 --> Z4["4 全方法对比表"]
    Z4 --> Z5["5 cluster paired<br>bootstrap"]
    Z5 --> Z6["6 三张主图<br>+ failure data"]
    Z6 --> Z7["7 探索轨迹导出<br>JSONL"]
    Z7 --> Z8["8 Review Budget<br>曲线"]
    Z8 --> Z9["9 Review Budget<br>cluster CI"]
    Z9 --> ZR["复现报告<br>NOT_EVALUABLE 纪律<br>不可达点位不填 Unsafe"]
```

---

## 图 6 · 开放探索闭环（Hypothesis → … → Limitation）

```mermaid
flowchart LR
    T1["v1.5.1 冻结负结果<br>天花板 45.64%<br>S 相 Δ+3.39pp 更差"] --> T2["Implementation audit<br>执行路径审计"]
    T2 --> T3["ROUTE bugfix 基线<br>7 个 invalid-pick<br>核心数字零变化"]
    T3 --> T4["Failure decomposition<br>703 未自动<br>487 / 112 / 99 / 5"]
    T4 --> T5["EXP17-A Consensus Route<br>采用：54.13% / 5.51% / 94.26%<br>c2 上界 +2.24pp → 非劣未确认"]
    T4 --> T6["EXP17-B 唯一可用幸存者<br>81.62% 但 c2 +4.87 / c3 64.55%<br>双败弃用"]
    T4 --> T7["EXP17-C floor sweep<br>留档：0.60→51.76% 等<br>劣于 A，不升级"]
    T5 --> T8["EXP17-R1 参数来源审计<br>P=0.34/S=0.51 显式重跑<br>完全一致 · 76/76 tests"]
    T6 --> T8
    T7 --> T8
    T8 --> T9["最终裁决：<br>Coverage recovery supported<br>safety non-inferiority inconclusive"]
```

---

## 图 7 · Demo 部署结构（B · Docker Compose）

```mermaid
flowchart TD
    U["评委浏览器"] -->|":8501"| FE["Streamlit 前端<br>web/app.py"]
    FE -->|"HTTP :8000"| BE["FastAPI 后端<br>demo_backend/app.py"]
    BE -->|"只读消费冻结产物<br>不重算科研指标"| RES[("results/ 冻结结果<br>main_results · exp17_summary<br>review_budget_* · R1")]
    BE -->|"参数变更时<br>调用真实 Trust Engine"| TE["trust_engine<br>（冻结 config）"]
    FE -.->|"展示"| FIX["Fixed 面板<br>冻结反馈 / Equal-Coverage"]
    FE -.->|"交互"| SEARCH["Searchable<br>threshold · tolerance · weight"]
    FE -.->|"反馈"| FB["Feedback<br>Coverage+Unsafe · Interception+Review"]
    FE -.->|"案例"| CASE["Case Explorer<br>真实失败样本 + ABSTAIN 确定性解释"]
```

---

## 补充建议（还可画的图，按答辩价值排序）

1. **单样本决策时序图**（sequence diagram）：数据组 JSON → pipeline →
   route_phase → PhaseDecision JSON → Demo 展示，适合解释"一次决策经过哪些模块"。
2. **Equal-Coverage 协议图**：top-k by risk（k=round(budget%×n)）与
   NOT_EVALUABLE / NOT_COMPARABLE_AT_TARGET 纪律的可视化。
3. **Reason Code → 解释模板对应表**（B 的 ABSTAIN 面板用，配合 schema_contract.md）。
4. **Review Budget 实验设计图**：746 错误全集 → 四策略排序 → 固定预算截获对比。
5. **PNG 导出**：本文件为 Mermaid 源，答辩/材料需要图片时用
   `npx @mermaid-js/mermaid-cli -i docs/architecture_diagrams.md -o docs/figures/`
   批量导出（图 1/2/4/6 最值得入片）。

> 图 2 的 reason code 与 `src/trust_engine/policy_router.py` 逐字一致；
> 图 3 的权重与 `configs/semifinal_main.yaml`（data 30 / single 24 / multi 37 /
> physics 40）及 `reliability.py` 的合成公式一致；图 6 的数字全部来自
> `results/` 冻结产物。
