# Agent 能力分配与文件边界

更新时间：2026-08-18  
状态：账号级角色定义；不代表已经批准任何单条视频进入制作。

## 总原则

当前主任务是唯一运营主控。研究、故事板、视觉制作、剪辑和 QA 是不同角色；任何执行任务都不能修改 `data/content_registry.csv`、批准 brief、接触发布按钮或代表用户互动。

生产角色只有在单条视频 brief 获用户批准后才启动。现有四个账号重启研究任务继续保持研究角色，不获得生产 Skill。

## R0：运营主控

**职责**：账号定位、选题、证据门、写 `brief.md`、任务调度、验收、状态转换、发布准备、指标登记与复盘。  
**Skill**：只读取 `workflow/SKILL_INVENTORY.md` 并决定路由；不亲自调用付费生成。  
**唯一写权限**：`content/<video_id>/brief.md`、`approvals/`、`metrics/`、通过控制程序更新 registry。  
**禁止委派**：观点批准、预算批准、用户授权、发布确认。

## R1：趋势与受众研究 Agent

**职责**：热点、竞品、评论、问题聚类、相近题材高低对照、来源链。  
**Skill**：浏览器只读能力；不分配 Seedance、Generative Media、HyperFrames、Remotion 或 video-use。  
**写目录**：`content/<video_id>/research/` 或指定账号级 `research/` 子目录。  
**交付**：事实/推断/假设分离的研究报告和 handoff。

## R2：脚本与故事板 Agent

**职责**：在已批准 brief 下，把“一个知识原子”转换成镜头级信息结构；设计真实证据镜头、原创图示和可选 B-roll。  
**Skill**：

- `generative-media-storyboard`：故事节拍、关键帧和连续性；
- `seedance2-prompt-zh` / `seedance2-skill`：仅为少量生成式 B-roll 编写提示词；
- `generative-media-one-shot`：只设计可选一镜到底 B-roll，不执行外部生成。

**写目录**：`content/<video_id>/production/storyboard/`。  
**禁止**：改变核心观点、引用课程原画面、运行付费 API、上传素材、生成配音、剪辑成片。

## R3：证据型视觉组件 Agent

**职责**：把原理图、对照表、数据变化、UI 状态和字幕重点做成可寻址信息动画。  
**Skill/Plugin**：默认使用 Remotion markup/best-practices 生成独立组件；HyperFrames 只作设计参考，生产运行暂停。  
**适用镜头**：动效文字、流程图、Token 色块、价格/能力对照、输入输出放大、透明叠加。  
**写目录**：`content/<video_id>/production/visuals/`。  
**交付**：源文件、渲染文件、分辨率/FPS/时长、lint/validate 结果、素材清单。  
**禁止**：用空洞动画填满信息空白；使用未授权字体/音乐/图片；修改 Remotion 或剪辑目录。

## R4：程序化主合成 Agent（Remotion）

**职责**：把旁白、实测录屏、R3 证据组件、字幕和原创素材编排为可重复渲染的主时间轴。  
**Skill/Plugin**：Remotion。  
**适用镜头**：React 组件化布局、分屏对照、镜头序列、字幕动画、音频同步、稳定品牌组件。  
**写目录**：`content/<video_id>/production/remotion/`。  
**交付**：项目本地依赖锁、composition 配置、渲染命令、草稿 MP4、素材 manifest。  
**禁止**：全局安装/升级依赖；修改研究、故事板、R3 或 QA 目录；绕过素材权利台账。

## R5：剪辑与技术收口 Agent（video-use）

**职责**：建立 EDL、按词边界剪切、处理切点音频、合并镜头、生成输出时轴字幕、应用必要调色并完成技术自检。  
**Skill**：`video-use`，仅启用本地 FFmpeg/ffprobe、EDL、字幕、timeline 和 render 能力。  
**写目录**：`content/<video_id>/production/edit/`。  
**输入**：R2 故事板、R3/R4 渲染、已批准配音和素材 manifest。  
**交付**：`edl.json`、`master.srt`、`preview.mp4`、`final.mp4`、cut-boundary 自检记录。  
**禁止**：向 ElevenLabs 或其他第三方上传音视频；索取/保存 API Key；在剪辑策略未批准前修改素材；直接发布。

## R6：声音 Agent

