"""Ordered implementation parts for the onboarding compatibility command.

The command executes these files in one namespace so existing consumers can
continue monkeypatching script-level globals while each responsibility remains
physically reviewable in a bounded module.
"""
