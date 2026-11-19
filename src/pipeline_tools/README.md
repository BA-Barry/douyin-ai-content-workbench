# 本地流水线接口

这组接口只处理本地文件，不登录平台，不读取 Cookie，不调用外部 API，不上传、发布或互动，也不会下载模型。运行前必须加载项目环境：

```powershell
. '.\config\project-env.ps1'
$py = '.\envs\content\Scripts\python.exe'
```

当前实现仅依赖 Python 标准库，以及已经固定在 项目目录的 FFmpeg/ffprobe。运行时版本与哈希见 `workspace/pipeline_test_20260818/tooling/runtime.lock.txt`。

## 1. qa_probe

只读探测媒体参数，运行黑帧、冻结、静音与 EBU R128 分析，并对比分析前后的 SHA256。

```powershell
& $py '.\src\pipeline_tools\qa_probe.py' `
  '.\workspace\pipeline_test_20260818\tooling\results\qa_synthetic_black_silence.mp4' `
  --output '.\workspace\pipeline_test_20260818\tooling\results\qa_probe.json'
```

输出的顶层 `status=PASS` 表示所有探测器成功运行且文件未改变，不代表视频内容没有异常。异常证据位于 `analyses.*.intervals` 和响度字段，最终阈值由独立 QA 决定。探针不生成或替换被测媒体。

## 2. material_manifest_validator

严格核对冻结模板表头、必填值、绝对路径、文件存在性、SHA256、授权状态以及 AI 来源和人工复核字段。模板中的 `status` 是首版契约中的权利状态字段；值为 `BLOCKED` 必定失败。AI 素材必须给出模型、版本、prompt 哈希，并通过人工复核。

```powershell
& $py '.\src\pipeline_tools\material_manifest_validator.py' `
  '.\workspace\pipeline_test_20260818\tooling\fixtures\material_manifest_valid.csv'
```

退出码：`0=PASS`、`1=规则校验失败`、`2=程序或输入错误`。

## 3. post_snapshot_importer

只读取用户手动导出的创作者中心 `.csv` 或 `.xlsx`，映射到 `POST_SNAPSHOTS_TEMPLATE.csv`。不包含网页控制、登录或数据抓取。支持中文表头、万/亿、百分比、UTF-8/GB18030 CSV；页面不可见值保持为空。`field_availability` 只列出确实存在的指标。重复键为 `video_id + snapshot_type + captured_at`，命中即整批阻断且不写输出。

```powershell
& $py '.\src\pipeline_tools\post_snapshot_importer.py' INPUT.xlsx OUTPUT.csv
```

默认拒绝覆盖已有输出；只追加用 `--append`，明确替换测试输出用 `--overwrite`，两者不可同时使用。XLSX 只读取第一个工作表，支持共享字符串、行内字符串和已有缓存数值；不计算公式。如抖音后续更改导出表头，应先增加别名 fixture 和测试，不能静默猜测。

## 4. transcript_adapter

把已保存的 FunASR 或 faster-whisper JSON 统一为逐句、逐词秒级时间结构。它只转换结果，不导入推理包，不加载或下载模型。

```powershell
& $py '.\src\pipeline_tools\transcript_adapter.py' INPUT.json OUTPUT.json --backend funasr
& $py '.\src\pipeline_tools\transcript_adapter.py' INPUT.json OUTPUT.json --backend faster-whisper
```

FunASR 的常规 `start/end` 与 `timestamp` 按毫秒解释，只有显式 `start_s/end_s` 按秒解释；faster-whisper 按秒解释。语言缺失、空词、负时间、结束早于开始或时间不单调都会阻断。

## 测试

```powershell
. '.\config\project-env.ps1'
& '.\envs\content\Scripts\python.exe' -m unittest discover `
  -s '.\tests\pipeline_tools' -v
```

测试临时文件只在 `.\workspace\pipeline_test_20260818\tooling\results\test_tmp` 创建，结束后删除。所有持久化 fixtures 与结果位于同一 tooling 目录。
