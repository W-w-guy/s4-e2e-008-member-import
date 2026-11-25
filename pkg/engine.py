# -*- coding: utf-8 -*-
"""历史会员批量导入：数据工厂 + 导入引擎 + 完整度口径（全部虚构数据）。

数据工厂（工单原文【本单范围】前置数据）
--------------------------------------
100 家企业、260 名联系人；故意构造：
  - 5 行信用代码错误   -> 导入失败
  - 3 行重复企业       -> 导入失败
  - 6 行联系人缺手机号 -> 导入成功，但计入完整度扣分
导入成功数 = 100 - 5 - 3 = 92；错误报告 = 5 + 3 = 8 行。

完整度口径（原文写「6 项的非空比例」，这里把口径写死以便复核）
--------------------------------------------------------------
记录单位 = 企业（92 家导入成功的）。6 项：
  企业名称 / 信用代码 / 产业方向 / 会籍档位  -- 来自企业表，导入成功即有值
  联系人姓名 / 联系人手机号                  -- 取该企业的主联系人
                                               （联系人表里该信用代码的第一条记录）
主联系人口径是原文未写死的地方，这里明示：一家企业有多名联系人时，
完整度只看主联系人，避免同一家企业的 4 个字段被算 3 遍。
"""

import re

# ---------------------------------------------------------------- 规格常量
CITIES = ["杭州", "苏州", "宁波", "上海", "南京", "无锡", "合肥", "武汉", "长沙", "成都"]
BRANDS = ["云栖", "明远", "港盛", "启元", "启明", "严州", "和昌", "锦泓", "青柚", "华筑"]
INDUSTRIES = ["数字医疗", "智能制造", "供应链物流", "低碳材料", "产业基金",
              "文旅运营", "跨境电商", "工业软件"]
TIERS = ["普通", "银卡", "金卡", "铂金"]
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴"]
GIVEN = ["建国", "雅琴", "志远", "晓岚", "文博", "海峰", "丽娟", "鹏飞", "静怡", "昊天"]
TITLES = ["总经理", "运营总监", "财务负责人", "招商经理", "办公室主任"]

N_COMPANIES = 100
N_CONTACTS = 260
# 联系人分布：前 60 家各 3 人、后 40 家各 2 人（60*3 + 40*2 = 260）
CONTACTS_3 = 60

# 失败行（企业序号，1 起）；Excel 行号 = 序号 + 1（第 1 行是表头）
BAD_CREDIT_ROWS = [11, 23, 37, 58, 74]
DUP_ROWS = [19, 45, 83]
DUP_OF = {19: 5, 45: 12, 83: 30}
# 主联系人缺手机号的企业（都必须是导入成功的）
NO_PHONE_ROWS = [2, 5, 9, 14, 21, 33]

EXPECT_OK = N_COMPANIES - len(BAD_CREDIT_ROWS) - len(DUP_ROWS)   # 92
EXPECT_ERROR_ROWS = len(BAD_CREDIT_ROWS) + len(DUP_ROWS)         # 8
EXPECT_ERROR_LINES = sorted([r + 1 for r in BAD_CREDIT_ROWS] + [r + 1 for r in DUP_ROWS])

RE_CREDIT = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{18}$")
KEY_FIELDS = ["企业名称", "信用代码", "产业方向", "会籍档位", "联系人姓名", "联系人手机号"]
RE_PHONE = re.compile(r"^1[3-9]\d{9}$")

# 轮询参数（工单原文：最多 60 次、间隔 2 秒）
POLL_MAX = 60
POLL_INTERVAL = 2.0


def credit_code(i):
    """18 位信用代码（虚构）。合法字符集，校验位用 i%97 造。"""
    return "91330100MA2%05d%02d" % (i, i % 97)


