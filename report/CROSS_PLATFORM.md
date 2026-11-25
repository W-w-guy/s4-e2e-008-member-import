# 跨平台实跑记录（同一份 zip，Windows 与 Ubuntu 各跑一遍）

## 传输方式

交付包先在 Windows 侧打成 `imp2757.zip`，经本机 HTTP 服务（192.168.112.1:8899）
下载到 Ubuntu 虚拟机（192.168.112.128）。两侧 zip 的 sha256 完全一致：

```
3ca1008c9092dd27940ef2cff3b204d4d6faaf64f7d45a857be0028ce5cd3609  imp2757.zip
```

## zip 可复现性

`tools/make_zip.py` 连跑两次产出的 zip sha256 完全相同（`3ca1008c9092dd27940ef2cff3b204d4d6faaf64f7d45a857be0028ce5cd3609`），
说明打包本身确定；唯一不确定的是 zip 里那份 xlsx 的内容字节（见下一节）。

## 结果对照

| 检查项 | Windows 11 / Python 3.11.7 | Ubuntu 24.04.5 / Python 3.12.3 |
| --- | --- | --- |
| openpyxl | 3.1.5 | 3.1.5 |
| pytest | 9.1.1 | 7.4.4 |
| SHA256SUMS 逐条复核 | 40/40 OK | **40/40 OK** |
| `tools/gen.py` | rc=0 | rc=0 |
| `tools/verify.py` | **32/32 PASS** | **32/32 PASS** |
| `pytest tests -q` | 通过（101 项） | **101 passed** |
| AC1 错误行号 | [12,20,24,38,46,59,75,84] | 完全相同 |
| AC2 完整度差 | 0.0 | 0.0 |
| AC3 轮询次数 | 60 | 60 |
| AC4 抽样差异 | 0 处 | 0 处 |
| 独立完整度 CLI | 546/552 = 0.989130434783 | 完全相同 |
| 单元格转储 CSV md5 | d8291bb9… / 9bb92fbc… | 完全相同 |
| 重跑 gen 后 CSV 仍幂等 | 是 | 是 |
| PII 扫描 | scanned=40 hits=0 | scanned=40 hits=0 |
| 包内可校验文件数 | 43 | 43 |

## ★ 关于 xlsx 的诚实处理

**本包不对 xlsx 做字节校验**，原因是实测出来的：

第一次跑 selfcheck 时，「全新目录重跑 gen 后校验和」这一步报 **1 条不一致**，不一致的文件正是
`data/source_members.xlsx`。原因是 openpyxl 写出的 xlsx 本身是个 zip，条目带**本地时间**与
`create_system`，同一台机器连跑两次字节都不同。

因此做了两件事：

1. **xlsx 不进 SHA256SUMS.txt**（但仍完整打进 zip，买家能拿到 Excel 样例）；
2. 另出一份**单元格值转储** `data/cells_companies.csv`（100 行）、`data/cells_contacts.csv`（260 行），
   跨平台比对的对象是这两份 CSV，不是 xlsx 字节。

实测：两侧 CSV 的 md5 完全相同（`d8291bb9f4b66310e0540e8015afd426` /
`9bb92fbca73e4c35540591de0ce12ce5`），且各自重跑 gen 后仍不变——说明数据生成是幂等的，
差异只在 xlsx 的容器元数据上。

## 顺带修掉的一个包级缺陷

为支持「xlsx 进 zip 但不进校验和」，给 `kitlib/pack.py` 增加了 `SUMS_SKIP_EXT = {".xlsx"}`：
`walk()` 产出的文件仍全部打进 zip，只是 `write_sums()` 时跳过 `.xlsx`。这条同时回流到了
`deliver_kit/kitlib/pack.py`，后续同类单不用再踩。

## 两个平台的原始日志

- `report/windows_run.log` —— Windows 侧完整输出
- `report/ubuntu_run.log` —— Ubuntu 侧完整输出（原样传回，sha256 `b3e1cc7982000b5477d29b32b4e87a3772c7e90ddb7d5516918be05a64ce1fcb`，与虚拟机内文件逐字节一致）

> `report/` 是打包时的快照，按约定不参与 `SHA256SUMS.txt` 校验。
