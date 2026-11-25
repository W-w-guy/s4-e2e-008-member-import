
# -*- coding: utf-8 -*-
"""独立完整度计算脚本（AC2 的「另一条路径」）。

刻意与导入引擎**不共享实现**：
  - 它自己用 openpyxl 读原始 Excel，不碰 ImportEngine 的任何内部结果；
  - 它自己重新判定哪些企业算「导入成功」（信用代码 18 位合法 + 首次出现），
    而不是拿引擎给的 ok_companies 列表；
  - 它自己按信用代码把主联系人挑出来（Excel 里第一条），再算 6 项非空比例。

只有「规则本身」（18 位合法字符、重复判定、主联系人取第一条）与引擎相同，
这是契约而不是共享代码——所以两边算出来的数应当严格相等，差为 0。
"""
import re

CITIES_CACHE = {}
RE_CREDIT = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{18}$")
KEY_FIELDS = ["企业名称", "信用代码", "产业方向", "会籍档位", "联系人姓名", "联系人手机号"]


def _s(v):
    return "" if v is None else str(v).strip()


def compute(xlsx_path):
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path, data_only=True)
    ws = wb["企业"]
    rows = list(ws.iter_rows(values_only=True))
    head = list(rows[0])
    comp_rows = [dict(zip(head, r)) for r in rows[1:]]

    ws2 = wb["联系人"]
    rows2 = list(ws2.iter_rows(values_only=True))
    head2 = list(rows2[0])
    cont_rows = [dict(zip(head2, r)) for r in rows2[1:]]

    # 独立判定导入成功的企业
    seen = set()
    ok = []
    bad = []
    for r in comp_rows:
        code = _s(r.get("信用代码"))
        if not RE_CREDIT.match(code):
            bad.append({"row": r.get("行号"), "reason": "信用代码不合法"})
            continue
        if code in seen:
            bad.append({"row": r.get("行号"), "reason": "企业重复"})
            continue
        seen.add(code)
        ok.append(r)

    # 独立挑主联系人：每个信用代码下出现的第一条
    prim = {}
    for c in cont_rows:
        code = _s(c.get("信用代码"))
        if code and code not in prim:
            prim[code] = c

    filled = 0
    total = 0
    per_field = {}
    for f in KEY_FIELDS:
        per_field[f] = [0, 0]
    for r in ok:
        code = _s(r.get("信用代码"))
        pc = prim.get(code) or {}
        vals = {
            "企业名称": _s(r.get("企业名称")),
            "信用代码": code,
            "产业方向": _s(r.get("产业方向")),
            "会籍档位": _s(r.get("会籍档位")),
            "联系人姓名": _s(pc.get("姓名")),
            "联系人手机号": _s(pc.get("手机号")),
        }
        for f in KEY_FIELDS:
            total += 1
            per_field[f][1] += 1
            if vals[f]:
                filled += 1
                per_field[f][0] += 1
    return {"ratio": round(filled / total, 12), "filled": filled, "total": total,
            "records": len(ok), "bad": bad,
            "per_field": {f: {"filled": v[0], "total": v[1]} for f, v in per_field.items()},
            "source": "独立脚本（直接读 xlsx，不使用导入引擎的任何中间结果）"}


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(compute(sys.argv[1]), ensure_ascii=False, indent=1))
