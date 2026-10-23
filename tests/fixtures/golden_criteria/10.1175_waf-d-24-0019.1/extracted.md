---
title: "A Bayesian Framework for the Probabilistic Interpretation of Radar Observations and Severe Hailstorm Reports"
authors: "Isabelle C. Greco, Steven C. Sherwood, Timothy H. Raupach, Gab Abramowitz"
doi: "10.1175/waf-d-24-0019.1"
source: "ams_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 18313
---

# A Bayesian Framework for the Probabilistic Interpretation of Radar Observations and Severe Hailstorm Reports

## Abstract

Understanding when and where severe hailstorms occur is key to managing the serious risk they pose. Radar products, such as the maximum expected size of hail (MESH), are often used to form a severe hail climatology. However, the challenges of relating reflectivity measured aloft to severe hail at the surface mean these climatologies have unknown uncertainty. Here, we quantify the uncertainty of radar observations of severe hailstorms by deriving a probabilistic interpretation of MESH within a fully Bayesian framework calibrated using reports from Australia’s Severe Storms Archive in southeast Queensland. Moreover, our novel approach accounts for the spatially varying (under)reporting rate in the region. Despite the popularity of using MESH thresholds to distinguish severe hail events, our results suggest that these thresholds are less sharp than previously believed and question their interpretation. Furthermore, we quantify the spatial variability in the severe hail reporting rate and suggest that, even over the most densely populated areas in the region, the reporting rate may be as low as 53%. Finally, we produce a hail climatology that has a similar magnitude to existing radar-based climatologies but with smoother and more realistic spatial gradients. Our method is generalizable to many other datasets within and beyond severe weather by enabling the principled usage of reports even when the absence of a report does not necessarily indicate the event did not occur.

## Significance Statement

Severe hailstorms are one of Australia’s costliest natural perils. This work aims to improve how we use radar to understand when and where these storms occur. Although radar is a popular tool in this pursuit, it is challenging to link reflectivity aloft to hail at the ground. Rather than using a binary threshold on a radar-based parameter to distinguish severe hail, we instead treat radar data as a predictor of the probability of severe hail, estimating this probability by concurrently estimating the reporting rate of severe hail. This work sheds new light on how we might reinterpret radar data to improve our forecasting and understanding of severe hail. Moreover, our method is applicable to other severe weather hazards and even beyond climate science.

## 1. Introduction

Australia is regularly ravaged by bushfires, floods, and cyclones, yet severe hailstorms over densely populated cities stand among the continent’s most costly insured weather events ([McAneney et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib48); [Insurance Council of Australia 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib39)). To better prepare for the associated social and economic impacts, particularly in a warming climate, it is necessary for us to understand severe hail risk ([Púčik et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib56)). As numerical modeling efforts are limited by the small spatial and temporal scale of hailstorms and their complex microphysics ([Leslie et al. 2008](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib45); [Mahoney et al. 2012](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib47); [Brooks 2013](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib17); [Raupach et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib59)), hail studies often rely upon imperfect observations (e.g., [Knight and Knight 2001](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib42); [Brooks et al. 2003](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib18); [Raupach et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib59)).

Radar products are commonly used to interrogate hail risk. While they provide consistent spatial and temporal coverage of their surrounds, it remains challenging to definitively link radar echoes to the hydrometeor types that generated them (e.g., [Brook et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15); [Murillo and Homeyer 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib49)), despite recent advances using dual-polarized radars (e.g., [Kumjian et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib44)). Moreover, hail aloft may be advected or melted as it falls, adding further uncertainty when linking radar-derived products to surface hail (e.g., [Schuster et al. 2006](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib65); [Saltikoff et al. 2010](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib63); [Brook et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15)). Nonetheless, radar products remain popular in research and operationally, particularly the maximum expected size of hail (MESH; [Witt et al. 1998](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90)), a temperature-weighted vertical integral of reflectivity. Many studies determine or apply a threshold on MESH to infer surface hail (e.g., [Cintineo et al. 2012](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib24); [Soderholm et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69); [Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84); [Raupach et al. 2023b](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib61); [Brook et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib16)). Given the numerous uncertainties in interpreting radar data, we argue that it is more precise to consider MESH probabilistically, as evidence influencing the probability of surface hail.

Creating a probabilistic (or deterministic) interpretation of MESH requires observations of hail at the surface. Reports of severe hail (hailstones greater than 20 mm in diameter) at the surface are typically made by storm chasers and the general public ([Allen et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib5); [Hand and Cappelluti 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib36)). Individual reports are frequently approximate, imprecise, and prone to human errors ([Schuster et al. 2006](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib65); [Allen and Tippett 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib3); [Brimelow and Taylor 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib14); [Murillo and Homeyer 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib49)). Further, reports are concentrated around more densely populated urban areas ([Allen et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib5); [Allen and Karoly 2014](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib2); [Tuovinen et al. 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib78); [Brimelow and Taylor 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib14)), are more likely during daylight hours ([Trapp et al. 2006](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib76); [Barras et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib10); [Wendt and Jirak 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib85)), and favor more severe and dramatic events ([Cintineo et al. 2012](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib24); [Taszarek et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib75)). Thus, (severe) hailstorms are reported at some unknown rate that is likely well below 100% and variable in space and time, frustrating attempts to use reports as a ground truth.

Nonetheless, probabilistic interpretations of radar data exist. Notably, [Witt et al. (1998)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90) formalized the probability of hail (POH) metric implied by [Waldvogel et al. (1979)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib83) and proposed a new probability of severe hail (POSH) metric. However, these methods suffer from several shortcomings. First, POH and POSH were calibrated under the assumption that all hail events were detected, ignoring the possibility of reporting rates well below unity. Hence, they quantify the probability of detected hail. Further, these probabilities are not always well defined ([Kopp et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib43)). Finally, a threshold is often placed on POH and POSH to create a binary hail discriminator (e.g., [Nisi et al. 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib50); [Farnell et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib32); [Madonna et al. 2018](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib46); [Barras et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib11)). This method ignores the (flawed) probabilistic insights yielded by POH and POSH and instead creates another binary indicator with unquantified uncertainty.

We address these shortcomings using a Bayesian approach. We calibrate and apply a probabilistic interpretation of MESH that accounts for underreporting by concurrently estimating the spatially varying reporting rate. We outline our novel Bayesian model in [section 2](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s2). After successfully applying this model to synthetic data in [section 3](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s3), we use observations of severe hail from the southeast Queensland region. Hence, in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4), we show that hopes for a sharp MESH threshold may be misplaced, present the first detailed analysis of the spatially varying severe hail reporting rate in the area, and illustrate how our Bayesian model can create a hail climatology. We discuss the implications of these results and suggest avenues for future work in [section 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s5) before concluding in [section 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s6).

## 2. Data and Bayesian model

### a. Gridded data

We fitted our model to radar, population density, and surface hail observations from southeast Queensland, Australia. This region ([Fig. 1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig1)) is a hail hotspot ([Allen and Allen 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib4); [Soderholm et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib70); [Brook et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib16); [Raupach et al. 2023b](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib61)), well observed by the Mount Stapylton radar, and relatively densely populated. We aggregated the three data sources onto a 0.25°, 6-hourly grid \[1000–2200 local time (LT)\] covering 6.5 hail seasons (January 2010–April 2016 inclusive). Australia’s hail season was conservatively defined as September–April inclusive ([Schuster et al. 2005](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib64); [Allen et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib5); [Allen and Karoly 2014](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib2); [Rasuly et al. 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib58); [Dowdy et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib29); [Brook et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib16)). Although a finer grid would reveal greater detail and facilitate comparisons between our results and other radar-based studies of the region (e.g., [Soderholm et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69); [Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84)), this coarse grid mitigated the low spatial and temporal accuracy of hail reports in the severe storms archive ([Schuster et al. 2005](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib64)) and the imbalance between grid cells with and without a report (only 0.6% of MESH observations had a corresponding report). Instead, the chosen spatial resolution enables comparisons with hail proxies constructed using ERA5 (e.g., [Raupach et al. 2023a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib60)) and still provides some diurnal insights. As all corrected severe hail reports were made between 1200 and 2000 LT, we assumed 1000–2200 LT captured all severe hail activity. Finally, our study was limited to January 2010–April 2016 due to poor reporting data quality. Between 2006 (when the radar commenced operating) and 2010, one-third of reports were assigned a default time of 0000 UTC and would require time-consuming manual correction. After 2016, reporting rates decreased to near zero.

![Figure 1](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f1.jpg)

**Figure 1.** Map of the study area in southeast Queensland and northeast New South Wales. The study area (red) encompasses the Queensland state capital (Brisbane) as well as several smaller urban areas indicated in the map by points sized according to their relative population ([Australian Bureau of Statistics 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib7)). The location of the Mount Stapylton radar is also highlighted (blue triangle) along with its 135-km range ring (blue) and its cone of silence (blue; 16 km as per [Soderholm et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69)).

#### 1) Radar observations

The Mount Stapylton radar is an S-band radar situated on an isolated hill southeast of Central Brisbane ([Bureau of Meteorology 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib21)). The native data resolution of the severe hail index (SHI) was a 1-km, 6-min Cartesian grid. We calculated MESH following [Witt et al. (1998)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90):

**Equation 1.**

$$
\text{MESH} = 2.54\sqrt{\text{SHI}}.
$$

