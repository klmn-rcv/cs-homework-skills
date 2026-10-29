# 参考来源与第三方依赖

本文件区分实际随仓库分发的依赖与设计时阅读的资料。参考某项方法，不表示自动安装或调用它的完整工作流。

## 实际依赖：Humanizer

报告语言编辑默认使用 [blader/humanizer](https://github.com/blader/humanizer) 3.1.0，固定提交为 `8c307f367c91bd974002f10f2be2965d642c13df`，许可证为 MIT。

完整上游文件保存在 [external-skills/humanizer](../external-skills/humanizer/SKILL.md)，没有改写上游正文。许可证与来源摘要分别见 [LICENSE](../external-skills/humanizer/LICENSE) 和 [origin.json](../external-skills/humanizer/origin.json)。

课程报告的学生视角、编辑范围及删除硬规统一由 [report-prose.md](../skills/cs-homework/references/report-prose.md) 和 [report-quality.md](../skills/cs-homework/references/report-quality.md) 规定。发生冲突时执行课程适配规则，不把上游的信息保留偏好当作附注必须保留的理由。

安装脚本只管理 cs-homework 系列，Humanizer 需另行安装。仅编程、运行或分析不需要报告语言依赖。

## 设计参考

| 来源 | 参考方向 |
| --- | --- |
| [Matt Pocock Skills](https://github.com/mattpocock/skills) | 需求澄清、测试、故障诊断、代码审阅及面向 Agent 的指导写法 |
| [course-lab-report](https://github.com/c0ffee-milk/course-lab-report) | 课程报告的内容组织和学生叙述 |
| [lab-report-craft](https://github.com/Rtiming/lab-report-craft) | 结果、图表和报告之间的对应关系及实际页面检查 |
| [technical-writer](https://github.com/riekelt/technical-writer) | 面向读者说明方法与过程 |
| [planning-loop](https://github.com/robjsliwa/skills) | 使用文件衔接不同阶段的工作 |
| [Humanizer-zh](https://github.com/op7418/Humanizer-zh) | 中文表达与句式的编辑方法 |
| [Stop Slop](https://github.com/hardikpandya/stop-slop) | 删除铺垫、重复评价和多余叙述的思路 |
| [avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) | 结合上下文判断表达是否需要改写，以及句段之间的承接 |

除 Humanizer 外，上述项目未作为完整第三方 Skill 随本仓库分发，也不是运行所有课程行为的必装依赖。是否另行使用其他 Skill，应服从当前任务与使用者的选择。
