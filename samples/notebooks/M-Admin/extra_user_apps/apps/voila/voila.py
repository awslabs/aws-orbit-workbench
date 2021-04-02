def setup_voila():
    return {
        "command": ["voila", "-port", "{port}", "--strip_sources", "False", "/home/jovyan/shared/samples/notebooks/voila", "--debug"],
        "timeout": 120,
        "absolute_url": False,
        "launcher_entry": {
            "icon_path": "/home/jovyan/.orbit/apps/voila/voila-logo.svg",
            "title": "Voila"
        }
    }