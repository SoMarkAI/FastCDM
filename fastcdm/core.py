from fastcdm.render.render_worker import RenderWorker
from fastcdm.matcher import update_inliers, HungarianMatcher, SimpleAffineTransform
from fastcdm.clean import (
    clean,
    PATTERN_STRIP_START_BRACKET,
    PATTERN_STRIP_END_BRACKET,
)
from fastcdm.tokenize import tokenize
from fastcdm.colorize import process_for_katex, generate_high_contrast_colors
from fastcdm.box import get_bboxes_from_array

import cv2
import numpy as np
from typing import List, Tuple
from pathlib import Path
from skimage.measure import ransac
import traceback
import subprocess
import shutil
import os

root_dir = Path(__file__).parent
TEMPLATE_FILE = root_dir / "render" / "templates" / "formula.html"


def preprocess(s: str):
    # --- 第一步：清洗与分词 ---
    clean_s = clean(s)
    success_tokenization, tokenized_s = tokenize(clean_s)

    if not success_tokenization:
        raise RuntimeError("Tokenization failed")

    # --- 第二步：生成着色 LaTeX ---
    katex_template, token_list = process_for_katex(tokenized_s)

    # 生成高对比度颜色
    num_colors = len(token_list) + 10
    colors_rgb = generate_high_contrast_colors(num_colors)

    final_latex = katex_template
    color_map = []  # (token, rgb颜色) 映射列表
    for c_idx, token in enumerate(token_list):
        r, g, b = colors_rgb[c_idx % len(colors_rgb)]
        final_latex = final_latex.replace(
            f"__COLOR__{c_idx}__", f"#{r:02x}{g:02x}{b:02x}"
        )
        color_map.append((token, (r, g, b)))

    # 移除首尾括号
    final_latex = PATTERN_STRIP_START_BRACKET.sub("", final_latex)
    final_latex = PATTERN_STRIP_END_BRACKET.sub("", final_latex)

    return final_latex, color_map


def calculate_metrics(gt_len, pred_len, match_num):
    """计算F1-score, Recall, Precision。"""
    recall = match_num / gt_len if gt_len > 0 else 0
    precision = match_num / pred_len if pred_len > 0 else 0
    f1_score = (
        2 * (precision * recall) / (precision + recall) if recall + precision > 0 else 0
    )
    return f1_score, recall, precision


