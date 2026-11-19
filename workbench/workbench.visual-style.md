---
name: "Douyin Content Workbench v4"
version: "1.1"
tags:
  - local productivity
  - video workflow
  - task console
author: "Codex"
source_url: "https://github.com/harry0703/MoneyPrinterTurbo | https://github.com/ATH-MaaS/Pixelle-Video"
created: "2026-08-23"

style_prompt_short: >
  一个以清晰任务流为核心的白色桌面工作台：MoneyPrinterTurbo 式参数卡、Pixelle 式三栏执行与预览、极少量珊瑚红强调色。

style_prompt_full: >
  Build a desktop-first Chinese content-production workbench with a clean #F5F6F8 canvas,
  crisp white #FFFFFF cards, dark graphite #20232A typography and a single coral-red #FF4B4B
  action color. Use Microsoft YaHei UI / Segoe UI, 8px spacing, 12px radii, subtle #E3E6EA
  borders, almost no shadow, and strong left-aligned hierarchy. The default page must read as
  one continuous workflow: account and project context, six-stage progress, plain-language task
  selection, grouped content/visual/audio/publish parameters, one unmissable full-width primary
  action, live task status and a 9:16 output preview. Borrow MoneyPrinterTurbo's large parameter
  cards and persistent generate bar, Pixelle's configuration/execution/preview separation, and
  social-auto-upload's account/platform payload boundary. Avoid decorative dashboards, oversized
  statistics, beige editorial styling, ambiguous cards, tiny text, gradients, floating actions,
  unexplained technical IDs, and buttons without a real handler.

colors:
  primary:
    - name: "Canvas Gray"
      hex: "#F5F6F8"
      role: "application background"
    - name: "Surface White"
      hex: "#FFFFFF"
      role: "cards, forms and preview surfaces"
    - name: "Graphite"
      hex: "#20232A"
      role: "primary text and navigation"
  accent:
    - name: "Action Coral"
      hex: "#FF4B4B"
      role: "primary buttons, selected controls and current workflow stage"
    - name: "Success Green"
      hex: "#19A15F"
      role: "completed stages and healthy engines"
  neutral:
    - name: "Border Gray"
      hex: "#E3E6EA"
      role: "card borders and separators"
    - name: "Secondary Gray"
      hex: "#69707D"
      role: "help text and metadata"

typography:
  display:
    family: "Microsoft YaHei UI, Segoe UI, sans-serif"
    weight: "700"
    style: "sentence case, compact, no decorative serif"
  body:
    family: "Microsoft YaHei UI, Segoe UI, sans-serif"
    weight: "400"
    style: "14px minimum, 1.55 line height"
  caption:
    family: "Microsoft YaHei UI, Segoe UI, sans-serif"
    weight: "600"
    style: "12px minimum, concise labels"
  rules:
    - "Never use body text below 12px"
    - "Technical IDs appear only as secondary metadata"
    - "Every form group starts with a plain-language title and one-line explanation"

layout:
  grid: "Desktop 12-column grid on an 8px base unit"
  alignment: "Flush left with consistent card headers"
  aspect_ratio: "desktop application with 9:16 media preview"
  notes:
    - "Default workspace combines context, progress, configuration, execution and preview"
    - "Primary action remains visible at the bottom of the configuration area"
    - "Responsive fallback becomes one column below 900px"

motion:
  transitions:
    - "120–180ms color and border transitions"
    - "short progress shimmer only while a task is running"
  animation_style: >
    Functional and restrained. No bouncing or decorative motion; status changes should be immediate.
  pacing: "fast and utilitarian"

mood:
  keywords:
    - "clear"
    - "reliable"
    - "production-ready"
    - "calm"
  era: "contemporary desktop SaaS"
  cultural_reference: "MoneyPrinterTurbo parameter console and Pixelle-Video task preview workspace"
  avoid:
    - "decorative dashboard cards"
    - "beige editorial styling"
    - "tiny type"
    - "multiple competing accent colors"
    - "controls whose result is unclear"

assets:
  reference_images:
    - "https://github.com/harry0703/MoneyPrinterTurbo/blob/main/docs/webui.jpg"
    - "https://github.com/ATH-MaaS/Pixelle-Video/blob/main/resources/webui.png"
  gsep_elements: []
  html_snippets: []
  color_palette_image:
    url: ""
---

## Design Principles

1. 每一屏先回答“现在在做什么、下一步是什么、按下按钮会发生什么”。
2. 项目状态、制作参数、执行日志和输出预览不得分散到互不关联的页面。
3. 一种颜色只承担一种语义：红色执行、绿色成功、黄色等待、灰色不可用。
4. 复杂能力逐步展开；默认表单只出现本次动作需要的字段。
5. 流程规范页先说明路线边界与人工关口，再展示可展开的证据门；不得把 18 个阶段压成难以扫描的表格。
6. 删除与恢复属于受保护操作，必须使用工作台内确认面板，清楚显示目标、影响、输入校验和 API 错误。

## HTML Application Mapping

- CSS variables map directly to the colors above.
- Form cards follow MoneyPrinterTurbo: title, help sentence, label, large input, optional advanced disclosure.
- Execution and preview follow Pixelle: configuration left, live status/history center, 9:16 preview right.
- The platform boundary follows social-auto-upload: account/platform context is explicit, but publishing remains a separately confirmed action.

## Extraction Notes

The references were inspected from the locally cloned repositories on 2026-08-23. The implementation adopts layout and interaction patterns, not their branding or project-specific copy.
