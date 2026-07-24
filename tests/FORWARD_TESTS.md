# 前向测试记录

日期：2026-07-25

## 方法

三个场景分别交给没有预期缺陷提示的全新代理上下文。代理从用户的模糊请求开始，必须按
`SKILL.md` 自行访谈、留存原话、确认环境与分工、生成规划并运行审计。场景都使用一次性
Git 项目；业务文件哈希在测试前后核对。前向测试产物不作为技能发布模板。

## 场景结果

| 场景 | 原话 | 需求 | 总任务 | 冻结合同 | 结构审计 | 业务改动 | 门禁结果 |
|---|---:|---:|---:|---:|---|---:|---|
| 新诊所预约项目；CCB + Claude/Codex/OpenCode | 2 | 14 | 16 | 17 | PASS | 0 | BLOCKED：等待 checkpoint、六审与最终批准 |
| 既有 Python 任务 CLI；无 CCB + 单 Codex | 3 | 7 | 17 | 以注册表为准 | PASS | 0 | BLOCKED：独立审查发现仍未闭环 |
| 大型企业知识审批；Claude 规划 + Codex 实现 + 独立 Claude Reviewer | 2 | 12 | 14 | 18 | PASS | 0 | BLOCKED：等待 checkpoint、六审与最终批准 |

三个场景都先询问 CCB、可用 AI、规划/合并角色、并行、Git 和定时审查，再拆任务；用户
回复先逐字追加到 `U-*`，然后同步环境、开放问题、状态和追踪。任何场景都没有提前改业务
文件，也没有在门禁前生成 `07-goals/` 或 `08-automation/` 最终产物。

## 六代理与负向门禁

既有项目执行了六个独立 round-1 审查，得到 1 个 RED 和多个 P0/P1/P2；审计保持
`BLOCKED`。规划修订后又用新上下文复审，继续发现授权、测试、I/O、架构和锁状态机问题，
证明审查没有被预设为 GREEN。

隔离负向测试也按预期停止：

- 一个 Reviewer 意外读到禁止材料后主动声明上下文污染，未生成可冒充 `clean` 的报告；
- 未先在 `CURRENT_STATE.md` 激活精确报告锁时，一个 Reviewer 将报告判为无效，另一个在
  写文件前停止；
- 手工分发时遗漏机器字段的报告被 gate-ready 审计拒绝；
- `degraded` 上下文、缺失 immutable 状态、错误 hash/bytes、复用路径都不能通过最终审计。

这些发现直接促成了最终版的审查分发表、串行锁交接状态机、同一行报告字段和 raw
SHA-256/bytes 来源校验。最终回归还要求六个唯一 run/thread ID、dispatch nonce 和统一
planning source snapshot；平台不给外部证明时只标记内部来源证据，不夸大为不可伪造证明。

## 最终差异复审

独立 Reviewer 对完整差异做最终复审，先复现出五项 P1：受保护原话 rename、执行提示词
未激活任务、嵌套 shell/命令替换、hook manager 伪链和重复 legacy ID。修复后 Reviewer
逐项重放：rename 的 pre-commit 返回 1，两种 Bash 绕过返回 2，伪链 verify 返回 1，
重复 legacy ID 审计返回 1；五个执行提示词均要求写入前激活 canonical 任务。Reviewer
还在两个真实 linked worktree 中分别激活不同任务，确认 `current-task.json` 状态隔离，
并复跑完整 30 项单元测试。最终结论为 P0/P1 无。

## 最终产物验证

`test_complete_evidence_tree_passes_gate_ready_without_final_prompts` 构造具备六份 clean、
immutable、hash/bytes 可复算报告的门禁就绪项目，验证：

1. 门禁未 READY 时最终提示词保持不存在；
2. gate-ready 证据完整时第一阶段审计通过；
3. 用户确认精确绑定 U-*、确认片段和被审查的真实 Git checkpoint；
4. 根据已确认环境生成匹配的执行提示词、定时审查提示词和设置说明；
5. 可执行护栏安装并验证后，最终产物审计通过；
6. 任一未解析占位符都会重新阻断。

## 结论

前向测试覆盖了“先问、原话追加、禁止过早编码、完整追踪、无冲突任务、审查失败时阻断”
以及“READY 后才允许定时审查提示词”两条路径。旧项目刻意保留为 BLOCKED 样例，没有为了
得到绿色结果而改写 raw 报告或跳过重新授权。
