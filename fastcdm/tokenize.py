import re
import subprocess
from pathlib import Path
from typing import Tuple
import sys


IMPLICIT_MULTIPLICATION_TARGETS = [
    "arccos",
    "arcsin",
    "arctan",
    "sinh",
    "cosh",
    "tanh",
    "coth",
    "sech",
    "csch",
    "lim",
    "log",
    "ln",
    "exp",
    "sin",
    "cos",
    "tan",
    "cot",
    "sec",
    "csc",
    "ArcCos",
    "ArcSin",
    "ArcTan",
    "Sinh",
    "Cosh",
    "Tanh",
    "Coth",
    "Sech",
    "Csch",
    "Lim",
    "Log",
    "Ln",
    "Exp",
    "Sin",
    "Cos",
    "Tan",
    "Cot",
    "Sec",
    "Csc",
    "det",
    "dim",
    "min",
    "max",
    "sup",
    "inf",
    "deg",
    "gcd",
    "lcm",
    "ker",
    "im",
    "Pr",
    "E",
    "Var",
    "Cov",
    "rank",
    "Tr",
    "span",
    "proj",
    "grad",
    "div",
    "curl",
    "Res",
    "pi",
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "eta",
    "theta",
    "iota",
    "kappa",
    "lambda",
    "mu",
    "nu",
    "xi",
    "omicron",
    "rho",
    "sigma",
    "tau",
    "upsilon",
    "phi",
    "chi",
    "psi",
    "omega",
    "Pi",
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Eta",
    "Theta",
    "Iota",
    "Kappa",
    "Lambda",
    "Mu",
    "Nu",
    "Xi",
    "Omicron",
    "Rho",
    "Sigma",
    "Tau",
    "Upsilon",
    "Phi",
    "Chi",
    "Psi",
    "Omega",
    "varepsilon",
    "vartheta",
    "varpi",
    "varrho",
    "varsigma",
    "varphi",
    "partial",
    "nabla",
    "int",
    "oint",
    "sum",
    "prod",
    "wedge",
    "vee",
    "cap",
    "cup",
    "therefore",
    "because",
    "Rightarrow",
    "rightarrow",
    "Leftarrow",
    "leftarrow",
    "Leftrightarrow",
    "leftrightarrow",
    "in",
    "ni",
    "subset",
    "supset",
    "subseteq",
    "supseteq",
    "equiv",
    "sim",
    "simeq",
    "approx",
    "propto",
    "cdot",
    "times",
    "otimes",
    "oplus",
    "quad",
    "qquad",
    "ldots",
    "cdots",
    "ddots",
    "forall",
    "exists",
    "neg",
    "infty",
    "hbar",
    "emptyset",
    "angle",
    "geqslant",
    "hat",
    "bar",
    "tilde",
    "vec",
    "dot",
    "ddot",
    "sqrt",
]
IMPLICIT_MULTIPLICATION_TARGETS.sort(key=len, reverse=True)
TARGETS_PATTERN = "|".join(IMPLICIT_MULTIPLICATION_TARGETS)

# \begin{equation}...\end{equation} — 剥去外层包装，保留内容
PATTERN_EQUATION_ENV = re.compile(
    r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", re.S
)
# \\ 后跟间距命令且不在矩阵环境内时，折叠为空格，例如 "X \\\quad=" → "X ="
PATTERN_LINEBREAK_SPACING = re.compile(
    r"\\\\[ \t]*(\\(?:quad|qquad|;|:|,|!| ))"
)
# \begin{subarray} 不被 KaTeX 支持，展开为逗号分隔的 token
PATTERN_SUBARRAY_ENV = re.compile(
    r"\\begin\{subarray\}\{[^}]*\}(.+?)\\end\{subarray\}", re.S
)
PATTERN_ALIGN_ENV = re.compile(
    r"\\begin{(split|align|alignedat|alignat|eqnarray)\*?}(.+?)\\end{\1\*?}", re.S
)
PATTERN_SMALLMATRIX = re.compile(r"\\begin{(smallmatrix)\*?}(.+?)\\end{\1\*?}", re.S)
PATTERN_INVALID_SINGLE_CHAR_CMD = re.compile(r"\\([a-zA-Z0-9])(?![a-zA-Z])")
PATTERN_LATEX_CMD_CONCAT_CMD = re.compile(
    r"\\(" + TARGETS_PATTERN + r")" + r"(\\[a-zA-Z])"
)
PATTERN_LATEX_CMD_CONCAT_TEXT = re.compile(r"\\(" + TARGETS_PATTERN + r")([a-zA-Z])")
PATTERN_NON_CMD_IMPLICIT_MULT = re.compile(
    r"\b(" + TARGETS_PATTERN + r")([a-zA-Z][a-zA-Z0-9]*)\b"
)

