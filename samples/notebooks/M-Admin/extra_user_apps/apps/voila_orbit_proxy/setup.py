import setuptools

setuptools.setup(
  name="voila_orbit_proxy",
  # py_modules rather than packages, since we only have 1 file
  py_modules=['voila'],
  entry_points={
      'jupyter_serverproxy_servers': [
          # name = packagename:function_name
          'code-server = voila:setup_voila',
      ]
  },
  install_requires=['jupyter-server-proxy~=3.0.2', 'voila==0.2.7', 'bqplot~=0.12.23', 'ipyvuetify~=1.6.2']
)
