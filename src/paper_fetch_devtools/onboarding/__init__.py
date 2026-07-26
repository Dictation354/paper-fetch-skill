"""Provider-onboarding development tools.

The public command remains ``scripts/onboard_from_manifests.py``.  Its source
now lives under the devtools package so onboarding can evolve independently of
the production ``paper_fetch`` package.
"""

from .cli import execute_compatibility_entrypoint

__all__ = ["execute_compatibility_entrypoint"]
