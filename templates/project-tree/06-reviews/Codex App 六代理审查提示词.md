# Codex App 六代理审查提示词

把以下提示词交给 Codex App。优先并行启动六个独立代理；若不支持，则按 reviewer_id 用六次新上下文串行执行。各代理不得看到其他代理结论。

```text
你是本项目的文档审查协调者。不要实现代码，不要修改用户原话，不要让审查代理静默修复文档。

项目根目录：<PROJECT_ROOT>

先读取：
1. AGENTS.md
2. CURRENT_STATE.md
3. docs/plan-docs/00-source/
4. docs/plan-docs/01-requirements/
5. docs/plan-docs/02-architecture/
6. docs/plan-docs/03-product/
7. docs/plan-docs/04-tasks/
8. docs/plan-docs/05-execution/环境与分工确认.md
9. docs/plan-docs/09-git/

启动六个相互独立、上下文干净的审查代理：

A1：检查用户原话与需求是否逐项对齐，列出 U-* ↔ REQ-* 的遗漏、误读或越界。
A2：检查遗漏、歧义、隐含假设、冲突和不可验收需求。
A3：检查架构、接口、数据流、产品模块树、按钮级交互、数据/API/测试引用是否完整一致。
A4：检查总任务、依赖拓扑、原子粒度、并行安全、写锁、共享接口、输入输出格式和文件冲突。
A5：检查 Claude、Codex、Reviewer（Claude）、OpenCode 的职责、禁止范围和 Reviewer 独立性。
A6：检查测试、Git checkpoint、执行反馈、CURRENT_STATE、自动化、护栏和停止条件。

每个代理只提交报告，保存为 `docs/plan-docs/06-reviews/agents/<review_round>-<reviewer_id>.md`。必须按 A1→A6 串行执行以下状态机：

1. 协调者在 `审查分发与写锁.md` 把当前行标为 `active`，并原子切换
   `CURRENT_STATE.md`：current task/owner/reviewer_id 指向当前 Reviewer，`locked_files`
   只含它的精确报告路径；同时登记外部调度器返回的唯一 run/thread ID、随机 nonce 和统一
   planning source snapshot SHA-256。完成此控制面切换后协调者停止写文件。
2. Reviewer 启动时只提取 `CURRENT_STATE.md` 从 `## Current snapshot` 到下一个 `##`
   之前的有界快照，以及分发表中自己的单行，验证上述四项；禁止整页读取状态日志、历史
   审查摘要或其他 Reviewer 行。任一不匹配或误读禁止内容就停止且不创建报告。它禁止读取
   同轮其他报告，禁止写汇总、门禁、规划、代码、状态或其他代理文件。
3. Reviewer 只写自己的报告，返回 `submitted` 后进程结束，不自行修改状态或分发表。
4. Reviewer 结束后，协调者拥有一次仅用于锁交接的控制面转换权：先校验报告路径和 schema，
   记录 SHA-256/bytes，把该行标为 `immutable`，再激活下一个 Reviewer。转换期间不得修改原始
   报告或其他规划内容。
5. 已存在或已登记过的报告路径不得覆盖；失败重跑使用新 review round/path。

协调者只能读取原始报告并写汇总/门禁，不能改写原始报告。严格使用项目所用 plan-docs skill 的
`templates/fragments/代理审查报告.md`，核心格式如下：
reviewer_id:
review_round:
context_isolation: clean / degraded（degraded 可留证，但不能通过门禁）
review_run_id: <外部调度器的唯一 run/thread ID>
dispatch_nonce: <本次分发唯一 nonce>
source_snapshot_sha256: <统一 planning source snapshot SHA-256>
scope: <非空单行范围>
verdict: GREEN / YELLOW / RED

## Findings

### REV-<reviewer_id>-001
finding_id: REV-<reviewer_id>-001
severity: P0 / P1 / P2
evidence: <非空单行证据>
affected_ids: []
problem: <非空单行问题>
required_resolution: <非空单行关闭条件>
status: OPEN / RESOLVED

coverage_checked: <非空单行覆盖证据>
unverified_items: none / <非空单行未核验项>

汇总六份报告到 docs/plan-docs/06-reviews/审查汇总.md，并在 `report_ref` 填入各原始报告相对路径。不要直接修复；先把每个 finding 分配给规划 owner。修订完成后，对受影响范围重新运行独立审查。

只有同时满足以下条件才把自动模式门禁标记 READY：
- 没有 RED；
- 没有未处理的 P0/P1 YELLOW；
- 所有需求都有任务和验收标准；
- 所有任务都有 owner、allowed/forbidden scope、验证/测试、write_lock、feedback 和 stop conditions；
- 不存在文件或接口写入冲突；
- 用户已确认环境、分工、Git 策略、最终规划和最终合并权威。

否则门禁保持 BLOCKED，并明确阻塞证据。不得生成最终执行提示词。
```
