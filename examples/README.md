# 本地数据初始化示例

公开仓库不包含真实账号、内容项目、审批、指标或运行任务。首次运行前，在仓库根目录执行：

```powershell
New-Item -ItemType Directory -Force '.\data' | Out-Null
Copy-Item '.\examples\data\content_registry.example.csv' '.\data\content_registry.csv'
Copy-Item '.\examples\data\account_profiles.example.json' '.\data\account_profiles.json'
Copy-Item '.\examples\data\account_content_map.example.csv' '.\data\account_content_map.csv'
Copy-Item '.\examples\data\media_library.example.json' '.\data\media_library.json'
```

这些文件只包含空登记表和通用示例账号。实际账号映射、草稿、任务、素材与指标均留在本机，并已被 `.gitignore` 排除。

