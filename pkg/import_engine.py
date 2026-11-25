
# -*- coding: utf-8 -*-
"""导入引擎（内存实现，接口语义对齐 FastAPI 服务）。

按工单【本单范围】的步骤：
  上传 -> 字段映射预览 -> 提交 -> 轮询任务状态 -> 下载核对报告

这里把「任务」做成显式状态机，便于测试轮询与超时：
  pending -> running -> succeeded | failed
另外提供 make_slow_job()：永远停在 running 的慢任务，用来验 AC3 的轮询上限。
"""
import uuid

import engine as E


class ImportJob:
    def __init__(self, job_id, total):
        self.job_id = job_id
        self.status = "pending"
        self.total = total
        self.processed = 0
        self.result = None
        self.fail_message = ""
        self.polls = 0          # 被查询过多少次（供超时断言用）

    def view(self):
        return {"job_id": self.job_id, "status": self.status,
                "total": self.total, "processed": self.processed,
                "fail_message": self.fail_message}


class ImportEngine:
    """一次导入 = 一个 job。导入逻辑与 HTTP 层解耦，便于直接单测。"""

    def __init__(self, source):
        self.source = source
        self.jobs = {}

    # ---- 字段映射预览
    def preview_mapping(self, columns=None):
        cols = columns or ["企业名称", "信用代码", "产业方向", "会籍档位", "所在城市", "成立年份"]
        target = {"企业名称": "name", "信用代码": "credit_code",
                  "产业方向": "industry", "会籍档位": "tier",
                  "所在城市": "city", "成立年份": "founded_year"}
        return [{"source": c, "target": target.get(c, "(未映射)"),
                 "mapped": c in target} for c in cols]

    # ---- 提交
    def submit(self, rows=None):
        rows = rows if rows is not None else self.source["companies"]
        job = ImportJob("imp-" + uuid.uuid5(uuid.NAMESPACE_URL, "imp-2757").hex[:12], len(rows))
        job.status = "running"
        seen = set()
        ok, errors = [], []
        for r in rows:
            errs = E.validate_company(r, seen)
            if errs:
                # 一行可能有多条原因，但报告口径是「一行一条」，取首条原因
                errors.append({"row": r["row"], "credit_code": r.get("信用代码") or "",
                               "reason": errs[0][0]})
            else:
                seen.add(r["信用代码"])
                ok.append(r)
            job.processed += 1
        comp = E.completeness(ok, self.source["contacts"])
        job.result = {"ok_companies": ok, "errors": errors, "completeness": comp}
        job.status = "succeeded"
        self.jobs[job.job_id] = job
        return job

    # ---- 轮询
    def get_job(self, job_id):
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError("任务 %s 不存在" % job_id)
        job.polls += 1
        return job

    # ---- 核对报告
    def report(self, job_id):
        job = self.jobs[job_id]
        if job.status != "succeeded":
            raise RuntimeError("任务 %s 未完成（%s），无法出报告" % (job_id, job.status))
        return job.result

    # ---- 慢任务（永不完成）
    def make_slow_job(self, total=100):
        job = ImportJob("imp-slow-0001", total)
        job.status = "running"
        job.processed = 1
        self.jobs[job.job_id] = job
        return job


def error_report_lines(result):
    """把错误列表渲染成「行号 + 原因」的纯文本行（AC1 要求逐行列出行号与原因）。"""
    out = []
    for e in sorted(result["errors"], key=lambda x: x["row"]):
        out.append("第 %d 行 | %s | %s" % (e["row"], e["credit_code"] or "(空)", e["reason"]))
    return out
