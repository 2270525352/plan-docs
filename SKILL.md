---
name: plan-docs
description: 把新项目的用户意图，或老项目经代码、接口、数据和测试证明的现状，与用户确认的目标收敛为可追溯、可审查、可分工并能直接驱动开发的文档树，再生成 Claude、Codex、Reviewer、CCB、OpenCode、单 AI CLI 与 Codex App 所需执行提示词。用于新项目需求访谈和从零规划、老项目增量改造或全量逆向接管、AS-IS/TO-BE/GAP 差异分析、PRD/架构/API/数据/测试设计、递归模块树、高保真原型、原子任务拆分、多 AI 分工、开发就绪审查、执行反馈、Git 检查点和防偏离护栏；只更新某类规划文档时也可单独调用。
---

# plan-docs

把用户原话和项目事实收敛为可追溯的产品、架构与执行合同。文档的完成标准是“足以安全开发”，不是文字完美；门禁通过后立即进入实现，并用代码、测试、反馈和 Git 证据持续校正文档。

## 不可违反的规则

1. 把用户原话视为最高级需求锚点。目标项目的 `docs/plan-docs/00-source/用户原话.md` 只保存用户原话和稳定记录编号 `U-001`、`U-002`……；严格追加，不改写、总结、润色、翻译、删除或重排。把 AI 推断、查证和解释写入 `AI推断与事实查证.md`。
2. 在需求、任务、AI 分工和用户确认完成前，不写实现代码，不启用自动执行，不生成最终执行提示词。
3. 先生成 `总任务文档.md`，再从中拆出各 AI 任务文档。每个子任务必须回溯到总任务、需求和原话。
4. 允许多个 AI 并行处理互不重叠的任务，但每个并行写任务必须使用独立 worktree，并有一个协调者和最终合并权威。同一 worktree 只有一个激活任务，同一最终文件同一时间只有一个写入者。
5. Reviewer 使用独立干净上下文，只报告，不静默修复；不得同时实现被其审查的任务。
6. 不凭空断言某个工具支持 `/goal`、定时任务、子代理或特定 hook。检测本地能力或查阅当前官方资料；无法确认时生成普通提示词。
7. 保护已有代码、文档、Git 改动、hooks、Claude settings 和 `AGENTS.md`。不 force push，不用无依据硬编码补需求。
8. 只让会阻塞开发、验收、安全或兼容性的 P0/P1 问题阻止门禁；P2 进入待办，不因措辞、格式或无开发影响的细节反复审查。
9. 长时间实际开发是允许的，但必须持续产生代码 diff、验证/测试、checkpoint 或明确 blocker；重复润色文档不能冒充执行进展。

## 启动与读取

1. 运行 `git status --short --branch`（若是 Git 仓库）并记录用户已有改动。
2. 判断并记录项目模式：
   - `greenfield`：从用户意图正向建设，现状视为尚未实现；
   - `brownfield/incremental`：老项目默认模式，只逆向本次变更影响链；
   - `brownfield/full`：仅在用户明确要求接管、补齐全量文档或大规模重构时全仓逆向。
   老项目必须先只读扫描现有代码、文档、接口、数据模型和测试，不能把代码现状自动当成目标需求。
3. 先运行幂等 bootstrap：

   ```bash
   python3 <skill-dir>/scripts/plan-docs-bootstrap.py install --project <target-project>
   ```

