---
title: "Hydrological response to climate change in a glacierized catchment in the Himalayas"
authors: "Walter W. Immerzeel, L. P. H. van Beek, M. Konz, A. B. Shrestha, M. F. P. Bierkens"
journal: "Climatic Change"
doi: "10.1007/s10584-011-0143-4"
published: "2012/02"
source: "springer_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 9782
---

# Hydrological response to climate change in a glacierized catchment in the Himalayas

## Abstract

The analysis of climate change impact on the hydrology of high altitude glacierized catchments in the Himalayas is complex due to the high variability in climate, lack of data, large uncertainties in climate change projection and uncertainty about the response of glaciers. Therefore a high resolution combined cryospheric hydrological model was developed and calibrated that explicitly simulates glacier evolution and all major hydrological processes. The model was used to assess the future development of the glaciers and the runoff using an ensemble of downscaled climate model data in the Langtang catchment in Nepal. The analysis shows that both temperature and precipitation are projected to increase which results in a steady decline of the glacier area. The river flow is projected to increase significantly due to the increased precipitation and ice melt and the transition towards a rain river. Rain runoff and base flow will increase at the expense of glacier runoff. However, as the melt water peak coincides with the monsoon peak, no shifts in the hydrograph are expected.

## 1 Introduction

More than one-sixth of the global population rely on glacier and snow melt for their water supply (Barnett et al. [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR3)). Changes in temperature and precipitation are expected to significantly affect the cryospheric processes and the hydrology of headwater catchments in the Himalayas (Cruz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR6); Immerzeel et al. [2009](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR14)). Accurate modeling of the hydrological response to climate change in these catchments is complicated due to the large climatic heterogeneity, the lack of data in mountain catchments, the resolution and accuracy of GCM outputs and uncertainty about the response of glacier and snow dynamics (Beniston [2003](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR4)). Traditionally, glacier dynamics are not linked to other hydrological processes such as evapotranspiration, surface runoff and base flow in a single model (Sharp et al. [1998](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR30)). Most hydrological impact studies on the contrary deploy simple degree day methods (Hock [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR13)) and assume hypothetical reduction in future glacier areas (Singh and Bengtsson [2004](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR32); Hock [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR13); Rees and Collins [2006](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR25); Immerzeel et al. [2009](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR14)). Although these studies provide valuable insights into the possible range of future options, they suffer from large uncertainty about the plausibility of the future evolution of snow and ice. Another issue that is often ignored in modeling melt from glaciers is that both accumulation and ablation of glaciers depend on the glacier area, which does not scale linearly with glacier volume. As larger glaciers have a smaller area to volume ratio they are less sensitive to climate change than smaller glaciers (Van de Wal and Wild [2001](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR35)).

Recently there has been a strong debate about the melt rate of Himalayan glaciers. The claim that all glaciers in the Himalayas could disappear by 2035 in the AR4 of the IPCC (Cruz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR6)) has been the source of great controversy and has been admitted to stem from a wrong quotation of grey literature (Schiermeier [2010](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR27)). Mass balance studies and regional reviews conclude otherwise, although there are very limited published studies and measurements available (Bolch et al. [2008](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR5); Zemp et al. [2009](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR38)). Obviously, there is large uncertainty and variability in the retreat rates of Himalayan glaciers and to settle the debate in a rational manner there is a strong need for reference studies that reliably model the transient evolution of glaciers under climate change.

In this study we attempt to provide such a reference study by developing a combined cryospheric hydrological model for a glacierized Himalayan catchment in Nepal. The model explicitly simulates glacier movement in combination with major hydrological processes such as evapotranspiration, surface runoff, ablation and groundwater base flow at a high spatial resolution with a daily time step. An innovative two stage calibration procedure is used. First the historical evolution of glaciers is calibrated using the recent location of glacier tongues and secondly the hydrological processes are optimized using discharge observations. The calibrated model is then forced with an ensemble of transient statically downscaled GCM outputs to evaluate the climate change impact on the future evolution of the glaciers and catchment hydrology.

## 2 Study area

