
# -*- coding: utf-8 -*-
"""轮询客户端：最多 60 次、间隔 2 秒，超时即以明确信息失败。

为什么要把 sleep 抽成参数：60 次 x 2 秒 = 120 秒，真等会让测试跑两分钟；
注入假时钟后 60 次轮询在毫秒内跑完，但**轮询次数、间隔、超时文案都是真的**。
真实使用时传默认值即可。
"""
import time

import engine as E


class ImportTimeout(RuntimeError):
    """轮询到上限任务仍未完成。"""


def poll_until_done(client, job_id, max_polls=E.POLL_MAX, interval=E.POLL_INTERVAL,
                    sleep=None, on_poll=None):
    """返回 job 视图（status=succeeded）。

    超过 max_polls 次仍未完成 -> 抛 ImportTimeout，消息里写明次数、间隔、总时长与最后状态。
    """
    sleep = sleep or time.sleep
    last = None
    for n in range(1, max_polls + 1):
        last = client.get_job(job_id).view()
        if on_poll:
            on_poll(n, last)
        if last["status"] in ("succeeded", "failed"):
            return last
        if n < max_polls:
            sleep(interval)
    total = int(max_polls * interval)
    raise ImportTimeout(
        "轮询 %d 次（间隔 %s 秒，合计 %d 秒）后任务 %s 仍未完成（最后状态 %s，已处理 %s/%s）；"
        "按约定判定超时失败，不再继续等待。" % (
            max_polls, interval, total, job_id,
            (last or {}).get("status"), (last or {}).get("processed"), (last or {}).get("total")))
