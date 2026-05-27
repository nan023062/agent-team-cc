---
name: cbim-unity-mcp
owner: architect
description: 基础能力三抽象之「MCP 服务（McpDescriptor）」——CBIM 顶层模块，跨维度共享抽象。abstract McpDescriptor + StdioMcpDescriptor / HttpMcpDescriptor 两子类 + McpTransportKind 枚举。能力侧（AgentDescription.McpList 跟人走）与业务侧（ModuleDescription.McpList 跟业务走）同抽象同类型共用——这是 CBIM 内最显式的跨维度共享点。装配机制（任务期生命周期）：启 server → 握手 → tools/list → 包 AIFunction → 任务结束 CloseInstance 必释放。McpRuntime 启动器/胶水后续在本模块内或装配侧落地。
keywords: []
dependencies: []
status: spec
---
## Positioning

<!-- One sentence: what this module is and why it exists. -->

## Class Diagram

```mermaid
classDiagram
    %% classes, interfaces, key method signatures, relationships
```

## Key Decisions

<!-- Design choices whose "why" is invisible from the code itself.
     Each decision applies to the module as a whole. -->