The Langtang river catchment (360 km<sup>2</sup>) is located approximately 100 km north of Kathmandu (Fig. [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig1)). The elevation ranges from 3800 m.a.s.l. up to the peak of Langtang Lirung at 7234 m.a.s.l with an average altitude of 5169 m.a.s.l.. In total 46% (166 km<sup>2</sup>) of the catchment is glacierized. The glacier tongues below 5200 m.a.s.l. are generally debris covered (32 km<sup>2</sup>). The main valley is dissected by the Langtang Khola River and it is typically U-shaped. Several sets of moraines occupy the valley bottom, which have been attributed to the Little Ice Age, Neoglacial and Late glacial (Heuberger et al. [1984](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR11)). Boulders and scree cover the steep slopes and high plateaus, while the occurrence of forest and grassland in the lower altitudes with less steep slopes along the river is limited to 1.5% of the catchment area. The riverbed consists of boulder and gravel. The area is part of the Main Central Thrust Zone, and its geology consists of granite, gneiss and schist. The characteristic feature of the climate of Nepal is the monsoon circulation with predominant easterly winds in the summer and westerly winds from October to May. In the Langtang Khola catchment, 77% of annual precipitation of 814 mm y<sup>−1</sup> falls during monsoon season (June to September; mean over period from 1957 to 2002, (Uppala et al. [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR34))). From June to August total precipitation amounts are large and precipitation occurs almost every day. However, the daily amount generally does not exceed 20 mm d<sup>−1</sup>. In the later part of the monsoon season (September to October) the maximum daily amount is considerably higher, while the number of rainy days decreases gradually compared to previous months. During the dry season (November to May), precipitation (mainly snow) occurs on only a few days, as it is produced by the occasional passage of westerly troughs (B. Wang [2006](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR36)). In general, the precipitation amounts increase with altitude during both the monsoon and the dry season (Seko [1987](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR29)). Mean daily air temperature from 1957 to 2002 is 0.5°C from October to June, and 8.4°C during the monsoon season at the meteorological station (3920 ma.s.l.) (Fig. [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig1)) and temperature is strongly correlated with elevation (Shiraiwa et al. [1992](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR31); Sakai et al. [2004](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR26)). The discharge regime can be classified as glacial with maximum discharges in July and August and minimum discharges during the winter season. Winter discharge is characterized by a rather constant base flow with negligible inflows of rainwater or melts water as the air temperature is generally below the melting point.

![Figure 1](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig1_HTML.gif)

**Figure 1.**

Location of Nepal and the Langtang khola catchment

## 3 Methods

The entire model is developed using the PCRaster environment for numerical modeling in environment science (Karssenberg et al. [2001](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR16)). The model is setup at a spatial resolution of 90 m (338 × 325 cells). For each cell the following model concepts are simulated at a daily time step.

### 3.1 Glaciers

We assume that the principal process for glacial movement is basal sliding. There is some evidence that in the north-western part of central Asia in the west Kunlun Shan mountains (Liu et al. [2009](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR19)), some glaciers are cold based and basal sliding does not occur, but glacial creep is the main process for glacier movement. Hewitt ([2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR12)) discusses that glaciers in the Karakoram are both cold and temperate across their length and even height and that shifts in their thermal regime may change their flow rates substantially. He ([2003](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR10)) shows that temperate glaciers are mainly found on the southern-eastern part of the Himalaya’s that is under strong influence of the monsoon. Kumar and Dobhal ([1997](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR18)) show that basal sliding is the main process of glacier movement for the Chhota Shigri glacier, which is also on the southern slopes of the Himalya’s and under strong monsoon influence. Mae et al. ([1975](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR20)) and Ageta and Higuchi ([1984](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR2)) also show that glaciers in the eastern part of Nepal are most likely warm-based. Therefore we assume that on the south-eastern part of the Himalayas, glaciers are mostly temperate given the much wetter climate, glacier morphological characteristics and the synchronous accumulation and ablation during the monsoon season. Basal sliding will be the dominant process of glacier movement in that case and this assumption is evaluated by checking the plausibility of the optimized parameters related to the basal sliding. Glacier bottom motion in that case is modeled as slow, viscous flow using Weertman’s sliding law (Weertman [1957](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR37)). It is assumed that the basal ice is at the melting point, such that a film of water is conceived to exist between the ice and the underlying bedrock. Two mechanisms are considered. The first is slow viscous deformation and the second is regelation. Regelation occurs because as the ice flows over a bedrock obstacle, the higher upstream pressure causes the ice to melt at the interface, because the melting temperature depends on pressure. The water which is thus formed squirts around the rock and correspondently refreezes on the downstream side. Weertman combines these two processes and derives the Weertman sliding law

$$
{\tau_b} \approx {\nu^2}R{u^{\frac{2}{{n + 1}}}}
$$

(1)

here *τ* <sub><em>b</em></sub> is the basal shear stress (Pa), *ν* (−) is a measure of the roughness of the bedrock, *R* is a material roughness coefficient (Pa s<sup>1/3</sup>), *u* is the sliding speed (m s<sup>-1</sup>) and *n* (−) is the creep constant of Glenn’s flow law (~3 in most cases) Glen ([1955](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR8)). The driving force of glacial movement is gravity and *τ* <sub><em>b</em></sub> is defined as

$$
{\tau_b} = \rho gH\sin (\beta )
$$

(2)

Where *ρ* (kg m<sup>-3</sup>) is the ice density, *g* is the gravitational acceleration (m s<sup>-2</sup>), *H* (m) is the ice thickness and *β* (°) is the surface slope. By combining Eqs. [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ1) and [2](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ2) under the assumption that glaciers only move when the basal shear stress exceeds the equilibrium shear stress (*τ* <sub><em>0</em></sub> (N m<sup>-2</sup>)) the sliding speed can be derived

