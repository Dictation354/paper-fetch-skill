---
title: "Assessing the impact of drought-land cover change on global vegetation greenness and productivity"
authors: "Jinlong Chen, Zhenfeng Shao, Xiao Huang, Qingwei Zhuang, Chaoya Dang, Bowen Cai, Xueke Zheng, Qing Ding"
doi: "10.1016/j.scitotenv.2022.158499"
source: "elsevier_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 11047
---

# Assessing the impact of drought-land cover change on global vegetation greenness and productivity

## Abstract

Drought–land cover change (D-LCC) is considered to be an important stress factor that affects vegetation greenness and productivity (VG&P) in global terrestrial ecosystems. Understanding the effects of D-LCC on VG&P benefits the development of terrestrial ecosystem models and the prediction of ecosystem evolution. However, till today, the mechanism remains underexploited. In this study, based on the Theil-Sen median estimator and Mann-Kendall test, Hurst exponent evaluation and rescaled range analysis (R/S), Pearson and Partial correlation coefficient analyses, we explore the spatiotemporal distribution characteristics and future trends of Leaf area index (LAI), Net primary productivity (NPP), Solar-induced chlorophyll fluorescence (SIF), Standardized precipitation evapotranspiration index (SPEI), Soil moisture (SM), Land cover type (LC), and the impact mechanism of D-LCC on global VG&P. Our results provide four major insights. First, three independent satellite observations consistently indicate that the world is experiencing an increasing trend of VG&P: LAI (17.69 %), NPP (20.32 %) and SIF (16.46 %). Nonetheless, productivity-reducing trends are unfolding in some tropical regions, notably the Amazon rainforest and the Congo basin. Second, from 2001 to 2020, the frequency, severity, duration, and scope of global droughts have been increasing. Third, the impact of land cover change on global VG&P is region-dependent. Finally, our results indicate that the continuous growth of VG&P in the global vegetation area is likely to become more difficult to maintain.

## Introduction

Since the 21st century, environmental changes caused by drought-land cover changes (D-LCC) pose enormous challenges to global terrestrial vegetation greenness and productivity (VG&P) (Radwan et al., 2021; Vicente-Serrano et al., 2013). The most significant productivity in terrestrial ecosystems is vegetation, which takes CO<sub>2</sub> from the atmosphere through photosynthesis and fixes it in soil and plants as biomass (Fatichi et al., 2019). Drought is one of the most prevalent stressors that affect vegetation ecosystem functions and carbon balance (Choat et al., 2018; Schwalm et al., 2017). Drought with a long duration can lead to long-term water deficit in vegetation (Jiang et al., 2022), weakened respiration and photosynthesis, increased mortality, and reduced VG&P (Choat et al., 2012). Many pieces of evidence have pointed to a global increase in the occurrence, intensity, and length of droughts (Chiang et al., 2021; Pokhrel et al., 2021; Schwalm et al., 2017). Severe drought will cause vegetation to brown and reduces the productivity capacity of terrestrial ecosystems (Gampe et al., 2021; Piao et al., 2020a), potentially directly transforming productivity into carbon sources (Doughty et al., 2015; Piao et al., 2019). Furthermore, global LCC is both the cause and consequence of global environmental change (Song et al., 2018), posing imminent challenges to the sustainability of terrestrial ecosystems and the global carbon cycle, especially at regional scales (Fang et al., 2021).

Investigating the changes of global VG&P with D-LCC benefits our understanding of the Earth as a gigantic system, sheds light on the feedback mode of the carbon cycle-drought-land cover change, and improves the carrying capacity of the global terrestrial ecosystem (Jiang et al., 2021; Schimel and Schneider, 2019). Despite that the impact of D-LCC on the VG&P of global terrestrial ecosystems has been widely studied, the response mechanism remains underexploited, mainly due to insufficient observational data (i.e., low density of meteorological stations) (Das et al., 2022). The limitations in the ground-based observation information make consistent global drought analysis challenging (Piao et al., 2020b). Scholars have attached increasing attention to the impact quantification of LCC on the global carbon cycle. Till now, however, a comprehensive understanding of the temporal and spatial trends in land cover types, including the magnitude, location, timing, and trends (decreases or increases) of LCC, is still lacking (Radwan et al., 2021). Such a knowledge gap brings difficulties to quantifying global LCCs across scales (Song et al., 2018), preventing us from obtaining the full picture of LCC interactions on VG&P.

Multi-sensor remote sensing observational technology enables the monitoring of drought-related variables from a climatological perspective (e.g., standardized precipitation evapotranspiration index; SPEI) (Li et al., 2021a), benefiting the assessment and quantification of drought impacts from an ecological perspective (e.g., soil moisture, SM) (Aghakouchak et al., 2015; Jiao et al., 2021). In addition, satellite-based monitoring is periodic, thus providing regular and synoptic views of the Earth's surface (Cai et al., 2021). This advantage allows us to gain a comprehensive understanding of global LCC and determine the impact of LCC on global VG&P (Schimel and Schneider, 2019). The changing global ecosystem diversity and complex carbon cycling mechanisms can be better understood via the top-down remote sensing biomass estimates (Stocker et al., 2019), through leaf area index (LAI), net primary productivity (NPP), solar-induced chlorophyll fluorescence (SIF), and other vegetation indices (Forzieri et al., 2018).

In this study, we present a global assessment of the synergistic D-LCC interactions on VG&P (0.05° spatial resolution) using six independent datasets, i.e., LAI, NPP, SIF, SPEI, SM, and LC. We hypothesize that both SPEI and SM increased contribute to the increase in vegetation greenness and productivity. If SPEI dominates global vegetation greenness and productivity, increased SPEI is expected to lead to more increase vegetation greenness and productivity, regardless of the effect of SM. If SM dominates global vegetation greenness and productivity, the increase in SM is expected to increase vegetation greenness and productivity, regardless of SPEI. The major contributions of this work include (1) analyzing the spatiotemporal distribution characteristics and change rules of LAI, NPP, SIF, SPEI, and SM at the global scale from 2001 to 2020; (2) documenting records of dynamic changes of eight land cover types at global and national scales from 2001 to 2020; (3) assessing the impact of D-LCC interactions on VG&P; (4) estimating future changes in global drought, vegetation greenness, and productivity.

## Materials and methods

### Datasets

We assess the synergistic D-LCC interactions on VG&P at the global scale using six different datasets. These datasets were uniformly resampled to a 0.05-degree latitude-longitude regular grid using bilinear interpolation, with temporal scale uniformed to years.

#### Leaf area index (LAI)

