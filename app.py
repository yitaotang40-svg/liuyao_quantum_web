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
YANG_STEMS = {"甲", "丙", "戊", "庚", "壬"}
FLOW_MONTH_BRANCHES = list("寅卯辰巳午未申酉戌亥子丑")
FLOW_MONTH_NAMES = ["寅月", "卯月", "辰月", "巳月", "午月", "未月", "申月", "酉月", "戌月", "亥月", "子月", "丑月"]
FLOW_MONTH_JIE_INDICES = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 0]
BRANCH_CLASH = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅", "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
BRANCH_COMBINE = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}
BRANCH_HARM = {"子": "未", "未": "子", "丑": "午", "午": "丑", "寅": "巳", "巳": "寅", "卯": "辰", "辰": "卯", "申": "亥", "亥": "申", "酉": "戌", "戌": "酉"}
BRANCH_TRINES = [("申子辰", "水"), ("亥卯未", "木"), ("寅午戌", "火"), ("巳酉丑", "金")]
BRANCH_MEETINGS = [("寅卯辰", "木"), ("巳午未", "火"), ("申酉戌", "金"), ("亥子丑", "水")]
STEM_COMBINES = {"甲": ("己", "土"), "己": ("甲", "土"), "乙": ("庚", "金"), "庚": ("乙", "金"), "丙": ("辛", "水"), "辛": ("丙", "水"), "丁": ("壬", "木"), "壬": ("丁", "木"), "戊": ("癸", "火"), "癸": ("戊", "火")}
STEM_CLASH = {"甲": "庚", "庚": "甲", "乙": "辛", "辛": "乙", "壬": "丙", "丙": "壬", "癸": "丁", "丁": "癸"}
NATAL_BRANCH_LABELS = ["年支", "月支", "日支", "时支"]
PILLAR_LABELS = ["年柱", "月柱", "日柱", "时柱"]
BRANCH_HIDDEN_STEMS = {
    "子": [("癸", 1.0)],
    "丑": [("己", 0.6), ("癸", 0.25), ("辛", 0.15)],
    "寅": [("甲", 0.6), ("丙", 0.25), ("戊", 0.15)],
    "卯": [("乙", 1.0)],
    "辰": [("戊", 0.6), ("乙", 0.25), ("癸", 0.15)],
    "巳": [("丙", 0.6), ("庚", 0.25), ("戊", 0.15)],
    "午": [("丁", 0.7), ("己", 0.3)],
    "未": [("己", 0.6), ("丁", 0.25), ("乙", 0.15)],
    "申": [("庚", 0.6), ("壬", 0.25), ("戊", 0.15)],
    "酉": [("辛", 1.0)],
    "戌": [("戊", 0.6), ("辛", 0.25), ("丁", 0.15)],
    "亥": [("壬", 0.7), ("甲", 0.3)],
}
ELEMENT_STORAGE_BRANCH = {"木": "未", "火": "戌", "土": "戌", "金": "丑", "水": "辰"}
HELPFUL_DAY_STATES = {"旺", "强"}
WEAK_DAY_STATES = {"衰", "弱"}
WEALTH_TEN_GODS = {"正财", "偏财"}
OUTPUT_TEN_GODS = {"食神", "伤官"}
PEER_TEN_GODS = {"比肩", "劫财"}
RESOURCE_TEN_GODS = {"正印", "偏印"}
OFFICER_TEN_GODS = {"正官", "七杀"}
GROWTH_STATES_BY_STEM = {
    "甲": dict(zip(list("亥子丑寅卯辰巳午未申酉戌"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "乙": dict(zip(list("午巳辰卯寅丑子亥戌酉申未"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "丙": dict(zip(list("寅卯辰巳午未申酉戌亥子丑"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "丁": dict(zip(list("酉申未午巳辰卯寅丑子亥戌"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "戊": dict(zip(list("寅卯辰巳午未申酉戌亥子丑"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "己": dict(zip(list("酉申未午巳辰卯寅丑子亥戌"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "庚": dict(zip(list("巳午未申酉戌亥子丑寅卯辰"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "辛": dict(zip(list("子亥戌酉申未午巳辰卯寅丑"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "壬": dict(zip(list("申酉戌亥子丑寅卯辰巳午未"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
    "癸": dict(zip(list("卯寅丑子亥戌酉申未午巳辰"), ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"])),
}
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
LIFE_KLINE_ENGINE_VERSION = "wealth-v3.4-market-dashboard-range"
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
你是一位严谨的八字命理分析师，精通用四柱、大运、流年生成“财运K线”。请根据用户信息、后端换算出的四柱干支、大运参数和财运结构诊断，生成以财富、现金流、项目变现、投资风险为重点的完整命理报告和 100 年 K 线数据。

硬性规则：
1. 只返回纯 JSON，不要 Markdown，不要解释文字。
2. 所有分析必须以“后端已换算四柱”和“后端已推算大运参数”为准，不要重新排四柱。
3. 分析分数字段使用 0-10 分；K线 open/close/high/low/score 使用 0-100 分。
4. chartPoints 必须正好 100 条，年龄采用虚岁，从 1 岁到 100 岁。
5. 每条 chartPoints 的 reason 控制在 20-30 个中文字符，简洁说明当年吉凶趋势。
6. 数据要有明显起伏，体现大运、流年、财星、食伤生财、比劫夺财、财库冲合和人生阶段差异，禁止输出平滑直线。
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
  "wealth": "财富分析，必须说明能否任财、财星喜忌、主要赚钱方式和破财风险",
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
你是一位严谨的八字命理分析师。请只为用户指定的年龄范围生成“财运K线”chartPoints。

硬性规则：
1. 只返回纯 JSON，不要 Markdown，不要解释文字。
2. 只输出 chartPoints，不要输出命理报告。
3. chartPoints 条数必须等于用户指定年龄范围的年数。
4. K线 open/close/high/low/score 使用 0-100 分。
5. 每条 reason 控制在 20-30 个中文字符，简洁说明当年吉凶趋势。
6. daYun、year、ganZhi 必须严格按用户给定的年龄、流年和大运表填写。
7. 数据要有明显起伏，体现大运、流年、财星、食伤生财、比劫夺财、财库冲合和人生阶段差异，禁止输出平滑直线。

输出 JSON 结构：
{
  "chartPoints": [
    {"age":1,"year":1990,"daYun":"童限","ganZhi":"庚午","open":50,"close":55,"high":60,"low":45,"score":55,"reason":"开局平稳，家庭助力较足"}
  ]
}
""".strip()

LIFE_KLINE_ANALYSIS_INSTRUCTION = """
你是一位严谨的八字命理分析师。请根据用户的出生信息、后端换算出的四柱干支、大运信息、财运结构诊断和K线摘要，生成以财运为重点的命理报告。

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
  "wealth": "财富分析，必须说明能否任财、财星喜忌、主要赚钱方式和破财风险",
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
        try:
            return json.loads(content, strict=False)
        except json.JSONDecodeError:
            repaired = re.sub(r"}\s*{", "},{", content)
            repaired = re.sub(r"]\s*\"", "],\"", repaired)
            repaired = re.sub(r"\"\s*\"", "\",\"", repaired)
            return json.loads(repaired, strict=False)


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


def apply_deterministic_life_analysis_fields(
    analysis: dict[str, Any],
    bazi: list[str],
    chart_data: list[dict[str, Any]],
) -> dict[str, Any]:
    peak = max(chart_data, key=lambda point: float(point["score"]))
    analysis["bazi"] = bazi
    analysis["cryptoYear"] = f"{peak['year']}年（{peak['ganZhi']}）"
    return analysis


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


def ten_god_for_stem(day_stem: str, target_stem: str) -> str:
    day_element = STEM_ELEMENTS[day_stem]
    target_element = STEM_ELEMENTS[target_stem]
    same_polarity = (day_stem in YANG_STEMS) == (target_stem in YANG_STEMS)
    if target_element == day_element:
        return "比肩" if same_polarity else "劫财"
    if GENERATES[target_element] == day_element:
        return "偏印" if same_polarity else "正印"
    if GENERATES[day_element] == target_element:
        return "食神" if same_polarity else "伤官"
    if CONTROLS[target_element] == day_element:
        return "七杀" if same_polarity else "正官"
    if CONTROLS[day_element] == target_element:
        return "偏财" if same_polarity else "正财"
    return "平"


def ten_god_category(ten_god: str) -> str:
    if ten_god in {"正印", "偏印"}:
        return "印星：学习、资源、修复"
    if ten_god in {"比肩", "劫财"}:
        return "比劫：人际、竞争、合伙"
    if ten_god in {"食神", "伤官"}:
        return "食伤：表达、创作、输出"
    if ten_god in {"正财", "偏财"}:
        return "财星：现金流、交易、机会"
    if ten_god in {"正官", "七杀"}:
        return "官杀：规则、职位、压力"
    return "平衡：观察、蓄力"


def element_relation_score(day_element: str, target_element: str) -> float:
    if target_element == day_element:
        return 7.0
    if GENERATES[target_element] == day_element:
        return 8.0
    if GENERATES[day_element] == target_element:
        return -4.0
    if CONTROLS[day_element] == target_element:
        return -5.5
    if CONTROLS[target_element] == day_element:
        return -7.0
    return 0.0


def day_master_profile(bazi: list[str]) -> dict[str, Any]:
    day_stem = bazi[2][0]
    day_element = STEM_ELEMENTS[day_stem]
    month_branch = bazi[1][1]
    month_state = element_season_state(day_element, month_branch)
    score = {"旺": 34.0, "相": 22.0, "休": 6.0, "囚": -12.0, "死": -24.0}[month_state]
    stem_weights = [0.8, 1.2, 0.0, 0.8]
    branch_weights = [0.8, 1.45, 1.15, 0.85]
    growth_scores = {
        "长生": 12.0,
        "沐浴": 0.0,
        "冠带": 8.0,
        "临官": 14.0,
        "帝旺": 16.0,
        "衰": -5.0,
        "病": -8.0,
        "死": -12.0,
        "墓": 3.0,
        "绝": -15.0,
        "胎": 2.0,
        "养": 4.0,
    }
    details: list[str] = [f"月令{month_branch}为日主{day_element}{month_state}"]
    for index, pillar in enumerate(bazi):
        if index != 2:
            stem_element = STEM_ELEMENTS[pillar[0]]
            score += element_relation_score(day_element, stem_element) * stem_weights[index]
        branch = pillar[1]
        growth = growth_state_for_stem(day_stem, branch)
        score += growth_scores.get(growth, 0.0) * branch_weights[index] * 0.65
        for hidden_stem, hidden_weight in BRANCH_HIDDEN_STEMS[branch]:
            hidden_element = STEM_ELEMENTS[hidden_stem]
            score += element_relation_score(day_element, hidden_element) * branch_weights[index] * hidden_weight
    if score >= 60:
        level = "旺"
    elif score >= 28:
        level = "强"
    elif score >= 4:
        level = "中和"
    elif score >= -22:
        level = "衰"
    else:
        level = "弱"
    if level in HELPFUL_DAY_STATES:
        useful = ["财星", "官杀", "食伤"]
        avoid = ["比劫", "印星"]
        strategy = "日主偏强，宜泄、宜克、宜用财官承接。"
    elif level in WEAK_DAY_STATES:
        useful = ["印星", "比劫"]
        avoid = ["财星", "官杀", "食伤"]
        strategy = "日主偏弱，先要印比扶身，再谈承财。"
    else:
        useful = ["财星", "官杀", "食伤", "印星"]
        avoid = ["劫财过重"]
        strategy = "日主中和，财官食伤可用，但忌一方过偏。"
    return {
        "dayStem": day_stem,
        "dayElement": day_element,
        "monthBranch": month_branch,
        "monthState": month_state,
        "strengthScore": round(score, 1),
        "strengthLevel": level,
        "usefulGroups": useful,
        "avoidGroups": avoid,
        "strategy": strategy,
        "details": details,
    }


def ten_god_group(ten_god: str) -> str:
    if ten_god in WEALTH_TEN_GODS:
        return "财星"
    if ten_god in OUTPUT_TEN_GODS:
        return "食伤"
    if ten_god in PEER_TEN_GODS:
        return "比劫"
    if ten_god in RESOURCE_TEN_GODS:
        return "印星"
    if ten_god in OFFICER_TEN_GODS:
        return "官杀"
    return "平衡"


def pillar_ten_gods(day_stem: str, pillar: str) -> list[tuple[str, float, str]]:
    stems = [(pillar[0], 1.0)] + BRANCH_HIDDEN_STEMS[pillar[1]]
    return [(ten_god_for_stem(day_stem, stem), weight, stem) for stem, weight in stems]


def bazi_ten_god_grid(bazi: list[str], day_profile: dict[str, Any]) -> list[dict[str, Any]]:
    day_stem = day_profile["dayStem"]
    day_element = day_profile["dayElement"]
    rows: list[dict[str, Any]] = []
    for index, pillar in enumerate(bazi):
        branch = pillar[1]
        hidden = [
            {
                "stem": hidden_stem,
                "element": STEM_ELEMENTS[hidden_stem],
                "tenGod": ten_god_for_stem(day_stem, hidden_stem),
                "weight": hidden_weight,
            }
            for hidden_stem, hidden_weight in BRANCH_HIDDEN_STEMS[branch]
        ]
        rows.append(
            {
                "label": PILLAR_LABELS[index],
                "pillar": pillar,
                "stem": pillar[0],
                "branch": branch,
                "stemElement": STEM_ELEMENTS[pillar[0]],
                "branchElement": BRANCH_ELEMENTS[branch],
                "stemTenGod": "日主" if index == 2 else ten_god_for_stem(day_stem, pillar[0]),
                "branchMainTenGod": hidden[0]["tenGod"],
                "hiddenStems": hidden,
                "growthState": growth_state_for_stem(day_stem, branch),
                "seasonState": element_season_state(day_element, branch),
            }
        )
    return rows


def bazi_pattern_profile(bazi: list[str], day_profile: dict[str, Any]) -> dict[str, Any]:
    day_stem = day_profile["dayStem"]
    month_branch = bazi[1][1]
    hidden = BRANCH_HIDDEN_STEMS[month_branch]
    candidate_stems = [bazi[index][0] for index in (1, 0, 3)]
    main_stem = hidden[0][0]
    visible_hidden = [(stem, weight) for stem, weight in hidden if stem in candidate_stems]

    if main_stem in candidate_stems:
        selected_stem = main_stem
        source = "月令本气透干取格"
    elif len(hidden) == 1:
        selected_stem = main_stem
        source = "月令独藏本气取格"
    elif visible_hidden:
        selected_stem = max(visible_hidden, key=lambda item: item[1])[0]
        source = "月令余气透干取格"
    else:
        selected_stem = max(hidden, key=lambda item: item[1])[0]
        source = "月令藏干强弱取格"

    ten_god = ten_god_for_stem(day_stem, selected_stem)
    group = ten_god_group(ten_god)
    if ten_god in PEER_TEN_GODS:
        pattern_name = "建禄格" if month_branch == RILU_BY_STEM.get(day_stem) else "比劫变格"
    elif ten_god == "七杀":
        pattern_name = "七杀格"
    else:
        pattern_name = f"{ten_god}格"

    visible_at = [PILLAR_LABELS[index] for index in (0, 1, 3) if bazi[index][0] == selected_stem]
    if group in day_profile.get("usefulGroups", []):
        quality = "格局落在喜用方向"
    elif group in day_profile.get("avoidGroups", []):
        quality = "格局落在忌神方向"
    else:
        quality = "格局需看全局扶抑"
    return {
        "monthBranch": month_branch,
        "selectedStem": selected_stem,
        "selectedElement": STEM_ELEMENTS[selected_stem],
        "tenGod": ten_god,
        "group": group,
        "patternName": pattern_name,
        "source": source,
        "visibleAt": visible_at,
        "quality": quality,
    }


def natal_relation_signals(bazi: list[str]) -> list[str]:
    stems = [pillar[0] for pillar in bazi]
    branches = [pillar[1] for pillar in bazi]
    signals: list[str] = []
    branch_set = set(branches)

    for group_text, element in BRANCH_MEETINGS:
        if set(group_text).issubset(branch_set):
            signals.append(f"{group_text}三会{element}局")
    for group_text, element in BRANCH_TRINES:
        if set(group_text).issubset(branch_set):
            signals.append(f"{group_text}三合{element}局")

    labels = list("年月日时")
    for left in range(4):
        for right in range(left + 1, 4):
            distance = "紧贴" if right - left == 1 else "隔位"
            left_stem, right_stem = stems[left], stems[right]
            combine_target = STEM_COMBINES.get(left_stem)
            if combine_target and combine_target[0] == right_stem:
                signals.append(f"{labels[left]}干{left_stem}{labels[right]}干{right_stem}合{combine_target[1]}（{distance}）")
            if STEM_CLASH.get(left_stem) == right_stem:
                signals.append(f"{labels[left]}干{left_stem}{labels[right]}干{right_stem}冲（{distance}）")

            left_branch, right_branch = branches[left], branches[right]
            if BRANCH_CLASH.get(left_branch) == right_branch:
                signals.append(f"{labels[left]}支{left_branch}{labels[right]}支{right_branch}冲（{distance}）")
            if BRANCH_COMBINE.get(left_branch) == right_branch:
                signals.append(f"{labels[left]}支{left_branch}{labels[right]}支{right_branch}合（{distance}）")
            if BRANCH_HARM.get(left_branch) == right_branch:
                signals.append(f"{labels[left]}支{left_branch}{labels[right]}支{right_branch}害（{distance}）")
            punishment = branch_punishment(left_branch, right_branch)
            if punishment:
                signals.append(f"{labels[left]}支{left_branch}{labels[right]}支{right_branch}{punishment}（{distance}）")
    return signals[:18]


def wealth_structure_profile(bazi: list[str], day_profile: dict[str, Any]) -> dict[str, Any]:
    day_stem = day_profile["dayStem"]
    day_element = day_profile["dayElement"]
    wealth_element = CONTROLS[day_element]
    wealth_storage = ELEMENT_STORAGE_BRANCH[wealth_element]
    visible_wealth = 0.0
    hidden_wealth = 0.0
    output_power = 0.0
    peer_power = 0.0
    officer_power = 0.0
    resource_power = 0.0
    wealth_branches: list[str] = []
    for index, pillar in enumerate(bazi):
        stem_ten_god = ten_god_for_stem(day_stem, pillar[0])
        if index != 2:
            if stem_ten_god in WEALTH_TEN_GODS:
                visible_wealth += 1.0
            if stem_ten_god in OUTPUT_TEN_GODS:
                output_power += 1.0
            elif stem_ten_god in PEER_TEN_GODS:
                peer_power += 1.0
            elif stem_ten_god in OFFICER_TEN_GODS:
                officer_power += 1.0
            elif stem_ten_god in RESOURCE_TEN_GODS:
                resource_power += 1.0
        for hidden_stem, weight in BRANCH_HIDDEN_STEMS[pillar[1]]:
            ten_god = ten_god_for_stem(day_stem, hidden_stem)
            if ten_god in WEALTH_TEN_GODS:
                hidden_wealth += weight
                if pillar[1] not in wealth_branches:
                    wealth_branches.append(pillar[1])
            elif ten_god in OUTPUT_TEN_GODS:
                output_power += weight
            elif ten_god in PEER_TEN_GODS:
                peer_power += weight
            elif ten_god in OFFICER_TEN_GODS:
                officer_power += weight
            elif ten_god in RESOURCE_TEN_GODS:
                resource_power += weight
    wealth_power = visible_wealth * 1.4 + hidden_wealth
    structures: list[str] = []
    if visible_wealth:
        structures.append("财星透干")
    if hidden_wealth:
        structures.append("财星藏支有根")
    if output_power and wealth_power:
        structures.append("食伤生财")
    if officer_power and wealth_power:
        structures.append("财官相生")
    if wealth_storage in [pillar[1] for pillar in bazi]:
        structures.append(f"命带{wealth_storage}财库")
    if day_profile["strengthLevel"] in HELPFUL_DAY_STATES and wealth_power:
        structures.append("身强可任财")
    if day_profile["strengthLevel"] in WEAK_DAY_STATES and wealth_power >= 2.2:
        structures.append("财多身弱")
    if peer_power >= 2.6 and wealth_power:
        structures.append("比劫分财")
    if not structures:
        structures.append("财星不显，重看岁运引动")
    if day_profile["strengthLevel"] in HELPFUL_DAY_STATES:
        wealth_favorability = 12 + min(10, wealth_power * 3) + min(6, output_power * 1.2) - min(8, peer_power * 1.1)
        wealth_readiness = "能任财" if wealth_power else "待财星引动"
    elif day_profile["strengthLevel"] in WEAK_DAY_STATES:
        wealth_favorability = -8 + min(8, resource_power + peer_power) - min(10, wealth_power * 2.2)
        wealth_readiness = "先扶身再取财"
    else:
        wealth_favorability = 6 + min(9, wealth_power * 2.2) + min(4, output_power) - min(6, peer_power)
        wealth_readiness = "可取财但看平衡"
    return {
        "wealthElement": wealth_element,
        "wealthStorageBranch": wealth_storage,
        "visibleWealth": round(visible_wealth, 2),
        "hiddenWealth": round(hidden_wealth, 2),
        "wealthPower": round(wealth_power, 2),
        "outputPower": round(output_power, 2),
        "peerPower": round(peer_power, 2),
        "officerPower": round(officer_power, 2),
        "resourcePower": round(resource_power, 2),
        "wealthBranches": wealth_branches,
        "structures": structures,
        "wealthFavorability": round(wealth_favorability, 1),
        "wealthReadiness": wealth_readiness,
    }


def bazi_principle_notes(
    day_profile: dict[str, Any],
    pattern_profile: dict[str, Any],
    relation_signals: list[str],
    wealth_profile: dict[str, Any],
) -> list[str]:
    relation_text = "；".join(relation_signals[:4]) if relation_signals else "原局少明显刑冲合会"
    return [
        f"以日干为主：本命日主为{day_profile['dayStem']}{day_profile['dayElement']}，所有十神都围绕日主换算。",
        f"以月令定旺衰：月令{day_profile['monthBranch']}令日主{day_profile['monthState']}，综合得令、得势、得地为{day_profile['strengthLevel']}。",
        f"以月令藏干取格：{pattern_profile['source']}，格局暂取{pattern_profile['patternName']}，{pattern_profile['quality']}。",
        f"以扶抑定喜忌：{day_profile['strategy']}喜用方向为{'、'.join(day_profile['usefulGroups'])}，忌偏重{'、'.join(day_profile['avoidGroups'])}。",
        f"以刑冲合会看触发：{relation_text}。",
        f"财运只是一条输出线：财为日主所克，财星{wealth_profile['wealthElement']}，须同时看日主能否任财、食伤能否生财、比劫是否分财、官印是否护财。",
    ]


def build_wealth_context(bazi: list[str]) -> dict[str, Any]:
    day_profile = day_master_profile(bazi)
    ten_gods = bazi_ten_god_grid(bazi, day_profile)
    pattern_profile = bazi_pattern_profile(bazi, day_profile)
    relation_signals = natal_relation_signals(bazi)
    wealth_profile = wealth_structure_profile(bazi, day_profile)
    return {
        "dayMaster": day_profile,
        "tenGods": ten_gods,
        "pattern": pattern_profile,
        "relations": relation_signals,
        "principles": bazi_principle_notes(day_profile, pattern_profile, relation_signals, wealth_profile),
        "wealth": wealth_profile,
    }


def group_is_useful(group: str, day_profile: dict[str, Any]) -> bool:
    return group in day_profile.get("usefulGroups", [])


def flow_wealth_score(day_profile: dict[str, Any], wealth_profile: dict[str, Any], ten_god: str) -> float:
    group = ten_god_group(ten_god)
    strong = day_profile["strengthLevel"] in HELPFUL_DAY_STATES
    weak = day_profile["strengthLevel"] in WEAK_DAY_STATES
    if strong:
        scores = {"财星": 9.0, "食伤": 6.4, "官杀": 3.2, "印星": -4.5, "比劫": -7.0, "平衡": 0.0}
    elif weak:
        scores = {"印星": 7.2, "比劫": 4.8, "财星": -6.2, "食伤": -4.8, "官杀": -6.5, "平衡": 0.0}
    else:
        scores = {"财星": 7.0, "食伤": 5.0, "官杀": 3.0, "印星": 1.4, "比劫": -3.6, "平衡": 0.0}
    score = scores.get(group, 0.0)
    if ten_god == "偏财":
        score += 1.0 if not weak else -0.8
    if ten_god == "劫财" and wealth_profile["wealthPower"] > 0:
        score -= 1.2
    if ten_god in OUTPUT_TEN_GODS and wealth_profile["wealthPower"] > 0 and not weak:
        score += 1.5
    return score


def wealth_flow_event(day_profile: dict[str, Any], wealth_profile: dict[str, Any], stem_ten_god: str, branch_ten_gods: list[str], signals: list[str]) -> dict[str, str]:
    all_ten_gods = [stem_ten_god] + branch_ten_gods
    strong = day_profile["strengthLevel"] in HELPFUL_DAY_STATES
    weak = day_profile["strengthLevel"] in WEAK_DAY_STATES
    if stem_ten_god in OUTPUT_TEN_GODS and any(ten_god in WEALTH_TEN_GODS for ten_god in branch_ten_gods):
        return {
            "event": "食伤生财",
            "opportunity": "靠作品、表达、产品、流量转化为钱",
            "risk": "输出过度会透支精力，伤官重忌冲规则",
            "advice": "适合上线、推广、报价、做销售闭环",
        }
    if stem_ten_god in WEALTH_TEN_GODS:
        if weak:
            return {
                "event": "财星压身",
                "opportunity": "有钱财机会或回款消息",
                "risk": "身弱承财吃力，易为钱劳心或现金流紧",
                "advice": "先控仓位和成本，等印比月份再放大",
            }
        return {
            "event": "财星引动",
            "opportunity": "收入、成交、回款、投资机会增强",
            "risk": "偏财旺时忌贪快，正财旺时忌拖账",
            "advice": "主动谈钱、谈合同、收款落袋",
        }
    if stem_ten_god in OUTPUT_TEN_GODS:
        return {
            "event": "食伤生财",
            "opportunity": "靠作品、表达、产品、流量转化为钱",
            "risk": "输出过度会透支精力，伤官重忌冲规则",
            "advice": "适合上线、推广、报价、做销售闭环",
        }
    if stem_ten_god in OFFICER_TEN_GODS:
        return {
            "event": "官杀管财",
            "opportunity": "规则、职位、平台、资质带来稳定财源",
            "risk": "税务、合规、合同压力上升",
            "advice": "适合签正式协议，不适合灰色操作",
        }
    if stem_ten_god in RESOURCE_TEN_GODS:
        return {
            "event": "印星护财",
            "opportunity": "学习、资质、贵人、信息差提供保护",
            "risk": "短期收益慢，容易花钱买资源",
            "advice": "适合复盘、学习、修系统，不急重仓",
        }
    if stem_ten_god in PEER_TEN_GODS:
        if weak:
            return {
                "event": "比劫助身",
                "opportunity": "朋友、团队、合伙资源能帮你扛事",
                "risk": "账目不清仍会分利失控",
                "advice": "合作可以，但分钱规则先写清楚",
            }
        return {
            "event": "比劫夺财",
            "opportunity": "适合竞争抢单或清理低效合伙",
            "risk": "被分利、被截胡、冲动消费概率高",
            "advice": "少借钱少担保，合同和权限收紧",
        }
    if any(ten_god in WEALTH_TEN_GODS for ten_god in branch_ten_gods):
        if weak:
            return {
                "event": "财星藏支",
                "opportunity": "暗处有回款、资源或副业机会",
                "risk": "机会不在明面，先核成本和承压能力",
                "advice": "适合查旧账、谈暗线资源、小步试单",
            }
        return {
            "event": "财星藏支",
            "opportunity": "暗处有回款、资源或副业机会",
            "risk": "机会不在明面，忌冲动放大",
            "advice": "适合查旧账、谈暗线资源、小步试单",
        }
    if any(ten_god in OUTPUT_TEN_GODS for ten_god in branch_ten_gods):
        return {
            "event": "输出蓄财",
            "opportunity": "内容、产品、技能在暗处积累财源",
            "risk": "短期回款不一定立刻出现",
            "advice": "适合打磨交付、报价体系和销售材料",
        }
    if any(ten_god in OFFICER_TEN_GODS for ten_god in branch_ten_gods):
        return {
            "event": "规则伏财",
            "opportunity": "资质、合同、平台规则暗中影响收入",
            "risk": "细则、税务、违约条款容易卡现金流",
            "advice": "适合审合同和流程，不急冒进",
        }
    if any(ten_god in PEER_TEN_GODS for ten_god in branch_ten_gods):
        return {
            "event": "暗比争财",
            "opportunity": "竞争关系会逼出效率或新单",
            "risk": "暗处竞争、分利、团队内耗",
            "advice": "权限、账目、客户归属要清楚",
        }
    if any("财库" in signal or "三合" in signal or "三会" in signal for signal in signals):
        return {
            "event": "财局/财库动",
            "opportunity": "隐藏资源、库存、旧账或长期项目被引动",
            "risk": "合冲并见时先动后稳",
            "advice": "查旧账、查资产、查应收款",
        }
    return {
        "event": "平衡蓄势",
        "opportunity": "财务节奏平稳，可做准备工作",
        "risk": "缺少明显财星触发，强行推进效率低",
        "advice": "整理账目、观察机会、等待触发",
    }


def flow_wealth_influence(bazi: list[str], wealth_context: dict[str, Any], flow_pillar: str) -> dict[str, Any]:
    day_profile = wealth_context["dayMaster"]
    wealth_profile = wealth_context["wealth"]
    day_stem = day_profile["dayStem"]
    flow_stem, flow_branch = flow_pillar[0], flow_pillar[1]
    stem_ten_god = ten_god_for_stem(day_stem, flow_stem)
    hidden = [(ten_god_for_stem(day_stem, stem), weight, stem) for stem, weight in BRANCH_HIDDEN_STEMS[flow_branch]]
    branch_ten_gods = [item[0] for item in hidden]
    score = flow_wealth_score(day_profile, wealth_profile, stem_ten_god)
    for ten_god, weight, _stem in hidden:
        score += flow_wealth_score(day_profile, wealth_profile, ten_god) * weight * 0.62
    signals = branch_relation_signals(flow_branch, bazi)
    wealth_element = wealth_profile["wealthElement"]
    storage_branch = wealth_profile["wealthStorageBranch"]
    for signal in signals:
        if f"三会{wealth_element}局" in signal:
            score += 9.0
        elif f"三合{wealth_element}局" in signal:
            score += 7.5
        elif f"半会{wealth_element}" in signal:
            score += 3.8
        elif f"半合{wealth_element}" in signal:
            score += 3.2
        elif signal.endswith("合"):
            score += 2.0
        elif signal.endswith("冲"):
            score -= 2.2
        elif signal.endswith("害"):
            score -= 1.3
        elif signal.endswith("刑") or signal.endswith("自刑"):
            score -= 1.0
    if flow_branch == storage_branch:
        score += 2.4
        signals.append(f"{storage_branch}财库临月")
    if BRANCH_CLASH.get(flow_branch) == storage_branch:
        score += 1.4 if day_profile["strengthLevel"] not in WEAK_DAY_STATES else -1.8
        signals.append(f"{storage_branch}财库被冲")
    event = wealth_flow_event(day_profile, wealth_profile, stem_ten_god, branch_ten_gods, signals)
    volatility = 4.0 + abs(score) * 0.55
    if any("冲" in signal or "刑" in signal or "害" in signal for signal in signals):
        volatility += 2.4
    if stem_ten_god == "偏财":
        volatility += 1.6
    return {
        "score": round(score, 2),
        "volatility": round(volatility, 2),
        "tenGod": stem_ten_god,
        "branchTenGods": branch_ten_gods,
        "category": ten_god_category(stem_ten_god),
        "signals": signals[:8],
        **event,
    }


def season_for_branch(branch: str) -> str:
    if branch in "寅卯":
        return "春"
    if branch == "辰":
        return "四季"
    if branch in "巳午":
        return "夏"
    if branch == "未":
        return "四季"
    if branch in "申酉":
        return "秋"
    if branch == "戌":
        return "四季"
    if branch in "亥子":
        return "冬"
    return "四季"


def element_season_state(element: str, branch: str) -> str:
    season = season_for_branch(branch)
    rules = {
        "春": {"木": "旺", "火": "相", "水": "休", "金": "囚", "土": "死"},
        "夏": {"火": "旺", "土": "相", "木": "休", "水": "囚", "金": "死"},
        "秋": {"金": "旺", "水": "相", "土": "休", "火": "囚", "木": "死"},
        "冬": {"水": "旺", "木": "相", "金": "休", "土": "囚", "火": "死"},
        "四季": {"土": "旺", "金": "相", "火": "休", "木": "囚", "水": "死"},
    }
    return rules[season][element]


def growth_state_for_stem(day_stem: str, branch: str) -> str:
    return GROWTH_STATES_BY_STEM.get(day_stem, {}).get(branch, "平")


def branch_punishment(branch: str, natal_branch: str) -> str | None:
    if {branch, natal_branch} == {"子", "卯"}:
        return "刑"
    if branch in {"寅", "巳", "申"} and natal_branch in {"寅", "巳", "申"} and branch != natal_branch:
        return "刑"
    if branch in {"丑", "未", "戌"} and natal_branch in {"丑", "未", "戌"} and branch != natal_branch:
        return "刑"
    if branch == natal_branch and branch in {"辰", "午", "酉", "亥"}:
        return "自刑"
    return None


def branch_trine_signals(month_branch: str, bazi: list[str]) -> list[str]:
    natal_branches = [pillar[1] for pillar in bazi]
    branch_set = set(natal_branches + [month_branch])
    signals: list[str] = []
    for group_text, element in BRANCH_MEETINGS:
        group = set(group_text)
        if month_branch not in group:
            continue
        if group.issubset(branch_set):
            signals.append(f"{group_text}三会{element}局")
            continue
        hits = sorted((branch for branch in group.intersection(natal_branches) if branch != month_branch), key=group_text.index)
        if hits:
            signals.append(f"{month_branch}{hits[0]}半会{element}")
    for group_text, element in BRANCH_TRINES:
        group = set(group_text)
        if month_branch not in group:
            continue
        if group.issubset(branch_set):
            signals.append(f"{group_text}三合{element}局")
            continue
        hits = sorted((branch for branch in group.intersection(natal_branches) if branch != month_branch), key=group_text.index)
        if hits:
            signals.append(f"{month_branch}{hits[0]}半合{element}")
    return signals


def branch_relation_signals(month_branch: str, bazi: list[str]) -> list[str]:
    signals: list[str] = branch_trine_signals(month_branch, bazi)
    for label, pillar in zip(NATAL_BRANCH_LABELS, bazi):
        natal_branch = pillar[1]
        if BRANCH_CLASH.get(month_branch) == natal_branch:
            signals.append(f"{label}{natal_branch}冲")
        if BRANCH_COMBINE.get(month_branch) == natal_branch:
            signals.append(f"{label}{natal_branch}合")
        if BRANCH_HARM.get(month_branch) == natal_branch:
            signals.append(f"{label}{natal_branch}害")
        punishment = branch_punishment(month_branch, natal_branch)
        if punishment:
            signals.append(f"{label}{natal_branch}{punishment}")
    return signals[:6]


def flow_month_pillars(flow_year_pillar: str) -> list[str]:
    start_stem = MONTH_START_STEM_BY_YEAR_STEM[flow_year_pillar[0]]
    start_index = STEMS.index(start_stem)
    return [STEMS[(start_index + index) % 10] + FLOW_MONTH_BRANCHES[index] for index in range(12)]


def flow_month_start_terms(year: int) -> list[dict[str, Any]]:
    tz = cast_timezone()
    terms: list[dict[str, Any]] = []
    for index, term_index in enumerate(FLOW_MONTH_JIE_INDICES):
        term_year = year + 1 if term_index == 0 else year
        term = solar_terms_for_year(term_year, tz)[term_index]
        terms.append(
            {
                "name": term["name"],
                "time": term["time"].isoformat(),
                "monthName": FLOW_MONTH_NAMES[index],
            }
        )
    return terms


def month_influence_score(
    day_stem: str,
    bazi: list[str],
    month_pillar: str,
    wealth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    day_element = STEM_ELEMENTS[day_stem]
    month_stem, month_branch = month_pillar[0], month_pillar[1]
    ten_god = ten_god_for_stem(day_stem, month_stem)
    season_state = element_season_state(day_element, month_branch)
    growth_state = growth_state_for_stem(day_stem, month_branch)
    if wealth_context is None:
        wealth_context = build_wealth_context(bazi)
    influence = flow_wealth_influence(bazi, wealth_context, month_pillar)
    season_adjust = {"旺": 1.6, "相": 0.8, "休": 0.0, "囚": -0.7, "死": -1.2}[season_state]
    growth_adjust = {
        "长生": 1.0,
        "冠带": 0.6,
        "临官": 1.2,
        "帝旺": 1.4,
        "衰": -0.5,
        "病": -0.8,
        "死": -1.0,
        "绝": -1.4,
        "胎": 0.4,
        "养": 0.5,
    }.get(growth_state, 0)
    influence["score"] = round(float(influence["score"]) + season_adjust + growth_adjust, 2)
    influence["seasonState"] = season_state
    influence["growthState"] = growth_state
    return influence


def flow_month_reason(month_pillar: str, influence: dict[str, Any]) -> str:
    signal_text = "、".join(influence.get("signals", [])[:2]) if influence.get("signals") else "少刑冲"
    return f"{month_pillar}{influence['event']}：{influence['opportunity']}；{signal_text}。"


def term_date_label(term: dict[str, Any]) -> str:
    try:
        return datetime.fromisoformat(str(term["time"])).strftime("%m/%d")
    except Exception:
        return str(term.get("name") or "")


def month_window_label(start_term: dict[str, Any], end_term: dict[str, Any]) -> str:
    return f"{term_date_label(start_term)}-{term_date_label(end_term)}"


def finance_trigger_level(score: float) -> str:
    if score >= 13:
        return "强触发"
    if score >= 7:
        return "中强触发"
    if score >= 2:
        return "温和触发"
    if score >= -4:
        return "蓄势观察"
    return "风险触发"


def month_trend_label(open_value: int, close: int, high: int, low: int) -> str:
    delta = close - open_value
    spread = high - low
    if delta >= 8:
        return "上行收涨"
    if delta <= -8:
        return "下行收跌"
    if spread >= 18:
        return "宽幅震荡"
    return "窄幅整理"


def month_signal_text(signals: list[str]) -> str:
    return "、".join(signals[:3]) if signals else "少明显刑冲合会"


def month_event_profile(
    wealth_context: dict[str, Any],
    month_pillar: str,
    influence: dict[str, Any],
    year_point: dict[str, Any],
    open_value: int,
    close: int,
    high: int,
    low: int,
    start_term: dict[str, Any],
    end_term: dict[str, Any],
) -> dict[str, Any]:
    day_profile = wealth_context["dayMaster"]
    wealth_profile = wealth_context["wealth"]
    event = str(influence["event"])
    ten_god = str(influence["tenGod"])
    branch_ten_gods = [str(item) for item in influence.get("branchTenGods", [])]
    signals = [str(item) for item in influence.get("signals", [])]
    score = float(influence["score"])
    weak = day_profile["strengthLevel"] in WEAK_DAY_STATES
    strong = day_profile["strengthLevel"] in HELPFUL_DAY_STATES
    signal_text = month_signal_text(signals)

    tone = "财务蓄势月"
    cashflow = "整理现金流"
    money_source = "准备工作、旧资源整理"
    likely = ["财务节奏以观察和准备为主", "适合整理报价、合同、账目和客户线索"]
    risk_focus = "机会触发不明显，强推容易低效"
    action_plan = ["复盘账目和客户池", "把收款节点和成本表理清", "等财星或食伤月份再放大"]
    avoid = "不要为了制造机会而重仓、借贷或乱承诺"

    if event in {"财星引动", "财星藏支", "财星压身"}:
        tone = "进财/收款月" if event != "财星压身" else "有财有压月"
        cashflow = "回款与成交"
        money_source = "客户付款、订单成交、销售佣金、副业收入或投资浮盈"
        likely = ["回款、成交、报价、佣金或副业单子更容易出现", "钱的机会会变得更具体，适合把口头机会落到合同和账期"]
        risk_focus = "财星压身" if weak else "偏财旺忌贪快，正财旺忌拖账"
        action_plan = ["主动谈价格和收款", "把合同、发票、交付和账期写清楚", "能先收定金就不要只靠口头承诺"]
        avoid = "不要把未到账的钱当现金花，也不要为了快钱加杠杆"
    elif event in {"食伤生财", "输出蓄财"}:
        tone = "输出变现月"
        cashflow = "产品/内容/技术变现"
        money_source = "作品、产品、流量、销售表达、技术服务或咨询交付"
        likely = ["询盘、报价、上线、推广、成交转化会更活跃", "越能把技能产品化，越容易把流量或表达变成钱"]
        risk_focus = "只忙输出不催款，或伤官太过冲规则"
        action_plan = ["上线产品或服务", "主动报价并设置成交路径", "把交付范围和修改次数写清楚"]
        avoid = "不要免费劳动过多，不要只做声量不做收款闭环"
    elif event in {"比劫夺财", "暗比争财", "比劫助身"}:
        tone = "竞争/分财月" if not weak else "团队助身月"
        cashflow = "竞争、合伙与支出"
        money_source = "团队资源、同业竞争、朋友客户介绍或合伙项目"
        likely = ["同业竞争、价格战、合伙分钱或人情开销会变多", "客户归属、权限、账目和分成容易成为焦点"]
        risk_focus = "被分利、被截胡、借钱担保、冲动消费"
        action_plan = ["先定分成和权限", "重要客户自己跟进", "减少借贷担保和模糊合伙"]
        avoid = "不要把账目交给别人凭感觉处理，也不要在人情压力下让利太多"
    elif event in {"官杀管财", "规则伏财"}:
        tone = "合同/合规月"
        cashflow = "制度性收入"
        money_source = "平台规则、职位责任、资质审批、正式合同或公司制度"
        likely = ["合同、税务、平台规则、领导审批或资质会影响钱", "正规签约、入职晋升、项目立项、结算流程会变重要"]
        risk_focus = "违约条款、税务、资质、审批慢或规则压力"
        action_plan = ["审合同和税务口径", "把流程节点提前排好", "用正规凭证保护收入"]
        avoid = "不要走灰色操作，也不要忽视平台规则和付款条件"
    elif event == "印星护财":
        tone = "资源护财月"
        cashflow = "慢收益与防守"
        money_source = "学习证照、贵人信息、系统工具、供应链或专业背书"
        likely = ["短期未必立刻进账，但适合补资源、修系统、拿信息差", "花钱买工具、课程、资质或人脉的情况会变多"]
        risk_focus = "投入见效慢，容易买资源但不变现"
        action_plan = ["复盘流程和风控", "学习能直接变现的技能", "把资源转成报价、交付或渠道"]
        avoid = "不要只学习不出货，也不要买太多暂时用不上的资源"
    elif event == "财局/财库动":
        tone = "财库/资产月"
        cashflow = "旧账、资产与库存"
        money_source = "应收款、尾款、库存、押金、长期项目、固定资产或沉淀资源"
        likely = ["旧账、尾款、库存、押金或长期项目被引动", "适合处理资产盘点、回款催收和历史遗留账"]
        risk_focus = "合冲并见时先动后稳，开库也可能伴随支出"
        action_plan = ["查应收款和库存", "催尾款或重谈长期项目", "把资产、押金、账期做成清单"]
        avoid = "不要只看表面收入，忽略同时出现的大额成本"

    if any("财库被冲" in signal for signal in signals):
        likely.append("财库被冲，旧账、押金、资产或大额支出会被翻出来")
        risk_focus = f"{risk_focus}；财库被冲时要防开库变破库"
        action_plan.append("单独检查大额支出、资产和应收款")
    if any("三会" in signal or "三合" in signal for signal in signals):
        likely.append("局势成气，相关事件会集中出现，不是零散小事")
    if any("冲" in signal or "刑" in signal or "害" in signal for signal in signals):
        risk_focus = f"{risk_focus}；{signal_text}带来波动"
        avoid = f"{avoid}；冲刑害明显时避免临时加杠杆"

    if strong and event in {"财星引动", "食伤生财", "财局/财库动"}:
        action_plan.append("高确定性收入可以主动推进，但仍要先定退出条件")
    if weak and event in {"财星引动", "财星藏支", "财星压身"}:
        action_plan.append("先控规模，等印比或资源支撑到位再放大")

    strength_percent = max(0, min(100, int(round(50 + score * 3.2))))
    if close - open_value >= 8 and score >= 5:
        stance = "可进攻"
    elif score < -4 or close < open_value - 6:
        stance = "防守控险"
    elif "收款" in tone or event in {"财星引动", "财星藏支", "财局/财库动"}:
        stance = "主收款"
    else:
        stance = "稳推进"

    timing = (
        f"{start_term.get('name', '节气')}后前段看天干{ten_god}，"
        f"中后段看地支藏干{'、'.join(branch_ten_gods[:3]) or '本气'}"
    )
    why = (
        f"{month_pillar}{ten_god}主事，日主{day_profile['strengthLevel']}，"
        f"财星{wealth_profile['wealthElement']}，{signal_text}"
    )
    return {
        "monthTone": tone,
        "cashflow": cashflow,
        "moneySource": money_source,
        "likely": likely[:4],
        "riskFocus": risk_focus,
        "actionPlan": action_plan[:4],
        "avoid": avoid,
        "timing": timing,
        "why": why,
        "triggerLevel": finance_trigger_level(score),
        "strengthPercent": strength_percent,
        "stance": stance,
        "trend": month_trend_label(open_value, close, high, low),
        "windowLabel": month_window_label(start_term, end_term),
        "yearBackdrop": f"{year_point['year']}年{year_point['ganZhi']}，大运{year_point['daYun']}，年主题{year_point.get('event', '财运起伏')}",
    }


def generate_months_for_year(year_point: dict[str, Any], bazi: list[str], wealth_context: dict[str, Any]) -> list[dict[str, Any]]:
    day_stem = bazi[2][0]
    month_pillars = flow_month_pillars(str(year_point["ganZhi"]))
    start_terms = flow_month_start_terms(int(year_point["year"]))
    next_li_chun = solar_terms_for_year(int(year_point["year"]) + 1, cast_timezone())[2]
    end_terms = start_terms[1:] + [{"name": next_li_chun["name"], "time": next_li_chun["time"].isoformat(), "monthName": "寅月"}]
    influences = [month_influence_score(day_stem, bazi, pillar, wealth_context) for pillar in month_pillars]
    raw_scores = [float(item["score"]) for item in influences]
    mean_score = sum(raw_scores) / len(raw_scores)
    centered = [score - mean_score for score in raw_scores]
    max_abs = max(1.0, max(abs(value) for value in centered))

    annual_open = clamp_life_value(float(year_point["open"]))
    annual_close = clamp_life_value(float(year_point["close"]))
    annual_high = clamp_life_value(float(year_point["high"]))
    annual_low = clamp_life_value(float(year_point["low"]))
    trend = annual_close - annual_open
    amplitude = min((annual_high - annual_low) * 0.22, 10)

    closes: list[int] = []
    for index, centered_score in enumerate(centered, start=1):
        base = annual_open + (trend * index / 12)
        closes.append(clamp_life_value(base + (centered_score / max_abs) * amplitude, annual_low, annual_high))
    closes[-1] = annual_close

    rows: list[dict[str, Any]] = []
    previous_close = annual_open
    for index, close in enumerate(closes):
        month_pillar = month_pillars[index]
        influence = influences[index]
        raw_score = float(influence["score"])
        cushion = max(1.0, min(8.0, abs(raw_score - mean_score) * 0.35 + float(influence.get("volatility", 4.0)) * 0.22))
        high = clamp_life_value(max(previous_close, close) + cushion, annual_low, annual_high)
        low = clamp_life_value(min(previous_close, close) - cushion, annual_low, annual_high)
        event_profile = month_event_profile(
            wealth_context,
            month_pillar,
            influence,
            year_point,
            previous_close,
            close,
            high,
            low,
            start_terms[index],
            end_terms[index],
        )
        rows.append(
            {
                "age": year_point["age"],
                "year": year_point["year"],
                "annualIndex": int(year_point["age"]) - 1,
                "annualGanZhi": year_point["ganZhi"],
                "daYun": year_point["daYun"],
                "monthIndex": index + 1,
                "monthName": FLOW_MONTH_NAMES[index],
                "monthLabel": f"{FLOW_MONTH_NAMES[index]} {month_pillar}",
                "ganZhi": month_pillar,
                "startTerm": start_terms[index],
                "tenGod": influence["tenGod"],
                "branchTenGods": influence.get("branchTenGods", []),
                "category": influence["category"],
                "seasonState": influence["seasonState"],
                "growthState": influence["growthState"],
                "signals": influence.get("signals", []),
                "event": influence["event"],
                "opportunity": influence["opportunity"],
                "risk": influence["risk"],
                "advice": influence["advice"],
                "rawScore": round(raw_score, 2),
                "open": previous_close,
                "close": close,
                "high": high,
                "low": low,
                "score": close,
                "reason": f"{event_profile['monthTone']}：{event_profile['likely'][0]}；{event_profile['stance']}。",
                **event_profile,
            }
        )
        previous_close = close

    peak_index = max(range(12), key=lambda idx: raw_scores[idx])
    trough_index = min(range(12), key=lambda idx: raw_scores[idx])
    rows[peak_index]["high"] = annual_high
    rows[trough_index]["low"] = annual_low
    return rows


def aggregate_months_to_year(months: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "open": int(months[0]["open"]),
        "close": int(months[-1]["close"]),
        "high": max(int(month["high"]) for month in months),
        "low": min(int(month["low"]) for month in months),
    }


def generate_month_life_chart(
    chart_data: list[dict[str, Any]],
    bazi: list[str],
    wealth_context: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    month_data: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    all_match = True
    sample_ages = {1, 7, 14, 25, 35, len(chart_data)}
    for point in chart_data:
        months = generate_months_for_year(point, bazi, wealth_context)
        month_data.extend(months)
        aggregate = aggregate_months_to_year(months)
        expected = {key: int(point[key]) for key in ("open", "close", "high", "low")}
        matches = aggregate == expected
        all_match = all_match and matches
        if int(point["age"]) in sample_ages:
            checks.append({"year": point["year"], "age": point["age"], "expected": expected, "aggregate": aggregate, "matches": matches})
    return month_data, {
        "basis": "以日主强弱、用神喜忌、财星状态为底；流月看财星、食伤生财、比劫夺财、官杀管财、印星护财、财库与三会三合刑冲；月K由财运年K边界约束生成",
        "monthsPerYear": 12,
        "yearPreserving": all_match,
        "sampleChecks": checks,
    }


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


def life_wealth_reason(year_influence: dict[str, Any], dayun_influence: dict[str, Any] | None, score: int) -> str:
    dayun_event = dayun_influence["event"] if dayun_influence else "童限蓄势"
    event = year_influence["event"]
    if score >= 82:
        tone = "财机强"
    elif score >= 66:
        tone = "可进取"
    elif score >= 50:
        tone = "宜稳做"
    else:
        tone = "要控险"
    return f"{dayun_event}遇{event}，{tone}：{year_influence['advice']}"


def generate_backend_life_chart(
    birth_year: int,
    bazi: list[str],
    dayun: dict[str, Any],
    wealth_context: dict[str, Any],
) -> list[dict[str, Any]]:
    day_profile = wealth_context["dayMaster"]
    wealth_profile = wealth_context["wealth"]
    natal_base = 52 + float(wealth_profile["wealthFavorability"])
    if "食伤生财" in wealth_profile["structures"]:
        natal_base += 4
    if "比劫分财" in wealth_profile["structures"]:
        natal_base -= 5
    if "财多身弱" in wealth_profile["structures"]:
        natal_base -= 8
    if "身强可任财" in wealth_profile["structures"]:
        natal_base += 5

    raw_years: list[dict[str, Any]] = []
    for age in range(1, 101):
        year = birth_year + age - 1
        gan_zhi = GANZHI[(year - 1984) % 60]
        da_yun = dayun_for_age(age, dayun)
        year_influence = flow_wealth_influence(bazi, wealth_context, gan_zhi)
        dayun_influence = None if da_yun == "童限" else flow_wealth_influence(bazi, wealth_context, da_yun)
        dayun_score = 0.0 if dayun_influence is None else float(dayun_influence["score"])
        flow_score = float(year_influence["score"])
        if age <= 16:
            age_curve = -12
        elif age <= 28:
            age_curve = 1
        elif age <= 45:
            age_curve = 9
        elif age <= 60:
            age_curve = 7
        elif age <= 75:
            age_curve = 1
        else:
            age_curve = -8
        year_event = str(year_influence["event"])
        event_tilt = {
            "财星引动": 8.0,
            "财星藏支": 4.5,
            "食伤生财": 7.0,
            "输出蓄财": 5.0,
            "财局/财库动": 10.0,
            "官杀管财": -4.5,
            "规则伏财": -2.5,
            "比劫夺财": -9.0,
            "暗比争财": -6.5,
            "财星压身": -7.0,
            "印星护财": 1.5,
            "比劫助身": 2.5,
        }.get(year_event, 0.0)
        signal_count = len(year_influence.get("signals", []))
        relation_shock = min(10.0, signal_count * 1.65)
        if any("冲" in signal or "刑" in signal or "害" in signal for signal in year_influence.get("signals", [])):
            relation_shock *= -1.0
        decade_wave = math.sin((age + GANZHI.index(bazi[2])) / 4.1) * 6.0
        long_wave = math.cos((age + STEMS.index(bazi[2][0]) * 2) / 9.5) * 5.0
        raw_close = natal_base + (dayun_score * 2.45) + (flow_score * 2.05) + age_curve + decade_wave + long_wave + event_tilt + relation_shock
        raw_volatility = (
            7.0
            + abs(dayun_score) * 0.48
            + abs(flow_score) * 0.9
            + float(year_influence.get("volatility", 4.0)) * 0.72
            + (0.0 if dayun_influence is None else float(dayun_influence.get("volatility", 4.0)) * 0.36)
            + abs(event_tilt) * 0.28
            + abs(relation_shock) * 0.34
        )
        raw_years.append(
            {
                "age": age,
                "year": year,
                "ganZhi": gan_zhi,
                "daYun": da_yun,
                "yearInfluence": year_influence,
                "dayunInfluence": dayun_influence,
                "rawClose": raw_close,
                "rawVolatility": raw_volatility,
            }
        )

    raw_values = [float(item["rawClose"]) for item in raw_years]
    raw_mean = sum(raw_values) / len(raw_values)
    raw_range = max(raw_values) - min(raw_values)
    target_mid = max(36.0, min(66.0, 50.0 + ((natal_base - 52.0) * 0.68)))
    target_spread = min(78.0, max(48.0, raw_range * 1.35))

    closes: list[int] = []
    for item in raw_years:
        if raw_range < 0.01:
            normalized = math.sin(float(item["age"]) / 4.0) * (target_spread * 0.22)
        else:
            normalized = ((float(item["rawClose"]) - raw_mean) / raw_range) * target_spread
        closes.append(clamp_life_value(target_mid + normalized, 4, 96))

    close_min = min(closes)
    close_max = max(closes)
    if close_max - close_min < 36:
        close_mid = sum(closes) / len(closes)
        factor = 36 / max(1, close_max - close_min)
        closes = [clamp_life_value(close_mid + ((close - close_mid) * factor), 4, 96) for close in closes]

    first_momentum = closes[1] - closes[0] if len(closes) > 1 else 0
    previous_close = clamp_life_value(closes[0] - (first_momentum * 0.45), 4, 96)
    points: list[dict[str, Any]] = []
    for item, close in zip(raw_years, closes):
        age = int(item["age"])
        year = int(item["year"])
        gan_zhi = str(item["ganZhi"])
        da_yun = str(item["daYun"])
        year_influence = item["yearInfluence"]
        dayun_influence = item["dayunInfluence"]
        open_value = previous_close
        volatility = min(34.0, float(item["rawVolatility"]) + abs(close - open_value) * 0.45)
        upper_wick = volatility * (0.58 + ((age % 5) * 0.08))
        lower_wick = volatility * (0.52 + (((age + 2) % 5) * 0.07))
        high = clamp_life_value(max(open_value, close) + upper_wick)
        low = clamp_life_value(min(open_value, close) - lower_wick)
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
                "event": year_influence["event"],
                "opportunity": year_influence["opportunity"],
                "risk": year_influence["risk"],
                "advice": year_influence["advice"],
                "reason": life_wealth_reason(year_influence, dayun_influence, close),
            }
        )
        previous_close = close
    return points


def fallback_life_analysis(
    bazi: list[str],
    chart_data: list[dict[str, Any]],
    wealth_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    average = round(sum(float(point["score"]) for point in chart_data) / len(chart_data), 1)
    peak = max(chart_data, key=lambda point: float(point["score"]))
    low = min(chart_data, key=lambda point: float(point["score"]))
    score_10 = max(1, min(10, round(average / 10, 1)))
    if wealth_context is None:
        wealth_context = build_wealth_context(bazi)
    wealth_profile = wealth_context["wealth"]
    day_profile = wealth_context["dayMaster"]
    wealth_text = (
        f"财运结构为{'、'.join(wealth_profile['structures'])}。"
        f"日主{day_profile['strengthLevel']}，{day_profile['strategy']}"
        f"财星五行为{wealth_profile['wealthElement']}，财库在{wealth_profile['wealthStorageBranch']}，"
        f"高分年份宜主动收款、成交和变现，低分年份重点防比劫分财、财多压身或合同成本。"
    )
    return {
        "bazi": bazi,
        "summary": f"后端已完成四柱、大运和财运结构诊断。财运K线均值约{average}，峰值在{peak['year']}年，低谷在{low['year']}年。",
        "summaryScore": score_10,
        "personality": "命局节奏以日主为核心，宜把稳定积累和阶段性突破结合。",
        "personalityScore": score_10,
        "industry": "适合选择能持续沉淀技能、资源和信用的方向，逢高分流年加速扩张。",
        "industryScore": score_10,
        "fengShui": "居住与办公宜保持采光、通风和动线清晰，重要年份少频繁搬动。",
        "fengShuiScore": score_10,
        "wealth": wealth_text,
        "wealthScore": score_10,
        "marriage": "关系经营宜避开事业压力峰值时的冲动决策，多以沟通稳定节奏。",
        "marriageScore": score_10,
        "health": "低分流年注意睡眠、脾胃、压力管理和长期运动习惯。",
        "healthScore": score_10,
        "family": "六亲互动宜以边界清晰为主，运势上行期更适合主动修复关系。",
        "familyScore": score_10,
        "crypto": "高波动交易只宜放在财星或食伤生财且K线高分阶段；比劫夺财、财星压身、官杀管财月份避免杠杆。",
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
    chunk_retries = max(1, int(os.getenv("LIFE_KLINE_CHUNK_RETRIES", "2")))

    def fetch_chunk(start_age: int, end_age: int) -> tuple[int, list[dict[str, Any]]]:
        base_chunk_prompt = f"""
{context_prompt}

【本批次只生成以下年龄范围】
{life_chart_rows_prompt(birth_year, dayun, start_age, end_age)}

请只输出上述 {start_age}-{end_age} 岁的 chartPoints JSON。
不要输出其他年龄，不要输出报告字段。
必须是合法 JSON：对象之间必须有英文逗号，字符串内不要直接换行。
""".strip()
        last_error: Exception | None = None
        for attempt in range(1, chunk_retries + 1):
            retry_line = "" if attempt == 1 else f"\n上一次第 {start_age}-{end_age} 岁 JSON 无效，请重新输出合法 JSON。"
            try:
                data = call_life_model(
                    [
                        {"role": "system", "content": LIFE_KLINE_CHART_CHUNK_INSTRUCTION},
                        {"role": "user", "content": f"{base_chunk_prompt}{retry_line}"},
                    ],
                    max_tokens=chunk_tokens,
                    timeout=chunk_timeout,
                    temperature=0.65 if attempt == 1 else 0.35,
                )
                return start_age, normalize_chart_points_range(data.get("chartPoints"), birth_year, dayun, start_age, end_age)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"{start_age}-{end_age} 岁模型K线生成失败: {last_error}")

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
    wealth_context = build_wealth_context(bazi)
    local = birth_time.astimezone(cast_timezone())
    backend_chart_data = generate_backend_life_chart(local.year, bazi, dayun, wealth_context)
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

    day_master = wealth_context["dayMaster"]
    pattern_profile = wealth_context["pattern"]
    wealth_profile = wealth_context["wealth"]
    ten_god_grid_text = "\n".join(
        (
            f"{row['label']}：{row['pillar']}，天干{row['stemTenGod']}，"
            f"地支本气{row['branchMainTenGod']}，十二宫{row['growthState']}，月令季态{row['seasonState']}"
        )
        for row in wealth_context["tenGods"]
    )
    relation_text = "；".join(wealth_context["relations"][:8]) if wealth_context["relations"] else "原局少明显刑冲合会"
    principle_text = "\n".join(f"- {note}" for note in wealth_context["principles"])

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

【后端已诊断命局总纲】
日主：{day_master["dayStem"]}{day_master["dayElement"]}，{day_master["strengthLevel"]}，强弱分 {day_master["strengthScore"]}
得令：月令{day_master["monthBranch"]}令日主{day_master["monthState"]}
扶抑策略：{day_master["strategy"]}
喜用方向：{"、".join(day_master["usefulGroups"])}
忌偏重：{"、".join(day_master["avoidGroups"])}
月令格局：{pattern_profile["patternName"]}（{pattern_profile["source"]}，{pattern_profile["quality"]}）
十神盘面：
{ten_god_grid_text}
原局刑冲合会：{relation_text}
命理原则：
{principle_text}

【后端已推算大运参数】
大运方向：{dayun["direction"]}
起运年龄（虚岁）：{dayun["startAge"]}
第一步大运：{dayun["firstDaYun"]}
大运序列：{"、".join(dayun["sequence"])}
参考节气：{dayun["referenceJie"]["name"]}，相差约 {dayun["referenceJie"]["deltaDays"]} 天

【后端已诊断财运结构】
财星五行：{wealth_profile["wealthElement"]}，财库：{wealth_profile["wealthStorageBranch"]}
财运结构：{"、".join(wealth_profile["structures"])}
财星显隐：透干 {wealth_profile["visibleWealth"]}，藏支 {wealth_profile["hiddenWealth"]}，综合财势 {wealth_profile["wealthPower"]}
食伤/比劫/官杀/印星：{wealth_profile["outputPower"]}/{wealth_profile["peerPower"]}/{wealth_profile["officerPower"]}/{wealth_profile["resourcePower"]}
取财状态：{wealth_profile["wealthReadiness"]}

请严格使用上面的四柱、大运方向、起运年龄、第一步大运和大运序列。
chartPoints 的 year 从 {local.year} 年开始，每增长 1 岁 year 增加 1；ganZhi 必须对应该流年干支。
报告只能说结构趋势、风险和建议；不要输出绝对命定、恐吓式断语，也不要使用带性别偏见的旧式断语。
""".strip()
    allow_model_charts = truthy(os.getenv("LIFE_KLINE_MODEL_CHARTS"))
    model_info = {
        "used": False,
        "error": None,
        "chartSource": "backend_deterministic",
        "method": "backend_formula",
        "deterministic": True,
        "engineVersion": LIFE_KLINE_ENGINE_VERSION,
    }
    if allow_model_charts:
        try:
            chart_data = generate_model_chart_chunks(context_prompt, local.year, dayun)
            model_info.update({"used": True, "chartSource": "model", "method": "chunked", "deterministic": False})
        except Exception as exc:
            chart_data = backend_chart_data
            model_info.update({"error": str(exc)[:500], "chartSource": "backend_deterministic", "method": "backend_formula", "deterministic": True})

    try:
        analysis = generate_model_analysis(context_prompt, bazi, chart_data)
        model_info["analysisSource"] = "model"
    except Exception as exc:
        analysis = fallback_life_analysis(bazi, chart_data, wealth_context)
        model_info["analysisSource"] = "backend_fallback"
        model_info["analysisError"] = str(exc)[:500]
    analysis = apply_deterministic_life_analysis_fields(analysis, bazi, chart_data)
    month_chart_data, month_kline = generate_month_life_chart(chart_data, bazi, wealth_context)
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
        "baziContext": wealth_context,
        "wealthContext": wealth_context,
        "chartData": chart_data,
        "monthChartData": month_chart_data,
        "monthKline": month_kline,
        "engineVersion": LIFE_KLINE_ENGINE_VERSION,
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
            self.json_response({"ok": True, "service": "liuyao_quantum_web", "engineVersion": LIFE_KLINE_ENGINE_VERSION})
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
