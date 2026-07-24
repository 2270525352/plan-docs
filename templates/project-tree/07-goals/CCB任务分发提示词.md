# CCB 任务分发提示词

```text
先检测当前 CCB 的实际命令和能力，再分发，不凭空构造参数。

项目根：<PROJECT_ROOT>
协调者：<COORDINATOR>
最终合并权威：<MERGE_AUTHORITY>

读取总任务、AI 任务文档、任务依赖与并行计划、CURRENT_STATE 和自动模式门禁。
只分发 status=ready、dependencies 已满足的任务。
每个 agent 收到完整合同：task_id、owner、U/REQ 来源、input_docs、dependencies、allowed/forbidden scope、write_lock、shared_interfaces、input/output contracts、merge_order、conflict_resolution、exact_steps、outputs、acceptance、verify/test、feedback、checkpoint、stop_conditions。
只并发分发写入范围和接口不重叠的任务。
agent 返回实际改动文件、验证/测试结果、假设、风险、反馈记录和建议合并顺序。
协调者逐个检查范围、接口、冲突、测试、追踪链和 git diff 后合并。
出现 RED、冲突或未满足依赖时停止对应任务。
```
