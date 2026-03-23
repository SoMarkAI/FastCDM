import re

# \ce{...} 包装会导致 mhchem 忽略内部 \color{}，取消包装后 KaTeX 可正常保留 token 颜色
PATTERN_CE_COMMAND = re.compile(r"\\ce\{([^}]*)\}")
PATTERN_XLONGEQUAL = re.compile(r"\\xlongequal\{([^}]*)\}")

# 移除 pred 字段首尾的 \[ 和 \]
# 该正则用于去掉字符串开头被颜色宏包裹的 \[，确保公式起始干净
PATTERN_STRIP_START_BRACKET = re.compile(
    r"^\s*\\color\{#[\da-fA-F]{6}\}\{\s*\\\[\s*\}\s*"
)
# 该正则用于去掉字符串末尾被颜色宏包裹的 \]，确保公式结尾干净
PATTERN_STRIP_END_BRACKET = re.compile(
    r"\s*\\color\{#[\da-fA-F]{6}\}\{\s*\\\]\s*\}\s*$"
)


def full_to_half_width(s: str) -> str:
    """
    将字符串中的全角字符转换为半角字符。
    """
    res = ""
    for char in s:
        inside_code = ord(char)
        if inside_code == 12288:  # 全角空格
            inside_code = 32
        elif 65281 <= inside_code <= 65374:  # 其他全角字符
            inside_code -= 65248
        res += chr(inside_code)
    return res


def clean_latex_delimiters(latex_string: str) -> str:
    """
    清理 LaTeX 字符串中的美元符号和双美元符号。
    """
    s = latex_string.strip()
    if s.startswith("$$") and s.endswith("$$"):
        return s[2:-2].strip()
    if s.startswith("$") and s.endswith("$"):
        return s[1:-1].strip()
    return s


def clean(s: str) -> str:
    """
    对字符串进行预处理，包括全角转半角、去空格等。
    """
    processed_text = full_to_half_width(s)
    processed_text = processed_text.replace("{/[}", r" \[").replace("{/]}", r" \]")
    # 取消 \ce{...} 和 \xlongequal{} 包装，确保 KaTeX 保留 token 颜色
    processed_text = PATTERN_CE_COMMAND.sub(r"\1", processed_text)
    processed_text = PATTERN_XLONGEQUAL.sub(r"\\xrightarrow{\1}", processed_text)
    # \bm 不被 KaTeX 支持，替换为 \boldsymbol
    processed_text = processed_text.replace(r"\bm{", r"\boldsymbol{")
    cleaned_text = clean_latex_delimiters(processed_text)
    return cleaned_text
