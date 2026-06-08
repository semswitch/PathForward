"""PathForward — a multi-agent reskilling system for displaced/at-risk workers.

Microsoft Agents League @ AISF 2026 · Reasoning Agents track (Microsoft Foundry).

This package is the Azure-independent core: the IQ derivation engine, the
code-driven Generator->Evidence Gate loop, cold-start calibration, the shared scorer,
and the credential mint. Everything here runs offline against a FakeLLMClient so
the reasoning spine can be developed and tested before any Foundry wiring.

See README.md and 03-Build-Plan.md for how the Azure layer plugs in.
"""

__version__ = "0.1.0"
