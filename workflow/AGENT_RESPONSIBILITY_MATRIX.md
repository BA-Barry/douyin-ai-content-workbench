# Agent 分工矩阵

## 唯一主控：当前任务

- 拥有账号定位、选题、正式 brief、状态转换、审批记录、发布准备、指标登记和复盘决策；
- 创建和调度其他任务，验收文件证据，处理角色之间的依赖；
- 唯一允许修改 `data/content_registry.csv` 与 `data/workflow_events.jsonl`；
- 发布、评论、点赞、关注、私信等对外动作必须在动作发生前取得用户确认。

## 热门视频研究 Agent

- 输入：账号方向、目标受众、研究问题、历史指标；
- 负责：目录采样、完整深看、高低热度对照、评论需求、结构规律、事实/推断/假设分离；
- 写入：`research/`、`content/<video_id>/research/`；
- 交付：目录快照、`reference_videos.csv`、`contrast_pairs.csv`、研究交接；
- 不负责：正式 brief、成片、QA结论、登记表、发布。

## 视频制作 Agent

- 输入：状态为 `BRIEF_APPROVED` 的 brief、研究交接、用户声音/授权素材；
- 负责：GitHub制作方法学习、生产链工程改造、分镜、录屏/素材、声音、字幕、封面、成片、production manifest；
- 写入：`content/<video_id>/production/` 和专属临时目录；
- 交付：storyboard、素材清单、音频、字幕、封面、成片、逐文件哈希、版权与AI生成清单；
- 不负责：选题批准、研究结论、独立QA PASS、登记表、上传发布。

## 独立质检 Agent

- 输入：批准后的 brief、production manifest、成片/封面/字幕；
- 负责：前2秒、5秒证据、节奏、字幕安全区、声音自然度、AI味、事实、版权、AI声明、技术规格；
- 写入：`content/<video_id>/qa/`；
- 交付：带时间点证据和严重度的 PASS/FAIL 报告；
- 不负责：修改成片、写 brief、改变状态、发布。

## 串行关系

`研究 → 主控写brief → 用户批准 → 制作 → 独立质检 → 用户批准 → prepare-only → 用户确认发布 → 主控监控与复盘`

研究可以与上一条视频的数据只读分析并行；制作与质检不得并行处理同一版本。
