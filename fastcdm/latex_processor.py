import re

# 以下列表定义了在后续 token_add_color 系列函数中“跳过”的正则模式。
# 任何匹配这些模式的 token 都不会被着色，而是保持原样（通常用黑色标记）。
# 主要用于括号、环境边界、上下标等结构元素。
SKIP_PATTERNS = [
    r"\{",
    r"\}",
    r"[\[\]]",
    r"\\begin\{.*?\}",
    r"\\end\{.*?\}",
    r"\^",
    r"\_",
    r"\\.*rule.*",
    r"\\.*line.*",
    r"\[[\-.0-9]+[epm][xtm]\]",
    # \left/\right 与定界符组合（如 \left\{、\left.、\right.）分词后构成单一 token，
    # 包裹进 \color{}{} 会破坏 KaTeX 的 \left...\right 配对
    r"\\left.",
    r"\\right.",
    # \tag{...} 和 \tag*{...} 是行间公式专属命令，包裹进 \color{}{} 会导致 KaTeX 解析失败
    r"\\tag",
]

# 以下列表中的 LaTeX 命令在后续处理中被视为“透明”或“无意义”的 token。
# 它们不会触发着色逻辑，直接跳过，避免干扰真正的数学内容。
SKIP_Tokens = [
    "\\",
    "\\\\",
    "\\index",
    "\\a",
    "&",
    "$",
    "\\multirow",
    "\\def",
    "\\edef",
    "\\raggedright",
    "\\url",
    "\\cr",
    "\\ensuremath",
    "\\left",
    "\\left[",
    "\\left(",
    "\\left{",
    "\\right",
    "\\right]",
    "\\right)",
    "\\right}",
    "\\mathchoice",
    "\\scriptstyle",
    "\\displaystyle",
    "\\qquad",
    "\\quad",
    "\\,",
    "\\!",
    "~",
    "\\boldmath",
    "\\gdef",
    "\\today",
    "\\the",
    # \tag 必须作为顶层命令，其 {arg} 需直接跟随，包裹进 \color{}{} 会破坏 KaTeX 解析
    "\\tag",
    "\\tag*",
    # 定界符尺寸命令必须紧接定界符，包裹进 \color{}{} 会破坏 \bigg( 等组合的关联
    "\\big", "\\Big", "\\bigg", "\\Bigg",
    "\\bigl", "\\Bigl", "\\biggl", "\\Biggl",
    "\\bigr", "\\Bigr", "\\biggr", "\\Biggr",
    "\\bigm", "\\Bigm", "\\biggm", "\\Biggm",
]

# PHANTOM_Tokens 中的命令在后续着色时被视为“幻影”命令：
# 它们本身不直接参与颜色标记，但其参数仍需递归处理。
# 主要用于字体、引用、颜色等不影响数学结构的命令。
PHANTOM_Tokens = [
    "\\fontfamily",
    "\\vphantom",
    "\\phantom",
    "\\rowcolor",
    "\\ref",
    "\\thesubequation",
    "\\global",
    "\\theboldgroup",
]

# 以下命令在后续处理中被识别为“双尾”命令：它们需要两个 {} 参数。
# 例如 \frac{分子}{分母}，在着色时会分别对两个参数进行灰色处理。
TWO_Tail_Tokens = ["\\frac", "\\binom", "\\cfrac"]

# AB_Tail_Tokens 中的命令具有“可选+必选”参数结构：
# 第一个参数可以是 []，第二个必须是 {}。
# 例如 \xrightarrow[下方]{上方}，在着色时会分别处理两个参数。
AB_Tail_Tokens = ["\\xrightarrow", "\\xleftarrow", "\\sqrt"]  # special token \xxx [] {}

# 以下命令也是“双尾”但被视为“不可见”结构，着色逻辑与 TWO_Tail_Tokens 类似，
# 但通常用于上下堆叠等排版，不影响数学含义。
TWO_Tail_Invisb_Tokens = ["\\overset", "\\underset", "\\stackrel"]

