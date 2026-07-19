# Private overlay

Public `Foprta/fund` is a DeFi **research** chatbot. Optional local modules for
configured deployments live in the private overlay
[`Foprta/fund-private`](https://github.com/Foprta/fund-private).

## Dev setup

```bash
git clone git@github.com:Foprta/fund.git
git clone git@github.com:Foprta/fund-private.git
cd fund
chmod +x scripts/link-private.sh
./scripts/link-private.sh ../fund-private
uv pip install -e ../fund-private   # do not uv-add into public pyproject
uv sync --all-packages
# merge secret keys from fund-private/.env.example into .env
```

## Modes

| Checkout | Behavior |
|----------|----------|
| Public only | Fail-closed research chat |
| Public + private overlay | Local modules import; configured capabilities unlock |

```bash
uv run pytest tests/test_access_failclosed.py -q
# with overlay linked:
uv run python -c "import api.policy_local, api.tools_local; print('ok')"
uv run pytest tests_local/ -q --ignore=tests_local/eval
```

## Deploy

Install public tree, then private package with a deploy token, link/copy local
data + migrations, set env secrets in the platform — not in either git.

`/health` → `overlay: {policy_local, detail_tools, piggy_tools}` (booleans only).
