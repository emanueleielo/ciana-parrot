---
title: Guides
---

# Guides

CianaParrot is designed around clear extension points. Each guide below walks you through adding or customizing a specific part of the system, from Introduction through Prerequisites, step-by-step implementation, wiring, and testing.

---

## Extension Points

| Guide | What It Covers |
|-------|----------------|
| [Add a Channel](add-channel.md) | Create a new channel adapter (Discord, Slack, webhook, etc.) implementing `AbstractChannel` and wire it into the message flow. |
| [Add a Bridge](add-bridge.md) | Expose a host CLI tool to the agent through the gateway's per-bridge command allowlisting system. |
| [Add a Skill](add-skill.md) | Drop a skill folder into `workspace/skills/` with a `SKILL.md` and `skill.py` -- functions auto-register as agent tools via DeepAgents. |
| [Add a Tool](add-tool.md) | Create a new `@tool`-decorated function in `src/tools/` using the module-level init pattern and wire it into the agent. |
| [Add a Mode Handler](add-mode-handler.md) | Implement the `ModeHandler` protocol to intercept Telegram messages for a dedicated UI mode (like Claude Code mode). |
| [Add a Config Section](add-config-section.md) | Add a new Pydantic v2 config model with validation, env var expansion, and YAML mapping. |
| [Customize the Agent](customize-agent.md) | Switch LLM providers, add memory files, configure MCP servers, adjust tool iterations, and mount host directories. |
| [Set Up the Gateway](setup-gateway.md) | Complete guide to running the host gateway server, configuring bridges, and securing access with token authentication. |

---

## How the Pieces Fit Together

```mermaid
graph LR
    A[Channel] -->|IncomingMessage| B[Router]
    B -->|thread_id| C[Agent]
    C -->|@tool calls| D[Tools]
    C -->|skills dir| E[Skills]
    C -->|host_execute| F[Gateway]
    F -->|bridge allowlist| G[Host CLI]
    H[Config] -->|AppConfig| A
    H -->|AppConfig| B
    H -->|AppConfig| C
    I[Mode Handler] -->|intercepts| A
```

Each guide is self-contained -- pick the one that matches what you want to build.
