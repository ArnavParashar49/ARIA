"""Central in-process message bus — avoids direct agent-to-agent coupling."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable

from hybrid.types import AgentMessage, AgentRole


Subscriber = Callable[[AgentMessage], None]


class TaskBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_topic: dict[str, list[Subscriber]] = defaultdict(list)
        self._by_role: dict[AgentRole, list[Subscriber]] = defaultdict(list)
        self._history: list[AgentMessage] = []
        self._max_history = 200

    def subscribe(self, topic: str, handler: Subscriber) -> None:
        with self._lock:
            self._by_topic[topic].append(handler)

    def subscribe_role(self, role: AgentRole, handler: Subscriber) -> None:
        with self._lock:
            self._by_role[role].append(handler)

    def publish(self, message: AgentMessage) -> None:
        with self._lock:
            self._history.append(message)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]
            topic_handlers = list(self._by_topic.get(message.topic, []))
            role_handlers = list(self._by_role.get(message.source, []))

        for handler in topic_handlers + role_handlers:
            try:
                handler(message)
            except Exception as e:
                print(f"[TaskBus] Handler error on {message.topic}: {e}")

    def emit(
        self,
        topic: str,
        payload: dict,
        *,
        task_id: str = "",
        source: AgentRole = AgentRole.ORCHESTRATOR,
    ) -> None:
        self.publish(
            AgentMessage(topic=topic, payload=payload, task_id=task_id, source=source)
        )


_bus: TaskBus | None = None


def get_task_bus() -> TaskBus:
    global _bus
    if _bus is None:
        _bus = TaskBus()
    return _bus
