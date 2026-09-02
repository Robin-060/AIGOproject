# 复赛 1 分钟 Demo Runbook

## 演示目标

在 60 秒内让评委确认三件事：系统消费真实冻结证据、参数变化调用真实后端、
失败与裁决边界在页面上可见。

## 开始前

- 提前启动 `bash scripts/run_demo.sh`，保留一个已打开的浏览器页面；
- 预先打开 Fixed Feedback 和 Case Explorer；
- 关闭更新弹窗、隐私通知和其他窗口；
- 准备离线备案：PPT 第 4、7、13 页和 `figures/` 中的图。

## 60 秒脚本

**0–15 秒：Review Efficiency**  
“这不是一个新拾取模型，而是一个可检查的 Trust Layer。在固定 50% 人工复核预算下，
Trust 排序截获 83.6% 错误，Random 为 50.0%。”

**15–30 秒：Safety Boundary**  
“EXP17-A 把 Coverage 从 45.64% 恢复到 54.13%。请看同一面板的 +2.24pp：
R1 的 PASS 只代表显式参数重跑一致，c2 仍是 NOT ESTABLISHED。”

**30–45 秒：Case Explorer**  
“这个 S 相反例中，FUSE 给出 142.61 秒，而 EQT 在 44.84 秒是正确的。
它说明多数一致不等于安全，因此必须保留 Safety Gate。”

**45–60 秒：真实后端反馈**  
“我现在修改一个允许的共识容差。页面不伪造指标，而是调用同一 Trust Engine 返回
action、risk 和 reason codes。”

## 故障备案

- 前端不可用：直接转 PPT 第 4 页（Review Curve）、第 7 页（EXP17）、第 13 页（反例）；
- 后端超时：保留错误提示，不口头声称未返回的科学数值；
- 网络中断：继续使用本地冻结产物，不下载模型或原始数据；
- 数字被追问：打开 `results/evidence_manifest.json` 或 `JUDGE_QUICKSTART.md`，不凭记忆更改口径。

## 演示后自检

- 是否在同一处同时说清 R1 PASS 和 c2 NOT ESTABLISHED；
- 是否把 Coverage 与 Unsafe、Interception 与 Review Burden 成对说明；
- 是否将传达结束在“可测、可控、可复现”，而不是“已可生产部署”。
