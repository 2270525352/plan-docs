# Claude /goal 提示词

仅在自动模式门禁为 READY、用户已确认且当前 Claude 环境已验证支持相应目标模式后生成。

prompt_mode: <verified-goal | ordinary-prompt>

capability_evidence: <F-*>

```text
目标：按已确认的 Plan Docs 文档树完成所有分配给 Claude 的任务，不重新解释需求。

项目根：<PROJECT_ROOT>

启动读取：
AGENTS.md → CURRENT_STATE.md → docs/plan-docs/00-source/用户原话.md
→ 01-requirements/AI可读需求文档.md
→ 03-product/产品及交互索引.md
→ 02-architecture/总体架构.md 与 接口契约.md
→ 04-tasks/总任务文档.md 与 Claude任务文档.md
→ 05-execution/执行反馈日志.md
→ 06-reviews/自动模式门禁.md

仅领取 owner=Claude、status=ready、dependencies 已满足的任务。
每次只在 allowed_scope 和 write_lock 内写入；不得修改 forbidden_scope、用户原话、未授权需求、页面/交互、prompt 或共享接口。
开始前更新 CURRENT_STATE 并运行 git status。
按 exact_steps 执行；运行全部 verification_commands 和 test_commands。
追加 feedback_record，检查 source_user_words/requirement_ids 对齐，再按 Git 策略 checkpoint 并更新 CURRENT_STATE。
并行任务只在文件、接口、依赖和写锁检查全部 PASS 时分发。
遇到锁冲突、未确认需求、接口变更、验证失败、RED 或 stop_conditions 时立即停止并记录 blocker。

完成条件：
- Claude任务文档中所有非阻塞任务为 done；
- 每个任务有通过的验收/测试证据、反馈记录和所需 checkpoint；
- 无越界 diff；
- CURRENT_STATE 与 Git 状态一致；
- 独立 Reviewer 最终无 RED 或未处理 P0/P1 YELLOW。
```
