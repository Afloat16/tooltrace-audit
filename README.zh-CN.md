# tooltrace-audit

[English](README.md) · **简体中文**

离线检查重复工具调用、重叠重试、孤立结果和未完成尝试。执行事件与对话协议严格区分；重复不等于确定死循环，也不替代幂等设计或修复上游调度。

由 **Afloat16** 独立维护，MIT 许可。实验性工具，格式与限制详见 [English README](README.md) 和[需求证据](docs/EVIDENCE.md)。未声称修复上游运行时问题或获得上游认可。

## 安装与首个示例

Python 3.10+。克隆仓库、进入目录，创建并激活虚拟环境后：

```bash
python -m pip install -e '.[dev]'
tooltrace-audit examples/attempts.jsonl --strict
```

基础离线路径使用标准库，无需 GPU、ROS 运行环境或模型权重。输入保持只读，输出必须是新文件，不覆盖已有文件。审计退出码：0 无错误，1 有错误（strict 也把警告当作失败），2 输入或写入失败。

## 验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m build
```

CI 配置覆盖三种系统的 Python 3.10 / 3.13，实际状态以 Actions 为准。示例均为合成数据，不包含用户附件或私人数据。


## 相关项目

按问题选择工具，查看[Afloat16项目导航](https://github.com/Afloat16/research-to-fix/blob/main/docs/PROJECTS.zh-CN.md)。
