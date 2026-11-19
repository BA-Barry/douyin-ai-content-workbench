# 抖音内容主控工作流 v3

版本：3.0  
项目根目录：当前工作副本，或 `DOUYIN_PROJECT_ROOT` 指定的完整副本
唯一状态源：`data/content_registry.csv`  
原则：每一步有输入、输出、负责人、硬门和失败回退；聊天记录不是完成证据。

公开部署与当前能力以根 README 和 `docs/` 为入口。本规范保留维护者风景账号的运营案例；其中栏目配比、历史发布数量和工具记录不作为新使用者已经完成的配置或证据。首次使用先运行 `python manage.py init`，再建立自己的账号定位与研究。

## 1. 当前账号定位

前 12 条只验证一个账号承诺：

> 用 AI 造出成年人想短暂停留的风景：现实里想去的地方，和现实里不存在的出口。

- 受众：18–40 岁，需要短暂减压、壁纸收藏、轻幻想或情绪陪伴的成年人。
- 栏目：成年不可能世界 6 条、现实治愈 4 条、节点特辑 2 条；前三条已计入。
- 前 12 条不混发 LLM 教程。课程内容保留为独立候选分支，12 条后再评估。
- 关注理由不是“每天有 AI 图”，而是稳定获得看得懂的异境、可代入的现实角落和时间节点情绪场景。
- 不能保证涨粉；能控制的是稳定承诺、栏目连续性、一次只改一个变量和数据复盘。

详细冻结卡：`workflow/ACCOUNT_POSITIONING_CARD.md`。

## 2. 固定角色与写入边界

| 角色 | 负责 | 只写 | 禁止 |
|---|---|---|---|
| 主控 | 定位、选题、假设、brief、状态、用户批准、发布准备、指标、复盘 | `brief.md`、`approvals/`、`metrics/`、registry | 未经确认点击发布或代表用户互动 |
| 选题/脚本 | 增量研究、选题池、脚本、shot list 建议 | `research/`、`content/<id>/research/` | 改状态、批准、制作、发布 |
| 制作 | 图片、视频、声音、音乐方案、manifest | `content/<id>/production/` | 改 brief、批准、发布 |
| 独立质检 | 路线化机器/人工 QA | `content/<id>/qa/` | 修改制作产物、代用户批准 |

发布与指标不另建长期任务，由主控承担。会话策略见 `workflow/SESSION_POLICY.md`。

## 3. 三条内容路线

### 统一素材底座与双轨制作

- 图片制作和视频制作是两条独立生产线；项目创建后路线固定，禁止为了复用素材而在制作中静默改变 `content_type`。
- 两条生产线共用 `assets/library/` 素材库、账号定位、选题、发布准备和指标复盘。
- 图片路线允许完全无素材：主题和制作要求经相关视觉 Skill 与提示词导演编译后，直接进入 Codex 图片生成。
- 视频路线在分镜前后执行素材策略判断：`NONE / USE_EXISTING / GENERATE_KEYFRAMES / GENERATE_ELEMENTS / EXTRACT_FROM_REFERENCE / MIXED`。只有人物、产品、场景或首尾画面需要稳定时，才创建条件性图片锚点子任务。
- 已完成的图片项目要转视频时，新建关联视频项目；不得覆盖原图片项目的路线、发布包或指标。
- 素材必须登记来源、权利、参考角色、允许保留项、必须改变项、哈希和外部上传许可。公开参考不自动等于可发布素材。

### IMAGE_CAROUSEL（当前默认）

- 图片生成入口固定为 Codex 端；风格 Skill 负责提示词、系列一致性与验收规则，不自行调用未批准的第三方生成服务。
- 用户只写内容目标、视觉方向和不可接受项；`douyin-media-orchestrator` 与工作台路由器自动选择一个主视觉 Skill、`imagegen` 和 `douyin-wallpaper-export`，不要求人工逐个选 Skill。
- 每批数量由 brief 指定；当前已经验证 6–12 张 1080×1920 图片，图序即发布顺序。
- 需要封面、contact sheet、逐图 prompt/hash、拒绝记录、素材权利、机器 QA、独立 QA。
- 音乐默认 `platform_manual`，由发布页手选；不把来源不明音乐嵌入图片。
- 已由三条真实发布验证。

### ATMOSPHERE_VIDEO（生产试片阶段）

- 视频默认执行入口为项目私有 Flova Skill `抖音导演提示词编译器`；它根据已批准导演包选择 Flova 内的 Seedance 2.5、Seedance 2.0、MiniMax H3 或合适生成模式。用户明确指定即梦 / Seedance 或 H3 时，保留直达任务包路线。
- 已过审关键帧或参考图 → `video_task_package.json` 生成任务确认卡 → 用户确认当前服务商、模型/时长/清晰度/素材上传/积分 → 对应服务商每镜生成 → Remotion / video-use / FFmpeg 合成与修整 → 15–30 秒竖屏视频。
- Remotion、DepthFlow、video-use 和 FFmpeg 是后期工具，不得在未生成真实镜头时把动图或推拉效果冒充生成式视频。
- 默认无旁白；音乐使用平台曲库或有权利的本地音乐。
- 自动 Skill 计划默认组合私有 Flova Skill、`hyperframes-motion-language`、所需 Remotion 子技能和 `video-use`；只有存在对白、旁白或证据文字时才加入字幕流水线。
- 本地提示词编译与合成工程链通过，但 Flova 的创建项目、真实提交、预览回收和导出下载尚未完成一次获批的生产验证；因此当前仍是“生成确认卡已自动化、真实生成受控试点”，不能标为全自动生产 PASS。

