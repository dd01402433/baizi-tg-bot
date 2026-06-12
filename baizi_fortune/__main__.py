"""
命令行入口 - python -m baizi_fortune
"""

import sys
from .engine import fortune_telling, format_report


def main():
    if len(sys.argv) >= 6:
        # 命令行模式: python -m baizi_fortune 1990 6 16 2 16 男
        year = int(sys.argv[1])
        month = int(sys.argv[2])
        day = int(sys.argv[3])
        hour = int(sys.argv[4])
        minute = int(sys.argv[5]) if len(sys.argv) > 5 else 0
        gender = sys.argv[6] if len(sys.argv) > 6 else "男"
        result = fortune_telling(year, month, day, hour, minute, gender)
        print(format_report(result))
    else:
        # 交互模式
        print("=" * 60)
        print("  八字算命 - 基于《中国古代算命术》(洪丕谟、姜玉珍 著)")
        print("=" * 60)
        try:
            year = int(input("出生年份(公历，如1990): "))
            month = int(input("出生月份(1-12): "))
            day = int(input("出生日期(1-31): "))
            hour = int(input("出生小时(0-23): "))
            minute = int(input("出生分钟(0-59，默认0): ") or "0")
            gender = input("性别(男/女，默认男): ") or "男"
            result = fortune_telling(year, month, day, hour, minute, gender)
            print(format_report(result))
        except ValueError as e:
            print(f"[错误] 输入格式不正确: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n已取消")
            sys.exit(0)


if __name__ == "__main__":
    main()