# ONE_Tail_Tokens 中的命令只需一个 {} 参数，且会显著改变数学符号外观。
# 在着色时，命令本身保持黑色，参数内容置灰。
ONE_Tail_Tokens = [
    "\\widetilde",
    "\\overline",
    "\\hat",
    "\\widehat",
    "\\tilde",
    "\\Tilde",
    "\\dot",
    "\\bar",
    "\\vec",
    "\\underline",
    "\\underbrace",
    "\\check",
    "\\breve",
    "\\Bar",
    "\\Vec",
    "\\mathring",
    "\\ddot",
    "\\Ddot",
    "\\dddot",
    "\\ddddot",
    "\\overrightarrow",
    "\\overleftarrow",
    "\\overleftrightarrow",
    "\\underrightarrow",
    "\\underleftarrow",
    "\\underleftrightarrow",
    "\\overbrace",
    "\\widecheck",
    "\\wideparen",
    "\\cancel",
    "\\bcancel",
    "\\xcancel",
    "\\cancelto",
    "\\boxed",
]

# ONE_Tail_Invisb_Tokens 中的命令同样只需一个 {} 参数，
# 但主要用于字体或样式切换，不改变数学含义，因此整体视为“不可见”，
# 在着色时命令本身不标记，仅对其参数递归处理。
ONE_Tail_Invisb_Tokens = [
    "\\boldsymbol",
    "\\pmb",
    "\\textbf",
    "\\mathrm",
    "\\mathbf",
    "\\mathsf",
    "\\mathbb",
    "\\mathcal",
    "\\mathinner",
    "\\mathit",
    "\\mathnormal",
    "\\mathring",
    "\\mathscr",
    "\\mathtt",
    "\\textmd",
    "\\texttt",
    "\\textnormal",
    "\\text",
    "\\textit",
    "\\textup",
    "\\mathop",
    "\\mathbin",
    "\\smash",
    "\\operatorname",
    "\\operatorname*",
    "\\textrm",
    "\\mathfrak",
    "\\emph",
    "\\textsf",
    "\\textsc",
]


def flatten_multiline(latex):
    brace_map = {
        "\\left(": "\\right)",
        "\\left[": "\\right]",
        "\\left{": "\\right}",
    }
    l_split = latex.split(" ")
    if l_split[0] == "\\begin{array}":
        if l_split[-1] == "\\end{array}":
            l_split = l_split[2:-1]
        else:
            l_split = l_split[2:]

    idx = 0
    while idx < len(l_split):
        token = l_split[idx]
        if token.startswith("\\left") and token in brace_map.keys():
            end_idx = find_matching_brace(l_split, idx, brace=[token, brace_map[token]])
            if end_idx != -1:
                idx = end_idx
        elif token in ["\\\\", "~", "\\qquad"]:
            l_split = l_split[0:idx] + l_split[idx + 1 :]
            idx -= 1
        idx += 1
    latex = " ".join(l_split)
    return "$ " + latex + " $"


def clean_latex(text):
    cleaned_text = re.sub(r"(?<=[^\\])\s+(?=[^\\])", "", text)
    for item in [
        "\\hline",
        "\\midrule",
        "\\times",
        "\\bf",
        "\\footnotesize",
        "\\cr",
        "\\log",
    ]:
        cleaned_text = cleaned_text.replace(item, item + " ")
    cleaned_text = cleaned_text.replace(" \\mathcolor{black}", "\\mathcolor{black}")
    return cleaned_text


def remove_trailing_latex(formula):
    pattern = r"(\\(hspace\*?\{[^{}]*?\}|vspace\*?\{[^{}]*?\}|smallskip|medskip|quad|qquad|bigskip|[;,])|\~|\.)*$"
    cleaned_formula = re.sub(pattern, "", formula, count=1)
    return cleaned_formula