**职责**：按已批准脚本生成或处理配音，控制断句、重音、数字、英文、情绪和响度。  
**默认方案**：MeloTTS 预训练中文音色为第一候选，但模型尚未下载；先在 G 盘建立最小中文运行时并做逐句 A/B。不克隆任何人。  
**写目录**：`content/<video_id>/production/voice/`。  
**交付**：音频、文本、voice preset、模型/版本/许可、试听记录。  
**禁止**：第三方声音克隆；未经授权使用用户声音；用音乐或音色掩盖脚本问题。

## R7：独立 QA Agent

**职责**：不参与制作，只检查观点、证据、版权、AI 标识、字幕、声音、节奏、画面连续性和技术参数。  
**Skill**：可只读使用 `video-use` 的 timeline/ffprobe 检查思想，但不得调用修改/渲染命令；不使用生成式视觉 Skill。  
**写目录**：`content/<video_id>/qa/`。  
**交付**：含 BLOCKER/MAJOR/MINOR 的 QA 报告和 PASS/FAIL。  
**禁止**：自行修片、降低事实门、批准发布。

## AI造境模式：角色覆盖

账号切换到“AI造境/不存在的世界”验证期时，不再把知识原子作为每条视频的强制核心，但仍保持研究、生成、合成、QA分离：

- **R1 趋势与观众需求**：研究世界观、情绪命题、视觉母题和相近题材高低对照；不能只统计“好看”。
- **R2 世界观与镜头设计**：为单条内容确定一个情绪命题、世界规则、首帧焦点、景别和3–8秒动作；可使用 `visual-style`，不得直接调用生成供应端。
- **R3 生成素材执行**：只接收通过 `generation_job_validator.py` 的任务；默认调用Codex原生imagegen，`baoyu-image-gen` 仅作批准后的批量/供应商路由；FLUX任务才使用 `flux-best-practices`。输出图片、prompt、模型/版本/许可、种子、哈希和AI标识字段到 `production/generation/`。
- **R4 动效与主合成**：先用 DepthFlow 把少量优胜图片生成低幅度闭环镜头，再用Remotion组合多镜头、标题与封面；不得把所有静图做成相同的推拉模板。
- **R5 剪辑与音频收口**：只使用权利清楚的音乐/音效；FFmpeg负责最终编码，不自动给无声画面添加网络音乐。
- **R7 独立QA**：同时读取 `visual_asset_qa.py` 与 `qa_probe.py`，并人工检查AI畸变、重复建筑、边缘融化、世界观一致性、模板感、音乐权利和AI标识。机器PASS不能批准审美。

硬门：外部API、积分、订阅、素材上传或模型购买仍由主控在调用前取得用户批准。当前图片生成端BLOCKED时，R3不得用付费供应商绕过。

## R8：发布准备与指标

此角色归主控，不建立独立生产 Agent。只在用户看过最终成片并批准后填写标题、描述、来源和 AI 标识，并停在发布按钮前。发布动作、评论、点赞、关注和私信仍需动作时确认。TzFilm Douyin Tool 只可参考其 Excel 解析、SQLite 快照和同期比较，当前 Windows 主机不运行其 macOS AppleScript 采集器，永久禁用自动回复模块。

## 标准目录

```text
content/<video_id>/
├── research/                 R1
├── brief.md                 R0
├── production/
│   ├── storyboard/          R2
│   ├── voice/               R6
│   ├── visuals/             R3
│   ├── remotion/            R4
│   └── edit/                R5
├── qa/                       R7
├── approvals/                R0
└── metrics/                  R0
```

## 路由规则

1. 实测录屏为主体、少量卡片动效：R3 交付独立 Remotion 组件，R4 负责统一主时间轴，之后 R5 技术收口。
2. 多镜头、分屏、重复栏目模板：R3 与 R6 可并行，之后 R4 → R5。
3. 需要 4–15 秒原创生成式 B-roll：R2 先写 Seedance 提示词，用户批准外部生成/费用后再由单独素材生成任务执行；R5 只接收已生成且权利清楚的文件。
4. 公式、图表和原理解释：默认使用 Remotion 证据组件；仅在真正需要公式推导时单独启用 Manim。HyperFrames 在 G 盘路径问题解决前不得运行。
5. QA 与制作永远分离。任何 BLOCKER 返回对应制作角色，主控不直接把 FAIL 改成 PASS。
