import setuptools

setuptools.setup(
    name="codeserver-proxy",
    # py_modules rather than packages, since we only have 1 file
    py_modules=["codeserver"],
    entry_points={
        "jupyter_serverproxy_servers": [
            # name = packagename:function_name
            "code-server = codeserver:setup_codeserver",
        ]
    },
    install_requires=["jupyter-server-proxy>=3.0.2"],
)
