# CCB 协作模式

status: unconfirmed

coordinator:

merge_authority:

## Startup

1. 检测 CCB 的实际安装、命令和能力。
2. 读取根规则、状态、总任务和各 AI 任务文档。
3. 只分发依赖已满足、写入范围不重叠的任务。
4. 为每个任务登记 owner、write_lock、shared_interfaces 和 merge_order。

## Return contract

每个 agent 返回：

- task_id
- actual_changed_files
- verification/test results
- assumptions
- blockers
- interface changes
- recommended merge order
- feedback record

## Stop

出现文件/接口冲突、越权、RED、未满足依赖或未确认需求时停止对应任务并通知协调者。
