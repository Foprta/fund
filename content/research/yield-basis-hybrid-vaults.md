---
title: "Yield Basis Hybrid Vault: масштабирование с поддержкой пега crvUSD"
summary: "Hybrid Vault Yield Basis (live в проде) для безопасного масштабирования TVL через Personal Caps, привязанные к вкладу в стабильность crvUSD. Personal Cap задаётся настраиваемым governance-параметром, целевая доля сейчас 45% (депозит $4500 crvUSD → cap $10000 ETH/BTC, ≈2.22×). Механика депозитов scrvUSD, аналогия с Dual Staking (CoreDAO/Stacks), эффект на спрос crvUSD. Не покрывает: точные realized caps/даты запуска, конкретные APY вне иллюстраций."
topics: [YieldBasis, crvUSD, HybridVault, Curve, stablecoin]
version: 2
---

The Hybrid Vault: Yield Basis scaling preserving $crvUSD stability
Since the launch of Yield Basis, all pools have been fully filled:
With each raise, the cap was filled in a matter of minutes
Demand for IL-free yield far exceeds the TVL that Yield Basis can accept
Thus, the primary focus is safe TVL scaling
The Hybrid Vault is the solution Yield Basis uses to scale, enabling Personal Caps for LPs participating in $crvUSD stability support. It is live in production (the design originated in the article summarized below).
The reason for the TVL limit
 
By capping YB pools, Yield Basis limits its influence on the $crvUSD peg and ensures safe utilization of Curve’s infrastructure:
IL is mitigated by creating and maintaining 2x leverage in YB pools.
$crvUSD borrowed from Curve DAO is used for liquidity and leverage purposes.
Swaps in YB pools trigger $crvUSD-stable swaps at Curve; significant BTC or ETH volatility could influence the $crvUSD peg
The YB<>$crvUSD interaction was recently covered in a comprehensive analysis by Llamarisk. It emphasizes the necessity of growing $crvUSD supply (minted by independent users) among other recommendations.
The observation on the possible limit for Yield Basis TVL cap calculated based on the current state of PegKeepers pools now is approximately $25m lower than the actual TVL.
Image
https://gov.curve.finance/t/heuristics-for-yieldbasis-to-roll-out-its-credit-line/10985
These results clearly demonstrate the following: Yield Basis requires a solution to provide additional support for the $crvUSD peg beyond the current subsidies (YB emissions provided as bribes to $crvUSD pools).
Scaling approach: $crvUSD Hybrid Vault (live)
 
Hybrid Vault is a vault that directly links $crvUSD peg support action with controlled TVL onboarding into the Yield Basis pool.
The core idea is to enable users to enter the Yield Basis pool by establishing a Personal Cap, determined by their contribution to $crvUSD peg stability:
$crvUSD deposit & stability contribution
Users deposit $crvUSD into the Hybrid Vault.
Deposited $crvUSD is automatically staked into $scrvUSD, generating yield (currently approximately 2.5% APY).
Personal Cap Creation
Upon deposit, a Personal Cap is created automatically.
The Personal Cap is governed by a configurable ratio: the deposited $crvUSD must represent a target share of the onboarded Yield Basis position. The current target is 45% — i.e. depositing $4,500 of $crvUSD unlocks a Personal Cap of $10,000 of ETH/BTC capital in the YB pool (≈ 2.22× the deposit). This ratio is a tunable governance parameter (earlier designs used a fixed 2.5× multiplier).
This cap defines the maximum amount of capital the user can onboard into the Yield Basis pool outside of the usual caps.
Withdrawal mechanics
Withdrawal of $crvUSD from the Hybrid Vault is gated by withdrawals from the Yield Basis pool.
To withdraw X amount of $crvUSD, the user must first withdraw the proportional amount of assets from the Yield Basis pool (at the current 45% target, ≈ 2.22·X worth), provided that there was no free cap beforehand.
Asset values are calculated at the exchange rate at the time of withdrawal.
Example user journey (at the current 45% target):
The user deposits 4,500 $crvUSD into the Hybrid Vault (which is deposited into $scrvUSD thereafter)
The user deposits $10,000 worth of WETH into the WETH pool.
To withdraw 50% of the $crvUSD position (2,250 $crvUSD), the user must first withdraw $5,000 equivalent to the existing WETH position, calculated at the prevailing exchange rate at the time of withdrawal.
Reference for a Hybrid Vault idea: Mechanics similar to the Hybrid Vault (in a different context), commonly referred to as “Dual Staking,” are used in the CoreDAO and Stacks protocols:
CoreDAO (EVM-compatible BTC Layer 1) has a dual consensus mechanism secured by BTC stakes and CoreDAO native token stakes at the same time. Staking only BTC, users receive minimal rewards in $CORE tokens. To increase the rewards amount, users must purchase $CORE and participate in Dual Staking, receiving $CORE rewards in amounts corresponding to the Boost Tier. Note, there are no rewards in native $BTC, only in $CORE; rewards are immediately liquid while staked $CORE has a 7 day withdrawal delay.
Stacks (Bitcoin L2) has a similar mechanism of dual staking. To receive rewards above the minimum baseline amount, users need to deposit not only BTC, but also $STX which boosts rewards up to 10x. Dual Staking rewards are paid out in sBTC and available after the PoX cycle is completed (2 weeks).
Analogy: the Dual Staking approach is created for enhancing cryptoeconomic security (cost of consensus attack) in mentioned networks, Hybrid Vault is created to enhance economic security (preserve stability) of $crvUSD.
Hybrid Vault effect on $crvUSD
 
