#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import re
import socket
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lunardate import LunarDate
from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
from qiskit.transpiler import generate_preset_pass_manager
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
RESULTS_DIR = APP_DIR / "results"
YAO_NAMES = {1: "初爻", 2: "二爻", 3: "三爻", 4: "四爻", 5: "五爻", 6: "上爻"}

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
GANZHI = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]
DAY_CALIBRATION_DATE = datetime(2026, 7, 7, tzinfo=ZoneInfo("Asia/Shanghai")).date()
DAY_CALIBRATION_INDEX = GANZHI.index("戊午")

SOLAR_TERM_NAMES = [
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
]
SOLAR_TERM_INFO_MINUTES = [
    0,
    21208,
    42467,
    63836,
    85337,
    107014,
    128867,
    150921,
    173149,
    195551,
    218072,
    240693,
    263343,
    285989,
    308563,
    331033,
    353350,
    375494,
    397447,
    419210,
    440795,
    462224,
    483532,
    504758,
]
JIE_MONTH_INDEX = {2: 0, 4: 1, 6: 2, 8: 3, 10: 4, 12: 5, 14: 6, 16: 7, 18: 8, 20: 9, 22: 10, 0: 11}
MONTH_START_STEM_BY_YEAR_STEM = {
    "甲": "丙",
    "己": "丙",
    "乙": "戊",
    "庚": "戊",
    "丙": "庚",
    "辛": "庚",
    "丁": "壬",
    "壬": "壬",
    "戊": "甲",
    "癸": "甲",
}
HOUR_START_STEM_BY_DAY_STEM = {
    "甲": "甲",
    "己": "甲",
    "乙": "丙",
    "庚": "丙",
    "丙": "戊",
    "辛": "戊",
    "丁": "庚",
    "壬": "庚",
    "戊": "壬",
    "癸": "壬",
}
XUNKONG = {
    0: "戌亥",
    10: "申酉",
    20: "午未",
    30: "辰巳",
    40: "寅卯",
    50: "子丑",
}
YIMA_BY_BRANCH_GROUP = {
    "申子辰": "寅",
    "寅午戌": "申",
    "巳酉丑": "亥",
    "亥卯未": "巳",
}
TAOHUA_BY_BRANCH_GROUP = {
    "申子辰": "酉",
    "寅午戌": "卯",
    "巳酉丑": "午",
    "亥卯未": "子",
}
RILU_BY_STEM = {
    "甲": "寅",
    "乙": "卯",
    "丙": "巳",
    "丁": "午",
    "戊": "巳",
    "己": "午",
    "庚": "申",
    "辛": "酉",
    "壬": "亥",
    "癸": "子",
}
GUIREN_BY_STEM = {
    "甲": "丑, 未",
    "戊": "丑, 未",
    "庚": "丑, 未",
    "乙": "子, 申",
    "己": "子, 申",
    "丙": "亥, 酉",
    "丁": "亥, 酉",
    "壬": "巳, 卯",
    "癸": "巳, 卯",
    "辛": "午, 寅",
}

TRIGRAM_BITS = {
    (1, 1, 1): "乾",
    (0, 1, 1): "巽",
    (0, 0, 1): "艮",
    (0, 0, 0): "坤",
    (1, 0, 0): "震",
    (0, 1, 0): "坎",
    (1, 0, 1): "离",
    (1, 1, 0): "兑",
}
TRIGRAM_LINES = {name: bits for bits, name in TRIGRAM_BITS.items()}
TRIGRAM_ELEMENTS = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
TRIGRAM_NAJIA = {
    "乾": {"inner": ["甲子", "甲寅", "甲辰"], "outer": ["壬午", "壬申", "壬戌"]},
    "兑": {"inner": ["丁巳", "丁卯", "丁丑"], "outer": ["丁亥", "丁酉", "丁未"]},
    "离": {"inner": ["己卯", "己丑", "己亥"], "outer": ["己酉", "己未", "己巳"]},
    "震": {"inner": ["庚子", "庚寅", "庚辰"], "outer": ["庚午", "庚申", "庚戌"]},
    "巽": {"inner": ["辛丑", "辛亥", "辛酉"], "outer": ["辛未", "辛巳", "辛卯"]},
    "坎": {"inner": ["戊寅", "戊辰", "戊午"], "outer": ["戊申", "戊戌", "戊子"]},
    "艮": {"inner": ["丙辰", "丙午", "丙申"], "outer": ["丙戌", "丙子", "丙寅"]},
    "坤": {"inner": ["乙未", "乙巳", "乙卯"], "outer": ["癸丑", "癸亥", "癸酉"]},
}
HEXAGRAM_NAMES = {
    ("乾", "乾"): "乾为天",
    ("乾", "兑"): "天泽履",
    ("乾", "离"): "天火同人",
    ("乾", "震"): "天雷无妄",
    ("乾", "巽"): "天风姤",
    ("乾", "坎"): "天水讼",
    ("乾", "艮"): "天山遁",
    ("乾", "坤"): "天地否",
    ("兑", "乾"): "泽天夬",
    ("兑", "兑"): "兑为泽",
    ("兑", "离"): "泽火革",
    ("兑", "震"): "泽雷随",
    ("兑", "巽"): "泽风大过",
    ("兑", "坎"): "泽水困",
    ("兑", "艮"): "泽山咸",
    ("兑", "坤"): "泽地萃",
    ("离", "乾"): "火天大有",
    ("离", "兑"): "火泽睽",
    ("离", "离"): "离为火",
    ("离", "震"): "火雷噬嗑",
    ("离", "巽"): "火风鼎",
    ("离", "坎"): "火水未济",
    ("离", "艮"): "火山旅",
    ("离", "坤"): "火地晋",
    ("震", "乾"): "雷天大壮",
    ("震", "兑"): "雷泽归妹",
    ("震", "离"): "雷火丰",
    ("震", "震"): "震为雷",
    ("震", "巽"): "雷风恒",
    ("震", "坎"): "雷水解",
    ("震", "艮"): "雷山小过",
    ("震", "坤"): "雷地豫",
    ("巽", "乾"): "风天小畜",
    ("巽", "兑"): "风泽中孚",
    ("巽", "离"): "风火家人",
    ("巽", "震"): "风雷益",
    ("巽", "巽"): "巽为风",
    ("巽", "坎"): "风水涣",
    ("巽", "艮"): "风山渐",
    ("巽", "坤"): "风地观",
    ("坎", "乾"): "水天需",
    ("坎", "兑"): "水泽节",
    ("坎", "离"): "水火既济",
    ("坎", "震"): "水雷屯",
    ("坎", "巽"): "水风井",
    ("坎", "坎"): "坎为水",
    ("坎", "艮"): "水山蹇",
    ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜",
    ("艮", "兑"): "山泽损",
    ("艮", "离"): "山火贲",
    ("艮", "震"): "山雷颐",
    ("艮", "巽"): "山风蛊",
    ("艮", "坎"): "山水蒙",
    ("艮", "艮"): "艮为山",
    ("艮", "坤"): "山地剥",
    ("坤", "乾"): "地天泰",
    ("坤", "兑"): "地泽临",
    ("坤", "离"): "地火明夷",
    ("坤", "震"): "地雷复",
    ("坤", "巽"): "地风升",
    ("坤", "坎"): "地水师",
    ("坤", "艮"): "地山谦",
    ("坤", "坤"): "坤为地",
}
BRANCH_ELEMENTS = {
    "子": "水",
    "亥": "水",
    "寅": "木",
    "卯": "木",
    "巳": "火",
    "午": "火",
    "申": "金",
    "酉": "金",
    "辰": "土",
    "戌": "土",
    "丑": "土",
    "未": "土",
}
STEM_ELEMENTS = {
    "甲": "木",
    "乙": "木",
    "丙": "火",
    "丁": "火",
    "戊": "土",
    "己": "土",
    "庚": "金",
    "辛": "金",
    "壬": "水",
    "癸": "水",
}
GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
SIX_SPIRITS = ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"]
SIX_SPIRIT_START_BY_DAY_STEM = {
    "甲": 0,
    "乙": 0,
    "丙": 1,
    "丁": 1,
    "戊": 2,
    "己": 3,
    "庚": 4,
    "辛": 4,
    "壬": 5,
    "癸": 5,
}

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
ACTIVE_STATUSES = {
    "CREATED",
    "CONNECTING",
    "SELECTING_BACKEND",
    "TRANSPILING",
    "SUBMITTING",
    "QUEUED",
    "INITIALIZING",
    "VALIDATING",
    "RUNNING",
    "READING_RESULT",
}

