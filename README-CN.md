<div align="center">

# ⚡️FastCDM

[**[GitHub Repo]**](https://github.com/BinyangQiu/FastCDM) | [**[HuggingFace Spaces]**](https://huggingface.co/spaces)

<p>
  <a href="https://pypi.org/project/fastcdm/">
    <img src="https://img.shields.io/badge/pypi-v0.1.1-blue" 
         alt="PyPI package version">
  </a>
  <a href="https://www.python.org">
    <img src="https://img.shields.io/badge/python-3.8%2B-blue" 
         alt="Python versions">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue"
         alt="GitHub license">
  </a>
</p>

</div>

## 🚀 简介

[CDM](https://github.com/opendatalab/UniMERNet/tree/main/cdm) 通过将预测和真实的LaTeX公式渲染为图像，然后使用视觉特征提取和定位技术进行精确的字符级匹配，结合空间位置信息，确保了评估的客观性和准确性。

**FastCDM** 旨在解决性能问题。作为原版 [CDM](https://github.com/opendatalab/UniMERNet/tree/main/cdm) 的高性能优化版本，FastCDM采用浏览器的Katex渲染引擎，而非传统的Latex编译，速度得到了极大的提升。

### 🎯 项目目标

FastCDM的核心目标是**在训练过程中提供便捷的使用体验**，帮助推动公式识别任务的进步。我们致力于：
- 提供简单易用的API接口，方便在训练循环中集成评估
- 支持实时评估和批量评估两种模式
- 提供训练过程中的评估指标可视化工具

### 为什么选择 FastCDM？

1.  **极速性能**：基于KaTeX的渲染引擎，相比传统LaTeX编译流程快数十倍
2.  **简化部署**：无需安装复杂的LaTeX环境（ImageMagick、texlive-full等）
3.  **准确评估**：采用字符检测匹配方法，避免传统文本指标的不公平性问题
4.  **持续优化**：对CDM符号支持进行补充完善，并持续迭代改进
5.  **易于集成**：提供统一的API接口，方便集成到各种训练框架中，未来将集成PyTorch、Transformers等多个主流训练框架

### ⚠️ 注意

虽然 KaTeX 跑得比八卦记者还快，但它毕竟是为了 Web 优化的轻量级选手，无法做到对所有 LaTeX 诡异语法的 **100%** 支持。

对于绝大部分的常规公式，它完美胜任。这是一个合理且能走得长远的技术选型。

可以在这里查阅 KaTeX 的支持范围：🔗 [KaTeX Support Table](https://katex.org/docs/support_table)

---

## 使用方法

### 安装

需要提前安装`node.js`和`chromedriver`。
* `node.js`的安装可以参考[这里](https://nodejs.org/)。
* `chromedriver`的安装可以参考[这里](docs/chromedriver_installation.md)。

```bash
pip install fastcdm
```

### 快速开始

```python
from fastcdm import FastCDM

chromedriver_path = "driver/chromedriver"

# 初始化 FastCDM 评估器
evaluator = FastCDM(chromedriver_path=chromedriver_path)

# 评估
cdm_score, recall, precision = evaluator.compute(gt="E = mc^2", pred="E + 1 = mc^2", visualize=False)

# 评估，并可视化
cdm_score, recall, precision, vis_img = evaluator.compute(gt="E = mc^2", pred="E + 1 = mc^2", visualize=True)
```

### 交互Demo

我们提供了一个Gradio开发的可视化Demo，您可以在[HuggingFace Spaces](https://huggingface.co/spaces)中尝试使用。也可以本地启动：

```bash
python3 scripts/app.py
```

## 贡献与反馈

我们欢迎所有形式的贡献，包括但不限于：
- 提交问题报告
- 建议改进
- 提交代码变更（请先开issue讨论）

请通过项目的[issues](https://github.com/BinyangQiu/FastCDM/issues)与我们联系。

---

## 协议

本项目基于 Apache 2.0 协议开源。您可以在遵守协议条款的前提下自由使用、修改和分发本项目的代码。