def find_matching_brace(sequence, start_index, brace=["{", "}"]):
    left_brace, right_brace = brace
    depth = 0
    for i, char in enumerate(sequence[start_index:], start=start_index):
        if char == left_brace:
            depth += 1
        elif char == right_brace:
            depth -= 1
            if depth == 0:
                return i
    if depth > 0:
        error_info = "Warning! found no matching brace in sequence !"
        raise ValueError(error_info)
    return -1


def normalize_latex(l, rm_trail=False):
    if "tabular" in l:
        latex_type = "tabular"
    else:
        latex_type = "formula"

    if rm_trail:
        l = remove_trailing_latex(l)
    l = l.strip().replace(r"\pmatrix", r"\mypmatrix").replace(r"\matrix", r"\mymatrix")

    for item in ["\\raggedright", "\\arraybackslash"]:
        l = l.replace(item, "")

    for item in ["\\lowercase", "\\uppercase"]:
        l = l.replace(item, "")

    pattern = r"\\[hv]space { [.0-9a-z ]+ }"
    old_token = re.findall(pattern, l, re.DOTALL)
    if latex_type == "tabular":
        new_token = ["" for item in old_token]
    else:
        new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    if latex_type == "tabular":
        l = l.replace("\\begin {tabular}", "\\begin{tabular}")
        l = l.replace("\\end {tabular}", "\\end{tabular}")
        l = l.replace("\\begin {array}", "\\begin{array}")
        l = l.replace("\\end {array}", "\\end{array}")
        l_split = l.split(" ")
        idx = 0
        while idx < len(l_split):
            token = l_split[idx]
            if token == "\\begin{tabular}":
                sub_idx = idx + 1
                end_idx = find_matching_brace(l_split, sub_idx)
                new_token = "".join(l_split[idx : end_idx + 1])
                l_split = l_split[0:idx] + [new_token] + l_split[end_idx + 1 :]
                break
            idx += 1
        l = " ".join(l_split)
        l_split = l.split(" ")
        idx = 0
        while idx < len(l_split):
            token = l_split[idx]
            if token in ["\\cmidrule", "\\cline"]:
                sub_idx = idx + 1
                if l_split[sub_idx] == "(":
                    mid_end = find_matching_brace(l_split, sub_idx, brace=["(", ")"])
                    end_idx = find_matching_brace(l_split, mid_end + 1)
                else:
                    end_idx = find_matching_brace(l_split, sub_idx)
                new_token = "".join(l_split[idx : end_idx + 1])
                l_split = l_split[0:idx] + [new_token] + l_split[end_idx + 1 :]
            idx += 1
        l = " ".join(l_split)

    pattern = r"\\begin{array} { [lrc ]+ }"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [
        item.replace("\\begin{array} ", "<s>")
        .replace(" ", "")
        .replace("<s>", "\\begin{array} ")
        for item in old_token
    ]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    l = " " + l + " "
    l = re.sub(r"(?<=\s)--(?=\s)", r"- -", l)
    l = re.sub(r"(?<=\s)---(?=\s)", r"- - -", l)
    l = re.sub(r"(?<=\s)…(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\ldots(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\hdots(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\cdots(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dddot(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dots(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dotsc(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dotsi(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dotsm(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dotso(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\dotsb(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\mathellipsis(?=\s)", r". . .", l)
    l = re.sub(r"(?<=\s)\\ex(?=\s)", r"\\mathrm { e x }", l)
    l = re.sub(r"(?<=\s)\\ln(?=\s)", r"\\mathrm { l n }", l)
    l = re.sub(r"(?<=\s)\\lg(?=\s)", r"\\mathrm { l g }", l)
    l = re.sub(r"(?<=\s)\\cot(?=\s)", r"\\mathrm { c o t }", l)
    l = re.sub(r"(?<=\s)\\mod(?=\s)", r"\\mathrm { m o d }", l)
    l = re.sub(r"(?<=\s)\\bmod(?=\s)", r"\\mathrm { m o d }", l)
    l = re.sub(r"(?<=\s)\\pmod(?=\s)", r"\\mathrm { m o d }", l)
    l = re.sub(r"(?<=\s)\\min(?=\s)", r"\\mathrm { m i n }", l)
    l = re.sub(r"(?<=\s)\\max(?=\s)", r"\\mathrm { m a x }", l)
    l = re.sub(r"(?<=\s)\\ker(?=\s)", r"\\mathrm { k e r }", l)
    l = re.sub(r"(?<=\s)\\hom(?=\s)", r"\\mathrm { h o m }", l)
    l = re.sub(r"(?<=\s)\\sec(?=\s)", r"\\mathrm { s e c }", l)
    l = re.sub(r"(?<=\s)\\scs(?=\s)", r"\\mathrm { s c s }", l)
    l = re.sub(r"(?<=\s)\\csc(?=\s)", r"\\mathrm { c s c }", l)
    l = re.sub(r"(?<=\s)\\deg(?=\s)", r"\\mathrm { d e g }", l)
    l = re.sub(r"(?<=\s)\\arg(?=\s)", r"\\mathrm { a r g }", l)
    l = re.sub(r"(?<=\s)\\log(?=\s)", r"\\mathrm { l o g }", l)
    l = re.sub(r"(?<=\s)\\dim(?=\s)", r"\\mathrm { d i m }", l)
    l = re.sub(r"(?<=\s)\\exp(?=\s)", r"\\mathrm { e x p }", l)
    l = re.sub(r"(?<=\s)\\sin(?=\s)", r"\\mathrm { s i n }", l)
    l = re.sub(r"(?<=\s)\\cos(?=\s)", r"\\mathrm { c o s }", l)
    l = re.sub(r"(?<=\s)\\tan(?=\s)", r"\\mathrm { t a n }", l)
    l = re.sub(r"(?<=\s)\\tanh(?=\s)", r"\\mathrm { t a n h }", l)
    l = re.sub(r"(?<=\s)\\cosh(?=\s)", r"\\mathrm { c o s h }", l)
    l = re.sub(r"(?<=\s)\\sinh(?=\s)", r"\\mathrm { s i n h }", l)
    l = re.sub(r"(?<=\s)\\coth(?=\s)", r"\\mathrm { c o t h }", l)
    l = re.sub(r"(?<=\s)\\arcsin(?=\s)", r"\\mathrm { a r c s i n }", l)
    l = re.sub(r"(?<=\s)\\arccos(?=\s)", r"\\mathrm { a r c c o s }", l)
    l = re.sub(r"(?<=\s)\\arctan(?=\s)", r"\\mathrm { a r c t a n }", l)
    l = re.sub(r"(?<=\s)\\bf([a-zA-Z])", r"\\mathbf{\1}", l)

    pattern = r"\\string [^ ]+ "
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft + " ")

    pattern = r"\\[Bb]ig[g]?[glrm]? [(){}|\[\]] "
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft + " ")

    pattern = r"\\[Bb]ig[g]?[glrm]? \\.*? "
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft + " ")

    pattern = r"\\operatorname \*"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = ["\\operatorname" for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    l = l.replace("\\lefteqn", "")

    l = l.replace("\\footnote ", "^ ")

    pattern = r"\\\' [^{] "
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft + " ")

    if latex_type == "tabular":
        pattern = r"\[ [\-.0-9 ]+[exptcm ]+ \]"
        old_token = re.findall(pattern, l, re.DOTALL)
        new_token = [item.replace(" ", "") for item in old_token]
        for bef, aft in zip(old_token, new_token):
            l = l.replace(bef, aft)

    pattern = r"\\parbox {[^{]+}"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    pattern = r"\\raisebox {[^{]+} [\[\]0-9 exptcm]+{"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft[0:-1] + " {")

    pattern = r"{ \\char[0-9\' ]+}"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, "{ " + aft[1:-1] + " }")

    pattern = r"\\rule {[ .0-9a-z]+} {[ .0-9a-z]+}"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    pattern = r"\\specialrule {[ .0-9a-z]+} {[ .0-9a-z]+} {[ .0-9a-z]+}"
    old_token = re.findall(pattern, l, re.DOTALL)
    new_token = [item.replace(" ", "") for item in old_token]
    for bef, aft in zip(old_token, new_token):
        l = l.replace(bef, aft)

    pattern = r"\\colorbox[ \[\]RGBrgb]+{ [A-Za-z 0-9,!]+ } |\\color[ \[\]RGBrgb]+{ [A-Za-z 0-9,!]+ } |\\textcolor[ \[\]RGBrgb]+{ [A-Za-z 0-9,!]+ } |\\cellcolor[ \[\]RGBrgb]+{ [A-Za-z 0-9,!]+ } "
    old_token = re.findall(pattern, l, re.DOTALL)
    for bef in old_token:
        l = l.replace(bef, "")

    l_split = l.split(" ")
    idx = 0
    while idx < len(l_split):
        token = l_split[idx]
        if token in ONE_Tail_Tokens + ONE_Tail_Invisb_Tokens:
            sub_idx = idx + 1
            while (
                sub_idx < len(l_split)
                and l_split[sub_idx] in ONE_Tail_Tokens + ONE_Tail_Invisb_Tokens
            ):
                sub_idx += 1
            new_split = l_split[0:idx]
            for ii in range(idx, sub_idx):
                new_split = new_split + [l_split[ii], "{"]
            if l_split[sub_idx] != "{":
                new_split = new_split + [l_split[sub_idx]] + ["}"] * (sub_idx - idx)
                l_split = new_split + l_split[sub_idx + 1 :]
            else:
                end_idx = find_matching_brace(l_split, sub_idx)
                new_split = (
                    new_split + l_split[sub_idx + 1 : end_idx] + ["}"] * (sub_idx - idx)
                )
                l_split = new_split + l_split[end_idx + 1 :]
        elif token in AB_Tail_Tokens:
            if l_split[idx + 1] != "[" and l_split[idx + 1] != "{":
                l_split = (
                    l_split[0 : idx + 1]
                    + ["{"]
                    + [l_split[idx + 1]]
                    + ["}"]
                    + l_split[idx + 2 :]
                )
            else:
                if l_split[idx + 1] == "[":
                    end1 = find_matching_brace(l_split, idx + 1, brace=["[", "]"])
                else:
                    end1 = idx
                if l_split[end1 + 1] != "{":
                    l_split = (
                        l_split[0 : end1 + 1]
                        + ["{"]
                        + [l_split[end1 + 1]]
                        + ["}"]
                        + l_split[end1 + 2 :]
                    )
        elif token in TWO_Tail_Tokens + TWO_Tail_Invisb_Tokens:
            if l_split[idx + 1] != "{":
                l_split = (
                    l_split[0 : idx + 1]
                    + ["{"]
                    + [l_split[idx + 1]]
                    + ["}"]
                    + l_split[idx + 2 :]
                )
            end1 = find_matching_brace(l_split, idx + 1)
            if l_split[end1 + 1] != "{":
                l_split = (
                    l_split[0 : end1 + 1]
                    + ["{"]
                    + [l_split[end1 + 1]]
                    + ["}"]
                    + l_split[end1 + 2 :]
                )

        idx += 1
    l = " ".join(l_split)

    return l