### NARRATED_EXPLAINER（当前阻断）

- 事实脚本、来源台账、逐镜证据、字幕、旁白短样和声音权利缺一不可。
- 先做 8–15 秒声音样本；用户明确接受自然度后才允许生成完整旁白。
- 现有 MeloTTS/zero-BERT 仅工程可用，用户已拒绝自然度；默认不得进入正式生产。
- ElevenLabs 官方 Skill 已安装，但只代表操作规范可调用；没有 API Key、费用批准、声音权利和自然度短样 PASS 时，不得调用或标记为生产可用。
- 字幕由 `douyin-caption-pipeline` 自动组合实际转写来源、Remotion Captions、烧录和对齐 QA；Captions AI 没有验证通过的官方 Skill，不作为隐式依赖。

完整路线合同：`workflow/CONTENT_ROUTE_RUNBOOK.md`。

图片与视频的逐步输入、输出、人工门和工具分工见 `workflow/MEDIA_PRODUCTION_WORKFLOW_V1.md`。

## 4. 唯一阶段链与工作留痕

```text
E0 账号定位
→ E1 增量研究
→ E2 选题池
→ E3 单变量假设卡
→ E4 主控 brief + 用户批准
→ E5 路线计划 + 脚本/shot list
→ P1 生成合同与素材
→ P2 路线化制作 manifest
→ Q1 机器 QA
→ Q2 独立 QA JSON
→ R1 哈希锁定发布包
→ A1 用户最终验收并绑定发布包
→ R2 prepare-only 上传
→ R3 用户手动发布 + 回执
→ M1 FIRST_VISIBLE
→ M2 H24
→ M3 H72 + 复盘
→ N1 下一条只改一个变量
```

### E0–E5：选题与脚本

| 阶段 | 必须文件 | 通过条件 | 失败回退 |
|---|---|---|---|
| E0 | `workflow/ACCOUNT_POSITIONING_CARD.md` | 受众、承诺、栏目、禁区和复核点明确 | 重写定位或拆账号 |
| E1 | `content/<id>/research/research_delta.md` | 事实/推断/假设分开；事实有来源定位 | 补证据或降级为假设 |
| E2 | `research/SCENERY_TOPIC_POOL.csv` | 首图可描述、6 图可展开、最近基线和指标明确 | 改题或改路线 |
| E3 | `content/<id>/hypothesis_card.md` | 一个变量、保持项、反证条件、最小样本 | 标为探索或退回选题池 |
| E4 | `brief.md` + `brief_approval.json` | 首屏、收益、证据、风险、AI披露、声音/音乐策略明确 | 退回最早受影响阶段 |
| E5 | `production/route_plan.json` + `production/shot_list.csv` | 每张/镜只有一个主任务，有验收句和失败回退 | 修 shot list；内容原子变化则回 brief |

### P1–P2：制作

- 所有生成、素材、模型/provider、prompt、版本、哈希、权利和人工复核进入 `material_manifest.csv` 与 `production_manifest.json`。
- 提示词失败不能静默换供应商；付费 API、素材上传、声音克隆和购买音乐要单独确认。
- 图片只替换失败单图，保留原图、拒绝原因和替换关系。
- 技术成功不等于审美成功；不得用首图假装视频字段来迁就旧审计器。

### Q1–Q2：审核与质检

- 机器工具只报告规格、哈希和可探测异常。
- 独立 QA 的唯一状态输入是 `qa/qa_result.json`；Markdown 只是可读附件。
- `PASS` 或 `PASS_WITH_MINOR`、开放 BLOCKER=0、开放 MAJOR=0，且 QA 绑定当前 production manifest 哈希，才可给用户查看。
- 路线专属硬门不能互相替代：图文无需音轨，讲解视频必须有旁白与字幕。

### R1–R3：发布包、批准、上传和发布

1. `approvals/release_package.json` 先锁定 brief、路线、制作 manifest、QA、最终产物顺序和发布文案哈希。
2. 用户随后查看该发布包；final approval 必须绑定 package hash。任何图、顺序、文案、声音或 QA 变化都要重新打包并重新批准。
3. 浏览器自动化只做到 `prepare-only`，回执必须证明 `publish_clicked=false`。
4. 点击发布必须由用户手动完成或在动作发生前再次取得明确确认。
5. `publish_receipt.json` 至少记录 `published=true`、报告时间、发布方法和 package/prepare/approval 哈希；作品 URL 暂不可见可留空，但 FIRST_VISIBLE 前要完成身份匹配。

### M1–M3：指标和复盘