LIFE_KLINE_SYSTEM_INSTRUCTION = """
你是一位严谨的八字命理分析师，精通用四柱、大运、流年生成“人生K线”。请根据用户信息、后端换算出的四柱干支和大运参数，生成完整命理报告和 100 年 K 线数据。

硬性规则：
1. 只返回纯 JSON，不要 Markdown，不要解释文字。
2. 所有分析必须以“后端已换算四柱”和“后端已推算大运参数”为准，不要重新排四柱。
3. 分析分数字段使用 0-10 分；K线 open/close/high/low/score 使用 0-100 分。
4. chartPoints 必须正好 100 条，年龄采用虚岁，从 1 岁到 100 岁。
5. 每条 chartPoints 的 reason 控制在 20-30 个中文字符，简洁说明当年吉凶趋势。
6. 数据要有明显起伏，体现大运、流年和人生阶段差异，禁止输出平滑直线。
7. daYun 必须严格按照用户提供的大运起运年龄和大运序列填写；起运前填“童限”。

输出 JSON 结构：
{
  "bazi": ["年柱", "月柱", "日柱", "时柱"],
  "summary": "命理总评",
  "summaryScore": 8,
  "personality": "性格分析",
  "personalityScore": 8,
  "industry": "事业行业分析",
  "industryScore": 7,
  "fengShui": "发展方位、城市环境、居住布局建议",
  "fengShuiScore": 8,
  "wealth": "财富分析",
  "wealthScore": 8,
  "marriage": "婚姻情感分析",
  "marriageScore": 7,
  "health": "健康分析",
  "healthScore": 6,
  "family": "六亲关系分析",
  "familyScore": 7,
  "crypto": "币圈/高波动交易运势分析",
  "cryptoScore": 7,
  "cryptoYear": "适合重点把握的流年",
  "cryptoStyle": "现货定投/链上Alpha/高倍合约/不建议重仓",
  "chartPoints": [
    {"age":1,"year":1990,"daYun":"童限","ganZhi":"庚午","open":50,"close":55,"high":60,"low":45,"score":55,"reason":"开局平稳，家庭助力较足"},
    "...共100条"
  ]
}
""".strip()

LIFE_KLINE_CHART_CHUNK_INSTRUCTION = """
你是一位严谨的八字命理分析师。请只为用户指定的年龄范围生成“人生K线”chartPoints。

硬性规则：
1. 只返回纯 JSON，不要 Markdown，不要解释文字。
2. 只输出 chartPoints，不要输出命理报告。
3. chartPoints 条数必须等于用户指定年龄范围的年数。
4. K线 open/close/high/low/score 使用 0-100 分。
5. 每条 reason 控制在 20-30 个中文字符，简洁说明当年吉凶趋势。
6. daYun、year、ganZhi 必须严格按用户给定的年龄、流年和大运表填写。
7. 数据要有明显起伏，体现大运、流年和人生阶段差异，禁止输出平滑直线。

输出 JSON 结构：
{
  "chartPoints": [
    {"age":1,"year":1990,"daYun":"童限","ganZhi":"庚午","open":50,"close":55,"high":60,"low":45,"score":55,"reason":"开局平稳，家庭助力较足"}
  ]
}
""".strip()

LIFE_KLINE_ANALYSIS_INSTRUCTION = """
你是一位严谨的八字命理分析师。请根据用户的出生信息、后端换算出的四柱干支、大运信息和K线摘要，生成“人生K线”命理报告。

硬性规则：
1. 只返回纯 JSON，不要 Markdown，不要解释文字。
2. 不要输出 chartPoints。
3. 分析分数字段使用 0-10 分。
4. 所有分析必须以“后端已换算四柱”和“后端已推算大运参数”为准，不要重新排四柱。

输出 JSON 结构：
{
  "bazi": ["年柱", "月柱", "日柱", "时柱"],
  "summary": "命理总评",
  "summaryScore": 8,
  "personality": "性格分析",
  "personalityScore": 8,
  "industry": "事业行业分析",
  "industryScore": 7,
  "fengShui": "发展方位、城市环境、居住布局建议",
  "fengShuiScore": 8,
  "wealth": "财富分析",
  "wealthScore": 8,
  "marriage": "婚姻情感分析",
  "marriageScore": 7,
  "health": "健康分析",
  "healthScore": 6,
  "family": "六亲关系分析",
  "familyScore": 7,
  "crypto": "币圈/高波动交易运势分析",
  "cryptoScore": 7,
  "cryptoYear": "适合重点把握的流年",
  "cryptoStyle": "现货定投/链上Alpha/高倍合约/不建议重仓"
}
""".strip()


@dataclass
class YaoRecord:
    yao: int
    yao_name: str
    bits: str
    backs: int
    symbol: str
    yao_type: str
    moving: bool
    ben: str
    bian: str


def now_label() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def cast_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("CAST_TIMEZONE", "Asia/Shanghai"))


def solar_terms_for_year(year: int, tz: ZoneInfo) -> list[dict[str, Any]]:
    base = datetime(1900, 1, 6, 2, 5, tzinfo=timezone.utc)
    year_offset_ms = 31556925974.7 * (year - 1900)
    terms = []
    for idx, minutes in enumerate(SOLAR_TERM_INFO_MINUTES):
        instant = base + timedelta(milliseconds=year_offset_ms + minutes * 60000)
        terms.append({"index": idx, "name": SOLAR_TERM_NAMES[idx], "time": instant.astimezone(tz)})
    return terms


