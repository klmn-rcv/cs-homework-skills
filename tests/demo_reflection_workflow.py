"""Retain actual source-only reports with explicitly synthetic reflection replies."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "skills/cs-homework/scripts/coursework.py"
FIXTURE = REPO / "tests/fixtures/report"


def latex_source(paragraphs):
    return r"""\documentclass[a4paper,11pt,UTF8,fontset=fandol]{ctexart}
\usepackage[margin=25mm]{geometry}
\pagestyle{plain}
\begin{document}
\section{问题与接口}
现有程序处理不变数组上的区间求和。\texttt{PrefixSum(values)} 接收数列，
\texttt{query(left,right)} 返回左闭右开区间 $[left,right)$ 的元素和。
本文只整理既有实现、固定样例与个人判断，不修改程序，不增加计时实验。
\section{方法与边界}
前缀数组以 $P[0]=0$ 起始，循环按 $P[k+1]=P[k]+a[k]$ 追加元素。
$P[k]$ 表示前 $k$ 项之和，因此区间和为 $P[right]-P[left]$。
构造长度为 $n+1$ 的列表需要 $O(n)$ 时间和额外空间；通常整数运算模型下查询为 $O(1)$，
Python 大整数成本还受位数影响。这是静态算法分析，没有实测耗时依据。
实现检查 $0\leq left\leq right\leq n$，不满足时抛出 \texttt{ValueError}；
异常分支本次未运行。$left=right$ 时相同前缀值相减得到零。
空输入会保留初始零且只允许 $[0,0)$，这是代码推导，不是本次新增测试。
\section{样例结果与解释}
固定输入 $[2,4,6,8]$ 的实际前缀为 $[0,2,6,12,20]$。
\begin{center}
\begin{tabular}{ccc}
区间 & 独立手算 & 实际输出 \\
$[0,4)$ & 20 & 20 \\
$[1,3)$ & 10 & 10 \\
$[2,2)$ & 0 & 0
\end{tabular}
\end{center}
全区间包含四个元素，和为20；中间区间只有4和6，和为10；空区间不含元素，和为零。
三项输出与独立手算一致，分别覆盖右端点等于数组长度、中间区间与空区间。
负数、越界与较大输入尚未运行，不能把本次结果扩大为所有输入都已验证，也不能据此评价速度。
\section{个人思考与限制}
""" + "\n\n".join(paragraphs) + "\n" + r"\end{document}" + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    workspace = root / "assignment"
    workspace.mkdir()
    for name in ["brief.md", "solution.py", "thoughts.md"]:
        shutil.copyfile(FIXTURE / name, workspace / name)
    context = {"assignment": {"title": "前缀和个人思考合成验证"},
               "request": "这是合成验证：基于已有前缀和代码和固定样例写可编辑报告源码，不要PDF，不改代码，不测时。已有思考够用时直接整理；另一个缺少思考的版本按实际依据给完整推荐，使用明确标注的合成回复演示更新。",
               "scope": {"goal": "有依据的报告源码及推荐/接受状态", "authorized_behaviors": ["report"]}}
    evidence = {"synthetic": True, "real_user_consent": False, "cases": []}

    def call(label, command, record):
        path = root / f"{label}-input.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        actual = subprocess.run([sys.executable, "-B", str(CLI), command, "--workspace", str(workspace), "--input", str(path)],
                                capture_output=True, text=True, encoding="utf-8")
        (root / f"{label}-stderr.txt").write_text(actual.stderr, encoding="utf-8")
        if actual.returncode:
            raise RuntimeError(actual.stderr)
        result = json.loads(actual.stdout)
        (root / f"{label}-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    expected = '{"values": [2, 4, 6, 8], "prefix": [0, 2, 6, 12, 20], "queries": [[0, 4], [1, 3], [2, 2]], "answers": [20, 10, 0]}' + os.linesep
    run = call("01-run", "run", {**context, "result_key": "required-prefix-example", "execution": {
        "argv": [sys.executable, "solution.py"], "source_paths": ["solution.py"], "input_paths": ["brief.md"],
        "purposes": ["correctness", "example"], "basis": "仅补充题目规定的固定输入，不增加实验",
        "report_support": {"basis": "brief.md固定数组[2,4,6,8]与三个区间[0,4)、[1,3)、[2,2)缺实际输出；仅补跑现有代码相同输入"},
        "dependency_coverage": {"status": "complete", "note": "读现有solution.py，仅标准库json和固定输入"},
        "expected": {"stdout": expected, "basis": "独立手算2+4+6+8=20，4+6=10，空区间0"}}})
    result_id = run["result"]["id"]

    def report(label, paragraphs, reflection=None, report_key="reflection"):
        stage = root / f"{label}.tex"
        stage.write_text(latex_source(paragraphs), encoding="utf-8")
        record = {**context, "report_key": report_key, "source_only": True, "main_file": "main.tex",
                  "files": [{"source": str(stage), "path": "main.tex"}], "source_paths": ["brief.md", "solution.py"], "result_ids": [result_id],
                  "content_review": {"requirement_map": [{"requirement": "方法、样例与个人限制", "source": "brief.md与实际运行", "location": "任务规定四节正文"}],
                    "structure_basis": "按brief.md四节：问题与接口、方法与边界、样例结果与解释、个人思考与限制；方法解释递推、边界与取舍",
                    "format_basis": "按brief.md仅采用A4/11pt/25mm/plain页码；ctexart Fandol；本次明确不要PDF",
                    "technical_review": "逐读当前代码与真实stdout，20/10/0独立手算；未加入未测事实",
                    "voice_review": "表达判断与未来计划，不编造个人调试、操作或感受",
                    "thoughts_basis": "直接整理已提供thoughts.md测试角色判断" if reflection is None else "完整段落来自精确reflection/questions；推荐与明确合成接受来源独立保存"}}
        if reflection is None:
            record["source_paths"].append("thoughts.md")
        else:
            record["reflection_sources"] = [{"reflection_id": reflection["id"], "question_ids": [q["id"] for q in reflection["questions"]]}]
        return call(label, "report", record)["report"]

    supplied = (workspace / "thoughts.md").read_text(encoding="utf-8").split("\n\n")[-1].strip()
    direct = report("02-existing-sufficient", [supplied], report_key="existing-thoughts")
    evidence["cases"].append({"case": "existing material sufficient: no interview", "report_id": direct["id"], "reflection_sources": direct["reflection_sources"]})

    questions = [
        {"id": "Q1", "question": "这三个样例通过后，你会怎样描述验证范围？",
         "recommendation": "我会把结论限定为这三个查询：它们分别覆盖全区间、中间区间和空区间，实际输出与独立手算一致。负数、越界和较大输入尚未运行，不能据此说所有情况均已验证。",
         "basis": f"真实result {result_id} stdout为20/10/0；brief.md固定三例，solution.py末尾仅这些查询", "source_paths": ["brief.md", "solution.py"], "result_ids": [result_id]},
        {"id": "Q2", "question": "为什么保留最前面的零，比把首个元素作为第一个前缀值更便于当前接口？",
         "background": "当前接口用P[right]-P[left]计算左闭右开区间；P[k]表示前k个元素之和。",
         "recommendation": "我倾向于保留初始零。这样左端点为零时仍能直接用相同的减法，空区间也由两个相同的前缀值相减得到零，不必为这两种情况增加求和分支。代价是前缀数组有n+1项。",
         "basis": "solution.py构造[0]与query的统一减法；实际全区间20和空区间0与该解释一致", "source_paths": ["solution.py"], "result_ids": [result_id]},
        {"id": "Q3", "question": "如果数组经常变化，你会怎样限定当前方法的适用性？",
         "recommendation": "当前实现适合数组不变而查询较多的情况。若修改元素，现有前缀值需要重新构建；我会先了解更新与查询的次数，再考虑是否需要支持更新的数据结构。本次没有测试动态更新，不评价替代结构的实测性能。",
         "basis": "solution.py只有构造和查询，无更新接口；当前运行仅固定数组，没有计时", "source_paths": ["solution.py"]}]
    prepared = call("03-prepare", "reflection", {**context, "reflection_key": "missing-thoughts", "need_basis": "另一个合成版本没有提供个人判断，报告仍需限制与取舍段落", "questions": questions})["reflection"]
    pending = report("04-unanswered-draft", [q["content"] for q in prepared["questions"]], prepared)
    evidence["cases"].append({"case": "unanswered complete recommendation paragraphs", "report_id": pending["id"], "status": pending["reflection_status"]})

    def reply(label, original, text, answers):
        return call(label, "reflection-reply", {**context, "reflection_id": original["id"],
                    "reply": {"text": text, "source": {"kind": "synthetic", "locator": f"demo_reflection_workflow.py:{label}; not real human consent"}}, "answers": answers})["reflection"]

    edited = "我倾向于保留初始零，使左端点为零和空区间都能使用同一减法。前缀数组有n+1项；只有一次查询时，直接遍历区间可能更简单。"
    partial = reply("05-accept-edit", prepared, "合成回复：接受Q1；Q2保留统一减法的说明，并补充只有一次查询时直接遍历可能更简单。Q3暂不回答。", [
        {"question_ids": ["Q1"], "action": "accept"}, {"question_ids": ["Q2"], "action": "edit", "answer": edited}])
    mixed = report("06-mixed-draft", [q["content"] for q in partial["questions"]], partial)
    evidence["cases"].append({"case": "accept/local edit and unanswered Q3", "report_id": mixed["id"], "status": mixed["reflection_status"]})
    alternative = "如果更新很少，先重新构建前缀数组也许已经足够；更新频繁时才值得比较其他结构。这个选择需要结合实际工作量，本次固定样例和未计时的结果不足以给出性能结论。"
    accepted = reply("07-replace", partial, "合成回复：Q3另答为“如果更新很少，先重新构建也许足够；更新频繁再比较其他结构，现有样例不能给出性能结论”。", [
        {"question_ids": ["Q3"], "action": "replace", "answer": alternative}])
    final = report("08-accepted-content", [q["content"] for q in accepted["questions"]], accepted)
    evidence["cases"].append({"case": "replacement and accepted attributed fixture content", "report_id": final["id"], "status": final["reflection_status"]})

    batch_questions = deepcopy(questions[:2])
    for question in batch_questions:
        question["id"] = "B" + question["id"][1:]
    batch = call("09-batch-prepare", "reflection", {**context, "reflection_key": "batch-example", "need_basis": "独立的批量回复合成分支，无真实人类判断", "questions": batch_questions})["reflection"]
    batch = reply("10-batch-accept", batch, "合成回复：一次接受B1和B2的两段推荐回答。", [{"question_ids": ["B1", "B2"], "action": "accept"}])
    batch_report = report("11-batch-report", [q["content"] for q in batch["questions"]], batch, report_key="batch")
    evidence["cases"].append({"case": "batch acceptance", "report_id": batch_report["id"], "status": batch_report["reflection_status"]})
    # An independent pending branch remains unanswered; silence never becomes acceptance.
    pending_questions = deepcopy(questions[:2])
    for question in pending_questions:
        question["id"] = "U" + question["id"][1:]
    unanswered = call("12-pending-prepare", "reflection", {**context, "reflection_key": "still-unanswered", "need_basis": "独立未回应合成分支，保留推荐状态供恢复与验收读取", "questions": pending_questions})["reflection"]
    unanswered_report = report("13-still-unanswered", [q["content"] for q in unanswered["questions"]], unanswered, report_key="unanswered")
    evidence["cases"].append({"case": "still unanswered after other independent work", "report_id": unanswered_report["id"], "status": unanswered_report["reflection_status"]})
    restored = subprocess.run([sys.executable, "-B", str(CLI), "resume", "--workspace", str(workspace)], capture_output=True, text=True, encoding="utf-8")
    if restored.returncode:
        raise RuntimeError(restored.stderr)
    (root / "14-fresh-resume.json").write_text(restored.stdout, encoding="utf-8")
    view = json.loads(restored.stdout)
    assert len(view["state"]["runs"]) == 1
    assert view["state"]["request"] == context["request"]
    assert next(r for r in view["reflections"] if r["id"] == unanswered["id"])["questions"][0]["status"] == "recommended"
    assert not prepared["questions"][0].get("background") and prepared["questions"][1]["background"]
    evidence.update(workspace=str(workspace), run_id=result_id, final_report_id=final["id"],
                    final_source=str(workspace / final["project"] / "main.tex"), source_only=True,
                    pdf_compilation="Not requested; no PDF authored or recompiled", real_run_count=1)
    (root / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
