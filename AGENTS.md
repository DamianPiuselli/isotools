# AI Agents Guide - isotools

Welcome! This document provides guidance, architecture context, and instructions for AI agents (and human developers) working on the **isotools** codebase. It outlines the system roles, design principles, file structures, and common tasks.

## 1. Codebase Overview
**isotools** is a Python library designed for automated processing, normalization, and uncertainty propagation of Stable Isotope Ratio Mass Spectrometry (IRMS) data.
For general information and installation instructions, see [README.md](file:///home/damianp/Proyectos/isotools/README.md).

## 2. Core Architectural Roles
When working in a team or as an individual agent, tasks are typically split into the following functional roles:

### A. Data Ingestion Specialist
*   **Focus:** Reading, parsing, and validating raw spectrometer Excel files.
*   **Core Files:**
    *   [isotools/utils/readers.py](file:///home/damianp/Proyectos/isotools/isotools/utils/readers.py): Contains the [IsodatReader](file:///home/damianp/Proyectos/isotools/isotools/utils/readers.py#L13) which handles loading and header validation.
    *   [isotools/config.py](file:///home/damianp/Proyectos/isotools/isotools/config.py): Contains [SystemConfig](file:///home/damianp/Proyectos/isotools/isotools/config.py#L10) definition and isotopic system column mappings.
*   **Key Rules:**
    *   All raw file column validations must fail gracefully with descriptive error messages.
    *   Do not modify the raw data columns; instead, map them to internal standard names non-destructively.

### B. Calibration & Mathematical Strategy Engineer
*   **Focus:** Implementing regressions and calibration models to normalize raw machine delta values to international standards scales.
*   **Core Files:**
    *   [isotools/strategies/normalization.py](file:///home/damianp/Proyectos/isotools/isotools/strategies/normalization.py): Contains strategies like [TwoPointLinear](file:///home/damianp/Proyectos/isotools/isotools/strategies/normalization.py#L14) and [MultiPointLinear](file:///home/damianp/Proyectos/isotools/isotools/strategies/normalization.py#L131).
*   **Key Rules:**
    *   Any new calibration strategy must subclass `CalibrationStrategy` from `isotools/strategies/abstract.py`.
    *   Calibration fits are fitted using the `working_value` column of registered anchors.

### C. Metrologist & Uncertainty Auditor
*   **Focus:** Scientific error propagation, uncertainty budgets, and quality control (QA/QC).
*   **Core Files:**
    *   [isotools/utils/kragten.py](file:///home/damianp/Proyectos/isotools/isotools/utils/kragten.py): Contains the [propagate_kragten](file:///home/damianp/Proyectos/isotools/isotools/utils/kragten.py#L8) numerical differentiation method.
    *   [isotools/models.py](file:///home/damianp/Proyectos/isotools/isotools/models.py): Contains the [ReferenceMaterial](file:///home/damianp/Proyectos/isotools/isotools/models.py#L9) data model.
    *   [isotools/standards.py](file:///home/damianp/Proyectos/isotools/isotools/standards.py): Standard database of certified standards values and aliases.
*   **Key Rules:**
    *   Ensure all new calibration strategies implement a `.propagate()` method that performs numerical uncertainty propagation correctly.
    *   Maintain strict checks for outlier flagging (variance, range, amplitude).

### D. Reporting & Visualization Specialist
*   **Focus:** Exporting analysis summaries to Excel and generating interactive dashboards.
*   **Core Files:**
    *   [isotools/reporting/html.py](file:///home/damianp/Proyectos/isotools/isotools/reporting/html.py): Handles Plotly graph creation and Jinja2 HTML rendering.
    *   [isotools/core.py](file:///home/damianp/Proyectos/isotools/isotools/core.py): Contains the [Batch](file:///home/damianp/Proyectos/isotools/isotools/core.py#L21) class with `.save_report()` and `.save_html_report()` endpoints.
*   **Key Rules:**
    *   Keep HTML reports fully standalone (embed Plotly graphs using non-binary HTML injection).
    *   Separate metadata, results, and QA/QC data into structured sheets in the Excel exporter.

## 3. General Development Guidelines for Agents
*   **Documentation Integrity:** Preserve all existing comments and docstrings unless explicitly asked to modify them.
*   **Non-Destructive Operations:** Keep raw measurements intact. Save intermediate corrections in distinct columns (e.g., `working_value`, `corrected_d18o`).
*   **Standard Naming:** Always use `get_canonical_name` from the [Batch](file:///home/damianp/Proyectos/isotools/isotools/core.py#L21) class to resolve messy raw standard names into their canonical form before processing.
*   **Testing:** Always write corresponding tests in [tests/](file:///home/damianp/Proyectos/isotools/tests) for any new configuration, reader improvement, or math correction.

## 4. Useful Tasks
*   **View Roadmap / Tasks:** Check [BACKLOG.md](file:///home/damianp/Proyectos/isotools/BACKLOG.md) to see current development phase tasks.
*   **Running Tests:** Execute `pytest` in the root folder to run the suite of unit and integration tests.
