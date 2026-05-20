---
name: knowledge
owner: engine-team
description: CBIM 模块树扫描、模块元数据加载与知识快照构建
keywords: [knowledge, module-tree, snapshot, parser]
dependencies: []
includeDirs: [src/knowledge]
---

## Positioning

@cbim/engine 的知识子层。负责扫描项目目录树以发现 CBIM 模块，解析 module.md / contract.md，构建面向 Coordinator 的知识快照（Snapshot）。

## Class Diagram

```mermaid
classDiagram
    class ModuleFrontmatter {
        <<interface>>
        +name: string
        +owner: string
        +description: string
        +keywords: string[]
        +dependencies: string[]
        +includeDirs: string[]
    }

    class ModuleSections {
        <<interface>>
        +positioning?: string
        +diagram?: string
        +keyDecisions?: string
    }

    class Module {
        <<interface>>
        +path: string
        +frontmatter: ModuleFrontmatter
        +sections: ModuleSections
        +contract?: string
        +workflows: WorkflowFrontmatter[]
    }

    class ModuleNode {
        <<interface>>
        +path: string
        +name: string
        +children: ModuleNode[]
        +isLeaf: boolean
        +metadata: object
    }

    class Snapshot {
        <<interface>>
        +focus: Module
        +ancestors: Module[]
        +descendants: Module[]
        +siblings: Module[]
        +related: Module[]
        +unresolvedDependencies: string[]
    }

    class KnowledgeAPI {
        +discoverModules(projectRoot) ModuleNode[]
        +loadModule(modulePath) Module
        +buildSnapshot(focusPath, tree) Snapshot
        +resolveModulePath(relativePath, root) string
        +parseModuleMd(raw) object
        +loadWorkflow(modulePath, name) Workflow
    }

    Module *-- ModuleFrontmatter
    Module *-- ModuleSections
    ModuleNode o-- ModuleNode : children
    Snapshot *-- Module : focus/ancestors/descendants
    KnowledgeAPI ..> Module : returns
    KnowledgeAPI ..> ModuleNode : returns
    KnowledgeAPI ..> Snapshot : returns
```

## Key Decisions

- **Stateless engine**: No built-in cache. The engine is a pure library; cache invalidation is the consumer's responsibility (extension caches and watches file changes; CLI runs once and exits).

- **Best-effort discovery**: `discoverModules` logs warnings for broken modules and skips them rather than throwing. Discovery is a full-tree scan; individual module failures must not abort the entire tree.

- **Eager frontmatter / lazy content for workflows**: Module loading eagerly parses workflow frontmatters (name, keywords, description, triggers) but defers body content to `loadWorkflow()`. This matches the skill loading pattern and keeps snapshot assembly lightweight.

- **js-yaml for YAML parsing**: The hand-written v1 YAML parser was fragile (no quoted strings, no multiline values). `js-yaml` / `yaml` is the Node.js standard, zero native dependencies, ~50KB bundled.
