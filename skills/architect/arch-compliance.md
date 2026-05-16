# Skill: 架构合规审查

两阶段执行：**脚本格式校验** → **LLM 语义分析**。脚本先行，机械可判定的问题不交给 LLM。

---

## 阶段一：脚本格式校验

加载整个知识库，对所有模块进行严格格式审查。

### 运行脚本

```bash
python skills/architect/scripts/arch-compliance.py <project-root>
# 或配置 config/projects.json 后直接运行（无需参数）
python skills/architect/scripts/arch-compliance.py
```

脚本自动完成：读取 `config/projects.json` → 读根模块 `index.md` → 加载全树 `module.json` → 执行所有格式检查 → 输出结构化报告。

### 格式检查项

**module.json 结构校验：**
- `name` 字段存在且为 kebab-case
- `owner` 字段存在且为有效 agent id
- `dependencies` 若存在，为字符串数组
- `includeDirs` 若存在，为字符串数组
- 无多余未定义字段

**文件完整性校验：**
- 每个模块目录存在 `architecture.md` 和 `contract.md`
- 根模块存在 `index.md`
- `index.md` 中的每条路径对应的目录确实存在且含 `.aiworkspace/`

**名称唯一性校验：**
- 所有模块的 `name` 字段全树唯一，无重复

**index.md 完整性校验：**
- 递归扫描项目目录，找出所有含 `.aiworkspace/` 的目录
- 与 `index.md` 路径列表对比：有无遗漏、有无多余

**includeDirs 物理重叠校验：**
- 收集所有模块的根目录 + `includeDirs`
- 检查是否存在同一物理路径被多个模块声明

脚本输出结构化错误列表，格式校验通过后方进入阶段二。

---

## 阶段二：LLM 语义分析

基于阶段一加载的知识库数据，进行需要推理的语义审查。

### 检查项

**循环依赖检测：**
- 构建依赖图（module.name → dependencies）
- 检测有向图中的环；发现即报告，必须解开，无商量余地

**幽灵依赖检测：**
- `dependencies` 中引用的模块 name 是否都存在于 index.md
- 引用了不存在的模块 → 幽灵依赖

**职责重叠检测：**
- 每个模块的 `description` 能否一句话说清？
- 是否存在两个模块 description 语义高度相似（职责重叠嫌疑）？

**依赖方向合规：**
- 依赖方向是否符合稳定性分层（易变侧 → 稳定侧，不可逆向）

---

## 输出报告格式

```
## 合规审查报告（{日期} · {项目}）

### 阶段一：格式校验
- 通过 / FAIL（{N} 处错误）
  - {错误描述} — {模块路径}

### 阶段二：语义分析
#### 循环依赖（{N} 处）
#### 幽灵依赖（{N} 处）
#### 职责重叠嫌疑（{N} 处）
#### 依赖方向问题（{N} 处）

### 结论
PASS / FAIL — 需处理后重审
```
