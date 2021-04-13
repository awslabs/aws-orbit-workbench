def setup_codeserver():
    return {
        "command": ["code-server", "--bind-addr", "localhost:{port}", "--auth", "none", "--user-data-dir",
                    "/home/jovyan/private", "", "--config", "/home/jovyan/private/.config/code-server/config.yaml"],
        "timeout": 120,
        "absolute_url": False,
        "launcher_entry": {
            "icon_path": "/home/jovyan/.orbit/apps/codeserver_proxy/favicon.svg",
            "title": "VS Code"
        }
    }
