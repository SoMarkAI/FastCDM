import numpy as np
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment


class SimpleAffineTransform:
    def __init__(self, translation=(0, 0), scale=1.0):
        self.translation = np.array(translation)
        self.scale = scale

    def estimate(self, src, dst):
        src_center = np.mean(src, axis=0)
        dst_center = np.mean(dst, axis=0)
        self.translation = dst_center - src_center
        src_dists = np.linalg.norm(src - src_center, axis=1)
        dst_dists = np.linalg.norm(dst - dst_center, axis=1)
        self.scale = np.mean(dst_dists) / (np.mean(src_dists) + 1e-10)

    def inverse(self):
        return SimpleAffineTransform(-self.translation, 1.0 / self.scale)

    def __call__(self, coords):
        return (
            self.scale * (coords - np.mean(coords, axis=0))
            + np.mean(coords, axis=0)
            + self.translation
        )

    def residuals(self, src, dst):
        return np.sqrt(np.sum((self(src) - dst) ** 2, axis=1))


def norm_coords(x, left, right):
    if x < left:
        return left
    if x > right:
        return right
    return x


def norm_same_token(token):
    special_map = {
        "\\dot": ".",
        "\\Dot": ".",
        "\\cdot": ".",
        "\\cdotp": ".",
        "\\ldotp": ".",
        "\\mid": "|",
        "\\rightarrow": "\\to",
        "\\top": "T",
        "\\Tilde": "\\tilde",
        "\\prime": "'",
        "\\ast": "*",
        "\\left<": "\\langle",
        "\\right>": "\\rangle",
        "\\lbrace": "\{",
        "\\rbrace": "\}",
        "\\lbrack": "[",
        "\\rbrack": "]",
        "\\blackslash": "/",
        "\\slash": "/",
        "\\leq": "\\le",
        "\\geq": "\\ge",
        "\\neq": "\\ne",
        "\\Vert": "\\|",
        "\\lVert": "\\|",
        "\\rVert": "\\|",
        "\\vert": "|",
        "\\lvert": "|",
        "\\rvert": "|",
        "\\colon": ":",
        "\\Ddot": "\\ddot",
        "\\Bar": "\\bar",
        "\\Vec": "\\vec",
        "\\parallel": "\\|",
        "\\dag": "\\dagger",
        "\\ddag": "\\ddagger",
        "\\textlangle": "<",
        "\\textrangle": ">",
        "\\textgreater": ">",
        "\\textless": "<",
        "\\textbackslash": "\\",
        "\\textunderscore": "_",
        "\\=": "=",
        "\\neg": "\\lnot",
        "\\neq": "\\not=",
    }
    if token.startswith("\\left") or token.startswith("\\right"):
        if (
            "arrow" not in token
            and "<" not in token
            and ">" not in token
            and "harpoon" not in token
        ):
            token = token.replace("\\left", "").replace("\\right", "")
    if token.startswith("\\big") or token.startswith("\\Big"):
        if "\\" in token[4:]:
            token = "\\" + token[4:].split("\\")[-1]
        else:
            token = token[-1]
    if token in special_map.keys():
        token = special_map[token]
    if token.startswith("\\wide"):
        return token.replace("wide", "")
    if token.startswith("\\var"):
        return token.replace("var", "")
    if token.startswith("\\string"):
        return token.replace("\\string", "")
    return token


class HungarianMatcher:
    def __init__(
        self,
        cost_token: float = 1,
        cost_position: float = 0.05,
        cost_order: float = 0.15,
    ):
        self.cost_token = cost_token
        self.cost_position = cost_position
        self.cost_order = cost_order
        self.cost = {}

    def calculate_token_cost(self, box_gt, box_pred):

        all_tokens = [data["token"] for data in box_gt + box_pred]
        unique_tokens = sorted(list(set(all_tokens)))
        token2id = {token: i for i, token in enumerate(unique_tokens)}
        num_classes = len(token2id)

        all_norm_tokens = [norm_same_token(data["token"]) for data in box_gt + box_pred]
        unique_norm_tokens = sorted(list(set(all_norm_tokens)))
        token2id_norm = {token: i for i, token in enumerate(unique_norm_tokens)}
        num_classes_norm = len(token2id_norm)

        gt_token_array = np.array([token2id[data["token"]] for data in box_gt])
        norm_gt_token_array = np.array(
            [token2id_norm[norm_same_token(data["token"])] for data in box_gt]
        )

        pred_token_logits = np.zeros((len(box_pred), num_classes))
        for i, data in enumerate(box_pred):
            if data["token"] in token2id:
                pred_token_logits[i, token2id[data["token"]]] = 1

        norm_pred_token_logits = np.zeros((len(box_pred), num_classes_norm))
        for i, data in enumerate(box_pred):
            norm_token = norm_same_token(data["token"])
            if norm_token in token2id_norm:
                norm_pred_token_logits[i, token2id_norm[norm_token]] = 1

        if gt_token_array.size == 0 or pred_token_logits.shape[0] == 0:
            return np.empty((len(box_gt), len(box_pred)))

        token_cost = 1.0 - pred_token_logits[:, gt_token_array]
        norm_token_cost = 1.0 - norm_pred_token_logits[:, norm_gt_token_array]

        token_cost[np.logical_and(token_cost == 1, norm_token_cost == 0)] = 0.005
        return token_cost.T

    def box2array(self, box_list, size):
        W, H = size
        box_array = []
        for box in box_list:
            x_min, y_min, x_max, y_max = box["bbox"]
            box_array.append(
                [
                    (x_min + x_max) / (2 * W),
                    (y_min + y_max) / (2 * H),
                    (x_max - x_min) / W,
                    (y_max - y_min) / H,
                ]
            )
        return np.array(box_array)

    def order2array(self, box_list, max_token_lens=None):
        if not max_token_lens:
            max_token_lens = len(box_list)
        return np.array([[idx / max_token_lens] for idx, _ in enumerate(box_list)])

    def calculate_l1_cost(self, gt_array, pred_array):
        if gt_array.shape[0] == 0 or pred_array.shape[0] == 0:
            return np.empty((gt_array.shape[0], pred_array.shape[0]))
        return cdist(gt_array, pred_array, "minkowski", p=1) / gt_array.shape[-1]

    def __call__(self, box_gt, box_pred, gt_size, pred_size):
        if not box_gt or not box_pred:
            return []
        gt_box_array = self.box2array(box_gt, gt_size)
        pred_box_array = self.box2array(box_pred, pred_size)
        max_token_lens = max(len(box_gt), len(box_pred))
        gt_order_array = self.order2array(box_gt, max_token_lens)
        pred_order_array = self.order2array(box_pred, max_token_lens)
        token_cost = self.calculate_token_cost(box_gt, box_pred)
        position_cost = self.calculate_l1_cost(gt_box_array, pred_box_array)
        order_cost = self.calculate_l1_cost(gt_order_array, pred_order_array)
        self.cost = {
            "token": token_cost,
            "position": position_cost,
            "order": order_cost,
        }
        cost = (
            self.cost_token * token_cost
            + self.cost_position * position_cost
            + self.cost_order * order_cost
        )
        cost[np.isnan(cost) | np.isinf(cost)] = 100
        row_ind, col_ind = linear_sum_assignment(cost)
        return list(zip(row_ind, col_ind))


def update_inliers(ori_inliers, sub_inliers):
    inliers = np.copy(ori_inliers)
    sub_idx = -1
    for idx in range(len(ori_inliers)):
        if not ori_inliers[idx]:
            sub_idx += 1
            if sub_inliers[sub_idx]:
                inliers[idx] = True
    return inliers

