# Skill: 扫描模块树

用 Python 脚本扫描项目内所有 `.aimodule/` 目录，输出结构化模块清单，避免逐文件阅读。

## 使用时机

- 需要了解当前项目的模块全貌（新建模块前的重叠检查、废弃分析、依赖梳理等）
- 需要更新 `index.md` 前确认现有模块路径
- 任何需要"先看全局再做局部"的场景

## 执行脚本

将以下脚本通过 Bash 运行，传入项目根目录路径：

```python
import os, json, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."

modules = []
for dirpath, dirnames, filenames in os.walk(root):
    # 跳过隐藏目录（.git、.claude 等）
    dirnames[:] = [d for d in dirnames if not d.startswith('.')]
    if '.aimodule' in dirnames:
        rel = os.path.relpath(dirpath, root).replace('\\', '/')
        if rel == '.':
            rel = '.'
        module_json_path = os.path.join(dirpath, '.aimodule', 'module.json')
        meta = {}
        if os.path.exists(module_json_path):
            try:
                with open(module_json_path, encoding='utf-8') as f:
                    meta = json.load(f)
            except Exception:
                meta = {"error": "module.json 解析失败"}
        modules.append({
            "path": rel,
            "name": meta.get("name", "—"),
            "owner": meta.get("owner", "—"),
            "description": meta.get("description", ""),
            "dependencies": meta.get("dependencies", []),
        })

print(f"共发现 {len(modules)} 个模块\n")
for m in modules:
    deps = ", ".join(m["dependencies"]) if m["dependencies"] else "无"
    print(f"[{m['path']}]")
    print(f"  name:  {m['name']}")
    print(f"  owner: {m['owner']}")
    if m["description"]:
        print(f"  desc:  {m['description']}")
    print(f"  deps:  {deps}")
    print()
```

**调用方式：**

```bash
python3 -c "
import os, json, sys
root = '.'
# ... 粘贴脚本主体 ...
" 
```

或将脚本写入临时文件后执行：

```bash
python3 /tmp/scan_modules.py <项目根目录绝对路径>
```

## 输出解读

| 字段 | 含义 |
|------|------|
| `path` | 相对于项目根目录的路径（`.` 表示根模块） |
| `name` | module.json 中的模块唯一名 |
| `owner` | 负责维护该模块知识文档的 agent |
| `desc` | 模块一句话定位 |
| `deps` | 代码层面依赖的其他模块名 |

## 注意事项

- 脚本只读取 `module.json`，不读取 `architecture.md` / `contract.md`，开销极低
- 若 `module.json` 缺失或解析失败，对应字段显示 `—` 或 `error`，不中断扫描
- 扫描结果作为后续操作（新建/废弃/拆分）的输入，不直接修改任何文件
