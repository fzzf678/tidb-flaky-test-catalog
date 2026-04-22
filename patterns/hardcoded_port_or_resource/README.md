# `hardcoded_port_or_resource`

这个目录把 review smell `hardcoded_port_or_resource` 从“关键词桶”细化为**机制级** family（subpatterns），用于后续更准确地：

- 区分真正共享同一类失稳机制的 case
- 支撑 subpattern formalization 与边界判断
- 支撑后续 repo-scan / retrieval / 人工复核流程

> 注意：这里的结论只来自 `patch-first` 的全量人工复读（读 PR patch 本体），不是由已有字段/regex 命中推出来的。

## Source set

- **source smell**: `hardcoded_port_or_resource`
- **source case set**: catalog 中 `review_smells` 含该 key 的全量 case
- **source case 总数**: `26`

## 人工复读进度与去向统计（本轮）

- 已人工阅读：`26 / 26`
- 去向统计：
  - `retain`: `21`
  - `exclude`: `2`
  - `migrate`: `0`
  - `watchlist`: `3`

全量逐例台账见：`patterns/hardcoded_port_or_resource/逐例梳理台账.tsv`

## 当前已 formalize 的 subpatterns

### 1) 本地服务端口必须由 listener/httptest 分配（`:0`）

**核心机制**：测试启动本地服务（HTTP/gRPC/TLS/embedded etcd/自建 TiDB server 等）时，使用硬编码端口、伪随机端口、或“只分配不保留”的端口分配方式，会在并行/负载环境下发生端口冲突（`EADDRINUSE`）、连到错误服务、或偶发启动失败。

- 覆盖 retained：`14`
- subpattern 文件：`patterns/hardcoded_port_or_resource/subpatterns/本地服务端口必须由_listener_httptest_分配_0_避免硬编码_伪随机_扫描端口.json`

### 2) 临时文件/目录必须用 `t.TempDir()` / `os.CreateTemp()` 隔离

**核心机制**：测试写入硬编码 `/tmp/...`、固定 basename（即便在 `os.TempDir()` 下）、或共享全局 `TempDir/TempStoragePath`，会导致并行/重跑时相互覆盖、互删，出现 “file exists / file not found / 被别的测试清理掉” 这类 flaky。

- 覆盖 retained：`4`
- subpattern 文件：`patterns/hardcoded_port_or_resource/subpatterns/临时文件目录必须_t_TempDir_os_CreateTemp_隔离_避免写死_tmp_共享_TempDir.json`

### 3) TiDB mock/server 的 unix socket 路径需唯一（或禁用）

**核心机制**：启动 TiDB server/mock cluster 时使用默认/固定的 `cfg.Socket`（常见落在 `/tmp`），并行测试或残留 socket 文件会导致冲突；修法通常是显式指定**唯一 socket 路径**（最好放到 `t.TempDir()` 下），或直接 `cfg.Socket = ""` 禁用 socket。

- 覆盖 retained：`3`
- subpattern 文件：`patterns/hardcoded_port_or_resource/subpatterns/TiDB_mock_server_unix_socket_路径需唯一或禁用_避免_tmp_冲突.json`

## 关键边界判断（避免“关键词聚类”）

- **端口分配 subpattern** vs **socket 路径 subpattern**：
  - 端口问题关注的是 `Listen(…:port)` 的冲突/分配策略（`:0`/httptest/getFreePort/retry）。
  - socket 问题关注的是 `cfg.Socket` 的路径唯一性与残留文件冲突。
  - 两者可能同一 patch 同时出现，但归类以**主要失稳点**为准；次要机制写进台账备注即可。

- **临时目录 subpattern** vs **其他 test isolation/state pollution**：
  - 本 family 只收“路径/命名空间冲突”这条机制（temp dir / temp storage / dump file / cert file 等）。
  - 如果 patch 的主体是“全局 knob restore / 背景 worker Stop/Wait / hook scope”，更应该迁到 `test_isolation_and_state_pollution`（本 source set 中未出现强迁移样例）。

## Watchlist（暂不落正式 JSON）

这 3 个 case 都已 patch-first 阅读，但目前不够稳定/不够集中，先作为 watchlist：

- `pr-14826`：Windows 平台行为差异（文件句柄未关闭导致无法删除、unix socket 地址差异等）混杂多机制，不够收敛。
- `pr-33295`：断言依赖 “instance/host/port + socket details” 的字符串形态；更像“避免断言动态网络细节”的方向，需更大样本再 formalize。
- `pr-58006`：网络错误文案在不同 OS/network stack 不一致；更像“避免断言 OS-specific error string”的方向，当前为 singleton。

## Exclude（本轮明确排除）

- `pr-43023`：通过限制 Bazel `--jobs` 缓解 CPU 争用导致的 flaky，更像 CI 资源/并行度治理，不属于端口/路径命名空间冲突机制。
- `pr-51284`：巨大 `LIMIT/OFFSET` 触发 OOM（预分配 slice 过大），属于资源上限/内存波动，不属于端口/路径冲突机制。

## 下一步建议

1. `retrieval_signals.json`（`v1`，candidate-only）已提供：建议对每个 subpattern 持续做 **TiDB repo 级** 的粗检索回放（先宽后窄），统计“命中→人工复核→保留率”，再按噪声类别迭代 signals（详见 `给agent的仓库扫描检索信号.md`）。
2. 若 watchlist 中的 “动态网络细节/错误文案断言” 能在更大样本里收敛，再考虑新开 subpattern（注意与 `nondeterministic_result_order` 的“断言字段选择”边界）。
3. 评估 `hardcoded_port_or_resource` 是否要拆成更明确的方向：
   - `port allocation / listener binding`
   - `filesystem temp namespace`
   - `unix socket namespace`
   - （可选）`resource contention / OOM` 另起 family（与本目录保持边界清晰）
