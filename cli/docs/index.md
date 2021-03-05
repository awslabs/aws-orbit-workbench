# Orbit
Orbit Workbench CLI - Data & ML Unified Development and Production Environment

#### Usage
```
orbit [OPTIONS] COMMAND [ARGS]…
```
#### Options
```
--help  Show this message and exit.
```

#### Commands
```
build    Build images,profiles,etc in your Orbit Workbench.
delete   Delete images,profiles,etc in your Orbit Workbench.
deploy   Deploy foundation,env,teams in your Orbit Workbench.
destroy  Destroy foundation,env,etc in your Orbit Workbench.
init     Creates a Orbit Workbench manifest model file (yaml) where all…
list     List images,profiles,etc in your Orbit Workbench.
run      Execute containers in the Orbit environment
```

## Commands
::: mkdocs-click
    :module: aws_orbit.__main__
    :command: build

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: delete

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: deploy

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: destroy

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: init_cli

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: list

---

::: mkdocs-click
    :module: aws_orbit.__main__
    :command: run_container
