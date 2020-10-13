import setuptools
import pip

long_description = "DataMaker client API library"

with open('../../../VERSION', 'r') as version_file:
    version = version_file.read().strip()

setuptools.setup(
    name="datamaker-utils",
    version=version,

    description="DataMaker Client APIs",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"notebook-utils": "notebook-utils"},
    packages=setuptools.find_packages(),

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: Apache Software License",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