def nearest_solar_terms(moment: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    tz = cast_timezone()
    local = moment.astimezone(tz)
    terms = []
    for year in (local.year - 1, local.year, local.year + 1):
        terms.extend(solar_terms_for_year(year, tz))
    terms.sort(key=lambda item: item["time"])
    previous = terms[0]
    next_term = terms[-1]
    for idx, term in enumerate(terms):
        if term["time"] <= local:
            previous = term
            if idx + 1 < len(terms):
                next_term = terms[idx + 1]
    return previous, next_term


def solar_term_for_local_date(moment: datetime) -> dict[str, Any] | None:
    tz = cast_timezone()
    local = moment.astimezone(tz)
    for year in (local.year - 1, local.year, local.year + 1):
        for term in solar_terms_for_year(year, tz):
            if term["time"].date() == local.date():
                return term
    return None


def ganzhi_index(stem: str, branch: str) -> int:
    return GANZHI.index(stem + branch)


def year_ganzhi(moment: datetime) -> str:
    tz = cast_timezone()
    local = moment.astimezone(tz)
    lichun = solar_terms_for_year(local.year, tz)[2]["time"]
    ganzhi_year = local.year if local >= lichun else local.year - 1
    return GANZHI[(ganzhi_year - 1984) % 60]


def month_ganzhi(moment: datetime, year_pillar: str) -> str:
    tz = cast_timezone()
    local = moment.astimezone(tz)
    terms = []
    for year in (local.year - 1, local.year, local.year + 1):
        terms.extend(term for term in solar_terms_for_year(year, tz) if term["index"] in JIE_MONTH_INDEX)
    terms.sort(key=lambda item: item["time"])
    active_jie = max((term for term in terms if term["time"] <= local), key=lambda item: item["time"])
    month_idx = JIE_MONTH_INDEX[active_jie["index"]]
    branch = BRANCHES[(2 + month_idx) % 12]
    start_stem = MONTH_START_STEM_BY_YEAR_STEM[year_pillar[0]]
    stem = STEMS[(STEMS.index(start_stem) + month_idx) % 10]
    return stem + branch


def day_ganzhi(moment: datetime) -> str:
    local_date = moment.astimezone(cast_timezone()).date()
    delta_days = (local_date - DAY_CALIBRATION_DATE).days
    return GANZHI[(DAY_CALIBRATION_INDEX + delta_days) % 60]


def hour_ganzhi(moment: datetime, day_pillar: str) -> str:
    local = moment.astimezone(cast_timezone())
    hour = local.hour
    branch_idx = 0 if hour == 23 else (hour + 1) // 2
    branch = BRANCHES[branch_idx % 12]
    start_stem = HOUR_START_STEM_BY_DAY_STEM[day_pillar[0]]
    stem = STEMS[(STEMS.index(start_stem) + branch_idx) % 10]
    return stem + branch


def xunkong_for_day(day_pillar: str) -> str:
    idx = GANZHI.index(day_pillar)
    xun_start = idx - (idx % 10)
    return XUNKONG[xun_start]


def branch_group_value(branch: str, table: dict[str, str]) -> str:
    for group, value in table.items():
        if branch in group:
            return value
    raise ValueError(f"未找到地支分组: {branch}")


def shensha_for_day(day_pillar: str) -> dict[str, str]:
    stem, branch = day_pillar[0], day_pillar[1]
    return {
        "yima": branch_group_value(branch, YIMA_BY_BRANCH_GROUP),
        "taohua": branch_group_value(branch, TAOHUA_BY_BRANCH_GROUP),
        "rilu": RILU_BY_STEM[stem],
        "guiren": GUIREN_BY_STEM[stem],
    }


def ganzhi_context(moment: datetime | None = None) -> dict[str, Any]:
    local = (moment or datetime.now(cast_timezone())).astimezone(cast_timezone())
    previous_term, next_term = nearest_solar_terms(local)
    display_term = solar_term_for_local_date(local) or previous_term
    year_pillar = year_ganzhi(local)
    month_pillar = month_ganzhi(local, year_pillar)
    day_pillar = day_ganzhi(local)
    hour_pillar = hour_ganzhi(local, day_pillar)
    return {
        "timezone": str(cast_timezone()),
        "iso": local.isoformat(),
        "date_label": f"{display_term['name']}：{local.year:04d}年{local.month:02d}月{local.day:02d}日{local.hour:02d}时{local.minute:02d}分",
        "date_parts": {
            "year": local.year,
            "month": local.month,
            "day": local.day,
            "hour": local.hour,
            "minute": local.minute,
        },
        "solar_term": display_term["name"],
        "active_solar_term": previous_term["name"],
        "next_solar_term": {
            "name": next_term["name"],
            "time": next_term["time"].isoformat(),
        },
        "pillars": {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "hour": hour_pillar,
        },
        "xunkong": xunkong_for_day(day_pillar),
        "shensha": shensha_for_day(day_pillar),
    }


def julian_day_number(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def life_day_ganzhi(moment: datetime) -> str:
    local = moment.astimezone(cast_timezone())
    jdn = julian_day_number(local.year, local.month, local.day)
    return GANZHI[(jdn + 49) % 60]


def life_bazi_context(moment: datetime) -> dict[str, Any]:
    local = moment.astimezone(cast_timezone())
    year_pillar = year_ganzhi(local)
    month_pillar = month_ganzhi(local, year_pillar)
    day_pillar = life_day_ganzhi(local)
    hour_pillar = hour_ganzhi(local, day_pillar)
    return {
        "timezone": str(cast_timezone()),
        "iso": local.isoformat(),
        "pillars": {
            "year": year_pillar,
            "month": month_pillar,
            "day": day_pillar,
            "hour": hour_pillar,
        },
    }


def normalized_gender(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"male", "m", "男", "乾造", "乾"}:
        return "male"
    if text in {"female", "f", "女", "坤造", "坤"}:
        return "female"
    raise ValueError("请选择性别。")


def gender_label(value: str) -> str:
    return "男（乾造）" if value == "male" else "女（坤造）"


def ganzhi_step(pillar: str, step: int) -> str:
    return GANZHI[(GANZHI.index(pillar) + step) % 60]


def dayun_direction(gender: str, year_pillar: str) -> tuple[bool, str]:
    yang_stems = {"甲", "丙", "戊", "庚", "壬"}
    is_yang_year = year_pillar[0] in yang_stems
    is_forward = is_yang_year if gender == "male" else not is_yang_year
    return is_forward, "顺行" if is_forward else "逆行"


def jie_terms_around(moment: datetime) -> list[dict[str, Any]]:
    tz = cast_timezone()
    local = moment.astimezone(tz)
    terms: list[dict[str, Any]] = []
    for year in (local.year - 1, local.year, local.year + 1):
        terms.extend(term for term in solar_terms_for_year(year, tz) if term["index"] in JIE_MONTH_INDEX)
    return sorted(terms, key=lambda item: item["time"])


def life_dayun_info(moment: datetime, gender: str, year_pillar: str, month_pillar: str) -> dict[str, Any]:
    local = moment.astimezone(cast_timezone())
    is_forward, direction = dayun_direction(gender, year_pillar)
    terms = jie_terms_around(local)
    previous_jie = max((term for term in terms if term["time"] <= local), key=lambda item: item["time"])
    next_jie = min((term for term in terms if term["time"] > local), key=lambda item: item["time"])
    target_jie = next_jie if is_forward else previous_jie
    delta_days = abs((target_jie["time"] - local).total_seconds()) / 86400
    actual_years = delta_days / 3
    start_age = max(1, round(actual_years) + 1)
    first_dayun = ganzhi_step(month_pillar, 1 if is_forward else -1)
    sequence = [ganzhi_step(first_dayun, idx if is_forward else -idx) for idx in range(10)]
    return {
        "direction": direction,
        "startAge": start_age,
        "firstDaYun": first_dayun,
        "sequence": sequence,
        "referenceJie": {
            "name": target_jie["name"],
            "time": target_jie["time"].isoformat(),
            "deltaDays": round(delta_days, 2),
        },
    }


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "闰", "闰月"}


def parse_birth_time(value: Any) -> datetime:
    if value in (None, ""):
        raise ValueError("请填写出生日期时间。")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"出生日期时间格式不正确: {text}") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=cast_timezone())
    return parsed.astimezone(cast_timezone())


def normalize_life_calendar_type(value: Any) -> str:
    text = str(value or "solar").strip().lower()
    if text in {"solar", "gregorian", "yangli", "阳历", "公历"}:
        return "solar"
    if text in {"lunar", "yinli", "农历", "阴历"}:
        return "lunar"
    raise ValueError("历法只能选择阳历/公历或农历/阴历。")


