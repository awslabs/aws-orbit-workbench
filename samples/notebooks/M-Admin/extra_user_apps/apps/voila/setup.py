import setuptools

setuptools.setup(
  name="voila",
  # py_modules rather than packages, since we only have 1 file
  py_modules=['voila'],
  entry_points={
      'jupyter_serverproxy_servers': [
          # name = packagename:function_name
          'code-server = voila:setup_voila',
      ]
  },
  install_requires=['jupyter-server-proxy'],
)