def postprocess(
    img_gt: np.ndarray,
    img_pred: np.ndarray,
    gt_color_map: List[Tuple[str, Tuple[int, int, int]]],
    pred_color_map: List[Tuple[str, Tuple[int, int, int]]],
    visualize: bool,
):
    # 对齐图像尺寸（取最大宽高）
    h_gt, w_gt = img_gt.shape[:2]
    h_pred, w_pred = img_pred.shape[:2]
    max_h = max(h_gt, h_pred)
    max_w = max(w_gt, w_pred)

    # 创建白色画布
    final_gt_img = np.full((max_h, max_w, 3), 255, dtype=np.uint8)
    final_gt_img[0:h_gt, 0:w_gt] = img_gt

    final_pred_img = np.full((max_h, max_w, 3), 255, dtype=np.uint8)
    final_pred_img[0:h_pred, 0:w_pred] = img_pred

    vis_img = None

    gt_colors = [c[1] for c in gt_color_map]
    pred_colors = [c[1] for c in pred_color_map]

    # bbox 格式：[xmin, ymin, xmax, ymax]
    gt_bboxes_list = get_bboxes_from_array(final_gt_img, gt_colors)
    pred_bboxes_list = get_bboxes_from_array(final_pred_img, pred_colors)

    # --- 第三步：匹配 Token ---
    # 转换为 HungarianMatcher 期望的格式：{'bbox': [xmin, ymin, xmax, ymax], 'token': str}

    gt_data = []
    for i, bbox in enumerate(gt_bboxes_list):
        if bbox:
            gt_data.append({"bbox": bbox, "token": gt_color_map[i][0]})

    pred_data = []
    for i, bbox in enumerate(pred_bboxes_list):
        if bbox:
            pred_data.append({"bbox": bbox, "token": pred_color_map[i][0]})

    matcher = HungarianMatcher()
    size_tuple = (max_w, max_h)

    matched_idxes = matcher(gt_data, pred_data, size_tuple, size_tuple)

    # RANSAC 几何验证
    src, dst = [], []
    for idx1, idx2 in matched_idxes:
        # 计算中心点
        x1_c = (gt_data[idx1]["bbox"][0] + gt_data[idx1]["bbox"][2]) / 2
        y1_c = (gt_data[idx1]["bbox"][1] + gt_data[idx1]["bbox"][3]) / 2
        x2_c = (pred_data[idx2]["bbox"][0] + pred_data[idx2]["bbox"][2]) / 2
        y2_c = (pred_data[idx2]["bbox"][1] + pred_data[idx2]["bbox"][3]) / 2
        src.append([y1_c, x1_c])
        dst.append([y2_c, x2_c])

    src, dst = np.array(src), np.array(dst)
    min_samples = 3

    if src.shape[0] <= min_samples:
        inliers = np.ones(len(matched_idxes), dtype=bool)
    else:
        inliers = np.zeros(len(matched_idxes), dtype=bool)
        for _ in range(5):
            if np.sum(~inliers) <= min_samples:
                break
            # SimpleAffineTransform expects (N, 2)
            # RANSAC fits model to data
            try:
                model, inliers_1 = ransac(
                    (src[~inliers], dst[~inliers]),
                    SimpleAffineTransform,
                    min_samples=min_samples,
                    residual_threshold=20,
                    max_trials=50,
                )
                if inliers_1 is not None and inliers_1.any():
                    inliers = update_inliers(inliers, inliers_1)
                else:
                    break
            except Exception:
                # 数据退化时 RANSAC 可能失败
                break

    # 复查内点的 token 代价：token 完全不同时即使空间对齐也拒绝
    for idx, (a, b) in enumerate(matched_idxes):
        if inliers[idx] and matcher.cost["token"][a, b] == 1:
            inliers[idx] = False

    match_num = np.sum(inliers)

    num_gt = len(gt_bboxes_list)
    num_pred = len(pred_bboxes_list)

    f1, recall, precision = calculate_metrics(num_gt, num_pred, match_num)

    if visualize:
        vis_img = np.full((max_h * 2 + 10, max_w, 3), 255, dtype=np.uint8)
        vis_img[0:max_h, 0:max_w] = final_gt_img
        vis_img[max_h + 10 : max_h + 10 + max_h, 0:max_w] = final_pred_img

        # 绘制内点匹配
        for idx, (gt_idx, pred_idx) in enumerate(matched_idxes):
            if inliers[idx]:
                gt_box = gt_data[gt_idx]["bbox"]
                pred_box = pred_data[pred_idx]["bbox"]

                # 绘制边界框
                cv2.rectangle(
                    vis_img,
                    (gt_box[0], gt_box[1]),
                    (gt_box[2], gt_box[3]),
                    (0, 255, 0),
                    1,
                )
                y_offset = max_h + 10
                cv2.rectangle(
                    vis_img,
                    (pred_box[0], pred_box[1] + y_offset),
                    (pred_box[2], pred_box[3] + y_offset),
                    (0, 0, 255),
                    1,
                )

                # 绘制连线
                pt1 = (
                    int((gt_box[0] + gt_box[2]) / 2),
                    int((gt_box[1] + gt_box[3]) / 2),
                )
                pt2 = (
                    int((pred_box[0] + pred_box[2]) / 2),
                    int((pred_box[1] + pred_box[3]) / 2) + y_offset,
                )
                cv2.line(vis_img, pt1, pt2, (255, 0, 0), 1)

    return (f1, recall, precision, vis_img) if visualize else (f1, recall, precision)


class FastCDM:
    def __init__(self, chromedriver: str = None) -> None:
        self.chromedriver = chromedriver
        self.check_environment()
        self.render_worker = None
        self.init_render_worker()

    def check_environment(self) -> None:
        """
        检查运行环境是否准备就绪。
        1. Node.js 环境是否安装。
        2. ChromeDriver 是否可用。
        """
        # 检查 Node.js
        node_path = shutil.which("node")
        if not node_path:
            raise RuntimeError(
                "Node.js is not found. Please install Node.js for formula normalization. "
                "Visit https://nodejs.org/ to install it."
            )

        try:
            subprocess.check_output(["node", "--version"], text=True)
        except Exception as e:
            raise RuntimeError(f"Node.js is found but failed to execute: {e}")

        # 检查 ChromeDriver
        if self.chromedriver:
            if not os.path.exists(self.chromedriver):
                raise FileNotFoundError(f"Specified ChromeDriver not found at: {self.chromedriver}")
        else:
            chromedriver_path = shutil.which("chromedriver")
            if not chromedriver_path:
                raise RuntimeError(
                    "ChromeDriver not found in PATH and no path was specified. "
                    "Please install ChromeDriver or provide the path via the 'chromedriver' parameter. "
                    "You can also use 'scripts/auto_install_chromedriver.py' to download it."
                )

    def init_render_worker(self) -> None:
        try:
            self.render_worker = RenderWorker(
                template_file="file://" + str(TEMPLATE_FILE.resolve()),
                timeout=30,
                driver_path=self.chromedriver,
            )
        except Exception as e:
            print("Failed to init RenderWorker:")
            print("=" * 30)
            print(traceback.format_exc())
            return None

    def close(self):
        if self.render_worker:
            self.render_worker.close()
            self.render_worker = None

    def __del__(self):
        self.close()

    def render(self, latex_list: list) -> list:
        """
        渲染 LaTeX 表达式列表。

        参数:
            latex_list (list): LaTeX 表达式列表。

        返回:
            list: 渲染后的图像列表。
        """
        try:
            latex_strings = [
                f"$${s}$$" if not s.startswith("$$") else s for s in latex_list
            ]
            imgs = self.render_worker.render(latex_strings)
        except Exception as e:
            print("Rendering failed:")
            print("=" * 30)
            print(traceback.format_exc())
            return []

        assert len(imgs) == len(
            latex_strings
        ), "Number of rendered images must match number of input strings"
        return imgs

    def compute(self, gt: str, pred: str, visualize: bool = False) -> tuple:
        """
        计算给定的 GT 和预测 LaTeX 表达式的 CDM 分数。

        参数:
            gt (str):  ground truth LaTeX 表达式。
            pred (str): 预测 LaTeX 表达式。

        返回:
            tuple: 包含 F1 分数、召回率和准确率的元组。
        """
        gt_latex, gt_color_map = preprocess(gt)
        pred_latex, pred_color_map = preprocess(pred)

        imgs = self.render([gt_latex, pred_latex])
        gt_img, pred_img = imgs[0], imgs[1]

        result = postprocess(gt_img, pred_img, gt_color_map, pred_color_map, visualize)
        return result

    def batch_compute(self, gt_list: list, pred_list: list) -> list:
        """
        TODO
        批量计算给定的 GT 和预测 LaTeX 表达式的 CDM 分数。

        参数:
            gt_list (list):  ground truth LaTeX 表达式列表。
            pred_list (list): 预测 LaTeX 表达式列表。

        返回:
            list: 包含每个表达式的 F1 分数、召回率和准确率的元组列表。
        """
        raise NotImplementedError("batch_compute is not implemented yet.")