def resolve_life_birth_time(body: dict[str, Any]) -> tuple[datetime, dict[str, Any]]:
    calendar_type = normalize_life_calendar_type(body.get("calendar_type"))
    parsed = parse_birth_time(body.get("birth_time"))
    local = parsed.astimezone(cast_timezone())
    birth_input: dict[str, Any] = {
        "inputCalendarType": calendar_type,
        "inputBirthTime": local.isoformat(),
    }
    if calendar_type == "solar":
        return local, birth_input

    is_leap_month = truthy(body.get("lunar_is_leap"))
    try:
        solar_date = LunarDate(local.year, local.month, local.day, isLeapMonth=is_leap_month).toSolarDate()
    except ValueError as exc:
        leap_label = "闰" if is_leap_month else ""
        raise ValueError(f"农历日期不正确：{local.year}年{leap_label}{local.month}月{local.day}日。") from exc

    converted = datetime(
        solar_date.year,
        solar_date.month,
        solar_date.day,
        local.hour,
        local.minute,
        local.second,
        local.microsecond,
        tzinfo=cast_timezone(),
    )
    birth_input["lunar"] = {
        "year": local.year,
        "month": local.month,
        "day": local.day,
        "isLeapMonth": is_leap_month,
    }
    birth_input["solarBirthTime"] = converted.isoformat()
    return converted, birth_input


def extract_json_object(text: str) -> dict[str, Any]:
    content = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if match:
        content = match.group(1).strip()
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return json.loads(content, strict=False)


def life_api_config() -> dict[str, Any]:
    api_key = (
        os.getenv("LIFE_KLINE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError("后端未配置 LIFE_KLINE_API_KEY 或 GEMINI_API_KEY。")
    base_url = (os.getenv("LIFE_KLINE_API_BASE") or "https://bboluo.com/v1").strip().rstrip("/")
    model = (os.getenv("LIFE_KLINE_MODEL") or "[L]gemini-3-flash-preview").strip()
    max_tokens = int(os.getenv("LIFE_KLINE_MAX_TOKENS", "30000"))
    timeout = int(os.getenv("LIFE_KLINE_TIMEOUT", "120"))
    return {"api_key": api_key, "base_url": base_url, "model": model, "max_tokens": max_tokens, "timeout": timeout}


def call_life_model(
    messages: list[dict[str, str]],
    *,
    max_tokens: int | None = None,
    timeout: int | None = None,
    temperature: float = 0.7,
) -> dict[str, Any]:
    config = life_api_config()
    request_body = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or config["max_tokens"],
    }
    request = Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout or config["timeout"]) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"人生K线 API 请求失败: {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"人生K线 API 无法连接: {exc.reason}") from exc

    content = payload.get("choices", [{}])[0].get("message", {}).get("content")
    if not content:
        raise RuntimeError("人生K线模型未返回内容。")
    return extract_json_object(content)


def normalize_score(value: Any, default: int = 5) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number.is_integer():
        return int(number)
    return round(number, 1)


def normalize_life_analysis(data: dict[str, Any], bazi: list[str]) -> dict[str, Any]:
    return {
        "bazi": data.get("bazi") if isinstance(data.get("bazi"), list) else bazi,
        "summary": data.get("summary") or "暂无总评",
        "summaryScore": normalize_score(data.get("summaryScore")),
        "personality": data.get("personality") or "暂无性格分析",
        "personalityScore": normalize_score(data.get("personalityScore")),
        "industry": data.get("industry") or "暂无事业分析",
        "industryScore": normalize_score(data.get("industryScore")),
        "fengShui": data.get("fengShui") or "暂无风水建议",
        "fengShuiScore": normalize_score(data.get("fengShuiScore")),
        "wealth": data.get("wealth") or "暂无财富分析",
        "wealthScore": normalize_score(data.get("wealthScore")),
        "marriage": data.get("marriage") or "暂无婚姻分析",
        "marriageScore": normalize_score(data.get("marriageScore")),
        "health": data.get("health") or "暂无健康分析",
        "healthScore": normalize_score(data.get("healthScore")),
        "family": data.get("family") or "暂无六亲分析",
        "familyScore": normalize_score(data.get("familyScore")),
        "crypto": data.get("crypto") or "暂无交易分析",
        "cryptoScore": normalize_score(data.get("cryptoScore")),
        "cryptoYear": data.get("cryptoYear") or "待定",
        "cryptoStyle": data.get("cryptoStyle") or "稳健低杠杆",
    }


def clamp_life_value(value: float, lower: float = 0, upper: float = 100) -> int:
    return int(round(max(lower, min(upper, value))))


def life_element_score(day_element: str, target_element: str) -> int:
    if target_element == day_element:
        return 4
    if GENERATES[target_element] == day_element:
        return 8
    if GENERATES[day_element] == target_element:
        return 3
    if CONTROLS[day_element] == target_element:
        return 6
    if CONTROLS[target_element] == day_element:
        return -7
    return 0


def pillar_element_score(day_element: str, pillar: str, stem_weight: float = 1.0, branch_weight: float = 1.2) -> float:
    stem_element = STEM_ELEMENTS.get(pillar[0], day_element)
    branch_element = BRANCH_ELEMENTS.get(pillar[1], day_element)
    return (life_element_score(day_element, stem_element) * stem_weight) + (
        life_element_score(day_element, branch_element) * branch_weight
    )


