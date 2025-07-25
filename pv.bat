@echo off
REM Poetry wrapper that auto-syncs versions
REM Usage: pv version patch (instead of poetry version patch)

python scripts\poetry_wrapper.py %*
