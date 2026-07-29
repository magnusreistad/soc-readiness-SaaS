from setuptools import setup, find_packages

setup(
    name="vendor-threat-monitor",
    packages=find_packages(exclude=["venv", "venv.*", "data", "*.egg-info"]),
)