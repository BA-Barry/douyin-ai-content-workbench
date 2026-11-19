# 独立任务调度表

更新时间：2026-08-18  
唯一运营主控：当前账号定位任务

| 任务 | thread_id | 文件所有权 | 主要目标 | 禁止动作 |
|---|---|---|---|---|
| 抖音工作流控制面 v2 | `01a01422-8fd2-7281-b29a-446aad0e6322` | `src/workflow_control.py`、`src/workflow_gate_v2.py`、控制面模板/测试/文档 | 批准绑定哈希、机器可读QA、视频级研究门、统一production manifest | 不改registry/events/content/正式审批指标，不访问外部页面 |
| 抖音指标与监控 v2 | `01a01422-939d-7d82-9445-93bd0c324eae` | `src/pipeline_tools/post_snapshot_importer.py`、`src/metrics_v2.py`、指标模板/fixture/测试 | 空值语义、只追加快照、2h/24h/72h调度、匿名评论入口 | 不改workflow_control/publish_gate/正式metrics，不登录抖音 |
| 抖音发布准备安全链 | `01a01422-9606-7973-93c5-c54a8a9ab678` | `src/publish_gate.py`、`src/prepare_only.py`、发布模板/模拟器/测试 | hash绑定payload、prepare-only、幂等与失败关闭 | 不打开抖音、不上传、不登录、不点击发布、不写正式approval |

## 调度规则

- 三条任务共享 `.`，但不能修改彼此所有文件。
- 每条任务必须先运行定向测试，再运行全项目测试与 `workflow audit`。
- 完成后只提交摘要与产物路径；当前主控读取证据后再决定是否合并为正式工作流。
- 配音、ASR、完整成片与外部生成按用户决定暂停，不分配任务。
- 清理或归档任务前先向用户列出候选并取得确认。
