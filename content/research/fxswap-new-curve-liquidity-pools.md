---
title: "FXSwap vs Uniswap V3: эффективность ликвидности для волатильных пар"
summary: "Сравнение нового пула FXSwap от Curve (с механизмом refuelling) против Uniswap V3 CLAMM на маршруте USDC→WBTC. FXSwap даёт лучшую цену для $10m свопов в ~80% блоков при схожем TVL; для мелких свопов выигрывает Uniswap из-за 1% комиссии YB. Не покрывает: smart-contract риски, газовые издержки."
topics: [FXSwap, Curve, YieldBasis, Uniswap, liquidity, AMM]
version: 1
---

A comparative analysis of liquidity efficiency for volatile pairings

Abstract
FXSwap is a new volatile-pair pool design from @CurveFinance that automatically concentrates liquidity around the active price range and periodically re-centres that concentration using a mechanism called ‘refuelling’. In partnership with Curve, we investigated the efficiency of this innovative new pool type and compared results against equivalent Uniswap V3 pools.

This study compares end-of-block quotes for USDC->WBTC trades between (i) the Uniswap V3 WBTC/USDC 0.3% pool and (ii) an equivalent USDC->WBTC route via the @yieldbasis WBTC/crvUSD FXSwap pool, bridged through Curve’s crvUSD/USDC stableswap pool.

The FXSwap route delivered a better execution price for a $10m trade in approximately 80% of blocks sampled, despite similar pool TVL. We also analysed liquidity distribution to explain when and why performance diverges.

Introduction
FXSwap is a new volatile pool implementation from Curve. Like previous Cryptoswap implementations, FXSwap automatically concentrates liquidity around the current price. In comparison, Uniswap’s V3 / V4 Concentrated Liquidity (CLAMM) pools require LPs to manually manage the price range in which their liquidity is provided.

First rolled out for Yieldbasis’ BTC/USD pools, FXSwap introduces an innovative new mechanism called ‘refuelling’. As explained in this post, refuelling is a way of subsidising the cost of rebalancing liquidity in the AMM. This ensures that liquidity is better concentrated around the current price, efficiently utilising the pool’s TVL to provide greater depth of market.

FXSwap was chosen as the pool implementation for Yieldbasis as it is designed to handle uncorrelated asset pairings such as BTC-USD. This also makes it ideal for foreign exchange trading between different fiat-pegged stablecoins. Bringing the trillion dollar Forex markets on-chain has been a long-standing goal for Curve, and FXSwap provides the technical foundation which makes this possible. This goal is now being realised, with Frankencoin recently launching the first FXSwap pool on Curve, enabling efficient trading between ZCHF (a collateralised stablecoin pegged to the Swiss Franc) and crvUSD.

In this study, we partnered with Curve to investigate the efficiency of the new FXSwap pool implementation in comparison to @Uniswap V3’s CLAMM. We compared depth of market pricing for USDC to WBTC swaps, finding that FXSwap pools tend to provide greater depth relative to pool TVL, due to a more efficient concentration of liquidity around the marginal price. FXSwap also proved more responsive in rebalancing liquidity around the active range during volatile periods. As a result, FXSwap provided better pricing for a $10m swap in ~80% of the blocks measured compared to the equivalent Uniswap pool.

Methodology
We investigated whether FXSwap provides better pricing than Uniswap V3 CLAMM pools, and if so, by how much. Our study addresses two key research questions:

How do FXSwap depth-of-market quotes compare to Uniswap?

How does the liquidity distribution in the two pools compare?

Of the few FXSwap pools currently deployed, we focused our study on the Yieldbasis WBTC/crvUSD pool. This was chosen because the Uniswap WBTC/USDC 0.3% pool has comparable TVL to the Yieldbasis pool, whilst cbBTC and tBTC routes have significantly less liquidity on Uniswap.

Using Pangea Studio, we collected end-of-block pool states from Nov 1 to Dec 17 and generated quotes at fixed input sizes. For Uniswap V3 we quote directly against the WBTC/USDC 0.3% pool. For Curve we quote a two-leg route: USDC→crvUSD (Curve crvUSD/USDC Stableswap) then crvUSD→WBTC (Yieldbasis WBTC/crvUSD FXSwap). Our quotes represent the price to buy BTC with USDC including swap fees, but excluding gas cost.

As well as comparing price and price impact, we also analysed the pool TVL, coin balances, volume, and liquidity distribution. These datapoints are important for comparing the relative efficiency of the pools, as we want to know not only which pools provide the best pricing in absolute terms, but also which provide the greatest depth of market relative to their TVL. We also compared how the pools allocated that TVL to see differences in liquidity concentration and how this impacts market depth.

Findings
Yieldbasis’ FXSwap pools provide significantly better pricing for $10m swaps than equivalent Uniswap V3 routes.

