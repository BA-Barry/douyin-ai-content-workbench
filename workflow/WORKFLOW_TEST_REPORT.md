# 工作流 v3 验证报告

- 验证时间：2026-08-19 12:59 +08:00
- 环境：`.\envs\content`
- 运行前：已加载 `config/project-env.ps1`
- 结果：`36 tests / 36 PASS / 0 skipped / 0 failed`
- 项目审计：`workflow_control.py audit = PASS`
- Skill 校验：项目副本与 Codex 端 `ai-scenery-studio` 均 `Skill is valid!`

## 已真实覆盖

- 图片轮播无需伪造 video 字段即可通过路线门；不足 6 张会阻断。
- 讲解视频缺 narration 会阻断。
- QA 未绑定当前 production manifest 哈希会阻断。
- 修改发布包内任一文件后，release package 校验会阻断。
- final approval 未绑定 release package 会阻断。
- 正确的六图 package → final approval → prepare-only job 离线闭环通过，且 `publish_clicked=false`。
- 发布回执 `published=false` 会阻断。
- 指标来源证据缺失、身份 MISMATCH、重复快照、非法百分比会阻断。
- 不可见指标保持空值；互动率只在分子和播放量均可见时计算。
- creator-center CSV/XLSX 手工导入、中文百分比、重复检测、空值语义均通过。
- 8–15 秒声音短样、48kHz mono、样本哈希批准、合成声音权利和克隆同意门通过正反测试。
- 平台手选音乐禁止意外嵌入本地文件；发布曲目记录必须绑定 release package。
- H72 缺失时复盘保持 `INCONCLUSIVE`，不会提前制造结论。
- 项目目录 FFmpeg/ffprobe 的视频、无音频视频、黑帧/冻结/静音/响度探针通过。
- 素材权利、AI 来源、人工复核和 BLOCKED 权利门通过正反测试。

## 仍需真实内容验证

- `ATMOSPHERE_VIDEO` 只有工程 PASS；需用正式风景图做 15–20 秒无旁白试片并通过用户审美。
- `NARRATED_EXPLAINER` 因声音自然度继续生产阻断；不能用工程测试替代用户试听。
- 抖音曲库实际音乐信息需要在每次发布回执中记录。
- H24/H72 需要等真实时间窗口到达，不能用当前快照替代。

## 运行命令

```powershell
. '.\config\project-env.ps1'
& '.\envs\content\Scripts\python.exe' -m unittest discover -s '.\tests' -v
& '.\envs\content\Scripts\python.exe' '.\src\workflow_control.py' audit
```
