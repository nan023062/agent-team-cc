# Skill: 扫描 Agent 清单

用 Python 脚本扫描 `.claude/agents/` 目录，提取所有 agent 的 frontmatter，输出结构化清单，避免逐文件阅读。

## 使用时机

- 招聘前做重叠检查，确认是否已有匹配 agent
- 考核/培训前获取所有 work agent 列表
- 秘书询问当前有哪些可用 agent

## 执行脚本

```python
import os, re, sys

agents_dir = sys.argv[1] if len(sys.argv) > 1 else ".claude/agents"
CORE = {"architect", "hr", "auditor", "programmer"}

def parse_frontmatter(text):
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, _, v = line.partition(':')
            result[k.strip()] = v.strip()
    return result

agents = []
if not os.path.isdir(agents_dir):
    print(f"目录不存在: {agents_dir}")
    sys.exit(1)

for entry in sorted(os.listdir(agents_dir)):
    agent_dir = os.path.join(agents_dir, entry)
    if not os.path.isdir(agent_dir):
        continue
    agent_file = os.path.join(agent_dir, f"{entry}.md")
    if not os.path.exists(agent_file):
        continue
    try:
        with open(agent_file, encoding='utf-8') as f:
            text = f.read()
        fm = parse_frontmatter(text)
        agents.append({
            "id": entry,
            "core": entry in CORE,
            "name": fm.get("name", entry),
            "description": fm.get("description", "—"),
            "model": fm.get("model", "—"),
            "tools": fm.get("tools", "—"),
        })
    except Exception as e:
        agents.append({"id": entry, "error": str(e)})

core_agents = [a for a in agents if a.get("core")]
work_agents = [a for a in agents if not a.get("core")]

print(f"核心 Agent ({len(core_agents)} 个)")
print("=" * 40)
for a in core_agents:
    print(f"[{a['id']}]  {a['description'][:60]}")

print(f"\nWork Agent ({len(work_agents)} 个)")
print("=" * 40)
if not work_agents:
    print("（无）")
for a in work_agents:
    if "error" in a:
        print(f"[{a['id']}]  ⚠ 读取失败: {a['error']}")
    else:
        print(f"[{a['id']}]")
        print(f"  desc:  {a['description']}")
        print(f"  model: {a['model']}")
        print(f"  tools: {a['tools']}")
        print()
```

**调用方式：**

```bash
python3 /tmp/scan_agents.py .claude/agents
```

## 输出解读

| 字段 | 含义 |
|------|------|
| `id` | agent 目录名，即唯一标识 |
| `desc` | frontmatter description，秘书据此判断是否匹配 |
| `model` | 使用的模型 |
| `tools` | 允许的工具列表 |

核心 4 个（architect / hr / auditor / programmer）单独列出，不参与 work agent 匹配。

## 注意事项

- 脚本只解析 frontmatter，不读取 agent 正文，开销极低
- 若 agent 目录下缺少 `<id>.md`，该 agent 被忽略
- 输出结果供 HR 判断是否已有匹配 agent，不直接修改任何文件
