# 工作流数据契约

更新时间：2026-08-19  
状态：v3；字段增加需由主控修改模板并重新运行审计，执行 Agent 不得自行改名或删列。

## 正式契约

| 契约 | 模板 | 生产者 | 主控用途 |
|---|---|---|---|
| 研究原始信号 | `workflow/templates/RAW_SIGNALS_TEMPLATE.csv` | R1 | 保存原始公开证据；事实、推断、假设必须用 `claim_kind` 分列 |
| 脚本来源台账 | `workflow/templates/SOURCE_LEDGER_TEMPLATE.csv` | R1/R2 | 让每个外部 claim 指向可复核来源、定位符与权利状态 |
| 证据优先镜头表 | `workflow/templates/SHOT_LIST_TEMPLATE.csv` | R2 | 每个镜头必须回答观众问题并承担一个 `proof_job` |
| AI造境生成任务 | `workflow/templates/AI_SCENERY_GENERATION_JOB_TEMPLATE.json` | R0/R2拟定，R3执行 | 在生成前锁定供应端、模型/许可、prompt哈希、种子、参考素材、预算批准和AI标识 |
| 素材与权利清单 | `workflow/templates/MATERIAL_MANIFEST_TEMPLATE.csv` | R3–R6 | 记录本地哈希、来源、许可、引用区间、AI 使用和人工复核 |
| 假设卡 | `workflow/templates/HYPOTHESIS_CARD_TEMPLATE.md` | 主控 | 锁定一个变量、基线、保持项和反证条件 |
| 路线计划 | `workflow/templates/ROUTE_PLAN_TEMPLATE.json` | 主控 | 在制作前选择唯一内容路线和失败回退 |
| 声音短样门 | `workflow/templates/VOICE_GATE_TEMPLATE.json` | 制作拟定、主控记录用户批准 | 锁定声音样本、权利/同意和自然度批准 |
| 音乐计划 | `workflow/templates/MUSIC_PLAN_TEMPLATE.json` | 制作拟定、主控记录实际选择 | 区分平台手选、本地许可、原创或无音乐 |
| 机器可读质检 | `workflow/templates/QA_RESULT_TEMPLATE.json` | 独立质检 | 绑定制作 manifest 哈希并重算开放问题 |
| 发布包 | `workflow/templates/RELEASE_PACKAGE_TEMPLATE.json` | 主控 | 锁定最终产物、顺序、文案和 QA 字节哈希 |
| 发布后指标快照 | `workflow/templates/POST_SNAPSHOTS_TEMPLATE.csv` | 主控 | 只追加 FIRST_VISIBLE/H24/H72；不可见留空，不用 0 代替 |
| 72小时复盘 | `workflow/templates/POSTMORTEM_72H_TEMPLATE.json` | 主控 | 区分事实/推断并决定下一单变量 |
| 自有作品评论需求 | `workflow/templates/OWN_COMMENT_SIGNALS_TEMPLATE.csv` | R0/R1 只读分析 | 不保存用户名；排除推广、作者自评和资料交换污染 |

六类CSV的字段说明与允许值工作簿位于最终交付目录的 `workflow_data_contracts_2026-08-18.xlsx`；AI造境JSON契约以模板和 `generation_job_validator.py` 为准。

## 使用规则

1. 每个新文件先复制模板表头，再追加数据；不要直接在模板写业务数据。
2. `source_url`、时间、ID 或页面不可见的指标留空并在说明字段解释，禁止编造或用 0 冒充。
3. `rights_status=BLOCKED` 的素材不能进入渲染；`human_review` 未通过的 AI 素材不能进入最终合成。
4. R1/R2/R3–R6 只写自己的内容目录；`PostSnapshots` 与正式 metrics 仍只由主控写。
5. TzFilm Douyin Tool 等外部采集器必须先映射到本契约，不能让外部数据库成为新的唯一事实源。
6. AI造境任务在调用生成端前运行 `src/ai_scenery/generation_job_validator.py`；`provider_mode=PAID_API` 且没有预算批准文件时必须失败。合同校验PASS不等于生成任务、审美或版权已经通过。
7. QA、final approval、prepare receipt 和 publish receipt 必须绑定同一 release package 哈希；历史作品只能标 `LEGACY_RETROSPECTIVE`，不得事后伪造当时不存在的哈希批准。
8. 图片轮播和视频使用不同指标字段；不适用字段留空并说明，不把图片平均浏览张数映射成视频平均观看时长。
