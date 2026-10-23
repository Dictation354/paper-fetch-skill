---
title: "Hashprice moderates the electricity demand response of Bitcoin miners"
authors: "Subir Majumder"
journal: "arXiv"
doi: "10.48550/arxiv.2606.00587v2"
published: "2026-06-03"
source: "arxiv_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 14079
---

# Hashprice moderates the electricity demand response of Bitcoin miners

## Abstract

Large controllable loads, such as Bitcoin-mining facilities, are increasingly viewed as valuable sources of power-system flexibility, yet the conditions under which this flexibility is realized remain poorly understood. We examine this issue in the Texas power market, where large loads face both wholesale electricity prices and incentives created by coincident-peak-based transmission charges. We find that mining load declines as costs rise across both channels, and this response is moderated by hashprice, a measure of expected revenue for Bitcoin miners. When hashprice is higher, mining load is less responsive to electricity-sector costs. This pattern is consistent with aggregate mining load arising from heterogeneous devices operated around distinct breakeven points. The wholesale-price response illustrates this mechanism most clearly. Mining load remains largely online at low electricity prices but begins to decline once prices exceed an implied curtailment threshold, and higher hashprice shifts this threshold to higher wholesale prices. Bitcoin miners therefore respond to electricity-sector costs, but the available flexibility varies with revenue conditions in the crypto-financial sector. Treating such loads as stable demand-response resources may overstate their available flexibility.

## keywords

Bitcoin mining, Demand response, State-dependent demand elasticity, Coincident-peak pricing, Financially driven loads

## 1 Introduction

Modern power systems increasingly need flexible electricity demand. In many countries, aggregate short-run electricity demand has historically been only weakly to moderately responsive to electricity prices [Lijesen (2007)](https://arxiv.org/html/2606.00587v2#bib.bib1); [Labandeira et al. (2017)](https://arxiv.org/html/2606.00587v2#bib.bib2); [Burke and Abayasekara (2018)](https://arxiv.org/html/2606.00587v2#bib.bib3); [Zhu et al. (2018)](https://arxiv.org/html/2606.00587v2#bib.bib4); [Hirth et al. (2024)](https://arxiv.org/html/2606.00587v2#bib.bib5). As renewable generation expands and peak-demand stress raises reliability concerns, loads that can adjust consumption when supply is scarce or system demand is high are becoming more valuable [Martinot (2016)](https://arxiv.org/html/2606.00587v2#bib.bib6); [Brunner et al. (2020)](https://arxiv.org/html/2606.00587v2#bib.bib7); [International Energy Agency (2025)](https://arxiv.org/html/2606.00587v2#bib.bib8); [Suna et al. (2022)](https://arxiv.org/html/2606.00587v2#bib.bib9). Large controllable loads are therefore increasingly viewed as potential sources of demand-side flexibility. Bitcoin mining is a prominent example of a large controllable load that can rapidly adjust electricity use in response to electricity-sector signals [North American Electric Reliability Corporation (2025)](https://arxiv.org/html/2606.00587v2#bib.bib10); [DLA Piper (2023)](https://arxiv.org/html/2606.00587v2#bib.bib11); [Public Utility Commission of Texas (2024)](https://arxiv.org/html/2606.00587v2#bib.bib12); [Gallant (2024)](https://arxiv.org/html/2606.00587v2#bib.bib13); [CPower Energy Management (2024)](https://arxiv.org/html/2606.00587v2#bib.bib14); [Renewable Energy World (2024)](https://arxiv.org/html/2606.00587v2#bib.bib15). Yet it remains unclear whether this flexibility is systematic enough to be treated as a predictable grid resource.

Bitcoin mining provides a useful empirical setting for studying this question because both sides of miners’ short-run operating margin can be measured and can change over short time scales. Electricity is the dominant variable input cost for Bitcoin mining [de Vries (2018)](https://arxiv.org/html/2606.00587v2#bib.bib16). Hashprice, which measures expected mining revenue per unit of computational power per unit time, summarizes the short-run value of continued operation [Hashrate Index (2025)](https://arxiv.org/html/2606.00587v2#bib.bib17); [Neumueller et al. (2025)](https://arxiv.org/html/2606.00587v2#bib.bib18). Operationally, industry accounts and modeling assumptions suggest that mining devices are operated around breakeven points. A device can remain online when expected mining revenue, determined by hashprice and device efficiency, exceeds electricity costs, and is curtailed otherwise [Bratcher (2024)](https://arxiv.org/html/2606.00587v2#bib.bib19); [Menati et al. (2023)](https://arxiv.org/html/2606.00587v2#bib.bib20); [Hajiaghapour-Moghimi et al. (2022)](https://arxiv.org/html/2606.00587v2#bib.bib21); [Garratt and Hayes (2015)](https://arxiv.org/html/2606.00587v2#bib.bib22). Existing empirical work has linked Bitcoin prices, wholesale electricity-price volatility, and mining electricity use [Sapra et al. (2024)](https://arxiv.org/html/2606.00587v2#bib.bib23); [Aye et al. (2023)](https://arxiv.org/html/2606.00587v2#bib.bib24). Still, empirical evidence on Bitcoin miners’ short-run curtailment behavior remains limited.

We examine Bitcoin miners’ short-run curtailment behavior using the institutional setting of the Texas power market, where large loads can be exposed to two distinct electricity-sector cost channels: contemporaneous wholesale electricity prices and incentives created by coincident-peak-based transmission charges. Although we do not observe individual device-level operating decisions, the aggregate response is consistent with mining load being composed of heterogeneous devices operating around their respective breakeven points. Two patterns support this interpretation. First, Bitcoin-mining load declines as electricity-sector costs rise, but this response weakens when hashprice is higher. This state dependence appears across both cost channels. Second, the wholesale-price response reveals an implied curtailment threshold. At a given hashprice, mining load remains largely online at low electricity prices but begins to fall once prices rise sufficiently. Higher hashprice shifts this threshold to higher wholesale prices, consistent with stronger revenue conditions allowing marginal devices to remain profitable at higher electricity costs.

These findings imply that Bitcoin-mining flexibility cannot be treated as a fixed grid resource. Its availability depends partly on revenue conditions in the crypto-financial sector. For power-system operations, planning, and market design, large controllable loads should therefore be modeled as economically state-dependent sources of flexibility.

## 2 Empirical design

In the Texas power market, large loads can be exposed to two electricity-sector cost channels, wholesale electricity prices and coincident-peak-based transmission charges. Under coincident-peak charges, electricity consumption by large loads during system peaks determines their transmission charges for the following year [Baldick (2018)](https://arxiv.org/html/2606.00587v2#bib.bib26); [Carmona et al. (2026)](https://arxiv.org/html/2606.00587v2#bib.bib27). By consuming electricity during intervals that are likely to become coincident peaks, loads forgo the opportunity to reduce future transmission charges through curtailment. This creates an expected opportunity cost of electricity consumption. In Texas, coincident peaks are determined during the summer months, June through September [Public Utility Commission of Texas (1999)](https://arxiv.org/html/2606.00587v2#bib.bib25), so this expected opportunity cost is concentrated in those months. Large loads are also exposed to wholesale electricity prices throughout the year. We use this setting to examine how aggregate Bitcoin-mining load responds to wholesale electricity prices and coincident-peak incentives.

Because the mining-load data are aggregated at the load-zone level, our estimates characterize aggregate behavior across multiple Bitcoin-mining firms within each zone. We pool hourly observations across three Texas load zones.

Our empirical design has two parts. First, we estimate responsiveness to wholesale electricity prices while accounting for broad exposure to coincident-peak incentives using a summer–daytime (SDT) window. The SDT window is defined as June–September, 12:00–19:00 Central time, and captures periods when the Texas power grid is most likely to experience coincident peaks (Figure [1](https://arxiv.org/html/2606.00587v2#S2.F1)A; see Methods). We interpret the SDT-window indicator as an intention-to-treat measure of exposure to coincident-peak incentives. This interpretation requires non-SDT observations to provide a valid counterfactual for SDT observations, conditional on controls and fixed effects [Roth et al. (2023)](https://arxiv.org/html/2606.00587v2#bib.bib28); [Angrist and Pischke (2009)](https://arxiv.org/html/2606.00587v2#bib.bib29). To support this comparison, we construct load-zone-specific growth covariates that account for mining-load growth across zones. After conditioning on these covariates, mining load appears more comparable outside the SDT window and diverges primarily within it (Figure [1](https://arxiv.org/html/2606.00587v2#S2.F1)B–C; see Methods). We therefore estimate the mining-load response associated with the SDT window while conditioning on growth covariates, weather, calendar fixed effects, and load-zone fixed effects.

![Figure 1](acquisition/source-members/figs/Near_peak_Event.png)

![Figure 1](acquisition/source-members/figs/lz_growth.png)

![Figure 1](acquisition/source-members/figs/Parallel_Trend.png)

**Figure 1.** Empirical definition of the summer–daytime window. (A) Historical near-peak events in the Texas power grid. Events are classified as near-peak when June–September system demand is close to the monthly system peak. Their distribution by hour of day and day of week shows that near-peak conditions are concentrated between 12:00 and 19:00 Central Standard Time. This pattern motivates the summer–daytime (SDT) window. (B) Load-zone-specific growth measures. Thick colored lines show the logged growth covariate for each load zone, constructed from prior mining-load observations outside the SDT window. Faint background lines show observed logged mining load. (C) Growth-adjusted mining load by load zone, year, season, and SDT status. Points show average $\log(\text{Mining Load}/\text{growth})$ in pre-summer, summer, and post-summer seasons. Values are shown separately for 2021 and 2022 and for SDT-window hours versus all other hours. Vertical bars show the interquartile range within each year–zone–season–SDT-status cell. After adjustment for growth, non-SDT observations are relatively similar across observed seasons, whereas SDT-window observations show a larger summer reduction in 2022.

Within this framework, we model wholesale-price responsiveness using a reduced-translog specification [Christensen et al. (1973)](https://arxiv.org/html/2606.00587v2#bib.bib30). This flexible demand specification allows the electricity-price response of Bitcoin-mining load to vary with hashprice, consistent with the descriptive patterns in Extended Data Figure [6](https://arxiv.org/html/2606.00587v2#S6.SSx6). Our main specification estimates a common price-response relationship across the three load zones. We also estimate zone-specific specifications to assess whether the response is present within individual zones.

Second, we examine whether mining load responds to the expected opportunity cost created by coincident-peak charges. This opportunity cost is not directly observed, so we proxy for it using a near-peak risk index, denoted NP-risk (see Methods). Higher NP-risk indicates greater proximity to the monthly system peak and therefore a higher expected opportunity cost for consuming electricity. We restrict this analysis to the SDT window, where coincident-peak incentives are concentrated. We also re-estimate the model using an alternative near-peak index to assess whether the results are sensitive to the proxy construction.

## 3 Hashprice moderates Bitcoin miners’ responsiveness to wholesale electricity prices

Our preferred estimates imply a threshold-like response of aggregate Bitcoin-mining load to wholesale electricity prices (Figure [2](https://arxiv.org/html/2606.00587v2#S3.F2)). Although we do not observe individual device-level operations, the fitted aggregate response suggests that mining load reflects heterogeneous devices operating around different breakeven points. Two features of the fitted response support this interpretation. First, at a given hashprice, mining load remains near its effective capacity ceiling when wholesale prices are low but begins to fall once prices rise sufficiently. This implied curtailment threshold shifts to higher wholesale prices when hashprice is higher, consistent with stronger revenue conditions allowing marginal devices to remain profitable at higher electricity costs. Second, within the responsive portion of the demand curve, aggregate load continues to decline as electricity prices rise, suggesting that an increasing share of mining capacity curtails as operating margins deteriorate. Higher hashprice also flattens this responsive region. Within this region, the model-implied electricity-price elasticity is about $-0.5$ at the 25th percentile of hashprice, about $-0.3$ at the median, and close to zero at the 75th percentile.

![Figure 2](acquisition/source-members/figs/bitcoin_miners_price_elasticity.png)

**Figure 2.** Threshold-like wholesale-electricity-price responsiveness of Bitcoin-mining load. (a) Growth-adjusted log mining load plotted against electricity price. Points show hourly observations split into low-hashprice (blue) and high-hashprice (red) groups. Solid lines show model-implied price–response profiles from the matched IV reduced-translog specification in Table [1](https://arxiv.org/html/2606.00587v2#S3.T1), column (3). Profiles are evaluated separately for the two hashprice groups, with other covariates held at their observed values. The dash-dotted black line (i) marks a representative contracted power cost of about \$30/MWh reported by large Texas miners [DeRoche and Elkin (2025)](https://arxiv.org/html/2606.00587v2#bib.bib31). The dotted vertical lines (ii) and (iii) mark where the fitted low- and high-hashprice profiles cross zero on the growth-adjusted log-load scale. These crossings indicate illustrative model-implied thresholds between the near-capacity region and the curtailment region. (b) Model-implied electricity-price elasticity at different hashprice levels. Estimates are from the same matched IV reduced-translog specification. The black line shows the point estimate, and the shaded region shows the 95% confidence interval. The labels p25, p50, and p75 mark the weighted 25th, 50th, and 75th percentiles of hashprice in the matched sample. The rug plot shows the corresponding weighted hashprice distribution.

Table [1](https://arxiv.org/html/2606.00587v2#S3.T1) shows how this pattern emerges across specifications. Column (1) estimates the broad effect associated with the SDT window, controlling for the growth covariate, weather controls, calendar fixed effects, and load-zone fixed effects. Mining load falls by about 9% within the SDT window in 2021, with an additional reduction in 2022 that implies total SDT curtailment of roughly 39%. These estimates are robust to alternative definitions of the SDT window and to an alternative growth covariate (Supplementary Tables 5, 7). Columns (2) and (3) add the reduced-translog block, which includes electricity price, hashprice, and their interaction. We treat these terms as endogenous and estimate the specifications using the instrumental-variables (IV) strategy described in the Methods. In the full-sample IV specification in column (2), the implied electricity-price elasticity, evaluated at \$75/MWh and \$0.15/TH/s/day, is about $-0.12$. The negative electricity-price coefficient and positive electricity-price–hashprice interaction indicate that mining load declines as electricity prices rise, but this response weakens when hashprice is higher. A Wald test rejects the restriction that the electricity-price–hashprice interaction can be omitted ($\chi^{2}=25.34$, $p<0.001$). However, excluding low-electricity-price observations substantially increases the magnitude of the interaction term (Supplementary Table 10).

**Table 1.** Elasticity estimation of Bitcoin mining load with respect to electricity prices and hashprice.Notes: Cluster-robust standard errors, clustered by date, are reported in parentheses. Asterisks denote statistical significance at the 1% (\*\*\*), 5% (\*\*), and 10% (\*) levels. The dependent variable is $\log(\text{Mining Load})$. All specifications include the growth covariate, 9-hour-lagged ambient temperature and its square, calendar fixed effects, and load-zone fixed effects. First-stage statistics report the range across endogenous regressors. Column (1) reports the baseline fixed-effects OLS specification for SDT effect estimation. Columns (2) and (3) incorporate two-stage least-squares (2SLS) estimates for the reduced-translog specification, where $\log(\text{electricity price})$, $\log(\text{hashprice})$, and $\log(\text{electricity price})\times\log(\text{hashprice})$ are treated as endogenous. The excluded instruments are realized Texas power-grid wind generation, logged Bitcoin price, and their interaction. Price variables are centered at \$75/MWh for electricity price and \$0.15/TH/s/day for hashprice, so lower-order coefficients in the translog specification are interpreted at those reference points. Column (3) is estimated on the matched sample using CEM weights. Matching is implemented separately by year using Texas power-grid day-ahead load forecasts and renewable-generation forecasts. Across years, the matched sample retains 29.1% of observations, including 91.1% of treated observations and 20.5% of control observations. Matching reduces overall $L_{1}$ imbalance from 0.847 to approximately zero in 2021 and from 0.876 to approximately zero in 2022.

|                                        |     |                            |                            |                            |
| -------------------------------------- | --- | -------------------------- | -------------------------- | -------------------------- |
|                                        |     | (1) FE-OLS (Baseline)      | (2) Full sample            | (3) Matched sample         |
|                                        |     |                            | IV-2SLS                    | IV-2SLS                    |
| Dependent variable:                    |     | $\log(\text{Mining Load})$ | $\log(\text{Mining Load})$ | $\log(\text{Mining Load})$ |
| SDT | | -0.0921<sup>∗∗∗</sup> | -0.1747<sup>∗∗∗</sup> | -0.0194 |
|                                        |     | (0.0279)                   | (0.0362)                   | (0.0630)                   |
| SDT $\times$ 2022 | | -0.4050<sup>∗∗∗</sup> | -0.1447<sup>∗∗</sup> | -0.2623<sup>∗∗∗</sup> |
|                                        |     | (0.0533)                   | (0.0686)                   | (0.0649)                   |
| $\log(\text{electricity price})$ | | — | -0.1154<sup>∗∗∗</sup> | -0.3050<sup>∗∗∗</sup> |
|                                        |     |                            | (0.0272)                   | (0.0636)                   |
| $\log(\text{hashprice})$ | | — | 0.2010<sup>∗∗∗</sup> | 0.3030<sup>∗∗</sup> |
|                                        |     |                            | (0.0475)                   | (0.1269)                   |
| $\log(\text{electricity price})\times$ | | — | 0.2359<sup>∗∗∗</sup> | 0.5311<sup>∗∗∗</sup> |
| $\log(\text{hashprice})$               |     |                            | (0.0469)                   | (0.1099)                   |
| $\log(\text{growth})$ | | 0.9906<sup>∗∗∗</sup> | 0.9835<sup>∗∗∗</sup> | 0.9350<sup>∗∗∗</sup> |
|                                        |     | (0.0299)                   | (0.0318)                   | (0.1218)                   |
| temperature | | 0.0185<sup>∗∗∗</sup> | 0.0204<sup>∗∗∗</sup> | 0.0431<sup>∗∗∗</sup> |
|                                        |     | (0.0048)                   | (0.0051)                   | (0.0158)                   |
| temperature<sup>2</sup> | | -0.0001<sup>∗∗∗</sup> | -0.0001<sup>∗∗∗</sup> | -0.0003<sup>∗∗∗</sup> |
|                                        |     | (0.0000)                   | (0.0000)                   | (0.0001)                   |
| Controls and FE                        |     | Yes                        | Yes                        | Yes                        |
| Observations                           |     | 29,635                     | 29,635                     | 8,637                      |
| Covariance Type                        |     | Clustered                  | Clustered                  | Clustered                  |
| $R^{2}$ (Within)                       |     | 0.4687                     | —                          | —                          |
| $R^{2}$                                |     | 0.6540                     | 0.6562                     | 0.6675                     |
| First-stage Partial $R^{2}$            |     | —                          | 0.18–0.93                  | 0.18–0.80                  |
| First-stage Partial $F$                |     | —                          | 642–20,371                 | 77–1,407                   |

Our preferred specification in column (3) re-estimates the reduced-translog model on a matched sample constructed using coarsened exact matching (CEM) [Iacus et al. (2012)](https://arxiv.org/html/2606.00587v2#bib.bib32) on system-wide demand and renewable-generation forecasts. Matching improves comparability between SDT and non-SDT observations by ensuring that they occur under similar forecasted grid conditions (Supplementary Figure 7). However, matching also reduces the influence of low-load, high-renewable states in the reduced-translog model, in which mining load is often near its effective capacity ceiling (Supplementary Figure 8). The matched-sample estimate implies an elasticity of about $-0.30$ at \$75/MWh and \$0.15/TH/s/day. By contrast, the corresponding elasticity is about $-0.05$ in the excluded observations. The matched-sample estimate also remains stable when low-price observations are removed (Supplementary Tables 11–12). We therefore use the matched-sample IV reduced-translog model as our preferred specification. Because the reduced-translog specification is smooth and unconstrained, it can extrapolate outside the physically and economically meaningful region for Bitcoin miners. We therefore interpret the fitted response only within the region defined by non-positive electricity-price elasticity, non-negative hashprice elasticity, and fitted growth-adjusted log mining load no greater than zero. Outside this region, we interpret mining load as operating near an effective capacity ceiling (Supplementary Note 2; Supplementary Figure 9). Figure [2](https://arxiv.org/html/2606.00587v2#S3.F2) illustrates the fitted demand curves implied by this interpretation.

Re-estimating the model separately by load zone yields a similar wholesale-price response despite smaller samples. The electricity-price coefficients remain negative, and joint Wald tests reject the null that the translog price terms are jointly zero in each zone (Supplementary Table 13). The magnitudes vary across zones, consistent with regional differences in mining fleet composition. Our preferred wholesale-electricity-price measure is the average of day-ahead and real-time prices; results are similar when using day-ahead or real-time prices separately (Supplementary Table 9).

## 4 Mining load responds to incentives created by coincident-peak-based transmission charges

The wholesale-price results show that aggregate Bitcoin-mining load decreases when wholesale electricity prices rise, and this response weakens when expected mining revenue is higher. Coincident-peak-based transmission charges create a second electricity-sector cost channel. Unlike wholesale electricity prices, the cost created by coincident-peak charges is not observed as a contemporaneous price. We therefore proxy for this cost using near-peak risk, which measures how close an interval is to becoming a coincident peak. Higher near-peak risk implies a higher expected opportunity cost of electricity consumption. If miners internalize this opportunity cost, aggregate mining load should fall as near-peak risk rises, and this response should be weaker when hashprice is higher.

**Table 2.** Bitcoin-mining load response to near-peak risk, wholesale electricity prices, and hashprice.Notes: Cluster-robust standard errors, clustered by date, are reported in parentheses. All columns use hourly summer–daytime observations. Asterisks denote statistical significance at the 1% (\*\*\*), 5% (\*\*), and 10% (\*) levels. The dependent variable is $\log(\text{Mining Load})$. All specifications include the growth covariate, 9-hour-lagged ambient temperature and its square, calendar fixed effects, and load-zone fixed effects. First-stage statistics report the range across endogenous regressors. Column (4) includes the NP-risk–hashprice block, column (5) includes the electricity-price–hashprice block, and column (6) includes both blocks jointly. The endogenous variables are the included NP-risk block, electricity-price block, and logged hashprice, as applicable in each specification, estimated using 2SLS. The excluded instruments are held fixed across columns and consist of Houston cooling degree days, Texas power-grid wind generation, logged Bitcoin price, and the corresponding interaction instruments. Variables are centered at $0.50$ for NP-risk, \$75/MWh for electricity price, and \$0.15/TH/s/day for hashprice, so lower-order coefficients in the specifications are interpreted at those reference points.

|                                  | (4) NP-risk block          | (5) Electricity price      | (6) NP-risk block          |
| -------------------------------- | -------------------------- | -------------------------- | -------------------------- |
|                                  |                            | block                      | + Electricity price block  |
| Dependent variable:              | $\log(\text{Mining Load})$ | $\log(\text{Mining Load})$ | $\log(\text{Mining Load})$ |
| NP-risk | -1.1831<sup>∗∗∗</sup> | — | -0.8313<sup>∗∗∗</sup> |
|                                  | (0.1784)                   |                            | (0.1579)                   |
| NP-risk | 1.1389<sup>∗∗∗</sup> | — | 0.6018<sup>∗∗∗</sup> |
| $\times\log(\text{hashprice})$   | (0.2265)                   |                            | (0.2123)                   |
| $\log(\text{electricity price})$ | — | -0.3231<sup>∗∗∗</sup> | -0.2349<sup>∗∗∗</sup> |
|                                  |                            | (0.0554)                   | (0.0568)                   |
| $\log(\text{electricity price})$ | — | 0.6530<sup>∗∗∗</sup> | 0.6210<sup>∗∗∗</sup> |
| $\times\log(\text{hashprice})$   |                            | (0.0845)                   | (0.0852)                   |
| $\log(\text{hashprice})$ | -0.8109<sup>∗∗∗</sup> | -0.5553<sup>∗∗∗</sup> | -0.7706<sup>∗∗∗</sup> |
|                                  | (0.2002)                   | (0.2015)                   | (0.2011)                   |
| $\log(\text{growth})$ | 1.1092<sup>∗∗∗</sup> | 1.2015<sup>∗∗∗</sup> | 1.1575<sup>∗∗∗</sup> |
|                                  | (0.1034)                   | (0.1047)                   | (0.1048)                   |
| temperature | -0.0523<sup>∗∗</sup> | -0.0311 | -0.0433<sup>∗∗</sup> |
|                                  | (0.0235)                   | (0.0218)                   | (0.0218)                   |
| temperature<sup>2</sup> | 0.0004<sup>∗∗</sup> | 0.0001 | 0.0003<sup>∗∗</sup> |
|                                  | (0.0002)                   | (0.0002)                   | (0.0002)                   |
| Controls and FE                  | Yes                        | Yes                        | Yes                        |
| Observations                     | 3,630                      | 3,630                      | 3,630                      |
| Covariance type                  | Clustered                  | Clustered                  | Clustered                  |
| $R^{2}$ (overall)                | 0.3583                     | 0.4004                     | 0.4160                     |
| First-stage partial $R^{2}$      | 0.47–0.85                  | 0.32–0.85                  | 0.32–0.85                  |
| First-stage partial $F$          | 324–2,947                  | 165–2,947                  | 165–2,947                  |

We test this prediction by estimating whether aggregate mining load declines with NP-risk and whether this relationship is moderated by hashprice. Because these opportunity costs are relevant primarily during coincident-peak determination periods, we restrict the analysis to SDT observations. Because NP-risk may be correlated with contemporaneous wholesale electricity prices, we compare specifications that include the NP-risk–hashprice block, the electricity-price–hashprice block, and both blocks jointly. The joint specification, reported in column (6) of Table [2](https://arxiv.org/html/2606.00587v2#S4.T2), is our preferred specification because it allows us to assess whether the relationship between mining load and near-peak risk persists after accounting for the contemporaneous wholesale-price signal. All specifications include the growth covariate, weather, calendar fixed effects, and load-zone fixed effects. We treat the included NP-risk, wholesale-price, hashprice, and interaction terms as endogenous and estimate the specifications using the IV strategy described in the Methods.

![Figure 3](acquisition/source-members/figs/NP_Risk_Index_Response.png)

**Figure 3.** Hashprice moderates the relationship between near-peak risk and Bitcoin-mining load. Growth-adjusted log Bitcoin-mining load is plotted against the near-peak risk index, NP-risk. Points represent hourly SDT observations split into low- and high-hashprice groups. Solid lines show model-implied responses from the specification in Table [2](https://arxiv.org/html/2606.00587v2#S4.T2), column (6). Higher NP-risk indicates a greater likelihood of contributing to future transmission charges.

The estimates support the predicted state-dependent response. In the NP-risk-only specification, higher NP-risk is associated with lower mining load, while the positive NP-risk–hashprice interaction indicates that this relationship weakens when hashprice is higher. When the NP-risk and electricity-price blocks are included jointly, the NP-risk coefficients attenuate but remain statistically and economically meaningful. A joint Wald test rejects the null that the NP-risk terms are jointly zero ($\chi^{2}=28.18$, $p<0.001$). We also re-estimate these specifications using an alternative NP-risk measure; the estimated coefficients preserve the same sign pattern (Methods; Supplementary Table 16). These results suggest that mining load responds to coincident-peak incentives in a way that is not solely explained by contemporaneous wholesale electricity prices. Figure [3](https://arxiv.org/html/2606.00587v2#S4.F3) illustrates the implied response, mirroring the state dependence observed in the wholesale-price response. Finally, because coincident-peak incentives should be most relevant during the SDT window, we estimate placebo specifications for summer nights and non-summer windows. The SDT specification is the only one that exhibits the expected sign pattern (Supplementary Table 17).

## 5 Discussion

Aggregate Bitcoin-mining load is flexible, but not in a fixed or unconditional way. Its responsiveness to electricity-sector costs depends on the revenue state of mining. We find that mining load declines when electricity-sector costs rise, and this response weakens when hashprice is higher. This state dependence appears across two distinct cost channels, contemporaneous wholesale electricity prices and expected opportunity costs created by coincident-peak-based transmission charges. The wholesale-price response provides the clearest evidence of the mechanism underlying Bitcoin miners’ demand response: aggregate mining load remains near its effective capacity ceiling at low prices, then begins to fall beyond an implied curtailment threshold. Higher hashprice shifts this threshold toward higher electricity prices. This behavior is consistent with heterogeneous mining devices operating around different breakeven points. As electricity-sector costs rise, devices with lower breakeven prices are curtailed first, generating the aggregate threshold-like response. Higher expected mining revenue raises these breakeven prices, allowing mining load to remain online at electricity prices that would otherwise induce curtailment.

This state dependence matters for power systems. Bitcoin-mining facilities may appear to offer a large source of demand response, but the flexibility available to the grid depends partly on revenue conditions in the crypto-financial sector. Treating such load as a stable flexibility resource may therefore overstate available demand response during periods when mining revenues are high. This interpretation is subject to several limitations. Mining-load data are aggregated to load zones, coverage differs across zones over time, hashprice is observed daily, whereas electricity prices are observed hourly, and we do not observe device-level operations, contractual exposure, or firm-specific curtailment strategies. Nevertheless, the consistency of the estimated responses across wholesale-price and coincident-peak cost channels supports the interpretation that Bitcoin-mining flexibility is economically state dependent. This state dependence may not be unique to Bitcoin mining. Similar patterns may arise in other emerging flexible-load sectors with sector-specific revenue couplings, including hydrogen electrolysis [Ruhnau (2022)](https://arxiv.org/html/2606.00587v2#bib.bib33), energy-intensive AI data centers [Colangelo et al. (2026)](https://arxiv.org/html/2606.00587v2#bib.bib34), and other electricity-intensive processes often assumed to be flexible. Estimating demand-side flexibility for planning, operations, and market design therefore requires identifying not only the electricity-sector signals that induce curtailment, but also the external revenue conditions that determine whether curtailment is economically attractive.

## 6 Methods

### Data

We construct an hourly panel linking Bitcoin-mining-related electricity-consumption data to mining-revenue conditions, ERCOT wholesale electricity prices, ERCOT grid conditions, and local weather. ERCOT operates most of the Texas electricity grid. In the main text, we use “Texas power market” and “Texas power grid” as shorthand for ERCOT; in the Methods, we use “ERCOT” to match the terminology used in data sources and market rules.

ERCOT provided confidential hourly observations of Large Flexible Load (LFL) power consumption aggregated to the load-zone level under a data-use agreement. The sample covers three ERCOT load zones: West, from January 1, 2021, through July 24, 2022; North, from March 2, 2022, through July 24, 2022; and South, from June 15, 2021, through December 12, 2022. We use load-zone LFL consumption as a proxy for Bitcoin-mining-related load. Because the LFL category may include some flexible loads that are not Bitcoin miners, we interpret our estimates as responses of ERCOT LFL consumption associated with Bitcoin-mining activity. This interpretation is supported by ERCOT documentation linking LFL forecasts to crypto-mining facilities and Bitcoin-market conditions [Electric Reliability Council of Texas (2025b)](https://arxiv.org/html/2606.00587v2#bib.bib35).

LFL consumption is measured in MW and can equal zero during curtailment episodes. To retain zero-load observations in logarithmic specifications, we add an offset of 0.0001 MW before taking logs. For notational simplicity, we refer to the resulting transformed outcome for load zone $z$ and hour $t$ as $\log(\text{Mining Load}_{zt})$ throughout.

We measure mining-revenue conditions using hashprice, defined as expected U.S.-dollar-denominated mining revenue per unit of computational power per unit time [Luxor Documentation Hub (2025)](https://arxiv.org/html/2606.00587v2#bib.bib36); [Neumueller et al. (2025)](https://arxiv.org/html/2606.00587v2#bib.bib18). We use the daily hashprice series published by Luxor and obtain both hashprice and Bitcoin price data from [https://hashrateindex.com/](https://hashrateindex.com/). These daily series are merged into the hourly panel by calendar date. The hashprice series is shown in Supplementary Figure 6.

Wholesale electricity prices are measured using hourly ERCOT day-ahead market (DAM) and real-time market (RTM) prices for each load zone. For the main elasticity specifications, we summarize wholesale price conditions using the average of DAM and RTM prices:

$$
\begin{aligned}
P_{zt}=\frac{\text{DAM Price}_{zt}+\text{RTM Price}_{zt}}{2}.
\end{aligned}\tag{1}
$$

We log-transform this variable in the empirical specifications. Hours in which the averaged electricity price is non-positive are excluded because the logarithm is undefined for these observations.

ERCOT grid conditions are measured using public day-ahead forecasts of ERCOT-wide demand, wind generation, and solar generation. For each operating day $d$, we use forecasts posted on day $d-1$ before the 10:00 cutoff for day-ahead market participation [Electric Reliability Council of Texas (2025a)](https://arxiv.org/html/2606.00587v2#bib.bib37). Specifically, we use the system load forecast posted around 09:30 and the wind and solar generation forecasts posted around 09:55. These forecasts were publicly available before the day-ahead market participation cutoff and therefore represent information that could have been available to miners when forming expectations about next-day operating conditions (Supplementary Figure 1). We sum the wind and solar forecasts to construct a renewable-generation forecast. We also collect realized ERCOT demand and realized ERCOT wind generation. Historical ERCOT demand from 2015 through 2020 is collected separately to define the summer–daytime (SDT) window described below.

To capture local ambient conditions relevant to mining operations, we assign a representative dry-bulb temperature series to each ERCOT load zone. Representative locations are chosen based on the approximate locations of large-scale Bitcoin-mining facilities shown in Supplementary Figure 2. Hourly dry-bulb temperature data are obtained from [https://meteostat.net](https://meteostat.net). We also collect Houston dry-bulb temperature and construct daily cooling degree days (CDD) relative to a base temperature of 65<sup>∘</sup>F. Daily CDD values are merged into the hourly panel by calendar date.

To proxy for effective installed mining capacity, we construct a growth covariate using only prior mining-load observations outside the SDT window:

$$
\begin{aligned}
\text{growth}_{zt}=\max_{\begin{subarray}{c}s<t,\ s\notin\text{SDT}\end{subarray}}\text{Mining Load}_{zs}.
\end{aligned}\tag{2}
$$

This measure depends only on mining load observed before hour $t$ and outside the SDT window, so it does not mechanically incorporate contemporaneous SDT curtailment. In the estimation sample, $\text{growth}_{zt}$ is strictly positive, allowing us to include $\log(\text{growth}_{zt})$ in the empirical specifications. The resulting growth covariate for each load zone is shown in Figure [1](https://arxiv.org/html/2606.00587v2#S2.F1)B. As a robustness check, we also construct an alternative growth covariate using a piecewise linear fit to non-SDT mining load.

All timestamps are converted to a fixed Central Standard Time (CST) convention before merging. This avoids discontinuities associated with daylight saving time transitions and ensures that calendar variables are defined consistently across the panel. Hour-of-day, day-of-week, month, and year indicators are constructed using this fixed-time convention. Hours with missing observations are excluded from the analysis. Because LFL data become available on different dates across load zones, the panel is unbalanced. All specifications use the available zone-hour observations. Descriptive statistics for the analysis sample are reported in Supplementary Table 1.

### SDT window

Under Public Utility Commission of Texas rules, coincident peaks are determined separately for each summer month, June through September, based on system peak demand [Public Utility Commission of Texas (1999)](https://arxiv.org/html/2606.00587v2#bib.bib25). We define the summer–daytime (SDT) window using historical ERCOT-wide demand from 2015–2020 and ERCOT estimates of the maximum load actively pursuing reduction during coincident-peak intervals (Supplementary Table 2). This pre-sample procedure identifies hours in which reported responsive load could have affected which interval set the coincident peak.

For year $y$, summer month $m$, and hour $t$, let $\text{Demand}_{ymt}$ denote realized ERCOT system demand, $\text{Curtailable\_Load}_{y}$ denote ERCOT’s reported maximum responsive load during coincident-peak intervals, and $\text{Peak\_Demand}_{ym}$ denote the realized monthly system peak. We define near-peak hours as

$$
\begin{aligned}
\begin{split}H^{\text{near-peak}}_{ym}&=\bigl\{t\in(y,m):\ \text{Demand}_{ymt}+\text{Curtailable\_Load}_{y}\\
&\hphantom{=\bigl\{t\in(y,m):}\geq\text{Peak\_Demand}_{ym}\bigr\}.\end{split}
\end{aligned}\tag{3}
$$

Pooling near-peak hours across 2015–2020 shows that they are concentrated between 12:00 and 19:00 using the fixed CST convention and can occur on both weekdays and weekends (Figure [1](https://arxiv.org/html/2606.00587v2#S2.F1)A). We therefore define the SDT window as June through September, 12:00–19:00 CST. Because this definition uses only pre-sample ERCOT demand and published curtailment estimates, it is determined independently of the mining-load outcomes analyzed in the estimation sample. This timing is consistent with documented coincident-peak intervals during 2001–2014 and with inferred miner-curtailment patterns in 2021–2022 (Supplementary Figures 3–5).

### Difference-in-differences specification

We use the SDT window to estimate broad curtailment responses associated with exposure to coincident-peak incentives. SDT window is defined as June–September, 12:00–19:00. We treat SDT hours as exposed observations and non-SDT hours as comparison observations.

The estimating equation is

$$
\begin{aligned}
\displaystyle\log(\text{Mining Load}_{zt})={} & \displaystyle\alpha_{z}+\gamma_{t}+\beta_{1}\,\text{SDT}_{t}+\beta_{2}\,\text{SDT}_{t}\times\mathbf{1}\{t\in 2022\} \\
{{+ {\theta\hspace{0pt}{\log \left(\text{growth}_{z\hspace{0pt}t} \right)}}} + {f{(\text{Weather}_{z\hspace{0pt}t})}} + \epsilon_{z\hspace{0pt}t}},
\end{aligned}\tag{4}
$$

where $\alpha_{z}$ are load-zone fixed effects and $\gamma_{t}$ includes fixed effects for hour of day, day of week, month, and year. The indicator $\mathbf{1}\{t\in 2022\}$ allows the SDT-window response to differ between 2021 and 2022. The variable $\text{growth}_{zt}$ is the preferred capacity-growth covariate. The weather control function $f(\text{Weather}_{zt})$ includes 9-hour-lagged temperature and its square. Standard errors are clustered by date.

We interpret the SDT coefficients as intention-to-treat responses. This interpretation relies on three considerations. First, the timing of SDT exposure must be plausibly exogenous to realized mining-load outcomes. The summer months are institutionally designated, and the intraday SDT window is defined using ERCOT system-load patterns from 2015–2020, before the mining-load sample.

Second, conditional on fixed effects, weather controls, and capacity-growth adjustment, non-SDT observations must provide a valid counterfactual for SDT observations absent SDT-related coincident-peak incentives. In difference-in-differences terms, SDT and non-SDT mining loads should have followed parallel trends in the absence of these incentives. We address the capacity growth-concern using the preferred growth covariate. The growth-adjusted patterns in Figure [1](https://arxiv.org/html/2606.00587v2#S2.F1)C are consistent with this parallel-trends requirement.

Third, exposed and comparison observations should have common support in system conditions relevant to miners’ operating conditions. To assess this requirement, we also estimate specifications on a matched sample constructed using ERCOT day-ahead load forecasts and renewable-generation forecasts, which were publicly available before the day-ahead market participation cutoff. Matching is implemented separately by calendar year and substantially reduces imbalance in these forecast covariates; the $L_{1}$ imbalance measure falls to approximately zero in both years (Supplementary Figure 7).

In specifications estimated on the matched sample, month-by-year fixed effects are omitted because they make identification rely on relatively thin within-month-year SDT versus non-SDT contrasts. Specifications including month-by-year fixed effects are reported in Supplementary Table 6. We use lagged temperature to allow observed mining load to reflect delayed responses to ambient conditions, such as thermal inertia in mining equipment or cooling systems. The estimates are robust to alternative temperature lags (Supplementary Table 8).

### IV reduced-translog specification

We estimate a reduced-translog specification using two-stage least squares (2SLS) to describe how Bitcoin-mining load varies with wholesale electricity prices and hashprice. The specification allows the electricity-price response to depend on mining-revenue conditions. The SDT block is included in the control vector.

The second-stage equation is

$$
\begin{aligned}
\displaystyle\log(\text{Mining Load}_{zt})={} & \displaystyle\alpha_{z}+\gamma_{t}+\beta_{p}\log P_{zt}+\beta_{h}\log H_{t}+\beta_{ph}\big(\log P_{zt}\,\log H_{t}\big) \\
{{+ {\delta^{\top}\hspace{0pt}X_{z\hspace{0pt}t}}} + u_{z\hspace{0pt}t}},
\end{aligned}\tag{5}
$$

where $P_{zt}$ is the average wholesale electricity price in load zone $z$ and hour $t$, and $H_{t}$ is hashprice. The terms $\alpha_{z}$ are load-zone fixed effects, and $\gamma_{t}$ includes fixed effects for hour of day, day of week, month, and year. The control vector $X_{zt}$ includes $\text{SDT}_{t}$, $\text{SDT}_{t}\times\mathbf{1}\{t\in 2022\}$, $\log(\text{growth}_{zt})$, 9-hour-lagged temperature, and lagged temperature squared. Standard errors are clustered by date.

We treat $\log P_{zt}$, $\log H_{t}$, and their interaction as endogenous. The excluded instruments are ERCOT-wide realized wind generation, logged Bitcoin price, and their interaction. The identifying assumption is that, conditional on controls and fixed effects, these instruments affect mining load only through wholesale electricity prices, hashprice, and their interaction. First-stage and endogeneity diagnostics are reported in Supplementary Note 1 and Supplementary Tables 3–4.

For each endogenous regressor $Z_{zt}\in\{\log P_{zt},\log H_{t},\log P_{zt}\log H_{t}\}$, the first-stage equation is

$$
\begin{aligned}
\displaystyle Z_{zt}={} & \displaystyle\alpha_{z}+\gamma_{t}+\pi_{1}\,\text{Wind}_{t}+\pi_{2}\,\log(\text{BTC price}_{t}) \\
{{+ {\pi_{3}\hspace{0pt}\left({\text{Wind}_{t} \times {\log {(\text{BTC price}_{t})}}} \right)}} + {\rho^{\top}\hspace{0pt}X_{z\hspace{0pt}t}} + \eta_{z\hspace{0pt}t}}.
\end{aligned}\tag{6}
$$

The implied electricity-price elasticity is $\varepsilon_{p}(P_{zt},H_{t})=\beta_{p}+\beta_{ph}\log H_{t}$, and the implied hashprice elasticity is $\varepsilon_{h}(P_{zt},H_{t})=\beta_{h}+\beta_{ph}\log P_{zt}$. Our preferred reduced-translog specification is estimated on the matched sample described above.

In estimation, the logged price variables are centered at \$75/MWh for wholesale electricity prices and \$0.15/TH/s/day for hashprice:

$$
\begin{aligned}
\widetilde{\log P}_{zt}=\log(P_{zt})-\log(75),\qquad\widetilde{\log H}_{t}=\log(H_{t})-\log(0.15).
\end{aligned}\tag{7}
$$

To keep the notation compact, equation ([5](https://arxiv.org/html/2606.00587v2#S6.E5)) writes these centered variables as $\log P_{zt}$ and $\log H_{t}$. With this centering, the lower-order coefficients $\beta_{p}$ and $\beta_{h}$ are interpreted as the electricity-price and hashprice elasticities, respectively, at \$75/MWh and \$0.15/TH/s/day.

### Near-peak risk specification

We restrict this analysis to SDT hours and construct a near-peak risk index, denoted NP-risk, using realized ERCOT-wide system load. The index proxies for the expected opportunity cost created by coincident-peak charges. We normalize system demand within each year–month because coincident peaks are determined separately for each summer month. Let $t$ denote an SDT hour in summer month $m$ and year $y$, and let $\mathcal{T}^{\text{SDT}}_{ym}$ denote the set of SDT hours in the same year–month. We define

$$
\begin{aligned}
\text{NP-risk}_{t}=\frac{\text{Demand}_{ymt}-\min_{t^{\prime}\in\mathcal{T}^{\text{SDT}}_{ym}}\text{Demand}_{ymt^{\prime}}}{\max_{t^{\prime}\in\mathcal{T}^{\text{SDT}}_{ym}}\text{Demand}_{ymt^{\prime}}-\min_{t^{\prime}\in\mathcal{T}^{\text{SDT}}_{ym}}\text{Demand}_{ymt^{\prime}}}.
\end{aligned}\tag{8}
$$

This transformation maps realized ERCOT-wide system load into the unit interval within each year–month, with larger values indicating hours closer to the monthly peak.

Within SDT hours, we estimate

$$
\begin{aligned}
\displaystyle\log(\text{Mining Load}_{zt})={} & \displaystyle\alpha_{z}+\gamma_{t} \\
{+ {\beta_{R}\hspace{0pt}\text{NP-risk}_{t}}} + {\beta_{R\hspace{0pt}H}\hspace{0pt}\text{NP-risk}_{t}\hspace{0pt}{\log H_{t}}} \\
{+ {\beta_{P}\hspace{0pt}{\log P_{z\hspace{0pt}t}}}} + {\beta_{P\hspace{0pt}H}\hspace{0pt}{\log {P_{z\hspace{0pt}t}\hspace{0pt}\log }}\hspace{0pt}H_{t}} \\
{{+ {\beta_{H}\hspace{0pt}{\log H_{t}}}} + {\theta^{\top}\hspace{0pt}X_{z\hspace{0pt}t}} + \nu_{z\hspace{0pt}t}},
\end{aligned}\tag{9}
$$

where $\alpha_{z}$ are load-zone fixed effects and $\gamma_{t}$ includes fixed effects for hour of day, day of week, and month-by-year. The control vector $X_{zt}$ includes $\log(\text{growth}_{zt})$, 9-hour-lagged temperature, and lagged temperature squared. Standard errors are clustered by date. Month-by-year fixed effects absorb year-month-specific level shifts in summer operating conditions. This specification is motivated by Extended Data Figure [6](https://arxiv.org/html/2606.00587v2#S6.SSx6), which suggests that, after conditioning on the growth covariate, remaining differences across months and years primarily reflect level shifts.

We estimate the model using 2SLS. We treat the NP-risk block, $\{\text{NP-risk}_{t},\text{NP-risk}_{t}\log H_{t}\}$, the electricity-price block, $\{\log P_{zt},\log P_{zt}\log H_{t}\}$, and $\log H_{t}$ as endogenous. The excluded instruments are Houston cooling degree days, realized ERCOT-wide wind generation, logged Bitcoin price, and interaction instruments formed from these variables corresponding to the endogenous interaction terms. The identifying assumption is that, conditional on controls and fixed effects, these instruments affect mining load only through near-peak risk, wholesale electricity prices, hashprice, and their interactions. First-stage and endogeneity diagnostics are reported in Supplementary Tables 14–15.

Using the same outcome, controls, fixed effects, and excluded instrument set, we also estimate two restricted specifications: one excluding the NP-risk block and one excluding the electricity-price block. We report joint Wald tests for the corresponding coefficient blocks in the unrestricted specification.

### Alternative near-peak risk definition

As a robustness check, we construct an alternative near-peak risk index based on each day’s maximum ERCOT system load. This alternative measure varies across days rather than across hours and captures whether a given day is close to the monthly peak-demand day.

For day $d$ in month $m$ and year $y$, let $\text{PeakLoad}_{ymd}$ denote the maximum ERCOT system load on that day, and let $\mathcal{D}_{ym}$ denote all days in the same year–month. We define

$$
\begin{aligned}
\text{NP-risk}_{d}=\frac{\text{PeakLoad}_{ymd}-\min_{d^{\prime}\in\mathcal{D}_{ym}}\text{PeakLoad}_{ymd^{\prime}}}{\max_{d^{\prime}\in\mathcal{D}_{ym}}\text{PeakLoad}_{ymd^{\prime}}-\min_{d^{\prime}\in\mathcal{D}_{ym}}\text{PeakLoad}_{ymd^{\prime}}}.
\end{aligned}\tag{10}
$$

The resulting value is assigned to each SDT hour on day $d$, and the specification in equation ([9](https://arxiv.org/html/2606.00587v2#S6.E9)) is re-estimated using this alternative index.

![Figure 1](acquisition/source-members/extended_data/elec-price-hashprice.png)

Extended Data Figure 1. Growth-adjusted Bitcoin-mining load in relation to logged electricity prices and logged hashprice. (A) $\log(\text{Mining Load}/\text{growth})$ versus $\log(\text{Electricity Price})$, split by low- and high-hashprice observations. (B) $\log(\text{Mining Load}/\text{growth})$ versus $\log(\text{Hashprice})$, split by low- and high-electricity-price observations. Here, “growth” is the zone-specific installed-capacity proxy used in the empirical analysis. Points show zone-hour observations, and solid lines show group-specific linear fits. Low-load observations are more frequent at high electricity prices, especially when hashprice is low. Conversely, the relationship between hashprice and growth-adjusted mining load is steeper during high-electricity-price periods. These descriptive patterns are consistent with electricity-price responsiveness varying with hashprice. The broken y-axis preserves extreme low-load observations while keeping the main variation visible.

![Figure 2](acquisition/source-members/extended_data/np-risk-hashprice-ercot.png)

Extended Data Figure 2. Growth-adjusted Bitcoin-mining load in relation to logged hashprice and Texas system demand during summer daytime hours. (A) $\log(\text{Mining Load}/\text{growth})$ versus $\log(\text{Hashprice})$. (B) $\log(\text{Mining Load}/\text{growth})$ versus Texas system demand. Here, “growth” is the zone-specific installed-capacity proxy used in the empirical analysis. Points show zone-hour observations, with colors indicating summer months from June through September, and solid lines show month-specific linear fits. Growth-adjusted mining load tends to be higher when hashprice is higher and lower when Texas system demand is higher. The fitted relationships are broadly similar across summer months, suggesting that the descriptive patterns are not driven by a single month. The broken y-axis preserves extreme low-load observations while keeping the main variation visible.

#### Supplementary information

This manuscript has supplementary information in the accompanying PDF.

#### Acknowledgements

The author gratefully acknowledges thoughtful discussions with Bitcoin miners and ERCOT participants involved in the Blockchain and Energy Research Consortium at Texas A&M University. The author thanks Le Xie for facilitating access to the proprietary large flexible load power-consumption dataset. The author also thanks Ignacio Aravena and Le Xie for mentorship and funding support. The author used ChatGPT for code-generation assistance and writing support. The author takes full responsibility for the data analysis, and conclusions of this manuscript.

## Declarations

- Funding: This work was supported in part by the U.S. Department of Energy (DOE) through the OPEN COG Grid project and in part by the Blockchain and Energy Research Consortium at Texas A&M University.
- Conflict of interest/Competing interests: The author declares no competing interests.
- Ethics approval and consent to participate: Not applicable.
- Consent for publication: The author has consented to publication of this manuscript.
- Data availability: Publicly shareable input data are provided in the replication package deposited on Zenodo: [https://doi.org/10.5281/zenodo.20272757](https://doi.org/10.5281/zenodo.20272757). The restricted LFL data cannot be redistributed because they are the property of ERCOT and were accessed under a data-use agreement. These restricted data are merged with public data using timestamps and ERCOT load zone. Access to the restricted LFL data is subject to ERCOT approval.
- Materials availability: Not applicable.
- Code availability: The replication package deposited on Zenodo, [https://doi.org/10.5281/zenodo.20272757](https://doi.org/10.5281/zenodo.20272757), provides the code used to generate the figures and tables in the main text and supplementary materials, together with the generated outputs. Some scripts require the restricted ERCOT data and therefore cannot be fully executed using only the public replication package.
- Author contribution: S.M. conceived the research, developed the empirical framework and identification strategy, conducted the data analysis, and wrote the original draft.

## References (37 total, showing 37)

- Angrist and Pischke (2009) J. D. Angrist and J. Pischke Mostly harmless econometrics: An empiricist’s companion. Princeton University Press, Princeton, NJ.

- Aye et al. (2023) G. C. Aye, R. Demirer, R. Gupta, and J. Nel The pricing implications of cryptocurrency mining on global electricity markets: Evidence from quantile causality tests. Journal of Cleaner Production 397, pp. 136572.

- Baldick (2018) R. Baldick Incentive properties of coincident peak pricing. Journal of Regulatory Economics 54 (2), pp. 165–194.

- Bratcher (2024) L. Bratcher ERCOT data tells the story. Texas Blockchain Council. Note: [https://texasblockchaincouncil.org/blog/ercot-data-tells-the-story?](https://texasblockchaincouncil.org/blog/ercot-data-tells-the-story?). Accessed 6 November 2025

- Brunner et al. (2020) C. Brunner, G. Deac, S. Braun, and C. Zöphel The future need for flexibility and the impact of fluctuating renewable power generation. Renewable Energy 149, pp. 1314–1324.

- Burke and Abayasekara (2018) P. J. Burke and A. Abayasekara The price elasticity of electricity demand in the United States: A three-dimensional analysis. The Energy Journal 39 (2), pp. 123–146.

- Carmona et al. (2026) R. Carmona, X. Yang, and C. Zeng Coincident peak prediction for capacity and transmission charge reduction. Energy Systems, pp. 1–30.

- Christensen et al. (1973) L. R. Christensen, D. W. Jorgenson, and L. J. Lau Transcendental logarithmic production frontiers. The Review of Economics and Statistics, pp. 28–45.

- Colangelo et al. (2026) P. Colangelo, A. K. Coskun, J. Megrue, C. Roberts, S. Sengupta, V. Sivaram, E. Tiao, A. Vijaykar, C. Williams, D. C. Wilson, et al. AI data centres as grid-interactive assets. Nature Energy 11 (2), pp. 254–261.

- CPower Energy Management (2024) CPower Energy Management Case study: Blockfusion – powering down Bitcoin mining for grid stability. CPower Energy Management. Note: [https://cpowerenergy.com/wp-content/uploads/2024/06/CPower-Case-Study-Blockfusion.pdf](https://cpowerenergy.com/wp-content/uploads/2024/06/CPower-Case-Study-Blockfusion.pdf). Accessed 7 November 2025

- de Vries (2018) A. de Vries Bitcoin’s growing energy problem. Joule 2 (5), pp. 801–805.

- DeRoche and Elkin (2025) M. DeRoche and J. Elkin How much do we subsidize cryptocurrency mining’s electricity use? No one knows.. Note: [https://earthjustice.org/experts/mandy-deroche/how-much-do-we-subsidize-cryptocurrency-minings-electricity-use-no-one-knows](https://earthjustice.org/experts/mandy-deroche/how-much-do-we-subsidize-cryptocurrency-minings-electricity-use-no-one-knows). Accessed 7 November 2025

- DLA Piper (2023) DLA Piper The role of Bitcoin mining in renewables projects. Note: [https://www.dlapiper.com/en/insights/publications/2023/02/the-role-of-bitcoin-mining-in-renewables-projects](https://www.dlapiper.com/en/insights/publications/2023/02/the-role-of-bitcoin-mining-in-renewables-projects). Accessed 18 December 2025

- Electric Reliability Council of Texas (2025a) Electric Reliability Council of Texas ERCOT nodal protocols, Section 4, Day-ahead operations.. Technical report

- Electric Reliability Council of Texas (2025b) Electric Reliability Council of Texas Monthly outlook for resource adequacy (MORA). Technical report

- Gallant (2024) C. Gallant Emergency alert, city deals idle Hat’s Bitcoin mines. Note: [https://medicinehatnews.com/news/local-news/2024/01/16/emergency-alert-city-deals-idle-hats-bitcoin-mines/](https://medicinehatnews.com/news/local-news/2024/01/16/emergency-alert-city-deals-idle-hats-bitcoin-mines/). Accessed 7 November 2025

- Garratt and Hayes (2015) R. Garratt and R. Hayes Entry and exit leads to zero profit for Bitcoin miners. Note: Liberty Street Economics, Federal Reserve Bank of New York. [https://libertystreeteconomics.newyorkfed.org/2015/08/entry-and-exit-leads-to-zero-profit-for-bitcoin-miners/](https://libertystreeteconomics.newyorkfed.org/2015/08/entry-and-exit-leads-to-zero-profit-for-bitcoin-miners/). Accessed 26 February 2026

- Hajiaghapour-Moghimi et al. (2022) M. Hajiaghapour-Moghimi, K. Azimi Hosseini, E. Hajipour, and M. Vakilian An approach to targeting cryptocurrency mining loads for energy efficiency enhancement. IET Generation, Transmission & Distribution 16 (23), pp. 4775–4790.

- Hashrate Index (2025) Hashrate Index Bitcoin hashprice index – network data. Note: [https://data.hashrateindex.com/network-data/bitcoin-hashprice-index](https://data.hashrateindex.com/network-data/bitcoin-hashprice-index). Accessed 7 November 2025

- Hirth et al. (2024) L. Hirth, T. M. Khanna, and O. Ruhnau How aggregate electricity demand responds to hourly wholesale price fluctuations. Energy Economics 135, pp. 107652.

- Iacus et al. (2012) S. M. Iacus, G. King, and G. Porro Causal inference without balance checking: Coarsened exact matching. Political analysis 20 (1), pp. 1–24.

- International Energy Agency (2025) International Energy Agency The value of demand flexibility: Benefits beyond balancing. Technical report Paris.

- Labandeira et al. (2017) X. Labandeira, J. M. Labeaga, and X. López-Otero A meta-analysis on the price elasticity of energy demand. Energy Policy 102, pp. 549–568.

- Lijesen (2007) M. G. Lijesen The real-time price elasticity of electricity. Energy Economics 29 (2), pp. 249–258.

- Luxor Documentation Hub (2025) Luxor Documentation Hub Understanding Bitcoin hashprice: What it is, how it’s calculated, and the factors that impact it. Note: [https://docs.luxor.tech/hashrateindex/hashprice](https://docs.luxor.tech/hashrateindex/hashprice). Accessed 22 October 2025

- Martinot (2016) E. Martinot Grid integration of renewable energy: flexibility, innovation, and experience. Annual Review of Environment and Resources 41 (1), pp. 223–251.

- Menati et al. (2023) A. Menati, Y. Cai, R. E. Helou, C. Tian, and L. Xie Optimization of cryptocurrency miners’ participation in ancillary service markets. arXiv preprint arXiv:2303.07276.

- Neumueller et al. (2025) A. Neumueller, G. C. Pieters, K. Mohaddes, V. Rousseau, and B. Z. Zhang Cambridge digital mining industry report: Global operations, sentiment, and energy use. Technical report Technical Report 2025-04, Cambridge Centre for Alternative Finance, Cambridge Judge Business School, University of Cambridge.

- North American Electric Reliability Corporation (2025) North American Electric Reliability Corporation Characteristics and risks of emerging large loads: Large loads task force white paper. Technical report

- Public Utility Commission of Texas (1999) Public Utility Commission of Texas Order adopting amendments to transmission service rates and recovery of fuel costs. Technical report Note: Poject No. 23014, Rulemaking and proceeding to determine the final fuel reconciliation schedule as directed in PURA 39.202(c).

- Public Utility Commission of Texas (2024) Public Utility Commission of Texas PUCT approves rule requiring registration of virtual currency mining facilities. Public Utility Commission of Texas. Note: [https://ftp.puc.texas.gov/public/puct-info/agency/resources/pubs/news/2024/PUCT\_Approves\_Rule\_Requiring\_Registration\_of\_Virtual\_Currency\_Mining\_Facilities.pdf](https://ftp.puc.texas.gov/public/puct-info/agency/resources/pubs/news/2024/PUCT_Approves_Rule_Requiring_Registration_of_Virtual_Currency_Mining_Facilities.pdf). Accessed 21 October 2025

- Renewable Energy World (2024) Renewable Energy World Black Hills Energy launches innovative tariff for Bitcoin miners, announces undergrounding. Note: [https://www.renewableenergyworld.com/power-grid/grid-modernization/black-hills-energy-launches-innovative-tariff-for-bitcoin-miners-announces-undergrounding/](https://www.renewableenergyworld.com/power-grid/grid-modernization/black-hills-energy-launches-innovative-tariff-for-bitcoin-miners-announces-undergrounding/). Accessed 7 November 2025

- Roth et al. (2023) J. Roth, P. H. Sant’Anna, A. Bilinski, and J. Poe What’s trending in difference-in-differences? A synthesis of the recent econometrics literature. Journal of Econometrics 235 (2), pp. 2218–2244.

- Ruhnau (2022) O. Ruhnau How flexible electricity demand stabilizes wind and solar market values: The case of hydrogen electrolyzers. Applied Energy 307, pp. 118194.

- Sapra et al. (2024) N. Sapra, I. Shaikh, D. Roubaud, M. Asadi, and O. Grebinevych Uncovering Bitcoin’s electricity consumption relationships with volatility and price: Environmental repercussions. Journal of Environmental Management 356, pp. 120528.

- Suna et al. (2022) D. Suna, G. Totschnig, F. Schöniger, G. Resch, J. Spreitzhofer, and T. Esterl Assessment of flexibility needs and options for a 100% renewable electricity system by 2030 in Austria. Smart Energy 6, pp. 100077.

- Zhu et al. (2018) X. Zhu, L. Li, K. Zhou, X. Zhang, and S. Yang A meta-analysis on the price elasticity and income elasticity of residential electricity demand. Journal of Cleaner Production 201, pp. 169–177.
