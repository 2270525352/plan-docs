# plan-docs

`plan-docs` 是一个面向 Claude、Codex、CCB、OpenCode 和单 AI CLI 的项目规划技能。它在开发前把用户的原始想法收敛成可追溯、可审查、可分工、可精确执行的文档树；规划通过独立审查后，才生成执行提示词和自动化审查提示词。

它不是对其他规划技能的简单改名。`plan-docs` 继续以 PM 需求讨论、递归产品模块树、按钮级交互、高保真原型、数据字典、API 和测试设计为核心，同时增加多 AI 分工、写入锁、执行反馈、六代理审查、Git checkpoint 和防偏离护栏。

## 核心流程

```text
用户原话留存
→ PM 式需求访谈
→ 开放问题与歧义消除
→ AI 可读需求
→ 产品及交互模块树
→ 架构与接口
→ 总任务
→ Claude/Codex/Reviewer/OpenCode 分工
→ 六代理文档审查
→ 修订和复审
→ 自动模式门禁
→ /goal 或普通执行提示词
→ Codex App 定时偏离审查
```

需求、任务、分工和门禁未确认前，技能不会进入自动执行模式。

## 保留的产品规划能力

- 逐字、追加式保存用户原话，使用稳定 `U-*` 编号；
- PM 视角讨论目标用户、场景、实用性、边界和验收；
- 模块 → 子模块 → 叶子交互的无限递归文档树；
- 按钮、字段、状态和错误反馈可独立成文；
- HTML/CSS/必要 JavaScript 的高保真可交互原型；
- 项目说明、架构、接口、术语、数据字典、API 和测试用例；
- 从模块依赖推导开发顺序，而不是凭空排序；
- 新项目从零规划和老项目非破坏性逆向初始化。

## 三种执行环境

### CCB 多 AI

检测实际 CCB 能力后，把边界完整的任务合同分发给 Claude、Codex 或 OpenCode。互不重叠的任务可以并行，但必须有协调者、最终合并权威、文件锁和共享接口约束。

### 无 CCB 的多窗口

Claude、Codex 和 Reviewer 可在独立窗口工作。根目录 `CURRENT_STATE.md` 记录当前阶段、任务、负责人、写入锁、各 AI 状态、commit、阻塞和下一步。

### 单 AI CLI

使用同一份总任务和稳定字段，按依赖顺序串行领取。每个任务都要完成验证、测试、反馈和 checkpoint 后才能进入下一个。

## 默认角色建议

| 角色 | 默认职责 |
|---|---|
| Claude | PM 访谈、产品/UX/交互、AI 提示词、总体架构讨论和文档 |
| Codex | 复杂工程实现、API/数据/算法、测试、调试、性能和构建验证 |
| Reviewer（Claude） | 独立干净上下文，只报告需求偏离、遗漏、歧义和冲突 |
| OpenCode | 用户选择后承担边界清晰、低耦合的实现、测试或资料任务 |

正式拆任务前，技能会让用户确认 CCB、可用 AI、规划者、协调者、最终合并者、并行策略、Git 策略和 Codex App 定时审查。

## 输出结构

```text
AGENTS.md
CURRENT_STATE.md
docs/plan-docs/
  00-source/
  01-requirements/
  02-architecture/
  03-product/
  04-tasks/
  05-execution/
  06-reviews/
  07-goals/
  08-automation/
  09-git/
  10-guards/
```

任务至少包含 `task_id`、owner、原话/需求来源、依赖、允许/禁止范围、共享接口读写模式、输入/输出合同、合并/冲突策略、精确步骤、输出、验收、验证/测试命令、写锁、Git checkpoint、反馈和停止条件。总任务与各 AI 文档逐字段一致；没有分配任务的角色必须显式写 `assignment_status: none` 及原因。

完整追踪链：

```text
用户原话 → 需求 → 产品/交互 → 架构/接口 → 总任务 → AI 子任务
→ 测试 → 审查 → 执行反馈 → Git commit
```

## 六代理审查

自动模式前，六个独立上下文分别审查：

1. 原话与需求对齐；
2. 遗漏、歧义、假设和可验收性；
3. 架构、接口、数据流和模块；
4. 任务、依赖、并行和文件冲突；
5. AI 职责边界；
6. 测试、Git、反馈、自动化和停止条件。

只有无 RED、无未处理 P0/P1 YELLOW、所有需求和任务都有完整追踪与验收、没有写入冲突且用户确认最终规划/分工后，门禁才为 READY。

## `/goal` 与普通提示词

技能不会声称所有 AI 都支持 `/goal`。它先检测当前环境或查阅当前官方资料：

- 支持且已确认时生成对应 `/goal` 提示词；
- OpenCode 默认使用普通任务提示词；
- 无法确认时使用普通串行或多窗口提示词；
- 最终执行提示词只在自动模式门禁通过后生成。

## 安装

### Claude Code

```bash
git clone https://github.com/2270525352/plan-docs.git ~/.claude/skills/plan-docs
```

### Codex

把仓库放入 Codex 可发现的技能目录，或在当前会话中直接使用此目录的 `$plan-docs`。

## 使用

示例：

```text
用 plan-docs 帮我规划一个面向设计团队的素材审批系统。先和我讨论需求，不要写代码。
```

技能先安全合并目标项目根协调文件：

```bash
python3 <skill-dir>/scripts/plan-docs-bootstrap.py install --project <project>
```

需要初始化规划骨架时：

```bash
python3 <skill-dir>/scripts/plan-docs-bootstrap.py install --project <project> --init-tree
```

`--init-tree` 不创建最终 `/goal` 和自动化提示词；它们要等门禁通过。

执行前用任务文档激活运行态，避免手工把字段抄错：

```bash
python3 <skill-dir>/scripts/plan-docs-activate-task.py \
  --project <project> \
  --task-doc docs/plan-docs/04-tasks/Codex任务文档.md \
  --task-id TASK-001
```

门禁和最终提示词分两步审计，避免用尚未允许生成的提示词反过来证明门禁：

```bash
python3 <skill-dir>/scripts/plan-docs-audit.py --project <project> --require-gate-ready
# 门禁通过后生成 07-goals/ 与 08-automation/
python3 <skill-dir>/scripts/plan-docs-audit.py --project <project> --require-final-artifacts
```

## 护栏

```bash
python3 <skill-dir>/scripts/plan-docs-guards.py install --project <project>
python3 <skill-dir>/scripts/plan-docs-guards.py verify --project <project>
```

脚本会结构化合并 Claude settings，并保留已有配置。已有 hook manager 或 linked worktree
共享默认 hooks 时不会覆盖配置；它会报告待串联状态。用
`git rev-parse --git-path hooks` 找到实际 hooks 目录，把三个 Plan Docs hook 显式串入现有
manager 后，用 `verify --allow-existing-hooks-path` 验证，再通过自动模式门禁。

## 旧版迁移

旧版 `docs/用户原话.md`、`docs/00-项目说明书.md` 到 `docs/08-测试用例.md` 及 `docs/modules/` 不会被移动、删除或覆盖。新版在 `docs/plan-docs/` 建立规范树，通过 legacy 映射逐项迁移和确认；旧用户原话保持原样。

## 开发验证

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py .
python3 -m unittest discover -s tests -v
python3 scripts/check-markdown-links.py .
```

## License

[MIT](LICENSE)
