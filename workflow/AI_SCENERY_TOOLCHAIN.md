# AI造境内容工具链

更新时间：2026-08-18  
定位：为“AI造境/不存在的世界”账号提供可批量、可追溯、低人工介入的图片与短循环视频生产链。

## 当前结论

- **静图后处理与动效链：PASS。** DepthFlow、FFmpeg、机器QA和既有Remotion主合成可用。
- **图像生成供应端：TECHNICAL_PASS / USER_AESTHETIC_REVIEW_PENDING。** 对话内直接调用原生 `imagegen` 仍返回 HTTP 404；GitHub `baoyu-image-gen` 的 `codex-cli` provider 已使用当前 Codex 登录成功生成 A01，无需 API Key、未调用第三方付费接口。本地 SD 1.4 仅保留工程基线。
- **正式生产链：PARTIAL。** A01机器门通过、主控初审为 `PASS_WITH_NOTE`，仍需用户确认审美后才扩到其余5张；图片确认后再验证动效与整片链。
- **本地文生视频：拒绝作为主线。** RTX 3050 Ti 4GB 不适合重型视频模型，首批使用“高质量静图 + 可控景深运动 + 程序化合成”。

## 标准流程

```text
系列世界观/情绪命题
  → visual-style.md（风格规则）
  → generation_job.json（模型、许可、prompt哈希、预算门、AI标识）
  → 图片生成供应端
  → visual_asset_qa.py + 人工审美/语义复核
  → 深度图（自动估计或人工修正）
  → DepthFlow 生成3–8秒无缝景深循环
  → Remotion 编排字幕/多镜头/封面
  → FFmpeg规格收口
  → qa_probe.py + visual_asset_qa.py + 独立QA
  → MATERIAL_MANIFEST_TEMPLATE.csv
```

## 供应端路由

1. **默认：baoyu-image-gen / codex-cli。** 这是已安装的 GitHub Skill，通过当前 ChatGPT/Codex 登录调用 Codex 图片生成，不需要 `OPENAI_API_KEY`。2026-08-18 已真实出图；默认配置为9:16、单并发，缓存和临时文件固定在项目目录。
2. **诊断备用：对话内原生 imagegen。** 本次即时返回 HTTP 404，判断为调用通道问题而不是提示词问题；保留作后续复测，不阻断已验证的 `codex-cli` 路线。
3. **外部供应商：默认禁用。** `baoyu-image-gen` 虽支持 OpenAI、Google 等多供应商，但任何付费或把完整提示词/参考图发给第三方的调用仍须先取得用户批准。
4. **本地生成：工程基线已验证，SD 1.4生产路线已停止。** 锁定的 SD 1.4 可在 RTX 3050 Ti 4GB 上以 model CPU offload 生成504×896图片；首图与单帧证据prompt-only修复均人工FAIL，后者还出现假文字/伪水印。只保留环境与基准，不再换seed或扩批。ComfyUI与更大模型仍未获生产批准。
5. **FLUX：仅提示词规范。** `flux-best-practices` 已安装；没有明确选择FLUX供应端时不得假装已使用FLUX，更不得在4GB显存上下载完整FLUX权重。

## 已安装组件

| 组件 | 项目路径 | 状态 | 生产权限 |
|---|---|---|---|
| visual-style Skill | `.\skills\visual-style` | 结构通过 | 可建立账号风格文件；不得直接复制第三方品牌资产 |
| flux-best-practices Skill | `.\skills\flux-best-practices` | 结构通过 | 仅在FLUX任务使用 |
| baoyu-image-gen Skill | `.\skills\baoyu-image-gen` | `codex-cli` live PASS | 当前默认供应端；无需API Key；外部付费provider禁用 |
| DepthFlow 1.0.0 | `.\projects\ai_scenery_tooling\DepthFlow` | 真实渲染通过 | 只处理已通过权利门的本地图片 |
| AI造境运动环境 | `.\envs\ai_scenery_motion` | `pip check`通过 | CPU PyTorch；OpenGL渲染使用本机3050 Ti |
| 景深缓存 | `.\cache\ai_scenery_motion` | 项目目录覆盖通过 | 不得回退到用户目录 |

Codex发现目录中的三个新Skill是 Junction，实体仍位于项目目录。首次导入DepthFlow产生的32KB 系统级目录缓存已原样迁移到 `.\cache\ai_scenery_motion\migrated_c_depthflow_20260818`，原路径不存在。

## 关键脚本

- `src/ai_scenery/generation_job_validator.py`：生成前合同门；付费API没有预算批准文件时失败。
- `src/ai_scenery/render_parallax.py`：低幅度、首尾闭合的景深循环渲染。
- `src/ai_scenery/run_depthflow.ps1`：把缓存、模型目录、临时目录和FFmpeg固定到项目目录。
- `src/ai_scenery/visual_asset_qa.py`：检查图片完整性、运动量、编码规格和近似循环闭合；不声称判断审美。

## 质量门

### 图片

- 9:16或可安全裁成9:16；最终不少于1080×1920；
- 不含未授权参考图、角色、品牌、艺术家模仿或水印；
- 前景/中景/背景可分，视觉中心明确；
- 人工检查建筑重复、边缘融化、纹理复制、错误透视和“默认AI仙境”同质化；
- 记录模型、版本、prompt哈希、种子、参考素材权利和AI标识。

### 短循环

- 首尾运动路径闭合；不得用大幅平移暴露空洞边缘；
- `visual_asset_qa.py` 的 motion 与 loop seam 通过；
- `qa_probe.py` 无黑场；冻结检测只作信号，不能把缓慢景深运动误判为内容失败；
- 音乐单独进入权利台账，不能因“平台可搜到”就假定可跨用途商用。

## 首批生产策略

- 先批量生成静图候选，只把通过审美与结构门的少数图片动画化；
- 首批视频以3–8秒可循环镜头为素材单元，再由Remotion组成15–30秒世界片段；
- 不安装本地文生视频模型；不启用RIFE，除非真实外部视频暴露帧率问题；
- Real-ESRGAN只固定源码，不默认超分，避免细节幻觉与过锐化；
- 任何Skill演示成功都不等于图片供应端、预算、版权或发布已经批准。

## 当前唯一硬缺口

图片生成供应端已经恢复。当前门只剩用户对 A01 的审美确认：若接受，则用同一 Skill 生成其余5张并进入盲评；若不接受，先只调整 A01 提示词/构图，不扩批。当前成功输出为941×1672，接近9:16但不是原生2K，发布候选需在审美通过后确定性缩放到1080×1920。
