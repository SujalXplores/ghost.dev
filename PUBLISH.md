# Publishing ghost-dev to PyPI

## One-time setup

1. Create a PyPI account at https://pypi.org/account/register/
2. Create an API token at https://pypi.org/manage/account/token/
3. Run the upload:

```bash
twine upload dist/* --username __token__ --password pypi-YOUR_TOKEN_HERE
```

## After publishing

Anyone can install and run ghost.dev with:

```bash
# Install permanently
pip install ghost-dev

# Or run without installing (like npx)
uvx ghost-dev run https://github.com/user/repo
pipx run ghost-dev run https://github.com/user/repo
```
