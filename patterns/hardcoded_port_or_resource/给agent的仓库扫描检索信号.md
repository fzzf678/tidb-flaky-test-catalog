# 给 agent 的仓库扫描检索信号（coarse retrieval）

本文档只记录 **coarse retrieval** 的检索草案与注意事项，用来支撑：

- 下一步对 TiDB repo 做“先宽后窄”的候选召回
- 对每条 subpattern 做命中→人工复核→保留率统计

它**不是** subpattern 成立的证据；subpattern 的证据来自 `patch-first` 的逐例机制聚类。

> patch-proxy：下面的“回放情况”基于本 family source set 的 PR patch（diff）做快速回放，只能证明“信号能抓到这些正例 patch 里的形态”，不能保证在 repo 全量扫描的 precision。

## Subpattern 1：端口分配必须由 listener/httptest 分配（`:0`）

### broad rg_template（先宽）

1) 直接抓“修法锚点”（能快速找到同型修复，但会漏掉未修复风险点）：

```bash
rg -n --glob '*_test.go' 'httptest\.NewServer|Listen\(\"tcp\", \":0\"\)|Listen\(\"tcp\", \"127\.0\.0\.1:0\"\)|Listen\(\"tcp\", \"localhost:0\"\)'
```

2) 抓“高风险端口策略”（更像 candidate retrieval；噪声相对可控）：

```bash
rg -n --glob '*_test.go' 'tempurl\.Alloc|rand\.Int31n\(|rand\.Intn\(|rand\.Int\(\)|51111\+port|for port := 40000'
```

3) 抓“server config 端口硬编码/显式设置”（容易炸，需要再加路径 hint）：

```bash
rg -n --glob '*_test.go' 'cfg\.Port\s*=\s*[0-9]+|StatusPort\s*=\s*[0-9]+'
```

### 为什么这么设计

- 端口问题的“风险点”往往不是 `:0` 本身，而是：
  - 硬编码端口号
  - rand/alloc 但不保留端口（TOCTOU）
  - 扫描端口区间（并行碰撞）
  - 假设 `port+1` 也可用（embedded etcd 常见）
- 所以检索分两跳：
  - 先用 `tempurl/rand/scan` 抓候选（较硬的 risk-shape）
  - 再用 `:0/httptest` 抓修法锚点（快速扩大正例种子）

### patch-proxy 回放（source set 正例命中示意）

在本 source set patch 中，以下信号能回放到部分正例：

- `httptest.NewServer` → `pr-14988`
- `tempurl.Alloc` → `pr-30716`（以及 `pr-31167` 的移除痕迹）
- `for port := 40000` → `pr-19434`（端口区间扫描）
- `51111+port` → `pr-65186`（固定基址 + 扫描）
- `rand.*`（端口生成）→ `pr-56310` / `pr-65773` / `pr-66552` 等
- `Listen("tcp", ":0")` / `localhost:0` → `pr-65186` / `pr-65773` / `pr-66552` 等

### 哪些信号会炸（需要 group narrowing）

- 任何直接扫 `:[0-9]+` 的模板都会非常噪（大量 DSN/注释/示例）。
- 建议强制加：
  - `--glob '*_test.go'`
  - 或限定目录：`br/`、`pkg/server/`、`pkg/privilege/`、`pkg/owner/` 等已知高密度区域
- 对 “cfg.Port/StatusPort” 这种信号，优先结合 `server.NewServer`/`NewTestServerClient` 等锚点二次收窄。

## Subpattern 2：临时文件/目录必须用 `t.TempDir()` / `CreateTemp()` 隔离

### broad rg_template（先宽）

1) 直接抓硬编码 `/tmp`：

```bash
rg -n --glob '*_test.go' '/tmp/'
```

2) 抓“共享 temp dir/config”锚点：

```bash
rg -n --glob '*_test.go' 'TempStoragePath|GetGlobalConfig\(\)\.TempDir|GetGlobalConfig\(\)\.TempStoragePath'
```

3) 抓“修法锚点”（t.TempDir/CreateTemp）：

```bash
rg -n --glob '*_test.go' 't\.TempDir\(|os\.CreateTemp\(|os\.MkdirTemp\('
```

### patch-proxy 回放（source set 正例命中示意）

- `/tmp/` → `pr-31876`（大量 `/tmp/*.csv`/`/tmp/*cert.pem`）、以及 `pr-29767/pr-29835/pr-65122`（socket/path）
- `TempStoragePath` → `pr-32225`
- `GetGlobalConfig().TempDir` → `pr-64457`
- `os.CreateTemp/os.MkdirTemp/t.TempDir` → `pr-31876/pr-32225/pr-64457` 等

### 哪些信号会炸

- `/tmp/` 在注释/文档/示例里也可能出现；必须配合 `*_test.go` 或目录限定。
- `t.TempDir()` 本身是“好实践”，它更适合用作“找到同类修法”而非“找到风险点”。找风险点优先扫 `/tmp`/固定 basename/共享 config。

## Subpattern 3：`cfg.Socket`（unix socket）路径需唯一（或禁用）

### broad rg_template（先宽）

```bash
rg -n --glob '*_test.go' 'cfg\.Socket\s*=|conf\.Socket\s*='
```

进一步聚焦 `.sock`：

```bash
rg -n --glob '*_test.go' 'cfg\.Socket\s*=.*\.sock|conf\.Socket\s*=.*\.sock'
```

### patch-proxy 回放（source set 正例命中示意）

- `cfg.Socket =` → `pr-29767` / `pr-29835` / `pr-65122`（以及 `pr-33246` 的 `cfg.Socket=""`）
- `\.sock` → `pr-29767` / `pr-29835` / `pr-65122`

### 哪些信号会炸

- 直接扫 `\.sock` 可能会在非 server config 场景里噪声上升；优先绑定到 `cfg.Socket`/`conf.Socket` 赋值语句。

## 交付状态说明

- 本轮已完成 subpatterns formalization，并将检索信号单独记录在本文档中。
- 已补充结构化的 `patterns/hardcoded_port_or_resource/retrieval_signals.json`（`v1`，candidate-only）：用来承载 broad_recall / fallback_no_path / group_intersection 三跳召回信号；**它不是 subpattern 成立证据**，verdict 仍然必须由人工复核 + verdict-layer subpattern JSON 给出。
- 2026-04-23 在 TiDB repo（本地 checkout）做了规模回放（仅用于评估“候选是否可 review”，不同 commit 会有波动）：
  - 端口分配：`broad_recall ≈ 34 files`；`group_intersection ≈ 21 files`
  - 临时目录：`broad_recall ≈ 176 files`；`group_intersection ≈ 26 files`
  - unix socket：`broad_recall ≈ 13 files`；`group_intersection ≈ 10 files`
- 后续建议：先跑一轮“命中→人工复核→保留率”统计，再按噪声类别迭代 signals（优先加 path hint / exclude 降噪，避免 hard gate）。
