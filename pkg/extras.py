
# -*- coding: utf-8 -*-
"""本单特有产物：Excel 样例、单元格值转储、错误报告、完整度报告、抽样比对表。

跨平台注意：xlsx 是 zip，条目带本地时间与 create_system，**字节级不可比**。
所以另出一份「单元格值转储 CSV」，两侧比对的是这份 CSV，不是 xlsx 字节。
"""
import os

import datafactory
import engine as E
import import_engine as IE

XLSX_REL = "data/source_members.xlsx"
DUMP_COMPANIES = "data/cells_companies.csv"
DUMP_CONTACTS = "data/cells_contacts.csv"
ERROR_REPORT = "docs/error_report.md"
COMPLETENESS = "docs/completeness.md"
SAMPLE_MD = "docs/sample10.md"


def _csv(path, header, rows):
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return path


def build_error_report(res):
    lines = IE.error_report_lines(res)
    L = ["# 导入错误报告（%d 行）" % len(lines), "",
         "每行一条原因，行号为 Excel 实际行号（第 1 行是表头）。", "",
         "| 序 | 行号 | 信用代码 | 原因 |", "| --- | --- | --- | --- |"]
    for i, e in enumerate(sorted(res["errors"], key=lambda x: x["row"]), 1):
        L.append("| %d | %d | `%s` | %s |" % (i, e["row"], e["credit_code"] or "(空)", e["reason"]))
    L += ["", "## 原文格式（与脚本输出一致）", ""]
    for ln in lines:
        L.append(ln)
    L += ["", "> 说明：这 8 行是**企业表**的错误。联系人表里 6 行缺手机号**不算错误**，"
          "照常导入，只在完整度上扣分（见 completeness.md）。", ""]
    return "\n".join(L)


def build_completeness_md(sysrep, indrep):
    L = ["# 关键字段完整度（6 项非空比例）", "",
         "## 口径", "",
         "- 记录单位：**企业**（本次导入成功的 %d 家）。" % sysrep["records"],
         "- 6 项：企业名称 / 信用代码 / 产业方向 / 会籍档位（来自企业表）+ "
         "联系人姓名 / 联系人手机号（取该企业的**主联系人**，即联系人表里该信用代码的第一条）。",
         "- 主联系人口径是工单未写死处，此处明示：一家企业有多名联系人时不重复计入。", "",
         "## 结果（系统报告 vs 独立脚本）", "",
         "| 项 | 系统报告 | 独立脚本 |", "| --- | --- | --- |",
         "| 非空计数 | %d | %d |" % (sysrep["filled"], indrep["filled"]),
         "| 总计数 | %d | %d |" % (sysrep["total"], indrep["total"]),
         "| 比例 | %.12f | %.12f |" % (sysrep["ratio"], indrep["ratio"]),
         "| 记录数 | %d | %d |" % (sysrep["records"], indrep["records"]),
         "", "**差 = %.12f**（断言要求为 0）" % abs(sysrep["ratio"] - indrep["ratio"]), "",
         "## 逐项明细", "", "| 字段 | 非空 | 总数 | 非空率 |", "| --- | --- | --- | --- |"]
    for f in E.KEY_FIELDS:
        d = sysrep["per_field"][f]
        L.append("| %s | %d | %d | %.4f |" % (f, d["filled"], d["total"],
                                              d["filled"] / d["total"]))
    L += ["", "> 独立脚本 `pkg/independent.py` 直接读 xlsx 自己重算，"
          "不使用导入引擎的任何中间结果；两条路径共享的只是「规则」本身。", ""]
    return "\n".join(L)


def build_sample_md(res, back):
    ok = res["ok_companies"]
    picks = [ok[i * 9] for i in range(10)]
    src_rows = {int(r["行号"]): r for r in back["companies"]}
    L = ["# 抽样 10 家逐字段比对", "",
         "抽样方式：在导入成功的 %d 家中按固定步长（每 9 家取 1 家，从第 0 个起）取 10 家，"
         "可复现、不依赖随机种子。" % len(ok), "",
         "| 序 | 行号 | 企业名称 | 比对字段数 | 差异 |", "| --- | --- | --- | --- | --- |"]
    fields = ["企业名称", "信用代码", "产业方向", "会籍档位", "所在城市", "成立年份"]
    for i, p in enumerate(picks, 1):
        s = src_rows.get(int(p["row"])) or {}
        diffs = [f for f in fields if str(p.get(f)) != str(s.get(f))]
        L.append("| %d | %d | %s | %d | %s |"
                 % (i, p["row"], p["企业名称"], len(fields),
                    ("**" + ", ".join(diffs) + "**") if diffs else "无"))
    L += ["", "比对字段共 %d 项；差异合计 %d 处。"
          % (len(picks) * len(fields),
             sum(len([f for f in fields
                      if str(p.get(f)) != str((src_rows.get(int(p["row"])) or {}).get(f))])
                 for p in picks)), ""]
    return "\n".join(L)


def write_extras(docs_dir):
    root = os.path.dirname(os.path.abspath(docs_dir))
    out = []
    src = E.build_source()
    xlsx = os.path.join(root, XLSX_REL)
    datafactory.write_xlsx(xlsx)
    out.append(xlsx)
    back = datafactory.read_back(xlsx)
    # 单元格值转储（跨平台比对用这份，不比 xlsx 字节）
    out.append(_csv(os.path.join(root, DUMP_COMPANIES), datafactory.COMPANY_HEADER,
                    [[r.get(h) for h in datafactory.COMPANY_HEADER] for r in back["companies"]]))
    out.append(_csv(os.path.join(root, DUMP_CONTACTS), datafactory.CONTACT_HEADER,
                    [[r.get(h) for h in datafactory.CONTACT_HEADER] for r in back["contacts"]]))
    eng = IE.ImportEngine(src)
    job = eng.submit()
    res = eng.report(job.job_id)
    import independent as IND
    sysrep = res["completeness"]
    indrep = IND.compute(xlsx)
    for rel, body in ((ERROR_REPORT, build_error_report(res)),
                      (COMPLETENESS, build_completeness_md(sysrep, indrep)),
                      (SAMPLE_MD, build_sample_md(res, back))):
        pp = os.path.join(root, rel)
        os.makedirs(os.path.dirname(pp), exist_ok=True)
        with open(pp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        out.append(pp)
    return out