if __name__ == "__main__":
    # gt = r"A_{M123}=u\,A^{M}"
    # pred = r"A_M123 = \hat{u} A^M"

    # gt = r"r = \frac { \alpha } { \beta } \vert \sin \beta \left( \sigma _ { 1 } \pm \sigma _ { 2 } \right) \vert"
    # pred = r"r={\frac{\alpha}{\beta}}|\sin\beta\left(\sigma_{2}+\sigma_{1}\right)|"

    # gt = r"\frac{1}{2}"
    # pred = r"\frac{1}{2}"

    # gt = r"\tilde{\theta}_k(t)=\frac{\hat{\theta}_k(t+1)-\hat{\theta}_k(t)}{T_s}"
    # pred = r"\tilde{\theta}_k(t)=\frac{\hat{\theta}_k(t+1)-\hat{\theta}_k(t)}{T_s}"

    gt = r"\begin{bmatrix}(\mathbf{I}-\mathbf{A}^{\mathsf{DD}})&-\mathbf{A}^{\mathsf{DP }}&-\mathbf{A}^{\mathsf{DN}}\\ 0&\mathbf{I}&0\\ -\mathbf{A}^{\mathsf{ND}}&-\mathbf{A}^{\mathsf{NP}}&(\mathbf{I}-\mathbf{A}^{ \mathsf{NN}})\end{bmatrix}^{-1}=\begin{bmatrix}\mathbf{B}^{\mathsf{DD}}& \mathbf{B}^{\mathsf{DP}}&\mathbf{B}^{\mathsf{DN}}\\ \mathbf{B}^{\mathsf{PD}}&\mathbf{B}^{\mathsf{PP}}&\mathbf{B}^{\mathsf{PN}}\\ \mathbf{B}^{\mathsf{ND}}&\mathbf{B}^{\mathsf{NP}}&\mathbf{B}^{\mathsf{NN}} \end{bmatrix}"
    pred = r"\left[ \begin{array} { c c c } { ( I - A ^ { \mathrm { D D } } ) } & { - A ^ { \mathrm { D P } } } & { - A ^ { \mathrm { D N } } } \\ { 0 } & { \mathbf { I } } & { 0 } \\ { - A ^ { \mathrm { N D } } } & { - A ^ { \mathrm { N P } } } & { ( I - A ^ { \mathrm { N N } } ) } \end{array} \right] ^ { - 1 } = \left[ \begin{array} { c c c } { \mathbf { B } ^ { \mathrm { D D } } } & { \mathbf { B } ^ { \mathrm { D P } } } & { \mathbf { B } ^ { \mathrm { D N } } } \\ { \mathbf { B } ^ { \mathrm { P D } } } & { \mathbf { B } ^ { \mathrm { P P } } } & { \mathbf { B } ^ { \mathrm { P N } } } \\ { \mathbf { B } ^ { \mathrm { N D } } } & { \mathbf { B } ^ { \mathrm { N P } } } & { \mathbf { B } ^ { \mathrm { N N } } } \end{array} \right]"

    fastcdm = FastCDM(chromedriver="driver/chromedriver")
    res = fastcdm.compute(gt, pred, visualize=True)
    f1, recall, precision, vis_img = res
    print(f"CDM Score (F1): {f1:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"Precision: {precision:.4f}")
    try:
        out_dir = Path(__file__).parent.parent / "vis"
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_dir / "match_vis.png"), vis_img)
    except Exception:
        pass
