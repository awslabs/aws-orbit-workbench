def setup_codeserver():
    def _command(port):
        return ["bash", "/opt/orbit/codeserver_proxy/startup.sh", "{port}"]

    return {
        "command": _command,
        "timeout": 120,
        "absolute_url": False,
        "launcher_entry": {"icon_path": "/opt/orbit/codeserver_proxy/favicon.svg", "title": "VS Code"},
    }
