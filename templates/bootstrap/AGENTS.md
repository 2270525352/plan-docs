# Repository AI Rules

<!-- PLAN_DOCS_START -->
## Plan Docs Rules

### Project coordination

- Planning tree: `docs/plan-docs/`
- Dynamic state: `CURRENT_STATE.md`
- Execution mode: CCB multi-AI / multi-window / single AI CLI
- Planning owner:
- Coordinator:
- Final merge authority:
- Git policy: auto / confirm / disabled

### Startup read order

Every AI must read:

1. `AGENTS.md`
2. `CURRENT_STATE.md`
3. `docs/plan-docs/00-source/用户原话.md`
4. `docs/plan-docs/01-requirements/AI可读需求文档.md`
5. `docs/plan-docs/03-product/产品及交互索引.md`
6. `docs/plan-docs/02-architecture/总体架构.md`
7. `docs/plan-docs/02-architecture/接口契约.md`
8. `docs/plan-docs/04-tasks/总任务文档.md`
9. the task document for the active AI
10. `docs/plan-docs/05-execution/执行反馈日志.md`

Skip a file only when it does not exist in the current planning phase.

### Source and planning rules

- `00-source/用户原话.md` is append-only and contains only verbatim user words plus record metadata.
- Never rewrite, summarize, polish, translate, delete, or reorder user words.
- Put AI inference, research and interpretation in `00-source/AI推断与事实查证.md`.
- Every requirement, product node, architecture decision, task, test, review and commit must trace to stable IDs.
- Resolve requirements, task ownership and reviews before implementation.
- Do not invent product behavior, interface changes, prompts or architecture during execution.
- Do not use unsupported hardcoding to bypass missing requirements or contracts.

### Multi-AI coordination

- One coordinator and one final merge authority must be named.
- Multiple AIs may own non-overlapping tasks.
- Only one writer may own a final file at a time.
- Before writing, acquire the file lock in `CURRENT_STATE.md`, reread the latest target file, and confirm dependencies.
- Do not modify another owner's allowed scope or a shared interface without coordinator approval.
- Reviewer agents report only and do not implement the work they review.
- On file/interface conflict, RED review, or unmet dependency, stop and record the blocker.

### Execution and feedback

- Execute only tasks present in `04-tasks/总任务文档.md` and the active AI task document.
- Respect `allowed_scope`, `forbidden_scope`, `write_lock`, `shared_interfaces`, `input_contracts`, `output_contracts`, `merge_order`, `conflict_resolution` and `stop_conditions`.
- Run every declared verification and test command.
- Append a structured feedback record after every task or self-check; no feedback means not complete.
- Update `CURRENT_STATE.md` on task start, lock change, completion, blocker, review and checkpoint.

### Git

- Run `git status` before edits and preserve existing changes.
- Follow the confirmed Git policy.
- Do not mix unrelated changes, force push, overwrite history or commit secrets/temp output.
- Commit messages include the task ID and executing AI.
- Before automatic execution, require a clean, reversible checkpoint.
<!-- PLAN_DOCS_END -->
