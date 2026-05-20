---
name: migration
owner: engine-team
description: v1 到 v2 项目布局的迁移规划与执行
keywords: [migration, v1, v2, upgrade]
dependencies: []
includeDirs: [src/migration]
---

## Positioning

负责将 CBIM v1 项目布局迁移到 v2 格式，包括迁移计划生成（planMigration）和执行（applyMigration）。

## Class Diagram

```mermaid
classDiagram
    class MigrationPlan {
        <<interface>>
        +steps: MigrationStep[]
        +sourceVersion: string
        +targetVersion: string
    }

    class MigrationStep {
        <<interface>>
        +type: string
        +source: string
        +target: string
        +description: string
    }

    class MigrationAPI {
        +planMigration(projectRoot) MigrationPlan
        +applyMigration(plan) void
        +summarizeMigration(plan) string
    }

    MigrationPlan *-- MigrationStep
    MigrationAPI ..> MigrationPlan : creates/consumes
```

## Key Decisions

- **Fully isolated from runtime**: `migration/` has no runtime coupling with `knowledge/`, `memory/`, `dispatch/`, or `tools/`. Migration is a one-time file transformation with no engine runtime state. This isolation keeps the runtime footprint clean.

- **Plan-then-apply pattern**: `planMigration` produces a deterministic, inspectable plan before any mutation. `applyMigration` executes the plan. This allows dry-run preview and partial execution.