Only observations within approximately 135 km of the radar’s location (see [Fig. 1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig1)) were used after noting that data quality degraded beyond this point; a naive estimate of the severe hail reporting rate revealed anomalously high reporting rates due to anomalously low numbers of events. We attribute this degradation to beam broadening and poorer vertical sampling ([Bunkers and Smith 2013](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib19); [Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84), Table 1 for volume coverage pattern). We applied a speckle filter to remove spurious three-dimensional groups of MESH measurements less than nine 1-km, 6-min pixels in size (J. Soderholm 2023, personal communication). We checked for between-scan changes in domain maximum MESH greater than 75 mm, which can indicate operational issues (J. Soderholm 2023, personal communication), but found that our data never violated this condition. MESH was then aggregated to the aforementioned grid by taking the maximum in each spatiotemporal grid cell to capture the storms’ greatest MESH-measured severity. Given our coarse spatiotemporal grid, we made no correction for radar’s “cone of silence” ([Blair et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib13); [Soderholm et al. 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib68), [2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69)), trusting storm advection to carry overhead cells into scanned regions. Similarly, we did not apply any advection corrections to smooth MESH measurements between radar scans ([Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84); [Brook et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15)).

#### 2) Population density data

We used the Australian estimated resident population at 1-km<sup>2</sup> resolution ([Australian Bureau of Statistics 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib8)) transformed from the Australian Albers coordinate reference system to a 0.25° Mercator grid using geographic information system (QGIS)’ warpreproject function ([QGIS Development Team 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib57)). For coastal grid cells, the ocean was treated as unpopulated land. The gridded product was only available for some years in 2010–16. Hence, we used only the 2016 estimate and modeled the population density as constant. We discuss this potential source of error further in [section 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s5).

#### 3) Severe hail reports

Reports of hail greater than 2 cm in diameter, hereafter hail reports, were drawn from the Australian Severe Storms Archive (SSA; [Bureau of Meteorology 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib20)). From January 2010 to April 2016, we obtained 115 reports corresponding to 52 hail days. We investigated reports made prior to 1200 LT ([Table 1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tbl1)). Reports assigned the default 0000 UTC (1000 LT) were corrected by consulting radar, comments associated with the report, and news articles. The remaining suspiciously early reports seemed to have had local time (as stated in the comments) incorrectly recorded as UTC. While we corrected impossible latitude and longitude values, we did not investigate smaller errors as we chose the 0.25° grid size in part to mitigate reporting inaccuracies. Finally, given the approximate and inconsistent nature of supplementary reporting information, the model uses only the binary indicator of whether at least one report was made in that cell.

**Table 1.** The number of reports in the study region adjusted for each of the three reasons described in [section 2a(3)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s2a3).

![Table 1](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-t1.jpg)

### b. Bayesian model

This section outlines the Bayesian framework to estimate the probability of severe surface hail from MESH via the concurrent estimation of the reporting rate as a function of population density. This model corrects for the spatial biases of hail reports, explicitly incorporates prior knowledge, and quantifies uncertainty using probabilities. We first set out our key assumptions before explaining the statistical model and how it is fitted. We draw upon models more common in the tornado literature (e.g., [Anderson et al. 2007](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib6); [Cheng et al. 2013](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib23); [Elsner et al. 2016a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib30),[b](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib31); [Potvin et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib53); [Nouri et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib51); [Potvin et al. 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib54)) but introduce MESH to parameterize the probability of severe hail.

#### 1) Probabilistic framing

We assume that when MESH is not recorded in some grid cell, the probability of severe surface hail is zero, as MESH is only recorded when there is sufficiently high reflectivity measured above the environmental melting level (derived from ERA5 reanalysis, [Hersbach et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib37); [Soderholm et al. 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib71)) to suggest the presence of hail. This assumption is imperfect: radar malfunction, beam blocking, and beam broadening can cause false absences of MESH observations ([Stržinar and Skok 2018](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib74)). Further, extreme size sorting can result in large hailstones at the surface despite only moderate reflectivity aloft ([Snyder et al. 2014](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib67); [Witt et al. 2018](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib91)). Nonetheless, this assumption is supported by the presence of a corresponding MESH measurement for all severe hail reports. Suppose that *R* and *H* are binary random variables indicating that a report was made and severe hail reached the surface, respectively. Then, when MESH is observed, our assumption implies

**Equation 2.**

$$
P{({R = 1})} = P{({H = 0})}P{({\left. {R = 1} \right|H = 0})} + P{({H = 1})}P{({\left. {R = 1} \right|H = 1})},
$$

where *P* is the probability. Second, we assume that reports cannot be false. While many reports in the SSA since 1995 are verified, the existence of some implausible reports suggests this verification is not total (J. Soderholm 2023, personal communication). However, this partial verification in tandem with our own quality control and the low volume of reports justifies this assumption. This assumption implies that a report cannot occur without severe surface hail; thus,

$$
P{({\left. {R = 1} \right|H = 0})} = 0.
$$

Hence, [(2)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E2) becomes

**Equation 3.**

$$
P{({R = 1})} = P{({H = 1})}P{({\left. {R = 1} \right|H = 1})},
$$

where the two factors are hereafter the hail and reporting functions. These factors are parameterized using the inverse logit function:

$$
\text{logit}^{- 1}{(x)} = \frac{1}{1 + \exp {({- x})}}
$$

for real *x*. The inverse logit function maps the real numbers to the open interval (0, 1) and thus always generates valid probabilities. Moreover, the resulting S-shaped curve reflects our current understanding of the relationship between the predictors (MESH and population density) and the probabilities of hail and reporting, respectively (e.g., Fig. 1 in the online [supplemental material](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf); [Witt et al. 1998](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90); [Allen and Allen 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib4); [Barras et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib10)). Specifically, the probability of hail increases as MESH increases and may perhaps saturate at a high enough value of MESH. This relationship is analogous to the reporting function.

Hence, we model the probability of hail as a function of MESH:

**Equation 4.**

$$
P{({H = 1})} = \text{logit}^{- 1}{\lbrack{\alpha_{1} + \alpha_{2}\text{YJ}^{*}{({m;\alpha_{3}})}}\rbrack}
$$

for MESH measurement *m* ≥ 0 (mm), where $\text{YJ}^{*}$ is a standardized Yeo–Johnson transform defined below and *α*<sub>1</sub>, *α*<sub>2</sub>, and *α*<sub>3</sub> are the tunable parameters. We model the reporting rate of severe surface hail using the population density:

**Equation 5.**

$$
P{({\left. {R = 1} \right|H = 1})} = \text{logit}^{- 1}{\lbrack{\beta_{1} + \beta_{2}\text{YJ}^{*}{({d;\beta_{3}})}}\rbrack}
$$

for population density in *d* ≥ 0 (people km<sup>−2</sup>) and parameters *β*<sub>1</sub>, *β*<sub>2</sub>, and *β*<sub>3</sub>. Population density is not the only influence on the reporting rate ([Allen and Tippett 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib3); [Allen and Allen 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib4)). However, the similarity between the distribution of people and hail reports in the area ([Fig. 2](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig2)) suggests this approach may capture the largest biases.

![Figure 2](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f2.jpg)

**Figure 2.** Map showing the (left) population density and (right) number of reports in the study area and surrounds. Note the similarity between the regions of high population density and high numbers of reports.

Both MESH and population density are transformed using the Yeo–Johnson transform, a smooth extension of the Box–Cox transform, given by

