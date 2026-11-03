# Land-atmosphere feedback exacerbated the mega heatwave and drought over the Yangtze River Basin of China during summer 2022

## Abstract

<a id="elsevier-abs0002"></a>

In the summer of 2022, a record-breaking heatwave and drought event occurred in the Yangtze River (YR) Basin of China, causing great damage to the society and ecosystem. However, the role of land-atmosphere (LA) interactions in driving and reinforcing this event has not been fully studied. In this study, using air temperature, soil moisture (SM), surface sensible heat fluxes, surface latent heat fluxes and radiation fluxes data from ERA5, we analyze the process of this event and reveal the contribution of the LA feedbacks. The results indicate that during the 2022 YR Basin heatwave and drought event, the regional average maximum air temperature and SM reached unprecedented levels of 2.7 standard deviations (SDs) and −3.5 SDs, respectively, compared to the climatology from 1980 to 2021. In August 2022, SM rapidly declined, pushing the region into a rare "dry" state. The dry soil increased the sensitivity of daily maximum air temperature to SM, intensifying the occurrence of heatwaves in the area. Simultaneously, increased downward solar radiation reached surface and most of that converted to sensible heat fluxes due to low soil moisture limitations leading to elevated air temperatures. While similar events have been reported multiple times in regions like Europe and western North America, their occurrence in the "moist" region of the YR Basin of China is exceptionally rare, which suggests an increasing likelihood of such extreme events in this region. Land-atmosphere interactions play an increasingly crucial role in exacerbating extreme conditions, and therefore, more studies such as this are needed for improving predictability of extreme events on a sub-seasonal time scale.

## 1. Introduction

<a id="elsevier-cesectitle0004"></a><a id="elsevier-sec0001"></a>

