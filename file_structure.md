isotools/
├── .github/
│   └── workflows/
│       ├── main.yml
│       └── pylint.yml
├── DATA/
│   ├── datos 2H y 18O procesados.xlsx
│   └── nitrate 26112025.xls
├── isotools/           # Main package source
│   ├── __init__.py
│   ├── core.py         # The 'Batch' controller
│   ├── config.py       # System configurations
│   ├── models.py       # Data classes (ReferenceMaterial)
│   ├── standards.py    # Database of known materials
│   ├── strategies/     # Mathematical calibration logic
│   │   ├── __init__.py
│   │   ├── abstract.py
│   │   └── normalization.py
│   └── utils/
│       ├── readers.py  # Isodat file parsing
│       └── kragten.py  # Uncertainty propagation math
├── tests/              # Test suite
│   ├── __init__.py
│   ├── test_core.py
│   ├── test_drift.py
│   ├── test_readers.py
│   └── test_strategies.py
├── BACKLOG.md          # Project roadmap and pending tasks
├── file_structure.md   # This file
├── LICENSE
├── README.md           # Project overview and installation
├── replication_water.ipynb # Water isotope replication notebook
├── requirements.txt    # Core dependencies
├── requirements-dev.txt # Development dependencies
├── .gitignore
├── .pylintrc           # Linting configuration
├── Water_18O_Report.xlsx
├── Water_2H_Report.xlsx
└── workflow.ipynb      # Usage example notebook
