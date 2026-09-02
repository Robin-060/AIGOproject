import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const [inputPath, outputPath] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("usage: revise_final_pptx.mjs INPUT.pptx OUTPUT.pptx");
}
if (path.resolve(inputPath) === path.resolve(outputPath)) {
  throw new Error("Refusing to overwrite the source PPTX");
}

const deck = await PresentationFile.importPptx(await FileBlob.load(inputPath));
const evidenceDoc = "docs/deliverables/10c 部分 GOAI_OBS_科研边界与实验契约_v1.10_包装验收与发布版.docx";
const common = [
  "[Sources]",
  `- ${evidenceDoc}`,
  "- docs/final_report.md",
];
const slideSpecific = [
  "- 封面数字来自 EXP16 与 EXP17 最终冻结结果。",
  "- RQ2 为 policy ceiling 诊断后形成的派生研究问题。",
  "- Review CI 为 Trust−Random @50%；Safety 为配对 station-cluster bootstrap。",
  "- EXP16 全量 Review Budget–Error Interception Curve；50% baselines: Random 50.0%, ModelConf 59.9%, Disagreement 56.3%。",
  "- EXP16 holdout Primary evaluation universe: n=260, errors=161；358 为全部 manifest holdout。",
  "- Policy ceiling reason decomposition: 703 / 487 / 112 / 57；312 与 89 仅用于事后诊断。",
  "- EXP17-A: Coverage 54.13%, Unsafe 5.51%, Error Interception 94.26%；one-sided upper +2.24pp。",
  "- Scientific Claim 不声称 CI-level safety non-inferiority 已建立。",
  "- 结论综合冻结成果层级。",
  "- v1.5.1 frozen result: 596 valid outputs, Coverage 45.64%, Unsafe 6.04%。",
  "- EXP17 protocol 为 post-hoc、failure-driven，不是原始预声明实验。",
  "- EXP17-A 只使用 truth-blind inference-time evidence。",
  "- v1.5.1 shared-error case: XO.LT04..HH.2018.07.12.08.32.02。",
  "- EXP17-B: Coverage 81.62%, c2 upper +4.87pp fail, c3 64.55% fail；参数审计使用 P=.34s/S=.51s。",
  "- 显式参数重跑完全复现 54.13% / 5.51% / 94.26%，upper +2.24pp，76/76 tests passed。\n- https://zenodo.org/records/10277799\n- https://github.com/seisbench/seisbench\n- THIRD_PARTY_NOTICES.md",
  "- No-Go 保留 post-hoc EXP17 边界；CI 级非劣仍需更大样本。",
];

for (const [index, slide] of deck.slides.items.entries()) {
  slide.speakerNotes.textFrame.setText([
    ...common,
    slideSpecific[index] ?? "- 页面数字以冻结 evidence manifest 为准。",
    "[/Sources]",
  ].join("\n"));
  slide.speakerNotes.setVisible(true);
}

const before = await deck.inspect({
  kind: "textbox,shape",
  search: "goai-2026-final-v2",
  maxChars: 12000,
});
const records = before.ndjson.trim().split("\n").filter(Boolean).map((line) => JSON.parse(line));
const targetRecord = records.find((record) => record.id && JSON.stringify(record).includes("goai-2026-final-v2"));
if (!targetRecord) {
  throw new Error("Could not locate the visible release tag on slide 15");
}
const target = deck.resolve(targetRecord.id);
target.text.replace("goai-2026-final-v2", "goai-2026-final-v3");

const internalLabels = await deck.inspect({
  kind: "textbox,shape",
  search: "A/B a6c5f1f|C 审核 003a1e7",
  maxChars: 12000,
});
for (const line of internalLabels.ndjson.trim().split("\n").filter(Boolean)) {
  const record = JSON.parse(line);
  if (!record.id) continue;
  const shape = deck.resolve(record.id);
  shape.text.replace("A/B a6c5f1f", "工程提交 a6c5f1f");
  shape.text.replace("C 审核 003a1e7", "证据审阅 003a1e7");
  shape.text.replace("C 审校 003a1e7", "证据审阅 003a1e7");
}

const disclosure = await deck.inspect({
  kind: "textbox,shape",
  search: "权重不随仓库分发。正式发布",
  maxChars: 12000,
});
for (const line of disclosure.ndjson.trim().split("\n").filter(Boolean)) {
  const record = JSON.parse(line);
  if (!record.id) continue;
  deck.resolve(record.id).text.replace(
    "权重不随仓库分发。正式发布",
    "权重不随仓库分发。\n正式发布",
  );
}

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const exported = await PresentationFile.exportPptx(deck);
await exported.save(outputPath);

const verify = await deck.inspect({
  kind: "textbox,shape,notes",
  search: "goai-2026-final-v3|/" + "Users/|Desktop/",
  maxChars: 20000,
});
await fs.writeFile("/private/tmp/goai-ppt-packaging-inspect.ndjson", verify.ndjson);
