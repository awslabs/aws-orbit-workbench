import setuptools

setuptools.setup(
  name="codeserverproxy",
  # py_modules rather than packages, since we only have 1 file
  py_modules=['codeserver'],
  entry_points={
      'jupyter_serverproxy_servers': [
          # name = packagename:function_name
          'code-server = codeserverproxy:setup_codeserver',
      ]
  },
  install_requires=['jupyter-server-proxy~=3.0.2'],
)
