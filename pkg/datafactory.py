
# -*- coding: utf-8 -*-
"""数据工厂：把 engine.build_source() 写成 Excel（两个 sheet：企业 / 联系人）。

确定性：openpyxl 写出的 xlsx 是 zip，条目带本地时间与 create_system，
字节级不可比。所以本包**不比对 xlsx 字节**，而是比对单元格值
（见 docs/ 下的 dump 与 verify 的「xlsx 单元格值」断言）。
"""
import os

from openpyxl import Workbook

import engine as E

COMPANY_HEADER = ["行号", "企业名称", "信用代码", "产业方向", "会籍档位", "所在城市", "成立年份"]
CONTACT_HEADER = ["信用代码", "企业名称", "姓名", "手机号", "职务", "是否主联系人"]


def build_workbook(source=None):
    src = source or E.build_source()
    wb = Workbook()
    ws = wb.active
    ws.title = "企业"
    ws.append(COMPANY_HEADER)
    for c in src["companies"]:
        ws.append([c["row"], c["企业名称"], c["信用代码"], c["产业方向"],
                   c["会籍档位"], c["所在城市"], c["成立年份"]])
    ws2 = wb.create_sheet("联系人")
    ws2.append(CONTACT_HEADER)
    for c in src["contacts"]:
        ws2.append([c["信用代码"], c["企业名称"], c["姓名"], c["手机号"],
                    c["职务"], c["是否主联系人"]])
    return wb


def write_xlsx(path):
    wb = build_workbook()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)
    return path


def read_back(path):
    """独立读回 Excel（供独立完整度脚本与抽样比对使用，不 import import_engine）。"""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    ws = wb["企业"]
    rows = list(ws.iter_rows(values_only=True))
    head = list(rows[0])
    companies = [dict(zip(head, r)) for r in rows[1:]]
    ws2 = wb["联系人"]
    rows2 = list(ws2.iter_rows(values_only=True))
    head2 = list(rows2[0])
    contacts = [dict(zip(head2, r)) for r in rows2[1:]]
    return {"companies": companies, "contacts": contacts, "company_header": head,
            "contact_header": head2}
