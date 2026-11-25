
# -*- coding: utf-8 -*-
"""本单 32 条 AC 断言。期望值一律硬编码在本文件里，不与被测对象互推。"""
import csv
import json
import os
import re

import datafactory
import engine as E
import import_engine as IE
import independent as IND
import scenarios as SC
from kitlib.checks import check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

# ---------------- 硬编码期望 ----------------
EXPECT_OK = 92
EXPECT_ERROR_ROWS = 8
EXPECT_TOTAL_ROWS = 100
EXPECT_ERROR_LINES = [12, 20, 24, 38, 46, 59, 75, 84]       # Excel 行号
EXPECT_BAD_CREDIT = [12, 24, 38, 59, 75]
EXPECT_DUP = [20, 46, 84]
EXPECT_COMP_FILLED = 546
EXPECT_COMP_TOTAL = 552
EXPECT_COMP_RATIO = 0.989130434783
EXPECT_NOPHONE = 6
EXPECT_POLL_MAX = 60
EXPECT_POLL_INTERVAL = 2.0
EXPECT_N_CONTACTS = 260
EXPECT_SAMPLE = 10
EXPECT_SAMPLE_FIELDS = 6


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _csv(rel):
    return list(csv.DictReader(open(os.path.join(ROOT, rel), encoding="utf-8")))