def company_name(i):
    return CITIES[(i - 1) % 10] + BRANDS[((i - 1) // 10) % 10] + INDUSTRIES[(i - 1) % 8] + "有限公司"


def build_companies():
    """100 家企业（字典列表）。故意构造 5 行信用代码错误 + 3 行重复企业。"""
    out = []
    for i in range(1, N_COMPANIES + 1):
        code = credit_code(i)
        if i in BAD_CREDIT_ROWS:
            code = code[:-1]          # 少一位，17 位 -> 校验不通过
        if i in DUP_ROWS:
            code = credit_code(DUP_OF[i])   # 与前面某家完全重复
        out.append({
            "row": i + 1,
            "seq": i,
            "企业名称": company_name(i),
            "信用代码": code,
            "产业方向": INDUSTRIES[(i - 1) % 8],
            "会籍档位": TIERS[(i - 1) % 4],
            "所在城市": CITIES[(i - 1) % 10],
            "成立年份": 2005 + (i % 18),
        })
    return out


def contact_counts():
    return [(3 if i <= CONTACTS_3 else 2) for i in range(1, N_COMPANIES + 1)]


def build_contacts(companies):
    """260 名联系人。每家第一个是主联系人；NO_PHONE_ROWS 的主联系人手机号留空。"""
    counts = contact_counts()
    out = []
    for idx, co in enumerate(companies):
        seq = co["seq"]
        for k in range(counts[idx]):
            name = SURNAMES[(seq + k) % 10] + GIVEN[(seq * 3 + k) % 10]
            # 手机号一律用掩码形式：既保证「非空」语义（完整度只看非空），
            # 又不携带可拨打的真实号码，可通过自身 PII 扫描（scanned 命中 0）。
            phone = "138****%04d" % ((seq * 100 + k) % 10000)
            if k == 0 and seq in NO_PHONE_ROWS:
                phone = ""            # 主联系人缺手机号
            out.append({
                "信用代码": co["信用代码"],
                "企业名称": co["企业名称"],
                "姓名": name,
                "手机号": phone,
                "职务": TITLES[(seq + k) % 5],
                "是否主联系人": "是" if k == 0 else "否",
            })
    assert len(out) == N_CONTACTS, len(out)
    return out


def build_source():
    companies = build_companies()
    contacts = build_contacts(companies)
    return {"companies": companies, "contacts": contacts}


# ---------------------------------------------------------------- 校验规则
def validate_company(row, seen_codes):
    """返回错误列表（空=通过）。seen_codes 是此前已成功录入的信用代码集合。"""
    errs = []
    code = (row.get("信用代码") or "").strip()
    if not code:
        errs.append(("信用代码为空", code))
    elif not RE_CREDIT.match(code):
        errs.append(("信用代码格式不合法（需 18 位合法字符，实际 %d 位）" % len(code), code))
    elif code in seen_codes:
        errs.append(("企业重复（信用代码 %s 已在前序行导入）" % code, code))
    for f in ("企业名称", "产业方向", "会籍档位"):
        if not (row.get(f) or "").strip():
            errs.append(("%s 为空" % f, ""))
    return errs


def primary_contact(contacts):
    """每家企业的主联系人：该信用代码下标记为「是」的第一条（没有标记则取第一条）。"""
    out = {}
    for c in contacts:
        code = c["信用代码"]
        if code not in out:
            out[code] = c
        elif c.get("是否主联系人") == "是" and out[code].get("是否主联系人") != "是":
            out[code] = c
    return out


def completeness(ok_companies, contacts):
    """6 项非空比例。分子分母都由调用方传入的实数据算出，不读任何预置常量。"""
    prim = primary_contact(contacts)
    total = 0
    filled = 0
    per_field = {f: [0, 0] for f in KEY_FIELDS}   # [非空数, 总数]
    for co in ok_companies:
        pc = prim.get(co["信用代码"]) or {}
        vals = {
            "企业名称": co.get("企业名称"),
            "信用代码": co.get("信用代码"),
            "产业方向": co.get("产业方向"),
            "会籍档位": co.get("会籍档位"),
            "联系人姓名": pc.get("姓名"),
            "联系人手机号": pc.get("手机号"),
        }
        for f in KEY_FIELDS:
            v = vals.get(f)
            per_field[f][1] += 1
            total += 1
            if isinstance(v, str) and v.strip():
                per_field[f][0] += 1
                filled += 1
    return {"ratio": round(filled / total, 12), "filled": filled, "total": total,
            "records": len(ok_companies),
            "per_field": {f: {"filled": v[0], "total": v[1]} for f, v in per_field.items()}}


# ---------------------------------------------------------------- rule_kit 契约
# CASES 是示例集入口名；本单的「示例」= 100 家企业源记录（逐行给出是否应导入成功）
CASES = build_companies()


def case_id(c):
    return str(c["row"])


def cats_of(c):
    return c["cats"]


def row_of(c):
    return {
        "row": c["row"],
        "企业名称": c["企业名称"],
        "信用代码": c["信用代码"],
        "产业方向": c["产业方向"],
        "会籍档位": c["会籍档位"],
        "所在城市": c["所在城市"],
        "成立年份": c["成立年份"],
        "期望结果": ("import_error" if c["seq"] in BAD_CREDIT_ROWS + DUP_ROWS
                     else "import_ok"),
    }


# 覆盖类：每家企业归到 1 类（外加 6 家缺手机号的单列，用 C07）
def _cats_for(seq):
    if seq in BAD_CREDIT_ROWS:
        return ["C01"]
    if seq in DUP_ROWS:
        return ["C02"]
    if seq in NO_PHONE_ROWS:
        return ["C03", "C07"]
    if seq <= CONTACTS_3:
        return ["C04"]
    return ["C05"]


for _c in CASES:
    _c["cats"] = _cats_for(_c["seq"])

CATS = [
    ("C01", "信用代码不合法，导入失败"),
    ("C02", "企业重复，导入失败"),
    ("C03", "主联系人缺手机号（导入成功但扣完整度）"),
    ("C04", "3 名联系人的企业（正常导入）"),
    ("C05", "2 名联系人的企业（正常导入）"),
    ("C06", "审计字段齐全（行号 / 城市 / 成立年份）"),
    ("C07", "缺手机号被计入完整度而不算错误"),
]
