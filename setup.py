from setuptools import setup, find_packages

setup(
    name="pox5fly-oj",
    version="0.1.1",
    description="A local utility package for Online Judge testing",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
)