- 快照只追加、不覆盖；不可见留空，页面明确显示 0 才记 0。
- `FIRST_VISIBLE`：创作者中心第一次确认作品身份且数据可见，不再伪装为“2 小时”。
- `H24`：发布后 22–28 小时；超过 28 小时标 `LATE`，不插值。
- `H72`：发布后 68–84 小时；超过 84 小时标 `LATE`。
- 图片看：划走率、平均浏览张数、文案展开率、收藏/分享/转粉。
- 视频看：2 秒/5 秒留存、平均观看、完播、收藏/分享/转粉。
- 72 小时只回答本条假设；输出 `postmortem_72h.json` 和 `.md`，结论只能是 `KEEP / STOP / INCONCLUSIVE`。
- `src/postmortem_v3.py` 在 H72 或基线证据不足时必须保持 `INCONCLUSIVE`，不能为了给下一题而强行判定。
- 下一条只改一个主变量，明确其余保持项。
- 监控任务配置与边界见 `workflow/MONITORING_AUTOMATION.md`；它只读创作者中心并写快照，不执行任何对外互动。

## 5. 状态机

兼容旧枚举：

`IDEA → RESEARCHING → RESEARCHED → BRIEF_DRAFT → BRIEF_APPROVED → PRODUCING → QA_REVIEW → READY_FOR_USER → USER_APPROVED → PREPARED_IN_DOUYIN → PUBLISHED → REVIEW_2H → REVIEW_24H → REVIEW_72H → CLOSED`

其中 v3 对 `REVIEW_2H` 的解释固定为 `REVIEW_FIRST_VISIBLE`；后续代码迁移完成前不把它解释为精确 2 小时。

状态只能由主控通过 `src/workflow_control.py transition` 修改。阶段文件存在不等于状态通过；先运行硬门和审计。

## 6. 用户需要介入的最少节点

- 账号定位发生重大变化；
- brief 最终批准；
- 付费、素材上传、声音克隆或本人录音授权；
- 查看最终图片/视频/声音；
- 登录、验证码和权限提示；
- 发布前动作确认或用户手动点击发布。

其余研究、草案、制作协调、QA、指标整理和下一题建议由主控组织。

## 7. 每条内容的完成清单

- [ ] 定位版本、栏目与基线明确
- [ ] research delta 可核验
- [ ] 假设卡只有一个变量
- [ ] brief 用户批准
- [ ] route plan 与 shot list 冻结
- [ ] material/production manifest 完整
- [ ] 机器 QA 和独立 QA 通过
- [ ] release package 哈希锁定
- [ ] 用户最终批准绑定 package
- [ ] prepare-only 回执
- [ ] 发布回执与作品身份匹配
- [ ] FIRST_VISIBLE / H24 / H72 只追加
- [ ] 72h 复盘与下一单变量

## 8. 常用命令

```powershell
. '.\config\project-env.ps1'
& '.\envs\content\Scripts\python.exe' '.\src\workflow_control.py' audit
& '.\envs\content\Scripts\python.exe' '.\src\workflow_trace.py' --video-id <video_id> --output <trace_report.json>
& '.\envs\content\Scripts\python.exe' '.\src\release_package.py' validate --package <release_package.json>
& '.\envs\content\Scripts\python.exe' '.\src\metrics_v2.py' summary --video-id <video_id>
& '.\envs\content\Scripts\python.exe' '.\src\voice_gate.py' --contract <voice_gate.json>
& '.\envs\content\Scripts\python.exe' '.\src\music_gate.py' plan --file <music_plan.json>
```

旧文件 `TOOLCHAIN_STATUS_20260818.md`、`THREAD_ASSIGNMENTS_20260818.md` 和多角色实验记录保留作历史证据；运行时只认本文件、`CONTENT_ROUTE_RUNBOOK.md`、`SESSION_POLICY.md` 与新模板。

## 9. 本地工作台

- 普通入口：`workbench/start-workbench.ps1`；
- 强制离线入口：`workbench/start-workbench-offline.ps1`；
- 无服务器只读快照：`workbench/export-offline-workbench.ps1`；
- 架构与联网边界：`workbench/ARCHITECTURE_V2.md`。
- 工作台保存制作要求时自动写入 `production/skill_plan.json`；网页负责计划、队列和留痕，Codex 任务负责执行 instruction-only Skills。完整自动化缺口与关闭方案见 `workflow/AUTONOMOUS_SKILL_ORCHESTRATION_V1.md`。
- 素材库事实源为 `data/media_library.json`，文件位于 `assets/library/<asset_id>/`；项目绑定写入 `production/assets/asset_bindings.json`，素材策略写入 `production/asset_strategy.json`。
- 工作台只保留一个“制作中心”入口；新建时选择图片或视频，项目创建后自动锁定路线，并且只显示该路线允许的动作。图片和视频的底层生产线仍然独立。

工作台可以离线浏览选题、收藏候选、创建本地项目、检查 E0–N1 证据、查看素材和历史指标、运行审计并导出快照。趋势刷新、创作者中心新指标、上传和发布仍属于联网环节。工作台的阶段就绪度只是文件证据视图，不能替代 registry 状态转换、用户批准或发布确认。
