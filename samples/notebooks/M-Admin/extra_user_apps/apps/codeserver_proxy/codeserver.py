def setup_codeserver():
    
    def _command(port):
        return ["bash", "/home/jovyan/.orbit/apps/codeserver_proxy/startup.sh", "{port}"]
                           
    return {
        "command": _command,
        "timeout": 120,
        "absolute_url": False,
        "launcher_entry": {
            "icon_path": "/home/jovyan/.orbit/apps/codeserver_proxy/favicon.svg",
            "title": "VS Code"
        }
    }