4. 每个普通规划/执行窗口按顺序读取：项目根 `AGENTS.md` → `CURRENT_STATE.md` → 用户原话 → 项目事实基线 → AI 可读需求 → 现状与目标差异 → 产品索引/架构 → 总任务 → 当前 AI 任务 → 执行反馈。独立 Reviewer 是例外：不得读取含历史审查结论的完整状态，只读 `CURRENT_STATE.md` 中从 `## Current snapshot` 到下一个二级标题前的有界快照、分发表中自己的单行和被分配的业务文档。
5. 按当前阶段读取对应 SOP；不要一次加载全部 references：

   - 访谈、原话、阶段门禁：[references/01-规划工作流.md](references/01-规划工作流.md)
   - 文档树、稳定字段、递归模块和追踪链：[references/02-文档体系与追踪.md](references/02-文档体系与追踪.md)
   - CCB、多窗口、单 AI 与角色边界：[references/03-多AI分工与执行.md](references/03-多AI分工与执行.md)
   - 六代理审查与自动模式门禁：[references/04-六代理审查.md](references/04-六代理审查.md)
   - `/goal` 适配、定时审查、Git 和护栏：[references/05-提示词自动化与Git.md](references/05-提示词自动化与Git.md)
   - 老项目兼容和迁移：[references/06-老项目与兼容迁移.md](references/06-老项目与兼容迁移.md)
   - 高保真原型：[references/07-高保真原型.md](references/07-高保真原型.md)
   - 用户选择可选 Web 项目看板时：[references/08-Web项目看板.md](references/08-Web项目看板.md)

## 阶段 0：确认环境与分工

在正式拆任务前，向用户确认并记录到 `05-execution/环境与分工确认.md`：

- 是否安装 CCB；
- 可用 AI：Claude、Codex、OpenCode、单 AI CLI；
- Claude 与 Codex/CCB 是否验证支持目标模式；把版本、时间、来源和结论写成已验证 `F-*` 证据，未验证时选择普通提示词；
- 主规划者和最终合并者；
- 是否接受推荐分工；
- 是否允许多 AI 并行；
- Git：自动提交、确认后提交、禁用提交；
- 是否启用 Codex App 定时独立审查；默认关闭，启用时确认频率和停止策略。
- 是否需要可选 Web 项目看板；默认 `disabled`，只在用户明确选择后给出 `npx` 或安装命令。
- `project_mode: greenfield | brownfield`；老项目再确认 `brownfield_scope: incremental | full`；
- 开发就绪审查默认采用一次完整六代理审查、最多一次定向复审、总计最多 12 次 Reviewer 调用；超出预算必须暂停并由用户明确批准。

给出默认推荐，但必须由用户确认或修改。信息尚未确认时可以继续访谈和草拟规划，不得正式分配执行任务或进入自动模式。

用户回复环境、分工或需求问题后，必须先完成“回复落盘检查点”，再扩展下游文档：

1. 把完整回复逐字追加为新的 `U-*`；
2. 立即把已确认值同步到 `环境与分工确认.md`，将 `confirmed_by_user` 和时间改为真实值；
3. `available_ais` 只能使用 `Claude`、`Codex`、`OpenCode`、`single-ai-cli` 这些稳定枚举，版本号和检测细节写入 `F-*`；
4. 更新 `开放问题.md`、`CURRENT_STATE.md` 与追踪矩阵；
5. 重读本轮用户原话，列出仍未同步的决定；清零后才进入下一阶段。

## 阶段 1：按项目模式建立需求与事实

1. 用 `scripts/plan-docs-append-user-words.py` 把每条需求、决定、修正和偏好逐字追加为
   稳定 `U-*` 记录；空树不预建占位 `U-001`。
2. 新项目站在产品经理角度讨论目标用户、真实场景、价值、边界、优先级、失败形态和可验收结果；把“尚未实现”记录为 AS-IS，并把全部实现工作写成 GAP。
3. 老项目先把代码/测试/接口可证明内容写入 `00-source/项目事实基线.md` 的 AS-IS；再让用户确认要保留、改变和新增的 TO-BE。`incremental` 只扫描受影响链，`full` 才建立全量基线。
4. 在 `01-requirements/现状与目标差异.md` 建立 `ASIS-* → REQ-* → GAP-* → TASK-*` 链。代码事实、用户目标和 AI 推断必须分开；冲突以开放问题交给用户决定。
5. 把歧义、冲突和待确认事项写入 `01-requirements/开放问题.md`；不要把默认猜测伪装成确认需求。
6. 获得用户明确确认后再冻结当前目标基线。

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
- `00-source/项目事实基线.md` 是 AS-IS 事实源，`01-requirements/现状与目标差异.md` 是 TO-BE/GAP 事实源；
- 微观文档确认后询问是否生成 HTML/CSS/JS 高保真可交互原型，不默认生成。

