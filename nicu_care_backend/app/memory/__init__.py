"""
Multi-Agent Memory Layer:
- Short-Term: Turn buffer, Redis / thread-safe fallback scratchpad, high-speed semantic cache.
- Long-Term: Living LLM Wiki (~350 tokens) and persistent clinical facts.
- Episodic: Longitudinal clinical episode history, milestones, and acute alerts.
"""
import sys
import importlib

try:
    from .short_term_memory import ShortTermMemory, short_term_memory
    from .long_term_memory import LongTermMemoryManager, long_term_memory
    from .episodic_memory import EpisodicMemoryService, episodic_memory
except (KeyError, ImportError):
    _stm = importlib.import_module("app.memory.short_term_memory")
    _ltm = importlib.import_module("app.memory.long_term_memory")
    _epm = importlib.import_module("app.memory.episodic_memory")
    ShortTermMemory = _stm.ShortTermMemory
    short_term_memory = _stm.short_term_memory
    LongTermMemoryManager = _ltm.LongTermMemoryManager
    long_term_memory = _ltm.long_term_memory
    EpisodicMemoryService = _epm.EpisodicMemoryService
    episodic_memory = _epm.episodic_memory

__all__ = [
    "ShortTermMemory",
    "short_term_memory",
    "LongTermMemoryManager",
    "long_term_memory",
    "EpisodicMemoryService",
    "episodic_memory",
]
