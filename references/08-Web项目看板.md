# 可选 Web 项目看板

Web 看板只帮助用户理解“项目在哪一步、为什么停在这里、接下来做什么”。它是独立 npm
伴生包，不是规划事实来源、编辑器、执行器或审计器。

## 启用规则

1. 在环境确认阶段记录 `web_dashboard: disabled | npx | installed`。
2. 用户未明确选择时，不检查 Node、不运行 npm、不创建 Web 文件。
3. 用户选择临时使用时，先确认 Node 可用，再运行：

   ```bash
   npx plan-docs-dashboard --project <target-project>
   ```

4. 用户选择长期安装时，展示准确命令并再次确认；不得静默全局安装。
5. 看板发布版本与 `plan_docs_schema` 不兼容时停止，不猜测迁移。

## v1 读取协议

`plan_docs_schema: plan-docs/v1` 写在根 `CURRENT_STATE.md` 的 `Current snapshot`。缺失该字段
时，看板可按兼容模式读取，但必须显示“未声明 schema”。

只读取这些项目内固定路径：

- `CURRENT_STATE.md`
- `docs/plan-docs/00-source/用户原话.md`
- `docs/plan-docs/01-requirements/AI可读需求文档.md`
- `docs/plan-docs/01-requirements/开放问题.md`
- `docs/plan-docs/03-product/产品及交互索引.md`
- `docs/plan-docs/03-product/测试用例.md`
- `docs/plan-docs/04-tasks/总任务文档.md`
- `docs/plan-docs/05-execution/current-task.json`
- `docs/plan-docs/05-execution/执行反馈日志.md`
- `docs/plan-docs/06-reviews/审查汇总.md`
- `docs/plan-docs/06-reviews/自动模式门禁.md`
- Git 的只读状态、日志和 checkpoint

事实优先级：确定性审计结果与 Git 证据 > `CURRENT_STATE.md` 当前快照 > 规范任务/需求文档 >
看板推导。推导值必须标为 `derived`，不能显示成门禁已经通过。

## 展示目标

首屏在五秒内回答：

- 当前阶段和总体状态；
- 当前任务、负责人和持续时间；
- 阻塞项目；
- 下一步；
- 需求、任务、测试、审查和门禁覆盖情况。

深入页展示原话到需求、产品、任务、测试、审查和 commit 的项目地图，以及只追加的事实时间线。
不使用无法解释的总进度百分比。

## 安全边界

- 默认只绑定 `127.0.0.1`，拒绝非本机监听和异常 Host；
- v1 只接受 GET，不提供文件写入、命令执行、审批、Git 变更或 Agent 启动；
- 固定路径读取必须限制在项目根，拒绝符号链接和超大文件；
- 不启用 CORS、遥测、云同步、数据库或安装时脚本；
- Web 解析失败时显示未知，不把空值解释为通过；
- Web 包不得复制、弱化或绕过 Plan Docs 的审计与护栏规则。
