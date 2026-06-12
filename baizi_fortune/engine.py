#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《中国古代算命术》八字排盘与秤骨算命引擎
基于洪丕谟、姜玉珍《中国古代算命术 古今世俗研究1(增补本)1992年12月第3版》
"""

from datetime import datetime, timedelta
import json
from collections import defaultdict

# ============================================================
# 一、基础数据表
# ============================================================

# 十天干
TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]

# 十二地支
DI_ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# 生肖
SHENG_XIAO = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

# 天干阴阳: 阳=1, 阴=0
TIAN_GAN_YIN_YANG = {"甲": 1, "乙": 0, "丙": 1, "丁": 0, "戊": 1, "己": 0, "庚": 1, "辛": 0, "壬": 1, "癸": 0}

# 地支阴阳
DI_ZHI_YIN_YANG = {"子": 1, "丑": 0, "寅": 1, "卯": 0, "辰": 1, "巳": 0, "午": 1, "未": 0, "申": 1, "酉": 0, "戌": 1, "亥": 0}

# 天干五行
TIAN_GAN_WU_XING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水"
}

# 地支五行
DI_ZHI_WU_XING = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"
}

# 地支藏干
DI_ZHI_CANG_GAN = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"]
}

# 六十甲子
LIU_SHI_JIA_ZI = []
for i in range(60):
    LIU_SHI_JIA_ZI.append(TIAN_GAN[i % 10] + DI_ZHI[i % 12])

# 纳音五行
NA_YIN = [
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
    "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
    "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
    "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
    "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水"
]

# 时辰对照
SHI_CHEN = {
    0: "子", 1: "子", 2: "丑", 3: "丑", 4: "寅", 5: "寅",
    6: "卯", 7: "卯", 8: "辰", 9: "辰", 10: "巳", 11: "巳",
    12: "午", 13: "午", 14: "未", 15: "未", 16: "申", 17: "申",
    18: "酉", 19: "酉", 20: "戌", 21: "戌", 22: "亥", 23: "亥"
}

SHI_CHEN_NAME = {
    "子": "子时(23:00-01:00)", "丑": "丑时(01:00-03:00)",
    "寅": "寅时(03:00-05:00)", "卯": "卯时(05:00-07:00)",
    "辰": "辰时(07:00-09:00)", "巳": "巳时(09:00-11:00)",
    "午": "午时(11:00-13:00)", "未": "未时(13:00-15:00)",
    "申": "申时(15:00-17:00)", "酉": "酉时(17:00-19:00)",
    "戌": "戌时(19:00-21:00)", "亥": "亥时(21:00-23:00)"
}

# 五虎遁月干表 [年干索引][月份-1]
# 年干索引: 甲0 乙1 丙2 丁3 戊4 己5 庚6 辛7 壬8 癸9
# 但五虎遁是甲己同、乙庚同... 所以用规则计算
def wu_hu_dun(nian_gan, yue_zhi_idx):
    """五虎遁：根据年干和月支索引(寅=0)返回月干索引"""
    nian_gan_idx = TIAN_GAN.index(nian_gan)
    # 甲己之年丙作首 -> (年干甲0或己5) -> 丙2
    base = {
        0: 2, 5: 2,  # 甲己 -> 丙寅
        1: 4, 6: 4,  # 乙庚 -> 戊寅
        2: 6, 7: 6,  # 丙辛 -> 庚寅
        3: 8, 8: 8,  # 丁壬 -> 壬寅
        4: 0, 9: 0,  # 戊癸 -> 甲寅
    }
    start = base[nian_gan_idx]
    return (start + yue_zhi_idx) % 10

def wu_shu_dun(ri_gan, shi_zhi_idx):
    """五鼠遁：根据日干和时支索引(子=0)返回时干索引"""
    ri_gan_idx = TIAN_GAN.index(ri_gan)
    base = {
        0: 0, 5: 0,  # 甲己 -> 甲子
        1: 2, 6: 2,  # 乙庚 -> 丙子
        2: 4, 7: 4,  # 丙辛 -> 戊子
        3: 6, 8: 6,  # 丁壬 -> 庚子
        4: 8, 9: 8,  # 戊癸 -> 壬子
    }
    start = base[ri_gan_idx]
    return (start + shi_zhi_idx) % 10

# ============================================================
# 二、节气数据库（1901-2000年，节=月界的关键节气）
# 格式: 每年12个节气的 (月, 日)，按 立春 惊蛰 清明 立夏 芒种 小暑 立秋 白露 寒露 立冬 大雪 小寒
# ============================================================
# 由于篇幅限制，这里内置常用年份的节气近似数据（精确到日）
# 实际使用中基于公式计算
JIE_QI_MONTH_DAYS = {
    "立春": (2, 4), "惊蛰": (3, 6), "清明": (4, 5), "立夏": (5, 6),
    "芒种": (6, 6), "小暑": (7, 7), "立秋": (8, 8), "白露": (9, 8),
    "寒露": (10, 8), "立冬": (11, 8), "大雪": (12, 7), "小寒": (1, 6)
}

def is_leap_year(year):
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def get_jie_qi_day(year, jie_qi_name):
    """
    获取指定年份某节气的公历日期（近似计算）
    基于1900-2000年节气基本规律，大部分年份误差在1天内
    """
    base = JIE_QI_MONTH_DAYS[jie_qi_name]
    month, day = base

    # 闰年对2月后节气微调（实际节气在闰年可能早1天）
    if is_leap_year(year) and month > 2:
        day -= 1
    # 3月惊蛰在闰年
    if jie_qi_name == "惊蛰" and is_leap_year(year):
        day = 5  # 闰年惊蛰多为3月5日

    return (month, max(day, 1))

# ============================================================
# 三、公历转农历日柱计算（精确到日干支）
# ============================================================
def get_day_gan_zhi(year, month, day):
    """
    计算公历日期的日柱干支（基于已知基准日推算）
    基准：1900年1月1日 = 甲戌 (10)
    """
    base_date = datetime(1900, 1, 1)
    base_gz_idx = 10  # 甲戌在六十甲子中索引为10

    target_date = datetime(year, month, day)
    delta_days = (target_date - base_date).days

    gz_idx = (base_gz_idx + delta_days) % 60
    return LIU_SHI_JIA_ZI[gz_idx]

def get_year_gan_zhi(year):
    """获取年柱干支（以立春为界）"""
    # 立春一般在2月4日左右
    reference_year = 1984  # 甲子年
    diff = year - reference_year

    # 如果日期在立春前，年柱属上一年
    # 此处返回公历年的初始年柱，调用方需要根据具体日期判断
    return LIU_SHI_JIA_ZI[(diff % 60 + 60) % 60]

def get_accurate_year_gan_zhi(year, month, day):
    """获取精确年柱（考虑立春分界）"""
    jie_qi_m, jie_qi_d = get_jie_qi_day(year, "立春")
    # 如果出生在立春之前，年柱用上一年
    if month < jie_qi_m or (month == jie_qi_m and day < jie_qi_d):
        return get_year_gan_zhi(year - 1)
    return get_year_gan_zhi(year)

def get_month_zhi_idx(month, day, year):
    """根据公历月日获取月支索引（以节气为界）"""
    # 节气列表
    jie_qi_names = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
                    "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]
    # 对应的月支索引(寅=0)
    yue_zhi_map = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    # 检查是否在小寒(1/6)之后、立春(2/4)之前
    xiao_han_d = get_jie_qi_day(year, "小寒")[1]
    li_chun_d = get_jie_qi_day(year, "立春")[1]

    if month == 1 and day >= xiao_han_d:
        return 11  # 丑月(十二月)
    if month == 2 and day < li_chun_d:
        return 11  # 还在丑月

    # 遍历十二个节气
    for i, jq_name in enumerate(jie_qi_names):
        jq_month, jq_day = get_jie_qi_day(year, jq_name)
        # 判断是否在该节气之后
        if month > jq_month or (month == jq_month and day >= jq_day):
            # 检查是否在下一个节气之前
            if i < 11:
                next_jq = jie_qi_names[i + 1]
                next_month, next_day = get_jie_qi_day(year, next_jq)
                if month < next_month or (month == next_month and day < next_day):
                    return yue_zhi_map[i]
            else:
                # 最后一个是小寒(已到次年)
                next_year_jq = get_jie_qi_day(year + 1, "立春")
                if month == 12 or (month == 1 and day < next_year_jq[1]):
                    return yue_zhi_map[i]

    return 0  # 默认寅月

# ============================================================
# 四、排四柱
# ============================================================

def pai_si_zhu(year, month, day, hour, minute=0):
    """
    排四柱：返回 {年柱, 月柱, 日柱, 时柱}
    year: 公历年份
    month: 公历月份
    day: 公历日期
    hour: 小时(0-23)
    """
    # 年柱
    nian_gz = get_accurate_year_gan_zhi(year, month, day)
    nian_gan = nian_gz[0]
    nian_zhi = nian_gz[1]

    # 月柱
    yue_zhi_idx = get_month_zhi_idx(month, day, year)
    yue_zhi = DI_ZHI[yue_zhi_idx]
    yue_gan_idx = wu_hu_dun(nian_gan, yue_zhi_idx)
    yue_gan = TIAN_GAN[yue_gan_idx]
    yue_gz = yue_gan + yue_zhi

    # 日柱
    ri_gz = get_day_gan_zhi(year, month, day)
    ri_gan = ri_gz[0]
    ri_zhi = ri_gz[1]

    # 时柱（处理子正问题）
    shi_zhi = SHI_CHEN[hour]
    shi_zhi_idx = DI_ZHI.index(shi_zhi)

    # 子正规则：23:00-0:00为晚子时，用次日日干；0:00-1:00为早子时，用当日日干
    effective_ri_gan = ri_gan
    if hour == 23:
        # 晚子时，用次日日干
        next_date = datetime(year, month, day) + timedelta(days=1)
        next_ri_gz = get_day_gan_zhi(next_date.year, next_date.month, next_date.day)
        effective_ri_gan = next_ri_gz[0]

    shi_gan_idx = wu_shu_dun(effective_ri_gan, shi_zhi_idx)
    shi_gan = TIAN_GAN[shi_gan_idx]
    shi_gz = shi_gan + shi_zhi

    return {
        "年柱": nian_gz, "月柱": yue_gz, "日柱": ri_gz, "时柱": shi_gz,
        "年干": nian_gan, "年支": nian_zhi,
        "月干": yue_gan, "月支": yue_zhi,
        "日干": ri_gan, "日支": ri_zhi,
        "时干": shi_gan, "时支": shi_zhi,
        "纳音": NA_YIN[LIU_SHI_JIA_ZI.index(nian_gz) // 2],
        "生肖": SHENG_XIAO[DI_ZHI.index(nian_zhi)],
        "时辰": SHI_CHEN_NAME.get(shi_zhi, shi_zhi)
    }

# ============================================================
# 五、排大运
# ============================================================

def pai_da_yun(year, month, day, nian_gan, nian_zhi, yue_gz, gender):
    """
    排大运
    gender: "男" 或 "女"
    """
    nian_gan_yang = TIAN_GAN_YIN_YANG[nian_gan]
    is_male = (gender == "男")

    # 阳男阴女顺行，阴男阳女逆行
    shun_xing = (nian_gan_yang == 1 and is_male) or (nian_gan_yang == 0 and not is_male)

    # 起运年龄：顺排数到下一个节气，逆排数到上一个节气
    jie_qi_names = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑",
                    "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]

    birth_date = datetime(year, month, day)

    # 找当前所处节气段
    target_jq = None
    if shun_xing:
        # 找下一个节气
        for jq_name in jie_qi_names:
            jq_month, jq_day = get_jie_qi_day(year, jq_name)
            jq_date = datetime(year, jq_month, jq_day)
            if jq_date > birth_date:
                target_jq = jq_date
                break
        if target_jq is None:
            # 如果当年没有，取下一年立春
            next_lc = get_jie_qi_day(year + 1, "立春")
            target_jq = datetime(year + 1, next_lc[0], next_lc[1])
    else:
        # 找上一个节气
        for jq_name in reversed(jie_qi_names):
            jq_month, jq_day = get_jie_qi_day(year, jq_name)
            jq_date = datetime(year, jq_month, jq_day)
            if jq_date < birth_date:
                target_jq = jq_date
                break
        if target_jq is None:
            # 如果当年没有，取上一年小寒
            prev_xh = get_jie_qi_day(year - 1, "小寒")
            target_jq = datetime(year - 1, prev_xh[0], prev_xh[1])

    days_diff = abs((target_jq - birth_date).days)
    qi_yun_age = max(1, days_diff // 3)  # 三天为一岁

    # 排大运干支序列
    yue_gz_idx = LIU_SHI_JIA_ZI.index(yue_gz)
    da_yun_list = []
    for i in range(1, 9):  # 排8个大运
        if shun_xing:
            da_yun_idx = (yue_gz_idx + i) % 60
        else:
            da_yun_idx = (yue_gz_idx - i) % 60
        da_yun_list.append({
            "干支": LIU_SHI_JIA_ZI[da_yun_idx],
            "起运年龄": qi_yun_age + (i - 1) * 10,
            "十年区间": f"{qi_yun_age + (i-1)*10}-{qi_yun_age + i*10 - 1}岁"
        })

    return {
        "顺逆": "顺排" if shun_xing else "逆排",
        "起运年龄": qi_yun_age,
        "大运列表": da_yun_list
    }

# ============================================================
# 六、十神计算
# ============================================================

def get_shi_shen(ri_gan, other_gan):
    """计算十神关系"""
    if ri_gan == other_gan:
        return "比肩"
    ri_idx = TIAN_GAN.index(ri_gan)
    other_idx = TIAN_GAN.index(other_gan)
    diff = (other_idx - ri_idx) % 10

    same_yin_yang = TIAN_GAN_YIN_YANG[ri_gan] == TIAN_GAN_YIN_YANG[other_gan]

    mapping = {
        # (生克关系, 同异性)
        0: "比肩",  # 同我
        5: "劫财",  # 同我异
        # 我生
        1: "食神" if same_yin_yang else "伤官",  # diff=1 木生火（甲生丙, 同阳=食神）
        # 需要仔细判断
    }

    # 更准确的十神判断
    # ri=甲(0), other=乙(1): 乙是甲的劫财(同我异)
    # ri=甲(0), other=丙(2): 甲生丙(我生), 同阳->食神
    # ri=甲(0), other=丁(3): 甲生丁(我生), 异阳->伤官
    # ri=甲(0), other=戊(4): 甲克戊(我克), 同阳->偏财
    # ri=甲(0), other=己(5): 甲克己(我克), 异阳->正财
    # ri=甲(0), other=庚(6): 庚克甲(克我), 同阳->偏官(七杀)
    # ri=甲(0), other=辛(7): 辛克甲(克我), 异阳->正官
    # ri=甲(0), other=壬(8): 壬生甲(生我), 同阳->偏印(枭)
    # ri=甲(0), other=癸(9): 癸生甲(生我), 异阳->正印

    # 五行的生克关系
    ri_wx = TIAN_GAN_WU_XING[ri_gan]
    other_wx = TIAN_GAN_WU_XING[other_gan]

    if ri_wx == other_wx:  # 同我
        return "比肩" if same_yin_yang else "劫财"
    elif is_sheng(ri_wx, other_wx):  # 我生
        return "食神" if same_yin_yang else "伤官"
    elif is_sheng(other_wx, ri_wx):  # 生我
        return "偏印" if same_yin_yang else "正印"
    elif is_ke(ri_wx, other_wx):  # 我克
        return "偏财" if same_yin_yang else "正财"
    elif is_ke(other_wx, ri_wx):  # 克我
        return "偏官" if same_yin_yang else "正官"

    return "?"

def is_sheng(wx1, wx2):
    """wx1 生 wx2?"""
    order = {"木": 0, "火": 1, "土": 2, "金": 3, "水": 4}
    return (order[wx1] + 1) % 5 == order[wx2]

def is_ke(wx1, wx2):
    """wx1 克 wx2?"""
    order = {"木": 0, "火": 1, "土": 2, "金": 3, "水": 4}
    return (order[wx1] + 2) % 5 == order[wx2]

# ============================================================
# 七、十神分析
# ============================================================

def analyze_shi_shen(si_zhu):
    """全面十神分析"""
    ri_gan = si_zhu["日干"]
    result = {"天干十神": {}, "地支藏干十神": {}, "十神统计": defaultdict(int)}

    # 天干十神
    for col_name in ["年柱", "月柱", "时柱"]:
        gan = si_zhu[col_name][0]
        shen = get_shi_shen(ri_gan, gan)
        result["天干十神"][col_name] = {"天干": gan, "十神": shen}
        result["十神统计"][shen] += 1

    # 日柱自身
    result["天干十神"]["日柱"] = {"天干": ri_gan, "十神": "日主"}

    # 地支藏干十神
    for col_name in ["年柱", "月柱", "日柱", "时柱"]:
        zhi = si_zhu[col_name[0] + "支"]
        cang_gan_list = DI_ZHI_CANG_GAN.get(zhi, [])
        result["地支藏干十神"][col_name] = []
        for cg in cang_gan_list:
            shen = get_shi_shen(ri_gan, cg)
            result["地支藏干十神"][col_name].append({"藏干": cg, "十神": shen})
            result["十神统计"][shen] += 1

    return result

# ============================================================
# 八、五行统计
# ============================================================

def analyze_wu_xing(si_zhu):
    """五行力量分析"""
    wuxing_count = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}

    # 天干五行
    for col in ["年柱", "月柱", "日柱", "时柱"]:
        gan = si_zhu[col][0]
        wuxing_count[TIAN_GAN_WU_XING[gan]] += 1

    # 地支五行
    for col in ["年柱", "月柱", "日柱", "时柱"]:
        zhi = si_zhu[col[0] + "支"]
        wuxing_count[DI_ZHI_WU_XING[zhi]] += 1

    # 地支藏干五行(权重减半)
    for col in ["年柱", "月柱", "日柱", "时柱"]:
        zhi = si_zhu[col[0] + "支"]
        for cg in DI_ZHI_CANG_GAN.get(zhi, []):
            wuxing_count[TIAN_GAN_WU_XING[cg]] += 0.5

    return wuxing_count

# ============================================================
# 九、日干强弱判定
# ============================================================

def analyze_ri_gan_strength(si_zhu):
    """日干强弱分析（得令、得势、得地）"""
    ri_gan = si_zhu["日干"]
    ri_wx = TIAN_GAN_WU_XING[ri_gan]
    yue_zhi = si_zhu["月支"]
    yue_wx = DI_ZHI_WU_XING[yue_zhi]

    reasons = []

    # 得令：日干五行与月令五行关系
    # 月令五行旺相判断
    season_king = {"寅": "木", "卯": "木", "辰": "土",  # 春
                   "巳": "火", "午": "火", "未": "土",  # 夏
                   "申": "金", "酉": "金", "戌": "土",  # 秋
                   "亥": "水", "子": "水", "丑": "土"}  # 冬

    season_wang = season_king[yue_zhi]
    if ri_wx == season_wang:
        de_ling = "旺"
        reasons.append(f"日干{ri_wx}得月令，生于{season_wang}旺之月")
    elif is_sheng(season_wang, ri_wx):
        de_ling = "相"
        reasons.append(f"日干{ri_wx}得月令相气")
    else:
        de_ling = "休囚"
        reasons.append(f"日干{ri_wx}不得月令")

    # 得势：统计同类五行
    wuxing = analyze_wu_xing(si_zhu)
    same_type = wuxing[ri_wx]
    sheng_ri = 0
    for wx, cnt in wuxing.items():
        if is_sheng(wx, ri_wx):
            sheng_ri += cnt

    if same_type >= 3:
        de_shi = "强"
        reasons.append(f"同类五行{ri_wx}力量充足({same_type})")
    elif same_type >= 2 or sheng_ri >= 3:
        de_shi = "中"
    else:
        de_shi = "弱"
        reasons.append(f"同类五行{ri_wx}力量不足")

    # 得地：日干在地支中的根气
    ri_gan_root = 0
    for col in ["年柱", "月柱", "日柱", "时柱"]:
        zhi = si_zhu[col[0] + "支"]
        for cg in DI_ZHI_CANG_GAN.get(zhi, []):
            if cg == ri_gan:
                ri_gan_root += 1

    if ri_gan_root >= 2:
        de_di = "强"
        reasons.append("日干地支有强根")
    elif ri_gan_root == 1:
        de_di = "中"
    else:
        de_di = "弱"

    # 综合判断
    if de_ling in ("旺", "相") and de_shi == "强" and de_di in ("强", "中"):
        strength = "旺"
    elif de_ling in ("旺", "相") or de_shi == "强" or de_di == "强":
        strength = "强"
    elif de_ling == "休囚" and de_shi == "弱":
        strength = "弱"
    elif de_ling == "休囚" and de_shi == "中":
        strength = "中弱"
    else:
        strength = "中"

    return {
        "强度等级": strength,
        "得令": de_ling,
        "得势": de_shi,
        "得地": de_di,
        "分析理由": reasons
    }

# ============================================================
# 十、用神推荐
# ============================================================

def recommend_yong_shen(si_zhu, strength_info):
    """用神推荐（扶抑法 + 调候法）"""
    strength = strength_info["强度等级"]
    ri_gan = si_zhu["日干"]
    ri_wx = TIAN_GAN_WU_XING[ri_gan]
    yue_zhi = si_zhu["月支"]
    yue_wx = DI_ZHI_WU_XING[yue_zhi]

    yong_shen = []
    ji_shen = []

    # 扶抑法
    if strength in ("旺", "强"):
        # 身强，用克泄耗
        ke_ri = [wx for wx in ["木", "火", "土", "金", "水"] if is_ke(wx, ri_wx)]
        ri_sheng = [wx for wx in ["木", "火", "土", "金", "水"] if is_sheng(ri_wx, wx)]
        yong_shen.extend(ke_ri)  # 官杀克身
        yong_shen.extend(ri_sheng)  # 食伤泄身
        # 财星(我克)
        ri_ke = [wx for wx in ["木", "火", "土", "金", "水"] if is_ke(ri_wx, wx)]
        yong_shen.extend(ri_ke)
        ji_shen = [ri_wx]  # 忌比劫帮身
        for wx in ["木", "火", "土", "金", "水"]:
            if is_sheng(wx, ri_wx):
                ji_shen.append(wx)  # 忌印星生身

    elif strength in ("弱", "中弱"):
        # 身弱，用生扶
        sheng_ri = [wx for wx in ["木", "火", "土", "金", "水"] if is_sheng(wx, ri_wx)]
        yong_shen.extend(sheng_ri)  # 印星生身
        yong_shen.append(ri_wx)  # 比劫帮身
        ke_ri = [wx for wx in ["木", "火", "土", "金", "水"] if is_ke(wx, ri_wx)]
        ji_shen.extend(ke_ri)  # 忌官杀
    else:
        yong_shen = ["木", "火", "土", "金", "水"]
        ji_shen = []

    # 调候法
    if yue_zhi in ("亥", "子", "丑"):
        if "火" not in yong_shen:
            yong_shen.insert(0, "火")
    elif yue_zhi in ("巳", "午", "未"):
        if "水" not in yong_shen:
            yong_shen.insert(0, "水")

    # 去重
    yong_shen = list(dict.fromkeys(yong_shen))
    ji_shen = list(dict.fromkeys(ji_shen))[:3]

    return {"用神五行": yong_shen, "忌神五行": ji_shen, "方法": "扶抑法+调候法"}

# ============================================================
# 十一、格局判定
# ============================================================

def determine_ge_ju(si_zhu):
    """格局判定（正格+部分变格）"""
    yue_zhi = si_zhu["月支"]
    ri_gan = si_zhu["日干"]
    cang_gan = DI_ZHI_CANG_GAN.get(yue_zhi, [])
    all_gan = [si_zhu["年干"], si_zhu["月干"], si_zhu["日干"], si_zhu["时干"]]

    # 找出月支藏干在天干透出者
    tou_chu = []
    for cg in cang_gan:
        if cg in all_gan:
            shen = get_shi_shen(ri_gan, cg)
            tou_chu.append((cg, shen))

    # 格局名称映射
    ge_ju_map = {
        "正官": "正官格", "偏官": "偏官格（七杀格）",
        "正财": "正财格", "偏财": "偏财格",
        "正印": "正印格", "偏印": "偏印格",
        "食神": "食神格", "伤官": "伤官格",
        "比肩": "建禄格", "劫财": "月刃格"
    }

    ge_ju_list = []
    for cg, shen in tou_chu:
        ge_ju_name = ge_ju_map.get(shen, shen + "格")
        ge_ju_list.append({"藏干透出": cg, "十神": shen, "格局": ge_ju_name})

    # 如无透出，取本气为格
    if not ge_ju_list and cang_gan:
        main_cg = cang_gan[0]
        shen = get_shi_shen(ri_gan, main_cg)
        ge_ju_list.append({"藏干透出": main_cg, "十神": shen, "格局": ge_ju_map.get(shen, shen + "格")})

    # 检测特殊格局
    special = check_special_ge_ju(si_zhu)
    if special:
        ge_ju_list.insert(0, special)

    return ge_ju_list

def check_special_ge_ju(si_zhu):
    """检测特殊格局"""
    ri_gan = si_zhu["日干"]
    ri_zhi = si_zhu["日支"]
    ri_gz = si_zhu["日柱"]

    # 魁罡格
    if ri_gz in ["壬辰", "庚戌", "庚辰", "戊戌"]:
        return {"藏干透出": "-", "十神": "-", "格局": "魁罡格（特殊格局）"}

    # 日贵格
    if ri_gz in ["丁酉", "丁亥", "癸巳", "癸卯"]:
        return {"藏干透出": "-", "十神": "-", "格局": "日贵格（特殊格局）"}

    # 专旺格检测
    zhi_set = [si_zhu["年支"], si_zhu["月支"], si_zhu["日支"], si_zhu["时支"]]
    if ri_gan in ("甲", "乙") and set(zhi_set) & {"寅", "卯", "辰", "未"} == set(zhi_set):
        return {"藏干透出": "-", "十神": "-", "格局": "曲直格（木专旺格）"}
    if ri_gan in ("丙", "丁") and set(zhi_set) & {"巳", "午", "未", "戌"} == set(zhi_set):
        return {"藏干透出": "-", "十神": "-", "格局": "炎上格（火专旺格）"}
    if ri_gan in ("庚", "辛") and set(zhi_set) & {"申", "酉", "戌", "丑"} == set(zhi_set):
        return {"藏干透出": "-", "十神": "-", "格局": "从革格（金专旺格）"}
    if ri_gan in ("壬", "癸") and set(zhi_set) & {"亥", "子", "丑", "辰"} == set(zhi_set):
        return {"藏干透出": "-", "十神": "-", "格局": "润下格（水专旺格）"}

    return None

# ============================================================
# 十二、神煞标注
# ============================================================

def calculate_shen_sha(si_zhu):
    """计算神煞"""
    nian_zhi = si_zhu["年支"]
    ri_gan = si_zhu["日干"]
    ri_zhi = si_zhu["日支"]
    all_zhi = [si_zhu["年支"], si_zhu["月支"], si_zhu["日支"], si_zhu["时支"]]

    shen_sha = {"吉神": [], "凶煞": []}

    # 天乙贵人
    tian_yi_map = {
        "甲": ["丑", "未"], "戊": ["丑", "未"],
        "乙": ["子", "申"], "己": ["子", "申"],
        "丙": ["亥", "酉"], "丁": ["亥", "酉"],
        "庚": ["午", "寅"], "辛": ["午", "寅"],
        "壬": ["卯", "巳"], "癸": ["卯", "巳"]
    }
    gui_ren = tian_yi_map.get(ri_gan, [])
    for zhi in all_zhi:
        if zhi in gui_ren:
            shen_sha["吉神"].append(f"天乙贵人({zhi})")

    # 文昌星
    wen_chang_map = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
                     "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
    wc = wen_chang_map.get(ri_gan)
    if wc and wc in all_zhi:
        shen_sha["吉神"].append(f"文昌星({wc})")

    # 华盖
    hua_gai_map = {"寅": "戌", "午": "戌", "戌": "戌",
                   "巳": "丑", "酉": "丑", "丑": "丑",
                   "申": "辰", "子": "辰", "辰": "辰",
                   "亥": "未", "卯": "未", "未": "未"}
    for zhi in all_zhi:
        if hua_gai_map.get(zhi) == ri_zhi or hua_gai_map.get(ri_zhi) == zhi:
            shen_sha["吉神"].append(f"华盖({zhi})")
            break

    # 禄神
    lu_map = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
              "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
    lu = lu_map.get(ri_gan)
    if lu and lu in all_zhi:
        shen_sha["吉神"].append(f"禄神({lu})")

    # 羊刃
    yang_ren_map = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
                    "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥"}
    yr = yang_ren_map.get(ri_gan)
    if yr and yr in all_zhi:
        shen_sha["凶煞"].append(f"羊刃({yr})")

    # 桃花（咸池）
    tao_hua_map = {"寅": "卯", "午": "卯", "戌": "卯",
                   "巳": "午", "酉": "午", "丑": "午",
                   "申": "酉", "子": "酉", "辰": "酉",
                   "亥": "子", "卯": "子", "未": "子"}
    for zhi in all_zhi:
        if tao_hua_map.get(zhi) in all_zhi:
            tao = tao_hua_map[zhi]
            shen_sha["凶煞"].append(f"桃花/{tao}")
            break

    # 驿马
    yi_ma_map = {"寅": "申", "午": "申", "戌": "申",
                 "巳": "亥", "酉": "亥", "丑": "亥",
                 "申": "寅", "子": "寅", "辰": "寅",
                 "亥": "巳", "卯": "巳", "未": "巳"}
    ym = yi_ma_map.get(ri_zhi)
    if ym and ym in all_zhi:
        shen_sha["凶煞"].append(f"驿马({ym})")

    # 空亡
    kong_wang_list = [
        (["甲子", "乙丑", "丙寅", "丁卯", "戊辰", "己巳", "庚午", "辛未", "壬申", "癸酉"], ["戌", "亥"]),
        (["甲戌", "乙亥", "丙子", "丁丑", "戊寅", "己卯", "庚辰", "辛巳", "壬午", "癸未"], ["申", "酉"]),
        (["甲申", "乙酉", "丙戌", "丁亥", "戊子", "己丑", "庚寅", "辛卯", "壬辰", "癸巳"], ["午", "未"]),
        (["甲午", "乙未", "丙申", "丁酉", "戊戌", "己亥", "庚子", "辛丑", "壬寅", "癸卯"], ["辰", "巳"]),
        (["甲辰", "乙巳", "丙午", "丁未", "戊申", "己酉", "庚戌", "辛亥", "壬子", "癸丑"], ["寅", "卯"]),
        (["甲寅", "乙卯", "丙辰", "丁巳", "戊午", "己未", "庚申", "辛酉", "壬戌", "癸亥"], ["子", "丑"]),
    ]
    for xun, kong_zhi in kong_wang_list:
        if si_zhu["日柱"] in xun:
            for zhi in all_zhi:
                if zhi in kong_zhi:
                    shen_sha["凶煞"].append(f"空亡({zhi})")

    # 魁罡
    if si_zhu["日柱"] in ["壬辰", "庚戌", "庚辰", "戊戌"]:
        shen_sha["吉神"].append("魁罡")

    # 三奇贵人
    gan_set = {si_zhu["年干"], si_zhu["月干"], si_zhu["日干"]}
    if gan_set == {"甲", "戊", "庚"} or gan_set == {"乙", "丙", "丁"}:
        shen_sha["吉神"].append("三奇贵人")

    return shen_sha

# ============================================================
# 十三、六亲定位
# ============================================================

def analyze_liu_qin(si_zhu, gender):
    """六亲分析"""
    ri_gan = si_zhu["日干"]
    shi_shen_info = analyze_shi_shen(si_zhu)

    # 男命
    if gender == "男":
        return {
            "祖父": f"年干({si_zhu['年干']})",
            "祖母": f"年支({si_zhu['年支']})",
            "父亲": f"偏财看月干({si_zhu['月干']})",
            "母亲": f"正印看月支({si_zhu['月支']})",
            "兄弟": "比肩劫财",
            "妻子": f"正财看日支({si_zhu['日支']})",
            "子女": f"官杀为子，食伤为女，看时柱({si_zhu['时柱']})"
        }
    else:
        return {
            "祖父": f"年干({si_zhu['年干']})",
            "祖母": f"年支({si_zhu['年支']})",
            "父亲": f"正财看月干",
            "母亲": f"正印看月支({si_zhu['月支']})",
            "兄弟": "比肩劫财",
            "丈夫": f"正官看日支({si_zhu['日支']})",
            "子女": f"食伤为子，看时柱({si_zhu['时柱']})"
        }

# ============================================================
# 十四、疾病健康提示
# ============================================================

def analyze_health(si_zhu, wuxing_count):
    """健康分析"""
    tips = []
    organ_map = {"木": "肝胆/筋骨", "火": "心血管/眼目", "土": "脾胃/消化",
                 "金": "肺/呼吸系统/骨骼", "水": "肾脏/泌尿/耳朵"}

    for wx, cnt in wuxing_count.items():
        if cnt == 0:
            tips.append(f"五行缺{wx}，注意{organ_map[wx]}保养")
        elif cnt >= 4:
            tips.append(f"五行{wx}过旺，{organ_map[wx]}易出问题")

    # 刑冲检查
    zhi_all = [(si_zhu["年支"], "年"), (si_zhu["月支"], "月"),
               (si_zhu["日支"], "日"), (si_zhu["时支"], "时")]
    chong_pairs = [("子", "午"), ("丑", "未"), ("寅", "申"),
                   ("卯", "酉"), ("辰", "戌"), ("巳", "亥")]
    for i in range(4):
        for j in range(i + 1, 4):
            pair = (zhi_all[i][0], zhi_all[j][0])
            if pair in chong_pairs or (pair[1], pair[0]) in chong_pairs:
                tips.append(f"{zhi_all[i][1]}支{zhi_all[i][0]}冲{zhi_all[j][1]}支{zhi_all[j][0]}")

    return tips

# ============================================================
# 十五、综合解读
# ============================================================

def comprehensive_reading(si_zhu, gender):
    """综合解读"""
    result = {}

    # 基础信息
    result["八字"] = f"{si_zhu['年柱']} {si_zhu['月柱']} {si_zhu['日柱']} {si_zhu['时柱']}"
    result["生肖"] = si_zhu["生肖"]
    result["纳音"] = si_zhu["纳音"]
    result["时辰"] = si_zhu["时辰"]

    # 排大运
    da_yun = pai_da_yun(
        int(si_zhu.get("_year", 1990)), int(si_zhu.get("_month", 1)),
        int(si_zhu.get("_day", 1)), si_zhu["年干"], si_zhu["年支"],
        si_zhu["月柱"], gender
    )
    result["大运"] = da_yun

    # 十神
    shi_shen = analyze_shi_shen(si_zhu)
    result["十神"] = shi_shen

    # 五行
    wuxing = analyze_wu_xing(si_zhu)
    result["五行"] = wuxing

    # 日干强弱
    strength = analyze_ri_gan_strength(si_zhu)
    result["日干强弱"] = strength

    # 用神
    yong_shen = recommend_yong_shen(si_zhu, strength)
    result["用神"] = yong_shen

    # 格局
    ge_ju = determine_ge_ju(si_zhu)
    result["格局"] = ge_ju

    # 神煞
    shen_sha = calculate_shen_sha(si_zhu)
    result["神煞"] = shen_sha

    # 健康
    health = analyze_health(si_zhu, wuxing)
    result["健康提示"] = health

    return result

# ============================================================
# 十六、秤骨算命法
# ============================================================

# 年份骨重（六十甲子）
YEAR_BONE = {
    "甲子": "1.2", "乙丑": "0.9", "丙寅": "0.6", "丁卯": "0.7",
    "戊辰": "1.2", "己巳": "0.5", "庚午": "0.9", "辛未": "0.8",
    "壬申": "0.7", "癸酉": "0.8", "甲戌": "1.5", "乙亥": "0.9",
    "丙子": "1.6", "丁丑": "0.8", "戊寅": "0.8", "己卯": "1.9",
    "庚辰": "1.2", "辛巳": "0.6", "壬午": "0.8", "癸未": "0.7",
    "甲申": "0.5", "乙酉": "1.5", "丙戌": "0.6", "丁亥": "1.6",
    "戊子": "1.5", "己丑": "0.7", "庚寅": "0.9", "辛卯": "1.2",
    "壬辰": "1.0", "癸巳": "0.7", "甲午": "1.5", "乙未": "0.6",
    "丙申": "0.5", "丁酉": "1.4", "戊戌": "1.4", "己亥": "0.9",
    "庚子": "0.7", "辛丑": "0.7", "壬寅": "0.9", "癸卯": "1.2",
    "甲辰": "0.8", "乙巳": "0.7", "丙午": "1.3", "丁未": "0.5",
    "戊申": "1.4", "己酉": "0.5", "庚戌": "0.9", "辛亥": "1.7",
    "壬子": "0.5", "癸丑": "0.7", "甲寅": "1.2", "乙卯": "0.8",
    "丙辰": "0.8", "丁巳": "0.6", "戊午": "1.9", "己未": "0.6",
    "庚申": "0.8", "辛酉": "1.6", "壬戌": "1.0", "癸亥": "0.6"
}

MONTH_BONE = {
    1: "0.6", 2: "0.7", 3: "1.8", 4: "0.9", 5: "0.5", 6: "1.6",
    7: "0.9", 8: "1.5", 9: "1.8", 10: "0.8", 11: "0.9", 12: "0.5"
}

DAY_BONE = {
    1: "0.5", 2: "1.0", 3: "0.8", 4: "1.5", 5: "1.6",
    6: "1.5", 7: "0.8", 8: "1.6", 9: "0.8", 10: "1.6",
    11: "0.9", 12: "1.7", 13: "0.8", 14: "1.7", 15: "1.0",
    16: "0.8", 17: "0.9", 18: "1.8", 19: "0.5", 20: "1.5",
    21: "1.0", 22: "0.9", 23: "0.8", 24: "0.9", 25: "1.5",
    26: "1.8", 27: "0.7", 28: "0.8", 29: "1.6", 30: "0.6"
}

SHI_BONE = {
    "子": "1.6", "丑": "0.6", "寅": "0.7", "卯": "1.0",
    "辰": "0.9", "巳": "1.6", "午": "1.0", "未": "0.8",
    "申": "0.8", "酉": "0.9", "戌": "0.6", "亥": "0.6"
}

CHENG_GU_GE_JUE = {
    2.1: "短命非业谓大凶，平生灾难事重重，凶祸频临陷逆境，终世困苦事不成。",
    2.2: "身寒骨冷苦伶仃，此命推来行乞人，劳劳碌碌无度日，终年打拱过平生。",
    2.3: "此命推来骨格轻，求谋作事事难成，妻儿兄弟应难许，别处他乡作散人。",
    2.4: "此命推来福禄无，门庭困苦总难荣，六亲骨肉皆无靠，流浪他乡作老翁。",
    2.5: "此命推来祖业微，门庭营度似稀奇，六亲骨肉如冰炭，一世勤劳自把持。",
    2.6: "平生衣禄苦中求，独自营谋事不休，离祖出门宜早计，晚来衣禄自无休。",
    2.7: "一生作事少商量，难靠祖宗作主张，独马单枪空做去，早年晚岁总无长。",
    2.8: "一生行事似飘蓬，祖宗产业在梦中，若不过房改名姓，也当移徒二三通。",
    2.9: "初年运限未曾亨，纵有功名在后成，须过四旬才可立，移居改姓始为良。",
    3.0: "劳劳碌碌苦中求，东奔西走何日休，若使终身勤与俭，老来稍可免忧愁。",
    3.1: "忙忙碌碌苦中求，何日云开见日头，难得祖基家可立，中年衣食渐无忧。",
    3.2: "初年运蹇事难谋，渐有财源如水流，到得中年衣食旺，那时名利一齐收。",
    3.3: "早年做事事难成，百年勤劳枉费心，半世自如流水去，后来运到始得金。",
    3.4: "此命福气果如何，僧道门中衣禄多，离祖出家方为妙，朝晚拜佛念弥陀。",
    3.5: "生平福量不周全，祖业根基觉少传，营事生涯宜守旧，时来衣食胜从前。",
    3.6: "不须劳碌过平生，独自成家福不轻，早有福星常照命，任君行去百般成。",
    3.7: "此命般般事不成，弟兄少力自孤行，虽然祖业须微有，来得明时去不明。",
    3.8: "一身骨肉最清高，早入簧门姓氏标，待到年将三十六，蓝衫脱去换红袍。",
    3.9: "此命终身运不通，劳劳作事尽皆空，苦心竭力成家计，到得那时在梦中。",
    4.0: "平生衣禄是绵长，件件心中自主张，前面风霜多受过，后来必定享安康。",
    4.1: "此命推来自不同，为人能干异凡庸，中年还有逍遥福，不比前时运未通。",
    4.2: "得宽怀处且宽怀，何用双眉皱不开，若使中年命运济，那时名利一起来。",
    4.3: "为人心性最聪明，作事轩昂近贵人，衣禄一生天注定，不须劳碌是丰亨。",
    4.4: "万事由天莫苦求，须知福碌赖人修，当年财帛难如意，晚景欣然便不忧。",
    4.5: "名利推求竟若何，前番辛苦后奔波，命中难养男和女，骨肉扶持也不多。",
    4.6: "东西南北尽皆通，出姓移居更觉隆，衣禄无穷无数定，中年晚景一般同。",
    4.7: "此命推求旺末年，妻荣子贵自怡然，平生原有滔滔福，可卜财源若水泉。",
    4.8: "初年运道未曾通，几许蹉跎命亦穷，兄弟六亲无依靠，一生事业晚来整。",
    4.9: "此命推来福不轻，自成自立显门庭，从来富贵人钦敬，使婢差奴过一生。",
    5.0: "为利为名终日劳，中年福禄也多遭，老来自有财星照，不比前番目下高。",
    5.1: "一世荣华事事通，不须劳碌自亨通，兄弟叔侄皆如意，家业成时福禄宏。",
    5.2: "一世亨通事事能，不须劳苦自然宁，宗族有光欣喜甚，家产丰盈自称心。",
    5.3: "此格推来福泽宏，兴家立业在其中，一生衣食安排定，却是人间一福翁。",
    5.4: "此格详采福泽宏，诗书满腹看功成，丰衣足食多安稳，正是人间有福人。",
    5.5: "策马扬鞭争名利，少年作事费筹论，一朝福禄源源至，富贵荣华显六亲。",
    5.6: "此格推来礼义通，一身福禄用无穷，甜酸苦辣皆尝过，滚滚财源盈而丰。",
    5.7: "福禄丰盈万事全，一身荣耀乐天年，名扬威震人争羡，此世逍遥宛似仙。",
    5.8: "平生衣食自然来，名利双全富贵偕，金榜题名登甲第，紫袍玉带走金阶。",
    5.9: "细推此格秀而清，必定才高学业成，甲第之中应有分，扬鞭走马显威荣。",
    6.0: "一朝金榜快题名，显祖荣宗大器成，衣禄定然无欠缺，田园财帛更丰盈。",
    6.1: "不作朝中金榜客，定为世上大财翁，聪明天赋经书熟，名显高科自是荣。",
    6.2: "此命生来福不穷，读书必定显亲宗，紫衣玉带为卿相，富贵荣华孰与同。",
    6.3: "命主为官福禄长，得来富贵实非常，名题雁塔传金榜，大显门庭天下扬。",
    6.4: "此格威权不可当，紫袍金带尘高堂，荣华富贵谁能及，万古留名姓氏扬。",
    6.5: "细推此命福非轻，富贵荣华孰与争，定国安邦人极品，威声显赫震寰瀛。",
    6.6: "此格人间一福人，堆金积玉满堂春，从来富贵有天定，金榜题名更显亲。",
    6.7: "此命生来福自宏，田园家业最高隆，平生衣禄盈丰足，一路荣华万事通。",
    6.8: "富贵由天莫苦求，万金家计不须谋，如今不比前翻事，祖业根基千古留。",
    6.9: "君是人间衣禄星，一生富贵众人钦，总然福禄由天定，安享荣华过一生。",
    7.0: "此命推来福不轻，何须愁虑苦劳心，荣华富贵已天定，正笏垂绅拜紫宸。",
    7.1: "此命生成大不同，公侯卿相在其中，一生自有逍遥福，富贵荣华极品隆。"
}

def cheng_gu_suan_ming(si_zhu, month, day, hour):
    """秤骨算命"""
    nian_gz = si_zhu["年柱"]
    shi_zhi = si_zhu["时支"]
    lunar_month = month  # 此处简化，用公历月份近似

    nian_bone = float(YEAR_BONE.get(nian_gz, "0.0"))
    yue_bone = float(MONTH_BONE.get(lunar_month, "0.0"))
    ri_bone = float(DAY_BONE.get(day, "0.0"))
    shi_bone = float(SHI_BONE.get(shi_zhi, "0.0"))

    total = nian_bone + yue_bone + ri_bone + shi_bone

    # 找最近匹配的歌诀
    ge_jue = "（未找到对应歌诀）"
    closest = min(CHENG_GU_GE_JUE.keys(), key=lambda x: abs(x - total))
    if abs(closest - total) <= 0.1:
        ge_jue = CHENG_GU_GE_JUE[closest]

    level = "上等" if total >= 5 else ("中上" if total >= 4 else ("中等" if total >= 3 else "下等"))

    return {
        "年骨重": f"{nian_bone:.1f}两",
        "月骨重": f"{yue_bone:.1f}两",
        "日骨重": f"{ri_bone:.1f}两",
        "时骨重": f"{shi_bone:.1f}两",
        "总骨重": f"{total:.1f}两",
        "等级": level,
        "歌诀": ge_jue
    }

# ============================================================
# 十七、主入口函数
# ============================================================

def fortune_telling(year, month, day, hour, minute=0, gender="男"):
    """
    完整的算命入口
    year: 公历年 (1901-2000)
    month: 公历月 (1-12)
    day: 公历日 (1-31)
    hour: 小时 (0-23)
    gender: "男" 或 "女"
    """
    # 排四柱
    si_zhu = pai_si_zhu(year, month, day, hour, minute)
    si_zhu["_year"] = year
    si_zhu["_month"] = month
    si_zhu["_day"] = day

    # 综合解读
    reading = comprehensive_reading(si_zhu, gender)

    # 秤骨算命
    cheng_gu = cheng_gu_suan_ming(si_zhu, month, day, hour)

    # 六亲
    liu_qin = analyze_liu_qin(si_zhu, gender)

    return {
        "出生信息": f"{year}年{month}月{day}日 {hour}:{minute:02d}",
        "性别": gender,
        "四柱": si_zhu,
        "八字解读": reading,
        "六亲": liu_qin,
        "秤骨算命": cheng_gu
    }

# ============================================================
# 十八、格式化输出
# ============================================================

def format_report(result):
    """将算命结果格式化为可读报告"""
    r = result
    s = r["四柱"]
    bz = r["八字解读"]

    lines = []
    lines.append("# 八字命理分析报告")
    lines.append("")
    lines.append(f"## 基本信息")
    lines.append(f"- 出生时间: {r['出生信息']}")
    lines.append(f"- 性别: {r['性别']}")
    lines.append(f"- 八字: **{bz['八字']}**")
    lines.append(f"- 生肖: {bz['生肖']}")
    lines.append(f"- 纳音: {bz['纳音']}")
    lines.append(f"- 时辰: {bz['时辰']}")
    lines.append("")

    lines.append("## 四柱排盘")
    lines.append("| 四柱 | 年柱 | 月柱 | 日柱 | 时柱 |")
    lines.append("|------|------|------|------|------|")
    lines.append(f"| 干支 | {s['年柱']} | {s['月柱']} | {s['日柱']} | {s['时柱']} |")
    lines.append(f"| 藏干 | {'、'.join(DI_ZHI_CANG_GAN.get(s['年支'],[]))} | {'、'.join(DI_ZHI_CANG_GAN.get(s['月支'],[]))} | {'、'.join(DI_ZHI_CANG_GAN.get(s['日支'],[]))} | {'、'.join(DI_ZHI_CANG_GAN.get(s['时支'],[]))} |")
    lines.append("")

    # 五行
    wx = bz["五行"]
    lines.append("## 五行力量分析")
    lines.append("| 五行 | 木 | 火 | 土 | 金 | 水 |")
    lines.append("|------|-----|-----|-----|-----|-----|")
    lines.append(f"| 力量 | {wx['木']} | {wx['火']} | {wx['土']} | {wx['金']} | {wx['水']} |")
    lines.append("")

    # 日干强弱
    qr = bz["日干强弱"]
    lines.append("## 日干强弱分析")
    lines.append(f"- **日主**: {s['日干']}（{TIAN_GAN_WU_XING[s['日干']]}）")
    lines.append(f"- **强度等级**: {qr['强度等级']}")
    lines.append(f"- 得令: {qr['得令']}")
    lines.append(f"- 得势: {qr['得势']}")
    lines.append(f"- 得地: {qr['得地']}")
    if qr.get("分析理由"):
        for reason in qr["分析理由"]:
            lines.append(f"  - {reason}")
    lines.append("")

    # 用神
    ys = bz["用神"]
    lines.append("## 用神喜忌")
    lines.append(f"- **用神五行**: {'、'.join(ys['用神五行'])}")
    lines.append(f"- **忌神五行**: {'、'.join(ys['忌神五行'])}")
    lines.append(f"- **取法**: {ys['方法']}")
    lines.append("")

    # 十神
    lines.append("## 十神分布")
    lines.append("| 位置 | 天干 | 十神 |")
    lines.append("|------|------|------|")
    for col, info in bz["十神"]["天干十神"].items():
        lines.append(f"| {col} | {info['天干']} | {info['十神']} |")
    lines.append("")

    # 格局
    lines.append("## 格局判定")
    for gj in bz["格局"]:
        lines.append(f"- **{gj['格局']}**（{gj['藏干透出']}透出，{gj['十神']}）")
    lines.append("")

    # 大运
    dy = bz["大运"]
    lines.append("## 大运走势")
    lines.append(f"- 排法: {dy['顺逆']}")
    lines.append(f"- 起运年龄: **{dy['起运年龄']}岁**")
    lines.append("")
    lines.append("| 大运 | 干支 | 年龄段 |")
    lines.append("|------|------|--------|")
    for i, d in enumerate(dy["大运列表"][:5], 1):
        lines.append(f"| 第{i}步 | {d['干支']} | {d['十年区间']} |")
    lines.append("")

    # 神煞
    ss = bz["神煞"]
    lines.append("## 神煞标注")
    if ss["吉神"]:
        lines.append(f"- **吉神**: {'、'.join(ss['吉神'])}")
    if ss["凶煞"]:
        lines.append(f"- **凶煞**: {'、'.join(ss['凶煞'])}")
    lines.append("")

    # 健康
    if bz["健康提示"]:
        lines.append("## 健康提示")
        for tip in bz["健康提示"]:
            lines.append(f"- {tip}")
        lines.append("")

    # 秤骨
    cg = r["秤骨算命"]
    lines.append("## 秤骨算命")
    lines.append(f"- 年骨重: {cg['年骨重']}")
    lines.append(f"- 月骨重: {cg['月骨重']}")
    lines.append(f"- 日骨重: {cg['日骨重']}")
    lines.append(f"- 时骨重: {cg['时骨重']}")
    lines.append(f"- **总骨重: {cg['总骨重']}（{cg['等级']}）**")
    lines.append(f"- 歌诀: {cg['歌诀']}")
    lines.append("")

    # 六亲
    lines.append("## 六亲参考")
    for key, val in r["六亲"].items():
        lines.append(f"- **{key}**: {val}")
    lines.append("")

    # 综合概述
    lines.append("---")
    lines.append(f"*以上分析基于《中国古代算命术》(洪丕谟、姜玉珍著) 四柱八字+秤骨算命体系，仅供娱乐参考。*")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试：1990年5月15日 8:00 男
    result = fortune_telling(1990, 5, 15, 8, 0, "男")
    report = format_report(result)
    print(report)
