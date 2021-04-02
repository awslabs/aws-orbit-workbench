c.ServerProxy.servers = {
    "http.server": {"command": ["python3", "-m", "http.server", "{port}"], "timeout": 60, "absolute_url": False},
    # 'code-server': {
    #     'command': ['code-server', '--bind-addr', 'localhost:{port}', '--auth', 'none'],
    #     'timeout': 120,
    #     'absolute_url': False
    #     launcher_entry=LauncherEntry(
    #         'enabled'=le.get('enabled', True),
    #         'icon_path'=le.get('icon_path'),
    #         'title'=le.get('title', name)
    #     ),
    # }
}
c.NotebookApp.tornado_settings = {"autoreload": True}
