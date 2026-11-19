# 视频生成服务接入决策 V1

更新时间：2026-08-23

## 结论

当前首选不是“即梦网页自动化”，也不是立即自建 Seedance API，而是对 **Flova 官方 CLI / Codex Plugin 做受控试点**。

理由：它是目前候选中唯一由平台官方提供、明确面向 Codex、覆盖项目创建—真实进度—素材—导出—下载的项目级接口。Seedance 官方 API 更适合后续成为精确、可计量的单镜头生成后端；即梦网页保留为人工低门槛备用。

这不是开放自动扣费。试点分为两段：

1. 零费用阶段：锁定版本和校验和、安装到 G 盘、让 Codex 识别 Skill、完成浏览器 OAuth、执行版本/登录/只读项目状态检查。
2. 费用阶段：每次生成前展示模型、时长、分辨率、预计积分或费用，由用户即时批准；没有批准不得提交生成。

## 候选判断

| 候选 | 官方接入 | 自动化能力 | 当前成本边界 | 决策 |
|---|---|---|---|---|
| Flova 官方 CLI | 官方 CLI、Skill、浏览器 OAuth | 完整项目、运行、真实进度、预览、导出、下载 | 免费档可安装体验；生成消耗积分 | 首选受控试点 |
| BytePlus ModelArk Seedance | 官方 REST/SDK 任务 API | 创建、查询、列出、取消/删除生成任务 | 按模型/分辨率/输入计量 | 后续直接后端 |
| 即梦网页 | 官方创作产品，无公开开发者合同 | 需要人工提交与下载 | 账号积分/会员依页面为准 | 人工备用 |
| pureheart/flova-video | 第三方浏览器脚本 | 页面预填和点击 | 不透明 | 不采用 |

## 已核验事实

### Seedance / ModelArk

- 字节跳动 Seed 官方页面将 Seedance 2.0 定位为支持多镜头叙事和音视频联合生成的视频模型。
- BytePlus ModelArk 已提供 Dreamina Seedance 2.5、2.0 教程与正式 Video Generation API。
- 创建接口为 `POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`；官方文档同时提供查询、列表和取消/删除任务接口。
- Seedance 2.5 当前模型 ID 为 `dreamina-seedance-2-5-260628`，最长一次可生成 30 秒，并可控制分辨率、比例、时长、格式、水印和音频。
- 2026-08-23 可见的官方限时价格：Seedance 2.5 1080p 约 USD 0.41/秒起；Seedance 2.0 mini 720p 约 USD 0.03/秒起。活动价有截止日期，工作台不能固化为长期价格。

### 即梦

- 即梦官方页是面向用户的一站式 AI 创作网页，公开提供文生图和视频生成入口；登录页当前出现 Seedance 2.0 创作模型。
- 在即梦公开主页、公开 sitemap 与创作页中未找到面向开发者的公开 API 文档或稳定接口合同。该结论仅表示“本轮未发现公开开发者 API”，不等同于断言内部没有接口。
- 因此即梦只进入 `prepare-only`：工作台可准备提示词、参考素材和参数，但不能依赖网页私有接口做无人值守生产。

### Flova

- Flova 官方页面明确提供面向 Codex 等 Agent 的 CLI；官方流程称可创建或继续项目、读取真实生成进度、使用 Flova Skills、导出和下载视频。
- 官方安装文档为 `https://cli.flova.ai/flovaCLI-setup.md`。Windows 安装脚本支持 `FLOVA_INSTALL_DIR` 和 `FLOVA_HOME`，可满足项目全部运行文件落 G 盘的规则。
- 当前官方 Windows 版本为 `v0.0.10`，发布包约 3.52 MB，官方 SHA-256 为 `89f9d319b3581df4e64e03f7b33bedb9242750b41e51aac6bcf187879ea3e746`。
- 官方月付价为 Free USD 0、Starter USD 19、Basic USD 49、Pro USD 199；视频生成按积分消耗。免费档存在不代表某一 Seedance 任务必然免费。
- Flova 服务条款禁止未授权 bot/抓取；官方 CLI 是应该使用的授权接入，第三方浏览器自动化不进入生产链。

## 受控安装结果（已完成零费用验收）

安装前已加载 `config/project-env.ps1`，并把下载、临时文件和运行目录定向到 G 盘。最终路径：

- CLI：`G:\抖音视频\envs\flova-cli\flova.exe`
- 官方 Skill：`G:\抖音视频\projects\flova-cli-official\skill`
- 运行状态：`G:\抖音视频\envs\flova-cli\state`
- Codex Skill 索引：`C:\Users\86135\.codex\skills\flova`，仅为指向 G 盘源文件的 Junction
- Flova 默认状态入口：`C:\Users\86135\.flova`，仅为指向 G 盘状态目录的 Junction

官方 `install.ps1` 已先下载到 G 盘再执行，没有使用管道直接执行远程脚本。Skill 的唯一内容源留在 G 盘。完整哈希和验证状态见 `research/tooling_refresh/video_provider/flova_install_manifest.json`。

零费用验收结果：

1. `flova version`：PASS，v0.0.10 / windows-amd64；
2. 安装脚本、二进制与 `SKILL.md` SHA-256 已记录；
3. 安装后的官方 `SKILL.md` 已完整读取；
4. Codex Skill 目录已通过 Junction 识别 `flova`；
5. 浏览器 OAuth 与 `auth status`：PASS，未读取凭据内容；
6. 未创建项目、未调用生成、未订阅、未充值。

## 工作台路由

- 图片轮播：Codex `imagegen` 路线保持不变。
- 视频项目：默认显示 `Flova 官方 CLI（受控试点）`；安装与登录门已通过，首次生成仍因积分/费用门不可自动提交。
- 单镜头或严格成本生产：未来可切换 `Seedance API` provider adapter。
- 即梦：保留“打开网页 + 复制任务包 + 用户手动提交”的回退按钮。
- 所有 provider 共用同一费用门、私人素材上传门、成片验收门和发布门。

## 下一确认门

首次视频生成前确认所选模型、时长、分辨率、预计积分或费用暴露。该确认只对单次任务生效。

## 官方来源

- [ByteDance Seedance 2.0](https://seed.bytedance.com/en/seedance2_0)
- [BytePlus Seedance 2.5 tutorial](https://docs.byteplus.com/en/docs/ModelArk/2607688)
- [BytePlus Video Generation API](https://docs.byteplus.com/en/docs/ModelArk/1520757)
- [BytePlus ModelArk pricing](https://docs.byteplus.com/en/docs/ModelArk/1544106)
- [即梦 AI](https://jimeng.jianying.com/)
- [即梦创作页](https://jimeng.jianying.com/ai-tool/home)
- [Flova CLI for AI Agents](https://www.flova.ai/en/agent-cli/)
- [Flova CLI tutorial](https://www.flova.ai/en/docs/features/flova-cli/)
- [Flova official setup](https://cli.flova.ai/flovaCLI-setup.md)
- [Flova pricing](https://www.flova.ai/en/pricing/)
- [Flova terms](https://www.flova.ai/en/terms-of-service/)
- [第三方 pureheart/flova-video](https://github.com/pureheart/flova-video)