OPERATORS = "\s?".join(
    "|".join(
        [
            "arccos",
            "arcsin",
            "arctan",
            "arg",
            "cos",
            "cosh",
            "cot",
            "coth",
            "csc",
            "deg",
            "det",
            "dim",
            "exp",
            "gcd",
            "hom",
            "inf",
            "injlim",
            "ker",
            "lg",
            "lim",
            "liminf",
            "limsup",
            "ln",
            "log",
            "max",
            "min",
            "Pr",
            "projlim",
            "sec",
            "sin",
            "sinh",
            "sup",
            "tan",
            "tanh",
        ]
    )
)
PATTERN_OPERATOR_NAME = re.compile(r"\\operatorname {(%s)}" % OPERATORS)



def tokenize(latex_code: str) -> Tuple[bool, str]:

    if not latex_code:
        return True, ""

    root_dir = Path(__file__).parent
    formula_script = root_dir / "tokenize_latex" / "preprocess_formula.js"

    prepre = latex_code.replace("\n", " ")
    # 剥去 \begin{equation}...\end{equation} 外层包装
    prepre = PATTERN_EQUATION_ENV.sub(r"\1", prepre)
    prepre = PATTERN_ALIGN_ENV.sub(r"\\begin{aligned}\2\\end{aligned}", prepre)
    prepre = PATTERN_SMALLMATRIX.sub(r"\\begin{matrix}\2\\end{matrix}", prepre)
    # 不在矩阵/cases/array 环境内时，将 \\+间距命令 折叠为空格
    if not any(kw in prepre for kw in ("matrix", "cases", "array", "begin")):
        prepre = PATTERN_LINEBREAK_SPACING.sub(" ", prepre)
    # 将 \begin{subarray}{c}...\end{subarray} 展开为逗号连接的行
    prepre = PATTERN_SUBARRAY_ENV.sub(
        lambda m: ",".join(part.strip() for part in m.group(1).split(r"\\")), prepre
    )
    prepre = PATTERN_INVALID_SINGLE_CHAR_CMD.sub(r"\1", prepre)
    prepre = PATTERN_LATEX_CMD_CONCAT_CMD.sub(r"\\\1 \2", prepre)
    prepre = PATTERN_LATEX_CMD_CONCAT_TEXT.sub(r"\\\1 \2", prepre)
    prepre = PATTERN_NON_CMD_IMPLICIT_MULT.sub(r"\1 \2", prepre)

    try:
        proc = subprocess.run(
            ["node", str(formula_script), "normalize"],
            input=prepre,
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        normalized_latex = proc.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error executing Node.js script (formula): {e}", file=sys.stderr)
        if hasattr(e, "stderr"):
            print(f"Node.js stderr: {e.stderr}", file=sys.stderr)
        return False, latex_code

    names = [
        "\\" + x.replace(" ", "")
        for x in re.findall(PATTERN_OPERATOR_NAME, normalized_latex)
    ]
    post = PATTERN_OPERATOR_NAME.sub(
        lambda match: str(names.pop(0)), normalized_latex
    ).replace(r"\\ \end{array}", r"\end{array}")
    return True, post.strip()
