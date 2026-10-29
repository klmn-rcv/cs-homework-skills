"""Demo computation: describe a supplied CSV, never claim these are fresh measurements."""
import csv
import json
import math
from pathlib import Path
import platform
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt


manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output = Path(sys.argv[2])
with Path(manifest["inputs"][0]["path"]).open(encoding="utf-8", newline="") as stream:
    reader = csv.DictReader(stream)
    if reader.fieldnames != ["n", "elapsed_ms"]:
        raise ValueError("Need explicit n,elapsed_ms columns; units must be confirmed before analysis")
    rows = list(reader)
if not rows:
    raise ValueError("No data rows; do not invent values")
x, y = [], []
for row in rows:
    a, b = float(row["n"]), float(row["elapsed_ms"])
    if not math.isfinite(a) or not math.isfinite(b) or b < 0:
        raise ValueError("Missing, non-finite or negative duration; inspect the original row")
    x.append(a)
    y.append(b)
metrics = {"count": len(rows), "total_ms": sum(y), "mean_ms": sum(y) / len(y),
           "min_ms": min(y), "max_ms": max(y),
           "source_sha256": manifest["inputs"][0]["sha256"],
           "python": platform.python_version(), "matplotlib": matplotlib.__version__}
(output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
with (output / "table.csv").open("w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["n", "elapsed_ms"])
    writer.writerows(zip(x, y))
fig, ax = plt.subplots(figsize=(6, 4), layout="constrained")
ax.plot(x, y, "o-", color="#176c9c", linewidth=1.5)
ax.set(xlabel="n (count)", ylabel="Supplied elapsed time (ms)",
       title="Supplied example data")
ax.grid(alpha=0.25)
fig.savefig(output / "figure.png", dpi=160)
fig.savefig(output / "figure.pdf")
plt.close(fig)
note = manifest["parameters"]["provenance_note"]
text = f'''# 已有数据分析

来源与范围：{note}。数据来自同一份已归档 CSV，生成过程未独立复核；图和表中的每个点都对应这份 CSV 的一行，没有新增实验。

观察：共有 {metrics['count']} 行，n 从 {min(x):g} 到 {max(x):g}，提供的 elapsed_ms 从 {min(y):g} 到 {max(y):g} ms。检查中未发现缺失、非有限或负的耗时值；每个 n 只有一行，缺少重复样本和运行环境。

计算结果：这些行的耗时总和为 {metrics['total_ms']:g} ms，算术平均值为 {metrics['mean_ms']:g} ms。表格保留原始两列，图的横轴为 n，纵轴单位为 ms；指标见 metrics.json。

解释与限制：这些数值只描述给出的行，回答了当前“整理已有数据”的目标。单次、不同 n 的样本不能提供重复测量的误差估计，也不能据此确认算法复杂度、一般性能或因果关系。若需要这些判断，应先明确新增实验范围、重复次数和环境条件。

未确认事项：实际生成命令、源码版本、硬件和计时方法未提供。没有将外部数据写成工作流新执行的测量。
'''
(output / "analysis.md").write_text(text, encoding="utf-8")
print(json.dumps({"count": metrics["count"], "mean_ms": metrics["mean_ms"]}))
