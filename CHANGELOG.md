# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2025-03-07

### Added

- Browser automation MCP server (browser_init, browser_open, click, input, get_text, get_html, screenshot, wait_for, extract_data).
- Trajectory recording and export (trajectory_start, trajectory_complete, trajectory_get, trajectory_list, trajectory_load, trajectory_delete).
- Fuzzy point marking for steps requiring AI/human judgment.
- Stability: SmartSelector, SmartWait, ErrorRecovery.
- Adaptive element locating (auto_save fingerprint, adaptive relocation).
- Stealth mode: browser_init(stealth=true) for reduced automation detection.
- Structured error responses (code, retryable) and optional include_screenshot.

[Unreleased]: https://github.com/your-org/zerotoken/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/zerotoken/releases/tag/v0.1.0
