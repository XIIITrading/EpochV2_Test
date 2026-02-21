"""
================================================================================
EPOCH TRADING SYSTEM - MODULE 05: SYSTEM ANALYSIS
Question Registry — Auto-discovers all q_*.py question modules
XIII Trading LLC
================================================================================

Drop a new q_*.py file in this directory with a BaseQuestion subclass and it
will be automatically discovered and available in the UI. No registration needed.
"""
import importlib
import pkgutil
from pathlib import Path
from typing import List

from questions._base import BaseQuestion


def get_all_questions() -> List[BaseQuestion]:
    """Discover and instantiate all BaseQuestion subclasses from q_*.py files.

    Returns:
        List of question instances sorted by (category, title)
    """
    questions = []
    package_dir = Path(__file__).parent

    for finder, name, _ in pkgutil.iter_modules([str(package_dir)]):
        if not name.startswith("q_"):
            continue
        try:
            module = importlib.import_module(f"questions.{name}")
        except Exception as e:
            print(f"[Questions] Failed to import {name}: {e}")
            continue

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                    and issubclass(attr, BaseQuestion)
                    and attr is not BaseQuestion
                    and getattr(attr, "id", "")):
                try:
                    questions.append(attr())
                except Exception as e:
                    print(f"[Questions] Failed to instantiate {attr_name}: {e}")

    questions.sort(key=lambda q: (q.category, q.title))
    return questions


__all__ = ["BaseQuestion", "get_all_questions"]