$$
\text{YJ}{({x;\lambda})} = {\{\begin{array}{ll} \frac{{({x + 1})}^{\lambda} - 1}{\lambda} & {\ {}\ {}\text{if}\ {}\lambda \neq 0,x \geq 0} \\ {\log {({x + 1})}} & {\ {}\ {}\text{if}\ {}\lambda = 0,x \geq 0} \end{array}}
$$

for *x* ≥ 0 and real power parameter *λ* ([Yeo and Johnson 2000](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib92)). Transformed MESH or population density is standardized to zero mean and variance using the sample mean and standard deviation to give the function $\text{YJ}^{*}$. MESH was employed in this study due to its greater popularity in producing hail climatologies (e.g., [Soderholm et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69); [Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84); [Ackermann et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib1)). However, as both [(1)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E1) and the Yeo–Johnson transformation are power transformations, we would not expect parameterizing the hail function using SHI to change this study’s results. Defining *α*<sub>2</sub> and *β*<sub>2</sub> as the coefficients of these standardized predictors ensures their scale remains the same even as *α*<sub>3</sub> and *β*<sub>3</sub> change.

The Yeo–Johnson transform encompasses several common power transforms that we also tested individually \[the identity transform given by *λ* = 1, the square root by *λ* = 1/2, and the (translated) logarithmic by *λ* = 0\]. However, the flexibility generated by estimating the power parameter yielded better results during early testing. Hence, the hail function in [(4)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E4) is defined by three parameters: *α*<sub>1</sub> translates the function along the (transformed) MESH axis, *α*<sub>2</sub> controls the steepness of the probability increase, and *α*<sub>3</sub> defines the power transform applied to MESH. The same is true for *β*<sub>1</sub>, *β*<sub>2</sub>, and *β*<sub>3</sub> in [(5)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E5) with respect to population density.

#### 2) Bayesian inference

We estimate posterior probability distributions for all parameters (*α*<sub>1</sub>, *α*<sub>2</sub>, *α*<sub>3</sub>, *β*<sub>1</sub>, *β*<sub>2</sub>, and *β*<sub>3</sub>) and other unknown quantities conditioned upon the observed data using Bayesian inference. We use Bayesian inference for several reasons:

1. Statements about uncertainty are made probabilistically (e.g., given the observed data, there is a 95% probability that the probability of severe hail at some MESH value is between *X* and *Y*).
2. Prior knowledge can be included to complement the sparse data through additional probabilistic statements about the parameters or other unknowns.
3. Computational Bayesian statistics provide a flexible and efficient tool to fit this nonlinear model.

Bayesian models consist of two components: the likelihood function and the prior distribution ([Gelman et al. 2004](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib35)). In our model, the likelihood function describes the distribution of reports given the parameters, MESH, and population density. The prior distribution describes prior knowledge of the parameters (or other unknown quantities). From these two distributions, we can make inferences from the posterior distribution: that of the parameters given the observed data.

Equations [(3)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E3)[](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E4)–[(5)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E5) form the basis of the likelihood function. To model all reports, we specify how these probabilities play out across the spatiotemporal grid. We assume conditional independence between cells: once we have observed MESH and the population density of a given cell, we assume that the surrounding cells provide no further information. This assumption simplifies the model (important when data are sparse) and also reflects our belief that MESH and population density provide sufficient information about the hail and reporting processes. Further, the scale of our grid cells, both spatially and temporally, reduces the pertinence of adjacent information. Future work could indirectly relax this assumption by including extra predictors or random terms that capture spatial or temporal dependence (e.g., [Cheng et al. 2013](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib23)) or by creating a hierarchical structure (e.g., [Potvin et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib53)).

Setting priors is challenging as we have limited knowledge of hail and reporting functions themselves, let alone the parameters which define them. However, the hail and reporting functions should be increasing (e.g., [Witt et al. 1998](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90); [Allen and Allen 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib4); [Barras et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib10)). Therefore, we require *α*<sub>2</sub> &gt; 0 and *β*<sub>2</sub> &gt; 0. We also explored the impacts of including prior information on the total number of hail events expected or the probability of hail at certain MESH values. Exact parameterizations of the priors trialed are given in [appendix B](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app2).

### c. Model fitting and evaluation

#### 1) Computational approach

We employed Markov chain Monte Carlo (MCMC) methods to sample from the posterior distribution and thereby make posterior inferences. To generate MCMC samples, we employed the no-U-turn sampler (NUTS), an efficient Hamiltonian Monte Carlo sampling algorithm developed by [Betancourt (2017)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib12) and implemented in Stan ([Stan Development Team 2022b](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib73)). For each model, we generated 2000 samples from four chains and discarded the first 1000 samples from each chain to reduce bias ([Gelman et al. 2004](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib35)). To ensure we correctly sampled the posterior distribution, we heeded the warnings of the NUTS’ internal consistency checks and monitored the $\hat{R}$ statistic and the effective sample size of the six parameters ([Vehtari et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib81)).

#### 2) Performance evaluation

Evaluating model quality is challenging as the model yields distributions of probabilities and quantities of interest which we must verify using the severe hail reports. We explored many goodness-of-fit metrics but focus here upon the expected log pointwise predictive density (ELPD) and out-of-sample calibration statistics.

##### (i) ELPD

The ELPD is the expected logarithm of the posterior predictive distribution evaluated on new, unseen data ([Vehtari et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib80)). The posterior predictive distribution is the distribution of new observations given the likelihood, priors, and the observed data ([Gelman et al. 2004](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib35)). Hence, a larger ELPD indicates that the model is making better predictions. As the ELPD cannot be calculated exactly and is tedious to approximate using leave-one-out cross validation (LOOCV), we use the efficient approximation derived by [Vehtari et al. (2017)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib80) (and implemented in [Vehtari et al. 2023](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib82)) and its 95% credible interval (not presented here for readability).

##### (ii) Out-of-sample calibration statistics

To assess out-of-sample model calibration, we employed fourfold cross validation. Given the data sparsity along every axis and the strong interannual variability of Australian severe hail ([Schuster et al. 2005](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib64); [Allen and Karoly 2014](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib2); [Dowdy et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib29)), evaluation using a random or temporal split would not be robust. Hence, we employed the multiplet algorithm ([Vakayil and Joseph 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib79)) to split the data with awareness of the multivariate predictor distribution. We considered the resulting weak dependence between the test and training sets an acceptable sacrifice for improved model evaluation.

The out-of-sample calibration metric we focused upon was the Bayesian *p* value ([Gelman et al. 2004](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib35)). For any given subset of the data, we can estimate the posterior distribution of the number of reports in that subset by simulating reports using the probabilities calculated out of sample. Ideally, this distribution would be centered around the observed number of reports in the subset. The Bayesian *p* value was defined as the smaller of the two tail probabilities: the posterior probability that the simulated number of reports was less than or equal to, or greater than or equal to, the observed number of reports.

The Bayesian *p* value was calculated for each of the 47 subsets created by partitioning the data in the following 11 ways:

- Four even (log) population density bins
- Ten latitudes.
- Seven longitudes.
- Urban indicator (&gt;100 people km<sup>−2</sup>).
- Seven storm seasons.
- Seven days of the week.
- Weekend indicator.
- Two hours of the day.
- MESH &gt; 22 mm.
- MESH &gt; 32 mm.
- MESH &gt; 44 mm.

We verified there were sufficient reports in each subset to enable robust evaluation.

#### 3) Model exploration

We partnered the likelihood described in [section 2b](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s2b) with many different priors ([appendix B](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app2)) to examine the sensitivity of our results to the specification of our imperfect prior knowledge. Given that our qualitative results were similar regardless of the prior (see [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4)), we used the prior that created the best-fitting model. We then explored the impact of adding extra spatial and temporal predictors believed to be related to hail occurrence or the reporting rate ([appendix B](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app2)). The paucity and sparsity of our data increased the risk of overfitting and prevented us from adding more than one predictor at a time, as well as from taking the opposite approach of creating a model with all possible predictors from which predictors are removed. Hence, our analysis in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4) focuses primarily on the two-predictor models and only leverages the experiments with additional predictors for further insights into model quality.

## 3. Proof-of-concept synthetic simulations

Solution nonuniqueness and parameter confounding were observed in some similar models ([Potvin et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib53), [2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib54)). However, using synthetic data, we show that our model arrives at a correct and unique solution, even under misleading priors.

### a. Solution uniqueness experiments

