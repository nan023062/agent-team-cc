# Skill: 扫描记忆 entries

用 Python 脚本扫描 `memory/entries/`，按 frontmatter 字段过滤，输出结构化列表，避免 LLM 逐文件阅读。

## 使用时机

- 知识治理前：获取涉及某模块的所有 entries（过滤 tags 含 `module-<name>`）
- 模块健康考核：查看相关 session 积压量
- 任意需要从记忆中查找特定条目的场景

## 执行脚本

```python
import os, re, sys

entries_dir = "memory/entries"
filters = {}

# 命令行参数：key=value，如 agent=programmer tags=module-combat
for arg in sys.argv[1:]:
    if '=' in arg:
        k, _, v = arg.partition('=')
        filters[k.strip()] = v.strip()

def parse_frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            key = k.strip()
            val = v.strip()
            if val.startswith('[') and val.endswith(']'):
                val = [x.strip().strip('"\'') for x in val[1:-1].split(',') if x.strip()]
            result[key] = val
    return result

if not os.path.isdir(entries_dir):
    print(f"目录不存在: {entries_dir}")
    sys.exit(1)

results = []
for fname in sorted(os.listdir(entries_dir)):
    if not fname.endswith('.md'):
        continue
    fpath = os.path.join(entries_dir, fname)
    try:
        with open(fpath, encoding='utf-8') as f:
            text = f.read()
        fm = parse_frontmatter(text)
        match = True
        for k, v in filters.items():
            fval = fm.get(k, '')
            if isinstance(fval, list):
                if v not in fval:
                    match = False
                    break
            else:
                if fval != v:
                    match = False
                    break
        if match:
            results.append((fname, fm))
    except Exception as e:
        print(f"error: {fname}: {e}")

print(f"共 {len(results)} 条 entry（过滤条件：{filters or '无'}）\n")
for fname, fm in results:
    tags = fm.get('tags', [])
    tag_str = ', '.join(tags) if isinstance(tags, list) else tags
    print(f"[{fm.get('date', '?')}] {fname}")
    print(f"  agent={fm.get('agent', '-')}  tags={tag_str or '-'}")
    print()
```

**调用示例：**

```bash
# 查某 agent 的所有记录（HR 压缩用）
python3 /tmp/scan_memory.py agent=programmer

# 查涉及某模块的所有记录（架构师压缩用）
python3 /tmp/scan_memory.py tags=module-combat

# 查某 agent 涉及某模块的记录
python3 /tmp/scan_memory.py agent=programmer tags=module-combat

# 查所有含 decision 标记的记录
python3 /tmp/scan_memory.py tags=decision
```

## 注意事项

- 脚本只读 frontmatter，不读正文，开销极低
- 拿到文件名列表后，按需 Read 具体 entry 正文
- tags 过滤为精确匹配单个 tag，多条件为 AND 关系