$$
{u^{\frac{2}{{n + 1}}}} = \frac{{\rho gH\sin (\beta ) - {\tau_0}}}{{{\nu^2}R}}
$$

(3)

This equation is used to model glacial movement as function of slope, ice thickness and bedrock properties for each daily time step for each cell. Snow accumulates in the upstream parts of the catchment and each time step the sliding speed is calculated for each cell. Based on the sliding speed the ice is transported down the digital elevation model. For numerical stability and given the viscous properties of ice, the ice is not transported to a single downstream cell but is distributed proportionally to all downstream cells according to the slope. As the snow and ice is progressively moving downstream, the temperature increases and snow and ice ablation (*Q* <sub><em>a</em></sub>) occurs using a degree day factor (*ddf*). A fraction (*α*) of the total ablation leaves the catchment as runoff while, the remainder of the ablation (*1- α*) is stored in the glacier/snow pack and is released as base flow. The initial ice depth is calculated based on the known extent of the glaciers derived from remote sensing and the depth is estimated by:

$$
H = \frac{{{\tau_0}}}{{\rho g\sin (\beta )}}
$$

(4)

The *ddf* is not uniform in space but depends on both exposure and in case of glaciers on debris cover. Debris covered glaciers are insulated and melt at a much lower rate than clean ice glaciers and on south faces the incident shortwave radiation is higher and thus the *ddf* is larger than on north faces (Konz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR17)). The exposure dependence of the *ddf* on the aspect is calculated by

$$
dd{f_c} = ddf \cdot ({1} - {R_{exp}} \cdot {\text{cos(}}aspect{)})
$$

(5)

Where *ddf* <sub><em>c</em></sub> is the corrected *ddf* and *R* <sub><em>exp</em></sub> is a factor quantifying the aspect dependence of the *ddf*. For the debris covered glaciers a multiplicative reduction factor has been used and for the Lirung glacier a separate multiplicative reduction factor for the *ddf* has been used. The relative low position of the glacial snout of the Lirung glacier can only be explained by a relative low melt rate of the glacier tongue due to a thick insulating debris cover. The model parameters related to glacier modeling are shown in Table [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Tab1).

**Table 1.** Model parameters

| Parameter            | Description                                                                               | Value    | Units                            |
| -------------------- | ----------------------------------------------------------------------------------------- | -------- | -------------------------------- |
| ρ | Ice density | 916.7 | kg m<sup>-3</sup> |
| g | Gravitational acceleration | 9.81 | m s<sup>-2</sup> |
| τ<sub>0</sub> | Equilibrium shear stress | 80000 | N m<sup>-2</sup> |
| ν                    | Bedrock roughness                                                                         | 0.1      | –                                |
| R | Material roughness coefficient | 1.00E-09 | N m<sup>-2</sup> s<sup>1/3</sup> |
| Ts                   | Threshold temperature for precipitation to fall as snow                                   | 0        | °C                               |
| λ<sub>t</sub> | Temperature lapse rate | −0.0063 | °C m<sup>-1</sup> |
| ddf | Degree day factor | 6 | mm °C day<sup>-1</sup> |
| R<sub>exp</sub> | Aspect dependence of ddf | 0.2 | – |
| R<sub>debris 1</sub> | Multiplicative factor for the ddf for debris covered glaciers | 0.7 | – |
| R<sub>debris 2</sub> | Multiplicative factor for the ddf for the Lirung glacier (exceptional thick debris cover) | 0.15 | – |
| α                    | Runoff fraction of total ablation                                                         | 0.33     | –                                |
| λ<sub>p,v</sub> | Vertical precipitation lapse rate | 0.04 | % m<sup>-1</sup> |
| λ<sub>p,h</sub> | Horizontal precipitation lapse rate (negative from west to east) | −0.003 | % m<sup>-1</sup> |
| cET0 | Temperature correction factor reference evapotranspiration | −0.0918 | mm °C<sup>-1</sup> |
| K<sub>e</sub> | Reduction factor to calculate Eta | 0.8 | – |
| CN                   | Curve number                                                                              | 94       | –                                |
| θ<sub>m</sub> | Maximum soil water capacity | 0.01 | m |
| k | Recession coefficient | 0.93 | d<sup>-1</sup> |

### 3.2 Hydrological processes

The model is forced by daily precipitation and temperature data at Kyangjing from 2000 to 2007. Temperature is spatially differentiated using a vertical lapse (*λ* <sub><em>t</em></sub>) rate, which is a calibration parameter. For precipitation both a positive vertical (*λ* <sub><em>p,v</em></sub>) and a negative horizontal gradient (*λ* <sub><em>p,h</em></sub>) from west to east is applied similar to (Konz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR17)). Precipitation is partitioned in either snow (*S*) or rain (*P*) using these daily fields, the lapsed temperature fields and a threshold temperature.

