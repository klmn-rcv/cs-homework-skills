"""Retain a real Chinese LaTeX report for semantic and actual-page review."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/report"
CLI = REPO / "skills/cs-homework/scripts/coursework.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plot-python", required=True)
    parser.add_argument("--latex", required=True)
    parser.add_argument("--pdftoppm", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "assignment"
    workspace.mkdir()
    for name in ["solution.py", "brief.md", "thoughts.md", "unrelated-template.tex"]:
        shutil.copyfile(FIXTURE / name, workspace / name)
    stage = root / "stage"
    stage.mkdir()
    shutil.copyfile(FIXTURE / "main.tex", stage / "main.tex")
    context = {"assignment": {"title": "静态区间求和报告"},
               "request": "按给定已有实现和思考写报告；缺少任务规定样例结果时补跑同一程序，不修改实现，不加测时实验。",
               "scope": {"goal": "可编辑LaTeX项目与实际PDF", "authorized_behaviors": ["report"]}}

    def command(name, record):
        path = root / f"{name}-input.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        actual = subprocess.run([sys.executable, "-B", str(CLI), name, "--workspace", str(workspace), "--input", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        if actual.returncode:
            raise RuntimeError(actual.stderr)
        result = json.loads(actual.stdout)
        (root / f"{name}-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    # Existing-code supplement is exactly the brief's required three queries, not a parameter scan.
    expected = '{"values": [2, 4, 6, 8], "prefix": [0, 2, 6, 12, 20], "queries": [[0, 4], [1, 3], [2, 2]], "answers": [20, 10, 0]}' + os.linesep
    run = command("run", {**context, "result_key": "required-prefix-example", "execution": {
        "argv": [sys.executable, "solution.py"], "source_paths": ["solution.py"], "input_paths": ["brief.md"],
        "purposes": ["correctness", "example"], "basis": "brief.md第3段指定固定数组与三个查询，独立答案20/10/0",
        "report_support": {"basis": "报告缺少brief.md第3段规定的三个样例执行证据；仅运行现有solution.py中相同固定数组和查询，不增加输入/计时/参数扫描"},
        "dependency_coverage": {"status": "complete", "note": "已读程序，仅依赖Python标准库json与内置固定值；brief保存独立期望"},
        "expected": {"stdout": expected, "exit_code": 0, "basis": "前缀手算0,2,6,12,20；完整和20，中间4+6=10，空区间0"}}})
    result = run["result"]
    analysis = command("analyze", {**context, "analysis_key": "required-prefix-example",
        "inputs": [{"result_id": result["id"], "path": run["run"]["execution"]["stdout"]["path"]}],
        "assessment": {"goal": "任务规定的前缀图、三个查询结果表与同源数字宏", "completeness": "固定四元素数组与三个查询完整，无计时记录",
                       "units": "横轴为元素个数，纵轴为整数累计和；没有时间单位", "anomalies": "全部前缀值和查询答案与独立手算一致",
                       "limitations": "只验证固定样例；负数、空输入、越界异常和大输入未实际运行，不推断测时或普遍正确性"},
        "computation": {"python": args.plot_python, "script": str(FIXTURE / "compute.py"),
                        "basis": "图、表、数字宏和说明读取同一份精确运行stdout；独立答案20/10/0",
                        "capture_env": ["MPLCONFIGDIR", "MPLBACKEND", "MPL_IGNORE_SYSTEM_FONTS"],
                        "products": [{"path": p, "kind": k} for p, k in [("metrics.json", "metrics"), ("table.tex", "table"),
                            ("numbers.tex", "table"), ("prefix.png", "figure"), ("prefix.pdf", "figure"), ("analysis.md", "analysis")]]}})["analysis"]
    products = {Path(p["path"]).name: p for p in analysis["products"]}
    metrics = json.loads((workspace / products["metrics.json"]["path"]).read_text(encoding="utf-8"))
    assert metrics["prefix"] == [0, 2, 6, 12, 20] and metrics["answers"] == [20, 10, 0]
    files = [{"source": str(stage / "main.tex"), "path": "main.tex"}]
    for name in ["numbers.tex", "table.tex", "prefix.pdf"]:
        product = products[name]
        files.append({"source": str(workspace / product["path"]), "path": "assets/" + name, "artifact_id": product["artifact_id"]})
    report = command("report", {**context, "report_key": "prefix-sums", "main_file": "main.tex", "files": files,
        "source_paths": ["brief.md", "solution.py", "thoughts.md", "unrelated-template.tex"],
        "result_ids": [result["id"]], "analysis_ids": [analysis["id"]], "artifact_ids": [p["artifact_id"] for p in analysis["products"]],
        "compiler": {"engine": "tectonic", "executable": args.latex, "capture_env": ["TECTONIC_CACHE_DIR", "FONTCONFIG_FILE"]},
        "renderer": {"executable": args.pdftoppm, "dpi": 120},
        "content_review": {
            "requirement_map": [{"requirement": "手写前缀和、接口、边界和复杂度取舍", "source": "brief.md:3; solution.py:5-15", "location": "方法与边界"},
                                {"requirement": "固定样例和图表", "source": "brief.md:5; 当前真实运行stdout", "location": "样例结果与解释"},
                                {"requirement": "指定四节结构、格式仅参考、已有思考", "source": "brief.md:7; thoughts.md:5", "location": "四节与个人思考"}],
            "structure_basis": "严格按brief最后一段四节；方法部分篇幅最多，解释递推、消去、空区间、非法边界和取舍；不取格式样例的地质章节或段落结构",
            "format_basis": "unrelated-template.tex仅取A4/11pt/25mm/plain页码；为中文使用ctexart Fandol；未复制Marine Sediment示例内容",
            "technical_review": "逐读PrefixSum实现；公式与操作对应；20/10/0和前缀手算核对；未运行的异常、空输入、负数、大输入仅说明静态推导或未覆盖；图非性能曲线",
            "voice_review": "正文客观、术语适度；解释具体方法而无空泛意义、推广或杜撰调试经历；个人思考使用给定测试角色文字",
            "thoughts_basis": "直接复用thoughts.md已有段落，无新推荐、空白或未经确认的接受状态"}})["report"]
    assert report["status"] == "awaiting_review", report
    assert report["pages"] and not report["diagnostics"]["undefined_reference"]
    evidence = {"workspace": str(workspace), "run_id": result["id"], "analysis_id": analysis["id"], "report_id": report["id"],
                "pdf": str(workspace / report["pdf"]["path"]), "project": str(workspace / report["project"]),
                "pages": [str(workspace / p["path"]) for p in report["pages"]], "review_pending": True}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