def dayun_for_age(age: int, dayun: dict[str, Any]) -> str:
    start_age = int(dayun["startAge"])
    if age < start_age:
        return "童限"
    da_yun_idx = min((age - start_age) // 10, len(dayun["sequence"]) - 1)
    return str(dayun["sequence"][da_yun_idx])


def life_reason(score: int, delta: int, age: int, gan_zhi: str, da_yun: str) -> str:
    if score >= 82:
        return f"{da_yun}承接{gan_zhi}，机会集中宜主动扩张。"
    if score >= 68:
        return f"{da_yun}助势{gan_zhi}，稳步推进多有进益。"
    if score >= 52:
        return f"{gan_zhi}气势平衡，守正蓄力可稳中有升。"
    if delta < -8:
        return f"{gan_zhi}波动偏大，宜收敛风险保现金流。"
    if age < 18:
        return f"{gan_zhi}童限养基，重在学习与身心根基。"
    return f"{gan_zhi}压力较显，宜慢决策少做重仓。"


def generate_backend_life_chart(
    birth_year: int,
    bazi: list[str],
    dayun: dict[str, Any],
) -> list[dict[str, Any]]:
    day_element = STEM_ELEMENTS.get(bazi[2][0], BRANCH_ELEMENTS.get(bazi[2][1], "土"))
    natal_base = 50
    natal_base += pillar_element_score(day_element, bazi[0], 0.5, 0.6)
    natal_base += pillar_element_score(day_element, bazi[1], 0.8, 1.1)
    natal_base += pillar_element_score(day_element, bazi[3], 0.4, 0.5)
    previous_close = clamp_life_value(natal_base)
    points: list[dict[str, Any]] = []
    for age in range(1, 101):
        year = birth_year + age - 1
        gan_zhi = GANZHI[(year - 1984) % 60]
        da_yun = dayun_for_age(age, dayun)
        flow_score = pillar_element_score(day_element, gan_zhi, 0.9, 1.0)
        luck_score = 0 if da_yun == "童限" else pillar_element_score(day_element, da_yun, 1.1, 1.3)
        age_curve = -7 if age <= 15 else 4 if age <= 35 else 9 if age <= 55 else 2 if age <= 75 else -5
        wave = math.sin((age + GANZHI.index(bazi[2])) / 4.8) * 6
        close = clamp_life_value(natal_base + (luck_score * 1.25) + flow_score + age_curve + wave)
        open_value = previous_close
        volatility = min(18, 5 + abs(close - open_value) * 0.35 + abs(flow_score) * 0.25)
        high = clamp_life_value(max(open_value, close) + volatility)
        low = clamp_life_value(min(open_value, close) - (volatility * 0.8))
        points.append(
            {
                "age": age,
                "year": year,
                "ganZhi": gan_zhi,
                "daYun": da_yun,
                "open": open_value,
                "close": close,
                "high": max(high, open_value, close, low),
                "low": min(low, open_value, close, high),
                "score": close,
                "reason": life_reason(close, close - open_value, age, gan_zhi, da_yun),
            }
        )
        previous_close = close
    return points


def fallback_life_analysis(bazi: list[str], chart_data: list[dict[str, Any]]) -> dict[str, Any]:
    average = round(sum(float(point["score"]) for point in chart_data) / len(chart_data), 1)
    peak = max(chart_data, key=lambda point: float(point["score"]))
    low = min(chart_data, key=lambda point: float(point["score"]))
    score_10 = max(1, min(10, round(average / 10, 1)))
    return {
        "bazi": bazi,
        "summary": f"后端已完成四柱和大运排盘。基础K线均值约{average}，峰值在{peak['year']}年，低谷在{low['year']}年。",
        "summaryScore": score_10,
        "personality": "命局节奏以日主为核心，宜把稳定积累和阶段性突破结合。",
        "personalityScore": score_10,
        "industry": "适合选择能持续沉淀技能、资源和信用的方向，逢高分流年加速扩张。",
        "industryScore": score_10,
        "fengShui": "居住与办公宜保持采光、通风和动线清晰，重要年份少频繁搬动。",
        "fengShuiScore": score_10,
        "wealth": "财富曲线宜顺势分批推进，高分阶段可进取，低分阶段重现金流。",
        "wealthScore": score_10,
        "marriage": "关系经营宜避开事业压力峰值时的冲动决策，多以沟通稳定节奏。",
        "marriageScore": score_10,
        "health": "低分流年注意睡眠、脾胃、压力管理和长期运动习惯。",
        "healthScore": score_10,
        "family": "六亲互动宜以边界清晰为主，运势上行期更适合主动修复关系。",
        "familyScore": score_10,
        "crypto": "高波动交易只宜在K线高分阶段小仓试错，低分阶段避免杠杆。",
        "cryptoScore": score_10,
        "cryptoYear": f"{peak['year']}年（{peak['ganZhi']}）",
        "cryptoStyle": "现货定投/低杠杆波段",
    }


def normalize_chart_points(points: Any, birth_year: int, dayun: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(points, list) or len(points) != 100:
        raise RuntimeError("人生K线模型返回的数据不完整：chartPoints 必须正好 100 条。")
    normalized = []
    for idx, point in enumerate(points, start=1):
        if not isinstance(point, dict):
            raise RuntimeError(f"第 {idx} 条 chartPoints 不是对象。")
        age = idx
        year = birth_year + age - 1
        start_age = int(dayun["startAge"])
        if age < start_age:
            da_yun = "童限"
        else:
            da_yun_idx = min((age - start_age) // 10, len(dayun["sequence"]) - 1)
            da_yun = dayun["sequence"][da_yun_idx]
        close = clamp_life_value(float(normalize_score(point.get("close") if point.get("close") is not None else point.get("score"), 50)))
        open_value = clamp_life_value(float(normalize_score(point.get("open"), close)))
        high = clamp_life_value(float(normalize_score(point.get("high"), max(open_value, close))))
        low = clamp_life_value(float(normalize_score(point.get("low"), min(open_value, close))))
        score = clamp_life_value(float(normalize_score(point.get("score"), close)))
        normalized.append(
            {
                "age": age,
                "year": year,
                "ganZhi": GANZHI[(year - 1984) % 60],
                "daYun": str(da_yun),
                "open": open_value,
                "close": close,
                "high": max(high, open_value, close, low),
                "low": min(low, open_value, close, high),
                "score": score,
                "reason": str(point.get("reason") or "流年趋势平稳，宜稳中求进。"),
            }
        )
    return normalized


def normalize_chart_points_range(
    points: Any,
    birth_year: int,
    dayun: dict[str, Any],
    start_age: int,
    end_age: int,
) -> list[dict[str, Any]]:
    expected_len = end_age - start_age + 1
    if not isinstance(points, list) or len(points) != expected_len:
        raise RuntimeError(f"人生K线模型返回的数据不完整：{start_age}-{end_age} 岁必须正好 {expected_len} 条。")
    normalized = []
    for offset, point in enumerate(points):
        if not isinstance(point, dict):
            raise RuntimeError(f"第 {start_age + offset} 岁 chartPoints 不是对象。")
        age = start_age + offset
        year = birth_year + age - 1
        da_yun = dayun_for_age(age, dayun)
        close = clamp_life_value(float(normalize_score(point.get("close") if point.get("close") is not None else point.get("score"), 50)))
        open_value = clamp_life_value(float(normalize_score(point.get("open"), close)))
        high = clamp_life_value(float(normalize_score(point.get("high"), max(open_value, close))))
        low = clamp_life_value(float(normalize_score(point.get("low"), min(open_value, close))))
        score = clamp_life_value(float(normalize_score(point.get("score"), close)))
        normalized.append(
            {
                "age": age,
                "year": year,
                "ganZhi": GANZHI[(year - 1984) % 60],
                "daYun": da_yun,
                "open": open_value,
                "close": close,
                "high": max(high, open_value, close, low),
                "low": min(low, open_value, close, high),
                "score": score,
                "reason": str(point.get("reason") or "流年趋势平稳，宜稳中求进。"),
            }
        )
    return normalized


def life_chart_rows_prompt(birth_year: int, dayun: dict[str, Any], start_age: int, end_age: int) -> str:
    rows = []
    for age in range(start_age, end_age + 1):
        year = birth_year + age - 1
        rows.append(f"{age}岁：{year}年，{GANZHI[(year - 1984) % 60]}，大运：{dayun_for_age(age, dayun)}")
    return "\n".join(rows)


def generate_model_chart_chunks(context_prompt: str, birth_year: int, dayun: dict[str, Any]) -> list[dict[str, Any]]:
    chunk_ranges = [(1, 25), (26, 50), (51, 75), (76, 100)]
    chunk_tokens = int(os.getenv("LIFE_KLINE_CHUNK_MAX_TOKENS", "9000"))
    chunk_timeout = int(os.getenv("LIFE_KLINE_CHUNK_TIMEOUT", "75"))
    chunk_workers = max(1, min(4, int(os.getenv("LIFE_KLINE_CHUNK_WORKERS", "4"))))

    def fetch_chunk(start_age: int, end_age: int) -> tuple[int, list[dict[str, Any]]]:
        chunk_prompt = f"""
{context_prompt}

【本批次只生成以下年龄范围】
{life_chart_rows_prompt(birth_year, dayun, start_age, end_age)}

请只输出上述 {start_age}-{end_age} 岁的 chartPoints JSON。
不要输出其他年龄，不要输出报告字段。
""".strip()
        data = call_life_model(
            [
                {"role": "system", "content": LIFE_KLINE_CHART_CHUNK_INSTRUCTION},
                {"role": "user", "content": chunk_prompt},
            ],
            max_tokens=chunk_tokens,
            timeout=chunk_timeout,
            temperature=0.65,
        )
        return start_age, normalize_chart_points_range(data.get("chartPoints"), birth_year, dayun, start_age, end_age)

    chunks: dict[int, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=chunk_workers) as executor:
        futures = [executor.submit(fetch_chunk, start_age, end_age) for start_age, end_age in chunk_ranges]
        for future in as_completed(futures):
            start_age, points = future.result()
            chunks[start_age] = points

    chart_data: list[dict[str, Any]] = []
    for start_age, _ in chunk_ranges:
        chart_data.extend(chunks[start_age])
    return normalize_chart_points(chart_data, birth_year, dayun)


def generate_model_analysis(context_prompt: str, bazi: list[str], chart_data: list[dict[str, Any]]) -> dict[str, Any]:
    average = round(sum(float(point["score"]) for point in chart_data) / len(chart_data), 1)
    peak = max(chart_data, key=lambda point: float(point["score"]))
    trough = min(chart_data, key=lambda point: float(point["score"]))
    analysis_tokens = int(os.getenv("LIFE_KLINE_ANALYSIS_MAX_TOKENS", "6000"))
    analysis_timeout = int(os.getenv("LIFE_KLINE_ANALYSIS_TIMEOUT", "60"))
    analysis_prompt = f"""
{context_prompt}

【模型已生成K线摘要】
K线均值：{average}
峰值流年：{peak["year"]}年 {peak["ganZhi"]}，{peak["age"]}岁，分数 {peak["score"]}
低谷流年：{trough["year"]}年 {trough["ganZhi"]}，{trough["age"]}岁，分数 {trough["score"]}

请只输出命理报告 JSON，不要输出 chartPoints。
""".strip()
    data = call_life_model(
        [
            {"role": "system", "content": LIFE_KLINE_ANALYSIS_INSTRUCTION},
            {"role": "user", "content": analysis_prompt},
        ],
        max_tokens=analysis_tokens,
        timeout=analysis_timeout,
        temperature=0.7,
    )
    return normalize_life_analysis(data, bazi)


def generate_life_kline(body: dict[str, Any]) -> dict[str, Any]:
    birth_time, birth_input = resolve_life_birth_time(body)
    gender = normalized_gender(body.get("gender"))
    name = str(body.get("name") or "").strip()
    bazi_context = life_bazi_context(birth_time)
    pillars = bazi_context["pillars"]
    bazi = [pillars["year"], pillars["month"], pillars["day"], pillars["hour"]]
    dayun = life_dayun_info(birth_time, gender, pillars["year"], pillars["month"])
    local = birth_time.astimezone(cast_timezone())
    backend_chart_data = generate_backend_life_chart(local.year, bazi, dayun)
    chart_data = backend_chart_data
    if birth_input["inputCalendarType"] == "lunar":
        lunar = birth_input["lunar"]
        input_calendar_line = (
            f"输入历法：农历，原始生日：{lunar['year']}年"
            f"{'闰' if lunar['isLeapMonth'] else ''}{lunar['month']}月{lunar['day']}日 "
            f"{local.hour:02d}:{local.minute:02d}；后端已换算为阳历 {local.strftime('%Y-%m-%d %H:%M')}"
        )
    else:
        input_calendar_line = f"输入历法：阳历/公历，阳历生日：{local.strftime('%Y-%m-%d %H:%M')}"

    context_prompt = f"""
【基本信息】
姓名：{name or "未提供"}
性别：{gender_label(gender)}
{input_calendar_line}
阳历出生时间：{local.strftime("%Y-%m-%d %H:%M")}（{bazi_context["timezone"]}）

【后端已换算四柱】
年柱：{pillars["year"]}
月柱：{pillars["month"]}
日柱：{pillars["day"]}
时柱：{pillars["hour"]}

【后端已推算大运参数】
大运方向：{dayun["direction"]}
起运年龄（虚岁）：{dayun["startAge"]}
第一步大运：{dayun["firstDaYun"]}
大运序列：{"、".join(dayun["sequence"])}
参考节气：{dayun["referenceJie"]["name"]}，相差约 {dayun["referenceJie"]["deltaDays"]} 天

请严格使用上面的四柱、大运方向、起运年龄、第一步大运和大运序列。
chartPoints 的 year 从 {local.year} 年开始，每增长 1 岁 year 增加 1；ganZhi 必须对应该流年干支。
""".strip()
    try:
        chart_data = generate_model_chart_chunks(context_prompt, local.year, dayun)
        model_info = {"used": True, "error": None, "chartSource": "model", "method": "chunked"}
    except Exception as exc:
        chart_data = backend_chart_data
        model_info = {"used": False, "error": str(exc)[:500], "chartSource": "backend_fallback"}
    if model_info["chartSource"] == "model":
        try:
            analysis = generate_model_analysis(context_prompt, bazi, chart_data)
            model_info["analysisSource"] = "model"
        except Exception as exc:
            analysis = fallback_life_analysis(bazi, chart_data)
            model_info["analysisSource"] = "backend_fallback"
            model_info["analysisError"] = str(exc)[:500]
    else:
        analysis = fallback_life_analysis(bazi, chart_data)
        model_info["analysisSource"] = "backend_fallback"
    return {
        "birthInfo": {
            "name": name,
            "gender": gender,
            "genderLabel": gender_label(gender),
            "calendarType": birth_input["inputCalendarType"],
            "inputBirthTime": birth_input["inputBirthTime"],
            "birthTime": local.isoformat(),
            "solarBirthTime": local.isoformat(),
            "lunar": birth_input.get("lunar"),
            "bazi": bazi,
            "dayun": dayun,
        },
        "analysis": analysis,
        "chartData": chart_data,
        "model": model_info,
    }


def line_bits_from_records(records: list[YaoRecord], attr: str) -> list[int]:
    return [1 if getattr(record, attr) == "阳" else 0 for record in records]


def trigrams_from_lines(lines: list[int]) -> tuple[str, str]:
    lower = TRIGRAM_BITS[tuple(lines[:3])]
    upper = TRIGRAM_BITS[tuple(lines[3:])]
    return lower, upper


def determine_palace(lines: list[int]) -> tuple[str, int, int]:
    cur = list(lines)
    if cur[:3] == cur[3:]:
        return TRIGRAM_BITS[tuple(cur[:3])], 5, 2

    for idx in range(5):
        cur[idx] ^= 1
        if cur[:3] == cur[3:]:
            shi = idx
            ying = (shi + 3) % 6
            return TRIGRAM_BITS[tuple(cur[:3])], shi, ying

    for idx in range(3, -1, -1):
        cur[idx] ^= 1
        if cur[:3] == cur[3:]:
            shi = 2 if idx == 0 else idx
            ying = (shi + 3) % 6
            return TRIGRAM_BITS[tuple(cur[:3])], shi, ying

    raise ValueError(f"无法安世应: {lines}")


def ganzi_element(ganzi: str) -> str:
    return BRANCH_ELEMENTS[ganzi[1]]


def six_relation(palace_element: str, branch_element: str) -> str:
    if palace_element == branch_element:
        return "兄弟"
    if GENERATES[branch_element] == palace_element:
        return "父母"
    if CONTROLS[branch_element] == palace_element:
        return "官鬼"
    if GENERATES[palace_element] == branch_element:
        return "子孙"
    if CONTROLS[palace_element] == branch_element:
        return "妻财"
    raise ValueError(f"无法计算六亲: {palace_element}, {branch_element}")


def najia_for_line(lines: list[int], line_idx: int) -> str:
    lower, upper = trigrams_from_lines(lines)
    if line_idx < 3:
        return TRIGRAM_NAJIA[lower]["inner"][line_idx]
    return TRIGRAM_NAJIA[upper]["outer"][line_idx - 3]


def hidden_spirits_for_lines(lines: list[int], palace: str, palace_element: str) -> dict[int, str]:
    visible_relations = set()
    for idx in range(6):
        ganzi = najia_for_line(lines, idx)
        visible_relations.add(six_relation(palace_element, ganzi_element(ganzi)))

    palace_lines = list(TRIGRAM_LINES[palace]) + list(TRIGRAM_LINES[palace])
    hidden = {}
    for idx in range(6):
        ganzi = najia_for_line(palace_lines, idx)
        element = ganzi_element(ganzi)
        relation = six_relation(palace_element, element)
        if relation not in visible_relations:
            hidden[idx] = f"{relation}{ganzi}{element}"
    return hidden


def line_symbol(kind: str) -> str:
    return "yang" if kind == "阳" else "yin"


def readable_bits(bits: str) -> str:
    return " ".join("背" if bit == "1" else "字" for bit in bits)


def build_chart_payload(records: list[YaoRecord], moment: datetime | None = None) -> dict[str, Any]:
    time_info = ganzhi_context(moment)
    ben_lines = line_bits_from_records(records, "ben")
    bian_lines = line_bits_from_records(records, "bian")
    ben_lower, ben_upper = trigrams_from_lines(ben_lines)
    bian_lower, bian_upper = trigrams_from_lines(bian_lines)
    palace, shi_idx, ying_idx = determine_palace(ben_lines)
    bian_palace, _, _ = determine_palace(bian_lines)
    palace_element = TRIGRAM_ELEMENTS[palace]
    hidden_spirits = hidden_spirits_for_lines(ben_lines, palace, palace_element)
    day_stem = time_info["pillars"]["day"][0]
    spirit_start = SIX_SPIRIT_START_BY_DAY_STEM[day_stem]
    spirits_bottom_to_top = [SIX_SPIRITS[(spirit_start + idx) % 6] for idx in range(6)]

    rows_bottom_to_top = []
    for idx, record in enumerate(records):
        ben_ganzi = najia_for_line(ben_lines, idx)
        ben_element = ganzi_element(ben_ganzi)
        ben_relation = six_relation(palace_element, ben_element)
        bian_ganzi = najia_for_line(bian_lines, idx)
        bian_element = ganzi_element(bian_ganzi)
        bian_relation = six_relation(palace_element, bian_element)
        rows_bottom_to_top.append(
            {
                "yao": record.yao,
                "yao_name": record.yao_name,
                "position_label": "世" if idx == shi_idx else "应" if idx == ying_idx else "",
                "six_spirit": spirits_bottom_to_top[idx],
                "hidden_spirit": hidden_spirits.get(idx, ""),
                "ben": {
                    "relation": ben_relation,
                    "ganzi": ben_ganzi,
                    "element": ben_element,
                    "text": f"{ben_relation}{ben_ganzi}{ben_element}",
                    "line": line_symbol(record.ben),
                },
                "change_mark": "○→" if record.yao_type == "老阳" else "×→" if record.yao_type == "老阴" else "",
                "bian": {
                    "relation": bian_relation,
                    "ganzi": bian_ganzi,
                    "element": bian_element,
                    "text": f"{bian_relation}{bian_ganzi}{bian_element}",
                    "line": line_symbol(record.bian),
                },
                "quantum": {
                    "bits": record.bits,
                    "faces": readable_bits(record.bits),
                    "backs": record.backs,
                    "yao_type": record.yao_type,
                },
            }
        )

    return {
        "time": time_info,
        "ben": {
            "palace": palace,
            "name": HEXAGRAM_NAMES[(ben_upper, ben_lower)],
            "upper": ben_upper,
            "lower": ben_lower,
            "palace_element": palace_element,
        },
        "bian": {
            "palace": bian_palace,
            "name": HEXAGRAM_NAMES[(bian_upper, bian_lower)],
            "upper": bian_upper,
            "lower": bian_lower,
        },
        "shi": shi_idx + 1,
        "ying": ying_idx + 1,
        "rows_bottom_to_top": rows_bottom_to_top,
        "rows_top_to_bottom": list(reversed(rows_bottom_to_top)),
    }


def set_job(run_id: str, **updates: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.setdefault(run_id, {})
        job.update(updates)
        job["updated_at"] = now_label()


def get_job(run_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(run_id)
        if job is None:
            return None
        return json.loads(json.dumps(job, ensure_ascii=False))


def active_job_locked() -> dict[str, Any] | None:
    for job in JOBS.values():
        if job.get("status") in ACTIVE_STATUSES:
            return job
    return None


def get_active_job() -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = active_job_locked()
        if job is None:
            return None
        return json.loads(json.dumps(job, ensure_ascii=False))


def runtime_status_name(status: Any) -> str:
    if hasattr(status, "name"):
        return str(status.name).upper()
    text = str(status).strip()
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.upper()


def build_single_yao_circuit(register_name: str = "meas") -> QuantumCircuit:
    qr = QuantumRegister(3, "q")
    cr = ClassicalRegister(3, register_name)
    qc = QuantumCircuit(qr, cr, name="single_yao")
    qc.h(qr[0])
    qc.h(qr[1])
    qc.h(qr[2])
    qc.measure(qr, cr)
    return qc


def make_service() -> QiskitRuntimeService:
    token = os.getenv("IBM_QUANTUM_API_KEY") or os.getenv("QISKIT_IBM_TOKEN")
    instance = os.getenv("IBM_QUANTUM_INSTANCE")
    channel = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform")

    if token:
        kwargs: dict[str, Any] = {"channel": channel, "token": token}
        if instance:
            kwargs["instance"] = instance
        return QiskitRuntimeService(**kwargs)

    kwargs = {"channel": channel}
    if instance:
        kwargs["instance"] = instance
    return QiskitRuntimeService(**kwargs)


def choose_backend(service: QiskitRuntimeService, backend_name: str | None = None):
    if backend_name:
        return service.backend(backend_name)
    return service.least_busy(operational=True, simulator=False, min_num_qubits=3)


def map_bitstring_to_yao(bitstring: str, *, one_means_back: bool = True) -> dict[str, Any]:
    if len(bitstring) != 3 or any(ch not in "01" for ch in bitstring):
        raise ValueError(f"非法 bitstring: {bitstring!r}")

    backs = bitstring.count("1") if one_means_back else bitstring.count("0")
    if backs == 0:
        return {"backs": 0, "symbol": "交", "yao_type": "老阴", "moving": True, "ben": "阴", "bian": "阳"}
    if backs == 1:
        return {"backs": 1, "symbol": "单", "yao_type": "少阳", "moving": False, "ben": "阳", "bian": "阳"}
    if backs == 2:
        return {"backs": 2, "symbol": "拆", "yao_type": "少阴", "moving": False, "ben": "阴", "bian": "阴"}
    return {"backs": 3, "symbol": "重", "yao_type": "老阳", "moving": True, "ben": "阳", "bian": "阴"}


MANUAL_YAO_BITS = {
    "old_yin": "000",
    "laoyin": "000",
    "老阴": "000",
    "老陰": "000",
    "交": "000",
    "0": "000",
    "young_yang": "001",
    "shaoyang": "001",
    "少阳": "001",
    "少陽": "001",
    "单": "001",
    "單": "001",
    "1": "001",
    "young_yin": "110",
    "shaoyin": "110",
    "少阴": "110",
    "少陰": "110",
    "拆": "110",
    "2": "110",
    "old_yang": "111",
    "laoyang": "111",
    "老阳": "111",
    "老陽": "111",
    "重": "111",
    "3": "111",
}


def normalize_manual_yao(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value") or value.get("yao_type") or value.get("type") or value.get("bits")
    text = str(value or "").strip()
    if len(text) == 3 and all(ch in "01" for ch in text):
        return text
    if text in MANUAL_YAO_BITS:
        return MANUAL_YAO_BITS[text]
    raise ValueError(f"无法识别手动爻值: {text or value!r}")


def records_from_manual_yaos(yaos: list[Any]) -> list[YaoRecord]:
    if len(yaos) != 6:
        raise ValueError("手动排盘需要自下而上输入 6 个爻。")

    records = []
    for idx, value in enumerate(yaos, start=1):
        bits = normalize_manual_yao(value)
        mapped = map_bitstring_to_yao(bits, one_means_back=True)
        records.append(
            YaoRecord(
                yao=idx,
                yao_name=YAO_NAMES[idx],
                bits=bits,
                backs=mapped["backs"],
                symbol=mapped["symbol"],
                yao_type=mapped["yao_type"],
                moving=mapped["moving"],
                ben=mapped["ben"],
                bian=mapped["bian"],
            )
        )
    return records


def parse_cast_time(value: Any) -> datetime:
    if value in (None, ""):
        return datetime.now(cast_timezone())

    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"起卦时间格式不正确: {text}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=cast_timezone())
    return parsed.astimezone(cast_timezone())


def ben_summary_label(record: YaoRecord) -> str:
    return record.yao_type if record.moving else record.ben


def build_result_payload(
    records: list[YaoRecord],
    *,
    backend_name: str,
    job_id: str,
    moment: datetime | None = None,
) -> dict[str, Any]:
    ben_gua = [r.ben for r in records]
    bian_gua = [r.bian for r in records]
    dong_yao = [r.yao for r in records if r.moving]
    dong_yao_detail = [f"{r.yao}={r.yao_type}" for r in records if r.moving]
    chart = build_chart_payload(records, moment)

    return {
        "backend": backend_name,
        "job_id": job_id,
        "convention": {
            "bit_meaning": "1=背, 0=字",
            "order": "初爻到上爻，自下而上",
            "execution": "3 qubits per yao, 6 pubs, 1 shot each",
        },
        "raw_bits_bottom_to_top": [r.bits for r in records],
        "yao_records": [asdict(r) for r in records],
        "ben_gua_bottom_to_top": ben_gua,
        "ben_gua_summary_bottom_to_top": [ben_summary_label(r) for r in records],
        "bian_gua_bottom_to_top": bian_gua,
        "yao_types_bottom_to_top": [r.yao_type for r in records],
        "dong_yao": dong_yao,
        "dong_yao_detail": dong_yao_detail,
        "chart": chart,
    }


def compact_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "backend": payload["backend"],
        "job_id": payload["job_id"],
        "yao_records": [
            {
                "yao": rec["yao"],
                "yao_name": rec["yao_name"],
                "yao_type": rec["yao_type"],
                "moving": rec["moving"],
            }
            for rec in payload["yao_records"]
        ],
        "dong_yao": payload["dong_yao"],
        "dong_yao_detail": payload["dong_yao_detail"],
        "chart": payload["chart"],
    }


def run_divination(run_id: str, backend_name: str | None) -> None:
    output_path = RESULTS_DIR / f"liuyao_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{run_id[:8]}.json"
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        set_job(run_id, status="CONNECTING", status_label="连接 IBM Quantum", backend=backend_name or "自动选择")
        service = make_service()

        set_job(run_id, status="SELECTING_BACKEND", status_label="选择量子机")
        backend = choose_backend(service, backend_name)
        set_job(run_id, backend=backend.name)

        set_job(run_id, status="TRANSPILING", status_label="编译量子电路")
        qc = build_single_yao_circuit(register_name="meas")
        optimization_level = int(os.getenv("QISKIT_OPTIMIZATION_LEVEL", "1"))
        pm = generate_preset_pass_manager(backend=backend, optimization_level=optimization_level)
        isa_circuit = pm.run(qc)
        sampler = Sampler(mode=backend)

        set_job(run_id, status="SUBMITTING", status_label="提交到量子机")
        pubs = [isa_circuit for _ in range(6)]
        runtime_job = sampler.run(pubs, shots=1)
        job_id = runtime_job.job_id()
        set_job(run_id, status="QUEUED", status_label="等待 IBM Runtime", job_id=job_id)

        terminal_states = {"DONE", "ERROR", "CANCELLED", "CANCELED"}
        while True:
            raw_status = runtime_status_name(runtime_job.status())
            if raw_status in {"QUEUED", "INITIALIZING", "VALIDATING", "RUNNING"}:
                set_job(run_id, status=raw_status, status_label=f"IBM 状态: {raw_status}")
            if raw_status in terminal_states:
                break
            time.sleep(2)

        if raw_status != "DONE":
            raise RuntimeError(f"IBM Runtime 作业未完成: {raw_status}")

        set_job(run_id, status="READING_RESULT", status_label="读取测量结果")
        result = runtime_job.result()

        records = []
        for idx, pub_result in enumerate(result, start=1):
            bitstrings = pub_result.data.meas.get_bitstrings()
            if len(bitstrings) != 1:
                raise RuntimeError(f"第 {idx} 爻返回 {len(bitstrings)} 条 bitstring，预期 1 条。")
            bits = bitstrings[0]
            mapped = map_bitstring_to_yao(bits, one_means_back=True)
            records.append(
                YaoRecord(
                    yao=idx,
                    yao_name=YAO_NAMES[idx],
                    bits=bits,
                    backs=mapped["backs"],
                    symbol=mapped["symbol"],
                    yao_type=mapped["yao_type"],
                    moving=mapped["moving"],
                    ben=mapped["ben"],
                    bian=mapped["bian"],
                )
            )

        payload = build_result_payload(records, backend_name=backend.name, job_id=job_id)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        set_job(
            run_id,
            status="DONE",
            status_label="完成",
            output_path=str(output_path),
            result=compact_result(payload),
        )
    except Exception as exc:
        set_job(run_id, status="ERROR", status_label="出错", error=str(exc), output_path=str(output_path))


class Handler(SimpleHTTPRequestHandler):
    server_version = "LiuYaoQuantumWeb/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def json_response(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, send_body: bool = True) -> bool:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/" or path == "":
            path = "/index.html"

        target = (STATIC_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or not target.is_file():
            return False

        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)
        return True

    def do_HEAD(self) -> None:
        if not self.serve_static(send_body=False):
            self.send_error(HTTPStatus.NOT_FOUND.value)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self.json_response({"ok": True, "service": "liuyao_quantum_web"})
            return

        if path == "/api/active-job":
            self.json_response({"job": get_active_job()})
            return

        if path.startswith("/api/jobs/"):
            run_id = path.rsplit("/", 1)[-1]
            job = get_job(run_id)
            if job is None:
                self.json_response({"error": "找不到这次起卦。"}, HTTPStatus.NOT_FOUND)
                return
            self.json_response(job)
            return

        if not self.serve_static(send_body=True):
            self.send_error(HTTPStatus.NOT_FOUND.value)

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/manual-chart":
            body = self.read_json_body()
            try:
                cast_time = parse_cast_time(body.get("cast_time"))
                yaos = body.get("yaos") or []
                records = records_from_manual_yaos(yaos)
                payload = build_result_payload(records, backend_name="手动排盘", job_id="manual", moment=cast_time)
            except ValueError as exc:
                self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.json_response({"result": compact_result(payload)})
            return

        if parsed.path == "/api/life-kline":
            body = self.read_json_body()
            try:
                result = generate_life_kline(body)
            except ValueError as exc:
                self.json_response({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except RuntimeError as exc:
                self.json_response({"error": str(exc)}, HTTPStatus.BAD_GATEWAY)
                return
            self.json_response({"result": result})
            return

        if parsed.path != "/api/divinations":
            self.send_error(HTTPStatus.NOT_FOUND.value)
            return

        body = self.read_json_body()

        backend_name = str(body.get("backend") or "").strip() or None
        run_id = uuid.uuid4().hex
        with JOBS_LOCK:
            active_job = active_job_locked()
            if active_job is not None:
                self.json_response(
                    {
                        "run_id": active_job["run_id"],
                        "already_running": True,
                        "message": "已有一卦正在运行。",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            JOBS[run_id] = {
                "run_id": run_id,
                "status": "CREATED",
                "status_label": "准备起卦",
                "backend": backend_name or "自动选择",
                "job_id": "",
                "created_at": now_label(),
                "updated_at": now_label(),
            }

        worker = threading.Thread(target=run_divination, args=(run_id, backend_name), daemon=True)
        worker.start()
        self.json_response({"run_id": run_id})


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IBM Quantum 六爻起卦本地网站")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not port_is_free(args.host, args.port):
        raise SystemExit(f"{args.host}:{args.port} 已被占用，请换一个端口。")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"六爻量子起卦网站已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
