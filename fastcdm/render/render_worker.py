import os
import cv2
import random
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class RenderResult:
    image: Optional[np.ndarray]
    error: bool
    error_text: Optional[str]
    width: int
    height: int


class RenderWorker:
    """
    一个使用 Selenium Headless Chrome 渲染HTML内容的工具类。
    它可以加载一个HTML模板，通过JavaScript渲染内容（如数学公式），
    并截取渲染后各元素的图像。
    """

    def __init__(self, template_file: str, timeout: int = 15, driver_path: str = None):
        # --- 配置浏览器选项 ---
        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--hide-scrollbars")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--log-level=3")
        opts.add_experimental_option("excludeSwitches", ["enable-logging"])
        opts.add_argument("--disable-font-antialiasing")
        opts.add_argument("--allow-file-access-from-files")

        # --- 使用 webdriver-manager 自动管理 ChromeDriver（需要代理下载）---
        if driver_path is None:
            driver_path = ChromeDriverManager().install()
            print(f"Installed driver_path: {driver_path}")
        elif not os.path.exists(driver_path):
            # TODO：如果指定路径不存在，则在该路径安装 ChromeDriver
            raise FileNotFoundError(f"ChromeDriver 未找到：{driver_path}")

        # 临时清除代理环境变量，避免 Selenium 连接到 ChromeDriver 时出现问题
        saved_http_proxy = os.environ.pop("http_proxy", None)
        saved_https_proxy = os.environ.pop("https_proxy", None)

        try:
            service = ChromeService(driver_path)
            # --- 初始化 WebDriver ---
            self.driver = webdriver.Chrome(service=service, options=opts)
        finally:
            # 恢复代理设置
            if saved_http_proxy:
                os.environ["http_proxy"] = saved_http_proxy
            if saved_https_proxy:
                os.environ["https_proxy"] = saved_https_proxy

        self.driver.get(template_file)

        self.timeout = timeout

        # 定义一个固定的窗口宽度
        self.window_fix_width = 2000
        self.window_init_height = 300

        self.driver.set_window_size(self.window_fix_width, self.window_init_height)

        # 动态计算浏览器边框和工具栏的高度
        self.outer_height = self.window_init_height - self.driver.execute_script(
            "return window.innerHeight"
        )

        # 等待页面容器加载完成
        WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_all_elements_located((By.ID, "container"))
        )

    def render(self, contents: List[str]) -> List[RenderResult]:
        if not contents:
            return []
        try:
            return self._render(contents)
        except (WebDriverException, cv2.error) as exc:
            return [RenderResult(None, True, type(exc).__name__, 0, 0) for _ in contents]

    def _render(self, contents: List[str]) -> List[RenderResult]:
        """
        渲染一组内容并返回每个元素的截图。
        """
        # 通过JS调用页面内的render函数
        self.driver.execute_script(
            "document.body.classList.remove('rendering-complete');"
        )
        self.driver.execute_script("render(arguments[0], false)", contents)

        # 等待JS渲染完成的信号
        WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, "rendering-complete"))
        )

        # 根据内容的总高度调整窗口大小，以确保能截取完整图像
        scroll_height = self.driver.execute_script(
            "return document.getElementById('container').scrollHeight"
        )
        # Chrome 窗口高度限制（通常最大约为 2^31 像素，但实际会更小）
        # 设置一个安全的最大高度值
        MAX_WINDOW_HEIGHT = 10000
        # 确保 outer_height 不会导致负值或过小值
        # 使用绝对值并添加额外的边距以确保内容完全可见
        safe_outer_height = max(abs(self.outer_height), 100)
        target_height = min(
            max(scroll_height + safe_outer_height, 100), MAX_WINDOW_HEIGHT
        )
        self.driver.set_window_size(self.window_fix_width, target_height)

        dom_results = self.driver.execute_script(
            "return [...document.querySelectorAll('.screenshot')].map(element => {"
            " const rect = element.getBoundingClientRect();"
            " const error = element.querySelector('.katex-error');"
            " return {"
            "   error: Boolean(error || element.dataset.renderError),"
            "   errorText: element.dataset.renderError || (error ? error.textContent : null),"
            "   width: Math.ceil(Math.max(element.scrollWidth, rect.width)),"
            "   height: Math.ceil(Math.max(element.scrollHeight, rect.height))"
            " };"
            "});"
        )
        if len(dom_results) != len(contents):
            return [
                RenderResult(None, True, "DOM result count mismatch", 0, 0)
                for _ in contents
            ]

        # 获取整个页面的截图
        png = self.driver.get_screenshot_as_png()
        nparr = np.frombuffer(png, np.uint8)
        fullpage_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if fullpage_img is None or fullpage_img.size == 0:
            return [
                RenderResult(
                    None,
                    True,
                    result.get("errorText") or "Empty browser screenshot",
                    int(result.get("width") or 0),
                    int(result.get("height") or 0),
                )
                for result in dom_results
            ]

        # 获取每个渲染元素的边界框
        rects = self.get_rects()
        if len(rects) != len(contents):
            return [RenderResult(None, True, "Capture rectangle count mismatch", 0, 0) for _ in contents]
        results = []
        img_h, img_w = fullpage_img.shape[:2]

        # 根据边界框裁剪出每个元素的图像
        for rect, dom_result in zip(rects, dom_results):
            width = int(dom_result.get("width") or 0)
            height = int(dom_result.get("height") or 0)
            error_text = dom_result.get("errorText")
            if rect is None or rect[2] <= 0 or rect[3] <= 0 or rect[0] < 0 or rect[1] < 0 or rect[0] + rect[2] > img_w or rect[1] + rect[3] > img_h:
                results.append(
                    RenderResult(None, True, error_text or "Invalid capture rectangle", width, height)
                )
            else:
                x, y, w, h = rect
                # 计算一个小的随机边距，让截图更自然
                max_side = max(w, h)
                base_border = int(max_side * 0.03)
                border_size = int(base_border * random.uniform(0.8, 1.2))
                x1 = max(0, x - border_size)
                y1 = max(0, y - border_size)
                x2 = min(img_w, x + w + border_size)
                y2 = min(img_h, y + h + border_size)

                cropped = fullpage_img[y1:y2, x1:x2]
                if cropped.size == 0:
                    results.append(
                        RenderResult(None, True, error_text or "Empty cropped image", width, height)
                    )
                else:
                    results.append(
                        RenderResult(
                            cropped,
                            bool(dom_result.get("error")),
                            error_text,
                            width,
                            height,
                        )
                    )

        return results

    def get_rects(self) -> list:
        """
        获取页面上所有渲染元素的位置和大小信息。
        """
        elements = WebDriverWait(self.driver, self.timeout).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "screenshot"))
        )

        rects = []
        for element in elements:
            location = element.location
            size = element.size
            x = int(location["x"])
            y = int(location["y"])
            w = int(size["width"])
            h = int(size["height"])

            # 如果元素宽度超过窗口，可能是一个渲染错误，标记为None
            if w > self.window_fix_width:
                rects.append(None)
            else:
                rects.append((x, y, w, h))

        return rects

    def close(self):
        """
        关闭浏览器驱动并释放资源。
        """
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __del__(self):
        """
        对象销毁时确保浏览器被关闭。
        """
        try:
            self.close()
        except Exception:
            pass
