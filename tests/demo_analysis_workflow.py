"""Retained actual plotting demo; requires a Python with Matplotlib via --plot-python."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "skills/cs-homework/scripts/coursework.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plot-python", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.output or Path(tempfile.mkdtemp(prefix="coursework-analysis-demo-"))
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / "assignment"
    workspace.mkdir()
    script = root / "compute.py"
    shutil.copyfile(REPO / "tests/fixtures/analysis/plot_supplied_data.py", script)
    source = root / "provided.csv"
    source.write_text("n,elapsed_ms\n1,2\n2,4\n3,6\n4,8\n", encoding="utf-8")
    independent = root / "independent.csv"
    independent.write_text("n,elapsed_ms\n1,10\n2,20\n", encoding="utf-8")
    context = {"assignment": {"title": "只分析已有数据"}, "request": "只整理提供的数据、计算指标、画图并说明限制，不新增实验、不修改程序。",
               "scope": {"goal": "独立分析已有数据", "authorized_behaviors": ["analyze"]}}

    def command(name, record):
        path = root / "input.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        actual = subprocess.run([sys.executable, "-B", str(CLI), name, "--workspace", str(workspace), "--input", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        if actual.returncode:
            raise RuntimeError(actual.stderr)
        return json.loads(actual.stdout)

    def external(key, path):
        return command("import-result", {**context, "result_key": key, "data_paths": [str(path)],
                       "provenance": {"provided_by": "test fixture", "location": str(path),
                                      "description": "已知算术示例数据，用于验证分析一致性；并非课程程序的真实测时"}})["result"]

    def analyze(key, result):
        return command("analyze", {**context, "analysis_key": key,
                       "inputs": [{"result_id": result["id"], "path": result["data"][0]["snapshot_path"]}],
                       "assessment": {"goal": "描述给定数据，不推断算法复杂度", "completeness": "n与elapsed_ms列完整，各n仅1条，无环境和重复记录",
                                      "units": "n为计数，elapsed_ms为毫秒", "anomalies": "已读原始四行，未发现缺失或负数；脚本另检查有限数",
                                      "limitations": "测试用已知示例数据，不是真实课程测量，不能产生性能/因果结论"},
                       "computation": {"python": args.plot_python, "script": str(script),
                                       "basis": "原始行经独立已知答案核对：初版总20/均值5，更新总40/均值10；另组均值15",
                                       "parameters": {"provenance_note": "已知算术示例数据，不是真实测时"},
                                       "products": [{"path": "metrics.json", "kind": "metrics"}, {"path": "table.csv", "kind": "table"},
                                                    {"path": "figure.png", "kind": "figure"}, {"path": "figure.pdf", "kind": "figure"},
                                                    {"path": "analysis.md", "kind": "analysis"}]}})

    first = analyze("provided", external("provided", source))
    other = analyze("independent", external("independent", independent))
    other_bytes = {p["path"]: hashlib.sha256((workspace / p["path"]).read_bytes()).hexdigest() for p in other["analysis"]["products"]}
    source.write_text("n,elapsed_ms\n1,4\n2,8\n3,12\n4,16\n", encoding="utf-8")
    final = analyze("provided", external("provided", source))
    for result, expected in [(first, 5), (other, 15), (final, 10)]:
        product = next(p for p in result["analysis"]["products"] if p["kind"] == "metrics")
        assert json.loads((workspace / product["path"]).read_text())["mean_ms"] == expected
    assert final["state"]["analysis_heads"]["independent"] == other["analysis"]["id"]
    assert all(hashlib.sha256((workspace / path).read_bytes()).hexdigest() == digest for path, digest in other_bytes.items())
    assert not final["needs_review"]
    assert not final["state"].get("runs") and "plan" not in final["state"]
    evidence = {"workspace": str(workspace), "first": first["analysis"], "independent": other["analysis"], "updated": final["analysis"],
                "independent_unchanged_hashes": other_bytes, "checks": "Known means 5,15,10; independent group unchanged; historical files retained; no course execution or planning"}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"root": str(root), "evidence": str(root / "evidence.json"), "updated_products": final["analysis"]["products"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
