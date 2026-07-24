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

每个代理只提交报告，保存为 `docs/plan-docs/06-reviews/agents/<review_round>-<reviewer_id>.md`。严格使用项目所用 plan-docs skill 的 `templates/fragments/代理审查报告.md`，核心格式如下：
reviewer_id:
review_round:
context_isolation: clean / degraded
scope:
verdict: GREEN / YELLOW / RED

## Findings

### REV-<reviewer_id>-001
finding_id: REV-<reviewer_id>-001
severity: P0 / P1 / P2
evidence:
affected_ids: []
problem:
required_resolution:
status: OPEN / RESOLVED

coverage_checked:
unverified_items:

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
