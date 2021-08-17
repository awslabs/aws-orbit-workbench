import setuptools

with open("VERSION", "r") as version_file:
    version = version_file.read().strip()

with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="aws-orbit-sdk",
    version=version,
    author="AWS Professional Services",
    author_email="aws-proserve-opensource@amazon.com",
    url="https://github.com/awslabs/aws-orbit-workbench",
    project_urls={"Org Site": "https://aws.amazon.com/professional-services/"},
    description="AWS Orbit Workbench SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords=["aws", "cdk"],
    package_dir={"aws_orbit_sdk": "aws_orbit_sdk"},
    packages=setuptools.find_packages(),
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=[
        "boto3~=1.18.0",
        "pyyaml~=5.4",
        "ipython~=7.23.0",
        "pandas>=1.1.0,<=1.2.0",
        "psycopg2-binary~=2.8.4",
        "SQLAlchemy>=1.3.10,<1.3.16",
        "sqlalchemy-redshift~=0.7.5",
        "requests>=2.24.0,<=2.26.0",
        "kubernetes~=12.0.1",
        "python-slugify~=4.0.1",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
