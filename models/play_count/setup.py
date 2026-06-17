from setuptools import find_packages
from setuptools import setup

setup(
    name='trainer',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'optuna',
        'optuna-integration[xgboost]',
        'pyarrow',
    ],
    description='My training application.'
)