"""Which AI Task entity runs which import job.

Pure Python without Home Assistant imports. The choice is made in the options
of the integration (Settings > Devices & services > Recipe Library > Configure).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import AI_JOBS


def entity_for_job(options: Mapping[str, Any], job: str) -> str | None:
    """Return the AI Task entity chosen for ``job``.

    ``None`` means nothing was chosen: the import then passes no entity to
    Home Assistant, which uses its preferred AI Task entity.
    """
    if job not in AI_JOBS:
        raise ValueError(f"unknown AI job: {job}")
    value = options.get(job)
    return value if isinstance(value, str) and value else None
