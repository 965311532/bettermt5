import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bettermt5",
    version="0.9.4",
    author="Gabriele Armento",
    author_email="contact@gabrielearmento.com",
    description="A simple MetaTrader5 wrapper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/965311532/bettermt5",
    packages=[
        "bettermt5",
        "bettermt5.templates",
        "bettermt5.templates.static",
        "bettermt5.templates.dynamic",
    ],
    install_requires=["MetaTrader5"],
    python_requires=">=3.6",
    include_package_data=True
)