A multihop route through the Curve crvUSD/USDC pool and the Yieldbasis WBTC/crvUSD pool provided better pricing for a $10m swap in ~80% of the blocks measured compared to a direct swap through the Uniswap WBTC/USDC 0.3% pool. On average, this route provided prices that were ~2.1% better than Uniswap. At most, trading through Uniswap resulted in an execution price ~7.5% worse than if that same trade was routed through Curve and Yieldbasis. The cap raise on the Yieldbasis cbBTC pool to $200m has also significantly deepened market depth, with the $10m quote to swap USDC for cbBTC now having as little as ~1% price impact.

For smaller swap sizes Uniswap tends to dominate, providing better quotes for $100k in ~85% of the blocks and for $1m in ~69% of the blocks. Only once trade size exceeded $2.45m did Yieldbasis provide better quotes in a majority of the blocks measured. This is not due to the FXSwap pool design specifically, but rather to Yieldbasis’ 1% fee. This high fee is by design, as it is required to pay for the costs of maintaining the pool. As a result however, smaller swaps will tend to route through Uniswap instead of Yieldbasis, and Yieldbasis tends to only receive volume when BTC volatility is high.

What’s remarkable about Yieldbasis’ dominance over Uniswap for the $10m quote range is that both pools had similar TVL during this period. Thus, not only does FXSwap provide better pricing in absolute terms, but also relative to its TVL.

For example, from the beginning of December onward, the TVL of both the Uniswap and Yieldbasis pools was almost constant yet the dominance of Yieldbasis’ quotes increased significantly, due to two main factors. Firstly, the Yieldbasis pool rebalanced its liquidity closer to 50/50, tightening concentration around the price and thus reducing price impact. At the same time, Uniswap LPs failed to allocate liquidity around the active tick range, increasing price impact.

In a CLAMM like UniV3, overall pool TVL and coin balances do not tell the whole story. We must instead look at how liquidity is being distributed by LPs across specific price ranges. Several factors influence how liquidity gets allocated. In the following video, we show how the liquidity distribution in the UniV3 WBTC/USDC 0.3% pool has changed over time:

LPs may be taking a directional bet that price will go up or down, and so positioning may be biased in one direction. Our data shows the UniV3 pool to be overweight in WBTC for the period measured, indicating a sell-side bias.

Some portion of liquidity is ‘lazy’, meaning it is not being efficiently managed as the price changes. This can be due to uninformed retail LPs, as well as lost keys and forgotten accounts.

A key factor is the cost of rebalancing. When a position goes out of range, moving it back in range can mean realising impermanent loss and paying gas costs. Thus, it may not be economically rational for LPs to always move their liquidity and chase the price. This can result in much of the pool’s liquidity sitting out of range, especially during times of high volatility and gas cost when liquidity is needed most.

By comparison, FXSwap efficiently allocates the pool’s liquidity by automating the rebalance process, socialising the rebalance cost, and subsidising it through the refuelling mechanism. This ensures that during volatile moments the majority of the pool’s liquidity remains concentrated where it is needed most.

Instead of relying on individual LPs to pay the cost of rebalancing liquidity, FXSwap draws on a refuelling budget. When volatility causes the pool price to dislocate from the oracle price, arbitrageurs are able to profit by rebalancing the pool. They do so by injecting part of the refuelling budget into the pool to subsidise the cost of moving the liquidity. In the above diagram, we plot the refuelling transactions in the pool. For the period measured, over $460k was spent in refuelling transactions - this sum represents the effective cost of maintaining the pool’s liquidity concentration.

In concrete terms, the differences in how UniV3 and FXSwap manage pool liquidity result in different outcomes for how the pool’s assets are priced. A clear example of this can be seen on Nov 21, when a sudden drop in the BTC price below $83k caused the price to fall outside both pools liquidity concentration, spiking the price impact for the larger quotes. The peak in the FXSwap pool’s price impact for the $10m quote was much lower at just 7.51% compared to 12.45% in UniV3. Moreover, the FXSwap pool was able to rebalance its liquidity more effectively, quickly stabilising price impact between 5-6% whilst UniV3 remained elevated at >10%.

In UniV3, not only was the loss of liquidity concentration much deeper, but it lasted for a sustained period of time. The FXSwap pool was able to automatically rebalance itself in a short space of time, as the cost of moving liquidity could be subsidised by a refuelling budget that had been accumulated for a moment of volatility such as this.

The following animation illustrates how these different pool types allocate liquidity and how this affects price impact:

