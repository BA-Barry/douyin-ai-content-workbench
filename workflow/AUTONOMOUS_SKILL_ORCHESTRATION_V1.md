# 工作台自主 Skill 编排与缺口关闭方案 v1

更新时间：2026-08-23  
目标：用户只定义内容目标并处理必要审批；工作台自动组合相关 Skills，Codex 执行并把证据写回项目。

## 1. 已实现架构

```text
内容目标 + 已批准 brief + registry 路线
              ↓
workbench/skill_router.py
              ↓
production/workbench_request.json
production/skill_plan.json
production/dispatch_receipt.json
              ↓
data/codex_dispatch_queue.json（幂等键 + 租约）
              ↓
Codex 任务领取并执行相关 Skills
              ↓
production / qa / approvals 可核验证据
```

- 不再提供“手选视觉 Skill”字段。
- 图文、氛围视频、旁白讲解采用不同组合；无关 Skills 明确写入 omitted。
- 图片默认内置 `imagegen`；视频默认进入私有 Flova Skill，再由其按任务选择 Seedance/H3 等支持模式；Remotion、HyperFrames 镜头语言和 video-use 只做后期。
- API 费用、私人素材上传、声音克隆、最终验收、prepare-only 和发布门不自动跨越。
- `src/codex_dispatcher.py` 已提供 enqueue / claim / complete / fail / retry；同一计划不会重复领取，超时租约自动回收。
- 只有 `IMAGE_CAROUSEL + READY_FOR_CODEX + Brief 已批准` 可进入 READY；视频和声音路线固定为 WAITING_APPROVAL。

## 2. 尚未关闭的缺口与准确解决方案

| 优先级 | 缺口 | 当前事实 | 关闭方案 | 验收证据 |
|---|---|---|---|---|
| P0 | 后台领取频率 | 已建立每 15 分钟图片调度心跳；热点/指标合并心跳已暂停 | 保持一次只领取一项；无 READY 时立即静默结束 | 自动化 `codex` 为 ACTIVE；空队列不访问抖音、不运行 QA、不生成 |
| P0 | Codex 图片生成桥 | 队列已能安全领取；还缺后台任务中的真实 imagegen 批次验收 | 后台调度获准后执行一条批准图片计划，回写原图、prompt、provider、hash | 工作台提交后出现真实原图、QA 和 COMPLETED 记录 |
| P0 | 视频生成回收闭环 | 私有 Flova Skill 已创建；工作台默认路由与 provider-agnostic `video_task_package.json` 确认卡编译已通过 Flova、Seedance 和 H3 路线测试；Seedance 官方 API 合同已核验 | 首个 Flova 生成前展示模型、时长、清晰度、引用素材及积分门；Seedance API 作为后续单镜头后端 | 尚需一次获批的真实项目状态、进度预览、导出文件与下载 hash |
| P0 | 任务状态机 | `READY→LEASED→COMPLETED/FAILED` 已落地 | 后续增加按步骤细分状态和单图重跑 | 崩溃恢复后状态一致，无双重执行 |
| P1 | 凭证与预算 | ElevenLabs/外部模型未配置 | 凭证只放操作系统或 Codex 安全凭证层；工作台只保存 provider 名、预算上限和批准 ID | 页面不返回明文；超过预算前阻断 |
| P1 | 素材与版本台账 | 现有 manifest 分散 | 统一 source/generated/final 资产 ID、父子关系、prompt、模型、许可、hash 和当前版本 | 任一成品可追溯到源素材和批准版本 |
| P1 | 自动 QA 与重试 | 技术探针已在，路线判断分散 | 把图像清晰度、视频黑帧/冻结/响度、字幕安全区、内容 QA 绑定计划步骤；只重跑失败图/镜 | QA JSON 绑定当前 manifest hash；BLOCKER/MAJOR=0 才能打包 |
| P1 | 趋势采集可靠性 | 浏览器控制不可用时会连续失败 | 为公开热榜/联想/官方活动建立稳定只读浏览任务、失败退避和来源可见性标记 | 连续快照、URL、采集时间、榜位/互动量、失败原因 |
| P1 | 发布准备 | 当前只能生成命令预览 | 接入 prepare-only 浏览任务：登录由用户处理，上传前即时确认，停在发布按钮前并截图/回执 | `publish_clicked=false`、页面身份、标题、素材顺序与包 hash 一致 |
| P2 | 指标反馈路由 | 指标窗口存在但样本仍不足 | H72 后把 KEEP/STOP/INCONCLUSIVE 和单变量建议写回下一条计划，不自动改账号定位 | 复盘引用真实快照；证据不足保持 INCONCLUSIVE |
| P2 | 账号级策略 | 已有本地账号切换 | 给每个账号增加允许路线、默认风格、预算、频率和禁区，路由器按账号过滤 | 切换账号后选题、Skill 计划和发布目标一致 |

## 3. 推荐实施顺序

1. 在出现已批准图片制作任务时，跑通一次“网页提交 → 队列领取 → 自动产出 1 张测试图 → 回写”；空队列不检查。
2. 统一资产台账和 QA 状态，再开放多图/多镜批处理。
3. 首次 Flova 视频生成在明确积分/费用后单独确认，并验收项目状态、预览、导出和下载回收。
4. 最后接 prepare-only、指标反馈和账号策略；正式发布始终保留即时人工确认。

## 4. 仍需用户决定的事项

- Seedance API 的账号区域与未来单条预算上限；
- 未来启用 ElevenLabs 时的单条预算上限与可上传素材范围。

在这些选择明确前，工作台会正常规划、排队和显示阻断原因，但不会伪装成已经开始后台生成。
