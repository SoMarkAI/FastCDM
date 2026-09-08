# DOM 错误检测分支验证记录

验证日期：2026-09-07。分支：`fix/dom-render-error-detection`。

本轮结果：`16 passed`，没有跳过测试。运行命令为设置 `CHROMEDRIVER` 后执行 `python -m pytest tests -q -p no:cacheprovider`。

环境：本机 Chrome 152.0.7977.77；缓存 ChromeDriver 151.0.7922.138。本次组合成功启动并通过测试，但主版本不一致，不作为 CI 固定版本推荐；CI 应使用匹配版本。

## 实际发现并修正的问题

- 原有真实浏览器测试失败：`throwOnError: false` 下未知命令显示红字但没有 `.katex-error`，因此误报成功。现在逐公式调用 auto-render，设置 `throwOnError: true`，通过 `errorCallback` 将解析错误记录到元素的 `data-render-error`。Python 同时检查该属性和 `.katex-error`。
- `RenderWorker.render()` 捕获 Selenium 的 `WebDriverException`（含超时和脚本异常）以及 OpenCV 解码异常，按输入数量返回失败结果。异常类型保存在 `error_text`。
- 补齐裁剪矩形数量检查、零尺寸、负坐标和越过截图边界检查，避免 zip 截断或部分截图冒充成功。
- `render_results()` 在 renderer 不可用时返回失败；`compute()` 要求恰好两个结果。

## 测试覆盖

- 真实 Chrome：合法红色公式、未知命令错误、后续正常渲染清除之前的错误状态、页面不发完成信号触发真实超时。
- 模拟边界：超时、脚本异常、WebDriver 异常、DOM 数量不一致、空截图、矩形数量不一致、无效及越界裁剪。
- 评分入口：超时返回兼容零元组并增加失败计数，不调用后处理。
- 空输入批次不访问浏览器。

本轮仅验证 DOM 分支，不包含其他六个分支，也未执行历史 88 对公式的全量回归。修改保留为 worktree 未提交差异，便于 VS Code Source Control 查看；未合并。
