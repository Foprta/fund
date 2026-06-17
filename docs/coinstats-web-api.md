# CoinStats web API (v8)

Same endpoint as the CoinStats website for a **shared portfolio**.

## Env

```env
COINSTATS_SHARE_TOKEN=...
COINSTATS_UUID=...
```

## Capture headers

1. Open portfolio on [coinstats.app](https://coinstats.app)
2. DevTools → Network → `portfolio_items`
3. Copy `sharetoken` and `uuid` headers

Do **not** commit tokens to git.

## Endpoint

```
GET https://api.coin-stats.com/v8/portfolio_items?coinExtraData=true&showAverage=true&includeAllAssets=true
```

## Sync

Background scheduler or:

```bash
curl -X POST http://localhost:8000/admin/jobs/sync -H "X-Admin-Secret: change-me"
```

Writes `holdings_snapshots` + `portfolio_snapshots`. PnL from `tpl.pt.all.USD`; PnL% = `pnl / (NAV - pnl) * 100`.
