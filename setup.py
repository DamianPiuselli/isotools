from setuptools import setup, find_packages

setup(
    name="isotools",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.21.0",
        "openpyxl>=3.0.0",
        "xlrd>=2.0.1",
        "matplotlib>=3.5.0",
        "seaborn>=0.11.0",
        "scipy>=1.7.0",
        "plotly",
        "jinja2"
    ],
    include_package_data=True,
    package_data={
        "isotools.reporting": ["templates/*.html"],
    },
)
