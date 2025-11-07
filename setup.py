import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="SungrowModbusTcpClient",
    version="0.1.7",
    author="Roberto Panerai Velloso",
    author_email="rvelloso@gmail.com",
    description="A ModbusTcpClient wrapper for talking to Sungrow solar inverters",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rpvelloso/Sungrow-Modbus",
    packages=setuptools.find_packages(),
    install_requires=[
        'pymodbus>=3.11.3,<4.0.0',
        'pycryptodomex>=3.11.0',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10.0',
)
