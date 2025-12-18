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

## 🚀 Introduction

[CDM](https://github.com/opendatalab/UniMERNet/tree/main/cdm) ensures the objectivity and accuracy of evaluation by rendering predicted and ground-truth LaTeX formulas into images, and then using visual feature extraction and localization techniques to perform precise character-level matching, combined with spatial position information.

**FastCDM** aims to address performance issues. As a high-performance optimized version of the original [CDM](https://github.com/opendatalab/UniMERNet/tree/main/cdm), FastCDM employs the browser-based KaTeX rendering engine instead of traditional LaTeX compilation, resulting in significantly improved speed.

### 🎯 Project Goals

The core objective of FastCDM is to **provide a convenient user experience during the training process**, helping to advance formula recognition tasks. We are committed to:
- Providing simple and easy-to-use API interfaces for convenient integration of evaluation within the training loop.
- Supporting both real-time evaluation and batch evaluation modes.
- Providing visualization tools for evaluation metrics during the training process.

### Why Choose FastCDM?

1.  **Extreme Performance**: Based on the KaTeX rendering engine, it is tens of times faster than the traditional LaTeX compilation process.
2.  **Simplified Deployment**: No need to install complex LaTeX environments (ImageMagick, texlive-full, etc.).
3.  **Accurate Evaluation**: Adopts character detection matching methods to avoid the unfairness issues associated with traditional text metrics.
4.  **Continuous Optimization**: Supplements and refines CDM symbol support, with continuous iterative improvements.
5.  **Easy Integration**: Provides a unified API interface for easy integration into various training frameworks. Future integration with mainstream training frameworks such as PyTorch and Transformers is planned.

### ⚠️ Note

Although KaTeX is extremely fast, it is a lightweight solution optimized for the Web and cannot support **100%** of all obscure LaTeX syntax.

For the vast majority of standard formulas, it performs perfectly. This is a reasonable and sustainable technical choice.

You can check KaTeX's support coverage here: 🔗 [KaTeX Support Table](https://katex.org/docs/support_table)

---

## Usage

### Installation

```bash
pip install fastcdm
```

### Quick Start

```python
from fastcdm import FastCDM

chromedriver_path = "driver/chromedriver"

# Initialize FastCDM evaluator
evaluator = FastCDM(chromedriver_path=chromedriver_path)

# Evaluate
cdm_score, recall, precision = evaluator.compute(gt="E = mc^2", pred="E + 1 = mc^2", visualize=False)

# Evaluate and visualize
cdm_score, recall, precision, vis_img = evaluator.compute(gt="E = mc^2", pred="E + 1 = mc^2", visualize=True)
```

### Interactive Demo

We provide a visualization Demo developed with Gradio, which you can try on [HuggingFace Spaces](https://huggingface.co/spaces). You can also launch it locally:

```bash
python3 scripts/app.py
```

## Contribution and Feedback

We welcome all forms of contribution, including but not limited to:
- Submitting issue reports
- Suggesting improvements
- Submitting code changes (please open an issue for discussion first)

Please contact us via the project's [issues](https://github.com/BinyangQiu/FastCDM/issues).

---

## License

This project is open-sourced under the Apache 2.0 license. You are free to use, modify, and distribute the code of this project under the terms of the license.