Reference evapotranspiration (*ET* <sub><em>0</em></sub>) is calculated based on minimum, maximum and average temperature data at Kyangjing from 2000 to 2007 according to the Hargreaves equation (Hargreaves et al. [1985](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR9)). *ET* <sub><em>0</em></sub> is spatially differentiated per cell by applying a temperature dependent correction factor (*cET* <sub><em>0</em></sub>). This factor is derived by using the temperature dependence of the Hargreaves equation. Actual ET (*ET* <sub><em>a</em></sub>) is derived by first deriving potential evapotranspiration by multiplying *ET* <sub><em>0</em></sub> by a crop reduction factor (*K* <sub><em>e</em></sub>). By limiting potential evapotranspiration with the actual soil water content actual evapotranspiration is calculated.

On snow and ice free cells surface runoff (*Q* <sub><em>s</em></sub>) is calculated according to the curve number method (SCS USDA [1972](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR28)). The curve number (*CN*) parameter is a calibration parameter. The sum of *P-ET* <sub><em>a</em></sub> *-Q* <sub><em>s</em></sub> is then added to the soil water storage and if the maximum soil water storage (*θ* <sub><em>m</em></sub>), which is calibrated, is exceeded recharge to the groundwater occurs. Groundwater base flow (*Q* <sub><em>b</em></sub>) is modeled similar to the SWAT model (Neitsch et al. [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR23)) that is based on the work of (Smedema and Rycroft [1983](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR33)) to quantify the non-steady response of groundwater flow to recharge. Finally, for each cell the total runoff (*Q*) is calculated as the sum of *Q* <sub><em>a</em></sub> *+ Q* <sub><em>s</em></sub> *+ Q* <sub><em>b</em></sub> and routed to the catchment outlet following a recession equation similar to the Snow Melt Runoff Model (Martinec [1975](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR21)):

$$
{Q_{out,t}} = (1 - k) \cdot {Q_t} + k \cdot {Q_{out,t - 1}}
$$

(6)

Where *k* is a recession coefficient that is calibrated and *Q* <sub><em>out,t</em></sub> (m<sup>3</sup> s<sup>-1</sup>) is the river discharge at the catchment outlet on day t. The model parameters related to the hydrological processes are shown in Table [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Tab1).

### 3.3 Calibration

The model is calibrated using the Parameter ESTimation (PEST) software. PEST is able to run a model as many times as it needs to while adjusting its parameters until the discrepancies between selected model outputs and a set of observations is reduced to a minimum. The PEST algorithm method is based on non-linear parameter estimation theory (Doherty [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR7)).

The calibration procedure follows a two step approach. First the parameters related to the glacier modeling are manually calibrated as glacier evolution is a much slower process than the hydrological processes such as evapotranspiration, surface runoff, ablation and base flow. Four parameters that influence glacier evolution are calibrated (*τ* <sub><em>0</em></sub>, *R, λ* <sub><em>t</em></sub>, *ddf*). A bias corrected time series of precipitation and temperature from 1957–2002, based on the ERA40 dataset (Uppala et al. [2005](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR34)), is used to force the model with the aim to reproduce the location of glaciers and permanent snow in the year 2000 based on remote sensing (Konz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR17)). The bias correction is done similar to the corrections applied for the GCMs Eq. [7](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ7)/Eq. [9](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ9). In the second step, PEST is used and four hydrological parameters are calibrated (*θ* <sub><em>m</em></sub>, *CN, α* and *k*) by simulating the period 2000–2006 for which observations of precipitation and temperature at Kyangjing are available. The parameters are calibrated against observed daily discharges from 2000–2006 at the outlet of the catchment.

### 3.4 Downscaling GCM output

