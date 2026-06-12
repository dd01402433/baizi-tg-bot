"""
Baizi Fortune (八字算命) - 中国古代算命术 Python 引擎

基于洪丕谟、姜玉珍著《中国古代算命术》全书实现的四柱八字排盘与秤骨算命。

Usage:
    from baizi_fortune import fortune_telling, format_report
    result = fortune_telling(1990, 6, 16, 2, 16, "男")
    print(format_report(result))
"""

from .engine import (
    fortune_telling,
    format_report,
)

__version__ = "1.0.0"
__all__ = ["fortune_telling", "format_report"]