UniV3 WBTC (top) vs Yieldbasis WBTC (bottom) liquidity distribution and price impact
We plotted a liquidity map for the UniV3 and FXSwap pools to illustrate the differences in how liquidity is distributed and show how liquidity depth is related to price impact. In the UniV3, each bar represents a tick range equivalent to a 0.6% price move. In FXSwap there is no concept of ticks, as liquidity is distributed by the AMM along a continuous curve, so to enable a direct comparison we bin the FXSwap liquidity into 0.6% price moves and report liquidity ‘at current bin’ in a stats window. This enables us to compare the dollar value of the ‘in-range liquidity’ in each pool’s active tick/bin. For example, in the final frame, we see that UniV3 had $679k of liquidity within the active tick range, whilst Yieldbasis had $1.39m in the equivalent bin. By having twice as much liquidity available in this active range, the FXSwap pool’s superior depth of market means it can deliver significantly better pricing for larger quotes.

In Univ3 we see that when the price suddenly moves lower, the majority of liquidity remains far away from where it is needed. On fast moves - like Nov 21 - there is some lag before liquidity is moved into the relevant range. We also see LPs positioning themselves in anticipation of where the price might move, but these bets are often wrong. Thus we see liquidity being continually repositioned whilst only a small portion of the overall pool TVL is actually in range. The relationship between the decreased liquidity depth and the increased price impact is clear to see from the chart.

In comparison, FXSwap concentrates liquidity uniformly along a curve. Like in UniV3, when the price initially moves lower the pool can also become imbalanced, with the majority of the liquidity remaining concentrated around a higher price range. However, FXSwap’s automatic rebalancing is far more responsive on sudden moves and the pool does a better job of dragging the liquidity concentration closer to the trading range, eventually restoring balance. Once rebalanced, the pool has significantly more liquidity depth than the UniV3 pool and so provides better quotes. Moreover, FXSwap ensures that the liquidity of all LPs in the pool is being utilised, returning a consistent yield with no management overhead.

As a further comparison, we also provide the same animation for the Yieldbasis cbBTC pool. Due to its fast fee-free redemptions through Coinbase, cbBTC is more frequently arbitraged than WBTC, leading to more frequent pool rebalances. We observe a liquidity concentration which is very responsive to price changes, ensuring a low and stable price impact. Of all the pools studied, the Yieldbasis cbBTC pool consistently performed the best. Following the pool cap raise to $200m in December price impact drops to just ~1% for the $10m quote. In comparison, the price impact of an equivalent route through Uniswap was significantly larger on average, providing better execution for a $10m swap in 82% of blocks measured. Moreover, due to liquidity movements in the relatively shallow cbBTC/WBTC 0.01% pool, the cbBTC quotes on Uniswap proved far less stable, briefly spiking to >300% price impact on Nov 21 whilst the Yieldbasis quotes only peaked at ~3.5%.

Comparison of UniV3 vs Yieldbasis cbBTC depth
This illustrates a key drawback of the CLAMM design - LPs are often not sufficiently responsive during periods of high volatility, leaving liquidity thin when it is needed most. This creates fragility in the DeFi market structure, as lending market assumptions about the price at which a position could be liquidated can break down under these extreme market conditions. By comparison, Curve’s automated liquidity management has repeatedly proven resilient during times of stress, proving the ‘liquidity of last resort’ to DeFi markets precisely when it’s needed most.

Conclusion
Our study shows that the new FXSwap pool implementation offers significant advantages over UniV3 CLAMM pools.

When compared against UniV3, FXSwap proved more responsive during volatile periods, ensuring deep liquidity remains available when it is needed most. Liquidity in the pool was better concentrated around the active price range most of the time, resulting in significantly lower price impact for large trades despite a similar pool TVL.

FXSwap marks an important milestone in the evolution of AMM design, with wide-ranging second-order effects across DeFi. Yieldbasis’ introduction of deep, reliable BTC liquidity on-chain strengthens DeFi markets and adds significant utility to the listed assets. Greater depth during periods of volatility allows liquidations to be executed at better prices, potentially supporting higher LTV ratios for those assets.

With foreign exchange pools such as ZCHF/crvUSD now being rolled out on Curve, the natural next question is how this mechanism generalises across non-correlated pairs and across volatility regimes. If refuelling can reliably keep depth close to the active price while fees remain competitive, FXSwap pools offer a credible path to tighter spreads and more dependable on-chain execution for fiat-pegged pairs.

More broadly, this study suggests a design direction for volatile AMMs: automate concentration, and socialise the cost of keeping it relevant when the market moves. For large trades, execution quality is dominated less by raw TVL than by how quickly liquidity can be re-centred when price moves. FXSwap’s refuelling mechanism turns that rebalancing problem into a pooled, subsidised process, making depth more available when volatility would otherwise push it out of range.

That said, the mechanism is not free. Better liquidity concentration is purchased with an explicit refuelling budget and fee policy. The practical question for deployments is how to tune fees and refuelling to strike the right balance between volume and fees. Given the dominance of Yieldbasis’ quotes for large swaps, finding a way to dynamically manage fees and capture these excesses could significantly increase fee revenue - a fruitful area of AMM design for further research.
