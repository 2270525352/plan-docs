# CCB 任务分发提示词

```text
先检测当前 CCB 的实际命令和能力，再分发，不凭空构造参数。

项目根：<PROJECT_ROOT>
协调者：<COORDINATOR>
最终合并权威：<MERGE_AUTHORITY>

读取总任务、AI 任务文档、任务依赖与并行计划、CURRENT_STATE 和自动模式门禁。
只分发 status=ready、dependencies 已满足的任务。
每个 agent 收到完整合同：task_id、owner、U/REQ/GAP 来源、input_docs、dependencies、allowed/forbidden scope、write_lock、shared_interfaces、input/output contracts、merge_order、conflict_resolution、exact_steps、outputs、acceptance、verify/test、feedback、checkpoint、stop_conditions。
每个 agent 在任何写入前，必须在自己的隔离 worktree 用对应的 canonical AI 任务文档激活唯一运行态：
python3 <PLAN_DOCS_SKILL_DIR>/scripts/plan-docs-activate-task.py --project <AGENT_WORKTREE> --task-doc <AGENT_WORKTREE>/docs/plan-docs/04-tasks/<CANONICAL_AI_TASK_DOC> --task-id <TASK_ID>
agent 必须确认 current-task.json 与所选合同完全一致。同一 worktree 同时只能激活一个任务；共享 worktree 时必须串行。
只在独立 worktree 中并发分发写入范围和接口不重叠的任务。
agent 返回实际改动文件、diff 摘要、验证/测试证据、checkpoint、假设、风险、反馈记录和建议合并顺序。
协调者逐个检查范围、接口、冲突、测试、追踪链和 git diff 后合并。
出现 RED、冲突或未满足依赖时停止对应任务。
文档措辞、格式或 P2 不得触发重复规划审查；只有新的需求/架构事实缺口才回到上游。
```
