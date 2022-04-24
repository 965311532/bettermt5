import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bettermt5",
    version="0.9.1",
    author="Gabriele Armento",
    author_email="contact@gabrielearmento.com",
    description="A simple MetaTrader5 wrapper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/965311532/bettermt5",
    packages=['bettermt5'],
    install_requires=['MetaTrader5'],
    python_requires=">=3.6",
)