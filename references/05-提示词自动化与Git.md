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
- 门禁通过后以实际开发为主，不因措辞、格式或 P2 反复回到规划审查；
- 允许长时间开发，但每个任务持续写入代码 diff、测试、checkpoint 或 blocker 证据。

## Codex App 定时审查

生成提示词和设置说明，不直接创建自动化。默认关闭；实际启用需用户确认频率和停止策略。
用户未另行指定时可建议每 30 分钟运行一次，并在连续两次 GREEN 后停止。

Reviewer 使用独立上下文，对照：

- 用户原话；
- AI 可读需求；
- 产品/交互、架构和接口；
- 总任务与 AI 子任务；
- 执行反馈与 `CURRENT_STATE.md`；
- 当前 Git diff 和最近 checkpoint。

输出 GREEN/YELLOW/RED 和证据。RED 要求主执行流程停止。默认只检测与报告，不自动修改任何文件；如果自动化需要把报告持久化，必须由用户明确授权写入 `06-reviews/`。

定时审查不得重复启动六代理完整文档审查，也不得把 P2 升级为阻塞项。项目完成、达到停止
策略或用户取消时停止产生新任务。

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

门禁记录并验证完整 40 位 `reviewed_checkpoint`：commit 必须存在且是 HEAD 祖先，规划 source
snapshot 必须与该 commit 一致，gate-ready 时工作树必须干净。最终提示词和护栏生成后，只
允许 `07-goals/`、`08-automation/` 与 Plan Docs 自有护栏文件形成预期 post-checkpoint
diff；其他变化重新阻断。`git_policy: disabled` 必须绑定到明确接受降级的 U-* 原话片段。

## 护栏

`plan-docs-guards.py` 安装：

- Claude `Edit`/`Write`/`Bash` 写入范围检查：识别常见 shell 重定向和写命令，只读 Bash 放行；动态目标、目录上下文变化、破坏性 Git 命令等无法可靠解析的高风险写法 fail-closed；
- Claude 停止前执行反馈检查；
- Git pre-commit 的用户原话 append-only、当前任务、反馈和测试门禁；
- commit-msg 的任务 ID/AI 格式检查；
- pre-push 的 force push 检测。

护栏不是需求解释器。实时 hook 对 `Edit`/`Write`/`Bash` 的内部错误也 fail-closed；Git pre-commit 仍是 staged diff 的第二道权威防线。已有 hook manager 时脚本只安装自有文件并报告集成待办，不覆盖现有 hook。显式串联三类 hook 后，使用 `verify --allow-existing-hooks-path` 校验真实调用痕迹。`.claude/settings.json` 通过结构化 JSON 合并，卸载时只移除 Plan Docs 项。