The global warming phenomenon has been empirically linked to an escalation in the frequency and intensity of droughts and heatwaves in various regions ([Dai, 2013](#elsevier-sbref0009); [Horton et al., 2016](#elsevier-sbref0023); [Huang et al., 2017](#elsevier-sbref0027); [Mujumdar et al., 2023](#elsevier-sbref0034); [Mishra and Singh, 2010](#elsevier-sbref0038); [Perkins-Kirkpatrick and Lewis, 2020](#elsevier-sbref0041)). Over the past few decades, the occurrence of compound hot and dry events has been rising, garnering increasing attention due to their devastating impacts on the environment, society, and the economy ([Bastos et al., 2023](#elsevier-sbref0003); [Seneviratne et al., 2012](#elsevier-sbref0047); [Zscheischler et al., 2020](#elsevier-sbref0057), [2018](#elsevier-sbref0059)). Furthermore, both observational data and modeling results indicate that, within a warming climate at regional and global scales, there has been an augmentation in the occurrence frequency and spatial extent of compound hot and dry events ([Alizadeh et al., 2020](#elsevier-sbref0002); [Zscheischler and Seneviratne, 2017](#elsevier-sbref0058)). This underscores the urgent need to enhance our understanding of the driving mechanisms behind the development of extreme heatwaves.

During the summer of 2022, an unprecedented and highly destructive extreme event struck the densely populated Yangtze River (YR) Basin in China. As reported by Nature News ([Mallapaty, 2022](#elsevier-sbref0033)), from July to August, the southern part of the YR Basin experienced the most severe drought in its recorded history, and the YR basin received 80 % less rainfall than the 30-year average, accompanied by air temperature soaring 2–4 °C above the norm level. Alongside the extreme heatwave, this region was also impacted by severe hydrological drought and wildfire incidents. For instance, Poyang Lake, China's largest freshwater lake, witnessed a drop of approximately 10 m in water levels by the end of August ([Wang et al., 2023](#elsevier-sbref0051)). In the same month, Chongqing, an upstream city in the YR basin experienced its most severe forest fire, which had profound implications for human health, food security, and terrestrial ecosystems. However, weather forecasts and numerical model predictions for the intensity of this event fell short of expectations, posing significant challenges to weather and climate models and forecasting systems ([Mallapaty, 2022](#elsevier-sbref0033)). There is an urgent need for a systematic investigation into the underlying mechanisms driving this event.

Typically, the development of extreme hot events is associated with anomalous high-pressure systems, accompanied by reduced cloud cover, deficient precipitation, enhanced shortwave solar radiation, and adiabatic heating from descending air currents ([Coumou et al., 2018](#elsevier-sbref0008); [Domeisen et al., 2023](#elsevier-sbref0016); [Ganeshi et al., 2023](#elsevier-sbref0018); [Hoskins and Woollings, 2015](#elsevier-sbref0024); [Miralles et al., 2019](#elsevier-sbref0035); [Sillmann et al., 2017](#elsevier-sbref0048)). In the YR Basin, the expansion or intensification of the Western Pacific Subtropical High ([Chaluvadi et al., 2024](#elsevier-sbref0005); [Chen et al., 2019](#elsevier-sbref0006); [Liu et al., 2019](#elsevier-sbref0031); [Ren et al., 2020](#elsevier-sbref0042)) and mid-scale atmospheric teleconnections ([Deng et al., 2020](#elsevier-sbref0010); [Lee et al., 2017](#elsevier-sbref0030); [Zhang et al., 2021](#elsevier-sbref0056)) play a significant role in the occurrence of heatwaves. Studies on the mechanisms behind this extreme event have confirmed their distinct driving roles in this instance. Under these abnormal atmospheric circulation conditions, the depletion of soil moisture and subsequent reduction in evaporative cooling may further amplify air temperature anomalies ([Chen et al., 2024](#elsevier-sbref0007); [Dirmeyer et al., 2021](#elsevier-sbref0013); [Miralles et al., 2014](#elsevier-sbref0036); [Seneviratne et al., 2010](#elsevier-sbref0045)). The elevated air temperature facilitates an increase in soil evaporative demand, accelerating soil drying. In conditions of sustained high net radiation levels, dry soil heats up faster than moist soil, and a larger proportion of energy input (i.e., net radiation) is transferred to the atmosphere through sensible heat flux, contributing to atmospheric heating ([Miralles et al., 2019](#elsevier-sbref0035); [Seneviratne et al., 2006](#elsevier-sbref0046)). This process is referred to as SM-air temperature feedback and is a crucial component of land-atmosphere interactions ([Hsu and Dirmeyer, 2023](#elsevier-sbref0026); [Koster et al., 2009](#elsevier-sbref0029); [Seneviratne et al., 2010](#elsevier-sbref0045)). Previous analyses about mega-heatwaves occurring in Europe and western North America have identified the above process as a key factor influencing the occurrence and development of extreme heatwaves ([Geirinhas et al., 2022](#elsevier-sbref0019); [Hirschi et al., 2011](#elsevier-sbref0022); [Santanello et al., 2013](#elsevier-sbref0043); [Seneviratne et al., 2006](#elsevier-sbref0046); [Whan et al., 2015](#elsevier-sbref0052)). In the case of the heatwave-drought event in the Yangtze River Basin, the role played by the soil moisture-air temperature feedback is a subject of inquiry. Previous studies indicated that the southern regions of China typically experienced humid conditions during warm summer seasons, with ample available water for evaporation, which is so-called energy-limited regime ([Koster et al., 2004](#elsevier-sbref0028); [Seneviratne et al., 2010](#elsevier-sbref0045)). Due to the moisture supply from the Yangtze River and water vapor supply from the ocean, this region is not considered a hotspot for land-atmosphere coupling, as opposed to the regions, such as, the North American Great Plains, Europe, and the Sahara in Africa. In recent years, the YR Basin has been witnessing shifts of evaporation regimes due to climate change and human activities, such as land use changes and agricultural practices ([Zhang et al., 2023](#elsevier-sbref0055)). However, the role of the alteration in the evaporation regimes the extreme event in 2022 remains unclear.

Considering the compound hot and dry event in 2022, the following questions deserve answers: Did the evaporation regimes in the YR Basin undergo a transformation in 2022, entering an unprecedented state—making it a hotspot for land-atmosphere coupling? What role did land-atmosphere coupling play in this extreme event? Due to the limitation of the in-situ observation data, we perform analysis using state-of-the-art gridded reanalysis dataset to investigate these questions and reveal its physical mechanisms.

## 2. Materials and methods

<a id="elsevier-cesectitle0005"></a><a id="elsevier-sec0002"></a>

### 2.1. Overview of the YR Basin

<a id="elsevier-cesectitle0006"></a><a id="elsevier-sec0003"></a>

The selected study area comprises nine provinces (and municipalities) within the Yangtze River Basin, namely Sichuan, Yunnan, Chongqing, Guizhou, Hubei, Hunan, Jiangxi, Anhui, and Jiangsu. The first four provinces (cities) are defined as the upper reaches of the YR Basin, and the following six are defined as its middle and lower reaches. The YR Basin serves as the demographic and economic center of the nation, with its population accounting for 39.5 % of the total national population in 2021 (Data from the National Bureau of Statistics of China). The YR Basin is characterized by a decrease in elevation from west to east, i.e., high in the western mountainous regions and low in the eastern areas [Fig. 1](#elsevier-fig0001).

![Figure 1](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr1_lrg.jpg)

<a id="elsevier-fig0001"></a>Fig. 1. Overview of the Yangtze River Basin. The figure on the left represents the DEM of the YR Basin, and the figure on the right depicts its geographic location.


Since the higher elevations in the western mountainous regions could cause deviations in regional climate averages, this study focused on the part of the basin with elevations below 2000 m for describing the regional characteristics of this extreme event.

### 2.2. Data

<a id="elsevier-cesectitle0007"></a><a id="elsevier-sec0004"></a>

#### 2.2.1. Climate data

<a id="elsevier-cesectitle0008"></a><a id="elsevier-sec0005"></a>

The meteorological data used in this study are from the European Climate Centre's ERA5 reanalysis products ([Hersbach et al., 2020](#elsevier-sbref0021)). The selected dataset spans from 1980 to 2022 and includes variables such as 0–7 cm soil moisture (SM), 2 m air temperature, potential evapotranspiration, surface sensible heat flux, surface latent heat flux, net shortwave radiation, and net longwave radiation. We downloaded hourly data from the ERA5 website according to the UTC time zone. For YR Basin, we converted the time of the raw data to the UTC+8 time zone and calculated the 24-hour average as the daily data. The daily maximum air temperature ($T_{max}$) is identified as the highest value among the 2 m air temperatures within a 24-hour period. Monthly data was derived by averaging the daily data.

#### 2.2.2. Elevation data

<a id="elsevier-cesectitle0009"></a><a id="elsevier-sec0006"></a>

Elevation data are provided by the Shuttle Radar Topography Mission (SRTM) and downloaded from the official SRTM website ([http://SRTM.csi.cgiar.org/download](http://SRTM.csi.cgiar.org/download)). The data were spatially resampled to a resolution of 0.25° using image processing software. To mitigate the influence of elevation on air temperature, grid points with elevations above 2000 m were masked when analyzing the characteristics of maximum air temperature and soil moisture within the study area, which are mainly located in the northwest part of the YR Basin.

### 2.3. Methods

<a id="elsevier-cesectitle0010"></a><a id="elsevier-sec0007"></a>

#### 2.3.1. Calculation of surface net radiation (R<sub>n</sub>) and evaporation fraction (EF)

<a id="elsevier-cesectitle0011"></a><a id="elsevier-sec0008"></a>

R<sub>n</sub> is obtained by adding the surface net shortwave radiation (SR) and the surface net longwave radiation (TR):

<a id="elsevier-eqn0001"></a>

**(1)**

$$

R_{n} = SR + TR

$$

The proportion of available energy allocated to the latent heat flux is referred to as the evaporation fraction (EF) ([Gentine et al., 2007](#elsevier-sbref0020)), which serves as a diagnostic indicator for surface energy partitioning and has been widely utilized in atmospheric and land surface modeling ([Dirmeyer et al., 2000](#elsevier-sbref0015); [Santanello et al., 2013](#elsevier-sbref0043); [Seneviratne et al., 2010](#elsevier-sbref0045)):

<a id="elsevier-eqn0002"></a>

**(2)**

$$

\begin{array}{r} {\mathit{EF} = \hspace{0.33em}\frac{\mathit{LE}}{R_{n}}} \end{array}

$$

where LE represents the surface latent heat flux.

#### 2.3.2. The extremes index

<a id="elsevier-cesectitle0012"></a><a id="elsevier-sec0009"></a>

A daily extreme index is calculated, which indicates the degree to which a climate variable deviates from its historical baseline. It is shown in terms of the numbers of standard deviation (SD).

<a id="elsevier-eqn0003"></a>

**(3)**

$$

{\text{Daily}\hspace{0.33em}\text{extreme}\hspace{0.33em}\text{index}\hspace{0.33em} = \hspace{0.33em}}\left({\text{Daily}\hspace{0.33em}\mathrm{X} - \text{mean}\hspace{0.33em}\text{daily}\hspace{0.33em}\mathrm{X}} \right)/{\text{Standard}\hspace{0.33em}\text{deviation}}

$$

which X represents various climate variables, such as $R_{n}$, precipitation, etc. The extreme index is calculated on every grid in the YR Basin. The daily mean is based on data within a 31-days moving window over the period 1980–2021.

#### 2.3.3. Metrics of land-atmosphere coupling

<a id="elsevier-cesectitle0013"></a><a id="elsevier-sec0010"></a>

Here, the term of “land-atmosphere coupling” refers to the relevance between surface conditions (negative anomaly in soil moisture) and atmospheric conditions (positive anomaly in air temperature), specifically denoting SM-air temperature coupling. We adopted the coupling metrics proposed by [Miralles et al. (2014](#elsevier-sbref0036), [2012](#elsevier-sbref0037)) to describe SM-air temperature coupling. The coupling metrics are defined as follows:

<a id="elsevier-eqn0004"></a>

**(4)**

$$

\mathrm{Ω} = \rho\left({H,T} \right) - \rho\left({H_{P},T} \right)

$$

where $\rho$ is the Pearson correlation coefficient, $H = R_{n} - \lambda E,\hspace{0.33em}H_{P} = R_{n} - \lambda E_{P}$, $\lambda$ is the latent heat of vaporization, $E$ is the actual evapotranspiration, and $E_{P}$ is the potential evapotranspiration. The potential evaporation is a measure of the extent to which near-surface atmospheric conditions are conducive to the process of evaporation, which are derived from ERA5 datasets and calculated based on the Penman-Monteith equation ([Hersbach et al., 2020](#elsevier-sbref0021); [Monteith, 1965](#elsevier-sbref0039); [Xu et al., 2024](#elsevier-sbref0054)). A positive $\mathrm{Ω}$ value indicates that a larger portion of the variability in temperature $T$ is due to soil moisture constraint in surface energy partitioning. In other words, it signifies the magnitude of the SM-air temperature coupling strength in the context of surface energy partitioning.

Since $\mathrm{Ω}$ is based on long-term correlations, it has to be modified for its application to the short time-scale events. Considering the standard deviations of T, H and $H_{p}$, [Eq. (4)](#elsevier-eqn0004) can also be expressed in terms of covariances ($Cov$):

<a id="elsevier-eqn0005"></a>

**(5)**

$$

\mathrm{Ω} = \frac{1}{\sigma_{T}}\left({\frac{Cov\left({H,T} \right)}{\sigma_{H}} - \frac{Cov\left({H_{p},T} \right)}{\sigma_{H_{p}}}} \right)

$$

where $\sigma_{T}$, $\sigma_{H}$ and $\sigma_{H_{p}}$ are the standard deviations of T, H and $H_{p}$. Similarly, we define the daily coupling measure ($\pi$) for day i as:

<a id="elsevier-eqn0006"></a>

**(6)**

$$

\pi_{i} = \frac{T_{i} - \overline{T}}{\sigma_{T}}\left({\frac{H_{i} - \overline{H}}{\sigma_{H}} - \frac{H_{p,i} - \bar{H_{p}}}{\sigma_{H_{p}}}} \right)

$$

where $\overline{T}$, $\overline{H}$ and $\bar{H_{p}}$ are the average of the long-term series of T, H and $H_{p}$. The daily coupling metric ($\pi$) can be further expressed as:

<a id="elsevier-eqn0007"></a>

**(7)**

$$

\pi = {T_{max}}^{{}'} \times \mathrm{e}' = {T_{max}}^{{}'}\left({H' - H_{p}^{{}'}} \right)

$$

where ${T_{max}}^{{}'}$, $H'$ and $H_{p}^{{}'}$ indicate the daily standard anomalies of $T_{max}$, $H$ and $H_{p}$, and $\mathrm{e}'$ represents the energy anomaly part that is equal to $H' - H_{p}^{{}'}$. The ${T_{max}}^{{}'}$ are calculated based on the long-term average and standard deviations of daily T<sub>max</sub> over the entire time series period, according to the [Eq. (6)](#elsevier-eqn0006). Specifically, the ${T_{max}}^{{}'}$ of day i are calculated based on data from day i−15 to day *i* + 15 of the 43-year period from 1980 to 2022 according to the so-called 31-day moving window. The similar calculations were done for $H'$ and $H_{p}^{{}'}$.All these above are expressed in the number of standard deviations (SD) relative to the expected values.

#### 2.3.4. Identification of soil moisture regime

<a id="elsevier-cesectitle0014"></a><a id="elsevier-sec0011"></a>

The canonical framework between SM and EF delineates two evaporation status: energy-limited and water-limited. The relationship may be nonlinear, but the first‐order linear term of the function is used to evaluate the critical thresholds, as shown in [Fig. 2](#elsevier-fig0002). Within this framework, three regimes—Dry, Transitional, and Wet—are identified by critical soil moisture points and wilting points ([Denissen et al., 2020](#elsevier-sbref0012); [Dirmeyer et al., 2012](#elsevier-sbref0014); [Seneviratne et al., 2010](#elsevier-sbref0045)). In practice, for a specific region and time period, not all stages may be covered. Instead, one or a combination of two consecutive stages serves as a candidate SM-EF curve, as shown in the inset of the upper panel of [Fig. 2](#elsevier-fig0002). Specifically, the three models are: dry-transition, transition and transition-wet. Additionally, due to the varying relationship between heating effects and SM in different evaporation regimes, the sensitivity of extreme air temperatures to SM differs. This disparity can be attributed to land-atmosphere feedback ([Wu and Dirmeyer, 2020](#elsevier-sbref0053)). Segmented regression is employed to identify evaporation regimes and determine whether there are significant changes in the sensitivity of $T_{max}$ to SM ([Dirmeyer et al., 2021](#elsevier-sbref0013), [2012](#elsevier-sbref0014), [2000](#elsevier-sbref0015); [Hsu and Dirmeyer, 2022](#elsevier-sbref0025); [Schwingshackl et al., 2017](#elsevier-sbref0044)). This approach aims to minimize the Mean Squared Error of linear regression as an optimization criterion, covering all SM ranges. The optimization is conducted with the goal of minimizing the MSE in linear regression, ensuring that the regression covers all SM ranges. In addition to this, the critical soil moisture threshold points are shown in the text as original values to demonstrate their realistic level.

![Figure 2](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr2_lrg.jpg)

<a id="elsevier-fig0002"></a>Fig. 2. Schematic of segmented linear regression fitting of SM-EF and SM-T<sub>max</sub> relationships. The attached figure in the top graph represents several candidates for the SM-EF relationship. The criterions for each regression are noted on the right side of the figure, respectively.


We utilized daily data from 1980 to 2022 to identify the SM-EF relationship of each grid point in the YR Basin. The data for dry states were insufficient due to the predominantly moist conditions in the YR Basin. We proposed several candidates of regression and used the Bayesian Information Criterion (BIC) to determine the best fit for each grid point.

<a id="elsevier-eqn0008"></a>

**(8)**

$$

BIC = nln\left({RSS/n} \right) + kln(n)

$$

where n is the sample size, RSS is the residual sum of squares, and k is the number of model parameters, which is used to penalize regressions with a more complex structure to prevent overfitting. Akaike information criterion was also tested and found to produce nearly identical results.

The SM-T<sub>max</sub> relationship consists of two pieces, both with slopes <0, intersecting at a common point. For the determination of each relationship, it is ensured that there are at least 10 data points on each segment of the piecewise function. Additional criteria are applied to ensure the reliability of the results, as shown in [Fig. 2](#elsevier-fig0002): [(1)](#elsevier-eqn0001) The two segments must be continuous; [(2)](#elsevier-eqn0002) The slope of left must have a larger magnitude than the right; [(3)](#elsevier-eqn0003) At least 10 data points on either side of the threshold exist. In the case of the SM-T<sub>max</sub> relationship, it is required that the absolute value of the slope of the line in the dry state range is greater than that in the wet state. Points that do not meet these criteria or result in non-convergence in optimization are excluded. Specific criteria are illustrated in the schematic diagram.

In order to avoid the influence of data distribution on the accuracy of the fitting results, model fitting is validated with a 10‐fold cross‐validation procedure (James et al., 2014) as used in previous hydrologic regime classification studies ([Akbar et al., 2018](#elsevier-sbref0001); [Feldman et al., 2019](#elsevier-sbref0017); [Schwingshackl et al., 2017](#elsevier-sbref0044)). Specifically, the observed (EF and SM) pairs are randomly divided into 10 equal-sized groups. Next, each model is fit to data using 9 of the 10 bins as training data to estimate their respective model parameters. Then, the fit models and parameters are compared against the data in the 10th group via a mean squared error (MSE) for each model. Each group was used once as validation data, generating 10 iterations. Thirty Monte Carlo replications of this process were obtained by randomly dividing the (EF and SM) pairs into 10 groups for 30 iterations. Thus, for each candidate model, an average of 300 MSEs was computed, and the "best" model was determined by having the lowest average MSE. These processes can be used as a validation of the results calculated by applying the BIC criterion. In addition to this, we show the average MSE results produced by the validation process and the difference with the results of the BIC method as a threshold for error estimation. The same process was used for the fitting of T<sub>max</sub>-SM.

## 3. Results

<a id="elsevier-cesectitle0015"></a><a id="elsevier-sec0012"></a>

### 3.1. YR Basin mega-heatwave and drought in 2022 summer

<a id="elsevier-cesectitle0016"></a><a id="elsevier-sec0013"></a>

To gain insights into the evolution of the 2022 summer mega-heatwave and drought event in the YR Basin, we initiate our analysis by examining the monthly climate variables in the region. By comparing the standardized anomalies of the 2022 T<sub>max</sub> and SM with the period from 1980 to 2021, we can identify the development of high air temperatures and drought, respectively. The spatial distribution of these anomalies (see [Fig. 3](#elsevier-fig0003)a,b) reveals that, despite experiencing elevated air temperatures in June, the majority of the YR Basin was, in fact, in a relatively moist state. However, as air temperatures increased further in July, soils in the upstream regions of the YR became drier, while downstream areas were less affected. By August, the concurrent occurrence of high air temperatures and drought became nearly pervasive throughout the basin.

![Figure 3](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr3_lrg.jpg)

<a id="elsevier-fig0003"></a>Fig. 3. The meteorology of the YR Basin 2022 heat extreme. (a) and (b) represent the standardized anomalies of monthly T<sub>max</sub> and SM in the YR Basin during the summer of 2022. (c) and (d) represent the observed daily T<sub>max</sub> and SM of JJA in YR Basin from 1980 to 2022. The shaded areas in (c) and (d) represent the range of the mean ±1 standard deviation. Historical data from 1980 to 2021 are plotted in grey, with record-breaking warm and dry events indicated by the T<sub>max</sub> (SM) exceeding (falling below) the horizontal values of any grey line during a specific period.


Analysis of the spatial-temporal distribution of net shortwave radiation and net longwave radiation (Fig. S1) indicates that, in June, the southern part of the Yangtze River Basin experienced negative anomalies in net shortwave radiation, while net longwave radiation exhibited positive anomalies. Concurrently, precipitation showed positive anomalies, suggesting that, due to cloud cover, severe dry and hot conditions were not prevalent in the region during June. In July, reduced cloud cover led to an increase in net shortwave radiation and a decrease in net longwave radiation, resulting in an overall increase in net surface radiation. With ample energy supply, surface latent heat flux exhibited positive anomalies, signifying a substantial loss of water from the surface. In August, excessive energy supply (positive anomaly in net radiation) coupled with insufficient water replenishment (negative anomaly in precipitation) led to soil moisture depletion. This, in turn, resulted in a reduction in latent heat flux (negative anomaly) and an increase in sensible heat flux, further elevating air temperatures and triggering the extreme heatwave.

While monthly standardized anomalies can partially describe the extent of the warm and dry conditions, they fail to reveal more detailed changes and capture the peak periods of event development. Therefore, the area-averaged daily time series of T<sub>max</sub> and SM for the three months from June to August in the YR Basin are presented in [Fig. 3c](#elsevier-fig0003), [d](#elsevier-fig0003). Additionally, to illustrate the extremity of this event, the conditions from 1980 to 2021 are concurrently plotted. The highest regional average daily T<sub>max</sub> in July was observed on July 14, 2022, at 35.5 °C, while in August, the highest regional average daily T<sub>max</sub> occurred on August 19, 2022, reaching 36.6 °C. Considering the deviation of the 2022 summer T<sub>max</sub> from the multi-year average daily air temperatures, record-breaking T<sub>max</sub> were observed, with 2.6 standard deviations (SDs) in July and 2.7 SDs in August. SM exhibited record-breaking deficits on July 14, 2022, and August 22, 2022, with deviations of −3.2 SDs and −3.6 SDs, respectively, compared to the multi-year average.

### 3.2. Formation of anomalous land-atmosphere coupling

<a id="elsevier-cesectitle0017"></a><a id="elsevier-sec0014"></a>

From a regional perspective, we applied the $\pi$ coupling metric to analyze the relationship between T<sub>max</sub> and SM anomalies throughout the summer of 2022 in the YR Basin (see [Fig. 4](#elsevier-fig0004)). The $\pi$ metric expresses the co-variability between daily maximum air temperature anomaly (${T_{max}}^{{}'}$) and soil dryness contributing to the surface energy anomaly ($\mathrm{e}'$)—here derived from the reanalysis data. As portrayed in [Fig. 4](#elsevier-fig0004), despite the occurrence of high-temperature days in June (positive anomaly in T'), the relatively sufficient SM prevented an excessively high energy anomaly term ($\mathrm{e}'$). In the middle of July, as the high-temperatures persisted, the soil gradually dried, leading to a slight increase in $\mathrm{e}'$ (up to a maximum of 2.5 SD). With the onset of the mega-heatwave in August, the soil rapidly became dry, resulting in a decrease in LE and an increase in sensible heat flux (H). This rapid change in soil conditions led to a sharp rise in $\mathrm{e}'$ (up to a maximum of 4.7 SD), intensifying the occurrence of high-temperature weather (elevated T', up to a maximum of 2.0 SD).

![Figure 4](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr4_lrg.jpg)

<a id="elsevier-fig0004"></a>Fig. 4. Land-atmosphere coupling in YR Basin during 2022 mega-heatwave summer. The pink color-filled block represents the mega-heatwave that occurred around August 2022. The orange filled part indicates the anomalies of the regional mean $T_{\max }\hspace{0.33em}\left({T_{\max }}' \right)$ in the YR Basin, and the blue solid and dashed lines indicate the anomalies of $H\hspace{0.33em}\left(H' \right)$ and $H_{p}\hspace{0.33em}\left(\hspace{4pt}{H_{p}}' \right)$, respectively. The blue filled part represents $H' - H_{p}^{{}'}$, which is the energy anomalies induced by negative SM anomalies.


To assess the magnitude of coupling strength during this event in the historical context, we calculated the values of the $\pi$ coupling metric for the summer months (June to August) in the YR Basin from 1980 to 2022 (see Fig. S2). It can be observed that for most of the historical period, the π values were mostly below 1, with a brief occurrence of values exceeding 4 in 2013. However, in August 2022, the π value reached a record-breaking high (8.5 on August 22), and it remained at elevated levels above 4 for 17 days (from August 8 to 25). This indicates that, in this unprecedented warm and dry event, both the intensity and the prolonged duration of high coupling strength were unparalleled in the historical record.

### 3.3. Soil moisture regimes of the YR basin

<a id="elsevier-cesectitle0018"></a><a id="elsevier-sec0015"></a>

Utilizing a segmented regression approach, we fitted daily SM and EF for each grid point in the YR Basin from 1980 to 2022, determining the evaporative regimes (see [Fig. 5a](#elsevier-fig0005)). The results reveal that the upper reaches of the YR Basin are predominantly in transition regime (with high-altitude northwestern areas in a transition-wet regime), while the middle and lower reaches are mostly in a transition-wet regime ([Fig. 5b](#elsevier-fig0005)). This indicates that within the basin, when encountering high air temperatures, the decrease in soil moisture in the upper subbasins leads to a rapid air temperature rise. In the middle and lower subbasins, which are generally in a wet state, the shift from wet to transition in evaporative regime lags behind as SM decreases, resulting in delayed feedback on air temperature.

![Figure 5](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr5_lrg.jpg)

<a id="elsevier-fig0005"></a>Fig. 5. Spatial distribution of soil regimes over YR Basin. (a) shows the SM-EF relationship for each grid point in the YR Basin. (b) shows the proportionality of each evaporation regime in the YR Basin via the longitude direction. (c)- (e) represent the spatial distribution of SM thresholds of SM—EF, SM—T<sub>max</sub> and the sensitivity difference of SM—T<sub>max</sub>, respectively.


Simultaneously, employing the same method, the SM-T<sub>max</sub> relationship for the YR Basin was determined, according to the previously mentioned criteria (see [Section 2.3.3](#elsevier-sec0010)), and the spatial distribution of critical points and sensitivity (slope) differences were exhibited in [Fig. 5e](#elsevier-fig0005). The results were calculated for each summer month, showing consistent evaporative state distribution (not shown), and thus, only the results for August are displayed. The spatial distribution of slope changes reveals a sharp increase in T<sub>max</sub> sensitivity to SM (slope of the segmented fitting line) when SM decreases (shift from wet to dry). This suggests that the occurrence of high-temperature weather is exacerbated as the soil becomes drier.

The 10-fold cross-validation combined with Monte Carlo process was then performed and used to validate the fitting results, as shown in Fig. S5 (for SM-EF) and Fig. S6 (for SM-T<sub>max</sub>). For the critical SM of SM-EF, spatial average of the difference between the results of 10-fold cross-validation and BIC method is −2.3 ± 6.5 (10<sup>−3</sup>·m<sup>3</sup>·*m*<sup>−3</sup>). Additionally, BIC estimated critical SM is within 0.01 m<sup>3</sup>·m<sup>-3</sup> of the mean critical SM from the 10‐fold cross validation replicates 85 % of the time. The spatial median critical SM bootstrapped standard deviation is 0.006 m<sup>3</sup>·*m*<sup>−3</sup>. Similarly, for the critical SM of SM-T<sub>max</sub>, spatial average of the difference between the results of 10-fold cross-validation and BIC method is −0.009±0.036 (m<sup>3</sup>·*m*<sup>−3</sup>). Besides, BIC estimated critical SM is within 0.05 m<sup>3</sup>·m<sup>-3</sup> of the mean critical SM from the 10‐fold cross validation replicates 67 % of the time. The spatial median critical SM bootstrapped standard deviation is 0.016 m<sup>3</sup>·*m*<sup>−3</sup>. Therefore, the BIC approach is deemed sufficient for use in this study.

## 4. Discussion

<a id="elsevier-cesectitle0019"></a><a id="elsevier-sec0016"></a>

### 4.1. The land-atmosphere feedback exacerbated the heat and drought events over China YR Basin during summer 2022

<a id="elsevier-cesectitle0020"></a><a id="elsevier-sec0017"></a>

Since the YR Basin was typically characterized as a humid region due to its abundant precipitation, previous studies failed to detect a significant feedback effect of land-atmosphere coupling on air temperature. Consequently, the YR Basin was not considered a hotspot for land-atmosphere coupling. However, during this recent hot and dry event in 2022, the record-breaking high coupling intensity occurred. Hence, it is imperative to investigate the underlying mechanisms.

In fact, when confronted with high air temperatures, the surface's evaporative demand increases, exacerbating the loss of SM. As SM declines from a higher level to critical threshold, actual evaporation transitions from energy-limited regime to water-limited regime ([Pan and Peters-Lidard, 2008](#elsevier-sbref0040)). This also leads to an increase in H at the surface, intensifying the air temperature rise, as reflected in the intensified sensitivity of T<sub>max</sub> to SM (dT<sub>max</sub>/dSM). We provide our explanation at a typical location, effectively illustrating the described process (see Fig. S3).

Before the onset of the heatwave in June, SM is at a relatively high level, and actual evaporation closely tracks potential evaporation at a ratio close to 1, indicating that SM does not limit the evaporation. In early July, as air temperatures rise, evaporation intensifies, and SM rapidly decreases, leading to the gradual separation between actual and potential evaporation. Similar processes occur during the August heatwave, with evaporation being water-limited throughout the entire month, causing an increase in H and further exacerbating high-temperature conditions. Using a segmented regression approach, we evaluated the critical soil moisture thresholds for the SM-EF and SM-T<sub>max</sub> relationships. The results indicate a critical point of 0.28 m³·*m*<sup>−</sup>³ for the SM-EF relationship and 0.18 m³·*m*<sup>−</sup>³ for the SM-T<sub>max</sub> relationship. Beyond the critical point of 0.28 m³·*m*<sup>−</sup>³, EF no longer increases with increasing SM, exhibiting a linear positive correlation below the critical point. For SM exceeding 0.18 m³·*m*<sup>−</sup>³, the magnitude of sensitivity of T<sub>max</sub> to SM is 11.6 °C/ (m³·*m*<sup>−</sup>³), while below 0.18 m³·*m*<sup>−</sup>³, T<sub>max</sub> sensitivity sharply increases to 80.4 °C/ (m³·*m*<sup>−</sup>³). This suggests a significant intensifying effect of soil dryness on high air temperatures.

Actually, other evidence for the effect of soil moisture is the diverging Hp' from H' in [Fig. 4](#elsevier-fig0004). Hp' represents the sensible heat flux without soil moisture limitation, characterizing the magnitude of the heating effect, and H' indicates the real magnitude of the heating effect with soil moisture limitation. Indeed, the difference between the two terms (i.e., e'), characterizes to some extent the magnitude of the intensification of the heating effect due to the drying soil, which closely matches the increase in T<sub>max</sub>. When SM falls below the critical threshold, it restricts surface LE and increases H, resulting in a heightened sensitivity of air temperature to dry soil conditions. The intensified high air temperatures exacerbate the atmospheric demand for evaporation, consequently amplifying SM loss. Simultaneously, the diminished water vapor hinders cloud formation, leading to an augmentation of net solar shortwave radiation. This further exacerbates surface heating. This establishes a potential positive feedback mechanism ([Fig. 6](#elsevier-fig0006)), where land surfaces may exacerbate heatwaves under drought conditions. However, such intensification is exceptionally rare in the YR Basin. In 2022, SM levels across the region were unprecedentedly below the threshold, indicating an unprecedented state of dryness with corresponding impacts. This suggests that the occurrence of extreme hot and dry events is not only limited to traditionally water-stressed arid or semi-arid regions and may become increasingly widespread in other climate regions in the future.

![Figure 6](https://ars.els-cdn.com/content/image/1-s2.0-S0168192324004349-gr6_lrg.jpg)

<a id="elsevier-fig0006"></a>Fig. 6. Schematic representation of land-atmosphere feedbacks exacerbating heat and drought events. Here, plus (+) and minus (‒) indicate positive and negative relations, respectively.


### 4.2. Uncertainties

<a id="elsevier-cesectitle0021"></a><a id="elsevier-sec0018"></a>

The results presented in this study are obtained through primarily utilizing standardized anomalies based on historical same-period averages to characterize heatwaves and droughts. From a climatic perspective, using standardized anomalies to represent the extremity of heat and dryness is a crucial indicator ([Thompson et al., 2022](#elsevier-sbref0050)). In certain situations, events with relatively small numerical intensity may have a more significant impact than events with larger absolute values, as the regions where they occur may not be adapted to such extreme changes. Therefore, the use of standardized anomalies is highly suitable for describing this dry and hot event. To emphasize the uniqueness of this event, this study compares the daily maximum air temperature and soil moisture anomalies during this event with the historical same-period levels (1980–2021). Although the chosen standardization period starts at 1980, which is not the entire record, this timeframe is considered as a period of climate change after a climatic shift ([Tavakol et al., 2020](#elsevier-sbref0049)). Contrasting with this climate state still demonstrates its unprecedented nature. Due to significant topographical variations in the upstream YR Basin, [Fig. 3c](#elsevier-fig0003), [d](#elsevier-fig0003) represent an area-weighted average for the entire region. We separately analyzed the statistics for the upstream and downstream regions regarding maximum air temperature and soil moisture (Fig. S4). While there are slight differences in the air temperature and soil moisture variations between the two regions in August, overall, they both reached unprecedented levels during that month.

The reference to the YR Basin entering an unprecedented "dry state" in this research pertains to the largest number of days in August characterized by the water-limited state defined by the SM-EF framework, coupled with the heightened sensitivity of air temperature to SM in such dry conditions. In recent studies, the SM-LE relationship was also used for critical soil moisture point assessment (Duan et al.,2023). However, considering that the SM-LE relationship can be affected by weather conditions ([Gentine et al., 2007](#elsevier-sbref0020); Ford et al., 2014; Gu et al., 2006; Haghighi et al., 2018), we still chose the SM-EF relationship as our method and ensured the reliability of the results by limiting the range of the EF and excluding precipitation day data. The SM-EF relationship employed in this study has been assumed to remain unchanged over the nearly 40-year period under consideration. Thus, we have exclusively utilized data from August over the 40-year period for identification, emphasizing prolonged durations in a state characterized by higher T<sub>max</sub>/SM sensitivity. The differences in sensitivity between extreme temperatures and SM above and below threshold levels serve as a source of predictability for severe heatwaves. Under dry soil conditions, the probability distribution of extreme temperatures undergoes changes, contributing to the potential occurrence of heatwaves. Representing the disparities in sensitivity between extreme temperatures and soil moisture accurately and correctly in forecasting models is crucial. Real-time updates on soil moisture conditions can enhance forecasting accuracy of heatwaves and the effectiveness of the heatwave warnings, especially in regions with characteristics similar to the YR Basin.

### 4.3. Implications

<a id="elsevier-cesectitle0022"></a><a id="elsevier-sec0019"></a>

The mega compound hot and dry event that occurred in the YR Basin during the summer of 2022 is unprecedented in local records since 1980. Compound hot and dry events can be attributed to both large-scale atmospheric circulations and local land-atmosphere (LA) interactions. In addition to the anomalous atmospheric circulation patterns studied by previous researchers, we provided evidences indicating an intensified role of local LA feedbacks in this study.

Due to its subtropical monsoon climate, the YR Basin is typically characterized by a warm and moist environment, receiving moisture from both the Indian Ocean and the western Pacific. During the summer of 2022, preceding high air temperatures and insufficient rainfall led to SM depletion without adequate replenishment. Indeed, due to the influences of climate change and human activities, the soil moisture levels in the YR Basin have shown a decreasing trend, despite still being at relatively high levels (Fig. S7). In particular, the probability of low soil moisture occurring increases apparently. While these findings have already issued warnings about climate change in the region, the assessment based on climate averages remains inadequate in the face of this unprecedented event, given the limited records of extreme heat events. The spatial and temporal variability of precipitation in the YR Basin makes the average results insufficient to capture the trends in variable changes under extreme conditions. Previous studies have documented shifts in regional evaporation regimes in Arid and semi-arid zones ([Berg et al., 2016](#elsevier-sbref0004); J. M. C. [Denissen et al., 2022](#elsevier-sbref0011); [Lo et al., 2021](#elsevier-sbref0032)), which may cause more heatwaves and drought events. However, prolonged periods of soil moisture limitation in humid regions can also trigger strong LA feedbacks that can cause extreme heat events, like the mega heatwave and drought event in 2022 summer in the YR Basin. The eruption of the super extreme hot and dry event in 2022, fueled by the gradually decreasing soil moisture and atmospheric circulation anomalies, highlights the urgent need for studying the physical mechanisms behind such super extreme events. This research can contribute to enhancing the predictability of such events and reducing the associated losses.

## 5. Conclusion

<a id="elsevier-cesectitle0023"></a><a id="elsevier-sec0020"></a>

In this study, we have used high-quality reanalysis data of surface SM, T<sub>max</sub>, and surface energy fluxes to analyzes the characteristics of a mega heatwave and drought event in the Yangtze River Basin in the summer of 2022, and reveals the role of land-atmosphere coupling due to reduced soil moisture in exacerbating the extreme event.

The August extreme event in the Yangtze River Basin in 2022 was unprecedented since 1980, with area-averaged maximum air temperature reaching 2.7 SDs and soil moisture reaching −3.6 SDs. Based on the SM-EF and SM-T<sub>max</sub> curves, we have demonstrated the existence of a threshold in the range of SM below which LE would limited due to low SM and the sensitivity of the T<sub>max</sub> to SM substantially During this event, the YR Basin shifted from usual energy-limited condition into a state of rare dryness, providing a potentially strong positive feedback mechanism by which the land surface may exacerbate heatwaves. Besides, enhanced solar radiation due to reduced cloud cover increases the amount of energy available at the surface (R<sub>n</sub>), while dry soils allow more energy to be converted into sensible heat flux, resulting in enhanced surface heating. We hope that our results will raise more awareness about the role of land-atmosphere interactions in extreme events, including areas that have not previously been identified as hotspots.

## CRediT authorship contribution statement

<a id="elsevier-cesectitle0023a"></a><a id="elsevier-sec0020a"></a>

**Xiao Chen:** Conceptualization, Writing – original draft. **Jialin Wang:** Writing – review & editing. **Feifei Pan:** Writing – review & editing. **Yu Song:** Writing – review & editing. **Ju Liang:** Writing – review & editing. **Na Huang:** Data curation, Investigation, Formal analysis. **Kang Jiang:** Data curation, Investigation, Formal analysis. **Riping Gao:** Data curation, Investigation, Formal analysis. **Jingyu Men:** Data curation, Investigation, Formal analysis. **Pengshuai Bi:** Data curation, Investigation, Formal analysis. **Fangxiao Zhang:** Data curation, Investigation, Formal analysis. **Zhanrui Huang:** Data curation, Investigation, Formal analysis. **Binxiang Huang:** Supervision, Methodology. **Zhihua Pan:** Supervision, Methodology.

## Declaration of competing interest

<a id="elsevier-cesectitle0025"></a><a id="elsevier-coi0001"></a>

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Acknowledgments

<a id="elsevier-cesectitle0026"></a><a id="elsevier-sec0022"></a>

This work is funded by the <a id="elsevier-gs0001"></a>National Key Research and Development Plan of China (No. [2023YFF0805703](#elsevier-gs0001)).

## Data availability

<a id="elsevier-cesectitle0027"></a><a id="elsevier-sec0023"></a>

All data used in this work are publicly available: The global high-resolution gridded climate reanalysis dataset, ERA5, is available at [https://cds.climate.copernicus.eu/](https://cds.climate.copernicus.eu/). Elevation data are provided by the Shuttle Radar Topography Mission (SRTM) and downloaded from the official SRTM website ([http://SRTM.csi.cgiar.org/download](http://SRTM.csi.cgiar.org/download)). The data that support the findings of this study are available upon reasonable request from the authors.

## References

1. <a id="elsevier-sbref0001"></a>R. Akbar, D.J.S. Gianotti, K.A. McColl, E. Haghighi, G.D. Salvucci, D. Entekhabi Estimation of landscape soil water losses from satellite observations of soil moisture J. Hydrometeorol., 19 (5) (2018), pp. 871-889, 10.1175/jhm-D-17-0200.1 [Akbar et al., 2018]

2. <a id="elsevier-sbref0002"></a>M.R. Alizadeh, J. Adamowski, M.R. Nikoo, A. AghaKouchak, P. Dennison, M. Sadegh A century of observations reveals increasing likelihood of continental-scale compound dry-hot extremes Sci. Adv., 6 (39) (2020), 10.1126/sciadv.aaz4571 [Alizadeh et al., 2020]

3. <a id="elsevier-sbref0003"></a>A. Bastos, S. Sippel, D. Frank, M.D. Mahecha, S. Zaehle, J. Zscheischler, M. Reichstein A joint framework for studying compound ecoclimatic events Nat. Rev. Earth Environ., 4 (5) (2023), pp. 333-350, 10.1038/s43017-023-00410-3 [Bastos et al., 2023]

4. <a id="elsevier-sbref0004"></a>A. Berg, K. Findell, B. Lintner, A. Giannini, S.I. Seneviratne, B. van den Hurk, et al. Land-atmosphere feedbacks amplify aridity increase over land under global warming Nat. Clim. Change, 6 (9) (2016), 10.1038/nclimate3029 869–+ [Berg et al., 2016]

5. <a id="elsevier-sbref0005"></a>R. Chaluvadi, H. Varikoden, M. Mujumdar, S.T. Ingle Unravelling the linkages between the intraseasonal variability of the west pacific subtropical high and Indian summer monsoon rainfall Asia Pac. J. Atmos. Sci., 60 (1) (2024), pp. 49-64, 10.1007/s13143-023-00335-3 [Chaluvadi et al., 2024]

6. <a id="elsevier-sbref0006"></a>M.Y. Chen, J.Y. Yu, X. Wang, W.P. Jiang The changing impact mechanisms of a diverse El Nino on the western pacific subtropical high Geophys. Res. Lett., 46 (2) (2019), pp. 953-962, 10.1029/2018 gl081131 [Chen et al., 2019]

7. <a id="elsevier-sbref0007"></a>X. Chen, Z. Pan, B. Huang, J. Liang, J. Wang, Z. Zhang, et al. Influence paradigms of soil moisture on land surface energy partitioning under different climatic conditions Sci. Total Environ., 916 (2024), Article 170098, 10.1016/j.scitotenv.2024.170098 -170098 [Chen et al., 2024]

8. <a id="elsevier-sbref0008"></a>D. Coumou, G. Di Capua, S. Vavrus, L. Wang, S. Wang The influence of Arctic amplification on mid-latitude summer circulation Nat. Commun., 9 (2018), 10.1038/s41467-018-05256-8 [Coumou et al., 2018]

9. <a id="elsevier-sbref0009"></a>A.G. Dai Increasing drought under global warming in observations and models (vol 3, pg 52, 2013) Nat. Clim. Change, 3 (2) (2013), p. 171, 10.1038/nclimate1811 -171 [Dai, 2013]

10. <a id="elsevier-sbref0010"></a>K.Q. Deng, X.W. Jiang, C.D. Hu, D.L. Chen More frequent summer heat waves in southwestern China linked to the recent declining of Arctic sea ice Environ. Res. Lett., 15 (7) (2020), 10.1088/1748-9326/ab8335 [Deng et al., 2020]

11. <a id="elsevier-sbref0011"></a>J.M.C. Denissen, A.J. Teuling, A.J. Pitman, S. Koirala, M. Migliavacca, W.T. Li, et al. Widespread shift from ecosystem energy to water limitation with climate change Nat. Clim. Change, 12 (7) (2022), 10.1038/s41558-022-01403-8 677–+ [Denissen et al., 2022]

12. <a id="elsevier-sbref0012"></a>J.M.C. Denissen, A.J. Teuling, M. Reichstein, R. Orth Critical soil moisture derived from satellite observations over Europe J. Geophys. Res. Atmos., 125 (6) (2020), 10.1029/2019jd031672 [Denissen et al., 2020]

13. <a id="elsevier-sbref0013"></a>P.A. Dirmeyer, G. Balsamo, E.M. Blyth, R. Morrison, H.M. Cooper Land-atmosphere interactions exacerbated the drought and heatwave over northern europe during summer 2018 Agu Adv., 2 (2) (2021), 10.1029/2020av000283 [Dirmeyer et al., 2021]

14. <a id="elsevier-sbref0014"></a>P.A. Dirmeyer, B.A. Cash, J.L. Kinter, C. Stan, T. Jung, L. Marx, et al. Evidence for enhanced land-atmosphere feedback in a warming climate J. Hydrometeorol., 13 (3) (2012), pp. 981-995, 10.1175/jhm-D-11-0104.1 [Dirmeyer et al., 2012]

15. <a id="elsevier-sbref0015"></a>P.A. Dirmeyer, F.J. Zeng, A. Ducharne, J.C. Morrill, R.D. Koster The sensitivity of surface fluxes to soil water content in three land surface schemes J. Hydrometeorol., 1 (2) (2000), pp. 121-134, 10.1175/1525-7541 (2000)001<0121:Tsosft>2.0.Co;2 [Dirmeyer et al., 2000]

16. <a id="elsevier-sbref0016"></a>D.I.V. Domeisen, E.A.B. Eltahir, E.M. Fischer, R. Knutti, S.E. Perkins-Kirkpatrick, C. Schar, et al. Prediction and projection of heatwaves Nat. Rev. Earth Environ., 4 (1) (2023), pp. 36-50, 10.1038/s43017-022-00371-z [Domeisen et al., 2023]

17. <a id="elsevier-sbref0017"></a>A.F. Feldman, D.J.S. Gianotti, I.F. Trigo, G.D. Salvucci, D. Entekhabi Satellite-based assessment of land surface energy partitioning-soil moisture relationships and effects of confounding variables Water Resour. Res., 55 (12) (2019), pp. 10657-10677, 10.1029/2019wr025874 [Feldman et al., 2019]

18. <a id="elsevier-sbref0018"></a>N.G. Ganeshi, M. Mujumdar, Y. Takaya, M.M. Goswami, B.B. Singh, R. Krishnan, T. Terao Soil moisture revamps the temperature extremes in a warming climate over India NPJ Clim. Atmos. Sci., 6 (1) (2023), 10.1038/s41612-023-00334-1 [Ganeshi et al., 2023]

19. <a id="elsevier-sbref0019"></a>J.L. Geirinhas, A.C. Russo, R. Libonati, D.G. Miralles, P.M. Sousa, H. Wouters, R.M. Trigo The influence of soil dry-out on the record-breaking hot 2013/2014 summer in Southeast Brazil Sci. Rep., 12 (1) (2022), 10.1038/s41598-022-09515-z [Geirinhas et al., 2022]

20. <a id="elsevier-sbref0020"></a>P. Gentine, D. Entekhabi, A. Chehbouni, G. Boulet, B. Duchemin Analysis of evaporative fraction diurnal behaviour Agric. For. Meteorol., 143 (1–2) (2007), pp. 13-29, 10.1016/j.agrformet.2006.11.002 [Gentine et al., 2007]

21. <a id="elsevier-sbref0021"></a>H. Hersbach, B. Bell, P. Berrisford, S. Hirahara, A. Horanyi, J. Munoz-Sabater, et al. The ERA5 global reanalysis Q. J. R. Meteorol. Soc., 146 (730) (2020), pp. 1999-2049, 10.1002/qj.3803 [Hersbach et al., 2020]

22. <a id="elsevier-sbref0022"></a>M. Hirschi, S.I. Seneviratne, V. Alexandrov, F. Boberg, C. Boroneant, O.B. Christensen, et al. Observational evidence for soil-moisture impact on hot extremes in southeastern Europe Nat. Geosci., 4 (1) (2011), pp. 17-21, 10.1038/ngeo1032 [Hirschi et al., 2011]

23. <a id="elsevier-sbref0023"></a>R.M. Horton, J.S. Mankin, C. Lesk, E. Coffel, C. Raymond A review of recent advances in research on extreme heat events Curr. Clim. Change Rep., 2 (4) (2016), pp. 242-259, 10.1007/s40641-016-0042-x [Horton et al., 2016]

24. <a id="elsevier-sbref0024"></a>B. Hoskins, T. Woollings Persistent extratropical regimes and climate extremes Curr. Clim. Change Rep., 1 (3) (2015), pp. 115-124, 10.1007/s40641-015-0020-8 [Hoskins and Woollings, 2015]

25. <a id="elsevier-sbref0025"></a>H. Hsu, P.A. Dirmeyer Deconstructing the soil moisture-latent heat flux relationship: the range of coupling regimes experienced and the presence of nonlinearity within the sensitive regime J. Hydrometeorol., 23 (7) (2022), pp. 1041-1057, 10.1175/jhm-D-21-0224.1 [Hsu and Dirmeyer, 2022]

26. <a id="elsevier-sbref0026"></a>H. Hsu, P.A. Dirmeyer Soil moisture-evaporation coupling shifts into new gears under increasing CO2 Nat. Commun., 14 (1) (2023), p. 1162, 10.1038/s41467-023-36794-5 -1162 [Hsu and Dirmeyer, 2023]

27. <a id="elsevier-sbref0027"></a>S.Z. Huang, G.Y. Leng, Q. Huang, Y.Y. Xie, S.Y. Liu, E.H. Meng, P. Li The asymmetric impact of global warming on US drought types and distributions in a large ensemble of 97 hydro-climatic simulations Sci. Rep., 7 (2017), 10.1038/s41598-017-06302-z [Huang et al., 2017]

28. <a id="elsevier-sbref0028"></a>R.D. Koster, P.A. Dirmeyer, Z.C. Guo, G. Bonan, E. Chan, P. Cox, et al. Regions of strong coupling between soil moisture and precipitation Science, 305 (5687) (2004), pp. 1138-1140, 10.1126/science.1100217 (1979) [Koster et al., 2004]

29. <a id="elsevier-sbref0029"></a>R.D. Koster, S.D. Schubert, M.J. Suarez Analyzing the concurrence of meteorological droughts and warm periods, with implications for the determination of evaporative regime J. Clim., 22 (12) (2009), pp. 3331-3341, 10.1175/2008jcli2718.1 [Koster et al., 2009]

30. <a id="elsevier-sbref0030"></a>M.H. Lee, S. Lee, H.J. Song, C.H. Ho The recent increase in the occurrence of a boreal summer teleconnection and its relationship with temperature extremes J. Clim., 30 (18) (2017), pp. 7493-7504, 10.1175/jcli-D-16-0094.1 [Lee et al., 2017]

31. <a id="elsevier-sbref0031"></a>Q. Liu, T.J. Zhou, H.T. Mao, C.B. Fu Decadal variations in the relationship between the western pacific subtropical high and summer heat waves in East China J. Clim., 32 (5) (2019), pp. 1627-1640, 10.1175/jcli-D-18-0093.1 [Liu et al., 2019]

32. <a id="elsevier-sbref0032"></a>M.H. Lo, W.Y. Wu, L.I. Tang, D. Ryu, M. Rashid, R.J. Wu Temporal changes in land surface coupling strength: an example in a semi-arid region of Australia J. Clim., 34 (4) (2021), pp. 1503-1513, 10.1175/jcli-D-20-0250.1 [Lo et al., 2021]

33. <a id="elsevier-sbref0033"></a>S. Mallapaty China's extreme weather challenges scientists trying to study it Nature, 609 (7929) (2022), p. 888, 10.1038/d41586-022-02954-8 -888 [Mallapaty, 2022]

34. <a id="elsevier-sbref0034"></a>P.B. Milind Mujumdar, B.B. Singh, G. Mangesh, N. Ganeshi Severe droughts in India Integrated Drought Management, 1, CRC Press, USA (2023), pp. 191-206 [Mujumdar et al., 2023]

35. <a id="elsevier-sbref0035"></a>D.G. Miralles, P. Gentine, S.I. Seneviratne, A.J. Teuling Land-atmospheric feedbacks during droughts and heatwaves: state of the science and current challenges Ann. N. Y. Acad. Sci., 1436 (1) (2019), pp. 19-35, 10.1111/nyas.13912 [Miralles et al., 2019]

36. <a id="elsevier-sbref0036"></a>D.G. Miralles, A.J. Teuling, C.C. van Heerwaarden, J.V.G. de Arellano Mega-heatwave temperatures due to combined soil desiccation and atmospheric heat accumulation Nat. Geosci., 7 (5) (2014), pp. 345-349, 10.1038/ngeo2141 [Miralles et al., 2014]

37. <a id="elsevier-sbref0037"></a>D.G. Miralles, M.J. van den Berg, A.J. Teuling, R.A.M. de Jeu Soil moisture-temperature coupling: a multiscale observational analysis Geophys. Res. Lett., 39 (2012), p. L21707, 10.1029/2012 gl053703 [Miralles et al., 2012]

38. <a id="elsevier-sbref0038"></a>A.K. Mishra, V.P. Singh A review of drought concepts J. Hydrol., 391 (1–2) (2010), pp. 204-216, 10.1016/j.jhydrol.2010.07.012 [Mishra and Singh, 2010]

39. <a id="elsevier-sbref0039"></a>J.L. Monteith Evaporation and environment Symp. Soc. Exp. Biol., 19 (1965), pp. 205-234 [Monteith, 1965]

40. <a id="elsevier-sbref0040"></a>F. Pan, C.D. Peters-Lidard On the relationship between mean and variance of soil moisture fields J. Am. Water Resour. Assoc., 44 (1) (2008), pp. 235-242, 10.1111/j.1752-1688.2007.00150.x [Pan and Peters-Lidard, 2008]

41. <a id="elsevier-sbref0041"></a>S.E. Perkins-Kirkpatrick, S.C. Lewis Increasing trends in regional heatwaves Nat. Commun., 11 (1) (2020), 10.1038/s41467-020-16970-7 [Perkins-Kirkpatrick and Lewis, 2020]

42. <a id="elsevier-sbref0042"></a>L.W. Ren, T.J. Zhou, W.X. Zhang Attribution of the record-breaking heat event over Northeast Asia in summer 2018: the role of circulation Environ. Res. Lett., 15 (5) (2020), 10.1088/1748-9326/ab8032 [Ren et al., 2020]

43. <a id="elsevier-sbref0043"></a>J.A. Santanello Jr., C.D. Peters-Lidard, A. Kennedy, S.V Kumar Diagnosing the nature of land-atmosphere coupling: a case study of dry/wet extremes in the US Southern great plains J. Hydrometeorol., 14 (1) (2013), pp. 3-24, 10.1175/jhm-D-12-023.1 [Santanello et al., 2013]

44. <a id="elsevier-sbref0044"></a>C. Schwingshackl, M. Hirschi, S.I. Seneviratne Quantifying spatiotemporal variations of soil moisture control on surface energy balance and near-surface air temperature J. Clim., 30 (18) (2017), pp. 7105-7124, 10.1175/jcli-D-16-0727.1 [Schwingshackl et al., 2017]

45. <a id="elsevier-sbref0045"></a>S.I. Seneviratne, T. Corti, E.L. Davin, M. Hirschi, E.B. Jaeger, I. Lehner, et al. Investigating soil moisture-climate interactions in a changing climate: a review Earth Sci. Rev., 99 (3–4) (2010), pp. 125-161, 10.1016/j.earscirev.2010.02.004 [Seneviratne et al., 2010]

46. <a id="elsevier-sbref0046"></a>S.I. Seneviratne, D. Lüthi, M. Litschi, C. Schär Land-atmosphere coupling and climate change in Europe Nature, 443 (7108) (2006), pp. 205-209, 10.1038/nature05095 [Seneviratne et al., 2006]

47. <a id="elsevier-sbref0047"></a>S.I. Seneviratne, N. Nicholls, D. Easterling, C.M. Goodess, S. Kanae, J. Kossin, et al. Changes in Climate Extremes and Their Impacts on the Natural Physical Environment Cambridge University Press, New York (2012) [Seneviratne et al., 2012]

48. <a id="elsevier-sbref0048"></a>J. Sillmann, T. Thorarinsdottir, N. Keenlyside, N. Schaller, L.V. Alexander, G. Hegerl, et al. Understanding, modeling and predicting weather and climate extremes: challenges and opportunities Weather Clim. Extrem., 18 (2017), pp. 65-74, 10.1016/j.wace.2017.10.003 [Sillmann et al., 2017]

49. <a id="elsevier-sbref0049"></a>A. Tavakol, V. Rahmani, J. Harrington Jr. Evaluation of hot temperature extremes and heat waves in the Mississippi River Basin Atmos. Res. (2020), p. 239, 10.1016/j.atmosres.2020.104907 [Tavakol et al., 2020]

50. <a id="elsevier-sbref0050"></a>V. Thompson, A.T. Kennedy-Asser, E. Vosper, Y.T.E. Lo, C. Huntingford, O. Andrews, et al. The 2021 western North America heat wave among the most extreme events ever recorded globally Sci. Adv., 8 (18) (2022), 10.1126/sciadv.abm6860 [Thompson et al., 2022]

51. <a id="elsevier-sbref0051"></a>W.J. Wang, K. Shi, X.W. Wang, S.Q. Wang, D. Zhang, Y.Y. Peng, et al. A record-breaking extreme heat event caused unprecedented warming of lakes in China Sci. Bull., 68 (6) (2023), pp. 578-582, 10.1016/j.scib.2023.03.001 (Beijing) [Wang et al., 2023]

52. <a id="elsevier-sbref0052"></a>K. Whan, J. Zscheischler, R. Orth, M. Shongwe, M. Rahimi, E.O. Asare, S.I. Seneviratne Impact of soil moisture on extreme maximum temperatures in Europe Weather Clim. Extrem., 9 (2015), pp. 57-67, 10.1016/j.wace.2015.05.001 [Whan et al., 2015]

53. <a id="elsevier-sbref0053"></a>J. Wu, P.A. Dirmeyer Drought demise attribution over CONUS J. Geophys. Res. Atmos., 125 (4) (2020), 10.1029/2019jd031255 [Wu and Dirmeyer, 2020]

54. <a id="elsevier-sbref0054"></a>C. Xu, W. Wang, Y. Hu, Y. Liu Evaluation of ERA5, ERA5-Land, GLDAS-2.1, and GLEAM potential evapotranspiration data over mainland China J. Hydrol. Reg. Stud., 51 (2024), 10.1016/j.ejrh.2023.101651 [Xu et al., 2024]

55. <a id="elsevier-sbref0055"></a>T.T. Zhang, Y. Deng, J.W. Chen, S. Yang, Y.J. Dai An energetics tale of the 2022 mega-heatwave over central-eastern China NPJ Clim. Atmos. Sci., 6 (1) (2023), 10.1038/s41612-023-00490-4 [Zhang et al., 2023]

56. <a id="elsevier-sbref0056"></a>T.T. Zhang, X.W. Jiang, J.W. Chen, S. Yang, Y. Deng, W. Wei, et al. Interannual variability of springtime extreme heat events over the southeastern edge of the Tibetan plateau: role of a spring-type circumglobal teleconnection pattern J. Clim., 34 (24) (2021), pp. 9915-9930, 10.1175/jcli-D-21-0049.1 [Zhang et al., 2021]

57. <a id="elsevier-sbref0057"></a>J. Zscheischler, O. Martius, S. Westra, E. Bevacqua, C. Raymond, R.M. Horton, et al. A typology of compound weather and climate events Nat. Rev. Earth Environ., 1 (7) (2020), pp. 333-347, 10.1038/s43017-020-0060-z [Zscheischler et al., 2020]

58. <a id="elsevier-sbref0058"></a>J. Zscheischler, S.I. Seneviratne Dependence of drivers affects risks associated with compound events Sci. Adv., 3 (6) (2017), 10.1126/sciadv.1700263 [Zscheischler and Seneviratne, 2017]

59. <a id="elsevier-sbref0059"></a>J. Zscheischler, S. Westra, B. van den Hurk, S.I. Seneviratne, P.J. Ward, A. Pitman, et al. Future climate risk from compound events Nat. Clim. Change, 8 (6) (2018), pp. 469-477, 10.1038/s41558-018-0156-3 [Zscheischler et al., 2018]
