# Reviewer（Claude）任务文档

role: Reviewer（Claude）

assignment_status: active

no_tasks_reason:

context_requirement: independent clean context

default_responsibilities: 只检查需求对齐、遗漏、歧义、冲突和偏离；输出结论与证据

forbidden_role_changes: 不直接修改被审查实现、规划或用户原话；不审查自己实现的任务

coordinator:

merge_authority:

## Assigned reviews

### TASK-REVIEW-001

task_id: TASK-REVIEW-001
phase: review
owner: Reviewer（Claude）
source_user_words: []
requirement_ids: []
input_docs: []
dependencies: []
allowed_scope:
  - docs/plan-docs/06-reviews/**
forbidden_scope:
  - docs/plan-docs/00-source/用户原话.md
  - 被审查的规划和实现文件
shared_interfaces: []
input_contracts: []
output_contracts: []
merge_order:
conflict_resolution:
exact_steps: []
expected_outputs: []
acceptance_criteria: 报告包含 GREEN/YELLOW/RED、严重级别和逐项证据
verification_commands: []
test_commands: []
write_lock: []
git_checkpoint:
feedback_record:
stop_conditions: 发现 RED 时停止并要求主流程阻塞
status: draft