def main():
    # ================= AC1：成功 92、错误报告 8 行 =================
    s01 = SC.s01_import()
    f1 = s01["final"]
    check("V01 AC1 源数据规模为 100 家企业（Excel 数据行数）",
          f1["total_rows"] == EXPECT_TOTAL_ROWS,
          "实测 %s 行" % f1["total_rows"])

    check("V02 AC1 导入成功数恰为 92",
          f1["ok_count"] == EXPECT_OK,
          "实测 %s（期望 %d）" % (f1["ok_count"], EXPECT_OK))

    check("V03 AC1 错误报告恰为 8 行",
          f1["error_count"] == EXPECT_ERROR_ROWS,
          "实测 %s（期望 %d）" % (f1["error_count"], EXPECT_ERROR_ROWS))

    check("V04 AC1 8 行错误报告的行号逐条等于硬编码清单 %s" % EXPECT_ERROR_LINES,
          f1["error_row_numbers"] == EXPECT_ERROR_LINES,
          "实测 %s" % (f1["error_row_numbers"],))

    check("V05 AC1 8 条错误里 5 条是信用代码不合法、3 条是企业重复",
          sum(1 for e in f1["error_lines"] if "信用代码格式不合法" in e) == 5
          and sum(1 for e in f1["error_lines"] if "企业重复" in e) == 3,
          "信用代码 %d 条 / 重复 %d 条"
          % (sum(1 for e in f1["error_lines"] if "信用代码格式不合法" in e),
             sum(1 for e in f1["error_lines"] if "企业重复" in e)))

    check("V06 AC1 每一行错误都同时写了行号与原因（不是只有行号或只有原因）",
          f1["every_line_has_row_and_reason"] is True
          and all(re.match(r"^第 \d+ 行 \| ", l) for l in f1["error_lines"]),
          "示例：%s" % (f1["error_lines"][0] if f1["error_lines"] else "无"))

    check("V07 AC1 落盘的错误报告文档含全部 8 行且行号与 CSV/脚本一致",
          all(("第 %d 行" % r) in _read("docs/error_report.md") for r in EXPECT_ERROR_LINES),
          "文档内出现行号 %s"
          % [r for r in EXPECT_ERROR_LINES if ("第 %d 行" % r) in _read("docs/error_report.md")])

    s1b = SC.s01b_contacts_imported()
    check("V08 AC1 缺手机号的 6 行联系人导入成功、且未被计入错误报告",
          s1b["final"]["nophone_total"] == EXPECT_NOPHONE
          and s1b["final"]["nophone_in_ok_companies"] == EXPECT_NOPHONE
          and s1b["final"]["in_error_report"] == 0,
          "缺手机 %d 行 / 在成功企业内 %d 行 / 错误报告里 %d 条"
          % (s1b["final"]["nophone_total"], s1b["final"]["nophone_in_ok_companies"],
             s1b["final"]["in_error_report"]))

    check("V09 联系人表规模为 260 行",
          len(E.build_source()["contacts"]) == EXPECT_N_CONTACTS,
          "实测 %d" % len(E.build_source()["contacts"]))

    # ================= AC2：完整度之差为 0 =================
    s02 = SC.s02_completeness()
    f2 = s02["final"]
    check("V10 AC2 系统报告的完整度计数为 546/552（硬编码期望）",
          f2["system_filled"] == EXPECT_COMP_FILLED and f2["system_total"] == EXPECT_COMP_TOTAL,
          "实测 %s/%s" % (f2["system_filled"], f2["system_total"]))

    check("V11 AC2 系统报告的比例等于 %.12f" % EXPECT_COMP_RATIO,
          f2["system_ratio"] == EXPECT_COMP_RATIO,
          "实测 %s" % (f2["system_ratio"],))

    check("V12 AC2 独立脚本算出的比例同为 %.12f（两条路径各自得出同一个数）" % EXPECT_COMP_RATIO,
          f2["independent_ratio"] == EXPECT_COMP_RATIO
          and f2["ind_filled"] == EXPECT_COMP_FILLED and f2["ind_total"] == EXPECT_COMP_TOTAL,
          "独立脚本 %s（%s/%s）" % (f2["independent_ratio"], f2["ind_filled"], f2["ind_total"]))

    check("V13 AC2 系统报告与独立脚本之差恰为 0",
          f2["diff"] == 0,
          "diff=%s（容差 0，不允许近似）" % (f2["diff"],))

    check("V14 AC2 两条路径都没有抛异常（差为 0 不是因为两边都空）",
          f2["errs"] == ["", ""] and f2["system_filled"] is not None,
          "errs=%s" % (f2["errs"],))

    pf = f2["per_field"] or {}
    check("V15 AC2 6 项里只有「联系人手机号」非满（92 中 86），其余 5 项均满 92",
          pf.get("联系人手机号", {}).get("filled") == 86
          and all(pf.get(f, {}).get("filled") == 92
                  for f in ("企业名称", "信用代码", "产业方向", "会籍档位", "联系人姓名")),
          "；".join("%s=%s/%s" % (k, v["filled"], v["total"]) for k, v in pf.items()))

    # 反证：完整度不是恒为某个值——把 6 个手机号补上后比例必须变
    src2 = E.build_source()
    filled_back = 0
    for c in src2["contacts"]:
        if not (c.get("手机号") or "").strip():
            c["手机号"] = "138****9999"
            filled_back += 1
    eng2 = IE.ImportEngine(src2)
    j2 = eng2.submit()
    r2 = eng2.report(j2.job_id)
    check("V16 反证：补齐 6 个手机号后完整度升到 1.0（说明该指标真会随数据变化）",
          filled_back == 6 and r2["completeness"]["ratio"] == 1.0,
          "补了 %d 个；比例 %s" % (filled_back, r2["completeness"]["ratio"]))

    # ================= AC3：轮询上限后明确失败 =================
    s03 = SC.s03_timeout()
    f3 = s03["final"]
    check("V17 AC3 慢任务会抛异常而不是静默返回未完成状态",
          f3["raised"] is True and f3["error_type"] == "ImportTimeout",
          "raised=%s type=%s" % (f3["raised"], f3["error_type"]))

    check("V18 AC3 轮询次数恰为 60 次（硬编码上限，不多不少）",
          f3["poll_count"] == EXPECT_POLL_MAX,
          "实测 %s 次（期望 %d）" % (f3["poll_count"], EXPECT_POLL_MAX))

    check("V19 AC3 每次轮询间隔为 2 秒，sleep 调用 59 次（最后一次不等待）",
          f3["sleep_calls"] == EXPECT_POLL_MAX - 1 and f3["sleep_interval"] == EXPECT_POLL_INTERVAL,
          "sleep %s 次 / 间隔 %s" % (f3["sleep_calls"], f3["sleep_interval"]))

    check("V20 AC3 超时消息里写明次数、间隔、合计秒数与最后状态（明确信息）",
          all(x in f3["message"] for x in ("60 次", "2.0 秒", "120 秒", "running", "超时失败")),
          "消息：%s" % f3["message"][:120])

    s3b = SC.s03b_fast_success()
    check("V21 反证：正常任务 1 次轮询即成功、不 sleep、不误判超时",
          s3b["final"]["ok"] is True and s3b["final"]["status"] == "succeeded"
          and s3b["final"]["sleep_calls"] == 0,
          "status=%s sleep=%s" % (s3b["final"]["status"], s3b["final"]["sleep_calls"]))

    # ================= AC4：10 家抽样逐字段比对 =================
    s04 = SC.s04_sample10()
    f4 = s04["final"]
    check("V22 AC4 抽样数量恰为 10 家",
          f4["n_sampled"] == EXPECT_SAMPLE,
          "实测 %s" % f4["n_sampled"])

    check("V23 AC4 每家比对 6 个字段，合计 60 项",
          f4["total_fields_compared"] == EXPECT_SAMPLE * EXPECT_SAMPLE_FIELDS,
          "实测 %s 项" % f4["total_fields_compared"])

    check("V24 AC4 10 家逐字段全部一致（0 处差异）",
          f4["all_match"] is True
          and all(not r["diffs"] for r in f4["rows"]),
          "有差异的行：%s" % [r for r in f4["rows"] if r["diffs"]] or "无")

    check("V25 AC4 抽样来源是导入成功的 92 家（不含错误行）",
          all(r["row"] not in EXPECT_ERROR_LINES for r in f4["rows"]),
          "抽到的行号 %s" % [r["row"] for r in f4["rows"]])

    # 反证：抽样比对真的能发现差异（改坏一个字段必须报差异）
    back = datafactory.read_back(os.path.join(ROOT, "data/source_members.xlsx"))
    src_rows = {int(r["行号"]): dict(r) for r in back["companies"]}
    engx = IE.ImportEngine(E.build_source())
    jx = engx.submit()
    okx = engx.report(jx.job_id)["ok_companies"]
    victim = okx[0]
    tampered = dict(src_rows[int(victim["row"])])
    tampered["产业方向"] = "被改坏的产业方向"
    diffs = [f for f in ("企业名称", "信用代码", "产业方向", "会籍档位", "所在城市", "成立年份")
             if str(victim.get(f)) != str(tampered.get(f))]
    check("V26 反证：把源文件某字段改坏后比对必须报出差异（比对不是恒等于一致）",
          diffs == ["产业方向"],
          "报出差异 %s" % (diffs,))

    # ================= 其它交付一致性 =================
    s05 = SC.s05_mapping()
    check("V27 字段映射预览：6 列可映射、1 列如实标注未映射",
          s05["final"]["mapped"] == 6
          and s05["final"]["unmapped"] == ["备注（源表无对应）"],
          "可映射 %s / 未映射 %s" % (s05["final"]["mapped"], s05["final"]["unmapped"]))

    rows_csv = _csv("data/cells_companies.csv")
    check("V28 企业单元格值转储恰为 100 行、7 列（跨平台比这份 CSV 而非 xlsx 字节）",
          len(rows_csv) == EXPECT_TOTAL_ROWS and len(rows_csv[0]) == 7,
          "%d 行 / %d 列" % (len(rows_csv), len(rows_csv[0])))

    rows_c = _csv("data/cells_contacts.csv")
    check("V29 联系人单元格值转储恰为 260 行、6 列",
          len(rows_c) == EXPECT_N_CONTACTS and len(rows_c[0]) == 6,
          "%d 行 / %d 列" % (len(rows_c), len(rows_c[0])))

    comp_md = _read("docs/completeness.md")
    check("V30 完整度文档同时写出系统值与独立值，并标明差为 0",
          "%.12f" % EXPECT_COMP_RATIO in comp_md and "差 = 0.000000000000" in comp_md,
          "文档内出现两处 %.12f 与差值 0" % EXPECT_COMP_RATIO)

    sample_md = _read("docs/sample10.md")
    check("V31 抽样文档列出 10 行且差异合计为 0",
          len(re.findall(r"^\| \d+ \| \d+ \|", sample_md, re.M)) == EXPECT_SAMPLE
          and "差异合计 0 处" in sample_md,
          "文档行数 %d" % len(re.findall(r"^\| \d+ \| \d+ \|", sample_md, re.M)))

    md = _read("docs/members.md")
    check("V32 逐例 Markdown 含 100 个小节（每家企业一节）",
          len(re.findall(r"^## 第 \d+ 行 ", md, re.M)) == EXPECT_TOTAL_ROWS,
          "小节 %d 个" % len(re.findall(r"^## 第 \d+ 行 ", md, re.M)))
