# AI 风景账号工作流看板

更新时间：2026-08-19 12:59 +08:00

## 账号

- 定位：给成年人看的 AI 风景；现实能抵达，也有现实不存在的出口。
- 前 12 条：成年不可能世界 6 / 现实治愈 4 / 节点特辑 2。
- 当前已发布：3 条。
- 下一条：`ai-scenery-afterwork-exits-04`，状态 `BRIEF_DRAFT`。
- 当前唯一用户决策：是否批准第四条 brief；批准前不会出图。
- 第二个用户决策：是否批准 18 秒无旁白氛围视频试片策略；video-use Skill 要求策略确认后才执行剪辑。

## 三条作品当前观测

| 作品 | 发布时间 | 播放 | 赞 | 收藏 | 分享 | 划走率 | 平均浏览 | 吸粉 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 六个不可能世界 | 08-18 22:41 | 513 | 25 | 6 | 2 | 51.3% | 2.8 张 | 0 |
| 雨后现实治愈 | 08-18 23:44 | 266 | 22 | 2 | 1 | 70.5% | 1.7 张 | 0 |
| 七夕浪漫风景 | 08-19 02:37 | 59 | 4 | 1 | 0 | 62.79% | 2.1 张 | 0 |

这些是 12:51 的当前快照，不是同龄严格 A/B。第一条深度最好；第二条点赞率不低但划走和浏览深度较弱；三条目前均未产生关注转化。下一条因此保留高奇幻，只加入“下班后减压”这一变量。

## 生产路线

| 路线 | 状态 | 下一动作 |
|---|---|---|
| IMAGE_CAROUSEL | 生产 PASS，真实发布 3 条 | 第四条继续使用，保证单变量 |
| ATMOSPHERE_VIDEO | 工程 PASS | 另做 15–20 秒无旁白试片，不影响更新 |
| NARRATED_EXPLAINER | 生产 BLOCKED | 先解决 8–15 秒声音自然度，不制作完整旁白 |

## 固定角色

- 主控：当前会话；状态、批准、发布、指标。
- 选题/脚本：按条临时任务。
- 制作：brief 批准后启动。
- 独立质检：production manifest 完成后启动。

无需保留其他一次性任务。明天归档旧任务不会破坏工作流，所有证据均在 项目目录。

## 当前阶段门

`E0 PASS → E1 PASS → E2 PASS → E3 PASS → E4 BRIEF_DRAFT → 等待用户批准 → E5/P1 尚未启动`

入口文件：

- `workflow/MASTER_WORKFLOW.md`
- `workflow/ACCOUNT_POSITIONING_CARD.md`
- `workflow/CONTENT_ROUTE_RUNBOOK.md`
- `workflow/SESSION_POLICY.md`
- `workflow/TOOLCHAIN_STATUS.md`
- `workflow/WORKFLOW_TEST_REPORT.md`
- `workflow/COMPLETION_AUDIT.md`
