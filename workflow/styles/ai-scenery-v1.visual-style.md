---
name: "静谧异境 / Quiet Impossible Worlds"
version: "1.0"
tags:
  - AI造境
  - 成年人情绪价值
  - 克制电影感
  - 原创世界观
author: "抖音视频项目"
source_url: ""
created: "2026-08-18"

style_prompt_short: >
  为成年人创造“现实中不存在、但愿意停留片刻”的克制异境：可信的中国地貌与生活尺度，
  叠加一个清楚、可复述的世界规则；画面安静、电影化、有纵深，不做廉价霓虹仙境。

style_prompt_full: >
  Create an original vertical 9:16 cinematic impossible-world landscape for adult viewers.
  Begin with believable geography, architecture, weather, material wear, and human scale, then introduce
  exactly one visually legible impossible rule. Build strong foreground, middle ground, and background layers,
  with one unmistakable focal landmark and a restrained circular passage motif only when compositionally useful.
  Use mineral charcoal #1B2223, mist jade #6F8E83, warm stone #B8A78F, pale daylight #E8E3D8,
  and one sparse amber accent #D7A24A. Lighting is naturalistic and atmospheric; surfaces retain stone grain,
  damp wood, weathered metal, water tension, fog depth, and small imperfections. The mood is contemplative,
  slightly uncanny, emotionally restorative, and never childish. Leave the upper and lower interface-safe areas
  visually quiet; generated images contain no text because typography is added later. For motion, use slow,
  physically motivated parallax, drifting fog, water, foliage, light, or distant transit; keep loops subtle and
  stable. Avoid generic purple-cyan fantasy, excessive bloom, random particles, floating islands without a rule,
  ornamental clutter, plastic 3D surfaces, repeated buildings, melted edges, impossible perspective, human faces,
  celebrity likeness, brand marks, watermarks, existing characters, named artists, or imitation of a copyrighted
  franchise. The image should make a viewer able to say in one sentence both “where this is” and “what impossible
  rule governs it.”

colors:
  primary:
    - name: "矿物炭黑"
      hex: "#1B2223"
      role: "夜景、深层空间、轮廓锚点"
    - name: "雾玉绿"
      hex: "#6F8E83"
      role: "植被、水汽、系列识别色"
  accent:
    - name: "微光琥珀"
      hex: "#D7A24A"
      role: "唯一稀疏高光、引导视觉中心"
  neutral:
    - name: "暖石灰"
      hex: "#B8A78F"
      role: "建筑与土地中间调"
    - name: "薄云白"
      hex: "#E8E3D8"
      role: "日光、雾与字幕浅底"

typography:
  display:
    family: "Microsoft YaHei UI"
    weight: "bold"
    style: "短句、左对齐或依地平线锚定，最多两行"
  body:
    family: "Microsoft YaHei"
    weight: "regular"
    style: "中文口语短句，舒展行距，不覆盖视觉中心"
  caption:
    family: "Microsoft YaHei UI"
    weight: "regular"
    style: "小号来源与AI生成标识，清楚但不抢画面"
  rules:
    - "文字由后期添加，禁止让图片模型生成汉字"
    - "单屏只承担一个信息动作，不堆标题、解释和CTA"
    - "不得用超粗发光字、彩虹描边或幼态圆体"

layout:
  grid: "1080x1920竖屏；关键内容安全区x=92..888、y=150..1510"
  alignment: "视觉主体偏中轴但不死居中；地平线避开正中；文字服从画面动线"
  aspect_ratio: "9:16"
  notes:
    - "每幅图必须有可分离的前景、中景、背景，供景深运动使用"
    - "一幅图只设一个焦点和一个世界规则"
    - "右侧互动栏与底部文案区不放关键物体"
    - "封面先看景，再读一句命题；不做信息卡片"

motion:
  transitions:
    - "按自然遮挡完成的软切"
    - "雾、水面反光或暗部穿越"
    - "必要时直接硬切到尺度反差"
  animation_style: >
    低幅度、物理动机明确、首尾可闭合。优先环境微动和分层视差，镜头移动只服务于揭示世界规则；
    禁止全片统一推近、PPT式缩放、无意义摇摆或大幅横移暴露补边。
  pacing: "6至8秒单镜头可循环；15至24秒合集每2至4秒出现一次新信息或尺度变化"
  audio_cues:
    - "环境声优先：风、水、远处交通、木结构与低频空间感"
    - "音乐必须来源清楚；不以煽情钢琴掩盖画面信息不足"

mood:
  keywords:
    - "安静但不空洞"
    - "可信但不现实"
    - "成年人的短暂出走"
    - "可复述的世界规则"
  era: "近未来或时间不明，不绑定具体朝代"
  cultural_reference: "中国地貌与当代生活尺度的原创再构成；不模仿具体艺术家、影视或游戏IP"
  avoid:
    - "默认AI仙境、紫青霓虹、过量体积光和漂浮粒子"
    - "无规则的浮空城、巨大神像、美女背影和空泛治愈文案"
    - "动漫幼态、游戏登录页、壁纸站同质构图"
    - "重复建筑、融化边缘、假文字、错误倒影和尺度矛盾"

assets:
  reference_images: []
  gsep_elements: []
  html_snippets: []
  color_palette_image:
    url: ""

x_douyin:
  orientation: "portrait"
  canvas: "1080x1920"
  disclosure: "画面由AI生成；文案与后期由创作者完成"
  safe_zone: "x=92..888, y=150..1510"
  initial_formats:
    - "6-8秒无声或环境声循环"
    - "2-4张竖图图文轮播"
    - "15-24秒多世界合集"
---

## Design Principles

1. **先有规则，再有奇观。** 观众要能在一秒内看见异常，在一句话内复述异常。
2. **先可信，再超现实。** 地貌、材质、天气和生活尺度提供可信底座，只允许一个核心不可能条件。
3. **情绪价值不是空文案。** “想住进去”“想逃离现实”“想选择另一条人生”要由空间本身触发。
4. **一致性来自判断标准，不来自同一滤镜。** 系列可以换季节和地点，但保留克制用色、清晰纵深、单一规则和成年语气。
5. **AI痕迹必须被审查。** 技术规格通过不等于审美、语义或相似性通过。

## Production Mapping

- 图片生成：直接使用 `style_prompt_full`，再追加单条世界规则、地点、时间和镜头视角。
- DepthFlow：只给通过人工审美门且具有清晰三层纵深的图片生成低幅度闭环视差。
- Remotion：只承担文字、标识、节奏和多镜头编排，不用卡片遮住景观。
- 字幕/标题：后期叠加；图片内禁止文字、Logo和水印。

## Extraction Notes

本风格由账号定位与现有工具链约束原创建立，未从单一第三方作品提取，也未使用命名艺术家或品牌资产。