Future climate GCM data for the A1B SRES scenario (Meehl et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR22)) were used. Monthly temperature and precipitation from 2001 to 2099 were downloaded from the IPCC data distribution centre ([http://www.ipcc-data.org](http://www.ipcc-data.org)) of five different GCMs: (i) the CGCM3.1(T47) model of the Canadian Centre for Climate Modelling and Analysis (CCMA-CGCM3), the CM2.0 model of the Geophysical Fluid Dynamics Laboratory in the USA (GFDL-CM2), the ECHAM5 model of the Max Planck Institute for Meteorology in Germany (MPIM-ECHAM5), the high resolution version of the MIROC3.2 model of the National Institute for Environmental Studies in Japan (NIES-MIROC3) and the HADGEM1 model of the Hadley Centre for Climate Prediction and Research in the United Kingdom (UKMO-HADGEM1). More information and details on these models are given in (Randall et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR24)). Given that climate is highly variable in mountain areas and the resolution of the GCMs is coarse, the monthly GCM data were statistically downscaled using the 2001–2007 precipitation and temperature reference dataset of Kyangjing. The GCM data were corrected such that the monthly averages and variability during 2001–2007 matches the observations at Kyangjing similar to the procedure described in (Aerts and Droogers [2004](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR1)). First the monthly averages and standard deviations are calculated for the reference dataset and for each GCM then a correction factor is determined for the average Eq. [7](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ7) and the variation Eq. [8](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ8) in each climate parameter.

$$
{a_{adj,M}} = \frac{{\overline {{a_{obs,M}}} }}{{\overline {{a_{gcm,M}}} }}
$$

(7)

and

$$
{\sigma_{adj,M}} = \frac{{{\sigma_{obs,M}}}}{{{\sigma_{gcm,M}}}}
$$

(8)

Where a<sub>adj</sub> is the correction factor for averages, $\overline {{a_{obs}}}$ the average observed climate parameter (either average temperature or precipitation), $\overline {{a_{gcm}}}$ the average simulated climate parameter, σ<sub>adj</sub> is the correction factor for standard deviations, σ<sub>obs</sub> the standard deviation of the observed climate parameter, σ<sub>gcm</sub> the standard deviation of the simulated climate parameter and the subscript M indicates the month. From these two adjustment factors the monthly GCM values from 2001–2099 are calculated according to

$$
a_{gcm,M}^\prime = \left( {{a_{gcm,M}} - \overline {{a_{gcm,M}}} } \right) \cdot {\sigma_{adj,M}} + (\overline {{a_{gcm,M}}} \cdot {a_{adj,M}})
$$

(9)

Where a’<sub>gcm, M</sub> is the corrected climate parameter.

The monthly downscaled GCM time series from 2001 to 2099 were subsequently disaggregated into daily values by using monthly distributions of the daily 45 year ERA40 dataset from 1957–2002. The total monthly sums are equal to the downscaled GCM time series but the partitioning into daily values is based on the statistical distribution of the ERA40 dataset. This procedure resulted in a daily statistically downscaled precipitation and temperature time series from 2001 to 2099 for the five different GCMs for the Kyangjing station, which were then used to force the calibrated model. It can be expected that in the transient GCM runs both the effects as climate change (trends) as well as multi-year variability are present, such that they will be accounted for in our projections. Finally using ERA40 to simulate daily variation will assure that within month variation is properly represented. Note that further distribution of precipitation and temperature of the downscaled Kyangjing time series within the catchment is achieved by applying vertical temperature lapse rate and horizontal and vertical precipitation lapse rates (Table [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Tab1)) similar to the reference run from 2000–2007.

## 4 Results and discussion

Figure [2](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig2) compares remotely sensed glacier tongue positions (panel A) with simulation results (panel B). The model is able to simulate glacier evolution with high accuracy. After a 45 year simulation the glacier tongues are nearly in the same position as is observed by remote sensing. The green dot in the left figure also shows the snout position of the Lirung glacier as derived from GPS ground observations in August 2009. The difference between the remotely sensed position and the field observations can be explained by the 9 year time difference between the satellite image (year 2000) and 2009. However, the simulation of the glacier snout position corresponds reasonably well with the ground data and the slight difference could be due to the 7 years difference between the end of the 45 year simulation and the field work in 2009. The calibrated parameters related to glacier movement are all within realistic and plausible ranges and this confirms our assumption that glacier movement occurs mainly by basal sliding (Weertman [1957](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR37); Zhang et al. [2006](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR39); Konz et al. [2007](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR17)). We have assumed that basal sliding is the major process of glacier movement and that the resistance to glacier slip is dominated by drag over bed irregularities. Experiments have revealed however that in case of debris covered glaciers additional debris-bed resistance may further slowdown the flow velocity of debris covered glaciers (Iverson et al. [2003](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR15)). We use an overall resistance with the bedrock, but further research is recommended as to how debris-bed resistance could be parameterized in data-scarce environments.

![Figure 2](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig2_HTML.gif)

**Figure 2.**

Glacier extent in the year 2000 based on visual interpolation of Landsat image **a** and simulated ice depth in 2002 based on a 1957–2002 simulation with the calibrated model **b**

Figure [3](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig3) shows the average annual ice balance of the catchment from the 45 year simulation. Snow falls on the high elevations and is progressively transported downwards using the glacier movement equation Eq. [2](https://link.springer.com/article/10.1007/s10584-011-0143-4#Equ2). Most melt occurs on the glacier tongues and the lower melt rate on the Lirung glacier also shows in the ablation map. The net budget after 45 years of simulation is a slight thickening on the glacier tongues and a very small retreat of the snouts of most of the glacier tongues compared with the initial ice conditions that are based on the equilibrium shear stress. From these results we conclude that the cryospheric processes have been represented sufficiently realistic to allow for a climate change impact analysis.

![Figure 3](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig3_HTML.gif)

**Figure 3.**

Average annual snow fall **A**, ablation **B**, net mass balance by sliding **C** and net ice balance **D** based on a 1956–2002 simulation

Figure [4](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig4) shows the daily simulated and observed discharges at Kyangjing station. Based on these time series a number of model performance indicators were determined; the Nash-Sutcliffe model efficiency coefficient equals 0.76, the Pearson correlation coefficient is 0.87 and the bias is 3%. In addition the calibrated parameters (Table [1](https://link.springer.com/article/10.1007/s10584-011-0143-4#Tab1)) are all in a plausible range. Hence, the model is able to simulate the discharge at the outlet of the catchment realistically and with relatively high accuracy.

![Figure 4](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig4_HTML.gif)

**Figure 4.**

Simulated and observed river discharge at the Kyangjing discharge station from 2001 to 2006

Figure [5](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig5) shows that between 2000 and 2100 an annual increase in temperature of 0.06°C y<sup>-1</sup> is projected. There is considerably variability between the different GCMs but the average trend is distinctly positive and in line with global projections for the northern hemisphere. The precipitation prediction exhibits much more capricious behavior and the variability between the 5 GCMs is large. However, on average a positive precipitation trend is predicted of 1.9 mm y<sup>-1</sup> consistent with the acceleration of the hydrological cycle due to the increased atmospheric temperature (Fig. [5](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig5)). The positive temperature and precipitation trend will influence the hydrological cycle in several ways. Firstly, the higher temperatures will result in a higher reference evapotranspiration and increased melt of snow and ice. Secondly in addition to an increase in total precipitation the fraction of that falls in the form of rain instead of snow will increase. The net effect on the glacier area, total discharge and its composition, and temporal shifts in the hydrograph shifts are further quantified by our hydrological model analysis.

![Figure 5](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig5_HTML.gif)

**Figure 5.**

Downscaled annual total precipitation and average temperature for Kyangjing from 2001 to 2006. Bold line indicates the multi-model average (MMA) of 5 GCMs. Error bars indicate the 1σ of the 5 GCMs

Figures [6](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig6) and [7](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig7) show the future decrease in glacier area and glacier volume. A rapid and steady decline of the glaciers can be observed and from 2075 onwards permanent ice can only be found at the highest elevations in the catchment. By 2035 the glacier area has decreased by 32%, by 50% in 2055 and by 75% in 2088. The total ice volume shows a similar behavior but the decrease is slightly faster than the area. This catchment is representative of high altitude glacierized catchments in the central and eastern Himalayas and the findings confirm recent statements that the Himalayan glaciers are likely not to have disappeared by 2035 (Schiermeier [2010](https://link.springer.com/article/10.1007/s10584-011-0143-4#ref-CR27)). However it should be stressed that it is not possible to give a single date for the entire Himalayas. Across the Himalayas there are west to east and north to south transitions towards a warmer and wetter climate and this shows in the pattern and complexity of glacier changes being observed. Overall the Himalayan glaciers are melting, but regional anomalies exist and the rate of change is highly variable because glacier dynamics depend on the precipitation and temperature regime, topography, volume-area ratios and debris cover.

![Figure 6](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig6_HTML.gif)

**Figure 6.**

Simulated glacier extent in 2025 **A**, 2050 **B**, 2075 **C** and 2100 **D** based on forcing with MMA time series from 2001–2100

![Figure 7](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig7_HTML.gif)

**Figure 7.**

Anomalies in glacier area (*top*) and glacier ice volume (*bottom*) (% deviation from 2000). Error bars indicate 1σ of the 5 GCMs. Glaciers are defined as all pixels with an ice thickness of more than 5 m

The eventual impact of climate change on the hydrology does not merely depend on the melting of the glaciers but other factors are equally important. Our results reveal surprisingly that the total discharge is increasing between 2000 and 2100 (Fig. [8](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig8)). The mean ensemble discharge significantly increases annually with 0.05 m<sup>3</sup> s<sup>-1</sup> (~4 mm) and the increase slows down towards the end of the century. By 2050 the discharge has increased by 32%. Part of this increase can be attributed to an annual increase in net precipitation (0.03 m<sup>3</sup> s<sup>-1</sup>). The remainder is explained by the gradual change from a melt water river towards a rain river that causes the runoff coefficient to increase from 50% in 2000 to 65% in 2100.

![Figure 8](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig8_HTML.gif)

**Figure 8.**

Total MMA simulated discharge partitioned into rain runoff, glacier runoff, snow runoff and baseflow

Figures [8](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig8) and [9](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig9) also show the partitioning of stream flow in rain runoff, base flow, snow and glacier runoff. Over a period of 100 years an increase in rain runoff and baseflow is observed, the snow runoff remains constant and the glacier runoff decreases. It is interesting to note that the glacier runoff remains relatively constant until 2040 as the reduction in glacier area is compensated by the increased melt per unit area. However, after 2040 the decrease in glacier area becomes dominant leading to runoff decline. The increase in rain runoff and base flow is related to an overall increase in precipitation, a shift from rain to snow and a decrease in glacier area. It should be noted that an increase in the relative contribution of rain runoff will also results in a more direct response of river runoff to extreme dry or wet years. Figure [9](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig9) also shows that there is a large variation between the different GCMs in the partitioning of streamflow, in particular in base flow and glacier runoff. These differences can be explained by the large variation in temperature and precipitation projections between the GCMs.

![Figure 9](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig9_HTML.gif)

**Figure 9.**

Streamflow partitioning in 2005, 2025, 2050 and 2075 of the MMA. Error bars indicate the 1σ of the 5 GCMs

Figure [10](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig10) shows the monthly distribution of stream flow in 2000, 2025, 2050 and 2075 revealing a similar trend in partitioning of runoff components as in Figs. [8](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig8) and [9](https://link.springer.com/article/10.1007/s10584-011-0143-4#Fig9). A steady base flow is simulated in winter and the stream flow is highest in July during the peak of the melt and monsoon season. Shifts from glacier to rain runoff and base flow are most pronounced during the summer months. It is however interesting to note that the monthly distribution of total runoff remains relatively unchanged because the melt season coincides with the monsoon season so that no shift in runoff regime is point is lacking after observed.

![Figure 10](https://media.springernature.com/full/springer-static/image/art%3A10.1007%2Fs10584-011-0143-4/MediaObjects/10584_2011_143_Fig10_HTML.gif)

**Figure 10.**

Monthly partitioning in 2005, 2025, 2050 and 2075 of the MMA simulated discharges

## 5 Conclusions

In this study a combined cryospheric hydrological model is developed that explicitly simulates glacier movement in combination with major hydrological processes. The model is used to model the transient evolution of glaciers and hydrology under climate change. From an application of the model in the Langtang catchment in Nepal the following conclusions are drawn:

- The combination of hydrological processes and glacier movement in a high resolution raster based model enables the accurate simulation of both glacier evolution and river flow in a high altitude glacierized catchment in the Himalayas.
- Climate change analysis using downscaled data from 5 different GCMS shows that temperatures are projected to increase by 0.06°C y<sup>-1</sup> and precipitation by 1.9 mm y<sup>-1</sup>. The analysis also reveals a large variability among the different GCMs in particular for precipitation.
- In the catchment the glaciers are retreating steadily under climate change and it is estimated that in 2035 the glacier area has been reduced by 32%. This catchment is representative for the southern slopes of central and eastern Himalayas where glacier systems are dynamic, moderate in size and often characterized by debris covered tongues.
- The positive temperature and precipitation trends will increase evapotranspiration and snow and ice melt while more precipitation will fall as rain instead of snow. The net result is an increase in stream flow by 4 mm y<sup>-1</sup> that can be attributed to the increase in precipitation and the change from melt river to rain river. The partitioning of stream flow is indeed showing strong changes. Rain runoff and base flow are increasing, snow runoff remains more or less constant and glacier runoff is eventually decreasing.

This study shows an extensive analysis of a glacierized catchment in the central Himalayas but the results are not representative for the entire Himalayas. To arrive at a comprehensive assessment on how climate change is affecting the hydrology of the Himalayas it is recommendable to perform this analysis in reference catchments covering the east–west and north–south gradient in climatology and glacier and hydrological dynamics.

## References (39 total, showing 39)

- Aerts J, Droogers P (2004) Climate change in contrasting river basins: adaptation strategies for water, food, and environment. CABI, Cambridge

- Ageta Y, Higuchi K (1984) Estimation of mass balance components of a summer-accumulation type glacier in the Nepal Himalaya. *Geografiska Annaler. Series A, Physical Geography*, 66(3), p.249. Available at: http://www.jstor.org/stable/520698?origin=crossref.

- Barnett TP, Adam JC, Lettenmaier DP (2005) Potential impacts of a warming climate on water availability in snow-dominated regions. Nature 438(17):303–309

- Beniston M (2003) Climatic change in mountain regions: a review of possible impacts. Climatic Change 59:5–31

- Bolch T et al (2008) Planimetric and volumetric glacier changes in the Khumbu Himal, Nepal, since 1962 using Corona, Landsat TM and ASTER data. J Glaciol 54(187):592–600

- Cruz R et al (2007) Asia. In: Parry ML et al (eds) Climate change 2007: impacts, adaptation and vulnerability. contribution of working group II to the fourth assessment report of the intergovernmental panel on climate change. Cambridge University Press, Cambridge

- Doherty J (2005) PEST: model independent parameter estimation 5th ed. Watermark Numerical Computing, Brisbane

- Glen JW (1955) The creep of polycrystalline ice. Proc. R. Soc. Lond. A, 228:519–538

- Hargreaves GL, Hargreaves GH, Riley JP (1985) Agricultural benefits for Senegal River Basin. *Irrigation and Drainage Engr.*, ASCE 111, pp 113–124

- He Y (2003) Changing features of the climate and glaciers in China’s monsoonal temperate glacier region. J Geophys Res 108(D17):1–7

- Heuberger H et al (1984) Quaternary landslides and rock fusion in Central Nepal and in the Tyrolean Alps. Mt Res Dev 4:345–362

- Hewitt K (2007) Tributary glacier surges: an exceptional concentration at Panmah Glacier, Karakoram Himalaya. J Glaciol 53(181):181–188

- Hock R (2005) Glacier melt: a review of processes and their modelling. Progr Phys Geogr 29(3):362–391

- Immerzeel WW et al (2009) Large-scale monitoring of snow cover and runoff simulation in Himalayan river basins using remote sensing. Rem Sens Environ 113(1):40–49

- Iverson NR et al (2003) Effects of basal debris on glacier flow. Science (New York, NY) 301(5629):81–84

- Karssenberg D et al (2001) The PCRaster software and course materials for teaching numerical modelling in the environmental sciences. Transactions in GIS 5(2):99–110

- Konz M et al (2007) Implementation of a process-based catchment model in a poorly gauged, highly glacierized Himalayan headwater. Hydrol Earth Syst Sci 11(1993):1323–1339

- Kumar S, Dobhal DP (1997) Climatic effects and bedrock c ontrol on rapid fluctuations of Chhota Shigri glacier, northwest Himalaya, India. J Glaciol 43:467–472

- Liu Y et al (2009) Distribution of borehole temperature at four high-altitude Alpine Glaciers in Central Asia. J Mt Sci 6:221–227

- Mae S et al (1975) Thermail drilling and temperature measurements in Khumbu Glacier, Nepal Himalayas. Seppyo 37(161–169)

- Martinec J (1975) Snowmelt-runoff model for stream flow forecasts. Nord Hydrol 6:145–154

- Meehl GA et al (2007) Global climate projections. In: Miller HL, Solomon S, Tignor M et al (eds) Climate change 2007: the physical science basis. contribution of working group i to the fourth assessment report of the intergovernmental panel on climate change. Cambridge University Press, Cambridge

- Neitsch SL et al (2005) Soil and water assessment tool: theoretical documentation. Agricultural Research Service, Temple

- Randall DA et al (2007) Climate models and their evaluation. In: Miller HL, Solomon S, Tignor M et al (eds) Climate change 2007: the physical science basis. contribution of working group I to the fourth assessment report of the intergovernmental panel on climate change. Cambridge University Press, Cambridge

- Rees HG, Collins DN (2006) Regional differences in response of ow in glacier-fed Himalayan rivers to climatic warming. Hydrolog Process 20:2157–2169

- Sakai A, Fujita K, Kubota J (2004) Evaporation and percolation effect on melting at debris-covered Lirung Glacier, Nepal Himalayas, 1996. Bull Glacier Res 21:9–15

- Schiermeier Q (2010) Glacier estimate on thin ice. Geophys Res Lett 463(21):276–277

- SCS USDA (1972) National engineering handbook section for hydrology. In Washington, D.C.

- Seko K (1987) Seasonal variation of altitudinal dependence of precipitation in Langtang Valley, Nepal Himalayas. Bull Glacier Res 5:41–47

- Sharp M, Richards KS, Tranter M (1998) Advances in hydrological processes; glacier hydrology and hydrochemistry. Wiley, Chichester

- Shiraiwa T, Ueno K, Yamada T (1992) Distribution of mass input on glaciers in the Langtang Valley, Nepal Himalayas. Bull Glacier Res 10:21–30

- Singh P, Bengtsson L (2004) Hydrological sensitivity of a large Himalayan basin to climate change. Hydrolog Process 18(13):2363–2385

- Smedema LK, Rycroft DW (1983) Land drainage—planning and design of agricultural drainage systems. Cornell University Press, Ithica

- Uppala SM et al (2005) The ERA-40 re-analysis. Q J Roy Meteorol Soc 131(612):2961–3012

- Van de Wal RSW, Wild M (2001) Modelling the response of glaciers to climate change by applying volume-area scaling in combination with a high resolution GCM. Clim Dynam 18(3–4):359–366

- Wang B (2006) The Asian monsoon. Springer, Berlin

- Weertman J (1957) On the sliding of glaciers. J Glaciol 3:33–38

- Zemp M, Hoelzle M, Haeberli W (2009) Six decades of glacier mass-balance observations: a review of the worldwide monitoring network. *Annals of Glaciology*, 50(50), pp 101–111. Available at: http://openurl.ingenta.com/content/xref?genre=article&issn=0260-3055&volume=50&issue=50&spage=101

- Zhang Y, Liu S, Ding Y (2006) Observed degree-day factors and their spatial variation on glaciers in western China. Ann Glaciol 43(1):301–306
