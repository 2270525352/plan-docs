# Codex 或 CCB /goal 提示词

仅在自动模式门禁 READY 且实际环境已验证支持 `/goal` 或等价目标模式后生成；否则改用普通任务提示词。

prompt_mode: <verified-goal | ordinary-prompt>

capability_evidence: <F-*>

```text
目标：按 docs/plan-docs 的已确认任务合同执行，不改变产品、UX、AI 提示词或架构决策。

项目根：<PROJECT_ROOT>
执行环境：<Codex CLI / Codex App / CCB>
协调者：<COORDINATOR>
最终合并权威：<MERGE_AUTHORITY>

先读 AGENTS.md、CURRENT_STATE.md、用户原话、AI 可读需求、产品索引、架构/接口、总任务、Codex任务文档、执行反馈和自动模式门禁。
只领取 owner=Codex 且依赖满足的任务。
禁止无依据硬编码、另起接口、扩展 allowed_scope 或修改 forbidden_scope。
多任务并行前验证文件不重叠、接口不共写、依赖满足、I/O 契约一致、写锁唯一、合并顺序明确。
每个任务执行：锁定 → git status → exact_steps → verify/test → 反馈 → 对齐 diff → checkpoint → 更新 CURRENT_STATE。
发现 RED、锁/接口冲突、需求缺口、测试失败或 stop_conditions 时停止并报告，不猜测推进。

完成条件：
- Codex 任务全部 done 或有可追溯 blocker；
- 每个完成任务有验收、测试、反馈和 checkpoint；
- 无超范围文件、无未审查接口变更、无无依据硬编码；
- CURRENT_STATE、任务状态与 Git 一致；
- 独立 Reviewer 门禁通过。
```
