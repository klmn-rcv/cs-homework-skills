"""Review an existing Chinese report, then apply authored prose using real LaTeX.

Uses an existing ticket06 demo's recorded output/assets without rerunning coursework.
Leaves actual semantic and rendered-page acceptance for the reviewing agent.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests/fixtures/report-prose"
CLI = REPO / "skills/cs-homework/scripts/coursework.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-demo", type=Path, required=True)
    parser.add_argument("--latex", required=True)
    parser.add_argument("--pdftoppm", required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "assignment"
    workspace.mkdir()
    original = args.prior_demo.resolve()
    prior_report = json.loads((original / "report-final-output.json").read_text(encoding="utf-8"))["report"]
    prior_run = json.loads((original / "run-output.json").read_text(encoding="utf-8"))
    assets = original / "assignment" / prior_report["project"] / "assets"
    shutil.copytree(assets, workspace / "assets")
    shutil.copyfile(FIXTURE / "original.tex", workspace / "main.tex")
    for name in ["brief.md", "solution.py", "thoughts.md"]:
        shutil.copyfile(original / "assignment" / name, workspace / name)
    output = original / "assignment" / prior_run["run"]["execution"]["stdout"]["path"]
    shutil.copyfile(output, workspace / "recorded-output.json")
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["prefix"] == [0, 2, 6, 12, 20] and data["answers"] == [20, 10, 0]

    def command(label, name, record):
        path = root / f"{label}-input.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        actual = subprocess.run([sys.executable, "-B", str(CLI), name, "--workspace", str(workspace), "--input", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        if actual.returncode:
            raise RuntimeError(actual.stderr)
        result = json.loads(actual.stdout)
        (root / f"{label}-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def bytes_by_path():
        return {p.relative_to(workspace).as_posix(): p.read_bytes() for p in workspace.rglob("*") if p.is_file()}

    comparisons = [
        {"before": "在信息技术日新月异的时代，算法设计具有重要意义。", "after": "",
         "basis": "泛泛时代背景和重要性评价没有独立作业信息；下一句保留固定数组上的区间求和任务。"},
        {"before": "值得强调的是，据随附记录", "after": "据随附记录",
         "basis": "删去强调引导语，保留提供者归因、引用键和没有独立重跑的状态。"},
        {"before": "三个给定查询均与独立手算一致。换言之，这三个给定查询都得到了与独立手算相同的结果。",
         "after": "三个给定查询均与独立手算一致。", "basis": "两句的对象、数量和判定依据完全相同，合并重复，限定只支持所列样例仍在。"},
        {"before": "可以说，这充分彰显了本次实验的重要价值。", "after": "",
         "basis": "无独立信息的拔高收尾；数据、未测时、输入范围及后续计划分别完整保留。"}]
    review = {"request": "只审校已有main.tex，给具体建议，不改文件。",
        "scope": {"goal": "已有报告语言建议", "authorized_behaviors": ["report"], "report_mode": "review"},
        "sources": [{"path": "main.tex", "sha256": hashlib.sha256((workspace / "main.tex").read_bytes()).hexdigest()}],
        "reading_basis": "通读四节报告与技术限定；公式、接口、样例、归因、未测时和计划状态逐段核对。",
        "advice": [{"kind": "style", "path": "main.tex", "quote": c["before"], "suggestion": c["after"] or "删除这句。", "basis": c["basis"]} for c in comparisons] + [
            {"kind": "retain", "path": "main.tex", "quote": "首先构建前缀数组，其次处理区间查询。",
             "suggestion": "保留原句。", "basis": "连接词表示真实构建和查询的先后顺序。"}]}
    before = bytes_by_path()
    command("advice", "review-prose", review)
    assert before == bytes_by_path() and not (workspace / ".git").exists()

    # A second, explicit human request fixture authorizes edits. Internal calls keep it unchanged.
    context = {"assignment": {"title": "已有前缀和报告润色"},
        "request": "按已有结构润色main.tex，不改技术内容、个人思考或数据；交付LaTeX与PDF，不重跑程序。",
        "scope": {"goal": "润色后的可编辑项目与当前PDF", "authorized_behaviors": ["report"], "report_mode": "polish"}}
    result = command("provided", "import-result", {**context, "result_key": "provided-prefix-output",
        "data_paths": ["recorded-output.json", "assets/numbers.tex", "assets/table.tex", "assets/prefix.pdf"],
        "provenance": {"provided_by": "existing ticket06 demonstration", "location": str(original),
            "description": "原run_id=" + prior_run["run"]["id"] + "; report_id=" + prior_report["id"] + "; exact copied output/assets; generating run not repeated in this edit"}})["result"]
    stage = root / "stage"
    stage.mkdir()
    shutil.copyfile(FIXTURE / "polished.tex", stage / "main.tex")
    shutil.copytree(workspace / "assets", stage / "assets")
    report = command("polished", "report", {**context, "report_key": "prefix-prose", "main_file": "main.tex",
        "files": [{"source": str(stage / p), "path": p} for p in ["main.tex", "assets/numbers.tex", "assets/table.tex", "assets/prefix.pdf"]],
        "source_paths": ["main.tex", "brief.md", "solution.py", "thoughts.md", "recorded-output.json", "assets/numbers.tex", "assets/table.tex", "assets/prefix.pdf"],
        "result_ids": [result["id"]], "analysis_ids": [], "artifact_ids": [],
        "compiler": {"engine": "tectonic", "executable": args.latex, "args": ["--only-cached"], "capture_env": ["TECTONIC_CACHE_DIR", "FONTCONFIG_FILE"]},
        "renderer": {"executable": args.pdftoppm, "dpi": 120},
        "content_review": {"requirement_map": [{"requirement": "保留原有四节、技术内容与思考，仅改语言", "source": "当前请求; main.tex全文; brief.md四节要求", "location": "main.tex全文"}],
            "structure_basis": "四节标题、层级及先方法后结果和思考的组织逐字保留。",
            "format_basis": "保留原稿ctexart、25mm页边距和图表布局；不从其他样例采内容。",
            "technical_review": "读过solution.py与真实归档stdout；20/10/0手算一致；未重跑来源仍属提供结果，保留通常整数模型、大整数成本、仅所列样例、负数/异常/大输入未验证、未测ms耗时、静态条件及未来可能比较状态。",
            "voice_review": "只删冗余铺垫、重复和无信息拔高；自然的首先/其次及原个人思考保留，无新增经历。",
            "thoughts_basis": "原稿个人思考与thoughts.md文字一致，润色完全未修改，也不新增接受记录。",
            "prose_review": {"changes": comparisons, "comparison_basis": "已逐段对照两份模型写好的源码；四处表达编辑没有独立信息损失；公式/代码/cite/ref/label/图表/数据完全保留。字节比较仅作辅助，页面尚待实际审阅。"}}})["report"]
    assert report["status"] == "awaiting_review", report
    assert not report["diagnostics"]["undefined_reference"] and report["pages"]
    assert before == {p: (workspace / p).read_bytes() for p in before}
    for name in ["numbers.tex", "table.tex", "prefix.pdf"]:
        assert (workspace / "assets" / name).read_bytes() == (workspace / report["project"] / "assets" / name).read_bytes()
    evidence = {"workspace": str(workspace), "report_id": report["id"], "provided_result_id": result["id"],
        "prior_run_id": prior_run["run"]["id"], "source": str(workspace / "main.tex"), "edited_source": str(workspace / report["project"] / "main.tex"),
        "pdf": str(workspace / report["pdf"]["path"]), "pages": [str(workspace / p["path"]) for p in report["pages"]],
        "advice_preserved_assignment_bytes": True, "semantic_and_page_acceptance_pending": True}
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
