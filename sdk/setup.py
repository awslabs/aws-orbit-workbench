import setuptools

with open("VERSION", "r") as version_file:
    version = version_file.read().strip()

with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="aws-orbit-sdk",
    version=version,
    description="AWS Orbit Workbench SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="author",
    package_dir={"aws_orbit_sdk": "aws_orbit_sdk"},
    packages=setuptools.find_packages(),
    include_package_data=True,
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
