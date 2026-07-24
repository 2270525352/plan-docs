---
name: plan-docs
description: 在项目开发前把用户的原始想法收敛为需求对齐、结构完整、可审查、可分工、可由多个 AI 精确执行的文档树，并在审查通过后生成 Claude、Codex、Reviewer、CCB、OpenCode、单 AI CLI 与 Codex App 自动化所需提示词。用于新项目规划、老项目逆向初始化、PM 式需求访谈、PRD/架构/API/数据/测试设计、递归模块树与按钮级交互、高保真原型、原子任务拆分、多 AI 并行分工、六代理审查、执行反馈、Git 检查点和防偏离护栏；用户只要求更新某一类规划文档时也可单独调用。
---

# plan-docs

把用户原话逐步收敛为可追溯的产品、架构和执行文档。先讨论并冻结规划，再审查；只有门禁通过后才生成最终执行提示词或进入实现。

## 不可违反的规则

1. 把用户原话视为最高级需求锚点。目标项目的 `docs/plan-docs/00-source/用户原话.md` 只保存用户原话和稳定记录编号 `U-001`、`U-002`……；严格追加，不改写、总结、润色、翻译、删除或重排。把 AI 推断、查证和解释写入 `AI推断与事实查证.md`。
2. 在需求、任务、AI 分工和用户确认完成前，不写实现代码，不启用自动执行，不生成最终执行提示词。
3. 先生成 `总任务文档.md`，再从中拆出各 AI 任务文档。每个子任务必须回溯到总任务、需求和原话。
4. 允许多个 AI 并行处理互不重叠的任务，但必须有一个协调者和最终合并权威。同一最终文件同一时间只能有一个写入者。
5. Reviewer 使用独立干净上下文，只报告，不静默修复；不得同时实现被其审查的任务。
6. 不凭空断言某个工具支持 `/goal`、定时任务、子代理或特定 hook。检测本地能力或查阅当前官方资料；无法确认时生成普通提示词。
7. 保护已有代码、文档、Git 改动、hooks、Claude settings 和 `AGENTS.md`。不 force push，不用无依据硬编码补需求。

## 启动与读取

1. 运行 `git status --short --branch`（若是 Git 仓库）并记录用户已有改动。
2. 判断新项目或老项目。老项目先只读扫描现有代码、文档、接口、数据模型和测试。
3. 先运行幂等 bootstrap：

   ```bash
   python3 <skill-dir>/scripts/plan-docs-bootstrap.py install --project <target-project>
   ```

4. 每个新窗口按顺序读取：项目根 `AGENTS.md` → `CURRENT_STATE.md` → 用户原话 → AI 可读需求 → 产品索引/架构 → 总任务 → 当前 AI 任务 → 执行反馈。
5. 按当前阶段读取对应 SOP；不要一次加载全部 references：

   - 访谈、原话、阶段门禁：[references/01-规划工作流.md](references/01-规划工作流.md)
   - 文档树、稳定字段、递归模块和追踪链：[references/02-文档体系与追踪.md](references/02-文档体系与追踪.md)
   - CCB、多窗口、单 AI 与角色边界：[references/03-多AI分工与执行.md](references/03-多AI分工与执行.md)
   - 六代理审查与自动模式门禁：[references/04-六代理审查.md](references/04-六代理审查.md)
   - `/goal` 适配、定时审查、Git 和护栏：[references/05-提示词自动化与Git.md](references/05-提示词自动化与Git.md)
   - 老项目兼容和迁移：[references/06-老项目与兼容迁移.md](references/06-老项目与兼容迁移.md)
   - 高保真原型：[references/07-高保真原型.md](references/07-高保真原型.md)

## 阶段 0：确认环境与分工

在正式拆任务前，向用户确认并记录到 `05-execution/环境与分工确认.md`：

- 是否安装 CCB；
- 可用 AI：Claude、Codex、OpenCode、单 AI CLI；
- Claude 与 Codex/CCB 是否验证支持目标模式；把版本、时间、来源和结论写成已验证 `F-*` 证据，未验证时选择普通提示词；
- 主规划者和最终合并者；
- 是否接受推荐分工；
- 是否允许多 AI 并行；
- Git：自动提交、确认后提交、禁用提交；
- 是否需要 Codex App 每 30 分钟独立审查。

给出默认推荐，但必须由用户确认或修改。信息尚未确认时可以继续访谈和草拟规划，不得正式分配执行任务或进入自动模式。

## 阶段 1：留存原话并做 PM 访谈

1. 把每条需求、决定、修正和偏好逐字追加为稳定 `U-*` 记录。
2. 站在产品经理角度讨论目标用户、真实场景、价值、边界、优先级、失败形态和可验收结果。
3. 把歧义、冲突和待确认事项写入 `01-requirements/开放问题.md`；不要把默认猜测伪装成确认需求。
4. 获得用户明确确认后再冻结当前需求基线。

## 阶段 2：建立产品与技术文档树

使用 `templates/project-tree/` 中的唯一规范模板，在目标项目建立：

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

保留并发展 plan-docs 的产品能力：

- `03-product/产品及交互索引.md` 是模块树和横向依赖的结构事实来源；
- `03-product/modules/` 支持模块 → 子模块 → 叶子交互无限递归；
- 按钮、字段、状态、边界或一次交互均可成为独立叶子文档；
- 架构、接口、数据字典、API、测试用例和原型必须引用需求/原话编号；
- 微观文档确认后询问是否生成 HTML/CSS/JS 高保真可交互原型，不默认生成。

