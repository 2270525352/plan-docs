# 提示词、自动化与 Git

## `/goal` 能力检测

在生成 `/goal` 版本前：

1. 检查用户实际环境和版本；
2. 优先查看本地 `--help`、命令列表或当前官方文档；
3. 记录证据、版本和检测时间到 `AI推断与事实查证.md`；
4. 不支持或无法确认时生成普通任务提示词，不把 `/goal` 当作通用标准。

默认：

- CCB 可能提供 `/goal`，必须检测；
- Claude 可生成适配其当前环境的 `/goal` 提示词，仍需确认；
- Codex CLI/App 能力随版本和表面不同，必须检测；
- OpenCode 视为不支持 `/goal`，除非已验证。

## 最终提示词生成条件

只有 `06-reviews/自动模式门禁.md` 为 READY 且用户确认规划/分工后，才从模板生成最终文件。提示词必须：

- 先读 `AGENTS.md` 和 `CURRENT_STATE.md`；
- 指定协调者、任务 owner、写锁和依赖；
- 只从任务文档领取工作；
- 每个任务运行验证/测试、写反馈并 checkpoint；
- 命中停止条件、RED 或锁冲突时停止；
- 禁止重解释需求或无依据硬编码。

## Codex App 定时审查

生成提示词和设置说明，不直接创建自动化。默认建议每 30 分钟运行一次，实际启用需用户确认。

Reviewer 使用独立上下文，对照：

- 用户原话；
- AI 可读需求；
- 产品/交互、架构和接口；
- 总任务与 AI 子任务；
- 执行反馈与 `CURRENT_STATE.md`；
- 当前 Git diff 和最近 checkpoint。

输出 GREEN/YELLOW/RED 和证据。RED 要求主执行流程停止。默认只检测与报告，不自动修改任何文件；如果自动化需要把报告持久化，必须由用户明确授权写入 `06-reviews/`。

## Git 纪律

- 修改前运行 `git status`，保留用户已有改动；
- 不混入无关格式化、临时文件或秘密；
- 规划基线经用户确认后 checkpoint；
- 每个可独立验收的任务完成后按 Git 策略 checkpoint；
- 审查修订完成后 checkpoint；
- 自动模式前必须有干净、可回退的 checkpoint；
- commit message 包含 `task_id` 和执行 AI；
- 更新 `CURRENT_STATE.md` 中最近 commit 和下一步；
- 不 force push，不覆盖或删除用户历史；
- 推送目标分支遵循用户与仓库规则，不在技能中固定禁止 main/master。

## 护栏

`plan-docs-guards.py` 安装：

- Claude 写入范围检查；
- Claude 停止前执行反馈检查；
- Git pre-commit 的用户原话 append-only、当前任务、反馈和测试门禁；
- commit-msg 的任务 ID/AI 格式检查；
- pre-push 的 force push 检测。

护栏不是需求解释器。已有 hook manager 时脚本只安装自有文件并报告集成待办，不覆盖现有 hook。显式串联三类 hook 后，使用 `verify --allow-existing-hooks-path` 校验真实调用痕迹。`.claude/settings.json` 通过结构化 JSON 合并，卸载时只移除 Plan Docs 项。
