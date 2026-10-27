```text
isotools/
├── .github/
│   └── workflows/
│       ├── main.yml            # CI test runner (pytest across Python 3.10–3.12)
│       └── pylint.yml          # CI linter workflow
├── docs/                       # Conceptual & mathematical documentation
│   ├── calibration_and_uncertainty.md
│   ├── concepts_and_workflow.md
│   └── managing_standards.md
├── examples/
│   └── dual_isotope_water/     # Synthetic dual-isotope water workflow & report generator
│       ├── generate_synthetic_water_data.py
│       ├── process_and_report_water.py
│       ├── synthetic_water_sequence.xlsx
│       ├── Synthetic_Water_2H_Report.html
│       ├── Synthetic_Water_2H_Report.xlsx
│       ├── Synthetic_Water_18O_Report.html
│       ├── Synthetic_Water_18O_Report.xlsx
│       └── Synthetic_Water_Dual_Isotope_Report.html
├── isotools/                   # Main package source
│   ├── __init__.py
│   ├── core.py                 # The 'Batch' controller & canonical CF-IRMS pipeline
│   ├── config.py               # System configurations (NITROGEN, WATER_H, WATER_O, CARBON_13C)
│   ├── models.py               # Data classes (ReferenceMaterial)
│   ├── qaqc_log.py             # Long-term QA/QC CSV logger & Shewhart control charts
│   ├── standards.py            # Registry of reference materials, get_standard, register_standard
│   ├── reporting/              # Export and visualization modules
│   │   ├── __init__.py
│   │   ├── excel.py            # Multi-sheet Excel exporter (Results, QAQC, Uncertainty_Budget, Parameters)
│   │   ├── html.py             # Standalone Plotly + Jinja2 HTML report generators
│   │   ├── assets/             # Laboratory logo and static assets
│   │   │   └── isologo_lih.jpg
│   │   └── templates/          # Jinja2 HTML report templates
│   │       ├── base.html
│   │       ├── single_isotope.html
│   │       └── dual_isotope.html
│   ├── strategies/             # Mathematical calibration & uncertainty propagation logic
│   │   ├── __init__.py
│   │   ├── abstract.py
│   │   └── normalization.py    # SinglePointOffset, TwoPointLinear, MultiPointLinear
│   └── utils/
│       ├── __init__.py
│       ├── readers.py          # Isodat Excel file parsing & validation
│       └── kragten.py          # Numerical Kragten uncertainty propagation & variance budgets
├── tests/                      # Unit & integration test suite
│   ├── __init__.py
│   ├── test_carbon.py
│   ├── test_core.py
│   ├── test_drift.py
│   ├── test_linearity.py
│   ├── test_memory_and_elemental.py
│   ├── test_qaqc_and_log.py
│   ├── test_readers.py
│   ├── test_report_parameters.py
│   ├── test_reporting.py
│   ├── test_standards_expanded.py
│   ├── test_strategies.py
│   └── test_uncertainty_budget.py
├── AGENTS.md                   # AI Agents architecture & style guide
├── BACKLOG.md                  # Project roadmap and completed/pending tasks
├── file_structure.md           # Repository directory structure overview
├── LICENSE                     # GNU GPLv3 License
├── pyproject.toml              # Package metadata, dependencies, and build configuration
├── README.md                   # Project overview and quickstart
├── uv.lock                     # Deterministic uv dependency lockfile
├── .gitignore
└── .pylintrc                   # Linting configuration
```
