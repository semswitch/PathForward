"""Credential layer: the W3C VC 2.0-aligned, citation-backed competency proof.

v1 ships a cited evidence-trail artifact framed as VC-aligned (full signed VC is a
Day-6 stretch). The real mint runs behind the approval-gated MCP endpoint
(`require_approval:"always"`); this module builds and validates the artifact itself.
"""