## 阶段 3：总任务与 AI 分工

先写 `04-tasks/总任务文档.md`，再拆出：

- `Claude任务文档.md`
- `Codex任务文档.md`
- `Reviewer（Claude）任务文档.md`
- 用户选择 OpenCode 时才创建 `OpenCode任务文档.md`

每个可执行任务至少包含这些稳定字段：

```text
task_id
phase
owner
source_user_words
requirement_ids
input_docs
dependencies
allowed_scope
forbidden_scope
shared_interfaces
input_contracts
output_contracts
merge_order
conflict_resolution
exact_steps
expected_outputs
acceptance_criteria
verification_commands
test_commands
write_lock
git_checkpoint
feedback_record
stop_conditions
status
```

把任务拆成单一动作、可独立验证的原子单元。需要时细到一个字段、一次交互或一条 debug 语句。禁止把互不依赖的多个动作塞进同一任务。

并行前检查：

- 两个任务不写同一文件；
- 不同时修改同一接口或 schema；
- 依赖方向一致；
- 上游 `output_contracts` 与下游 `input_contracts` 一致；
- 已声明文件锁、共享接口、合并顺序和冲突处理。

各 AI 任务文档还必须在文件顶部声明 `assignment_status: active | none`。没有分配任务时使用
`none` 并填写具体 `no_tasks_reason`；不得用空文档代表“没有任务”。子任务必须逐字段继承
总任务合同，不能只复用 `task_id`。

## 阶段 4：六代理文档审查

使用 `06-reviews/Codex App 六代理审查提示词.md` 让六个独立代理分别检查：

1. 原话与需求对齐；
2. 遗漏、歧义、假设和可验收性；
3. 架构、接口、数据流和模块关系；
4. 总任务、依赖、并行安全和文件冲突；
5. AI 职责边界；
6. 测试、Git、反馈、自动化和停止条件。

平台不支持六个并发代理时，使用六次互不共享结论的新上下文。代理只写报告。协调者汇总、修订相关文档，再重新审查。

## 阶段 5：自动模式门禁

只有同时满足以下条件才把 `06-reviews/自动模式门禁.md` 标记为 `READY`：

- 没有 RED；
- 没有未处理的 P0/P1 YELLOW；
- 所有需求都有任务与验收标准；
- 所有任务都有负责人、允许/禁止范围、验证命令、写锁和停止条件；
- 不存在文件或接口写入冲突；
- 环境、分工、Git 策略和协调者已由用户确认；
- 用户确认最终规划与分工；
- 根协调文件、执行反馈和护栏策略已就绪。

任一条件失败时写明证据与阻塞项，保持 `BLOCKED`，不得生成最终执行提示词。

用确定性审计确认门禁证据，而不是只读取文档中的自报状态：

```bash
python3 <skill-dir>/scripts/plan-docs-audit.py \
  --project <target-project> \
  --require-gate-ready
```

命令失败时保持 `BLOCKED`。

## 阶段 6：生成执行提示词与护栏

门禁为 `READY` 后，根据已确认环境从 `templates/project-tree/07-goals/` 生成：

- Claude `/goal` 提示词；
- 检测确认可用时的 Codex 或 CCB `/goal` 提示词；
- OpenCode 普通任务提示词；
- 单 AI CLI 串行执行提示词；
- CCB 任务分发提示词。

再生成 Codex App 定时审查提示词和启用说明。默认每 30 分钟；只检测并报告 GREEN/YELLOW/RED，不自动改代码或原话。不要静默创建自动化。

生成完成后运行最终产物审计：

```bash
python3 <skill-dir>/scripts/plan-docs-audit.py \
  --project <target-project> \
  --require-final-artifacts
```

需要可执行护栏时运行：

```bash
python3 <skill-dir>/scripts/plan-docs-guards.py install --project <target-project>
python3 <skill-dir>/scripts/plan-docs-guards.py verify --project <target-project>
```

已有 hook manager 时不覆盖；按脚本报告进行显式串联或保留为待办。

## 阶段 7：执行反馈与 Git

每个执行任务遵循：

1. 重读根规则、状态、原话和任务合同；
2. 用确定性脚本把已确认任务合同激活为 `current-task.json` 运行态：

   ```bash
   python3 <skill-dir>/scripts/plan-docs-activate-task.py \
     --project <target-project> \
     --task-doc docs/plan-docs/04-tasks/<AI任务文档>.md \
     --task-id <TASK-ID>
   ```

3. 把负责人、当前任务和写锁同步到 `CURRENT_STATE.md`，再运行 `git status`；
4. 只在 `allowed_scope` 内执行；
5. 运行验证和测试；
6. 追加执行反馈；
7. 对照原话、需求、接口和 diff 自检；
8. 按用户确认的 Git 策略建立 checkpoint；
9. 更新任务状态、最近 commit 和下一步。

commit message 包含 `task_id` 和执行 AI。不得 force push、覆盖历史或混入无关格式化。

## 单独调用

用户只要求更新一个模块、接口、测试、追踪表或原型时，直接进入对应阶段，但仍须：

- 先追加新的用户原话；
- 读取上游文档和 `CURRENT_STATE.md`；
- 保留追踪编号和结构索引一致性；
- 不跨过用户确认与写入授权；
- 若请求将进入实现，仍须通过任务与自动模式门禁。

## 交付

报告生成/更新的文档、保留的旧内容、门禁状态、阻塞项、验证结果、Git checkpoint 和下一步。不要把模板占位符或未确认假设描述为已完成规划。
