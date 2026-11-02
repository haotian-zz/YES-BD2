"""梦幻广场的界面（bd2 会话 2026-11-01 更新后）。

广场现在和箱庭一样：右上角一排白色小图标（相机、C、I、H 主页），底部中间那排
快速切换按钮没了，所以 QUICK_SWITCH_TEMPLATE 在广场里一直是 -1。右上角主页
按钮底下的「创建队伍」长条字样稳定、主页上没有，用它认广场。
"""

from __future__ import annotations

from src.utils.calibration import FHD_1080
from src.utils.ocr_utils import normalize_ocr_text

# 1920x1080 参考：主页图标（H）的中心。
SQUARE_HOME_REFERENCE_POINT = (1797, 63)
SQUARE_HOME_RELATIVE_POINT = (
    SQUARE_HOME_REFERENCE_POINT[0] / FHD_1080.width,
    SQUARE_HOME_REFERENCE_POINT[1] / FHD_1080.height,
)
# 「创建队伍」长条（1080p 约 1570-1855, 135-165）；x/y/宽/高。
SQUARE_PARTY_OCR_REFERENCE_ROI = (1520, 115, 380, 70)
SQUARE_PARTY_OCR_RELATIVE_ROI = (
    1520 / FHD_1080.width,
    115 / FHD_1080.height,
    1900 / FHD_1080.width,
    185 / FHD_1080.height,
)
SQUARE_PARTY_LABEL = "创建队伍"


def square_party_label_read(text: object) -> bool:
    """「创建队伍」读到三个字以上就算（亮背景上偶尔少读一个字）。"""
    normalized = normalize_ocr_text(str(text or ""))
    if SQUARE_PARTY_LABEL in normalized:
        return True
    return any(SQUARE_PARTY_LABEL[i : i + 3] in normalized for i in range(2))
