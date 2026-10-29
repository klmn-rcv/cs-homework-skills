"""Derive the report's tables, plotted points and numeric macros from captured output."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out = Path(sys.argv[2])
data = json.loads(Path(manifest["inputs"][0]["path"]).read_text(encoding="utf-8"))
# Independent worked expectations from the fixture brief, not student implementation.
expected = [20, 10, 0]
if data["values"] != [2, 4, 6, 8] or data["queries"] != [[0, 4], [1, 3], [2, 2]]:
    raise ValueError("Wrong assignment example")
if data["prefix"] != [0, 2, 6, 12, 20] or data["answers"] != expected:
    raise ValueError("Output disagrees with independently worked example")
metrics = {**data, "expected": expected, "passed": 3, "cases": 3, "unit": "integer sum",
           "source_sha256": manifest["inputs"][0]["sha256"], "matplotlib": matplotlib.__version__}
(out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
table = [r"\begin{tabular}{rrrr}", r"\hline 区间 & 独立答案 & 实际输出 & 是否一致 \\", r"\hline"]
for (left, right), answer, oracle in zip(data["queries"], data["answers"], expected):
    table.append(f"$[{left},{right})$ & {oracle} & {answer} & 是 " + r"\\")
table += [r"\hline", r"\end{tabular}"]
(out / "table.tex").write_text("\n".join(table), encoding="utf-8")
macros = {"InputValues": ",".join(map(str, data["values"])), "PrefixValues": ",".join(map(str, data["prefix"])),
          "FullSum": data["answers"][0], "MiddleSum": data["answers"][1], "EmptySum": data["answers"][2],
          "PassedCases": metrics["passed"], "TotalCases": metrics["cases"]}
(out / "numbers.tex").write_text("\n".join("\\newcommand{\\" + key + "}{" + str(value) + "}" for key, value in macros.items()), encoding="utf-8")
fig, ax = plt.subplots(figsize=(5.6, 2.6), layout="constrained")
ax.plot(range(len(data["prefix"])), data["prefix"], "o-", color="#176c9c")
ax.set(xlabel="Prefix length k (elements)", ylabel="P[k] (integer sum)", xticks=range(5), yticks=[0, 2, 6, 12, 20])
ax.grid(alpha=0.25)
fig.savefig(out / "prefix.png", dpi=160)
fig.savefig(out / "prefix.pdf")
plt.close(fig)
(out / "analysis.md").write_text(
    f"固定样例的前缀值为 {data['prefix']}；三个查询输出为 {data['answers']}，"
    f"与独立手算答案 {expected} 全部一致。中间区间使用 P[3]-P[1]=12-2=10；空区间为 6-6=0。"
    "图仅展示同一数组的累计和，不是性能测量；三个样例不能证明所有输入正确，负数、越界异常和大输入未作本次执行验证。",
    encoding="utf-8")
