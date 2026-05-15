from dataclasses import dataclass, field


@dataclass
class AgentRun:
    run_id: str
    agent_name: str
    status: str
    steps: list[str] = field(default_factory=list)
