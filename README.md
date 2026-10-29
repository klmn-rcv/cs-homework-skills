# cs-homework-skills

面向计算机课程作业的模块化 AI Skills，支持要求梳理、代码实现、程序运行、结果分析、LaTeX 报告与独立审阅，可单独使用或按需组合。

把作业目录、任务材料和本次目标交给 Agent，由它接手需要完成的部分。材料可以是多份本地文件、在线文档和聊天补充。已有代码或有效结果可以继续使用，不必从头走完整套流程。

## 包含哪些 Skills

| Skill | 用途 |
| --- | --- |
| `cs-homework` | 总入口，根据当前目标和已有成果选择所需行为 |
| `cs-homework-plan` | 阅读材料，梳理要求、限制、待确认问题和实施计划 |
| `cs-homework-code` | 实现或修复程序，进行必要的正确性验证 |
| `cs-homework-run` | 运行已有程序、测试或实验，保存实际命令与输出 |
| `cs-homework-analyze` | 分析已有数据和运行结果，计算指标、制作图表 |
| `cs-homework-report` | 撰写或修改课程报告，交付可编辑 LaTeX 项目及所需 PDF |
| `cs-homework-report-review` | 独立审阅报告，检查语言、内容组织、详略和页面 |
| `cs-homework-check` | 按当前目标验收代码、运行记录、分析或报告 |

八个目录需要相邻安装，因为它们会引用共享指导和其他入口。使用时可以只调用其中一个 Skill。

## 使用示例

将示例路径换成实际作业目录和材料位置。示例采用 `$SkillName` 调用形式，其他宿主按其约定调用相应 Skill。

**完成整份作业：**

```text
$cs-homework 阅读 D:/课程/作业二 中的材料，按要求完成代码、运行和报告。
LaTeX 模板只供参考格式，报告结构按作业要求确定。
```

**只写代码：**

```text
$cs-homework-code 按 D:/课程/图算法 中的要求实现程序并验证正确性，不写报告。
```

**只生成报告：**

```text
$cs-homework-report 代码和实验结果已经在 D:/课程/作业二 中。
只用已有材料生成报告，不修改代码、不重跑实验。
本次报告要求 4—7 页，交付 LaTeX 项目和实际编译的 PDF。
```

**只审阅，不修改：**

```text
$cs-homework-report-review 阅读 D:/课程/作业二/report 中的报告，
指出具体问题并给出修改建议，不修改文件、不运行或编译。
```

也可以从已有作业继续，直接说明上次做到哪里、本次要交付什么。Agent 会读取目录中的实际文件和交接记录。

## 工作方式

- **按本次范围执行。** 只要求代码、运行、分析或报告时，不自动扩展为完整作业。明确的只读、不执行和阶段检查点持续有效。
- **保留真实过程。** 运行记录关联实际代码、输入、参数和输出。报告根据已有依据展开，不编造实验、调试经历或个人感受。
- **重视报告表达。** 使用学生视角，讲清实现和结果，保留必要衔接。逐项追加的多余解释、评价、纠正或限定，按当前规则直接删除。结构和篇幅由具体任务决定，LaTeX 样例只提供格式。
- **独立审阅并按问题修订。** 完整报告交给其他上下文审阅，按实际问题持续修改和复审，结束前另作新的独立全文审阅。
- **自动管理本地 Git。** 写入任务自动建立或沿用仓库，保护已有文件和用户修改，提交本任务成果。不会自行推送仓库或提交课程平台。

具体写作要求见 [共享报告质量标准](skills/cs-homework/references/report-quality.md)，审阅流程见 [报告审阅 Skill](skills/cs-homework-report-review/SKILL.md)。

## 安装

适用于支持 Skills、文件操作和命令执行的 AI 编程 Agent。完整报告流程需要独立上下文审阅能力。

准备好可用的 Python 3.12+，下载或克隆本仓库后，在仓库根目录执行安装。以下 PowerShell 命令以 `.codex/skills` 为例，假设 `python` 指向该解释器。请按所用 Agent 的要求调整安装目录。

先查看复制计划，再应用：

```powershell
$homeworkSkillsDir = Join-Path $HOME ".codex/skills"
python -B scripts/install_skills.py --dest $homeworkSkillsDir
python -B scripts/install_skills.py --dest $homeworkSkillsDir --apply
```

安装脚本只管理八个 `cs-homework*` 目录，不修改宿主配置、全局 PATH 或 Python 包。它会记录安装文件的摘要，更新时保护个人附加文件。已有同名非托管目录，或已安装文件被手动修改时，脚本会停止，需先检查差异。

### 报告语言依赖

报告写作默认使用 [Humanizer](https://github.com/blader/humanizer) 3.1.0。仓库在 `external-skills/humanizer/` 保存了固定版本的完整原文、许可证和来源记录。只编程、运行或分析时不需要这个报告依赖。

安装报告能力时，还需将该目录复制为与 `cs-homework` 相邻的 `humanizer` 目录。安装脚本不会自动执行这一步。下面的命令遇到已有安装会停止，避免覆盖：

```powershell
$humanizerDir = Join-Path $homeworkSkillsDir "humanizer"
if (Test-Path -LiteralPath $humanizerDir) {
    throw "humanizer 已存在，请先核对其版本和个人修改。"
}
Copy-Item -LiteralPath "./external-skills/humanizer" -Destination $humanizerDir -Recurse
```

### 工具与其他宿主

具体课程需要相应的编译器或运行环境。生成 PDF 还需要 LaTeX 编译器、所需字体及 PDF 页面渲染工具，绘图按任务使用可用工具。这些工具不随 Skill 自动安装。

审阅模型由宿主配置或用户选择确定，不要求特定厂商或型号。审阅者需要独立执行上下文，可由子 Agent 或独立新会话承担。

## 仓库结构

```text
skills/           八个 Skill 入口、共享指导和可选辅助脚本
external-skills/  固定版本的第三方语言依赖
scripts/          本地安装与更新脚本
tests/            辅助脚本和工作流的测试及合成材料
docs/             参考来源和测试说明
```

日常使用主要看 `skills/`，`docs/` 说明参考来源、依赖和测试方式。

辅助脚本用于保存和核对运行事实，可以按需使用。算法、报告语言和分析是否合理，仍需要 Agent 实际阅读与判断。

## 测试

安装保护测试可以单独运行：

```powershell
python -B -m unittest discover -s tests -p "test_installation.py" -v
```

完整测试命令、LaTeX 集成测试的工具配置及测试范围见 [测试说明](docs/validation.md)。

## 来源与许可

设计参考、实际依赖及适配方式见 [参考记录](docs/skill-references.md)。Humanizer 的 MIT 许可证保留在 [第三方许可证](external-skills/humanizer/LICENSE)，固定版本及摘要见 [来源记录](external-skills/humanizer/origin.json)。

本项目原创内容采用 [MIT 许可证](LICENSE)。随附 Humanizer 保留其原有 MIT 许可证及版权声明，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。
