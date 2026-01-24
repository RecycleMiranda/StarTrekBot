# architecture

## Goals
- local -> docker -> vps
- QQ官方机器人（合规）接入后，统一为内部 OneBot-like 事件层
- 任何改动都要更新 project.md 的 changelog

## Modules
- services/bot: bot service (health placeholder)
- infra/docker-compose.yml: deploy

## Conventions
- config via .env (never commit secrets)
- logs to stdout
