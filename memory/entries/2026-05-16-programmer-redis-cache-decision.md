---
date: 2026-05-16
agent: programmer
tags: [module-user-module, decision, incident]
---

程序员在用户模块引入 Redis 缓存，TTL 设为 300 秒，原因是 DB 查询热点问题严重，缓存命中率预期 80%+。