The leaf area index (LAI), one of the most striking features of the vegetation canopy (Dela Torre et al., 2021), denotes half of the total area of plant leaves per unit of land area (Liang et al., 2021). As an important indicator of vegetation growth and greenness in terrestrial ecosystems (Zhu et al., 2016), LAI plays an important role in the carbon cycle, climate model, terrestrial ecosystem simulation, and vegetation change monitoring (Fang et al., 2019). LAI data from the Global Land Surface Satellite (GLASS) product (http://glass.umd.edu/LAI/MODIS/0.05D/), with a spatial resolution of 0.05-degree and temporal resolution of 8 days (from 2000 to 2020), have been proven to be of higher quality compared to other LAI products and precision (Liang et al., 2021; Xiao et al., 2017).

#### Net primary productivity (NPP)

Net primary productivity (NPP) is defined as the amount of atmospheric carbon fixed in living plants per unit time per unit surface area (Gui et al., 2021; Zhao and Running, 2010; Zhuang et al., 2022a). As an important parameter of terrestrial productivity and net carbon storage, NPP is an important indicator for the global carbon cycle and for evaluating the sustainable development of terrestrial ecosystems (Xiao et al., 2019). The NPP product from GLASS was derived using an efficiency model (EC-LUE), considering long-term climate change (Zheng et al., 2020) (http://glass.umd.edu/NPP/MODIS/500m/). GLASS NPP products span from 2000 to 2020 with a spatial resolution of 500 m and temporal resolution of 8 days (annual products are also available).

#### Solar-induced chlorophyll fluorescence (SIF)

Solar-induced chlorophyll fluorescence (SIF) is an effective optical signal to quantify vegetation photosynthesis on varying spatial scales (Malenovský et al., 2021; Zhang et al., 2020), with significant spatiotemporal consistency between vegetation greenness and terrestrial ecosystem NPP on a global scale (Sun et al., 2017; Zhang et al., 2016). We choose SIF as a supplementary proxy for LAI and NPP (http://data.globalecology.unh.edu/data/GOSIF\_v2/) (Dang et al., 2022; Li and Xiao, 2019). The SIF products span from 2001 to 2020 with a spatial resolution of 0.05° and temporal resolution of 8 days (monthly and annual products are also available).

#### Standardized precipitation evapotranspiration index (SPEI)

Drought severity is quantified using the multiscalar standardized precipitation evapotranspiration index (SPEI) (Schwalm et al., 2017). SPEI also considers the influence of temperature and precipitation conditions on drought development and has a flexible temporal scale; therefore, it has been widely used in large-scale and long-term meteorological drought monitoring (Deng et al., 2021). SPEI on different temporal scales reflects the drought state of different temporal lengths. Short-term SPEI is suitable for monitoring drought formation, while long-term SPEI focuses on monitoring drought persistence (Zhai et al., 2020). In this study, we used the SPEI-annual (the SPEI-12 of December) to characterize interannual drought (Jiao et al., 2021). We reproduced the monthly SPEI global dataset using the SPEI package in the R software, with a 0.5° spatial resolution from 1901 to 2020 (Beguería et al., 2010; Vicente-Serrano et al., 2010). The input datasets to derive SPEI are monthly precipitation and potential evapotranspiration (derived from the website of the Climatic Research Unit (CRU) TS v4.05 (http://www.cru.uea.ac.uk/data/).

#### Soil moisture (SM)

Soil moisture (SM) is an important parameter for understanding the interactions and feedbacks of the atmosphere and the Earth's surface through the energy and water cycles and plays a key role in drought monitoring and prediction (Li et al., 2021b). SM variability and trends reduce the present land VG&P (Aghakouchak et al., 2015; Green et al., 2019). The SM products used in this study are from global land evaporation Amsterdam model v3.5a (GLEAM) root-zone soil moisture (SMroot) and surface soil moisture (SMsurf) (https://www.gleam.eu/). SM products span from 1980 to 2020, with a spatial resolution of 0.25° and temporal resolution of the day (Martens et al., 2017; Miralles et al., 2011).

#### Land cover type (LC)

Land cover type (LC) represents spatial information on different types of physical coverage of the Earth's surface, e.g., forests, grasslands, croplands, lakes, and wetlands (Li et al., 2022; Song et al., 2018). LC products are derived from MODIS-derived global land cover type products, i.e., MCD12C1 (Sulla-Menashe et al., 2019) (https://lpdaac.usgs.gov/products/mcd12c1v006/). The LC products used in this study are yearly products spanning from 2000 to 2020, with a spatial resolution of 0.05°.

### Methods

We used the Theil-Sen median estimator and Mann-Kendall test, Hurst exponent evaluation, rescaled range analysis (R/S), Pearson and Partial correlation coefficient to explore the spatiotemporal distribution characteristics of LAI, NPP, SIF, SPEI, SM, LC, and the impact mechanism of D-LCC on global VG&P. We also made predictions for the near future trends in global drought and VG&P.

#### Theil-Sen median estimator and Mann-Kendall test

In this study, the Theil-Sen median estimator trend analysis was coupled with the Mann-Kendall test to analyze the time series of LAI, NPP, and SIF. The Theil-Sen median estimator is a stable nonparametric statistical trend calculation method with high calculation efficiency. It is suitable for trend analysis of long-term series data and has been successfully applied in geospatial, meteorological, hydrological, and climate change-related studies (Feng et al., 2020; Fu et al., 2022; Hamed, 2008; Huang et al., 2019).

- (1) Theil-Sen median estimator:

(1)

$$
\beta = \mathit{Median}\left(\frac{x_{j} - x_{i}}{j - i} \right)\forall j > i
$$

where *i* and *j* are the ordinal time, *x*<sub>*i*</sub> and *x*<sub>*j*</sub> represent the grid unit values at times *i* and *j* (*j* &gt; *i*)*,* and *β* refers to the estimated median slope. When *β* &gt; 0, the time series presents an upward trend. On the contrary, when *β* < 0, the time series presents a downward trend.

- (2) Mann-Kendall trend test:

(2)

$$
{}S = \sum\limits_{i = 1}^{n - 1}\sum\limits_{j = i + 1}^{n}\mathit{sgn}\left({x_{j} - x_{i}} \right)
$$

(3)

$$
\begin{matrix} {\mathit{sgn}\left({x_{j} - x_{i}} \right) = \left\{\begin{matrix} {+ 1\hspace{2.5em}x_{j} - x_{i} > 0} \\ {\hspace{0.5em}0\hspace{3em}x_{j} - x_{i} = 0} \\ {- 1\hspace{2.5em}x_{j} - x_{i} < 0} \end{matrix} \right.} \end{matrix}
$$

(4)

$$
\begin{matrix} {Z = \left\{\begin{matrix} {\frac{S}{\sqrt{\mathit{Var}(S)}}\hspace{3.25em}\left({S > 0} \right)} \\ {\hspace{1.75em}0\hspace{5.25em}\left({S = 0} \right)} \\ {\frac{S}{\sqrt{\mathit{Var}(S)}}\hspace{3.5em}\left({S < 0} \right)} \end{matrix} \right.} \end{matrix}
$$

(5)

$$
\begin{matrix} {\mathit{Var}(S) = \frac{n\left({n - 1} \right)\left({2n + 5} \right) - \sum\limits_{m = 1}^{n}t_{m}\left({m - 1} \right)\left({2m + 5} \right)}{18}} \end{matrix}
$$

where *x*<sub>*i*</sub> and *x*<sub>*j*</sub> are the observations corresponding to the *i* and *j* of time series (*i* < *j*), *sgn*() represents the sign function, *Z* refers to standardized test statistics, *n* is the number of the time series (*n* &gt; 10), and *t*<sub>*m*</sub> refers to the range of any given tie *m*. The experimental results pass the bilateral significance test with a confidence level of 95 % (significance level, *α* = 0.05), when ∣*Z* ∣ ≥ 1.96 (or 2.32) represents the trend of the time series that passed the 95 % (or 99 %) confidence levels.

#### Hurst exponent evaluation and rescaled range analysis (R/S)

Hurst exponent reflects the autocorrelation, especially the persistence of long-term changes in time series data (Markonis and Koutsoyiannis, 2016). It has been widely used in climatological and ecological research (Jiang et al., 2017). We use rescaled range analysis (R/S) to establish the Hurst exponent. The processing workflow contains the following steps:

- (1) Dividing the long-term sequence (*x*<sub>1</sub>, *x*<sub>2</sub>…, *x*<sub>*n*</sub>) into *s* groups of length *r* non-overlapping subsequences (*x*<sub><em>i</em>1</sub>, *x*<sub><em>i</em>2</sub>…, *x*<sub>*ij*</sub>, *i* = 1, 2, 3, …, *s*, *j* = 1, 2, 3, …, *r*).
- (2) Defining the long-term memory of the time series mean ${\overline{x}}_{\mathit{ij}}$:

(6)

$$
\begin{matrix} {{\overline{x}}_{\mathit{ij}} = \frac{1}{r}\sum\limits_{j = 1}^{r}x_{\mathit{ij}}\hspace{2em}\left({{i = 1},2,3,\ldots,{s\hspace{0.5em}j = 1},2,3,\ldots,r} \right)} \end{matrix}\hspace{0.25em}
$$

- (3) Calculating the accumulated deviation of *z*<sub>*ij*</sub>:

(7)

$$
z_{\mathit{ij}} = \sum\limits_{k = 1}^{j}\left({x_{\mathit{ij}} - {\overline{x}}_{\mathit{ij}}} \right)\hspace{2em}\left({{i = 1},2,3,\ldots,{s\hspace{0.5em}j = 1},2,3,\ldots,r} \right)
$$

- (4) Defining the range sequence of *R*<sub>*i*</sub>:

(8)

$$
\begin{matrix} {R_{i} = \mathrm{m}\mathit{ax}\left(z_{\mathit{ij}} \right) - \mathit{min}\left(z_{\mathit{ij}} \right)\hspace{0.25em}\left({{i = 1},2,3,\ldots,s} \right)} \end{matrix}
$$

- (5) Defining the standard deviation sequence of *S*<sub>*i*</sub>:

(9)

$$
\begin{matrix} {S_{i} = \sqrt{\frac{1}{r - 1}\sum\limits_{j = 1}^{r}\left({x_{\mathit{ij}} - {\overline{x}}_{i}} \right)^{2}}\hspace{0.25em}\left({{i = 1},2,3,\ldots,s} \right)} \end{matrix}
$$

- (6) Calculating the rescaled range of *RS*:

(10)

$$
\begin{matrix} {\mathit{RS} = \frac{R_{i}}{S_{i}}\hspace{1.5em}\left({{i = 1},2,3,\ldots,s} \right)} \end{matrix}
$$

- (7) Obtaining the Hurst exponent (H) by fitting the following formula:

(11)

$$
\begin{matrix} {\mathit{log}\mathit{RS} = a + H \times \mathit{log}(n)} \end{matrix}
$$

where *H* is an indicator that measures time series correlation and trend strength (0 < *H* ≤ 1), and *a* is a constant. *H* = 0.5 indicates that the time series presents a random pattern; 0.5 < *H* ≤ 1 indicates the existence of long-term memory in the time series; 0 < *H* < 0.5 indicates that the time series exhibits anti-persistence (the lower the *H*, the greater the anti-persistence).

#### Pearson and partial correlation coefficient

The correlation coefficient expresses the degree of linear association between the variables under consideration (Zhuang et al., 2022b). We calculate the Pearson correlation coefficient at the pixel scale for each indicator:

(12)

$$
\begin{matrix} {R_{({x,y})} = \frac{\sum_{i = 1}^{n}\left({X_{i} - \overline{X}} \right)\left({Y_{i} - \overline{Y}} \right)}{\sqrt{\sum_{i = 1}^{n}\left({X_{i} - \overline{X}} \right)^{2}}\sqrt{\sum_{i = 1}^{n}\left({Y_{i} - \overline{Y}} \right)^{2}}}} \end{matrix}
$$

where *X*<sub>*i*</sub> and *Y*<sub>*i*</sub> refers to values of two indicators, $\overline{X}$ and $\overline{Y}$ refer to the mean of *X* and *Y*, respectively, and *R*<sub>(*x*,*y*)</sub> refers to the correlation coefficient. 0 < *R*<sub>(*x*,*y*)</sub> < 1 suggests that X and Y are positively correlated, while −1 < *R*<sub>(*x*,*y*)</sub> < 0 suggests that *X* and *Y* are negatively correlated. The significance test is performed at *p* < 0.05.

Further, to better understand the response mechanism of LAI, NPP, SIF to SPEI and SM, we also calculate the partial correlation coefficient at the pixel scale for each indicator. The partial correlation coefficient is used to analyze when SPEI and SM are both related to LAI, NPP, and SIF. The influence of one indicator is eliminated, with only the correlation between the other two variables analyzed:

(13)

$$
\begin{matrix} {R_{({i,j|h})} = \frac{R_{\mathit{ij}} - R_{\mathit{ih}}R_{\mathit{jh}}}{\sqrt{\left({1 - R_{\mathit{ih}}^{2}} \right)\left({1 - R_{\mathit{jh}}^{2}} \right)}}} \end{matrix}
$$

where *R*<sub>*ij*</sub> is the correlation coefficient between variables *x*<sub>*i*</sub> and *x*<sub>*j*</sub>, *R*<sub>*ih*</sub> is the correlation coefficient between variables *x*<sub>*i*</sub> and *x*<sub>*h*</sub>, *R*<sub>*jh*</sub> is the correlation coefficient between variables *x*<sub>*j*</sub> and *x*<sub>*h*</sub>, and *R*<sub>(*i*,*j*|*h*)</sub> is the partial correlation coefficient between *x*<sub>*i*</sub> and *x*<sub>*j*</sub> after excluding the influence of the variable *x*<sub>*h*</sub>.

#### Regression analysis

We quantify the elucidation of vegetation greenness and productivity response to SM and SPEI on an annual time scale via linear regression analysis. Before performing the linear regression calculation, we performed max-min normalization on LAI, SM and SPEI to eliminate the dimensional influence between different data products. The linear regression follows:

(14)

$$
\begin{matrix} {Y_{\mathit{LAI}} = a \times X_{\mathit{SM}} + b \times X_{\mathit{SPEI}} + c} \end{matrix}
$$

where *X*<sub>SM</sub> is the normalized SM value, *X*<sub>SPEI</sub> is the normalized precipitation value, *Y*<sub>LAI</sub> is the normalized LAI value, *a* is the regression coefficient of *X*<sub>SM</sub>, *b* is the regression coefficient of *X*<sub>SPEI</sub>, and *c* is the constant of the regression equation.

## Results

### Global spatiotemporal trends of LAI, NPP, and SIF

In this study, we perform a long-term spatiotemporal analysis of global LAI, NPP, and SIF from 2001 to 2020. As a complimentary proxy to LAI and NPP, SIF has similar spatiotemporal trends to LAI and NPP (Fig. S1). Our results suggest that global LAI, NPP, and SIF have significant changes in recent decades (Fig. 1a, b, c), accounting for about 19.67 % (LAI), 24.62 % (NPP), and 18.37 % (SIF) of the land area, respectively (Fig. 1d). We notice a persistent and widespread improvement of LAI (greening) in about 17.69 % of the global land area, whereas <2 % of the globe shows LAI degradation (i.e., browning). Furthermore, since 2001, regions with increased NPP account for about 20.32 % of the total land area, while regions with reduced NPP account for 4.29 %. SIF is strongly correlated with terrestrial photosynthesis (Li et al., 2018), with about 16.46 % of the land presenting an increasing trend in SIF and about 1.91 % presenting a decreasing trend in SIF.

![Figure 1](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr1_lrg.jpg?httpAccept=%2A%2F%2A)

Global spatiotemporal trends of global leaf area index (LAI), net primary productivity (NPP), and solar-induced chlorophyll fluorescence (SIF). The overall trend is classified into five types, i.e., significant increase (*P* < 0.01), increase (*P* < 0.05), stable or non-vegetated, decrease (*P* < 0.05), and significant decrease (*P* < 0.01). The trend of the time series passes the 99 % or 95 % confidence levels, respectively. (a) The spatiotemporal trend distribution of LAI using the Theil-Sen median estimator and Mann-Kendall test; (b) The spatiotemporal trend distribution of NPP; (c) the spatiotemporal trend distribution of SIF; (d) Distribution of the relative percentage of decreases and increases in LAI, NPP, and SIF.

From 2001 to 2020, the global vegetation area has shown a significant increase in greening and productivity (Fig. 1a, b, c; LAI, NPP, and SIF as proxy), with Russian (LAI, 22.26 %; NPP, 26.93 %; SIF, 19.89 %), Canada (LAI, 6.68 %; NPP, 11.43 %; SIF,7.11 %), China (LAI, 11.50 %; NPP, 12.86 %; SIF, 12.25 %), America (LAI, 6.91 %; NPP, 7.89 %; SIF, 6.91 %), Brazil (LAI, 6.12 %; NPP, 2.10 %; SIF, 6.31 %), India (LAI, 5.40 %; NPP, 4.82 %; SIF,4.89 %), Indonesia (LAI, 1.20 %; NPP, 1.23 %; SIF,1.93 %), and other intensive farming or policy-driven afforestation countries particularly evident (Fig. 1a, b, c). The above statistics denote the contribution ratio of global vegetation greening and productivity growth at the national scale. Note that we omit some countries with small land areas. The contribution of all countries to global vegetation greening and productivity growth can be found in Table S1. In Russia, significant vegetation greening and 26.93 % productivity growth occurred in 28.89 % of Russia's land (mainly in the east). In China, 45.35 % of its land experienced significant vegetation greening and 58.28 % productivity growth (mainly in China's northern and southern regions); In the United States, 23.82 % of its land experienced significant vegetation greening and 31.26 % productivity growth (mainly in the western region). In India, 75.18 % of its land experienced significant vegetation greening and 77.21 % productivity growth (covering the entire of India (Fig. 1a, b, c). However, we also observe a decreasing trend of NPP in Congo (Kinshasa) (66.36 %), Peru (41.90 %), Colombia (40.18 %), Brazil (29.33 %), and Kazakhstan (16.16 %), among others. The potential drivers could be forest degradation due to environmental change (e.g., drought, wildfire, insect infestation, etc.) (Doughty et al., 2015; Stocker et al., 2019), and human activities (e.g., forestry management, expansion of the agricultural frontier, commodity-driven deforestation, etc.) (Al-Hanbali et al., 2022; Gatti et al., 2021).

### Spatiotemporal trends of SPEI, SM, and LC

From 2001 to 2020, areas with increased SPEI accounted for 7.38 % of the global land, while areas with decreased SPEI accounted for 11.49 % (Fig. 2d), coinciding with the patterns revealed via simulated data (Fig. 2c). It is necessary to consider the limitation of SM in analyzing the spatiotemporal changes of VG&P, especially in drought-related assessments (Stocker et al., 2018), as SM presents a strong influence on plant physiology. We notice that SPEI and SM have strong consistency in spatiotemporal distribution characteristics (Fig. 2). In the past two decades, areas where SM increased (9.06 %) were slightly larger than areas where SM decreased (7.50 %) (Fig. 2d). We observe a notable increasing trend of SPEI and SM in the northern hemisphere, mainly in the northeastern region of China, the southern part of the United States, northern India and some African countries, while the decreasing trends in the eastern part of Russia, the central region of Brazil, and Canada the eastern region of Germany, Ukraine, and some countries in central and southern Africa (Fig. 2a, b). The above patterns are considerably consistent with the spatiotemporal distributions of LAI, NPP, and SIF (see Fig. S2 in Supplementary material).

![Figure 2](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr2_lrg.jpg?httpAccept=%2A%2F%2A)

Global spatiotemporal trends of root-zone soil moisture (SMroot), surface soil moisture (SMsurf), and standardized precipitation evapotranspiration index (SPEI). The overall trend is classified into five types, i.e., significant increase (*P* < 0.01), increase (*P* < 0.05), stable or insufficient data, decrease (*P* < 0.05), and significant decrease (*P* < 0.01). The trend of the time series passes the 99 % or 95 % confidence levels, respectively. (a) The spatiotemporal trend distribution of SMroot using Theil-Sen median and Mann-Kendall; (b) The spatiotemporal trend distribution of SMsurf; (c) The spatiotemporal trend distribution of SPEI; (d) The distribution of the relative percentage of decreases and increases in SMroot, SMsurf, and SPEI.

In this study, we reveal the spatiotemporal trends of LCC at global and national scales from 2001 to 2020 (Fig. 3 ). From 2001 to 2020, the worldwide LCC rate reached 4.29 %, induced by natural or anthropogenic drivers. LCC varies at the national scale: Russia (20.86 %), Canada (13.71 %), China (8.12 %), America (7.04 %), Brazil (4.71 %), and India (2.74 %) contributed a higher proportion of the global LCC (Fig. 3a,b,c; Table S2). To clearly assess the impact of LCC on VG&P, we perform attribute extraction and reclassification according to MCD12Q1 International Geosphere-Biosphere Programmer (IGBP) classification descriptions (Sulla-Menashe et al., 2019) and generate global land cover data with eight major categories (Table S3), which are used to analyze the effects of urbanization, deforestation, agricultural land expansion, conversion of farmland to forest, afforestation, and intensive farming on VG&P (Curtis et al., 2018). Forests around the world are in a state of constant change. Studies have shown that, compared with 2001, forest coverage has lost about 2.43 %, and the area of shrublands and savannas increased by 1.16 % in 2020. Due to effective development and utilization and functional improvement, the global bare land area decreased by 2.78 % during the investigated period (Fig. 3d). We observe urban expansion as the end of the LCC (Shao et al., 2021), presumably due to the direct transformation of forests, shrublands and savannas or barren areas, also possibly due to the indirect transformation of these land cover types through croplands (Radwan et al., 2021). Through the temporal trends of the eight global land cover types (Fig. 3d), we notice that the area of urban and built-up lands increased by 13.42 %, mainly due to the transformation of shrublands and savannas (50.37 %) and croplands (42.46 %) (Fig. 4a). The shrublands and savannas showed an obvious increasing trend (34.25 %), while the forests (22.50 %) and barren areas (22.81 %) showed a significant decreasing trend. The changes in these three land cover types accounted for 80.96 % of the total change area of the global LCC (Fig. 4a). The area of global forest, permanent wetlands, snow and ice, and barren areas showed a decreasing trend, and the ratios of net change and gross loss reached 22.22 %, 34.20 %, 37.77 %, and 53.63 %, respectively. The area of global water bodies, shrublands and savannas, croplands, and urban and built-up lands showed an increasing trend, and the ratios of net change and gross gain reached 20.19 %, 19.44 %, 17.81 %, and 83.73 %, respectively (Fig. 4b). These results suggest that urbanization, deforestation, agricultural land expansion, conversion of farmland to forests, afforestation, and intensive farming are constantly changing the global LCC patterns, which in turn affects the VG&P of terrestrial ecosystems.

![Figure 3](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr3_lrg.jpg?httpAccept=%2A%2F%2A)

Global spatiotemporal trends of global land cover changes (LCC), consisting of water bodies, forests, shrublands and savannas, permanent wetlands, croplands, urban and built-up lands, snow and ice, and barren areas. (a) Global distribution map of eight major land cover types in 2001; (b) Global distribution map of eight major land cover types in 2020; (c) Changes in land cover types at the national scale from 2001 to 2020, where LCC represents the land cover type change rate, and the size of the circle represents the number of land type change pixels at the national scale; (d) Dynamics of the pixel-wise changes amount in global land type from 2001 to 2020.

![Figure 4](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr4_lrg.jpg?httpAccept=%2A%2F%2A)

Global land cover type transitions from 2001 to 2020. (a) Global land cover type transfer diagram; (b) The number of global gross gains, gross losses, and net changes pixels for different land cover types from 2001 to 2020 (error bars represent 10 % error values).

### Quantifying of VG&P response to SM and SPEI

We quantify the elucidation of VG&P response to SM and SPEI on an annual time scale via linear regression analysis. The experimental results show that LAI, NPP, and SIF present highly consistent response mechanisms to SPEI and SM. SM, SPEI, and VG&P show a high linear correlation (Fig. 5a, c). Both climate drought (SPEI) and soil drought (SM) have different degrees of impact on VG&P, while the weight of soil drought on VG&P is more prominent than that of climate drought on VG&P (Fig. 5b, d). The SM regression coefficient shows a relatively stable positive trend between 60°N and 50°S latitude (Fig. 5b), while SPEI regression coefficient shows relatively strong positive and negative fluctuations between 80°N and 60°S latitude (Fig. 5d). These results further point out that the impact of soil drought (lower SM) on VG&P is rather direct compared with the impact of meteorological drought on VG&P.

![Figure 5](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr5_lrg.jpg?httpAccept=%2A%2F%2A)

Linear regression analysis with soil moisture (SM) and solar-induced chlorophyll fluorescence (SIF) as independent variables and leaf area index (LAI) as the dependent variable. (a) Spatial distribution of regression coefficients of SM; (b) The regression coefficient of SM arranges the curve by latitude (red shading is the standard deviation). (c) Spatial distribution of regression coefficients of SM; (d) The regression coefficient of SM arranges the curve by latitude (red shading is the standard deviation).

### Estimating future changes in global drought and VG&P

In this study, we use Hurst exponent evaluation and rescaled range analysis, combined with Theil-Sen median estimator and Mann-Kendall test, to perform pixel-wise persistence predictions for six indicators, i.e., LAI, NPP, SIF, SMroot, SMsurf, and SPEI (Figs. 6, 7). We observe that LAI, NPP, and SIF are consistent in terms of indicating the future development and change of VG&P (Fig. 6a, b, c). Specifically, about two-fifths of the previously stable vegetation areas are expected to change in the future (SC), and about one-fifth of previously stable vegetated areas are expected to continue their stable trend (SS); A small percentage (about 3 %) of areas are expected to experience reduced VG&P, mainly in the Amazon rainforest and Congo basin; The VG&P of a very small percentage of areas (about 2 %) is likely to rebound, i.e., VG&P decreased in the past and is expected to increase in the future. Notably, the vegetation area that presents increased VG&P will no longer continue to grow and is expected to decrease in the future. The vegetation area that maintains the continuous increase of VG&P only accounts for about one-seventh of the global vegetation area.

![Figure 6](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr6_lrg.jpg?httpAccept=%2A%2F%2A)

Estimating future changes in global vegetation greenness and productivity (VG&P) based on observed leaf area index (LAI), net primary productivity (NPP), and solar-induced chlorophyll fluorescence (SIF) indicators from 2001 to 2020. the overall trend of future changes is classified into six types: stable in the past and expected to change in the future (SC), stable in the past and remains stable in the future (SS), decreased in the past and is likely to increase in the future (DI), decreased in the past and remains decreasing in the future (DD), increased in the past but transitions to decrease in the future (ID), increased in the past and will increase in the future (II). (a) Predicted LAI spatiotemporal trends; (b) Predicted NPP spatiotemporal trends; (c) Predicted SIF spatiotemporal trends; (d) The proportion of six types of trends in LAI, NPP, and SIF. For LAI, NPP and SIF, the proportions of the future six types of changes are: LAI (SC: 38.97 %, SS: 23.61 %; DI: 1.28 %, DD: 2.41 %, ID: 16.83 %, II 16.90 %), NPP (SC: 37.46 %, SS: 20.34 %, DI: 2.51 %, DD: 4.85 %, ID: 21.88 %, II: 12.96 %), and SIF (SC: 41.65 %, SS: 23.71 %, DI: 1.90 %, DD: 1.70 %, ID: 19.70 %, II: 11.34 %).

By estimating future changes in global drought based on observed SM and SPEI indicators from 2001 to 2020, we derive the spatiotemporal distribution characteristics of six types of trends (Fig. 7a, b, c). The results suggest that in the future, nearly 40 % of the land SM and SPEI will no longer maintain a relatively stable state; 30 % of the land will continue to maintain a stable state. These two types of changing trends cover 70 % of the global land (Fig. 7d).

![Figure 7](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr7_lrg.jpg?httpAccept=%2A%2F%2A)

Estimating future changes in global drought based on observed root-zone soil moisture (SMroot), surface soil moisture (SMsurf), and standardized precipitation evapotranspiration index (SPEI) indicators from 2001 to 2020. The overall trend of future changes is classified into six types: SC, SS, DI, DD, ID, and II. (a) Predicted future trends of SMroot; (b) Predicted future trends of SMsurf; (c) Predicted trends of SPEI; (d) The proportion of six types of trends in SMroot, SMsurf, and SPEI. SMroot (SC: 40.86 %, SS: 32.88 %; DI: 5.48 %, DD: 6.30 %, ID: 6.25 %, II 8.22 %), SMsurf (SC: 45.97 %, SS: 30.43 %, DI: 5.84 %, DD: 4.96 %, ID: 6.49 %, II: 6.30 %), and SPEI (SC: 39.59 %, SS: 33.92 %, DI: 7.53 %, DD: 8.60 %, ID: 5.53 %, II: 4.83 %).

## Discussion

Our results point to a significant VG&P growth trend, which is consistent with existing findings (Forzieri et al., 2018; Zhu et al., 2016). Nonetheless, the vegetation browning and NPP reduction trends in some tropical regions deserve our attention. Recent studies have shown that, due to factors such as climate change, natural disaster events, and deforestation (Curtis et al., 2018), ecosystem pressures in the Amazon have increased with carbon accumulation on a long-term downward trend (Achard et al., 2002; Gatti et al., 2021). Our study provides direct evidence for the long-term decline of productivity in tropical rainforests, as we observe that more than three-quarters of the Amazon region showed a significant decline in productivity during the investigated period. In addition, we also observe that the tropical rainforest in the Congo Basin, the second-largest tropical rainforest in the world after the Amazon rainforest, is undergoing drastic changes, as more than three-quarters of the tropical rainforest in the Congo Basin are showing a significant downward trend in productivity.

Our results suggest significant SPEI and SM changes in about one-sixth of global land (Fig. 2a, b, c). We define meteorological drought as SPEI ≤ −1 and divide SPEI into four different types, i.e., extremely dry (SPEI ≤ −2), severely dry (−2 < SPEI ≤ −1.5), moderately dry (−1.5 < SPEI ≤ −1), near normal conditions (−1 < SPEI < +1), and wet (SPEI ≥ 2). Compared with 2001, the global land area with meteorological drought increased by 67.92 %, and the proportion of extremely dry and severely dry increased by 158.08 %. We found that meteorological drought represented by SPEI is more sensitive to monitoring vegetation productivity trends (Schwalm et al., 2017), especially for the Amazon rainforest, Germany, and Ukraine, where notable downward trends of productivity occurred (Fig. 1b, Fig. 2c). SM is an important factor in global vegetation primary production and interannual carbon cycle changes (Stocker et al., 2019), and SM deficiency has a direct impact on vegetation (Liu et al., 2020). The results of this study show that SM has a strong correlation with LAI, NPP, and SIF (Fig. 8 ). Overall, the global soil moisture in 2020 decreased by 2.50 % compared with 2000, which is consistent with the current study (Dang et al., 2022). Changes in vegetation structure under drought stress may lead to the reduction of leaf area and leaf abscission, which are usually inferred based on LAI; The impact of drought on terrestrial productivity is reflected through NPP, while SIF is used to assist in verifying the impact of drought on VG&P. LAI, NPP, and SIF have highly consistent response mechanisms to drought (Figs. 8 and S2).

![Figure 8](https://api.elsevier.com/content/object/eid/1-s2.0-S004896972205598X-gr8_lrg.jpg?httpAccept=%2A%2F%2A)

Distribution of partial correlation coefficients between leaf area index (LAI), net primary productivity (NPP), solar-induced chlorophyll fluorescence (SIF), on soil moisture (SM) after excluding the influence of standardized precipitation evapotranspiration index (SPEI). (a) Distribution of partial correlation coefficients between LAI and SM after excluding the influence of SPEI, R (LAI, SM|SPEI); (b) Distribution of partial correlation coefficients between NPP and SM after excluding the influence of SPEI, R (NPP, SM|SPEI); (c) Distribution of partial correlation coefficients between SIF and SM after excluding the influence of SPEI, R (SIF, SM|SPEI); (d); Combination plots of Box-whisker and violin representing R(LAI, SM|SPEI), R (NPP, SM|SPEI) and R (SIF, SM|SPEI) data distributions, with boxes representing quartiles, circles representing the median, and whisker representing the range of maximum and minimum values.

From 2001 to 2020, the global vegetation area has shown notable increases in greening and productivity (LAI, NPP, and SIF as proxy), especially evident in areas of intensive farming or policy-driven afforestation such as Russia, Canada, China, America, Brazil, India, Indonesia, and Turkey, to list a few (Fig. 1a, b, c). Our study confirms the effectiveness of China's large-scale afforestation policy, especially in the southern and northern regions of China. Policy-driven LCCs, such as returning farmland to forests and afforestation, have greatly improved VG&P capacity, making the southern and northern regions of China one of the regions with the densest vegetation greenness and NPP around the world, suggesting that policy-driven afforestation is a possible solution to boost vegetation cover and enhance carbon storage (Piao et al., 2020a). At the global and national scales, LCC improves the global vegetation coverage by increasing the vegetation area as well as the productivity capacity per unit area of vegetation through policy-driven afforestation and reasonable intervention in forest areas, thereby maximizing the increasing vegetation cover and enhancing carbon storage.

Globally, the gains and losses of forests, shrublands and savannas, croplands, and barren areas are synchronized, with 95 % of the global net forest loss attributed to environmental changes (e.g., drought, wildfires, pests, etc.) and human activities (e.g., forestry management, deforestation caused by the expansion of agricultural frontiers, commodity-driven deforestation, etc.). The drivers of forest loss vary by region, with environmental change being the main disturbance factor in temperate and boreal forests. In the tropics, human activities become the most important factor (Curtis et al., 2018). We notice that the global cropland areas show a balance of complements. Despite the land transfer for urban and built-up lands, the transfer of shrublands and savannas has been compensated accordingly, suggesting that bare land has been effectively utilized with improved functionality in the past two decades. The area of land converted from barren areas to shrublands and savannas is more than three times than that converted from shrublands and savannas to barren areas (Fig. 4b), indicating that land desertification can be slowed down through correct and effective human intervention and, to some extent, the long-term land degradation caused by climate change can be compensated.

Therefore, we cannot pin our hopes on achieving carbon neutrality entirely on unrestricted VG&P growth in the global vegetated area, as half of the areas with significant VG&P growth are expected to show a decreasing trend in the near future. It is foreseeable that the continuous growth of VG&P in the global vegetation area will become more and more difficult to maintain, presumably due to a variety of reasons that include climate, temperature, soil conditions, and nutrients (e.g., nitrogen, phosphorus, and potassium) that limit the growth of vegetation (Wang et al., 2020). The results suggest that the Amazon rainforest and the Congo Basin will continue to present a downward trend in NPP (Fig. 6b), which deserves more attention in the future. At last, due to the errors and limitations of observations in remote sensing datasets, there are obvious data fluctuations in high latitudes, such as north of 60°N and south of 30°S. For the multiple linear regression analysis, only the scenarios where the effects of SM and SPEI on the vegetation greenness and productivity are linearly correlated are considered, and the nonlinear correlation scenarios are not considered sufficiently (Liu et al., 2020), which should be improved in future research.

## Conclusions

In this study, we explored the spatiotemporal distribution characteristics of LAI, NPP, SIF, SPEI, SM, LC and the impact mechanism of D-LCC on global VG&P using six global-scale datasets. The results of this study provide four valuable insights into the synergistic D-LCC interactions on VG&P. First, three independent satellite observations consistently indicate that the world is showing an increasing trend of VG&P: LAI (17.69 %), NPP (20.32 %) and SIF (16.46 %). Nonetheless, productivity-reducing trends are unfolding in some tropical regions, notably the Amazon rainforest and the Congo basin. Second, from 2001 to 2020, the frequency, severity, duration, and scope of global droughts have seen an increasing trend. LAI, NPP, and SIF present highly consistent response mechanisms to SPEI and SM. The coverage of shrublands and savannas showed a notable increasing trend (34.25 %); On the contrary, the forests (22.50 %) and barren areas (22.81 %) showed a significant decreasing trend. The changes in these three land cover types accounted for 80.96 % of the total change area of the global LCC. (3) From 2001 to 2020, Russia, Canada, China, America, Brazil, India, Indonesia, and Turkey, among others, with intensive farming or afforestation, presented a significant increase in VG&P. Policy-driven LCCs, such as reforestation and afforestation, have made southern and northern China one of the regions with the densest VG&P in the world. (4) It is foreseeable that the continuous growth of VG&P in the global vegetation area is likely to become more difficult to maintain, and the regeneration of natural forests may be an important strategy to capture additional carbon emissions.

## Author contributions

All authors contributed to the manuscript writing. Jinlong Chen and Zhenfeng Shao initially designed the experiment and writing-original draft preparation. Xiao Huang helped with writing-original the draft preparation and evaluating the results. Xueke Zheng implemented the analysis and visualization preparation. Qingwei Zhuang, Chaoya Dang, Bowen Cai and Qing Ding provided suggestions for improvement of the experimental design and analysis.

## Funding information

This work was supported by the National Natural Science Foundation of China (42090012), in part by Guangxi Science and Technology Program (GuiKe 2021AB30019), 03 special research and 5G project of Jiangxi Province in China (20212ABC03A09), Zhuhai Industry University Research Cooperation Project of China (ZH22017001210098PWC), Sichuan Science and Technology Program (2022YFN0031) and Zhizhuo Research Fund on Spatial-Temporal Artificial Intelligence (ZZJJ202202).

## Acknowledgements

Thanks sincerely to Wenping Yuan, Liang Shunlin, Jingfeng Xiao, Xing Li, Mengxia Li, Ian Harris, Santiago Beguería, D. G. Miralles and Damien Sulla-Menashe for their help with this paper.

## Data availability

All other data supporting the findings of this study are freely available from the following locations: GLASS LAI product, http://glass.umd.edu/LAI/MODIS/0.05D/; GLASS NPP products, http://www.glass.umd.edu/NPP/MODIS/500m/; GOSIF products, http://data.globalecology.unh.edu/data/GOSIF\_v2/; Global SPEI database, https://spei.csic.es/database.html; CRU TS v4.05 products, http://www.cru.uea.ac.uk/data/; GLEAM SM database, https://www.gleam.eu/; Land Cover Type products, https://lpdaac.usgs.gov/products/mcd12c1v006/.

## References (67 total, showing 67)

1. F. Achard, H.D. Eva, H.J. Stibig, P. Mayaux, J. Gallego, T. Richards, J.P. Malingreau. 2002. Determination of deforestation rates of the world’s humid tropical forests. Science (80-. ), 297: 999-1002. 10.1126/science.1070656 [Achard et al., 2002]

2. A. Aghakouchak, A. Farahmand, F.S. Melton, J. Teixeira, M.C. Anderson, B.D. Wardlow, C.R. Hain. 2015. Reviews of geophysics remote sensing of drought: Progress, challenges. Rev. Geophys., 53: 1-29. 10.1002/2014rg000456.received [Aghakouchak et al., 2015]

3. A. Al-Hanbali, K. Shibuta, B. Alsaaideh, Y. Tawara. 2022. Analysis of the land suitability for paddy fields in Tanzania using a GIS-based analytical hierarchy process. Geo-Spatial Inf. Sci., 25: 212-228. 10.1080/10095020.2021.2004079 [Al-Hanbali et al., 2022]

4. S. Beguería, S.M. Vicente-Serrano, M. Angulo-Martínez. 2010. A multiscalar global drought dataset: the SPEI base: a new gridded product for the analysis of drought variability and impacts. Bull. Am. Meteorol. Soc., 91: 1351-1356. 10.1175/2010bams2988.1 [Beguería et al., 2010]

5. B. Cai, Z. Shao, S. Fang, X. Huang, M.E. Huq, Y. Tang, Y. Li, Q. Zhuang. 2021. Finer-scale spatiotemporal coupling coordination model between socioeconomic activity and eco-environment: a case study of Beijing, China. Ecol. Indic., 131: 108165. 10.1016/j.ecolind.2021.108165 [Cai et al., 2021]

6. F. Chiang, O. Mazdiyasni, A. AghaKouchak. 2021. Evidence of anthropogenic impacts on global drought frequency, duration, and intensity. Nat. Commun., 12: 1-10. 10.1038/s41467-021-22314-w [Chiang et al., 2021]

7. B. Choat, S. Jansen, T.J. Brodribb, H. Cochard, S. Delzon, R. Bhaskar, S.J. Bucci, T.S. Feild, S.M. Gleason, U.G. Hacke, A.L. Jacobsen, F. Lens, H. Maherali, J. Martínez-Vilalta, S. Mayr, M. Mencuccini, P.J. Mitchell, A. Nardini, J. Pittermann, R.B. Pratt, J.S. Sperry, M. Westoby, I.J. Wright, A.E. Zanne. 2012. Global convergence in the vulnerability of forests to drought. Nature, 491: 752-755. 10.1038/nature11688 [Choat et al., 2012]

8. B. Choat, T.J. Brodribb, C.R. Brodersen, R.A. Duursma, R. López, B.E. Medlyn. 2018. Triggers of tree mortality under drought. Nature, 558: 531-539. 10.1038/s41586-018-0240-x [Choat et al., 2018]

9. P.G. Curtis, C.M. Slay, N.L. Harris, A. Tyukavina, M.C. Hansen. 2018. Classifying drivers of global forest loss. Science (80-. ), 361: 1108-1111. 10.1126/science.aau3445 [Curtis et al., 2018]

10. C. Dang, Z. Shao, X. Huang, J. Qian, G. Cheng, Q. Ding, Y. Fan. 2022. Assessment of the importance of increasing temperature and decreasing soil moisture on global ecosystem productivity using solar-induced chlorophyll fluorescence. Glob. Chang. Biol., 28: 2066-2080. 10.1111/gcb.16043 [Dang et al., 2022]

11. P. Das, Z. Zhang, H. Ren. 2022. Evaluating the accuracy of two satellite-based quantitative precipitation estimation products and their application for meteorological drought monitoring over the Lake Victoria Basin, East Africa. Geo-Spatial Inf. Sci., 00: 1-19. 10.1080/10095020.2022.2054731 [Das et al., 2022]

12. D.M.G. Dela Torre, J. Gao, C. Macinnis-Ng. 2021. Remote sensing-based estimation of rice yields using various models: a critical review. Geo-Spatial Inf. Sci., 24: 580-603. 10.1080/10095020.2021.1936656 [Dela Torre et al., 2021]

13. Y. Deng, X. Wang, K. Wang, P. Ciais, S. Tang, L. Jin, L. Li, S. Piao. 2021. Responses of vegetation greenness and carbon cycle to extreme droughts in China. Agric. For. Meteorol., 298–299: 108307. 10.1016/j.agrformet.2020.108307 [Deng et al., 2021]

14. C.E. Doughty, D.B. Metcalfe, C.A.J. Girardin, F.F. Amézquita, D.G. Cabrera, W.H. Huasco, J.E. Silva-Espejo, A. Araujo-Murakami, M.C. Da Costa, W. Rocha, T.R. Feldpausch, A.L.M. Mendoza, A.C.L. Da Costa, P. Meir, O.L. Phillips, Y. Malhi. 2015. Drought impact on forest carbon dynamics and fluxes in Amazonia. Nature, 519: 78-82. 10.1038/nature14213 [Doughty et al., 2015]

15. H. Fang, F. Baret, S. Plummer, G. Schaepman-Strub. 2019. An overview of global leaf area index (LAI): methods, products, validation, and applications. Rev. Geophys., 57: 739-799. 10.1029/2018rg000608 [Fang et al., 2019]

16. L. Fang, Lunche Wang, W. Chen, J. Sun, Q. Cao, S. Wang, Lizhe Wang. 2021. Identifying the impacts of natural and human factors on ecosystem service in the Yangtze and Yellow River basins. J. Clean. Prod., 314: 127995. 10.1016/j.jclepro.2021.127995 [Fang et al., 2021]

17. S. Fatichi, C. Pappas, J. Zscheischler, S. Leuzinger. 2019. Modelling carbon sources and sinks in terrestrial vegetation. New Phytol., 221: 652-668. 10.1111/nph.15451 [Fatichi et al., 2019]

18. W. Feng, H. Lu, T. Yao, Q. Yu. 2020. Drought characteristics and its elevation dependence in the Qinghai-Tibet plateau during the last half-century. Sci. Rep., 10: 1-11. 10.1038/s41598-020-71295-1 [Feng et al., 2020]

19. G. Forzieri, R. Alkama, D.G. Miralles, A. Cescatti. 2018. Response to comment on “Satellites reveal contrasting responses of regional climate to the widespread greening of Earth”. Science (80-. ), 360: 1180-1184. 10.1126/science.aap9664 [Forzieri et al., 2018]

20. J. Fu, Y. Gong, W. Zheng, J. Zou, M. Zhang, Z. Zhang, J. Qin, J. Liu, B. Quan. 2022. Spatial-temporal variations of terrestrial evapotranspiration across China from 2000 to 2019. Sci. Total Environ., 825: 153951. 10.1016/j.scitotenv.2022.153951 [Fu et al., 2022]

21. D. Gampe, J. Zscheischler, M. Reichstein, M. O’Sullivan, W.K. Smith, S. Sitch, W. Buermann. 2021. Increasing impact of warm droughts on northern ecosystem productivity over recent decades. Nat. Clim. Chang., 11: 772-779. 10.1038/s41558-021-01112-8 [Gampe et al., 2021]

22. L.V. Gatti, L.S. Basso, J.B. Miller, M. Gloor, L. Gatti Domingues, H.L.G. Cassol, G. Tejada, L.E.O.C. Aragão, C. Nobre, W. Peters, L. Marani, E. Arai, A.H. Sanches, S.M. Corrêa, L. Anderson, C. Von Randow, C.S.C. Correia, S.P. Crispim, R.A.L. Neves. 2021. Amazonia as a carbon source linked to deforestation and climate change. Nature, 595: 388-393. 10.1038/s41586-021-03629-6 [Gatti et al., 2021]

23. J.K. Green, S.I. Seneviratne, A.M. Berg, K.L. Findell, S. Hagemann, D.M. Lawrence, P. Gentine. 2019. Large influence of soil moisture on long-term terrestrial carbon uptake. Nature, 565: 476-479. 10.1038/s41586-018-0848-x [Green et al., 2019]

24. X. Gui, L. Wang, X. Su, X. Yi, X. Chen, R. Yao, S. Wang. 2021. Environmental factors modulate the diffuse fertilization effect on gross primary productivity across chinese ecosystems. Sci. Total Environ., 793: 148443. 10.1016/j.scitotenv.2021.148443 [Gui et al., 2021]

25. K.H. Hamed. 2008. Trend detection in hydrologic data: the mann-kendall trend test under the scaling hypothesis. J. Hydrol., 349: 350-363. 10.1016/j.jhydrol.2007.11.009 [Hamed, 2008]

26. X. Huang, C. Wang, J. Lu. 2019. Understanding the spatiotemporal development of human settlement in hurricane-prone areas on the US Atlantic and gulf coasts using nighttime remote sensing. Nat. Hazards Earth Syst. Sci., 19: 2141-2155. 10.5194/nhess-19-2141-2019 [Huang et al., 2019]

27. L. Jiang, G. Jiapaer, A. Bao, H. Guo, F. Ndayisaba. 2017. Vegetation dynamics and responses to climate change and human activities in Central Asia. Sci. Total Environ., 599–600: 967-980. 10.1016/j.scitotenv.2017.05.012 [Jiang et al., 2017]

28. W. Jiang, L. Wang, M. Zhang, R. Yao, X. Chen, X. Gui, J. Sun, Q. Cao. 2021. Analysis of drought events and their impacts on vegetation productivity based on the integrated surface drought index in the Hanjiang River Basin, China. Atmos. Res., 254. 10.1016/j.atmosres.2021.105536 [Jiang et al., 2021]

29. W. Jiang, Z. Niu, L. Wang, R. Yao, X. Gui, F. Xiang, Y. Ji. 2022. Impacts of drought and climatic factors on vegetation dynamics in the Yellow River Basin and Yangtze River Basin, China. Remote Sens., 14. 10.3390/rs14040930 [Jiang et al., 2022]

30. W. Jiao, L. Wang, M.F. McCabe. 2021. Multi-sensor remote sensing for drought characterization: current status, opportunities and a roadmap for the future. Remote Sens. Environ., 256: 112313. 10.1016/j.rse.2021.112313 [Jiao et al., 2021]

31. X. Li, J. Xiao. 2019. A global, 0.05-degree product of solar-induced chlorophyll fluorescence derived from OCO-2, MODIS, and reanalysis data. Remote Sens., 11. 10.3390/rs11050517 [Li and Xiao, 2019]

32. X. Li, J. Xiao, B. He, M. Altaf Arain, J. Beringer, A.R. Desai, C. Emmel, D.Y. Hollinger, A. Krasnova, I. Mammarella, S.M. Noe, P.S. Ortiz, A.C. Rey-Sanchez, A.V. Rocha, A. Varlagin. 2018. Solar-induced chlorophyll fluorescence is strongly correlated with terrestrial photosynthesis for a wide variety of biomes: first global analysis based on OCO-2 and flux tower observations. Glob. Chang. Biol., 24: 3990-4008. 10.1111/gcb.14297 [Li et al., 2018]

33. X. Li, W. Fan, Lunche Wang, M. Luo, R. Yao, S. Wang, Lizhe Wang. 2021. Effect of urban expansion on atmospheric humidity in Beijing-Tianjin-Hebei urban agglomeration. Sci. Total Environ., 759: 144305. 10.1016/j.scitotenv.2020.144305 [Li et al., 2021a]

34. Z.L. Li, P. Leng, C. Zhou, K.S. Chen, F.C. Zhou, G.F. Shang. 2021. Soil moisture retrieval from remote sensing measurements: current knowledge and directions for the future. Earth-Science Rev., 218: 103673. 10.1016/j.earscirev.2021.103673 [Li et al., 2021b]

35. R. Li, S. Zheng, C. Duan, L. Wang, C. Zhang. 2022. Land cover classification from remote sensing images based on multi-scale fully convolutional network. Geo-Spatial Inf. Sci., 25: 278-294. 10.1080/10095020.2021.2017237 [Li et al., 2022]

36. S. Liang, J. Cheng, K. Jia, B. Jiang, Q. Liu, Z. Xiao, Y. Yao, W. Yuan, X. Zhang, X. Zhao, J. Zhou. 2021. The global land surface satellite (GLASS) product suite. Bull. Am. Meteorol. Soc., 102: E323-E337. 10.1175/bams-d-18-0341.1 [Liang et al., 2021]

37. L. Liu, L. Gudmundsson, M. Hauser, D. Qin, S. Li, S.I. Seneviratne. 2020. Soil moisture dominates dryness stress on ecosystem production globally. Nat. Commun., 11: 1-9. 10.1038/s41467-020-18631-1 [Liu et al., 2020]

38. Z. Malenovský, O. Regaieg, T. Yin, N. Lauret, J. Guilleux, E. Chavanon, N. Duran, R. Janoutová, A. Delavois, J. Meynier, G. Medjdoub, P. Yang, C. van der Tol, D. Morton, B.D. Cook, J.P. Gastellu-Etchegorry. 2021. Discrete anisotropic radiative transfer modelling of solar-induced chlorophyll fluorescence: structural impacts in geometrically explicit vegetation canopies. Remote Sens. Environ., 263. 10.1016/j.rse.2021.112564 [Malenovský et al., 2021]

39. Y. Markonis, D. Koutsoyiannis. 2016. Scale-dependence of persistence in precipitation records. Nat. Clim. Chang., 6: 399-401. 10.1038/nclimate2894 [Markonis and Koutsoyiannis, 2016]

40. B. Martens, D.G. Miralles, H. Lievens, R. Van Der Schalie, R.A.M. De Jeu, D. Fernández-Prieto, H.E. Beck, W.A. Dorigo, N.E.C. Verhoest. 2017. GLEAM v3: satellite-based land evaporation and root-zone soil moisture. Geosci. Model Dev., 10: 1903-1925. 10.5194/gmd-10-1903-2017 [Martens et al., 2017]

41. D.G. Miralles, T.R.H. Holmes, R.A.M. De Jeu, J.H. Gash, A.G.C.A. Meesters, A.J. Dolman. 2011. Global land-surface evaporation estimated from satellite-based observations. Hydrol. Earth Syst. Sci., 15: 453-469. 10.5194/hess-15-453-2011 [Miralles et al., 2011]

42. S. Piao, X. Zhang, A. Chen, Q. Liu, X. Lian, X. Wang, S. Peng, X. Wu. 2019. The impacts of climate extremes on the terrestrial carbon cycle: a review. Sci. China Earth Sci., 62: 1551-1563. 10.1007/s11430-018-9363-5 [Piao et al., 2019]

43. S. Piao, X. Wang, T. Park, C. Chen, X. Lian, Y. He, J.W. Bjerke, A. Chen, P. Ciais, H. Tømmervik, R.R. Nemani, R.B. Myneni. 2020. Characteristics, drivers and feedbacks of global greening. Nat. Rev. Earth Environ., 1: 14-27. 10.1038/s43017-019-0001-x [Piao et al., 2020a]

44. S. Piao, X. Wang, K. Wang, X. Li, A. Bastos, J.G. Canadell, P. Ciais, P. Friedlingstein, S. Sitch. 2020. Interannual variation of terrestrial carbon cycle: issues and perspectives. Glob. Chang. Biol., 26: 300-318. 10.1111/gcb.14884 [Piao et al., 2020b]

45. Y. Pokhrel, F. Felfelani, Y. Satoh, J. Boulange, P. Burek, A. Gädeke, D. Gerten, S.N. Gosling, M. Grillakis, L. Gudmundsson, N. Hanasaki, H. Kim, A. Koutroulis, J. Liu, L. Papadimitriou, J. Schewe, H. Müller Schmied, T. Stacke, C.E. Telteu, W. Thiery, T. Veldkamp, F. Zhao, Y. Wada. 2021. Global terrestrial water storage and drought severity under climate change. Nat. Clim. Chang., 11: 226-233. 10.1038/s41558-020-00972-w [Pokhrel et al., 2021]

46. T.M. Radwan, G.A. Blackburn, J.D. Whyatt, P.M. Atkinson. 2021. Global land cover trajectories and transitions. Sci. Rep., 11: 1-16. 10.1038/s41598-021-92256-2 [Radwan et al., 2021]

47. D. Schimel, F.D. Schneider. 2019. Flux towers in the sky: global ecology from space. New Phytol., 224: 570-584. 10.1111/nph.15934 [Schimel and Schneider, 2019]

48. C.R. Schwalm, W.R.L. Anderegg, A.M. Michalak, J.B. Fisher, F. Biondi, G. Koch, M. Litvak, K. Ogle, J.D. Shaw, A. Wolf, D.N. Huntzinger, K. Schaefer, R. Cook, Y. Wei, Y. Fang, D. Hayes, M. Huang, A. Jain, H. Tian. 2017. Global patterns of drought recovery. Nature, 548: 202-205. 10.1038/nature23021 [Schwalm et al., 2017]

49. Z. Shao, N.S. Sumari, A. Portnov, F. Ujoh, W. Musakwa, P.J. Mandela. 2021. Urban sprawl and its impact on sustainable urban development: a combination of remote sensing and social media data. Geo-Spatial Inf. Sci., 24: 241-255. 10.1080/10095020.2020.1787800 [Shao et al., 2021]

50. X.P. Song, M.C. Hansen, S.V. Stehman, P.V. Potapov, A. Tyukavina, E.F. Vermote, J.R. Townshend. 2018. Global land change from 1982 to 2016. Nature, 560: 639-643. 10.1038/s41586-018-0411-9 [Song et al., 2018]

51. B.D. Stocker, J. Zscheischler, T.F. Keenan, I.C. Prentice, J. Peñuelas, S.I. Seneviratne. 2018. Quantifying soil moisture impacts on light use efficiency across biomes. New Phytol., 218: 1430-1449. 10.1111/nph.15123 [Stocker et al., 2018]

52. B.D. Stocker, J. Zscheischler, T.F. Keenan, I.C. Prentice, S.I. Seneviratne, J. Peñuelas. 2019. Drought impacts on terrestrial primary production underestimated by satellite monitoring. Nat. Geosci., 12: 264-270. 10.1038/s41561-019-0318-6 [Stocker et al., 2019]

53. D. Sulla-Menashe, J.M. Gray, S.P. Abercrombie, M.A. Friedl. 2019. Hierarchical mapping of annual global land cover 2001 to present: the MODIS collection 6 land cover product. Remote Sens. Environ., 222: 183-194. 10.1016/j.rse.2018.12.013 [Sulla-Menashe et al., 2019]

54. Y. Sun, C. Frankenberg, J.D. Wood, D.S. Schimel, M. Jung, L. Guanter, D.T. Drewry, M. Verma, A. Porcar-Castell, T.J. Griffis, L. Gu, T.S. Magney, P. Köhler, B. Evans, K. Yuen. 2017. OCO-2 advances photosynthesis observation from space via solar-induced chlorophyll fluorescence. Science (80-. ), 358. 10.1126/science.aam5747 [Sun et al., 2017]

55. S.M. Vicente-Serrano, S. Beguería, J.I. López-Moreno, M. Angulo, A. El Kenawy. 2010. A new global 0.5° gridded dataset (1901–2006) of a multiscalar drought index: comparison with current drought index datasets based on the palmer drought severity index. J. Hydrometeorol., 11: 1033-1043. 10.1175/2010jhm1224.1 [Vicente-Serrano et al., 2010]

56. S.M. Vicente-Serrano, C. Gouveia, J.J. Camarero, S. Beguería, R. Trigo, J.I. López-Moreno, C. Azorín-Molina, E. Pasho, J. Lorenzo-Lacruz, J. Revuelto, E. Morán-Tejeda, A. Sanchez-Lorenzo. 2013. Response of vegetation to drought time-scales across global land biomes. Proc. Natl. Acad. Sci. U. S. A., 110: 52-57. 10.1073/pnas.1207068110 [Vicente-Serrano et al., 2013]

57. S. Wang, Y. Zhang, W. Ju, J.M. Chen, P. Ciais, A. Cescatti, J. Sardans, I.A. Janssens, M. Wu, J.A. Berry, E. Campbell, M. Fernández-Martínez, R. Alkama, S. Sitch, P. Friedlingstein, W.K. Smith, W. Yuan, W. He, D. Lombardozzi, M. Kautz, D. Zhu, S. Lienert, E. Kato, B. Poulter, T.G.M. Sanders, I. Krüger, R. Wang, N. Zeng, H. Tian, N. Vuichard, A.K. Jain, A. Wiltshire, V. Haverd, D.S. Goll, J. Peñuelas. 2020. Recent global decline of CO2 fertilization effects on vegetation photosynthesis. Science (80-., ). 370: 1295-1300. 10.1126/science.abb7772 [Wang et al., 2020]

58. Z. Xiao, S. Liang, B. Jiang. 2017. Evaluation of four long time-series global leaf area index products. Agric. For. Meteorol., 246: 218-230. 10.1016/j.agrformet.2017.06.016 [Xiao et al., 2017]

59. J. Xiao, F. Chevallier, C. Gomez, L. Guanter, J.A. Hicke, A.R. Huete, K. Ichii, W. Ni, Y. Pang, A.F. Rahman, G. Sun, W. Yuan, L. Zhang, X. Zhang. 2019. Remote sensing of the terrestrial carbon cycle: a review of advances over 50 years. Remote Sens. Environ., 233: 111383. 10.1016/j.rse.2019.111383 [Xiao et al., 2019]

60. J. Zhai, S.K. Mondal, T. Fischer, Y. Wang, B. Su, J. Huang, H. Tao, G. Wang, W. Ullah, M.J. Uddin. 2020. Future drought characteristics through a multi-model ensemble from CMIP6 over South Asia. Atmos. Res., 246: 105111. 10.1016/j.atmosres.2020.105111 [Zhai et al., 2020]

61. Yao Zhang, X. Xiao, C. Jin, J. Dong, S. Zhou, P. Wagle, J. Joiner, L. Guanter, Yongguang Zhang, G. Zhang, Y. Qin, J. Wang, B. Moore. 2016. Consistency between sun-induced chlorophyll fluorescence and gross primary production of vegetation in North America. Remote Sens. Environ., 183: 154-169. 10.1016/j.rse.2016.05.015 [Zhang et al., 2016]

62. Z. Zhang, Y. Zhang, A. Porcar-Castell, J. Joiner, L. Guanter, X. Yang, M. Migliavacca, W. Ju, Z. Sun, S. Chen, D. Martini, Q. Zhang, Z. Li, J. Cleverly, H. Wang, Y. Goulas. 2020. Reduction of structural impacts and distinction of photosynthetic pathways in a global estimation of GPP from space-borne solar-induced chlorophyll fluorescence. Remote Sens. Environ., 240: 111722. 10.1016/j.rse.2020.111722 [Zhang et al., 2020]

63. M. Zhao, S.W. Running. 2010. Drought-induced reduction in global. Science (80-. ), 329: 940-943. 10.1126/science.1192666 [Zhao and Running, 2010]

64. Y. Zheng, R. Shen, Y. Wang, X. Li, S. Liu, S. Liang, J.M. Chen, W. Ju, L. Zhang, W. Yuan. 2020. Improved estimate of global gross primary production for reproducing its long-term variation, 1982–2017. Earth Syst. Sci. Data, 12: 2725-2746. 10.5194/essd-12-2725-2020 [Zheng et al., 2020]

65. Z. Zhu, S. Piao, R.B. Myneni, M. Huang, Z. Zeng, J.G. Canadell, P. Ciais, S. Sitch, P. Friedlingstein, A. Arneth, C. Cao, L. Cheng, E. Kato, C. Koven, Y. Li, X. Lian, Y. Liu, R. Liu, J. Mao, Y. Pan, S. Peng, J. Peuelas, B. Poulter, T.A.M. Pugh, B.D. Stocker, N. Viovy, X. Wang, Y. Wang, Z. Xiao, H. Yang, S. Zaehle, N. Zeng. 2016. Greening of the earth and its drivers. Nat. Clim. Chang., 6: 791-795. 10.1038/nclimate3004 [Zhu et al., 2016]

66. Q. Zhuang, Z. Shao, D. Li, X. Huang, B. Cai, O. Altan, S. Wu. 2022. Unequal weakening of urbanization and soil salinization on vegetation production capacity. Geoderma, 411: 115712. 10.1016/j.geoderma.2022.115712 [Zhuang et al., 2022a]

67. Q. Zhuang, S. Wu, X. Huang, L. Kong, Y. Yan, H. Xiao, Y. Li, P. Cai. 2022. Monitoring the impacts of cultivated land quality on crop production capacity in arid regions. Catena, 214: 106263. 10.1016/j.catena.2022.106263 [Zhuang et al., 2022b]