To test whether our model successfully estimates hail probabilities, we fitted the model to simulated data. We used known inverse logit hail and reporting functions as per [(3)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E3)[](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E4)–[(5)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#E5) to assign a probability of a (simulated) report given MESH and population density to each observed MESH and population density pair in our data. Simulated reports were then randomly generated according to these probabilities. For simplicity, we assumed that the transformations were known: the logarithm for population density (effectively, though not exactly, *β*<sub>3</sub> = 0) and the identity for MESH (*α*<sub>3</sub> = 1). Therefore, we did not standardize the predictors. The remaining parameters (see [appendix A](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app1)) were selected to generate approximately equal numbers of reports under two different regimes:

1. Low probability of hail but high reporting rate (LHHR).
2. High probability of hail but low reporting rate (HHLR).

We generated 100 synthetic datasets of the same size as the original. We trialed numerous priors when fitting the model to each generated dataset. We focus in this section on the three most illustrative examples:

1. Strongly informative priors centered at the true values of *α*<sub>1</sub>, *α*<sub>2</sub>, *β*<sub>1</sub>, and *β*<sub>2</sub> and with negligible overlap with the priors for the opposing regime.
2. Weakly informative priors that were centered as in item 1 but had noticeable overlap.
3. Misleading priors, in which the priors described in item 1 were used for the opposing regime.

These priors are defined in more detail in [appendix A](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app1) and visualized in [supplemental Fig. 7](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf).

The distribution of the hail and reporting functions estimated from one synthetic dataset is shown in [Fig. 3](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig3). Despite noticeable bias when the misleading prior was used, the model consistently differentiates the LHHR and HHLR regimes. Moreover, in the two informative cases, the posterior uncertainty correctly captures the true function. These results are seen across the 100 simulations ([supplemental Fig. 2](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf)). [Figure 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig4) shows the prior and posterior distributions of the LHHR parameters (see [supplemental Fig. 3](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf) for the corresponding figure for the HHLR parameters). The posterior estimates move toward the true values, and the priors dictate the posterior bias and variance. Note the larger posterior uncertainty in the hail function than in the reporting function visible in [Fig. 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig4) is likely due to the larger prior uncertainty visualized in [Fig. 3](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig3).

![Figure 3](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f3.jpg)

**Figure 3.** Hail and reporting functions estimated by each of the three experiments on one synthetic dataset. The functions used to generate the data are given by the black dashed line and the 50% and 95% credible intervals are shaded. The corresponding values of the LOOCV ELPD estimate are given in each figure.

![Figure 4](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f4.jpg)

**Figure 4.** The prior (dashed) and posterior (solid) distributions of the four parameters of one LHHR simulation experiment. (top) Two parameters of the hail function and (bottom) those of the reporting function in this simulation. Note the different scales in each panel.

### b. Parametric misalignment

Such exact alignment between the data-generating process and the likelihood as tested in [section 3a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s3a) is unrealistic. Hence, we also tested performance when inverse logit functions were not utilized to generate the data, seeking indicators that the model was inappropriate for these data. We used combinations of linear (*α*<sub>1</sub>+ *α*<sub>2</sub>*x*), quadratic (*α*<sub>1</sub>+ *α*<sub>2</sub>*x*<sup>2</sup>), and exponential ($1 - e^{- \alpha_{1}x}$) functions of simulated and observed MESH and population density to generate synthetic reports.

In the least successful cases, the degraded model performance was obvious, revealing itself in non-Gaussian bivariate posterior distributions and in numerical warnings of divergent transitions and of low effective sample size. In others, model–data mismatch manifested as poor estimation of the overall reporting probability \[*P*(*R* = 1)\] and so was detectable using the evaluation metrics. However, compensating errors in the hail and reporting functions that still produced good estimates of the overall reporting probability were challenging to detect. Hence, where possible, it is important to also verify model results against information dependent on only one of the hail or reporting functions. For our observational models, we could compare our results with the existing interpretations of MESH, estimates of the total number of hail days in the region, and local climatologies. It is more challenging to evaluate the reporting function as there is minimal quantification of underreporting in the SSA.

Thus, poor numerical performance is a sufficient, but not necessary, indicator that the model is unsuitable for the data. These experiments revealed that even when a model is fitted without numerical issues, it remains important to increase confidence in the model by evaluating the hail and reporting functions separately using any available domain knowledge.

## 4. Results

Unless otherwise stated, [Figs. 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5)–[7](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig7) that follow utilize the posterior distribution derived from the two-predictor model that gave the highest ELPD and the highest score on several other in- and out-of-sample metrics considered. In this model, the priors on *α*<sub>1</sub> and *β*<sub>1</sub> were weakly informative normal distributions, gamma distributions on *α*<sub>2</sub> and *β*<sub>2</sub>, and very weakly informative normal distributions for *α*<sub>3</sub> and *β*<sub>3</sub> (see [appendix B](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app2)). Given the uncertainty in the ELPD approximation, other two-predictor models of potentially equal or higher ELPD were those employing a weakly informative normal distribution or lognormal distribution in place of the gamma distribution, which yielded qualitatively similar results, and several models with additional information regarding the MESH value at which the probability of hail should be 0.5 (see [appendix B](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#app2)). However, these latter models did not achieve similarly good performance on other (out of sample) metrics and so are not considered further.

### a. Probabilistically interpreting MESH

The best-fitting posterior relationship between MESH and the probability of severe surface hail ([Fig. 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5), top) is flatter and lower than anticipated. At 30-mm MESH, a reasonable severe hail threshold, the probability of severe surface hail is between 0.05 and 0.17 (95% credible interval). We would expect, however, that a MESH threshold should be the value at which severe surface hail becomes more likely than not. [Figure 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5) suggests this point occurs at a MESH value of 49–100 mm (95% credible interval) in the best-fitting model and is similar under numerous prior perturbations (unless prior information about this quantity is included in the model). Although some studies do consider uncertainty regarding MESH thresholds (e.g., [Brook et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib16)), our approach is unique in quantifying this uncertainty. [Figure 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5) also questions the wisdom of a threshold; the increase in the probability of hail with MESH is not sharp, even in the model informed of the expected number of severe hail events (see last row of [Fig. 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5)). Hence, existing estimates of the number of hail events in the area are compatible with this slower increase in severe hail probability with increasing MESH.

![Figure 5](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f5.jpg)

**Figure 5.** (top) The hail function for the best-performing model as determined by the ELPD. (bottom) The distribution of the value of MESH at which severe hail becomes more likely than not with the different prior perturbations. The dashed line indicates a 30-mm MESH threshold. References to strength in the prior names refer to the informativeness of the prior (e.g., weakly informative, strongly informative, etc.). The models in which information about this quantity is included are not shown.

### b. Understanding the hail reporting rate

[Figure 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig6) reveals that the spatial variability of reporting across the region is large. While [Murillo and Homeyer (2019)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib49) concluded that above a density of 25 people mi<sup>−2</sup> (approximately 10 people km<sup>−2</sup>) hail reporting in the contiguous United States is acceptably unbiased, [Fig. 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig6) (right) suggests that closer to 300 people km<sup>−2</sup> is required to make such an assertion in southeast Queensland. This difference is likely attributable to lower community participation in hail reporting. [Murillo and Homeyer (2019)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib49) discarded nonstorm data over areas that did not meet this threshold. In contrast, our method enables us to use these observations with an awareness of the inherent bias. Further, we have quantified this bias and no longer need to “overpredict” when interpreting MESH or reports (e.g., [Witt et al. 1998](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90); [Doswell et al. 2005](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib28); [Prein and Holland 2018](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib55)). The newfound ability to use observations over sparsely populated areas is particularly important in Australia; [Fig. 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig6) reveals that even around the country’s third-most populous city, there are many regions where we expect that fewer than half of severe hail events are reported.

![Figure 6](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f6.jpg)

**Figure 6.** (left) The posterior mean reporting rate across the region. Coastlines and the New South Wales–Queensland state border are shown in red. (right) The reporting function from the best-fitting model to illustrate the uncertainty and possibility of a plateau.

[Figure 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig6) also suggests that beyond a population density of, for example, 100 people km<sup>−2</sup>, the reporting rate may plateau at a value less than one. This limiting value could be as low as 0.53 (95% credible interval). This conclusion is reasonable since we know of numerous severe events in populated areas that do not appear in the SSA (e.g., the severe hail event in Chinchilla, Queensland, on 28 November 2015; [Courier Mail 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib25)).

### c. Climatological insights

Exact comparisons between our (short) climatology of the expected number of hail days in [Fig. 7](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig7) and the work of others in the region are impeded by the differing grid sizes that smooth or enhance local hotspots and the time periods considered (which overlap but are not identical). Despite these differences, our results in [Fig. 7](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig7) are qualitatively similar to the climatologies produced by [Soderholm et al. (2017)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69) and [Warren et al. (2020)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84). We too observe an inland severe hail maximum in the lee of the elevated terrain at the western edge of the study area, particularly just west of Casino, and decreasing frequencies toward the coast. Further, despite our disagreement on MESH threshold values, our estimate of 5.04 (95% credible interval of 4.16–6.41) severe hail days annually per 10 000 km<sup>2</sup> lies between the estimates of 3.67 damaging hail days as indicated by insurance reports and 7.35 hail (of any size) days produced by [Warren et al. (2020)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84) and [Soderholm et al. (2017)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69), respectively. Finally, note that our climatology is less speckled than any of the threshold-based climatologies presented in [Fig. 7](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig7). Given that the gridding is identical, utilizing probabilities to find the expected number of hail days is responsible for the more realistic spatial gradients.

![Figure 7](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-f7.jpg)

**Figure 7.** The posterior mean estimate of the average number of annual hail days over the region with a 95% credible interval, in comparison with three threshold-based estimates of the same quantity. Coastlines and the state border are shown in red with three regional centers referenced in other regional climatologies marked in white.

Experimentation with additional predictors in the hail function also supported the existing process-based understanding of this climatology. When testing the inclusion of MESH in adjacent grid cells to incorporate spatial structure into our estimates, the ELPD, calibration on weekends, and urban Brisbane calibration improved the most when the eastward MESH observation was incorporated. The general west-to-east motion of storms in the region ([Soderholm et al. 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib68)) and the eastward offset of the regions of most frequent hail development from the regions of most frequent hailstorm initiation ([Soderholm et al. 2017](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69)) support the importance of the eastward predictor over the northward and southward predictors. It is unclear why the westward predictor was not equally important given the coarse time scales considered. While further work and different data (e.g., Doppler winds, [Brook et al. 2021](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15)) are required to understand this connection and explore the role of storm motion and hail advection, this insight highlights the potential of our model to include or elucidate physical processes.

## 5. Discussion

### a. Reconciling different MESH thresholds

We propose several possible explanations for the discrepancy between the MESH thresholds employed in existing literature and our findings.

First, we suspect part of the uncertainty in the threshold is linked to the role of advection. Both [Brook et al. (2021)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15) and [Ackermann et al. (2024)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib1) showed that when MESH is adjusted for advection, their MESH thresholds are better able to discriminate severe hail (see their Figs. 2 and 7, respectively). Although we leave including advection to future work, we propose either advecting MESH prior to the fitting process and modeling the probability of hail given advected MESH or, alternatively, including an advection predictor into the hail function.

The different grid resolutions between studies may also explain the differences in the estimated threshold though this is unlikely. A larger grid size would reduce, not increase, the estimated MESH threshold (e.g., [Warren et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84), Fig. 6). As our grid is larger than the grid or radius used in many other studies (e.g., [Cintineo et al. 2012](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib24); [Ackermann et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib1)), our grid is likely mitigating, not exacerbating the differing results.

To further investigate whether it was our data or our assumptions leading to different MESH thresholds, we determined, using the top one, two, three, etc., most densely populated grid cells, the MESH threshold which optimizes the Heidke skill score (HSS; [Wilks 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib87)). When using only grid cells with a population density over 100 people km<sup>−2</sup>, optimal thresholds were in the range of 44–46 mm ([supplemental Fig. 4](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf)). These values are not unreasonable; [Warren et al. (2020)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84) and [Brook et al. (2021)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib15) obtained thresholds of 44 and 46 mm, respectively, when maximizing the HSS using insurance reports on a daily 1-km<sup>2</sup> grid. However, our optimal thresholds increased as progressively less densely populated areas were included. Further, [Table B3](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB3) illustrates that despite the differing ground truths used to determine a MESH threshold, the estimated thresholds are still similar. Hence, our assumptions drive most of the difference between our findings and previous studies.

Specifically, further experimentation suggests that our explicit modeling of underreporting and the disconnection between a probabilistic hail threshold and a threshold that maximizes the HSS explain the larger MESH in [Fig. 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5). To illustrate the disconnection between two definitions of the MESH threshold, we applied logistic regression ([Wilks 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib87)) to the same subsets of our data for which we estimated HSS optimal thresholds. When using the one, two, and three most densely populated cells, the value of the MESH threshold which optimized the HSS yielded severe hail probabilities near 0.5. However, as less densely populated grid cells were included and we continued to assume that all severe hail events were reported, the probabilistic MESH threshold increased, while the HSS optimal threshold did not ([supplemental Fig. 5](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf)). While this assumption may be appropriate in some locations and for some sources of reports (e.g., insurance reports), [Fig. 6](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig6) illustrates it is not reasonable in our study. Therefore, [Fig. 5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#fig5) gives the results of (transformed) logistic regression when we acknowledge this low (and spatially varying) reporting rate. Further, it suggests that HSS optimal thresholds applied in the region correspond to severe hail probabilities significantly less than 0.5; they should perhaps be interpreted as the point where the probability of severe hail is appreciably nonzero.

### b. Understanding and improving model performance

The best-performing model presented in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4), like most others tested, has two key calibration issues. First, the model underpredicts the number of reports in moderately high-density cells (approximately 500 people km<sup>−2</sup>) but overpredicts in 27.625°S, 153.125°E, the second most populous grid cell ([supplemental Fig. 6](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf)). Second, observed reports are split almost evenly between weekends and weekdays, but the model underpredicts the number of weekend reports. These issues may arise from modeling the population density as constant, but the Yeo–Johnson transform acts to minimize the impact of the largest increases in population density in the most densely populated grid cells. Instead, the simple reporting function is likely unable to capture some of the subtleties of (urban) reporting behavior. [Supplemental Fig. 6](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf) reveals that more reports are observed than expected in the cells west of Brisbane, in which lies a major highway to Toowoomba that may increase the number of observers, particularly on weekends ([Kelly et al. 1985](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib41); [Allen and Tippett 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib3); [Allen and Allen 2016](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib4); [Brook et al. 2024](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib16)). Further, reports are underpredicted at the Gold Coast, a populous but touristic urban center. In these two areas, it is likely that the reporter density (and thus reporting rate) has changed without a corresponding change in population density. This possibility was not included in our model but is now visible in the results. Including the weekend as a predictor in the model did improve the calibration on the weekend/weekday partition but did not address these other issues, supporting our hypothesis of a more fundamental modeling shortcoming.

Finally, the model can always be improved. Considering the role of hail size in the reporting process (e.g., [Kelly et al. 1985](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib41); [Williams et al. 1999](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib88); [Cintineo et al. 2012](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib24)) and including predictors describing storm chaser behavior (e.g., [Tuovinen et al. 2009](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib77); [Allen and Tippett 2015](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib3)) could improve the model of severe hail reporting and thereby improve our estimates of severe hail probability. Further, incorporating additional data, including radar data over a longer period, time-varying population density estimates, insurance claims, or (social) media reports, could also reduce the uncertainty in our results and ensure they are not dependent upon one dataset.

## 6. Conclusions

We used MESH observations and severe hail reports to nuance the popular approach of estimating MESH thresholds. We instead calibrated a probabilistic relationship between MESH and severe hail at the surface. This relationship accounts for the influence of population density on the severe hail reporting rate. At MESH values commonly used as a severe hail threshold, the probability of severe hail was lower than anticipated (between 0.05 and 0.17 at 30-mm MESH and 95% credible interval). Further, severe hail only became more likely than not when MESH reached 49–100 mm (95% credible interval). Together, these results cast doubt upon accepted interpretations of MESH thresholds and on the certainty with which MESH is commonly used. We also found that even over the city of Brisbane, Australia’s third most densely populated city, severe hail events were regularly not reported to the SSA. We estimate that the reporting rate could be as low as 0.53 and even lower in less populated surrounding areas. Finally, our regional climatology identified similar hail hotspots to those highlighted in other studies but had smoother spatial gradients, suggesting that we have found a better-calibrated severe hail indicator.

However, our study was limited by the paucity of reports in Australia and the lack of time-varying population data. Obtaining more and higher-quality data, particularly in situ observations, is an avenue for future work that would reduce some of the uncertainty in our results. Moreover, our model is limited by multiple, common, assumptions: temporal stationarity of the relationships investigated, conditional independence between spatiotemporal grid cells, and the accuracy of quality-controlled reports. Relaxing these assumptions (e.g., via a more detailed investigation of spatial dependence, modeling false reports, using a finer grid) are also potential avenues of future work, provided more data become available. Similarly, increasing the sophistication of the model by modeling the propensity for reporting more severe events and the behavior of storm spotters on road networks may also refine our results.

Nonetheless, tests with synthetic data suggest our model is skillful even with little prior knowledge and highlight several indicators of a poor match between the model and data. We conclude therefore by noting that the robustness and generalizability of this approach lends it to numerous applications in addition to calibrating an interpretation of MESH. Other hail proxies (e.g., [Raupach et al. 2023a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib60)) are also frequently calibrated using hail reports, but few explicitly account for the numerous known nonmeteorological biases in their ground truth. Our method could explicitly link these proxies to probabilities of hail at the ground (rather than hail-prone environments) and quantify the uncertainty in this link while accounting for reporting biases. Further, other severe weather events, like tornadoes and severe wind gusts (e.g., [Allen et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib5); [Potvin et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib53)), as well as nonmeteorological applications like the identification of money laundering (e.g., [Jullum et al. 2020](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib40)), could all be areas of application for the proposed framework where the absence of an event’s reporting or detection does not guarantee the event did not occur.

## Acknowledgments

All authors are supported by the Australian Research Council (ARC) Centre of Excellence for Climate Extremes (Major Investment Grant CE170100023). IG was supported by an Australian Government Research Training Program Fee Offset (RSAI8000) and ARC Grant Scholarship (RSGA1000). Since March 2024, TR’s position at UNSW Sydney has been supported by QBE Insurance. Computation was undertaken with the assistance of Gadi, part of Australia’s National Computing Infrastructure (NCI), an NCRIS-enabled capability supported by the Australian Government. The authors are grateful to the NCI team and the Computational Modelling and Support team within the ARC Centre of Excellence for Climate Extremes for their support. The authors thank three anonymous reviewers for their constructive comments.

## Data availability statement

The elevation data are from Geoscience Australia’s smoothed Digital Elevation Model (DEM-S; [Gallant et al. 2011](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib34)). The radar data are part of the level 2 operational dataset from the Australian Unified Radar Archive ([Soderholm et al. 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib71)). The population density data are freely available from the Australian Bureau of Statistics ([Australian Bureau of Statistics 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib8)) at [https://www.abs.gov.au/statistics/people/population/regional-population/2021#data-download](https://www.abs.gov.au/statistics/people/population/regional-population/2021#data-download). The hail reports are freely available on the severe storms archive website ([Bureau of Meteorology 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib20)) at [http://www.bom.gov.au/australia/stormarchive/](http://www.bom.gov.au/australia/stormarchive/). All codes are available on GitHub and Zenodo: [https://github.com/isabelle-greco/bayes-hail-reportmodel](https://github.com/isabelle-greco/bayes-hail-reportmodel) and [https://doi.org/10.5281/zenodo.14275035](https://doi.org/10.5281/zenodo.14275035). Analysis was performed in R ([R Core Team 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib62)) with assistance from the RStan ([Stan Development Team 2022a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib72)), bayesplot ([Gabry and Mahr 2022](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib33)), posterior ([Bürkner et al. 2023](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib22)), loo ([Vehtari et al. 2023](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib82)), SciCo ([Crameri 2023](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib26)), poibin ([Hong 2013](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib38)), and tidyverse ([Wickham et al. 2019](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib86)) packages. The color palette, batlow, was chosen to be perceptually uniform and ordered and accessible to color-vision-deficient and color-blind people whether viewed in color or black and white following [Crameri et al. (2020)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib27).

## APPENDIX A

### Priors in LHHR and HHLR Experiments

[Tables A1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblA1) and [A2](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblA2) detail the three priors used in the LHHR and HHLR experiments discussed in [section 3a](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s3a). They are visualized in [supplemental Fig. 7](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf). In [Tables A1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblA1) and [A2](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblA2), and hereinafter, $\mathcal{N}_{\text{trunc}}{({\mu,\sigma^{2}})}$ represents the normal distribution with mean *μ* and variance *σ*<sup>2</sup> truncated to the range \[0, ∞).

**Table A1.** Priors on the parameters of the hail function used in the LHHR and HHLR simulations.

![Table A1](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tA1.jpg)

**Table A2.** Priors on the parameters of the reporting function used in the LHHR and HHLR simulations.

![Table A2](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tA2.jpg)

## APPENDIX B

### Priors for Observational Models

The priors for the parameters of the observational models considered in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4) are given in [Tables B1](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB1) and [B2](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB2) and plotted in [supplemental Figs. 8](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf)–[13](https://journals.ametsoc.org/supplemental//journals/wefo/39/12/WAF-D-24-0019.1.xml/10.1175_WAF-D-24-0019.s1.pdf). The strongly informative priors on *α*<sub>3</sub> and *β*<sub>3</sub> are derived from the posterior credible intervals generated by the models that used weakly informative priors on these parameters. The filtered priors append a multiplicative factor to the very weakly informative priors. This factor represents a probabilistic summary of our review of the literature concerning either the expected total number of hail events in the region or optimal MESH thresholds.

**Table B1.** Parameters of the prior distributions considered in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4). The same priors were applied to the parameters of the reporting function.

![Table B1](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tB1.jpg)

**Table B2.** Parameters of the prior distributions used for *α*<sub>3</sub> and *β*<sub>3</sub> in [section 4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#s4).

![Table B2](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tB2.jpg)

From [Soderholm et al. (2017)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib69), [Prein and Holland (2018)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib55), and [Warren et al. (2020)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib84), we conclude that southeast Queensland experiences 3–8 hail days per 10 000 km<sup>2</sup>. Moreover, applying a range of MESH thresholds suggests that one hail day corresponds to 3–14 hail events on our grid. Hence, we estimate 225–2750 hail events occurred in our data covering 37 700 km<sup>2</sup> and 6.5 storm seasons. Let $\mu_{N_{\text{hail}}}$ be the expected total number of hail events in our study period given the observed MESH and population density data and *p*<sub>data</sub> be the proportion of data used to fit the model (i.e., *p*<sub>data</sub> = 0.75 during fourfold cross validation). Then, summing over all observations, we have

$$
\mu_{N_{\text{hail}}} = {\sum\limits_{\text{time}}{\sum\limits_{\text{space}}P}}{({\left. {H = 1} \right|\alpha_{1},\alpha_{2},\alpha_{3},m_{\text{obs}}})},
$$

where *m*<sub>obs</sub> is the relevant observed MESH value. Our knowledge of the number of expected events is summarized with

$$
\mu_{N_{\text{hail}}} \sim \mathcal{N}{({1490p_{\text{data}},{({420p_{\text{data}}})}^{2}})}.
$$

While we have expressed the filter as the prior distribution of $\mu_{N_{\text{hail}}}$, to the model, it is simply a function of parameters *α*<sub>1</sub>, *α*<sub>2</sub>, and *α*<sub>3</sub> which increases or decreases the prior mass assigned by the very weakly informative prior in different parts of the parameter space.

The second filter is constructed assuming that the optimal MESH threshold represents the value at which hail becomes more likely than not. Hence, the optimal MESH threshold is the solution $m^{*}$ to

$$
P{({\left. {H = 1} \right|\alpha_{1},\alpha_{2},\alpha_{3},m^{*}})} = \frac{1}{2}.
$$

We summarize the range of MESH thresholds reviewed in [Table B3](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB3) by the skew normal distribution ([Azzalini 1985](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib9)):

$$
m^{*} \sim s\text{kew}\mathcal{N}{({25,8,4})}
$$

and apply this filter the same way as the first.

**Table B3.** MESH thresholds used in other radar-based studies of hail. The radars employed are a mixture of S and C bands. SHAVE denotes the Severe Hazards Analysis and Verification Experiment. References made to size in the “Calibrating data” column refer to the size of reports considered. Note thresholds vary within the range given by [Witt et al. (1998)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib90) due to the melting level. The two thresholds given by [Wilson et al. (2009)](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib89) are optimal when evaluated using the HSS and critical index, respectively.

![Table B3](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tB3.jpg)

[](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib52)[](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#bib66)

Last, the predictors and the associated priors utilized for experiments with additional predictors are given in [Tables B4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB4) and [B5](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB5).

**Table B4.** The predictors added to the hail function with their associated prior. Where multiple priors are given, the second indicates the prior on the transformation parameter. The six variations on the MESH predictors and their parameters were each applied separately but are listed together as the priors were identical. Note that neighborhood maximum MESH is given by the maximum, for a given time and location, of maximum MESH measurements in grid cells in each of the four cardinal directions. Where not available, this predictor is set to zero.

![Table B4](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tB4.jpg)

**Table B5.** The predictors added to the reporting function with their associated prior. The same meaning applies when two parameters are given and when multiple predictors are given. Neighborhood maximum MESH is calculated as described in [Table B4](https://journals.ametsoc.org/view/journals/wefo/39/12/WAF-D-24-0019.1.xml#tblB4).

![Table B5](https://journals.ametsoc.org/view/journals/wefo/39/12/full-WAF-D-24-0019.1-tB5.jpg)

## References (92 total, showing 92)

- Ackermann, L., J. Soderholm, A. Protat, R. Whitley, L. Ye, and N. Ridder, 2024: Radar and environment-based hail damage estimates using machine learning. <em>Atmos. Meas. Tech.</em>, **17**, 407–422, https://doi.org/10.5194/amt-17-407-2024.

- Allen, J. T., and D. J. Karoly, 2014: A climatology of Australian severe thunderstorm environments 1979–2011: Inter-annual variability and ENSO influence. <em>Int. J. Climatol.</em>, **34**, 81–97, https://doi.org/10.1002/joc.3667.

- Allen, J. T., and M. K. Tippett, 2015: The characteristics of United States hail reports: 1955–2014. <em>Electron. J. Severe Storms Meteor.</em>, **10** (3), https://ejssm.com/ojs/index.php/site/article/view/60/59.

- Allen, J. T., and E. R. Allen, 2016: A review of severe thunderstorms in Australia. <em>Atmos. Res.</em>, **178–179**, 347–366, https://doi.org/10.1016/j.atmosres.2016.03.011.

- Allen, J. T., D. J. Karoly, and G. A. Mills, 2011: A severe thunderstorm climatology for Australia and associated thunderstorm environments. <em>Aust. Meteor. Oceanogr. J.</em>, **61**, 143–158, https://doi.org/10.22499/2.6103.001.

- Anderson, C. J., C. K. Wikle, Q. Zhou, and J. A. Royle, 2007: Population influences on tornado reports in the United States. <em>Wea. Forecasting</em>, **22**, 571–579, https://doi.org/10.1175/WAF997.1.

- Australian Bureau of Statistics, 2021: Statistical area level 2. Australian Bureau of Statistics, accessed 15 January 2024, https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/main-structure-and-greater-capital-city-statistical-areas/statistical-area-level-2.

- Australian Bureau of Statistics, 2022: Australian population grid in ESRI grid format, 2016 to 2021. Australian Bureau of Statistics, accessed 7 February 2023, https://www.abs.gov.au/statistics/people/population/regional-population/2021#data-download.

- Azzalini, A., 1985: A class of distributions which includes the normal ones. <em>Scand. J. Stat.</em>, **12**, 171–178.

- Barras, H., A. Hering, A. Martynov, P.-A. Noti, U. Germann, and O. Martius, 2019: Experiences with &gt;50,000 crowdsourced hail reports in Switzerland. <em>Bull. Amer. Meteor. Soc.</em>, **100**, 1429–1440, https://doi.org/10.1175/BAMS-D-18-0090.1.

- Barras, H., O. Martius, L. Nisi, K. Schroeer, A. Hering, and U. Germann, 2021: Multi-day hail clusters and isolated hail days in Switzerland—large-scale flow conditions and precursors. <em>Wea. Climate Dyn.</em>, **2**, 1167–1185, https://doi.org/10.5194/wcd-2-1167-2021.

- Betancourt, M., 2017: A conceptual introduction to Hamiltonian Monte Carlo. arXiv, 1701.02434v2, https://doi.org/10.48550/arXiv.1701.02434.

- Blair, S. F., D. R. Deroche, J. M. Boustead, J. W. Leighton, B. L. Barjenbruch, and W. P. Gargan, 2011: A radar-based assessment of the detectability of giant hail. <em>Electron. J. Severe Storms Meteor.</em>, **6** (7), https://ejssm.com/ojs/index.php/site/article/view/34.

- Brimelow, J. C., and N. Taylor, 2017: Verification of the MESH product over the Canadian prairies using a high-quality surface hail report dataset sourced from social media. *38th Conf. on Rediative Meteorology*, Chicago, IL, Amer. Meteor. Soc., 240, https://ams.confex.com/ams/38RADAR/webprogram/Paper321272.html.

- Brook, J. P., A. Protat, J. Soderholm, J. T. Carlin, H. McGowan, and R. A. Warren, 2021: Hailtrack—Improving radar-based hailfall estimates by modeling hail trajectories. <em>J. Appl. Meteor. Climatol.</em>, **60**, 237–254, https://doi.org/10.1175/JAMC-D-20-0087.1.

- Brook, J. P., J. S. Soderholm, A. Protat, H. McGowan, and R. A. Warren, 2024: A radar-based hail climatology of Australia. <em>Mon. Wea. Rev.</em>, **152**, 607–628, https://doi.org/10.1175/MWR-D-23-0130.1.

- Brooks, H. E., 2013: Severe thunderstorms and climate change. <em>Atmos. Res.</em>, **123**, 129–138, https://doi.org/10.1016/j.atmosres.2012.04.002.

- Brooks, H. E., J. W. Lee, and J. P. Craven, 2003: The spatial distribution of severe thunderstorm and tornado environments from global reanalysis data. <em>Atmos. Res.</em>, **67**–**68**, 73–94, https://doi.org/10.1016/S0169-8095(03)00045-0.

- Bunkers, M. J., and P. L. Smith, 2013: Comments on “An objective high-resolution hail climatology of the contiguous United States”. <em>Wea. Forecasting</em>, **28**, 915–917, https://doi.org/10.1175/WAF-D-13-00020.1.

- Bureau of Meteorology, 2022: Severe storms archive. Bureau of Meteorology, accessed 6 March 2023, http://www.bom.gov.au/australia/stormarchive/.

- Bureau of Meteorology, 2024: Radar site information. Bureau of Meteorology, accessed 15 January 2024, http://www.bom.gov.au/australia/radar/about/radar\_site\_info.shtml#:∼:text=The%20radar%20site%20information%20is,location%2C%20radar%20type%20and%20availability.

- Bürkner, P.-C., J. Gabry, M. Kay, and A. Vehtari, 2023: Posterior: Tools for working with posterior distributions, version 1.4.1. R package, https://mc-stan.org/posterior/.

- Cheng, V. Y. S., G. B. Arhonditsis, D. M. L. Sills, H. Auld, M. W. Shephard, W. A. Gough, and J. Klaassen, 2013: Probability of tornado occurrence across Canada. <em>J. Climate</em>, **26**, 9415–9428, https://doi.org/10.1175/JCLI-D-13-00093.1.

- Cintineo, J. L., T. M. Smith, V. Lakshmanan, H. E. Brooks, and K. L. Ortega, 2012: An objective high-resolution hail climatology of the contiguous United States. <em>Wea. Forecasting</em>, **27**, 1235–1248, https://doi.org/10.1175/WAF-D-11-00151.1.

- Courier Mail, 2015: Hailstones across the downs. *The Courier Mail*, 28 November, https://www.couriermail.com.au/news/queensland/chinchilla/hailstones-across-the-downs/image-gallery/1928e5efeb5e6674d5da277ef01b0867.

- Crameri, F., 2023: Scientific colour maps version 8.0.1. Zenedo, https://doi.org/10.5281/zenodo.1243862.

- Crameri, F., G. E. Shephard, and P. J. Heron, 2020: The misuse of colour in science communication. <em>Nat. Commun.</em>, **11**, 5444, https://doi.org/10.1038/s41467-020-19160-7.

- Doswell, C. A., III, H. E. Brooks, and M. P. Kay, 2005: Climatological estimates of daily local nontornadic severe thunderstorm probability for the United States. <em>Wea. Forecasting</em>, **20**, 577–595, https://doi.org/10.1175/WAF866.1.

- Dowdy, A. J., J. Soderholm, J. Brook, A. Brown, and H. McGowan, 2020: Quantifying hail and lightning risk factors using long-term observations around Australia. <em>J. Geophys. Res. Atmos.</em>, **125**, 2020JD033101, https://doi.org/10.1029/2020JD033101.

- Elsner, J. B., T. H. Jagger, and T. Fricker, 2016a: Statistical models for tornado climatology: Long and short-term views. <em>PLOS ONE</em>, **11**, e0166895, https://doi.org/10.1371/journal.pone.0166895.

- Elsner, J. B., and Coauthors, 2016b: The relationship between elevation roughness and tornado activity: A spatial statistical model fit to data from the central Great Plains. <em>J. Appl. Meteor. Climatol.</em>, **55**, 849–859, https://doi.org/10.1175/JAMC-D-15-0225.1.

- Farnell, C., T. Rigo, and N. Pineda, 2017: Lightning jump as a nowcast predictor: Application to severe weather events in Catalonia. <em>Atmos. Res.</em>, **183**, 130–141, https://doi.org/10.1016/j.atmosres.2016.08.021.

- Gabry, J., and T. Mahr, 2022: Bayesplot: Plotting for Bayesian models, version 1.10.0. R package, https://mc-stan.org/bayesplot/.

- Gallant, J., N. Wilson, T. Dowling, A. Read, and C. Inskeep, 2011: SRTM-derived 1 second digital elevation models version 1.0. Geoscience Australia, accessed 21 July 2024, https://www.ga.gov.au/scientific-topics/national-location-information/digital-elevation-data.

- Gelman, A., J. B. Carlin, H. S. Stern, and D. B. Rubin, 2004: *Bayesian Data Analysis*. 2nd ed. Texts in Statistical Science, Chapman and Hall/CRC, 668 pp.

- Hand, W. H., and G. Cappelluti, 2011: A global hail climatology using the UK Met Office Convection Diagnosis Procedure (CDP) and model analyses. <em>Meteor. Appl.</em>, **18**, 446–458, https://doi.org/10.1002/met.236.

- Hersbach, H., and Coauthors, 2020: The ERA5 global reanalysis. <em>Quart. J. Roy. Meteor. Soc.</em>, **146**, 1999–2049, https://doi.org/10.1002/qj.3803.

- Hong, Y., 2013: On computing the distribution function for the Poisson binomial distribution. <em>Comput. Stat. Data Anal.</em>, **59**, 41–51, https://doi.org/10.1016/j.csda.2012.10.006.

- Insurance Council of Australia, 2022: Insurance Catastrophe Resilience Report 2021–22. Catastrophe Rep., Insurance Council of Australia, 24 pp., https://insurancecouncil.com.au/wp-content/uploads/2022/09/20683\_ICA\_Final\_WebOptimised.pdf.

- Jullum, M., A. Løland, R. B. Huseby, G. Ånonsen, and J. Lorentzen, 2020: Detecting money laundering transactions with machine learning. <em>J. Money Laundering Control</em>, **23**, 173–186, https://doi.org/10.1108/JMLC-07-2019-0055.

- Kelly, D. L., J. T. Schaefer, and C. A. Doswell III, 1985: Climatology of nontornadic severe thunderstorm events in the United States. <em>Mon. Wea. Rev.</em>, **113**, 1997–2014, https://doi.org/10.1175/1520-0493(1985)113<1997:CONSTE&gt;2.0.CO;2.

- Knight, C. A., and N. C. Knight, 2001: Hailstorms. *Severe Convective Storms*, *Meteor. Monogr.*, No. 50, Amer. Meteor. Soc., 223–254, https://link.springer.com/chapter/10.1007/978-1-935704-06-5\_6.

- Kopp, J., A. Hering, U. Germann, and O. Martius, 2024: Verification of weather-radar-based hail metrics with crowdsourced observations from Switzerland. <em>Atmos. Meas. Tech.</em>, **17**, 4529–4552, https://doi.org/10.5194/amt-17-4529-2024.

- Kumjian, M. R., Z. J. Lebo, and A. M. Ward, 2019: Storms producing large accumulations of small hail. <em>J. Appl. Meteor. Climatol.</em>, **58**, 341–364, https://doi.org/10.1175/JAMC-D-18-0073.1.

- Leslie, L. M., M. Leplastrier, and B. W. Buckley, 2008: Estimating future trends in severe hailstorms over the Sydney Basin: A climate modelling study. <em>Atmos. Res.</em>, **87**, 37–51, https://doi.org/10.1016/j.atmosres.2007.06.006.

- Madonna, E., D. Ginsbourger, and O. Martius, 2018: A Poisson regression approach to model monthly hail occurrence in northern Switzerland using large-scale environmental variables. <em>Atmos. Res.</em>, **203**, 261–274, https://doi.org/10.1016/j.atmosres.2017.11.024.

- Mahoney, K., M. A. Alexander, G. Thompson, J. J. Barsugli, and J. D. Scott, 2012: Changes in hail and flood risk in high-resolution simulations over Colorado’s mountains. <em>Nat. Climate Change</em>, **2**, 125–131, https://doi.org/10.1038/nclimate1344.

- McAneney, J., B. Sandercock, R. Crompton, T. Mortlock, R. Musulin, R. Pielke Jr., and A. Gissing, 2019: Normalised insurance losses from Australian natural disasters: 1966–2017. <em>Environ. Hazards</em>, **18**, 414–433, https://doi.org/10.1080/17477891.2019.1609406.

- Murillo, E. M., and C. R. Homeyer, 2019: Severe hail fall and hailstorm detection using remote sensing observations. <em>J. Appl. Meteor. Climatol.</em>, **58**, 947–970, https://doi.org/10.1175/JAMC-D-18-0247.1.

- Nisi, L., O. Martius, A. Hering, M. Kunz, and U. Germann, 2016: Spatial and temporal distribution of hailstorms in the Alpine region: A long-term, high resolution, radar-based analysis. <em>Quart. J. Roy. Meteor. Soc.</em>, **142**, 1590–1604, https://doi.org/10.1002/qj.2771.

- Nouri, N., N. Devineni, V. Were, and R. Khanbilvardi, 2021: Explaining the trends and variability in the United States tornado records using climate teleconnections and shifts in observational practices. <em>Sci. Rep.</em>, **11**, 1741, https://doi.org/10.1038/s41598-021-81143-5.

- Ortega, K. L., 2018: Evaluating multi-radar, multi-sensor products for surface hailfall diagnosis. <em>Electron. J. Severe Storms Meteor.</em>, **13** (1), https://ejssm.com/ojs/index.php/site/article/view/69.

- Potvin, C. K., C. Broyles, P. S. Skinner, H. E. Brooks, and E. Rasmussen, 2019: A Bayesian hierarchical modeling framework for correcting reporting bias in the U.S. tornado database. <em>Wea. Forecasting</em>, **34**, 15–30, https://doi.org/10.1175/WAF-D-18-0137.1.

- Potvin, C. K., C. Broyles, P. S. Skinner, and H. E. Brooks, 2022: Improving estimates of U.S. tornado frequency by accounting for unreported and underrated tornadoes. <em>J. Appl. Meteor. Climatol.</em>, **61**, 909–930, https://doi.org/10.1175/JAMC-D-21-0225.1.

- Prein, A. F., and G. J. Holland, 2018: Global estimates of damaging hail hazard. <em>Wea. Climate Extremes</em>, **22**, 10–23, https://doi.org/10.1016/j.wace.2018.10.004.

- Púčik, T., C. Castellano, P. Groenemeijer, T. Kühne, A. T. Rädler, B. Antonescu, and E. Faust, 2019: Large hail incidence and its economic and societal impacts across Europe. <em>Mon. Wea. Rev.</em>, **147**, 3901–3916, https://doi.org/10.1175/MWR-D-19-0204.1.

- QGIS Development Team, 2022: GQIS geographical information system version 3.26. QGIS Association, https://www.qgis.org/project/visual-changelogs/visualchangelog326/.

- Rasuly, A. A., K. K. W. Cheung, and B. McBurney, 2015: Hail events across the Greater Metropolitan Severe Thunderstorm Warning Area. <em>Nat. Hazards Earth Syst. Sci.</em>, **15**, 973–984, https://doi.org/10.5194/nhess-15-973-2015.

- Raupach, T. H., and Coauthors, 2021: The effects of climate change on hailstorms. <em>Nat. Rev. Earth Environ.</em>, **2**, 213–226, https://doi.org/10.1038/s43017-020-00133-9.

- Raupach, T. H., J. Soderholm, A. Protat, and S. C. Sherwood, 2023a: An improved instability–shear hail proxy for Australia. <em>Mon. Wea. Rev.</em>, **151**, 545–567, https://doi.org/10.1175/MWR-D-22-0127.1.

- Raupach, T. H., J. S. Soderholm, R. A. Warren, and S. C. Sherwood, 2023b: Changes in hail hazard across Australia: 1979–2021. <em>npj Climate Atmos. Sci.</em>, **6**, 143, https://doi.org/10.1038/s41612-023-00454-8.

- R Core Team, 2022: R: A language and environment for statistical computing version 4.2.2. R package, https://www.r-project.org/.

- Saltikoff, E., J.-P. Tuovinen, J. Kotro, T. Kuitunen, and H. Hohti, 2010: A climatological comparison of radar and ground observations of hail in Finland. <em>J. Appl. Meteor. Climatol.</em>, **49**, 101–114, https://doi.org/10.1175/2009JAMC2116.1.

- Schuster, S. S., R. J. Blong, and M. S. Speer, 2005: A hail climatology of the greater Sydney area and New South Wales, Australia. <em>Int. J. Climatol.</em>, **25**, 1633–1650, https://doi.org/10.1002/joc.1199.

- Schuster, S. S., R. J. Blong, and K. J. McAneney, 2006: Relationship between radar-derived hail kinetic energy and damage to insured buildings for severe hailstorms in Eastern Australia. <em>Atmos. Res.</em>, **81**, 215–235, https://doi.org/10.1016/j.atmosres.2005.12.003.

- Skripniková, K., and D. Řezáčová, 2014: Radar-based hail detection. <em>Atmos. Res.</em>, **144**, 175–185, https://doi.org/10.1016/j.atmosres.2013.06.002.

- Snyder, J. C., A. V. Ryzhkov, H. B. Bluestein, and S. F. Blair, 2014: Polarimetric analysis of two giant-hail-producing supercells observed by X-band and S-band radars. *27th Conf. on Severe Local Storms*, Madison, WI, Amer. Meteor. Soc., 166, https://ams.confex.com/ams/27SLS/webprogram/Paper255455.html.

- Soderholm, J., H. McGowan, H. Richter, K. Walsh, T. Weckwerth, and M. Coleman, 2016: The Coastal Convective Interactions Experiment (CCIE): Understanding the role of sea breezes for hailstorm hotspots in eastern Australia. <em>Bull. Amer. Meteor. Soc.</em>, **97**, 1687–1698, https://doi.org/10.1175/BAMS-D-14-00212.1.

- Soderholm, J., H. McGowan, H. Richter, K. Walsh, T. Weckwerth, and M. Coleman, 2017: An 18-year climatology of hailstorm trends and related drivers across southeast Queensland, Australia. <em>Quart. J. Roy. Meteor. Soc.</em>, **143**, 1123–1135, https://doi.org/10.1002/qj.2995.

- Soderholm, J. S., K. I. Turner, J. P. Brook, T. Wedd, and J. Callaghan, 2019: High-impact thunderstorms of the Brisbane Metropolitan Area. <em>J. South. Hemisphere Earth Syst. Sci.</em>, **69**, 239–251, https://doi.org/10.1071/ES19017.

- Soderholm, J. S., V. Louf, J. Brook, A. Protat, and R. Warren, 2022: AURA—Operational radar network level 2 archive. Accessed 25 January 2023, https://doi.org/10.25914/JJWZ-0F13.

- Stan Development Team, 2022a: RStan: The R interface to Stan, version 2.21.5. R package, https://mc-stan.org/rstan/.

- Stan Development Team, 2022b: Stan modeling language users guide and reference manual. Stan Development Team, accessed 26 January 2023, https://www.mc-stan.org.

- Stržinar, G., and G. Skok, 2018: Comparison and optimization of radar-based hail detection algorithms in Slovenia. <em>Atmos. Res.</em>, **203**, 275–285, https://doi.org/10.1016/j.atmosres.2018.01.005.

- Taszarek, M., J. T. Allen, P. Groenemeijer, R. Edwards, H. E. Brooks, V. Chmielewski, and S.-E. Enno, 2020: Severe convective storms across Europe and the United States. Part I: Climatology of lightning, large hail, severe wind, and tornadoes. <em>J. Climate</em>, **33**, 10 239–10 261, https://doi.org/10.1175/JCLI-D-20-0345.1.

- Trapp, R. J., D. M. Wheatley, N. T. Atkins, R. W. Przybylinski, and R. Wolf, 2006: Buyer beware: Some words of caution on the use of severe wind reports in postevent assessment and research. <em>Wea. Forecasting</em>, **21**, 408–415, https://doi.org/10.1175/WAF925.1.

- Tuovinen, J.-P., A.-J. Punkka, J. Rauhala, H. Hohti, and D. M. Schultz, 2009: Climatology of severe hail in Finland: 1930–2006. <em>Mon. Wea. Rev.</em>, **137**, 2238–2249, https://doi.org/10.1175/2008MWR2707.1.

- Tuovinen, J.-P., J. Rauhala, and D. M. Schultz, 2015: Significant-hail-producing storms in Finland: Convective-storm environment and mode. <em>Wea. Forecasting</em>, **30**, 1064–1076, https://doi.org/10.1175/WAF-D-14-00159.1.

- Vakayil, A., and V. R. Joseph, 2022: Data twinning. <em>Stat. Anal. Data Min.</em>, **15**, 598–610, https://doi.org/10.1002/sam.11574.

- Vehtari, A., A. Gelman, and J. Gabry, 2017: Practical Bayesian model evaluation using leave-one-out cross-validation and WAIC. <em>Stat. Comput.</em>, **27**, 1413–1432, https://doi.org/10.1007/s11222-016-9696-4.

- Vehtari, A., A. Gelman, D. Simpson, B. Carpenter, and P.-C. Bürkner, 2021: Rank-normalization, folding, and localization: An improved R ^ for assessing convergence of MCMC. <em>Bayesian Anal.</em>, **16**, 695–702, https://doi.org/10.1214/20-BA1221.

- Vehtari, A., J. Gabry, M. Magnusson, Y. Yao, P.-C. Bürkner, T. Paananen, and A. Gelman, 2023: Efficient LOO-CV and WAIC for Bayesian models, version 2.6.0. R package, https://mc-stan.org/loo/reference/loo-package.html.

- Waldvogel, A., B. Federer, and P. Grimm, 1979: Criteria for the detection of hail cells. <em>J. Appl. Meteor.</em>, **18**, 1521–1525, https://doi.org/10.1175/1520-0450(1979)018<1521:CFTDOH&gt;2.0.CO;2.

- Warren, R. A., H. A. Ramsay, S. T. Siems, M. J. Manton, J. R. Peter, A. Protat, and A. Pillalamarri, 2020: Radar-based climatology of damaging hailstorms in Brisbane and Sydney, Australia. <em>Quart. J. Roy. Meteor. Soc.</em>, **146**, 505–530, https://doi.org/10.1002/qj.3693.

- Wendt, N. A., and I. L. Jirak, 2021: An hourly climatology of operational MRMS MESH-diagnosed severe and significant hail with comparisons to *storm data* hail reports. <em>Wea. Forecasting</em>, **36**, 645–659, https://doi.org/10.1175/WAF-D-20-0158.1.

- Wickham, H., and Coauthors, 2019: Welcome to the tidyverse. <em>J. Open Source Software</em>, **4**, 1686, https://doi.org/10.21105/joss.01686.

- Wilks, D. S., 2011: *Statistical Methods in the Atmospheric Sciences*. 3rd ed. Elsevier, 676 pp.

- Williams, E., and Coauthors, 1999: The behavior of total lightning activity in severe Florida thunderstorms. <em>Atmos. Res.</em>, **51**, 245–265, https://doi.org/10.1016/S0169-8095(99)00011-3.

- Wilson, C. J., K. Ortega, and V. Lakshmanan, 2009: Evaluating multi-radar, multi-sensor hail diagnosis with high resolution hail reports. *25th Conf. on Interactive Information Processing Systems*, Phoeniz, AZ, Amer. Meteor. Soc., P2.9, https://ams.confex.com/ams/pdfpapers/146206.pdf.

- Witt, A., M. D. Eilts, G. J. Stumpf, J. T. Johnson, E. D. W. Mitchell, and K. W. Thomas, 1998: An enhanced hail detection algorithm for the WSR-88D. <em>Wea. Forecasting</em>, **13**, 286–303, https://doi.org/10.1175/1520-0434(1998)013<0286:AEHDAF&gt;2.0.CO;2.

- Witt, A., D. W. Burgess, A. Seimon, J. T. Allen, J. C. Snyder, and H. B. Bluestein, 2018: Rapid-scan radar observations of an Oklahoma tornadic hailstorm producing giant hail. <em>Wea. Forecasting</em>, **33**, 1263–1282, https://doi.org/10.1175/WAF-D-18-0003.1.

- Yeo, I.-K., and R. A. Johnson, 2000: A new family of power transformations to improve normality or symmetry. <em>Biometrika</em>, **87**, 954–959, https://doi.org/10.1093/biomet/87.4.954.