The llamarisk report primarily emphasizes the need for additional mint markets to preserve $crvUSD stability:
“This is because mint markets remain the most direct revenue driver for crvUSD (creating demand for the stablecoin via scrvUSD).”
The Hybrid Vault serves a very similar purpose:
It creates direct demand for the stablecoin, as participation requires $crvUSD deposits (which must be directly minted or purchased by the user).
It can be considered as an alternative revenue driver for $crvUSD, since TVL deposited in case of a Personal Cap generates revenue for $crvUSD (which is tied to $crvUSD ownership & usage).
Explanation of $crvUSD alternative revenue driver: user deposits 4,500 $crvUSD and $10,000 WETH to the Vault (at the current 45% target).
The user's annual yield is a theoretical calculation that assumes the $scrvUSD Vault reward APY and the WETH price remain stable and that the WETH earns an 8% APY, as in the simulations:
$112.5 from $scrvUSD (2.5%) and 8%, or $800, from WETH
If the user instead deposits $4,500 in $crvUSD into a low-risk, stablecoin yield option, such as the $crvUSD-$USDC pool at StakeDAO, the revenue will be ~7%, or $315. The $10,000 $ETH LST revenue will be ~2.5%, or $250. This gives us a total of $565.
Therefore, by owning $crvUSD and utilizing the unique option to participate in the Yield Basis Pool via the Hybrid Vault, the user generated an additional $347.5 in yield.
So, Hybrid Vault replicates the core economic mechanics of the mint market, incentivizing $crvUSD demand through a revenue-generating mechanism.
The Llamarisk analysis further states:
“Additional mint markets: In addition, we believe there is a need for additional mint markets. This enables use cases where leverage is, ideally, independent of market cycles to avoid contraction in bearish conditions and attract size.”
The introduction of the Hybrid Vault directly aligns with it, as it:
Enables demand mechanism that is less dependent on market cycles
Provide alternative, non-cyclical pathway for scale $crvUSD
It becomes possible since Yield Basis pools generate yield from volatility, not from market direction itself.
So, the Hybrid Vault is not only a solution to scale Yield Basis, it can be also considered as a solution to enrich $crvUSD yield options.
Implementation status
 
The Hybrid Vault has passed its audit, cleared YB DAO governance, and is live in production: deposits and the UI are enabled. (The pathway followed the steps below — audit → official YB DAO proposal with specifications and initial cap → governance approval → deployment.)
Note that:
YB DAO sets the Hybrid Vault Cap for each pool, since the protocol still has an overall TVL cap, as it is limited primarily by the $crvUSD credit line from CurveDAO.
The Personal Cap ratio (currently a 45% target) is itself a governance-tunable parameter.
The vision is to gradually increase the utilization of the credit line by Hybrid Vault until the $1 billion limit is reached.
Based on the results of the live Hybrid Vault and its impact on $crvUSD peg stability, YB DAO continues to decide on the next steps for the $crvUSD credit line.
 
This publication is provided for informational purposes only and does not constitute financial advice, investment advice, or an offer or solicitation to acquire any digital asset. All mechanisms described are subject to governance approval, smart-contract logic, and applicable regulatory requirements, including MiCA and AML/CFT frameworks. Any examples or calculations are illustrative and non-binding; past or hypothetical performance does not guarantee future results.
