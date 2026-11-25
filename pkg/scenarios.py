
# -*- coding: utf-8 -*-
"""本单 6 个场景（AC1~AC4 与两条边界），每个都在独立实例上执行，可单独重放。

★ 一律用 _safe 包装业务异常：变异把规则改坏时，断言必须「失败并指出哪条不成立」，
  而不是让断言器自己崩掉（崩溃也非零退出，但说不清是哪条规则失效）。
"""
import os
import tempfile

import datafactory
import engine as E
import import_engine as IE
import independent as IND
import polling


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw), ""
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def _run_import(source=None):
    src = source or E.build_source()
    eng = IE.ImportEngine(src)
    job = eng.submit()
    return eng, job, eng.report(job.job_id)


# ---------------------------------------------------------------- AC1
def s01_import():
    """跑一次真实导入：92 家成功、8 行错误报告（逐行给出行号与原因）。"""
    tmp = tempfile.mkdtemp(prefix="imp2757_")
    xlsx = os.path.join(tmp, "source.xlsx")
    w, err = _safe(datafactory.write_xlsx, xlsx)
    eng, job, res = _run_import()
    lines = IE.error_report_lines(res)
    return {"id": "S01", "desc": "AC1 导入 92 家成功、错误报告 8 行",
            "final": {"xlsx_written": bool(w), "xlsx_err": err,
                      "job_status": job.status, "total_rows": job.total,
                      "ok_count": len(res["ok_companies"]),
                      "error_count": len(res["errors"]),
                      "error_lines": lines,
                      "error_row_numbers": [e["row"] for e in sorted(res["errors"],
                                                                     key=lambda x: x["row"])],
                      "every_line_has_row_and_reason":
                          all("第 " in l and " | " in l for l in lines)}}


def s01b_contacts_imported():
    """缺手机号的 6 行联系人**导入成功**（不是被当错误拦掉）。"""
    _eng, _job, res = _run_import()
    src = E.build_source()
    codes_ok = {c["信用代码"] for c in res["ok_companies"]}
    nophone = [c for c in src["contacts"] if not (c.get("手机号") or "").strip()]
    imported = [c for c in nophone if c["信用代码"] in codes_ok]
    return {"id": "S01b", "desc": "缺手机号联系人导入成功（只扣完整度分，不算错误）",
            "final": {"nophone_total": len(nophone),
                      "nophone_in_ok_companies": len(imported),
                      "in_error_report": sum(1 for e in res["errors"]
                                             if "手机" in e["reason"])}}


# ---------------------------------------------------------------- AC2
def s02_completeness():
    """系统报告值与独立脚本计算值之差必须为 0。"""
    tmp = tempfile.mkdtemp(prefix="imp2757c_")
    xlsx = os.path.join(tmp, "source.xlsx")
    datafactory.write_xlsx(xlsx)
    _eng, _job, res = _run_import()
    sysrep, e1 = _safe(lambda: res["completeness"])
    ind, e2 = _safe(IND.compute, xlsx)
    diff = None
    if sysrep and ind:
        diff = abs(sysrep["ratio"] - ind["ratio"])
    return {"id": "S02", "desc": "AC2 完整度：系统报告 vs 独立脚本",
            "final": {"system_ratio": (sysrep or {}).get("ratio"),
                      "independent_ratio": (ind or {}).get("ratio"),
                      "diff": diff,
                      "system_filled": (sysrep or {}).get("filled"),
                      "system_total": (sysrep or {}).get("total"),
                      "ind_filled": (ind or {}).get("filled"),
                      "ind_total": (ind or {}).get("total"),
                      "errs": [e1, e2],
                      "per_field": (sysrep or {}).get("per_field")}}


# ---------------------------------------------------------------- AC3
def s03_timeout():
    """慢任务轮询到上限后以明确信息失败：次数、间隔、最后状态都要在消息里。"""
    src = E.build_source()
    eng = IE.ImportEngine(src)
    slow = eng.make_slow_job()

    class Client:
        def get_job(self, jid):
            return eng.get_job(jid)

    sleeps = []
    polls = []
    out, err = _safe(polling.poll_until_done, Client(), slow.job_id,
                     sleep=lambda s: sleeps.append(s),
                     on_poll=lambda n, v: polls.append((n, v["status"])))
    msg = ""
    if out is None:
        msg = err
    return {"id": "S03", "desc": "AC3 慢任务轮询到上限后明确失败",
            "final": {"raised": bool(err), "error_type": err.split(":")[0] if err else "",
                      "message": msg,
                      "poll_count": len(polls),
                      "sleep_calls": len(sleeps),
                      "sleep_interval": sleeps[0] if sleeps else None,
                      "last_status": polls[-1][1] if polls else None,
                      "engine_polls": slow.polls}}


def s03b_fast_success():
    """反证：正常任务在 1 次轮询就成功，不该被超时逻辑误伤。"""
    eng = IE.ImportEngine(E.build_source())
    job = eng.submit()

    class Client:
        def get_job(self, jid):
            return eng.get_job(jid)

    sleeps = []
    out, err = _safe(polling.poll_until_done, Client(), job.job_id,
                     sleep=lambda s: sleeps.append(s))
    return {"id": "S03b", "desc": "反证：正常任务不触发超时",
            "final": {"ok": bool(out), "err": err,
                      "status": (out or {}).get("status"),
                      "sleep_calls": len(sleeps)}}


# ---------------------------------------------------------------- AC4
def s04_sample10():
    """随机抽样 10 家与源文件逐字段比对（抽样用固定步长，保证可复现）。"""
    tmp = tempfile.mkdtemp(prefix="imp2757s_")
    xlsx = os.path.join(tmp, "source.xlsx")
    datafactory.write_xlsx(xlsx)
    back, e0 = _safe(datafactory.read_back, xlsx)
    _eng, _job, res = _run_import()
    ok = res["ok_companies"]
    # 固定步长抽样：92 家里每 9 家取 1 家，共 10 家（可复现，不依赖随机种子）
    picks = [ok[i * 9] for i in range(10)]
    src_rows = {int(r["行号"]): r for r in back["companies"]}
    rows = []
    for p in picks:
        s = src_rows.get(int(p["row"])) or {}
        fields = ["企业名称", "信用代码", "产业方向", "会籍档位", "所在城市", "成立年份"]
        diffs = [f for f in fields if str(p.get(f)) != str(s.get(f))]
        rows.append({"row": p["row"], "name": p["企业名称"],
                     "fields_compared": len(fields), "diffs": diffs})
    return {"id": "S04", "desc": "AC4 抽样 10 家逐字段比对",
            "final": {"n_sampled": len(rows),
                      "rows": rows,
                      "all_match": all(not r["diffs"] for r in rows),
                      "total_fields_compared": sum(r["fields_compared"] for r in rows),
                      "err": e0}}


def s05_mapping():
    """字段映射预览：可映射列给出目标字段，未映射列如实标注。"""
    eng = IE.ImportEngine(E.build_source())
    prev = eng.preview_mapping([ "企业名称", "信用代码", "产业方向", "会籍档位",
                                "所在城市", "成立年份", "备注（源表无对应）"])
    return {"id": "S05", "desc": "字段映射预览",
            "final": {"items": prev,
                      "mapped": sum(1 for x in prev if x["mapped"]),
                      "unmapped": [x["source"] for x in prev if not x["mapped"]]}}


ALL = [s01_import, s01b_contacts_imported, s02_completeness, s03_timeout,
       s03b_fast_success, s04_sample10, s05_mapping]


def run_all():
    return [f() for f in ALL]
