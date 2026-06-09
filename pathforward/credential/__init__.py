"""Credential layer: the W3C VC 2.0-aligned, citation-backed competency proof.

v1 ships a cited evidence-trail artifact framed as VC-aligned (full signed VC is a
future stretch). The mint logic is wrapped by a local approval gate
(`require_approval:"always"` semantics) and still validates the artifact itself. A hosted
MCP/Agent Framework approval surface can call that wrapper; it must not bypass it.
"""
