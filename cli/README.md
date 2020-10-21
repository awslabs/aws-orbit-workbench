# AWS EKS Data Maker CLI

## Contributing

### Visual Studio Code

#### Recommended extensions

* [ms-python.python](https://marketplace.visualstudio.com/items?itemName=ms-python.python)
* [kddejong.vscode-cfn-lint](https://marketplace.visualstudio.com/items?itemName=kddejong.vscode-cfn-lint)

#### Recommended settings

```json
{
    "cfnLint.ignoreRules": [
        "E1029",
        "E3031"
    ],
    "python.formatting.blackArgs": [
        "--line-length 120",
        "--target-version py36"
    ],
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Args": ["--max-line-length 120"],
    "python.linting.flake8Enabled": true,
    "python.linting.mypyCategorySeverity.error": "Hint",
    "python.linting.mypyCategorySeverity.note": "Hint",
    "python.linting.mypyEnabled": true,
    "python.linting.pylintEnabled": false
}
```