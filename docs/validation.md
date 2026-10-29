# 测试说明

## 运行测试

以下命令从仓库根目录运行，要求 `python` 指向可用的 Python 3.12+。

只检查安装和更新保护：

```text
python -B -m unittest discover -s tests -p "test_installation.py" -v
```

运行全部辅助脚本测试：

```text
python -B -m unittest discover -s tests -v
```

涉及实际 LaTeX 编译的测试读取 `COURSEWORK_TEST_TECTONIC` 和 `COURSEWORK_TEST_PDFTOPPM` 环境变量。没有提供工具时，相应集成测试会跳过。需要时可为测试子进程另外设置 Tectonic 缓存和 Fontconfig 配置，不应把本机路径写进源码或提交到仓库。

## 测试范围

测试使用临时目录和合成作业材料，覆盖安装与更新保护、原文件保护、运行记录、结果复用、报告编译及失败恢复。

测试只能验证辅助脚本的行为。报告语言、算法思路和分析内容需要另外通过 Agent 的实际使用与独立审阅判断。
