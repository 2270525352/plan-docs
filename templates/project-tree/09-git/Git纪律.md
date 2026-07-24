# Git 纪律

git_policy: auto / confirm / disabled

branch_policy:

## Rules

- 每次修改前运行 `git status` 并保护已有改动。
- 不混入无关格式化、秘密、临时或失败输出。
- 规划基线、独立任务、审查修订分别建立可回退 checkpoint。
- 自动模式开始前工作区应干净，或所有保留改动都有明确 owner 和记录。
- commit message 格式：`<task_id> (<AI>): <summary>`。
- 每次 commit 后更新任务状态、反馈和 `CURRENT_STATE.md`。
- 不 force push，不覆盖或删除历史。
- 是否推送 main/master 由用户和仓库规则决定，不由 Plan Docs 固定禁止。

## Checkpoint

### CP-001

checkpoint_id: CP-001

task_id:

owner:

source_user_words: []

requirement_ids: []

changed_files: []

verification:

tests:

review_refs: []

commit:

next_step:
