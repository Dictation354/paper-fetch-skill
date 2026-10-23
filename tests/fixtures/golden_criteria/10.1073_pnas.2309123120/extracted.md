---
title: "Amazon deforestation causes strong regional warming"
authors: "Edward W. Butt, Jessica C. A. Baker, Francisco G. Silva Bezerra, Celso von Randow, Ana P. D. Aguiar, Dominick V. Spracklen"
doi: "10.1073/pnas.2309123120"
source: "pnas"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 11681
---

# Amazon deforestation causes strong regional warming

## Significance

Tropical deforestation warms the climate with negative impacts on people living nearby. Most previous studies have focused on the local warming caused by deforestation and less is known about how deforestation impacts surrounding areas. Our study used satellite data to show that deforestation in the Amazon caused substantial warming up to 100 km away from the location of forest loss. We show that this nonlocal warming increased deforestation-induced warming by a factor of four. We estimate that reducing deforestation in the Brazilian Amazon could reduce future warming in the southern Amazon by 0.56 °C. These findings highlight the role of deforestation in regional climate change and emphasize the importance of reducing deforestation for climate adaptation and resilience in the Amazon.

## Abstract

Tropical deforestation impacts the climate through complex land–atmosphere interactions causing local and regional warming. However, whilst the impacts of deforestation on local temperature are well understood, the regional (nonlocal) response is poorly quantified. Here, we used remote-sensed observations of forest loss and dry season land–surface temperature during the period 2001 to 2020 to demonstrate that deforestation of the Amazon caused strong warming at distances up to 100 km away from the forest loss. We apply a machine learning approach to show nonlocal warming due to forest loss at 2–100 km length scales increases the warming due to deforestation by more than a factor 4, from 0.16 K to 0.71 K for each 10-percentage points of forest loss. We estimate that rapid future deforestation under a strong inequality scenario could cause dry season warming of 0.96 K across Mato Grosso state in southern Brazil over the period 2020 to 2050. Reducing deforestation could reduce future warming caused by forest loss to 0.4 K. Our results demonstrate the contribution of tropical deforestation to regional climate warming and the potential for reduced deforestation to deliver regional climate adaptation and resilience with important implications for sustainable management of the Amazon.

## Main Text

Biophysical effects of forests can strongly impact properties of the land surface through changes in land–atmosphere fluxes of heat, moisture, and momentum ([1](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r1)–[3](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r3)). Forest landscapes typically exhibit higher leaf area index, deeper roots, lower albedo, greater evapotranspiration, and aerodynamic surface roughness compared to nonforest landscapes ([1](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r1)).

Changes to these biophysical effects as a result of deforestation cause changes in climate at the location of land cover change, known as local effects ([4](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r4)). Deforestation has contrasting local effects, with increased albedo acting to cool the surface whilst reduced surface roughness and evapotranspiration, acting to warm the surface ([5](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r5)). Numerous studies have shown that the combined impact of these contrasting effects is local warming with tropical deforestation increasing local daytime surface temperature by 1–2 °C or more ([6](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r6)–[14](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r14)). Deforested areas in the Amazon were found to have warmed by as much as 3 °C locally, with the largest warming during the dry season ([15](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r15), [16](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r16)). The local warming impacts of deforestation are well recognized by people living within tropical forest landscapes ([17](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r17)).

Deforestation can also impact the climate of nearby areas that are 10 s or 100 s of km from the location of land-use change ([3](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r3)). Much less is known about these nonlocal climate impacts of deforestation, which are more challenging to assess ([18](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r18)). Nonlocal impacts which occur via advection, circulation changes, and atmospheric feedbacks depend on the geographical distribution and spatial extent of surrounding deforestation, meaning that these effects are much more difficult to identify or interpret. Indeed, many observational assessments of the local impacts of land-use change use a “space-for-time” approach that compares the climate over forest and neighboring nonforest that excludes nonlocal effects or assumes that they are negligible ([4](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r4), [19](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r19)). In contrast, some observational studies suggest that nonlocal effects could be substantial. Large (&gt;1,000 km<sup>2</sup>) deforested patches are known to warm more than smaller patches of deforestation ([20](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r20)). Cohn et al. ([21](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r21)) found significant and substantial nonlocal warming at undisturbed locations in Brazil’s Amazon and Cerrado biomes at distances up to 50 km away from forest loss. In maritime Southeast Asia, deforestation has been shown to result in warming up to 6 km away from the location of deforestation ([22](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r22)). Climate models have been used to separate the local and nonlocal effects of deforestation suggesting that the nonlocal effects of deforestation on surface temperature are similar in magnitude to the local effects ([4](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r4)). These studies have highlighted a potentially important, but poorly quantified, impact of deforestation on regional temperatures. A much better quantification and understanding of these regional responses is needed to inform sustainable management of tropical landscapes.

In this study, we examined both local and nonlocal effects due to forest loss across the Amazon biome where deforestation is dramatically changing the landscape ([23](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r23)). Large-scale deforestation started in the 1970 s, ([24](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r24)) and about 17% of the Amazon had been deforested by 2021, with rates of deforestation accelerating in the past few years ([25](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r25), [26](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r26)). A business-as-usual scenario of continued deforestation of the Amazon has estimated that up to 40% of the basin could be deforested by 2050 ([27](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r27)). Given the extent of land cover change across the Amazon, both local and nonlocal temperature responses to forest loss may represent an important mechanism for shaping local and regional climates.

We combined a number of remote-sensed datasets to quantify and predict changes in dry season surface temperature due to forest cover loss across the Amazon at varying length-scales. A previous study ([21](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r21)) assessed how warming in undisturbed areas of Amazon forest was impacted by the amount of nonlocal forest loss. Our study focuses on areas experiencing forest loss and aims to understand how temperature changes at the local scale depend on the extent of both local and nonlocal forest loss. We calculated the change in remotely sensed observations of land surface temperature at *n* = ~3.7 million locations (each 1 km<sup>2</sup> in extent) across the Amazon between 2001 and 2020. Using remotely sensed observations of forest fraction over the same period, we explored how warming from forest loss depended on the extent of both local and nonlocal forest loss. We then used a machine learning approach to further isolate the local and nonlocal effects of forest loss. Finally, we use this model to make the first prediction of how the temperature response depends on local and nonlocal forest loss across the Amazon.

## Results and Discussion

### Forest Loss and Surface Temperature Change

[Fig. 1](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig01) shows Amazon forest loss and corresponding dry season (defined as driest 3 mo per pixel) land surface temperature change (Δ<em>T</em>) over 2001 to 2020. Forest loss and Δ<em>T</em> show similar spatial patterns, with stronger warming over regions of forest loss particularly across the “arc of deforestation” along the southern Amazon. Warming exceeds 5 K over regions of extensive forest loss, with stronger warming over regions with more extensive forest loss ([Fig. 1<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig01)). Across the whole Amazon basin (*n* = 3.7 million), median and mean Δ<em>T</em> were 0.48 and 0.6 K, respectively ([Fig. 1<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig01)). Across the Brazilian Amazon biome, observed median and mean Δ<em>T</em> were greater at 0.58 and 0.78 K, respectively ([Fig. 1<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig01)).

![Figure 1](https://www.pnas.org/cms/10.1073/pnas.2309123120/asset/3f537f5c-31b7-4e4a-85d1-a94ad1f40b73/assets/images/large/pnas.2309123120fig01.jpg)

**Figure 1.** Forest loss and surface temperature change during 2001 to 2020. (*A*) Percentage point loss (%) in forest fraction. (*B*) Change in surface temperature (Δ<em>T</em>, Kelvin) of the driest month. Change in forest fraction and Δ<em>T</em> over 2001 to 2020 is calculated as the difference between the mean of the first 3-y and the last 3-y of the study period (i.e., 2001–2003 versus 2018–2020). Data are shown for the Amazon basin with the boundary of the Brazilian Amazon biome also shown.

### Observed Δ<em>T</em> as a Function of Forest Loss at Local and Regional Scales

[Fig. 2](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig02) shows observed Δ<em>T</em> for varying amounts of local and regional forest loss. In locations with little or no forest loss (<10 percentage points forest loss), median Δ<em>T</em> is 0.3 K, which we consider a background rate. Locations with 10–20% local forest loss but little regional forest loss (i.e., <10 percentage points forest loss at regional scales from 2 to 100 km), experience median warming of 0.6 K, or double the background rate. Locations with 40–50% local forest but little regional forest loss experience a median warming of 1.3 K, more than quadruple the background rate. Warming over locations with both local and regional forest loss is even greater. Locations with 10–20% local forest loss and 10–20% regional forest loss at scales of 2–10 km experience a warming of 0.9 K, triple the background rate. When both local and regional forest loss is 40–50%, median warming is 6 times the background rate (1.9 K). When the regional scale of forest loss extends to 100 km, warming is 3.5 times (1.1 K) to 14 times (4.4 K) greater for 10–20% and 40–50% forest loss, respectively. Warming exceeding 4 K that is observed over regions with strong local and regional forest loss is at the upper end of that reported in previous studies of tropical deforestation ([5](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r5)–[13](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r13)). Dry-season warming of 3 K has been reported for regions of large-scale deforestation in the southern Amazon ([16](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r16)). Together this suggests that large-scale forest loss leads to substantially greater warming.

![Figure 2](https://www.pnas.org/cms/10.1073/pnas.2309123120/asset/ef690f17-c6e1-4430-aa30-0b160a958b5a/assets/images/large/pnas.2309123120fig02.jpg)

**Figure 2.** Change in observed dry season surface temperature (Δ<em>T</em>, Kelvin) as a function of forest loss at different length scales. Δ<em>T</em> is shown from left to right: Local (0–2 km) forest loss only (i.e., less <10% forest loss at regional scales from 2 to 100 km), local plus regional forest loss at 2–10 km (i.e., less <10% forest loss at regional scales from 10 to 100 km), and local plus regional forest loss at 2–100 km. Labeled central values are the median of the distribution. Figure is restricted to displaying forest loss <50%.

### Machine Learning Prediction

To understand the relative roles of local and regional forest loss on Δ<em>T</em>, we developed a range of machine learning models including different aspects of local and regional forest loss. We employed the XGBoost algorithm, suitable for tabular data, using hyperparameters selected via cross-validation. Our dataset of ~3.7 million records was split into 95% training and 5% testing datasets. Models were trained and tested, including simulations with varying degrees of forest loss at different length scales. We also included a range of factors that are known to influence the temperature response to forest loss, including latitude ([9](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r9)), elevation ([28](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r28)), and distance to coast ([29](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r29)). [Fig. 3](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03) shows our machine learning prediction of Δ<em>T</em> using different local and regional forest loss features (*Methods*). Predictions of Δ<em>T</em> are poor when no information on forest loss is included in the model training (*MAE* = 0.52, *RMSE* = 0.78, *r*<sup>2</sup> = 0.07) ([Fig. 3 *A*–*C*](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03)). Including information on local (0–2 km) forest loss improves the model, albeit with substantial scatter in predictions (*MAE* = 0.47, *RMSE* = 0.68, *r*<sup>2</sup> = 0.43). Including information on regional forest loss substantially improves the model with a consistent improvement to the model performance when information on regional forest loss at scales of 2–100 km is included ([Fig. 3 *A*–*C*](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03), solid blue line). The best prediction is found when the model includes information on forest loss out to the 100-km scale (Base model: *MAE* = 0.31, *RMSE* = 0.45, *r*<sup>2</sup> = 0.81), resulting in a model that is substantially better than the model based on local forest loss only. Adding features can artificially improve the model performance. To ensure that this was not influencing our analysis, we show that incrementally adding dummy forest fraction halos populated with random forest loss data did not improve model prediction ([Fig. 3 *A*–*C*](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03), dashed blue line). These results demonstrate that accounting for regional forest loss greatly improves Δ<em>T</em> prediction. Overall, our modeling results show that good Δ<em>T</em> prediction is only achieved when both local and regional (non-local) forest loss at length scales up to 100 km are accounted for in model training. Our results suggest that nonlocal neighboring forest cover loss is significantly contributing to observed temperature responses across the Amazon.

![Figure 3](https://www.pnas.org/cms/10.1073/pnas.2309123120/asset/8acfbd4c-bcbe-4421-87d4-f32d95e8a85e/assets/images/large/pnas.2309123120fig03.jpg)

**Figure 3.** Prediction of surface temperature change due to forest loss. (*A*) Mean absolute error, (*B*) RMSE, (*C*) coefficient of determination. Model prediction metrics on the test dataset (*n* = 184,582). Simulations include no information on forest fraction loss (Non-FF), local forest loss (Δ0–2 km) only, local forest loss and information of regional forest loss at scales of 2 to 100 km added to the model incrementally (solid blue line). The blue dashed line represents adding dummy halo features incrementally populated with random values between 0 and 1. (*D*) Model prediction of Δ<em>T</em> with local and all regional forest loss features (2–100 km) included compared to observations from the test dataset.

#### Δ<em>T</em> Prediction as a Function of Forest Loss at Local and Regional Scales

[Fig. 4](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04) shows predicted Δ<em>T</em> as a function of local and nonlocal forest loss. Warming over regions with only local forest loss increases from <0.2 K over regions with less than 5% local forest loss to 0.7 K when local forest loss reaches 40% ([Fig. 4<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04)). In regions with both local and regional (2–10 km) forest loss, warming increases to 1.6 K when forest loss reaches 40%. When the regional extent of forest loss extends further to 100 km, warming in areas of 40% forest loss increases to 2.8 K ([Fig. 4<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04)). For each 10-percentage points of forest loss, warming increases by an average of 0.16 K for local forest loss only, to 0.4 K for local and regional (2–10 km) forest loss, and to 0.71 K for local and regional (2–100 km) forest loss. Our results therefore show that regional forest loss at scales up to 100 km increases the warming due deforestation by more than a factor of 4. Our modeling results provide further evidence that both local and nonlocal forest losses are contributing to the climate responses observed across the Amazon biome. Importantly, our results show that previous estimates may underestimate the warming from tropical forest loss ([6](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r6)–[10](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r10), [15](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r15)) as they do not fully account for the contribution from regional forest loss ([Fig. 4<em>B</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04)). Many of these studies apply a nearest neighbor or difference-in-difference approach to separate temperature changes from climate change to those from deforestation. However, such approaches may remove the regional climate signal from the analysis, implicitly assuming that it is a signal of climate variability or change rather than a regional response to deforestation as we show here. Our analysis focused on the dry season. Tropical deforestation leads to local warming across all seasons ([6](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r6), [16](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r16)) and future work is needed to assess the nonlocal climate impacts of Amazon deforestation outside of the dry season.

![Figure 4](https://www.pnas.org/cms/10.1073/pnas.2309123120/asset/36542f4c-2e9d-4e05-823d-7d9793ab2b52/assets/images/large/pnas.2309123120fig04.jpg)

**Figure 4.** Model simulated surface temperature change (Δ<em>T</em>) due to forest loss. (*A*) Model predicted Δ<em>T</em> from 693 simulations covering the full range of local and regional forest loss. Median predicted values are calculated using dataset average values for latitude, elevation, and distance to coast. (*B*) Model predicted Δ<em>T</em> as a function of increasing local only (blue) and local plus regional (orange and red) forest loss. Observed Δ<em>T</em> as a function of increasing tropical forest loss are from three different observational studies ([6](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r6), [15](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r15), [30](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r30)). (*C*) Observed (2000 to 2020) and model predicted (2020 to 2050) Δ<em>T</em> for the Brazilian Amazon biome. Predicted Δ<em>T</em> for future land cover change under a middle-of-the-road scenario (SSP2\_RCP45) and a strong Inequality scenario (SSP1\_RCP70). Median Δ<em>T</em> values are provided on each boxplot. (*D*) Observed (2000 to 2020) and model predicted (2020 to 2050) Δ<em>T</em> for two Brazilian states located in the southern Brazilian Amazon biome: Rondônia (blue polygon) and Mato Grosso (red polygon).

#### Warming Associated with Future Deforestation

The future trajectory of deforestation in the Amazon depends on a wide range of local, national and global factors. We combined our model with two land cover change scenarios for Brazil to explore the impact of these different trajectories on regional climate. Both scenarios are aligned with the Shared Socioeconomic Pathways (SSPs) and Representative Concentration Pathway (RCPs) refined with regionally specific information ([31](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r31)). The first scenario represents a Strong Inequality scenario (SSP3\_RCP7) where the Brazilian Forest Code is not respected, protected areas are not safeguarded, and there is continued expansion of paved roads which together result in rapid continued deforestation. The second scenario represents a middle-of-the-road scenario with respect for the Forest Code, some additional safeguarding for protected areas and measures to reduce negative impacts of road expansion. Widespread forest loss is predicted in both scenarios with 762,739 km<sup>2</sup> of forest loss in the strong inequality scenario and with 673,066 km<sup>2</sup> of forest loss in the middle-of-the-road scenario ([*SI Appendix*, Figs. S1 and S2](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). Across the Brazilian Amazon biome, we estimate this forest loss will cause a median (mean) surface warming of between 0.62 K (0.63 K) under the middle-of-the-road scenario and 0.73 K (0.79 K) under the strong inequality scenario ([Fig. 4<em>C</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04)). In the southern Amazon, rapid forest loss over the period 2000–2020 resulted in strong warming ([Fig. 1<em>D</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig01)). Stronger future warming is also simulated across the southern Amazon where projected forest loss is greatest ([*SI Appendix*, Figs. S1<em>D</em> and S2<em>D</em>](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). In Rondônia, predicted median (mean) surface warming increases from 0.59 K (0.75 K) under the middle-of-the-road scenario to 0.82 K (0.95 K) under the strong inequality scenario. In Mato Grosso, predicted warming increases from 0.4 K (0.56 K) under the middle-of-the-road scenario to 0.96 K (1 K) under the strong inequality scenario ([Fig. 4<em>D</em>](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig04)). This reduced warming in the southern Amazon in the middle-of-the-road scenario is due to lower deforestation rates in this region, which are up for factor of two slower compared to the strong inequality scenario. Our analysis isolates warming due to forest loss and does not include changes due to global warming. Potential positive feedbacks and tipping points in the system ([32](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r32)) will not be captured in our approach so future warming may be stronger than estimated here. Our analysis is restricted to the impacts of deforestation in the Amazon. Further work is needed to explore the nonlocal climate impacts of deforestation in other tropical forest regions.

##### Implications

The regional warming due to Amazon deforestation will have negative consequences for the 30 million people living within the Amazon basin, many of whom are already exposed to dangerous levels of heat ([33](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r33)). Previous studies have suggested that the combined impacts of future climate change and deforestation could expose an additional 11 million people across the Amazon to extreme heat stress ([34](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r34)). Increased temperatures will reduce human productivity ([35](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r35)) and increase all-cause human mortality ([36](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r36)) for already marginalized communities. Increased temperatures will also impact livestock and reduce crop yields ([37](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r37)), exacerbated by deforestation-induced reductions in rainfall ([38](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r38), [39](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r39)). Increased regional temperatures caused by deforestation will also impact carbon storage of remaining forest ([40](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r40)–[42](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r42)) and increase the risk of fire, with the resultant haze having further consequences for human health ([43](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r43)).

In 2020, Amazon deforestation was at the highest rate in the last decade ([44](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r44)) with consequent loss of biodiversity and substantial carbon emissions ([45](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r45)). Our analysis shows that controlling future deforestation in the Amazon would reduce future warming particularly for the southern states of Rondônia and Mato Grosso, with important social and economic benefits across the region. Forest degradation, where forests have been selectively logged or experienced fire, impacts large areas of the Amazon ([46](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r46)) contributing substantially to carbon emissions ([47](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r47), [48](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r48)). Evapotranspiration in degraded forests can be up to 34% lower compared to intact forests ([49](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r49)) with likely consequences for regional climate. Recovery of secondary and degraded forests can act as a carbon sink ([50](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r50)) and may offer additional local and regional cooling through biophysical effects. Future work is needed to analyze the regional climate impacts of forest degradation and regrowth of secondary and degraded forests ([51](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r51)). Identifying options for sustainable development of the Amazon without major future deforestation or degradation is crucial ([52](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r52)) to supporting climate adaptation and resilience of the region.

Our analysis does not provide information on the mechanisms for regional warming. Tropical deforestation leads to local warming due to reductions in the turbulent energy flux caused by reduced evapotranspiration and reduced surface roughness outweighing the cooling effects of increased surface albedo ([12](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r12)). These local climate changes will generate thermal, moisture, and surface pressure gradients that will alter the lateral movement of heat and moisture ([3](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r3)). Changes in circulation driven by deforestation will transport warmer air from surrounding regions of deforestation ([53](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r53), [54](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r54)) and may alter cloud cover ([55](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r55)) with further impacts on temperature. In a similar way, the urban heat island effect has shown to extend into surrounding rural areas ([56](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r56), [57](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r57)). Climate model simulations confirm that tropical deforestation leads to local warming ([2](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r2), [13](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r13)), although models disagree as to the relative contribution of changes in evapotranspiration, turbulent heat fluxes, and albedo to the surface temperature change ([58](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r58), [59](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r59)). Climate model studies separating local and nonlocal effects of deforestation show that nonlocal effects become comparable to local effects only under extensive land cover change ([4](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r4)), as is now the case in the southern Amazon. However, coarse resolution global climate models simulations ([58](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r58)) with resolutions of 0.7°–2.8°, equivalent to 70–280 km in the tropics, are unable to separate the local and nonlocal responses of deforestation that occur at the 10 to 100 km scale. Higher-resolution simulations show how Amazon deforestation can initiate mesoscale circulations ([54](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r54)) contributing to nonlocal effects. Convection-permitting regional climate models simulating the impacts of deforestation at a resolution of 4 km are now available ([60](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r60), [61](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r61)) providing new opportunities to understand the key processes driving the observed temperature response at these scales.

Our work quantifies the nonlocal (regional) impacts of deforestation on land surface temperature across the Amazon. We show that regional forest loss increases warming by more than a factor of 4 with serious consequences for the remaining Amazon forest and the people living there. We estimate that efforts to reduce deforestation could reduce the future warming experienced over the southern Amazon by 0.56 K over the next 30 y. Such findings demonstrate the contribution of tropical deforestation to regional climate warming and the urgent need for reduced deforestation and forest conservation to deliver regional climate resilience with important implications for sustainable management of the Amazon.

## Methods

### Land Cover Classification Data

Land cover data from the MapBiomas project ([62](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r62)) was used, which provides annual land cover classification at 30-m resolution for the period 1985 to 2020. We used data for the year 2020.

### Rainfall Data

We used precipitation data from Climate Hazards Group InfraRed Precipitation with Stations (CHIRPS) version 2.0 ([63](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r63)). The CHIRPS dataset is a blended rainfall product combining 5-y precipitation climatology, satellite observations, model simulations, and in situ observations from gage stations. Quasiglobal gridded products are available from 1981 to near-present at 0.05° spatial resolution (approx. 5 km at the equator) ([63](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r63)). We used monthly data spanning the period 1 January 2001 to 31 December 2020.

### Elevation Data

We used elevation data taken from Global Multi-resolution Terrain Elevation Data (GMTED2010) ([64](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r64)) at 7.5-arc-second spatial resolution.

### Distance to Coast Data

We used data on distance to the nearest coast from [https://oceancolor.gsfc.nasa.gov/resources/docs/distfromcoast/](https://oceancolor.gsfc.nasa.gov/resources/docs/distfromcoast/).

### Land Surface Temperature Data

We used land surface temperature (LST) data from MOD11A2 version 6 MODIS 8-d LST data at 0.01-degree resolution grid downloaded from [https://www.earthdata.nasa.gov/](https://www.earthdata.nasa.gov/) (variable name: LST\_Day\_1km). Following Li et al. ([9](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r9)), we excluded data where the estimated emissivity error was greater than 0.02 and where the LST error was greater than 1 K. Extensive cloud cover can reduce the spatial and temporal availability of satellite data. For this reason, we focus our analysis on the dry season when there is less cloud cover. To obtain monthly data, we aggregated by month ignoring any 8-day period where data were missing due to clouds or as a result of the quality screening process. Although Terra’s 10:30 AM local overpass time usually senses a cooler surface than Aqua with its 1:30 PM overpass, we opted to use Terra for its longer sampling period and due to lower cloud cover in the morning.

For each pixel, we analyzed LST data for the driest month identified using CHIPRS monthly rainfall data ([*SI Appendix*, Fig. S3](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). Dry season surface temperature change (Δ<em>T</em>) was then calculated by subtracting the average surface temperature of the driest month for two periods at the end (2018 to 2020) and start (2001 to 2003) of the study period. Using 3-y averages reduces the influences of climate variability. As a final preprocessing step, we used land cover classifications in the year 2020 to remove data points that contained ≥5% fraction of water, urban, flooded forest, and wetlands in both start and end periods. In addition, we excluded pixels at elevations above 500 m to avoid significant effects of elevation on Δ<em>T</em>. Our final Δ<em>T</em> dataset comprised *n* = ~3.7 million pixels (1 km<sup>2</sup> in extent) over the Amazon biome region.

### Forest Fraction Data

Forest fraction data were taken from Global Forest Change (Source: Hansen/UMD/Google/USGS/NASA) ([23](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r23)) V1.8. Annual forest fraction for the period 2000 to 2020 was calculated by taking tree cover in the year 2000, defined as canopy closure for all vegetation taller than 5 m in height encoded as a percentage per output grid cell units ranging 0–100 and subjecting it to annual forest loss, defined as a disturbance from a forest to nonforest state. Forest loss from this product has user’s and producer’s accuracies of greater than 80%. Our analysis does not fully represent forest degradation or secondary forest regrowth. Average forest fraction change was calculated as the difference between average forest fraction for two periods at the start (2001 to 2003) and end of the study period (2018 to 2020). We calculated both local and nonlocal regional forest cover change at different length scales of Δ<em>T</em> locations. Local forest cover change included forest loss at distances of 0–2 km, while regional forest cover change was calculated in “halos” located 2–5 km, 5–10 km, 10–25 km, 25–50 km, and 50–100 km of Δ<em>T</em> locations ([*SI Appendix*, Fig. S4](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). Halo analysis was conducted in Python version 3.9.7 using the Geopandas package version 0.10.2.

Large forest losses occur not only at local scales (0–2 km), but also at nonlocal regional length scales 2–10 km and 10–100 km from of Δ<em>T</em> locations. We find a 2-percentage point change in median forest cover between start (99%) and end (97%) forest fraction period at local scales (0–2 km) of Δ<em>T</em> locations ([*SI Appendix*, Fig. S5](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). For nonlocal regional distances 2–10 km of Δ<em>T</em> locations, we find a 5-percentage point change in median forest cover between start (96.5%) and end (91.5%) periods, while we find a 7-percentage point change at regional distances 10–100 km of Δ<em>T</em> locations between start (92%) and end (85%) periods ([*SI Appendix*, Fig. S5](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)).

### Supervised Machine Learning

We used a supervised machine learning (ML) model to predict Δ<em>T</em>. All data was regridded to 0.01° resolution. [Table 1](https://www.pnas.org/doi/10.1073/pnas.2309123120#t01) provides details of the features used in the model including ΔT, local and regional forest cover at the start and end of the analysis period, latitude, elevation above sea level, and distance to the nearest coast. We used a gradient-boosting decision tree algorithm (XGBoost) ([65](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r65)) as our model of choice, well suited to the regression problem with tabular data. Briefly, the XGBoost algorithm adds decision tree models to an ensemble that are fit to correct errors made by prior decision tree models. Models are fit using a loss function and gradient descent optimization algorithm whereby the loss gradient is minimized as the model is fitted to training data (gradient boosting). The algorithm is computationally efficient and highly effective, as well as being found to dominate regression problems using tabular datasets on the Kaggle competitive data science platform ([65](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r65)).

**Table 1.** Description of model features

| Feature name               | Distance  | Description                                                                                                                                                                                                      | Units                                            |
| -------------------------- | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Δ<em>T</em>                | 0 km      | Target feature: Surface temperature change calculated by subtracting the average surface temperature of the driest month for two periods at the end (2018 to 2020) and start (2001 to 2003) of the study period. | Kelvin (K)                                       |
| Latitude                   | 0 km      | Model feature: Latitude at Δ<em>T</em> locations.                                                                                                                                                                | Degrees: rescaled (0 to 1)                       |
| Elevation                  | 0 km      | Model feature: Elevation at Δ<em>T</em> locations.                                                                                                                                                               | Meters (m): rescaled (0 to 1)                    |
| Distance to coast          | 0 km      | Model feature: Distance to the nearest coastline from Δ<em>T</em> locations.                                                                                                                                     | Kilometers (km): rescaled (0 to 1)               |
| Local\_0–2km\_change       | 0–2 km    | Model feature: Average forest fraction change in halo 0–2 km of Δ<em>T</em> locations.                                                                                                                           | Percentage point forest fraction loss (0 to 100) |
| Regional\_2–5km\_change    | 2–5 km    | Model feature: Average forest fraction change in halo 2–5 km of Δ<em>T</em> locations.                                                                                                                           | Percentage point forest fraction loss (0 to 100) |
| Regional\_5–10km\_change   | 5–10 km   | Model feature: Average forest fraction change in halo 5–10 km of Δ<em>T</em> locations.                                                                                                                          | Percentage point forest fraction loss (0 to 100) |
| Regional\_10–25km\_change  | 10–25 km  | Model feature: Average forest fraction change in halo 10–25 km of Δ<em>T</em> locations.                                                                                                                         | Percentage point forest fraction loss (0 to 100) |
| Regional\_25–50km\_change  | 25–50 km  | Model feature: Average forest fraction change in halo 25–50 km of Δ<em>T</em> locations.                                                                                                                         | Percentage point forest fraction loss (0 to 100) |
| Regional\_50–100km\_change | 50–100 km | Model feature: Average forest fraction change in halo 50–100 km of Δ<em>T</em> locations.                                                                                                                        | Percentage point forest fraction loss (0 to 100) |

XGBoost hyperparameters were selected based on a fivefold cross validation grid-search approach, in addition to a manual trial and error approach (see provided Jupyter notebook python code for hyperparameters used). The dataset comprising ~3.7 million records was randomly split into training and test datasets, comprising ~3.5 million training (95%) and ~0.2 million testing (5%) records, with almost identical target (Δ<em>T</em>) distributions ([*SI Appendix*, Fig. S6](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). Models were then trained on the training dataset and tested on the test dataset.

We conducted a number of model simulations using the XGBoost algorithm ([Fig. 3](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03)). The Non-FF simulation used nonforest fraction features only (latitude, elevation, and distance to the nearest coastline), which was found to be a poor model ([Fig. 3](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03)). In order to understand the sensitivity of temperature response to forest loss at difference length scales, we developed a range of models including both local and regional forest loss over progressively larger distances from 0 to 100 km. Including both local and regional forest loss substantially improved model performance ([Fig. 3](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03)). Adding forest fraction loss features may artificially improve model performance, so we repeated the same sensitivity, but instead substituting forest fraction loss data with random data ranging 0 to 1, which was found not to improve model prediction. Our best model used all available features including information on forest fraction loss at both local scales of 0 to 2 km and out to regional scales of 2 to 100 km ([Fig. 3](https://www.pnas.org/doi/10.1073/pnas.2309123120#fig03)).

We found that there is some collinearity between forest fraction loss features ([*SI Appendix*, Fig. S7](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)), which is a problem in that it undermines the statistical significance of independence among model features. We tested two additional models whereby the six forest fraction loss features ([Table 1](https://www.pnas.org/doi/10.1073/pnas.2309123120#t01)) were replaced by exact copies of either the local forest loss feature (0–2 km) or by the outermost regional forest loss feature (50–100 km). Our reasoning was such that if collinearity was important, using multiple copies of either forest loss feature would produce a model that was just a good as the best model using the correct forest fraction loss data. However, we found that these two models were inferior when predicting subsets of the test dataset focusing on data points experiencing different levels of local and regional loss ([*SI Appendix*, Fig. S8](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). These results suggest that these collinearities are not important because good model prediction requires information on both local and regional forest loss.

Finally, we deployed a linear least squares regression model to compare the results from the XGBoost algorithm under the best simulation using all available features. We found that using a linear model resulted in poor model prediction ([*SI Appendix*, Fig. S9](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)) justifying the supervised machine learning algorithm used here.

We used the model combined with observed forest loss to simulate the 2000–2020 warming across the Amazon. We did this separately for locations where we had observations of as well as across the whole Brazilian Amazon Biome. We found median (mean) warming of 0.58 K (0.78 K) over locations with observations and 0.47 K (0.63 K) over the whole biome.

### Forest Cover Change Scenarios in 2050

We use a new set of land cover change scenarios for the Brazilian Amazon biome to 2050 ([31](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r31)) to predict future forest loss across the region. The scenarios are aligned with SSPs and RCPs and consider a balance between global forest loss drivers (such as GDP growth, population growth, per capita consumption of agricultural products, international trade policies, and climatic conditions) and local factors driving deforestation (such as land use, agrarian structure, agricultural suitability, protected areas, distance to roads, and infrastructure projects) ([31](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r31)). We consider two scenarios: a middle-of-the-road narrative (SSP2\_RCP4.5) and a strong inequality scenario (SSP3\_RCP7.0). Both scenarios exhibit considerable forest cover loss by 2050 with greater wide-spread forest loss in SSP3\_RCP7.0 ([*SI Appendix*, Figs. S1 and S2](https://www.pnas.org/lookup/doi/10.1073/pnas.2309123120#supplementary-materials)). Data for each scenario is provided on a 10 x 10 km grid in NetCDF format ([https://zenodo.org/record/5123560#.Y9zmhT3P2Ls](https://zenodo.org/record/5123560#.Y9zmhT3P2Ls)) at 5-y increments from 2015 to 2050. We regridded the data by assigning the same forest fraction value from the native resolution within a 0.01-degree resolution grid (approx. 1 km at the equator) for each scenario to obtain forest loss to 2050. Finally, we estimate warming associated with each scenario across the whole Brazilian Amazon Biome between 2020 and 2050.

## Data, Materials, and Software Availability

Data and code that support the findings of this study are available at [http://archive.researchdata.leeds.ac.uk/id/eprint/1085](http://archive.researchdata.leeds.ac.uk/id/eprint/1085) ([66](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r66)). Dataset and code data have been deposited in Amazon deforestation causes strong regional warming ([http://archive.researchdata.leeds.ac.uk/id/eprint/1085](http://archive.researchdata.leeds.ac.uk/id/eprint/1085)) ([66](https://www.pnas.org/doi/10.1073/pnas.2309123120#core-collateral-r66)).

## Acknowledgments

This work received funding from the European Research Council under the European Union’s Horizon 2020 research and innovation program (Grant agreement no. 771492), the Natural Environmental Research Council (NE/J009822/1), and the Newton Fund, through the Met Office Climate Science for Service Partnership Brazil.

### Author contributions

E.W.B., J.C.A.B., and D.V.S. designed research; E.W.B. and J.C.A.B. performed research; F.G.S.B., C.v.R., and A.P.D.A. contributed new reagents/analytic tools; E.W.B. and J.C.A.B. analyzed data; and E.W.B., J.C.A.B., and D.V.S. wrote the paper.

### Competing interests

The authors declare no competing interest.

## Supplementary Materials

Appendix 01 (PDF)

- [Download](https://www.pnas.org/doi/suppl/10.1073/pnas.2309123120/suppl_file/pnas.2309123120.sapp.pdf)
- 1.28 MB

## References (66 total, showing 66)

1. G. B. Bonan, Forests and climate change: Forcings, feedbacks, and the climate benefits of forests. *Science* **320**, 1444–1449 (2008).

2. D. Lawrence, K. Vandecar, Effects of tropical deforestation on climate and agriculture. *Nat. Clim. Change* **5**, 27–36 (2015).

3. G. Jia et al., “Land–climate interactions. Climate change and land: An IPCC Special Report on climate change, desertification, land degradation, sustainable land management” in *Food Security, and Greenhouse Gas Fluxes in Terrestrial Ecosystems* (2019), pp. 1–186.

4. J. Winckler et al., Robust identification of local biogeophysical effects of land-cover change in a global climate model. *J. Clim.* **30**, 1159–1176 (2017).

5. M. H. Costa, P. M. Brando, J. A. Marengo, S. R. Saleska, L. V. Gatti, *Chapter 7: Biogeophysical Cycles: Water et al. Amazon Assessment Report* (United Nations Sustainable Development Solutions Network, New York, NY, 2021).

6. R. Alkama, A. Cescatti, Biophysical climate impacts of recent changes in global forest cover. *Science* **351**, 600–604 (2016).

7. J. A. Prevedello et al., Impacts of forestation and deforestation on local temperature across the globe. *PLoS ONE* **14**, e0213368 (2019).

8. G. Duveiller et al., A dataset mapping the potential biophysical effects of vegetation cover change. *Sci. Data* **5**, 1–15 (2018).

9. Y. Li et al., Local cooling and warming effects of forests based on satellite observations. *Nat. Commun.* **6**, 1–8 (2015).

10. R. M. Bright et al., Local temperature response to land cover and management change driven by non-radiative processes. *Nat. Clim. Change.* **7**, 296–302 (2017).

11. M. Zhang et al., Response of surface air temperature to small-scale land clearing across latitudes. *Environ. Res. Lett.* **9**, 034002 (2014).

12. G. Duveiller et al., The mark of vegetation change on Earth’s surface energy balance. *Nat. Commun.* **9**, 679 (2018).

13. D. Lawrence et al., The unseen effects of deforestation: Biophysical effects on climate. *Front. For. Global Change* **49**, 756115 (2022).

14. L. Zhu et al., Comparable biophysical and biogeochemical feedbacks on warming from tropical moist forest degradation. *Nat. Geosci.* **16**, 244–249 (2023).

15. J. Baker, D. Spracklen, Climate benefits of intact Amazon forests and the biophysical consequences of disturbance. *Front. For. Global Change* **2**, 47 (2019).

16. E. E. Maeda et al., Large-scale commodity agriculture exacerbates the climatic impacts of Amazonian deforestation. *Proc. Natl. Acad. Sci. U.S.A.* **118**, e2023787118 (2021).

17. N. H. Wolff et al., Impacts of tropical deforestation on local temperature and human well-being perceptions. *Global Environ. Change* **52**, 181–189 (2018).

18. J. Winckler et al., Nonlocal effects dominate the global mean surface temperature response to the biogeophysical effects of deforestation. *Geophys. Res. Lett.* **46**, 745–755 (2019).

19. L. Chen, P. Dirmeyer, Reconciling the disagreement between observed and simulated temperature responses to deforestation. *Nat. Commun.* **11**, 202 (2020).

20. L. R. V. Zeppetello et al., Large scale tropical deforestation drives extreme warming. *Environ. Res. Lett.* **15**, 084012 (2020).

21. A. S. Cohn et al., Forest loss in Brazil increases maximum temperatures within 50 km. *Environ. Res. Lett.* **14**, 084047 (2019).

22. O. Crompton et al., Deforestation-induced surface warming is influenced by the fragmentation and spatial extent of forest loss in Maritime Southeast Asia. *Environ. Res. Lett.* **16**, 114018 (2021).

23. M. C. Hansen et al., High-resolution global maps of 21st-century forest cover change. *Science* **342**, 850–853 (2013).

24. M. J. van Marle et al., Fire and deforestation dynamics in Amazonia (1973–2014). *Global Biogeochem. Cycles* **31**, 24–38 (2017).

25. L. E. Aragao et al., Environmental change and the carbon balance of Amazonian forests. *Biol. Rev.* **89**, 913–931 (2014).

26. S.P.f.t. Amazon, *Executive Summary of the Amazon Assessment Report 2021* (United Nations, New York, NY, 2021).

27. B. Soares-Filho et al., *LBA-ECO LC-14 Modeled Deforestation Scenarios, Amazon Basin: 2002–2050* (ORNL DAAC, 2013).

28. Z. Zeng et al., Deforestation-induced warming over tropical mountain regions regulated by elevation. *Nat. Geosci.* **14**, 23–29 (2021).

29. C. M. Taylor et al., “Late-stage” deforestation enhances storm trends in coastal West Africa. *Proc. Natl. Acad. Sci. U.S.A.* **119**, e2109285119 (2022).

30. G. Duveiller et al., Local biophysical effects of land use and land cover change: Towards an assessment tool for policy makers. *Land Use Policy* **91**, 104382 (2020).

31. F. G. Silva Bezerra et al., New land-use change scenarios for Brazil: Refining global SSPs with a regional spatially-explicit allocation model. *PLoS ONE* **17**, e0256052 (2022).

32. T. E. Lovejoy, C. Nobre, *Amazon Tipping Point* (American Association for the Advancement of Science, 2018).

33. C. Mora et al., Global risk of deadly heat. *Nat. Clim. Change* **7**, 501–506 (2017).

34. B. F. Alves de Oliveira et al., Deforestation and climate change are projected to increase heat stress risk in the Brazilian Amazon. *Commun. Earth Environ.* **2**, 1–8 (2021).

35. L. A. Parsons et al., Tropical deforestation accelerates local warming and loss of safe outdoor working hours. *One Earth.* **4**, 1730–1740 (2021).

36. N. H. Wolff et al., The effect of deforestation and climate change on all-cause mortality and unsafe work conditions due to heat exposure in Berau, Indonesia: A modelling study. *Lancet Planet. Health* **5**, e882–e892 (2021).

37. R. Flach et al., Conserving the Cerrado and Amazon biomes of Brazil protects the soy economy from damaging warming. *World Dev.* **146**, 105582 (2021).

38. A. T. Leite-Filho et al., Deforestation reduces rainfall and agricultural revenues in the Brazilian Amazon. *Nat. Commun.* **12**, 1–7 (2021).

39. C. Smith et al., Tropical deforestation causes large reductions in observed precipitation. *Nature* **615**, 270–275 (2023).

40. Y. Li et al., Deforestation-induced climate change reduces carbon storage in remaining tropical forests. *Nat. Commun.* **13**, 1964 (2022).

41. M. J. Sullivan et al., Long-term thermal sensitivity of Earth’s tropical forests. *Science* **368**, 869–874 (2020).

42. L. E. Aragão et al., 21st Century drought-related fires counteract the decline of Amazon deforestation carbon emissions. *Nat. Commun.* **9**, 1–12 (2018).

43. E. W. Butt et al., Achieving Brazil’s deforestation target will reduce fire and deliver air quality and public health benefits. *Earth's Future* **10**, e2022EF003048 (2022).

44. C. H. S. Junior et al., The Brazilian Amazon deforestation rate in 2020 is the greatest of the decade. *Nat. Ecol. Evol.* **5**, 144–145 (2020).

45. L. V. Gatti et al., Amazonia as a carbon source linked to deforestation and climate change. *Nature* **595**, 388–393 (2021).

46. D. M. Lapola et al., The drivers and impacts of Amazon forest degradation. *Science* **379**, eabp8622 (2023).

47. D. Fawcett et al., Declining Amazon biomass due to deforestation and subsequent degradation losses exceeding gains. *Global Change Biol.* **29**, 1106–1118 (2023).

48. T. O. Assis et al., Projections of future forest degradation and CO<sub>2</sub> emissions for the Brazilian Amazon. *Sci. Adv.* **8**, eabj3309 (2022).

49. M. Longo et al., Impacts of degradation on water, energy, and carbon cycling of the Amazon tropical forests. *J. Geophys. Res. Biogeosci.* **125**, e2020JG005677 (2020).

50. V. H. Heinrich et al., The carbon sink of secondary and degraded humid tropical forests. *Nature* **615**, 436–442 (2023).

51. C. Vancutsem et al., Long-term (1990–2019) monitoring of forest cover changes in the humid tropics. *Sci. Adv.* **7**, eabe1603 (2021).

52. C. A. Nobre et al., Land-use and climate change risks in the Amazon and the need of a novel sustainable development paradigm. *Proc. Natl. Acad. Sci. U.S.A.* **113**, 10759–10768 (2016).

53. A. J. Hartley et al., Simulation of vegetation feedbacks on local and regional scale precipitation in West Africa. *Agric. For. Meteorol.* **222**, 59–70 (2016).

54. J. Khanna et al., Regional dry-season climate changes due to three decades of Amazonian deforestation. *Nat. Clim. Change* **7**, 200–204 (2017).

55. R. Xu et al., Contrasting impacts of forests on cloud cover based on satellite observations. *Nat. Commun.* **13**, 670 (2022).

56. R. Bassett et al., Observations of urban heat island advection from a high-density monitoring network. *Q. J. R. Meteorol. Soc.* **142**, 2434–2441 (2016).

57. D. Zhou et al., The footprint of urban heat island effect in China. *Sci. Rep.* **5**, 1–11 (2015).

58. L. R. Boysen et al., Global climate response to idealized deforestation in CMIP6 models. *Biogeosciences* **17**, 5615–5638 (2020).

59. S. J. De Hertog et al., The biogeophysical effects of idealized land cover and land management changes in Earth system models. *Earth Syst. Dyn.* **14**, 629–667 (2023).

60. J. Crook et al., Effects on early monsoon rainfall in West Africa due to recent deforestation in a convection-permitting ensemble. *Weather Clim. Dyn.* **4**, 229–248 (2023).

61. R. Trancoso et al., Converting tropical forests to agriculture increases fire risk by fourfold. *Environ. Res. Lett.* **17**, 104019 (2022).

62. Collection 5 of the annual land use land cover maps of Brazil \[Online database\] (2020).

63. C. C. Funk et al., A quasi-global precipitation time series for drought monitoring. *US Geol. Surv. Data Ser.* **832**, 1–12 (2014).

64. J. J. Danielson, D. B. Gesch, *Global Multi-resolution Terrain Elevation Data 2010 (GMTED2010)* (US Department of the Interior, US Geological Survey, Washington, DC, 2011).

65. T. Chen, C. Guestrin, “XGBoost: A scalable tree boosting system” in *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining* (2016), pp. 785–794.

66. E. W. Butt, Amazon deforestation causes strong regional warming: Dataset. Research Data Leeds Repository, University of Leeds. https://archive.researchdata.leeds.ac.uk/1085/. Deposited 3 April 2023.
