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

先读 AGENTS.md、CURRENT_STATE.md、用户原话、项目事实基线、AI 可读需求、现状与目标差异、产品索引、架构/接口、总任务、Codex任务文档、执行反馈和自动模式门禁。
只领取 owner=Codex 且依赖满足的任务。
选定一个任务后、任何写入前，必须用该任务在 Codex 任务文档中的原样合同激活唯一运行态：
python3 <PLAN_DOCS_SKILL_DIR>/scripts/plan-docs-activate-task.py --project <PROJECT_ROOT> --task-doc <PROJECT_ROOT>/docs/plan-docs/04-tasks/Codex任务文档.md --task-id <TASK_ID>
确认 current-task.json 的 task_id、范围、写锁和合同字段与所选任务一致；同一 worktree 同时只能激活一个任务。
禁止无依据硬编码、另起接口、扩展 allowed_scope 或修改 forbidden_scope。
多任务并行只能使用彼此隔离的 worktree；每个 worktree 分别激活一个任务。并行前验证文件不重叠、接口不共写、依赖满足、I/O 契约一致、写锁唯一、合并顺序明确。
每个任务执行：锁定 → 记录开始/最近进展时间 → git status → exact_steps → verify/test → 反馈 → 对齐 U/REQ/GAP 与 diff → checkpoint → 更新 CURRENT_STATE。
发现 RED、锁/接口冲突、需求缺口、测试失败或 stop_conditions 时停止并报告，不猜测推进。
允许长时间实际开发，但必须持续形成代码、测试、checkpoint 或 blocker 证据；措辞、格式和 P2
不得触发重复规划审查。

完成条件：
- Codex 任务全部 done 或有可追溯 blocker；
- 每个完成任务有验收、测试、反馈和 checkpoint；
- 无超范围文件、无未审查接口变更、无无依据硬编码；
- CURRENT_STATE、任务状态与 Git 一致；
- 独立 Reviewer 门禁通过。
```