## 阶段 3：总任务与 AI 分工

先写 `04-tasks/总任务文档.md`，再拆出：

- `Claude任务文档.md`
- `Codex任务文档.md`
- `Reviewer（Claude）任务文档.md`
- 用户选择 OpenCode 时才创建 `OpenCode任务文档.md`

所有 `input_contracts` / `output_contracts` 先在 `任务合同注册表.md` 定义唯一
`CONTRACT-*`：生产者、消费者、实际制品、必需内容、完成条件、验证、兼容性和冻结状态。
只有名字而没有定义的合同不允许通过门禁。

每个可执行任务至少包含这些稳定字段：

```text
task_id
phase
owner
source_user_words
requirement_ids
change_refs
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

把任务拆成单一动作、可独立验证的原子单元。需要时细到一个字段、一次交互或一条 debug 语句。每个任务必须引用至少一个 `GAP-*`；禁止把互不依赖的多个动作塞进同一任务。

拆分完成后立即做一次闭环检查：每个已确认 `REQ-*` 都有实际存在的 `TASK-*` 与
`TEST-*`，总任务逐字段复制到且仅复制到一个 AI 文档；然后运行 gate-ready 审计并只把
“尚未执行六代理审查/最终用户批准”保留为预期阻塞。若还出现环境、追踪、任务合同或冲突
错误，先修正这些规划文档，不继续扩展细节，也不生成最终提示词。

并行前检查：

- 每个写任务使用独立 worktree，分别激活自己的唯一 `current-task.json`；
- 两个任务不写同一文件；
- 不同时修改同一接口或 schema；
- 依赖方向一致；
- 上游 `output_contracts` 与下游 `input_contracts` 一致；
- 已声明文件锁、共享接口、合并顺序和冲突处理。

各 AI 任务文档还必须在文件顶部声明 `assignment_status: active | none`。没有分配任务时使用
`none` 并填写具体 `no_tasks_reason`；不得用空文档代表“没有任务”。子任务必须逐字段继承
总任务合同，不能只复用 `task_id`。

## 阶段 4：有预算的开发就绪审查

使用 `06-reviews/Codex App 六代理审查提示词.md` 让六个独立代理分别检查：

1. 原话与需求对齐；
2. 遗漏、歧义、假设和可验收性；
3. 架构、接口、数据流和模块关系；
4. 总任务、依赖、并行安全和文件冲突；
5. AI 职责边界；
6. 测试、Git、反馈、自动化和停止条件。

先运行确定性审计并由协调者关闭可机械发现的问题，规划稳定后才执行一次完整六代理审查。平台不支持六个并发代理时，使用六次互不共享结论的新上下文。代理只写报告。

每个 finding 必须写出 `development_impact`、`blocking_task_ids` 和 `affected_paths`。无法指出对开发、验收、安全或兼容性的具体影响时只能标为 P2。P2 进入待办，不阻塞开发。

完整六代理审查默认最多一轮；修订后只重跑受影响 Reviewer，默认最多一轮定向复审。默认 Reviewer 总调用预算为 12。第二轮完整审查、第二轮定向复审或超预算都必须保持门禁 `BLOCKED`，停止自动循环并取得新的用户原话授权。

每次分发必须遵循 `审查分发与写锁.md` 的状态机：协调者先在该表和
`CURRENT_STATE.md` 激活唯一精确 raw 报告锁，然后停止写；Reviewer 验证锁后只写自己的
报告，返回 `submitted` 并退出；协调者再执行仅限锁交接的控制面转换，记录报告
SHA-256/bytes、标为 `immutable`，然后激活下一位。路径已存在、锁不匹配或上下文降级时
不得计入通过证据，重试必须使用新 round/path。

每次分发还要记录外部调度器返回的唯一 run/thread ID、随机 dispatch nonce 和统一的
planning source snapshot SHA-256，并由 raw 报告逐字段回传。离线审计会复算 snapshot、
报告 hash/bytes 和唯一性；若平台不给可验证的外部执行证明，只能把独立性标为“内部来源
证据”，不得声称获得了不可伪造的调度器证明。

Reviewer 的 preflight 只能提取 `CURRENT_STATE.md` 的有界 `Current snapshot`（遇到下一个
`##` 立即停止）和分发表中自己的单行；禁止整页读取状态日志、旧报告摘要或其他 Reviewer
行。若工具误读了这些内容，必须声明污染、停止且零写入。