def token_add_color(l_split, idx, render_dict):
    token = l_split[idx]
    if token in PHANTOM_Tokens:
        if l_split[idx + 1] == "{":
            brace_end = find_matching_brace(l_split, idx + 1)
        else:
            brace_end = idx + 1
        next_idx = brace_end + 1
    elif token in TWO_Tail_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        den_start = num_end + 1
        den_end = find_matching_brace(l_split, den_start)
        l_split_copy = (
            l_split[:idx]
            + [r"\mathcolor{black}{" + token + "{"]
            + [r"\mathcolor{gray}{"]
            + l_split[num_start + 1 : num_end]
            + ["}"]
            + [r"}{"]
            + [r"\mathcolor{gray}{"]
            + l_split[den_start + 1 : den_end]
            + ["}"]
            + ["}"]
            + ["}"]
            + l_split[den_end + 1 :]
        )

        l_new = " ".join(l_split_copy)
        l_new = r"\mathcolor{gray}{ " + l_new + " }"
        render_dict[str(idx)] = l_new, token
        next_idx = idx + 1
    elif token in ONE_Tail_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        l_split_copy = (
            l_split[:idx]
            + [r"\mathcolor{black}{"]
            + l_split[idx : num_start + 1]
            + [r"\mathcolor{gray}{"]
            + l_split[num_start + 1 : num_end]
            + ["}"]
            + l_split[num_end : num_end + 1]
            + ["}"]
            + l_split[num_end + 1 :]
        )
        l_new = " ".join(l_split_copy)
        l_new = r"\mathcolor{gray}{ " + l_new + " }"
        render_dict[str(idx)] = l_new, token
        next_idx = idx + 1
    elif token in ONE_Tail_Invisb_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        sub_idx = num_start + 1
        if num_end - num_start == 2:
            l_split_copy = l_split.copy()
            l_split_copy[sub_idx] = (
                r"{\mathcolor{black}{" + l_split_copy[sub_idx] + "}}"
            )
            l_new = " ".join(l_split_copy)
            l_new = r"\mathcolor{gray}{ " + l_new + " }"
            render_dict[str(idx)] = l_new, l_split[sub_idx]
            next_idx = num_end
        else:
            while sub_idx < num_end:
                l_split, sub_idx, render_dict = token_add_color(
                    l_split, sub_idx, render_dict
                )
        next_idx = num_end + 1
    elif token in AB_Tail_Tokens:
        if l_split[idx + 1] == "{":
            num_start = idx + 1
            num_end = find_matching_brace(l_split, num_start)
            l_split_copy = (
                l_split[:idx]
                + [r"\mathcolor{black}{"]
                + l_split[idx : idx + 2]
                + [r"\mathcolor{gray}{"]
                + l_split[num_start + 1 : num_end]
                + ["}}"]
                + l_split[num_end:]
            )
            l_new = " ".join(l_split_copy)
            l_new = r"\mathcolor{gray}{ " + l_new + " }"
            render_dict[str(idx)] = l_new, token
            sub_idx = num_start + 1
            while sub_idx < num_end:
                l_split, sub_idx, render_dict = token_add_color(
                    l_split, sub_idx, render_dict
                )
            next_idx = num_end + 1
        elif l_split[idx + 1] == "[":
            num_start = idx + 1
            num_end = find_matching_brace(l_split, num_start, brace=["[", "]"])
            den_start = num_end + 1
            den_end = find_matching_brace(l_split, den_start)
            l_split_copy = (
                l_split[:idx]
                + [r"{\mathcolor{black}{"]
                + l_split[idx : idx + 2]
                + [r"\mathcolor{gray}{"]
                + l_split[idx + 2 : num_end]
                + ["}"]
                + l_split[num_end : den_start + 1]
                + [r"\mathcolor{gray}{"]
                + l_split[den_start + 1 : den_end]
                + ["}"]
                + l_split[den_end : den_end + 1]
                + ["}}"]
                + l_split[den_end + 1 :]
            )
            l_new = " ".join(l_split_copy)
            l_new = r"\mathcolor{gray}{ " + l_new + " }"
            render_dict[str(idx)] = l_new, token
            sub_idx = num_start + 1
            while sub_idx < num_end:
                l_split, sub_idx, render_dict = token_add_color(
                    l_split, sub_idx, render_dict
                )
            sub_idx = den_start + 1
            while sub_idx < den_end:
                l_split, sub_idx, render_dict = token_add_color(
                    l_split, sub_idx, render_dict
                )
            next_idx = den_end + 1
    elif token in ["\\multicolumn", "\\multirow"]:
        first_start = idx + 1
        first_end = find_matching_brace(l_split, first_start)
        second_start = first_end + 1
        second_end = find_matching_brace(l_split, second_start)
        third_start = second_end + 1
        third_end = find_matching_brace(l_split, third_start)

        sub_idx = third_start + 1
        while sub_idx < third_end:
            l_split, sub_idx, render_dict = token_add_color(
                l_split, sub_idx, render_dict
            )
        next_idx = third_end + 1
    elif token in SKIP_Tokens + TWO_Tail_Invisb_Tokens or any(
        re.match(pattern, token) for pattern in SKIP_PATTERNS
    ):
        if (token == "[" and l_split[idx - 1] != "\\sqrt") or (
            token == "]" and idx >= 3 and l_split[idx - 3] != "\\sqrt"
        ):
            l_split_copy = l_split.copy()
            l_split_copy[idx] = r"\mathcolor{black}{ " + l_split_copy[idx] + " }"
            l_new = " ".join(l_split_copy)
            l_new = r"\mathcolor{gray}{ " + l_new + " }"
            render_dict[str(idx)] = l_new, token
            next_idx = idx + 1
        else:
            next_idx = idx + 1
    else:
        l_split_copy = l_split.copy()
        l_split_copy[idx] = r"\mathcolor{black}{ " + l_split_copy[idx] + " }"

        l_new = " ".join(l_split_copy)
        l_new = r"\mathcolor{gray}{ " + l_new + " }"
        render_dict[str(idx)] = l_new, token
        next_idx = idx + 1

    return l_split, next_idx, render_dict


