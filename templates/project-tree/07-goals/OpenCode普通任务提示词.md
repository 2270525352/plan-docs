# OpenCode 普通任务提示词

不假设 OpenCode 支持 `/goal`。仅在用户选择 OpenCode 后按任务逐条生成。

```text
任务：<TASK_ID>
owner: OpenCode
协调者：<COORDINATOR>
来源原话：<U-*>
来源需求：<REQ-*>
输入文档：<paths>
依赖：<TASK-* / commits>
允许修改：<exact paths>
禁止修改：<exact paths>
写锁：<exact paths>
共享接口：<API-*; read-only unless authorized>
输入合同：<stable contract IDs>
输出合同：<stable contract IDs>
合并顺序：<order>
冲突处理：<authority and action>
具体步骤：<ordered steps>
预期输出：<files/results>
验收标准：<criteria>
验证命令：<commands>
测试命令：<commands>
反馈记录：<FB-*>
Git checkpoint：<policy>
停止条件：<conditions>

不要改变需求、产品、架构或接口。完成后返回实际文件、命令结果、假设、阻塞和建议合并顺序。
```