## 阶段 5：自动模式门禁

只有同时满足以下条件才把 `06-reviews/自动模式门禁.md` 标记为 `READY`：

- 没有 RED；
- 没有未处理的 P0/P1 YELLOW；
- P2 已进入非阻塞待办；
- 所有需求都有任务与验收标准；
- 所有任务都有负责人、允许/禁止范围、验证命令、写锁和停止条件；
- 不存在文件或接口写入冲突；
- 环境、分工、Git 策略和协调者已由用户确认；
- 用户确认最终规划与分工；
- 根协调文件、执行反馈和护栏策略已就绪。
- 审查轮次与 Reviewer 调用没有超过用户确认的预算。

最终确认必须再追加成 `U-*`，且原话明确写出被批准的 40 位 Git checkpoint；门禁记录该
ID、含 checkpoint 的精确确认片段和批准时间。`auto`/`confirm` 策略要求 checkpoint 真实存在、是当前 HEAD 的祖先、
规划 source snapshot 未变化且工作树干净；`disabled` 只有在另一个精确 U-* 片段明确接受
无 Git 降级时才可继续。

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

再生成 Codex App 定时审查提示词和启用说明。默认关闭；用户启用时可建议每 30 分钟运行，但必须设置停止策略，推荐连续两次 GREEN 后停止。只检测并报告 GREEN/YELLOW/RED，不自动改代码或原话。不要静默创建自动化。

用户确认需要 Web 项目看板时，按
[references/08-Web项目看板.md](references/08-Web项目看板.md) 检查 Node 环境并启动独立
npm 伴生包。不得把 Web 依赖写入目标项目或技能核心，不得自动安装、联网暴露或把看板
推导状态冒充审计结论。

生成完成后安装并验证可执行护栏，再运行最终产物审计：

```bash
python3 <skill-dir>/scripts/plan-docs-guards.py install --project <target-project>
python3 <skill-dir>/scripts/plan-docs-guards.py verify --project <target-project>
python3 <skill-dir>/scripts/plan-docs-audit.py \
  --project <target-project> \
  --require-final-artifacts
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

   激活脚本只接受项目内规范 AI 任务文档，逐字段比对总任务，并重新运行 gate-ready 审计；
   外部任务文件、漂移副本和未过门禁的执行任务都会被拒绝。需求访谈期只有规范 `intake`
   任务可启用 append 权限。同一 worktree 只保存一个激活任务；并行写任务必须各自使用
   独立 worktree。

3. 把负责人、当前任务和写锁同步到 `CURRENT_STATE.md`，再运行 `git status`；
4. 只在 `allowed_scope` 内执行；
5. 运行验证和测试；
6. 追加执行反馈；
7. 对照原话、需求、接口和 diff 自检；
8. 按用户确认的 Git 策略建立 checkpoint；
9. 更新任务状态、最近 commit 和下一步。

任务运行可跨较长时间，不设置会截断正常开发的总时长上限；但 `CURRENT_STATE.md` 必须记录
`task_started_at`、`last_progress_at` 和 `last_progress_kind`，执行反馈必须记录实际改动文件、
验证/测试结果和 checkpoint。只有这些开发证据或明确 blocker 才算进展，单纯重复审查或润色
规划文档不算。

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