def token_add_color_RGB(l_split, idx, token_list, brace_color=False):
    """using \mathcolor[RGB]{r,g,b} to render latex."""
    token = l_split[idx]
    if not token:
        next_idx = idx + 1
    elif token in PHANTOM_Tokens:
        if l_split[idx + 1] == "{":
            brace_end = find_matching_brace(l_split, idx + 1)
        else:
            brace_end = idx + 1
        next_idx = brace_end + 1
    elif token in TWO_Tail_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        den_start = num_end + 1
        den_end = find_matching_brace(l_split, den_start)
        color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
            "<idx>", str(len(token_list))
        )
        l_split = (
            l_split[:idx]
            + [color_token + token]
            + l_split[idx + 1 : den_end + 1]
            + ["}"]
            + l_split[den_end + 1 :]
        )
        token_list.append(token)
        next_idx = idx + 1
    elif token in ONE_Tail_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
            "<idx>", str(len(token_list))
        )
        if (
            token != "\\underbrace"
            and num_end + 1 < len(l_split)
            and l_split[num_end + 1] == "_"
        ):
            l_split = (
                l_split[:idx]
                + ["{" + color_token + token]
                + l_split[idx + 1 : num_end + 1]
                + ["}}"]
                + l_split[num_end + 1 :]
            )
        else:
            l_split = (
                l_split[:idx]
                + [color_token + token]
                + l_split[idx + 1 : num_end + 1]
                + ["}"]
                + l_split[num_end + 1 :]
            )
        token_list.append(token)
        next_idx = idx + 1
    elif token in ONE_Tail_Invisb_Tokens:
        num_start = idx + 1
        num_end = find_matching_brace(l_split, num_start)
        sub_idx = num_start + 1
        if num_end - num_start == 2:
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            token_list.append(l_split[num_start + 1])
            l_split = (
                l_split[: num_start + 1]
                + [color_token + l_split[num_start + 1] + "}"]
                + l_split[num_end:]
            )
        else:
            while sub_idx < num_end:
                l_split, sub_idx, token_list = token_add_color_RGB(
                    l_split, sub_idx, token_list
                )
        next_idx = num_end + 1
    elif token in AB_Tail_Tokens:
        if l_split[idx + 1] == "{":
            num_start = idx + 1
            num_end = find_matching_brace(l_split, num_start)
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            l_split = (
                l_split[:idx]
                + [color_token + token]
                + l_split[idx + 1 : num_end + 1]
                + ["}"]
                + l_split[num_end + 1 :]
            )
            token_list.append(token)
            sub_idx = num_start + 1
            while sub_idx < num_end:
                l_split, sub_idx, token_list = token_add_color_RGB(
                    l_split, sub_idx, token_list
                )
            next_idx = num_end + 1
        elif l_split[idx + 1] == "[":
            num_start = idx + 1
            num_end = find_matching_brace(l_split, num_start, brace=["[", "]"])
            den_start = num_end + 1
            den_end = find_matching_brace(l_split, den_start)
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            l_split = (
                l_split[:idx]
                + [color_token + token]
                + l_split[idx + 1 : den_end + 1]
                + ["}"]
                + l_split[den_end + 1 :]
            )
            token_list.append(token)
            sub_idx = num_start + 1
            while sub_idx < num_end:
                l_split, sub_idx, token_list = token_add_color_RGB(
                    l_split, sub_idx, token_list, brace_color=True
                )
            sub_idx = den_start + 1
            while sub_idx < den_end:
                l_split, sub_idx, token_list = token_add_color_RGB(
                    l_split, sub_idx, token_list
                )
            next_idx = den_end + 1
    elif token in ["\\multicolumn", "\\multirow"]:
        first_start = idx + 1
        first_end = find_matching_brace(l_split, first_start)
        second_start = first_end + 1
        second_end = find_matching_brace(l_split, second_start)
        third_start = second_end + 1
        third_end = find_matching_brace(l_split, third_start)

        sub_idx = third_start + 1
        while sub_idx < third_end:
            l_split, sub_idx, token_list = token_add_color_RGB(
                l_split, sub_idx, token_list
            )
        next_idx = third_end + 1
    elif token in SKIP_Tokens + TWO_Tail_Invisb_Tokens or any(
        re.match(pattern, token) for pattern in SKIP_PATTERNS
    ):

        if (token == "[" and l_split[idx - 1] != "\\sqrt") or (
            token == "]" and idx >= 3 and l_split[idx - 3] != "\\sqrt"
        ):
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            l_split = (
                l_split[:idx] + [color_token + l_split[idx] + "}"] + l_split[idx + 1 :]
            )
            token_list.append(token)
            next_idx = idx + 1
        else:
            next_idx = idx + 1
    else:
        # 以空格分词后可能产生结构不完整的片段 token，对其着色会破坏外层 LaTeX 结构。
        # 以下三种情况之一触发时跳过着色，直接透传：
        #   1. {} 数量不平衡 → 片段跨越多个 token 构成完整括号对
        #   2. 运行时括号深度降至负值 → token 跨越了前一个 token 开启的括号边界
        #   3. 包含 \\ → LaTeX 换行分隔符，不能嵌套在 \color{}{} 参数内
        open_count = token.count("{")
        close_count = token.count("}")
        has_row_sep = "\\\\" in token  # \\ 为 LaTeX 换行分隔符（两个实际反斜杠）
        balance = 0
        min_balance = 0
        for ch in token:
            if ch == "{":
                balance += 1
            elif ch == "}":
                balance -= 1
                if balance < min_balance:
                    min_balance = balance
        if open_count != close_count or has_row_sep or min_balance < 0:
            next_idx = idx + 1
        elif brace_color or (idx > 1 and l_split[idx - 1] == "_"):
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            l_split = (
                l_split[:idx]
                + ["{" + color_token + l_split[idx] + "}}"]
                + l_split[idx + 1 :]
            )
            token_list.append(token)
            next_idx = idx + 1
        else:
            color_token = "\\mathcolor[RGB]{<color_<idx>>}{".replace(
                "<idx>", str(len(token_list))
            )
            l_split = (
                l_split[:idx] + [color_token + l_split[idx] + "}"] + l_split[idx + 1 :]
            )
            token_list.append(token)
            next_idx = idx + 1
    return l_split, next_idx, token_list
