# Private overlay (fund digits / piggy bank)

Public `Foprta/fund` is fail-closed: without local modules it is a DeFi **research**
chatbot only. Fund figures, participant slots, and the piggy bank live in the
private overlay repo [`Foprta/luna-fund-private`](https://github.com/Foprta/luna-fund-private).

## Dev setup

```bash
git clone git@github.com:Foprta/fund.git
git clone git@github.com:Foprta/luna-fund-private.git
cd fund
chmod +x scripts/link-private.sh
./scripts/link-private.sh ../luna-fund-private
# optional venv install (do not commit into public pyproject.toml):
uv pip install -e ../luna-fund-private
uv sync --all-packages
# merge INSIDER_AUTH_PHRASE / PIGGY_* from luna-fund-private/.env.example into .env
```

`link-private.sh` symlinks `*_local.py`, `local/`, `tests_local/`, and the
participant migration into this tree (still gitignored here). Optionally
`uv pip install -e ../luna-fund-private` registers the same modules via
`pkgutil.extend_path` (keep that path dep out of public `pyproject.toml` so CI
stays public-only).

## Modes

| Checkout | Behavior |
|----------|----------|
| Public only | `DENY_ALL` — no fund/piggy tools |
| Public + private overlay | Insider / piggy phrases unlock tools |

```bash
# public-only sanity
uv run pytest tests/test_access_failclosed.py -q

# with overlay
uv run python -c "import api.policy_local, api.tools_local; print('ok')"
uv run pytest tests_local/test_policy.py tests_local/test_piggy_bank.py -q
```

## Deploy

1. Build/install the public monorepo.
2. Install private package with a deploy token:

```bash
uv pip install "luna-fund-private @ git+https://x-access-token:${GITHUB_TOKEN}@github.com/Foprta/luna-fund-private.git"
```

3. Ensure Alembic sees `900_participant_local.py` (run `link-private.sh` in the
   image build, or copy that migration into `migrations/versions/`).
4. Put phrases and wallet in **platform secrets** / runtime env — not in either git.

Optional health: log `fund_local=yes/no` and `piggy_tools=yes/no` at API startup
(see `api.main` overlay status) without printing secret phrases.

## Never commit

`*_local.py`, `/local/`, `/tests_local/`, `.env` stay gitignored in public.
CI may assert they are absent from the tracked tree.
