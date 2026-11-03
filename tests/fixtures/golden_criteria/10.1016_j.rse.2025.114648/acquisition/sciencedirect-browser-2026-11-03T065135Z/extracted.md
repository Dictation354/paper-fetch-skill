# Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations

## Abstract

<a id="elsevier-ab0005"></a>

Tropical forests in the Amazon are characterized by a dry-season green-up, indicating a light-dominated regime in the seasonal variation of ecosystem functions. Southeast Asia, which hosts some of the most carbon-dense and diverse ecosystems in the world, is also expected to green up in dry seasons, however, recent in-situ evidence suggests otherwise. Here, we utilized high-frequency observations from the Himawari-8 geostationary satellite to examine the seasonality of vegetation greenness across Southeast Asia and to investigate potential factors driving this seasonality. We found that evergreen forests in maritime Southeast Asia green up in dry seasons, which is linked to positive anomaly in incoming radiation, similar to the Amazon forests. However, deciduous forests, croplands, and evergreen forests in continental Southeast Asia tend to green up in wet seasons, which is associated with the changes in climate sensitivities of vegetation greenness between dry and wet seasons. Our study highlights seasonal differences in tropical vegetation across biomes and sheds light on the underlying mechanisms of climate-vegetation interactions in Southeast Asia.

## 1. Introduction

<a id="elsevier-st0025"></a><a id="elsevier-s0005"></a>

Vegetation dynamics underline the variation in land-atmosphere carbon exchange and accordingly modulate many aspects of ecosystem functions. Tropical ecosystems, which host the largest land-atmosphere carbon exchange in the world ([Beer et al., 2010](#elsevier-rf0020); [Malhi, 2012](#elsevier-rf0220)), demonstrate a unique seasonal dynamic referred to as dry-season green-up ([Huete et al., 2006](#elsevier-rf0160)). Evidence from remote sensing and ground observations has shown an increase in canopy greenness and photosynthesis in Amazon forests during the periods of low rainfall ([Guan et al., 2015](#elsevier-rf0135); [Huete et al., 2006](#elsevier-rf0160); [Wang et al., 2020b](#elsevier-rf0305)). Most studies attribute this phenomenon to a coordination of anomalous high sunlight in dry seasons and the flushing of new leaves at the same time ([De Moura et al., 2017](#elsevier-rf0085); [Janssen et al., 2021](#elsevier-rf0170); [Lopes et al., 2016](#elsevier-rf0210)). The knowledge has been incorporated into Earth System Models to estimate the pan-tropical carbon cycle ([Chen et al., 2020](#elsevier-rf0070); [De Weirdt et al., 2012](#elsevier-rf0090)). However, it remains unknown whether the dry-season green-up prevails in other parts of the tropics, such as Southeast Asia, where vegetation composition ([Brearley et al., 2016](#elsevier-rf0050); [Procheş et al., 2021](#elsevier-rf0240)) and climate sensitivities ([Satriawan et al., 2024](#elsevier-rf0250)) are reported to be different from those of the Amazon.

Southeast Asia hosts some of the most carbon-dense ecosystems in the world ([Baccini et al., 2012](#elsevier-rf0005)) and is a global hotspot for biodiversity ([Estoque et al., 2019](#elsevier-rf0105); [Procheş et al., 2021](#elsevier-rf0240)). Due to the complexity of topography ([Guan et al., 2023](#elsevier-rf0140)), climate seasonality (e.g., continental and maritime monsoon seasons) ([Suepa et al., 2016](#elsevier-rf0265)) and intense anthropogenic land use (e.g., cropland expansion) ([Vadrevu and Ohara, 2020](#elsevier-rf0285)), vegetation in Southeast Asia demonstrate considerable variety and are likely to differ in its climatic dependencies. Several studies have examined the seasonality of vegetation in Southeast Asia using remote sensing or in-situ observations. However, they have reported contrasting results on the seasonality of greenness. For example, a remote sensing-based study ([Zhang et al., 2016](#elsevier-rf0370)) suggests that evergreen forests in continental Southeast Asia exhibit higher greenness in dry seasons than wet seasons (i.e., dry-season green-up), while in-situ observations ([Huete et al., 2008](#elsevier-rf0165); [Yang et al., 2023](#elsevier-rf0345)) indicate otherwise. These studies all noticed the differences in the seasonality of greenness among biomes (e.g., evergreen or deciduous forests), though there is no consensus on the specific nature of these differences. This highlights a large knowledge gap in our understanding of vegetation seasonality in Southeast Asia.

Although MODIS theoretically observes tropical land surfaces at least once a day and is suitable for detecting vegetation seasonality, persistent cloud cover severely limits the availability of clear-sky observations for analysis ([Hashimoto et al., 2021](#elsevier-rf0145); [Wilson and Jetz, 2016](#elsevier-rf0315)). In recent years, thanks to the launch of geostationary satellites (e.g., Himawari-8/9, FY-4, and GOES-16/17) that monitor the land surface at very high observation frequencies (e.g., every 10–15 minutes), it has become possible to acquire more cloud-free observations of tropical vegetation ([Wang et al., 2020a](#elsevier-rf0300); [Yan et al., 2016](#elsevier-rf0335); [Zhang et al., 2022](#elsevier-rf0385)). For example, the amount of cloud-free observations from GOES-16/17 is 21–35 times more than that from MODIS in the Amazon ([Hashimoto et al., 2021](#elsevier-rf0145)). When it comes to monitoring vegetation in Southeast Asia using geostationary satellites, the Advanced Himawari Imager (AHI) onboard the Himawari-8 geostationary satellite, with its nadir point centered at 140.7°E of the equator, offers a suitable data source for this purpose. Himawari-8 became operational on 7 July 2015 ([Bessho et al., 2016](#elsevier-rf0030)), which provides the longest continuous geostationary observations for Southeast Asia ([She et al., 2019](#elsevier-rf0260)) and over 50 times more clear-sky data than MODIS based on a site analysis (Ichii et al., 2025, *in preparation*).

Motivated by the knowledge gap on vegetation seasonality in Southeast Asia and the availability of new observations from Himawari-8, we aim to address the following two questions: (i) does vegetation in Southeast Asia show dry-season green-up? and (ii) what are the climate drivers of vegetation greenness seasonality in Southeast Asia? To do so, we used the normalized difference vegetation index (NDVI) as a proxy for vegetation greenness, which was estimated from two versions of Himawari-8 reflectance: top-of-atmosphere (TOA) reflectance and surface reflectance (SR) retrieved by the Multi-Angle Implementation of Atmospheric Correction (MAIAC) algorithm. We investigated the differences in NDVI between dry and wet seasons and employed an advanced statistical framework to examine the contributions of climate anomalies and changes in climate sensitivities of vegetation to the detected green-up signals.

## 2. Materials and methods

<a id="elsevier-st0030"></a><a id="elsevier-s0010"></a>

### 2.1. Himawari-8 data

<a id="elsevier-st0035"></a><a id="elsevier-s0015"></a>

Himawari-8 is a geostationary satellite operated by the Japan Meteorological Agency (JMA), launched on October 7, 2014 ([Bessho et al., 2016](#elsevier-rf0030)). The AHI onboard Himawari-8 captures TOA reflectance (hereafter named “Himawari-8 TOA”) in six visible and near infrared (VNIR) bands every 10 minutes ([She et al., 2019](#elsevier-rf0260); [Yu and Wu, 2016](#elsevier-rf0350)). The six bands include 0.5 km resolution for B3 (0.64 μm), 1 km resolution for B1 (0.47 μm), B2 (0.51 μm) and B4 (0.86 μm), and 2 km resolution for B5 (1.6 μm) and B6 (2.3 μm) ([Yu and Wu, 2016](#elsevier-rf0350)). TOA reflectance is influenced by complex atmospheric conditions (e.g., aerosols, water vapor and gases) ([Nazeer et al., 2021](#elsevier-rf0235)). Meanwhile, we also used a version of SR from Himawari-8, produced by the Geostationary National Aeronautics and Space Administration (NASA) Earth exchange (GeoNEX) project using the MAIAC algorithm (hereafter named “Himawari-8 SR”). The MAIAC algorithm was developed to detect clouds and cloud shadows and retrieve aerosol optical depth (AOD) and SR simultaneously from MODIS data ([She et al., 2019](#elsevier-rf0260)). It has been proven to be a robust method for remote sensing studies in tropical environment ([Guan et al., 2015](#elsevier-rf0135); [Hilker et al., 2015](#elsevier-rf0150)). Its Quality Assurance (QA) bands provide the information on different confidence levels of cloud masks (e.g., clear, possibly cloudy, cloudy, and cloud shadow) ([She et al., 2019](#elsevier-rf0260)). The Himawari-8 SR products utilized the highest confidence level of cloud masks to ensure the retention of the clearest possible observations.

### 2.2. MODIS data

<a id="elsevier-st0040"></a><a id="elsevier-s0020"></a>

To provide a reference for the performance of Himawari-8 data, we also used MODIS NDVI in this study. The MODIS NDVI is retrieved from the MODIS MCD19A3CMG (v061), a daily cloud-cleared vegetation index product estimated from MODIS MAIAC reflectance at a spatial resolution of 0.05°. The MODIS MAIAC data undergo a series of processing procedures, including cloud screening, atmospheric correction, and bidirectional reflectance distribution function (BRDF) normalization applied to raw MODIS TOA reflectance ([De Moura et al., 2017](#elsevier-rf0085); [Lyapustin et al., 2011](#elsevier-rf0215)), and have been widely used in tropical vegetation studies ([Bi et al., 2015](#elsevier-rf0035); [De Moura et al., 2017](#elsevier-rf0085); [Hashimoto et al., 2021](#elsevier-rf0145)). In this study, we used two versions of MODIS products from MCD19A3CMG (v061): NDVI based on SR (hereafter named “MODIS SR”) and NDVI based on BRDF-normalized SR (nadir view and solar zenith angle = 45°) (hereafter named “MODIS BRDF-normalized SR”). We resampled all NDVI datasets (i.e., Himawari-8 TOA, Himawari-8 SR, MODIS SR and MODIS BRDF-normalized SR) to a uniform spatial resolution of 0.1° to match climate data using the Pixel Aggregation method.

### 2.3. Land cover map

<a id="elsevier-st0045"></a><a id="elsevier-s0025"></a>

We used the land cover map from the European Space Agency Climate Change Initiative (ESA CCI) (v2.1.1) at a spatial resolution of 300 m, which was produced to ensure temporal consistency by merging multiple global reflectance products ([Li et al., 2018](#elsevier-rf0200)). It comprises 37 categories based on the United Nations Land Cover Classification System and demonstrates the highest overall accuracy compared to other similar-resolution land cover products (e.g., MCD12Q1, GLC, IGBP, and UMD) ([Yang et al., 2017](#elsevier-rf0340)). We further simplified the land cover map into 7 classes: evergreen forests, deciduous forests, croplands, mosaics (e.g., a mix of types not matching any of other definitions), others (e.g., shrublands and grasslands), non-vegetation (e.g., urban and built-up lands) and water bodies in our study ([Fig. A1](#elsevier-f0060)). To match the spatial resolution with the above-mentioned NDVI products and maintain the classification scheme, we resampled the land cover map into 0.1° using the Nearest Neighbour method. We did not use MODIS land cover product in this study due to its potential misclassification of a substantial portion of savanna and the underestimation of deciduous forest extent in tropical Asia ([Fang et al., 2013](#elsevier-rf0110)).

### 2.4. Climate data

<a id="elsevier-st0050"></a><a id="elsevier-s0030"></a>

ERA5-Land, a reanalysis dataset that combines model data from the Integrated Forecasting System (IFS) with observations, provides hourly climate variables at an enhanced resolution (0.1°) compared to ERA5 ([Gomis-Cebolla et al., 2023](#elsevier-rf0120)). From the ERA5-Land dataset, we extracted hourly air temperature ($T$), dewpoint temperature ($T_{d}$), total precipitation ($\mathit{PRE}$), solar radiation ($\mathit{RAD}$), and volumetric soil water ($\mathit{VSW}$) in layers 1 (0–7 cm) and 2 (7–28 cm). The soil water content ($\mathit{SWC}$) was the weighted mean of the $\mathit{VSW}$ from two layers, and the vapor pressure deficit ($\mathit{VPD}$) was calculated using Eq. [(1)](#elsevier-fo0005) ([Barkhordarian et al., 2019](#elsevier-rf0015); [Behrangi et al., 2016](#elsevier-rf0025); [Weiss et al., 2012](#elsevier-rf0310)):

<a id="elsevier-fo0005"></a>

**(1)**

$$

\mathit{VPD} = c_{1} \times \mathit{exp}\left(\frac{c_{2} \times T}{c_{3} + T} \right) - c_{1} \times \mathit{exp}\left(\frac{c_{2} \times T_{d}}{c_{3} + T_{d}} \right)

$$

where $c_{1}$, $c_{2}$, and $c_{3}$ are equal to 0.611, 17.5 and 240.978, respectively. $T$ and $T_{d}$ represent air temperature and dewpoint temperature in °C, and $\mathit{VPD}$ refers to the vapor pressure deficit in kPa. The first and second terms in Eq. [(1)](#elsevier-fo0005) represent the saturated vapor pressure ($e_{s}$) and actual vapor pressure ($e_{a}$), respectively.

### 2.5. Reconstructing daily and 16-day NDVI time series

<a id="elsevier-st0055"></a><a id="elsevier-s0035"></a>

To minimize the diurnal sun-angle variations, we calculated the daytime (i.e., 9 a.m. to 3 p.m. local time) 10-minute NDVI time series from Himawari-8 TOA and SR data using Eq. [(2)](#elsevier-fo0010):

<a id="elsevier-fo0010"></a>

**(2)**

$$

\mathit{NDVI} = \frac{B_{4} - B_{3}}{B_{4} + B_{3}}

$$

where $B_{3}$ and $B_{4}$ represent the red (0.64 μm) and NIR (0.86 μm) reflectance of Himawari-8 TOA and SR, respectively. As one of the most common proxies of vegetation greenness, NDVI effectively captures and reflects vegetation characteristics ([Zeng et al., 2022](#elsevier-rf0360)) and is not sensitive to both atmospheric effects ([Chen et al., 2003](#elsevier-rf0065)) and seasonal changes in sun-sensor geometry in the tropics ([Morton et al., 2014](#elsevier-rf0230)). We then resampled the 10-minute NDVI time series into the daily time series using the maximum value composite (MVC) method ([Fig. 1](#elsevier-f0005)a and c). The MVC method is conventionally used to minimize cloud and atmospheric effects on NDVI time series by outputting the highest NDVI value in a defined time interval ([Hashimoto et al., 2021](#elsevier-rf0145); [Tian et al., 2021](#elsevier-rf0275)). We used the 95<sup>th</sup> percentile values instead of the highest NDVI values to reduce the impact of abnormally high outliers (e.g., highlighted in [Fig. 1](#elsevier-f0005)a). To assess the performance of Himawari-8 NDVI, we also extracted daily NDVI from the MODIS SR product. Since daily NDVI time series are still susceptible to cloud contamination and abnormal values, we further employed two common approaches to smooth the daily Himawari-8 and MODIS NDVI time series: penalized cubic splines (SP) filter and MVC method ([Tian et al., 2021](#elsevier-rf0275)) ([Fig. 1](#elsevier-f0005)). The former generates a smoothed daily and gap-free NDVI time series and has been used to produce official phenology products (e.g., MODIS MCD12Q2) ([Moon et al., 2019](#elsevier-rf0225)). The latter generates a smoothed 16-day NDVI time series and has also been incorporated into some official vegetation index datasets (e.g., MODIS MOD/MYD13) ([Huete et al., 2002](#elsevier-rf0155)). Even so, it is worth noting that the 16-day MODIS NDVI time series may still contain the gaps when no data are available over a given 16-day period, in which cases we used linear interpolation to fill these gaps ([Fig. 1](#elsevier-f0005)b and d). Considering the potential saturation effects of NDVI ([Gao et al., 2023](#elsevier-rf0115), [Gao et al., 2000](#elsevier-or0005); [Zeng et al., 2023](#elsevier-rf0365)), we also calculated the enhanced vegetation index (EVI) from the Himawari-8 TOA and SR products using Eq. [(3)](#elsevier-fo0015) and repeated the steps of the above NDVI processing.

<a id="elsevier-fo0015"></a>

**(3)**

$$

\mathit{EVI} = 2.5 \times \frac{B_{4} - B_{3}}{B_{4} + 6 \times B_{3} - 7.5 \times B_{1} + 1}

$$

where $B_{1}$, $B_{3}$ and $B_{4}$ represent the blue (0.47 μm), red (0.64 μm) and NIR (0.86 μm) reflectance of Himawari-8, respectively.

![Figure 1](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr1_lrg.jpg)

<a id="elsevier-f0005"></a>Fig. 1. The concept diagrams illustrate the processing of NDVI time series. (a) and (b) display the processing of Himawari-8 SR and MODIS SR NDVI time series for a specific pixel in continental Southeast Asia (104.9E, 15.1 N). (c) and (d) show the same processing for a specific pixel in maritime Southeast Asia (111.6E, 1.1S). The pale green shaded areas in the background indicate the dates with no available clear observations. SR: surface reflectance. SP filter: penalized cubic splines filter. MVC method: maximum value composite method. The red arrow in (a) points to an example of an abnormally high value. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


### 2.6. Defining dry and wet seasons

<a id="elsevier-st0060"></a><a id="elsevier-s0040"></a>

To define dry and wet seasons for each pixel, we first extracted the start and end of the wet season (i.e., SWS and EWS) from the ERA5-Land daily precipitation time series using Eq. [(4)](#elsevier-fo0020) ([Dunning et al., 2016](#elsevier-rf0095); [Jiang et al., 2019](#elsevier-rf0180); [Tian et al., 2024](#elsevier-rf0280); [Xu et al., 2021](#elsevier-rf0325)).

<a id="elsevier-fo0020"></a>

**(4)**

$$

C(d) = \sum_{i = 1\mathit{Jan}}^{d}Q_{i} - \overline{Q}

$$

where $C(d)$ is the cumulative daily precipitation anomaly. $Q_{i}$ refers to the daily precipitation, and $\overline{Q}$ represents the mean precipitation throughout the year. $C_{\mathit{min}}$ and $C_{\mathit{max}}$ dates are extracted from the smoothed $C(d)$ processed by a Gaussian filter, corresponding to the SWS and EWS, respectively. The period between SWS and EWS constituted the wet season, and the remaining period in each calendar year is considered the dry season ([Fig. 2](#elsevier-f0010)a). Considering that some tropical regions experience two alternations of dry-wet seasons, we employed harmonic analysis to quantify the number of dry-wet seasons each year by a Fourier transform of the entire daily precipitation time series ([Liebmann et al., 2012](#elsevier-rf0205); [Tian et al., 2024](#elsevier-rf0280); [Xu et al., 2021](#elsevier-rf0325)). Regions with a harmonic ratio greater than one were identified as having two cycles of dry-wet seasons ([Tian et al., 2024](#elsevier-rf0280); [Xu et al., 2021](#elsevier-rf0325)). For these regions, the dry and wet seasons of each alternation were defined, respectively ([Fig. 2](#elsevier-f0010)b).

![Figure 2](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr2_lrg.jpg)

<a id="elsevier-f0010"></a>Fig. 2. The concept diagrams demonstrate the definitions of single and double dry-wet cycles for two specific pixels (a) (106.4E, 21.1 N) and (b) (101.9E, 2.7 N), respectively. The blue shaded areas indicate the duration of the wet season, and the yellow solid lines represent the mean precipitation. SWS: the start of the wet season. EWS: the end of the wet season. SWS1 and EWS1 denote the start and end of the first wet season, while SWS2 and EWS2 indicate the start and end of the second wet season. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


### 2.7. Identifying the climate factors driving green-up of vegetation

<a id="elsevier-st0065"></a><a id="elsevier-s0045"></a>

To examine the green-up of vegetation in dry or wet seasons for each pixel, we calculated the NDVI anomaly (i.e., $\mathrm{\Delta}\mathit{NDVI}$) and its difference between dry and wet seasons (i.e., $\mathit{NDVI}_{d - w}$) using Eqs. [(5)](#elsevier-fo0025), [(6)](#elsevier-fo0030).

<a id="elsevier-fo0025"></a>

**(5)**

$$

\mathrm{\Delta}\mathit{NDVI} = \mathit{NDVI} - \overline{\mathit{NDVI}}

$$

<a id="elsevier-fo0030"></a>

**(6)**

$$

\mathit{NDVI}_{d - w} = \overline{\mathit{NDVI}_{\mathit{dry}}} - \overline{\mathit{NDVI}_{\mathit{wet}}}

$$

where $\mathit{NDVI}$ refers to the NDVI time series processed by the SP filter or MVC method, and $\overline{\mathit{NDVI}}$ represents the mean of the NDVI time series throughout the entire year. $\overline{\mathit{NDVI}_{\mathit{dry}}}$ and $\overline{\mathit{NDVI}_{\mathit{wet}}}$ represent the mean of $\mathrm{\Delta}\mathit{NDVI}$ in dry and wet seasons, respectively. Positive $\mathit{NDVI}_{d - w}$ values indicate the green-up of vegetation in dry seasons, while negative $\mathit{NDVI}_{d - w}$ values suggest the green-up of vegetation in wet seasons. Subsequently, we further quantified the contribution of climate factors driving the seasonality of vegetation greenness for each pixel. Based on previous studies, we selected four underlying factors for the analysis: $T$ ([Zhang et al., 2016](#elsevier-rf0370)), $\mathit{SWC}$ ([Borchert, 1994](#elsevier-rf0040); [Vico et al., 2015](#elsevier-rf0290)), $\mathit{RAD}$ ([Bi et al., 2015](#elsevier-rf0035); [Huete et al., 2006](#elsevier-rf0160)) and $\mathit{VPD}$ ([Brando et al., 2010](#elsevier-rf0045); [Green et al., 2020](#elsevier-rf0130)). We used a multiple regression method ([Wang et al., 2018](#elsevier-rf0295); [Zhu et al., 2016](#elsevier-rf0390)) to quantify the climate sensitivities of each factor. To minimize the effects of collinearity among climate factors, we conducted a reduced variable regression analysis ([Wang et al., 2018](#elsevier-rf0295)) based on Eq. [(7)](#elsevier-fo0035).

<a id="elsevier-fo0035"></a>

**(7)**

$$

Y_{\mathit{NDVI}} = \gamma_{T} \times \mathrm{\Delta}_{T} + \gamma_{\mathit{SWC}} \times \mathrm{\Delta}_{\mathit{SWC}} + \gamma_{\mathit{RAD}} \times \mathrm{\Delta}_{\mathit{RAD}} + \gamma_{\mathit{VPD}} \times \mathrm{\Delta}_{\mathit{VPD}} + \varepsilon

$$

where $Y_{\mathit{NDVI}}$ represents the standardized daily NDVI anomalies in dry or wet seasons using the z-score function, a statistical measure that centers and scales data (mean: 0 and standard deviation: 1) ([Barbosa et al., 2006](#elsevier-rf0010); [Li et al., 2013](#elsevier-rf0195)). This process ensures that data from different distributions are directly comparable. $\mathrm{\Delta}_{T}$, $\mathrm{\Delta}_{\mathit{SWC}}$, $\mathrm{\Delta}_{\mathit{RAD}}$, and $\mathrm{\Delta}_{\mathit{VPD}}$ correspond to the standardized climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry or wet seasons using the z-score function. The $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients using least square (LSQ) estimates with a 95% confidence interval, and $\varepsilon$ refers to unexplained variation of regression models. For each reduced variable regression, the residuals ($e$), i.e., the differences between each observation and estimate from the regression models, were further employed to evaluate the climate sensitivity of the excluded variable using Eq. [(8)](#elsevier-fo0040).

<a id="elsevier-fo0040"></a>

**(8)**

$$

e = \sigma \times \mathit{factor}

$$

where $\sigma$ is the regression coefficient using LSQ with a 95% confidence interval and reflects the sensitivity of NDVI to each climate factor. Positive and negative $\sigma$ values represent the positive and negative climate sensitivities of vegetation greenness to climate factors, respectively. The $\mathit{factor}$ means $\mathrm{\Delta}_{T}$, $\mathrm{\Delta}_{\mathit{SWC}}$, $\mathrm{\Delta}_{\mathit{RAD}}$, and $\mathrm{\Delta}_{\mathit{VPD}}$. Eq. [(7)](#elsevier-fo0035) suggests that climate anomalies and climate sensitivities jointly contribute to NDVI seasonality. Therefore, we decomposed and quantified the contributions of seasonal greenness changes (i.e., $\mathit{NDVI}_{d - w}$) into ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by changes in climate sensitivities) using Eqs. [(9)](#elsevier-fo0045), [(10)](#elsevier-fo0050), [(11)](#elsevier-fo0055), [(12)](#elsevier-fo0060).

<a id="elsevier-fo0045"></a>

**(9)**

$$

{\mathit{NDVI}_{d - w}}_{\mathit{cli}} = \mathit{NDVI}_{\mathit{dry}}' - \mathit{NDVI}_{\mathit{wet}}

$$

<a id="elsevier-fo0050"></a>

**(10)**

$$

{\mathit{NDVI}_{d - w}}_{\mathit{sen}} = {\mathit{NDVI}_{d - w}}_{\mathit{total}} - {\mathit{NDVI}_{d - w}}_{\mathit{cli}}

$$

<a id="elsevier-fo0055"></a>

**(11)**

$$

\mathit{NDVI}_{\mathit{dry}}' = \gamma_{T_{\mathit{wet}}} \times \mathrm{\Delta}_{T_{\mathit{dry}}} + \gamma_{\mathit{SWC}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{SWC}_{\mathit{dry}}} + \gamma_{\mathit{RAD}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{RAD}_{\mathit{dry}}} + \gamma_{\mathit{VPD}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{VPD}_{\mathit{dry}}} + \varepsilon

$$

<a id="elsevier-fo0060"></a>

**(12)**

$$

{\mathit{NDVI}_{d - w}}_{\mathit{total}} = \mathit{NDVI}_{\mathit{dry}} - \mathit{NDVI}_{\mathit{wet}}

$$

where ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ are $\mathit{NDVI}_{d - w}$ values induced by climate anomalies and the changes in climate sensitivities, respectively. Considering that both climate anomalies and climate sensitivities to vegetation greenness are different between dry and wet seasons, we introduced an intermediate variable (i.e., $\mathit{NDVI}_{\mathit{dry}}'$). $\mathit{NDVI}_{\mathit{dry}}'$ refers to the NDVI anomalies in dry seasons when climate sensitivities to vegetation greenness are assumed to be consistent with those in wet seasons (i.e., using climate sensitivities of vegetation greenness in wet seasons: $\gamma_{T_{\mathit{wet}}}$, $\gamma_{\mathit{SWC}_{\mathit{wet}}}$, $\gamma_{\mathit{RAD}_{\mathit{wet}}}$ and $\gamma_{\mathit{VPD}_{\mathit{wet}}}$). $\mathrm{\Delta}_{T_{\mathit{dry}}}$, $\mathrm{\Delta}_{\mathit{SWC}_{\mathit{dry}}}$, $\mathrm{\Delta}_{\mathit{RAD}_{\mathit{dry}}}$ and $\mathrm{\Delta}_{\mathit{VPD}_{\mathit{dry}}}$ are standardized climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry seasons, and $\varepsilon$ refers to unexplained variation of regression models. ${\mathit{NDVI}_{d - w}}_{\mathit{total}}\hspace{0.25em}$represents the total NDVI anomalies between dry and wet seasons.

## 3. Results

<a id="elsevier-st0070"></a><a id="elsevier-s0050"></a>

### 3.1. The length of dry and wet seasons in Southeast Asia

<a id="elsevier-st0075"></a><a id="elsevier-s0055"></a>

Considering the complexity of dry-wet seasonality across Southeast Asia, we used a harmonic analysis on daily precipitation time series to determine whether each pixel experiences a single or double cycles of dry-wet seasons ([Fig. 2](#elsevier-f0010)) (see Materials and methods). We found that 83.3% of regions in Southeast Asia, including continental Southeast Asia, southern maritime Southeast Asia and the majority of New Guinea, experienced a single dry-wet cycle annually ([Fig. 3](#elsevier-f0015)e). In comparison, 16.7% of regions in Southeast Asia, distributed along the equator, experienced double dry-wet cycles each year (harmonic ratio &gt; 1) ([Fig. 3](#elsevier-f0015)d-f) (see Materials and methods). Across Southeast Asia, the dry season (mean: 195.1 days) was typically longer than that of the wet season (mean: 169.9 days) ([Fig. 3](#elsevier-f0015)a-c).

![Figure 3](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr3_lrg.jpg)

<a id="elsevier-f0015"></a>Fig. 3. Spatial patterns of the length of dry and wet seasons in 2019 in Southeast Asia. Spatial patterns of (a) dry-season length and (b) wet-season length, (d) harmonic ratio and (e) cycles of dry-wet seasons. Regions with a harmonic ratio greater than one were identified as having double cycles of dry-wet seasons (see Materials and methods). (c) Histograms summarize the length of dry and wet seasons, and dotted lines indicate their mean values. (f) Histogram summarizes the values of the harmonic ratio, and dotted lines indicate the reference line of one. The numbers 1 and 2 in (e) indicate the locations of [Fig. 2](#elsevier-f0010) (a) and (b).


### 3.2. The differences in vegetation greenness between dry and wet seasons

<a id="elsevier-st0080"></a><a id="elsevier-s0060"></a>

Himawari-8 SR NDVI and MODIS SR NDVI showed substantial spatial differences in the seasonality of vegetation greenness, especially in maritime Southeast Asia ([Fig. 4](#elsevier-f0020), [Fig. 5](#elsevier-f0025)). We found that Himawari-8 SR NDVI showed 42.1% positive $\mathit{NDVI}_{d - w}$ (i.e., green-up in dry seasons) and 57.9% negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons), with dry-season green-up prevailing in the majority of maritime Southeast Asia and wet-season green-up occurring in continental Southeast Asia ([Fig. 4](#elsevier-f0020)a and c). On the contrary, MODIS SR NDVI exhibited negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons) in the majority of Southeast Asia, accounting for 82.1% of the regions ([Fig. 4](#elsevier-f0020)b and c). To test the robustness of the green-up signals, we replaced the SP smoothing method with the MVC method to reconstruct the NDVI time series and repeated the analysis. We found that the difference between Himawari-8 SR NDVI and MODIS SR NDVI in greenness seasonality remained ([Fig. 4](#elsevier-f0020), [Fig. 5](#elsevier-f0025)), i.e., Himawari-8 SR NDVI can capture more dry-season green-up signals than MODIS SR NDVI. Based on the robustness of the high-frequency observations from Himawari-8 SR products across processing methods ([Fig. 4](#elsevier-f0020), [Fig. 5](#elsevier-f0025) and [Fig. A2](#elsevier-f0065)), we opted to use the results from SP-processed Himawari-8 SR NDVI (Fig. 4a) for our subsequent analysis.

![Figure 4](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr4_lrg.jpg)

<a id="elsevier-f0020"></a>Fig. 4. Spatial patterns of the differences in vegetation greenness (i.e., NDVI) in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) were calculated from daily NDVI time series acquired from (a) Himawari-8 SR and (b) MODIS SR, processed by the penalized cubic splines (SP) filter. The $\mathit{NDVI}_{d - w}$ values were calculated from the 16-day NDVI time series acquired from (d) Himawari-8 SR and (e) MODIS SR, processed by the maximum value composite (MVC) method. (c) and (f) summarize their values by latitude, and the solid lines indicate the mean values. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). The shaded error bars in (c) and (f) indicate the mean ± standard deviation. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


![Figure 5](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr5_lrg.jpg)

<a id="elsevier-f0025"></a>Fig. 5. The glyph-maps of NDVI time series in 2019 derived from Himawari-8 and MODIS for each sub-region in Southeast Asia. (a) and (c) are the glyph-maps of regional average NDVI processed by the penalized cubic splines (SP) filter and the maximum value composite (MVC) method (see Materials and methods). (b) and (d) are zoom-in regions corresponding to the sub-regions in (a) and (c), and the colour of the box border indicates the location of the regions. Each grid cell covers a 6° × 9° space. Grid cells marked with crosses indicate no available data or no land surface in the cell.


Considering the potential saturation effects of NDVI, we also calculated the differences in the EVI between dry and wet seasons (see Materials and methods). We found that $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ derived from Himawari-8 SR products showed high agreement for both data processing methods ([Fig. A3](#elsevier-f0070)). Additionally, to examine the potential effects of BRDF on NDVI, we have also validated our results by comparing MODIS SR NDVI and MODIS BRDF-normalized SR NDVI (nadir view and solar zenith angle = 45°) (see Materials and methods). As expected, our results confirmed their high consistencies (R-squared: 0.86 for the SP filter and 0.80 for the MVC method) ([Fig. A4](#elsevier-f0075)). This analysis, in combination with a preliminary examination of the BRDF effects on geostationary-derived NDVI ([Seong et al., 2020](#elsevier-rf0255)), suggested that the BRDF has limited impacts on NDVI seasonality, though it might affect the magnitude of NDVI values.

### 3.3. Climate drivers for the seasonality of greenness

<a id="elsevier-st0085"></a><a id="elsevier-s0065"></a>

Across Southeast Asia, the climate anomalies and climate sensitivities of vegetation greenness between dry and wet seasons differ considerably ([Fig. 6](#elsevier-f0030) and [Fig. A5](#elsevier-f0080)). Wet seasons exhibited higher $T$ (air temperature) and $\mathit{SWC}$ (soil water content), but lower $\mathit{RAD}$ (solar radiation) and $\mathit{VPD}$ (vapor pressure deficit) compared to dry seasons ([Fig. 6](#elsevier-f0030)a-d). On average, the differences in $T$, $\mathit{SWC}$, $\mathit{RAD}$ and $\mathit{VPD}$ between dry and wet seasons were −0.83 °C, −0.09 m<sup>3</sup>m<sup>−3</sup>, 1.74\*10<sup>6</sup> Jm<sup>−2</sup>, and 0.34 kPa, respectively. We also found significant latitude-based differences in the climate sensitivities of vegetation greenness between dry and wet seasons ([Fig. 6](#elsevier-f0030)e-h). Specifically, across Southeast Asia, the sensitivity of vegetation greenness to temperature ($\gamma_{T}$) was weaker in dry seasons compared to wet seasons (Fig. 6e and [Fig. A5](#elsevier-f0080)i and m), suggesting that vegetation greenness decreased faster with temperature in wet seasons. The sensitivities of vegetation greenness to water stress (i.e., $\mathit{SWC}$ and $\mathit{VPD}$), $\gamma_{\mathit{SWC}}$ and $\gamma_{\mathit{VPD}}$ showed more significant differences in continental and maritime Southeast Asia, respectively ([Fig. 6](#elsevier-f0030)f and h, and [Fig. A5](#elsevier-f0080)j, n, l and p), especially for $\gamma_{\mathit{SWC}}$. This indicates that vegetation greenness is more sensitive to $\mathit{SWC}$ in continental Southeast Asia in dry seasons. The sensitivity of vegetation greenness to solar radiation ($\gamma_{\mathit{RAD}}$) also exhibited clear differences in continental Southeast Asia, with the $\gamma_{\mathit{RAD}}$ changing from positive in wet seasons to negative in dry seasons ([Fig. 6](#elsevier-f0030)g and [Fig. A5](#elsevier-f0080)k and o). Our analysis suggested that climate sensitivities of vegetation greenness between dry and wet seasons played important roles in modulating the seasonality of vegetation greenness across Southeast Asia.

![Figure 6](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr6_lrg.jpg)

<a id="elsevier-f0030"></a>Fig. 6. Comparison of (a)-(d) climate anomalies and (e)-(h) climate sensitivities of vegetation greenness in dry and wet seasons across different latitudes. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ correspond to the climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry and wet seasons. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients (i.e., climate sensitivities of vegetation greenness) corresponding to each climate factor (see Materials and methods). The solid lines represent the mean values, while the dotted lines indicate reference lines of zero. The cross symbols (×) at each degree of latitude denote statistical significance between dry and wet seasons (*p* ≤ 0.001, *t*-test). The shaded error bars indicate the mean ± standard deviation.


### 3.4. Differences among different vegetation types

<a id="elsevier-st0090"></a><a id="elsevier-s0070"></a>

To assess the contributions of climate anomalies and changes in climate sensitivities to greenness seasonality, we decomposed changes in NDVI (i.e., $\mathit{NDVI}_{d - w}$) into ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by the changes in climate sensitivities) (see Materials and methods). We found a positive contribution of climate anomalies to vegetation greenness (i.e., positive ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$) in maritime Southeast Asia ([Fig. 7](#elsevier-f0035)a and c), while the changes in climate sensitivities mostly exhibited a negative impact on NDVI (i.e., negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$) in continental Southeast Asia ([Fig. 7](#elsevier-f0035)b and c). We further examined the differences in $\mathit{NDVI}_{d - w}$, ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ across main vegetation types in Southeast Asia, including evergreen forests, deciduous forests and croplands ([Fig. A1](#elsevier-f0060)). We found that $\mathit{NDVI}_{d - w}$ for maritime evergreen forests tended to be positive (i.e., green-up in dry seasons), but $\mathit{NDVI}_{d - w}$ for deciduous forests, croplands and continental evergreen forests were mostly negative (i.e., green-up in wet seasons) (Fig. 7d). The maritime evergreen forests showed positive ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$, while others vegetation types showed negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ at different levels ([Fig. 7](#elsevier-f0035)e and f). The sum of ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ determined the observed seasonality. Specifically, for maritime evergreen forests, we found that climate anomalies drove the green-up in dry seasons, though this effect was partly offset by changes in climate sensitivities ([Fig. 7](#elsevier-f0035)d-f). For deciduous forests, croplands and continental evergreen forests, due to stronger effects of the changes in climate sensitivities, they appeared to green up in wet seasons ([Fig. 7](#elsevier-f0035)d-f).

![Figure 7](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr7_lrg.jpg)

<a id="elsevier-f0035"></a>Fig. 7. Spatial patterns of $\mathit{NDVI}_{d - w}$ induced by climate anomalies and the changes in climate sensitivities. (a) and (b) are spatial patterns of ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by the changes in climate sensitivities), respectively. (c) summarizes the values by latitude. The solid lines indicate the mean values, and the shaded error bars indicate the mean ± standard deviation. Violin and box plots summarize the values of (d) $\mathit{NDVI}_{d - w}$, (e) ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and (f) ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ for four vegetation types. EF<sub>con</sub>: continental evergreen forests. EF<sub>mar</sub>: maritime evergreen forests. DF: deciduous forests. CL: croplands. \*\*\*: *p* ≤ 0.001. non-significance (ns): *p* &gt; 0.05. *n*: number of pixels.


## 4. Discussion

<a id="elsevier-st0095"></a><a id="elsevier-s0075"></a>

In this study, we examined the seasonality of vegetation greenness in Southeast Asia using new observations from a geostationary satellite (i.e., Himawari-8). We found that across Southeast Asia, 42.1% of the regions (mainly maritime evergreen forests) showed positive $\mathit{NDVI}_{d - w}$ (i.e., green-up in dry seasons), while 57.9% of the regions (mainly deciduous forests, croplands and continental evergreen forests) showed negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons) ([Fig. 7](#elsevier-f0035)d). Meanwhile, we found that both climate anomalies and the changes in climate sensitivities of vegetation greenness between dry and wet seasons imposed impacts on $\mathit{NDVI}_{d - w}$, with climate anomalies driving green-up in dry seasons but changes in climate sensitivities of vegetation greenness driving green-up in wet seasons ([Fig. 7](#elsevier-f0035)). We found that the seasonality of vegetation greenness in Southeast Asia was governed by the interplay of these two processes.

We utilized new observations from the geostationary Himawari-8 satellite to detect the seasonality of vegetation greenness in Southeast Asia and found spatially inconsistent results compared to those from MODIS ([Fig. 4](#elsevier-f0020)). The difference likely arises from the numbers of clear observations from two sensors, as optical sensors are often obscured by persistent cloud cover in the tropics ([Hashimoto et al., 2021](#elsevier-rf0145); [Wilson and Jetz, 2016](#elsevier-rf0315)). We further analyzed the ratios of clear observations from the Himawari-8 and MODIS products. The numbers of clear observations from Himawari-8 SR and MODIS SR were extracted from their respective cloud mask bands. We found that on an annual basis, Himawari-8 provided 43.5% more clear daily observations and 18.4% more clear 16-day observations than those of MODIS ([Fig. 8](#elsevier-f0040)i). Based on this, we further found that in the regions where Himawari-8 and MODIS reported conflicting seasonality, there were greater differences in the number of clear observations between the two sensors ([Fig. 9](#elsevier-f0045)). The increase in the availability of clear observations enables geostationary satellites (e.g., Himawari-8) to capture the seasonality of tropical vegetation greenness more effectively than optical polar-orbit satellites (e.g., MODIS). Meanwhile, we also acknowledge recent progress in using spatiotemporal observations from polar-orbit satellites to statistically address the cloud issues in the tropics and reconstruct long-term vegetation index series ([Cai et al., 2025](#elsevier-rf0055); [Cao et al., 2018](#elsevier-rf0060)). These methods can complement geostationary observations, which often have shorter temporal coverage.

![Figure 8](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr8_lrg.jpg)

<a id="elsevier-f0040"></a>Fig. 8. Spatial patterns of the ratio of clear observations for the daily and 16-day time series in 2019. Spatial patterns of the ratio of Himawari-8-derived clear observations for the (a) daily and (d) 16-day time series in 2019. Spatial patterns of the ratio of MODIS-derived clear observations for the (b) daily and (e) 16-day time series in 2019. Spatial patterns of the differences in the ratio of Himawari-8- and MODIS-derived clear observations for the (g) daily and (h) 16-day time series in 2019. (c), (f) and (i) summarize their values by latitude, and the solid lines indicate the mean values. The shaded error bars in (c), (f) and (i) indicate the mean ± standard deviation.


![Figure 9](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr9_lrg.jpg)

<a id="elsevier-f0045"></a>Fig. 9. The relationship between the number of conflicting $\mathit{NDVI}_{d - w}$ pixels (i.e., opposite seasonality detected by Himawari-8 SR NDVI and MODIS SR NDVI) and their differences in the ratio of clear observations. The pie in each sub-figure represents the number of conflicting $\mathit{NDVI}_{d - w}$ pixels. SP filter: penalized cubic splines filter. MVC method: maximum value composite method.


Our study reported that the green-up of maritime evergreen forests in dry seasons is primarily driven by relatively higher radiation levels ([Fig. 10](#elsevier-f0050)g). This result is consistent with earlier evidence of the green-up in Amazon forests in dry seasons ([Huete et al., 2006](#elsevier-rf0160)). Several recent studies have suggested that this apparent impact of radiation is due to the coincidence of radiation patterns with the emergence of new leaf flushing. Specifically, young leaves have been found to exhibit higher reflectance in the near infrared band compared to old leaves. This change in leaf quality has been identified as the driving factor behind the shift in greenness ([Gonçalves et al., 2023](#elsevier-rf0125); [Saleska et al., 2016](#elsevier-rf0245); [Wu et al., 2016](#elsevier-rf0320)). This coordination between radiation and leaf flushing is likely a main mechanism for the green-up of evergreen forests in maritime Southeast Asia in dry seasons. While our study is unable to provide direct observations of the coordination between leaf quality and radiation, there are some pieces of local evidence from Southeast Asia showing the leaf flushing of trees in dry seasons ([Elliott et al., 2006](#elsevier-rf0100)). We propose that the radiation drives the green-up of evergreen forests in maritime Southeast Asia in dry seasons through a mechanism similar to that in the Amazon. Meanwhile, we found that for maritime evergreen forests, dry seasons show greater water stress (i.e., lower $\mathit{SWC}$ and higher $\mathit{VPD}$) than wet seasons ([Fig. 10](#elsevier-f0050)f and h), which may suppress vegetation productivity and growth in dry seasons ([Kannenberg et al., 2024](#elsevier-rf0185); [Yuan et al., 2019](#elsevier-rf0355)). However, compared to deciduous forests, croplands and continental evergreen forests, the differences in $\mathit{SWC}$ and $\mathit{VPD}$ between dry and wet seasons are minor for maritime evergreen forests ([Fig. 10](#elsevier-f0050)), suggesting that deciduous forests, croplands and continental evergreen forests may experience greater growth suppression in dry seasons than maritime evergreen forests.

![Figure 10](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr10_lrg.jpg)

<a id="elsevier-f0050"></a>Fig. 10. The climate anomalies in dry and wet seasons for different vegetation types. Violin and box plots summarize the values of climate anomalies in dry and wet seasons for (a)-(d) EF<sub>con</sub>: continental evergreen forests, (e)-(h) EF<sub>mar</sub>: maritime evergreen forests, (i)-(l) DF: deciduous forests and (m)-(p) CL: croplands. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ are anomalies of air temperature, soil water content, solar radiation, and vapor pressure deficit, respectively. \*\*\* *p* ≤ 0.001.


In contrast to the seasonality of maritime evergreen forests, we found that deciduous forests, croplands and continental evergreen forests in Southeast Asia tended to green up in wet seasons ([Fig. 7](#elsevier-f0035)d). Our statistical analysis indicated that this phenomenon was mainly driven by the changes in their climate sensitivities between dry and wet seasons ([Fig. 7](#elsevier-f0035)e and f). Specifically, in dry seasons, deciduous forests, croplands and continental evergreen forests exhibited greater sensitivities to temperature and soil moisture, but lower sensitivities to radiation compared to wet seasons ([Fig. 11](#elsevier-f0055)). The mechanisms underlying the changes in climate sensitivities for different vegetation types in Southeast Asia may differ. For deciduous forests and continental evergreen forests, the changes in climate sensitivities were also noted in previous studies ([Wang et al., 2018](#elsevier-rf0295); [Zhang et al., 2021](#elsevier-rf0380)), where they reported that vegetation become more sensitive to temperature and water in dry seasons, compared to wet seasons, though their results are based on an analysis at the interannual time scale. The enhanced sensitivity to temperature in dry seasons was attributed to enhanced evapotranspiration and thus leaf cooling in dry seasons, making the thermoregulation less effective in dry seasons and emerging as a stronger temperature sensitivity ([Wang et al., 2018](#elsevier-rf0295)). This seems to be consistent with flux site observations where evapotranspiration was higher in dry seasons ([Costa et al., 2010](#elsevier-rf0075); [Da Rocha et al., 2004](#elsevier-rf0080)). The enhanced sensitivity to water in dry seasons is related to the increased evaporative demand of the atmosphere, which may cause the higher sensitivity of deciduous forests and continental evergreen forests to water stress ([Zhang et al., 2018](#elsevier-rf0375), [Zhang et al., 2021](#elsevier-rf0380)) ([Fig. 11](#elsevier-f0055)). Meanwhile, for croplands, the changes in climate sensitivities are likely driven by variations in plant species or crop rotations. In continental Southeast Asia, the wet seasons typically span from May to the end of October ([Fig. 5](#elsevier-f0025)) ([Suepa et al., 2016](#elsevier-rf0265); [Xu et al., 2021](#elsevier-rf0325)), during which rice is the prevailing crop, with the growing season extending from March to November ([Suepa et al., 2016](#elsevier-rf0265)). Outside of the wet seasons, the main land use types vary substantially, with maize being common or fallow land used for the growth of natural vegetation ([Lasco et al., 2011](#elsevier-rf0190)). In some places, the same crops (e.g., rice) are planted for the second round in dry seasons, and the differences in crop varieties may contribute to changes in climate sensitivities ([Jiang et al., 2016](#elsevier-rf0175); [Suprihatin et al., 2021](#elsevier-rf0270)).

![Figure 11](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-gr11_lrg.jpg)

<a id="elsevier-f0055"></a>Fig. 11. The climate sensitivities of vegetation greenness in dry and wet seasons for different vegetation types. Violin and box plots summarize the values of climate sensitivities in dry and wet seasons for (a)-(d) EF<sub>con</sub>: continental evergreen forests, (e)-(h) EF<sub>mar</sub>: maritime evergreen forests, (i)-(l) DF: deciduous forests and (m)-(p) CL: croplands. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients of air temperature, soil water content, solar radiation, and vapor pressure deficit, respectively (see Materials and methods). \*\*\* *p* ≤ 0.001. \* *p* ≤ 0.05.


We also note that a recent study reported higher gross primary productivity (GPP) in wet seasons at four eddy covariance sites in Southeast Asia ([Yang et al., 2023](#elsevier-rf0345)). Therefore, we further examined the relationship between the seasonality of NDVI and GPP using flux data from five available sites located in Southeast Asia, namely four evergreen forest sites (BNS, SKR, PSO and LHP) and a deciduous forest site (PSO) ([Fig. A1](#elsevier-f0060)). We found that the Himawari-8 SR-derived NDVI time series and leaf area index (LAI) time series calculated based on light transmittance ([Yang et al., 2023](#elsevier-rf0345)) generally exhibited similar seasonal patterns, although some differences were observed ([Fig. A6](#elsevier-f0085)). Note that the method for calculating LAI based on light transmittance relies on assumptions about canopy structure and is subject to uncertainty. We found that all continental sites exhibited higher GPP in wet seasons compared to dry seasons, consistent with NDVI patterns we observed ([Fig. A6](#elsevier-f0085)p and q). This phenomenon can be attributed to the ample water supply in wet seasons, which enhances canopy conductance and photosynthesis, resulting in higher GPP compared to dry seasons ([Fig. A6](#elsevier-f0085)q) ([Yang et al., 2023](#elsevier-rf0345)).

We also acknowledge that previous studies reporting the green-up of tropical vegetation in dry seasons were based on representative dry and wet months ([Morton et al., 2014](#elsevier-rf0230); [Saleska et al., 2016](#elsevier-rf0245)). Here, we defined the dry and wet seasons using daily precipitation time series ([Tian et al., 2024](#elsevier-rf0280); [Xu et al., 2022](#elsevier-rf0330)), which provides fine information on the dry-wet seasons transition ([Fig. 2](#elsevier-f0010)). To test the robustness of our results regarding the definition of dry and wet seasons, we calculated $\mathit{NDVI}_{d - w}$ values between representative dry and wet months, which were defined as the months with the locally lowest and highest total precipitation in Southeast Asia ([Fig. A7](#elsevier-f0090)a-d). We found that the results derived from this conventional definition showed highly similar spatial patterns in greenness seasonality to our main results ([Fig. 4](#elsevier-f0020)a and d and [Fig. A7](#elsevier-f0090)e and f), suggesting the robustness of our results.

## 5. Conclusions

<a id="elsevier-st0100"></a><a id="elsevier-s0080"></a>

In conclusion, we used new observations from the Himawari-8 geostationary satellite to examine the seasonality of vegetation greenness in Southeast Asia. We found that across Southeast Asia, maritime evergreen forests typically green up in dry seasons, while deciduous forests, croplands and continental evergreen forests tend to green up in wet seasons. The positive anomaly in solar radiation is the primary reason behind the dry-season green-up of maritime evergreen forests, while the changes in the sensitivities to climate between dry and wet seasons contribute to the wet-season green-up of deciduous forests, croplands and continental evergreen forests. Our study offers novel insights into vegetation dynamics in Southeast Asia and critical knowledge to support the estimation of the carbon cycle and other ecosystem functions in the region.

## Code availability

<a id="elsevier-st0105"></a><a id="elsevier-s0085"></a>

The codes used for data processing and analysis in this study are available at [https://zenodo.org/records/14847742](https://zenodo.org/records/14847742).

## CRediT authorship contribution statement

<a id="elsevier-st0115"></a><a id="elsevier-s0095"></a>

**Jiaqi Tian:** Writing – review & editing, Writing – original draft, Visualization, Software, Methodology, Investigation, Formal analysis, Data curation, Conceptualization. **Xiangzhong Luo:** Writing – review & editing, Writing – original draft, Supervision, Methodology, Funding acquisition, Conceptualization. **Weile Wang:** Writing – review & editing, Methodology, Data curation, Conceptualization. **Liyao Yu:** Writing – review & editing, Methodology, Data curation, Conceptualization. **Diane Tan Ting Ng:** Writing – review & editing, Conceptualization. **Kazuhito Ichii:** Writing – review & editing, Methodology, Funding acquisition, Conceptualization. **Yao Zhang:** Writing – review & editing, Conceptualization. **Xiaoyang Zhang:** Writing – review & editing, Methodology, Conceptualization.

## Declaration of competing interest

<a id="elsevier-st0120"></a><a id="elsevier-coi0005"></a>

The authors declare no conflict of interests.

## Acknowledgements

<a id="elsevier-st0125"></a><a id="elsevier-ac0005"></a>

J.T. and X.L. are supported by the <a id="elsevier-gts0005"></a>NUS Presidential Young Professorship awarded to X.L. ([A-0003625-01-00](#elsevier-gts0005)) and a <a id="elsevier-gts0010"></a>Tier 2 Academic Research Fund from Singapore Ministry of Education ([MOE-T2EP50222-0006](#elsevier-gts0010)). K.I. is supported by the <a id="elsevier-gts0015"></a>JSPS KAKENHI, [JP22H05004](#elsevier-gts0015), and [JP20K20487](#elsevier-gts0015), and <a id="elsevier-gts0020"></a>JSPS Core-to-Core Program (grant number: [JPJSCCA20220008](#elsevier-gts0020)).

## Appendix

<a id="elsevier-st0130"></a><a id="elsevier-s0100"></a>

![Figure A1](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx1_lrg.jpg)

<a id="elsevier-f0060"></a>Fig. A1. Land cover map in Southeast Asia. This map is from the European Space Agency Climate Change Initiative (ESA CCI) (v2.1.1) product in 2019. The flux sites include BNS (101.20E, 21.95 N), SKR (101.92E, 14.49 N), MKL (98.84E, 14.58 N), PSO (102.30E, 2.97 N) and LHP (114.04E, 4.20 N).


![Figure A2](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx2_lrg.jpg)

<a id="elsevier-f0065"></a>Fig. A2. Spatial patterns of the differences in vegetation greenness (i.e., NDVI and EVI) derived from Himawari-8 TOA products in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ values are the differences in vegetation greenness between dry and wet seasons (see Materials and methods). SP filter: penalized cubic splines filter. MVC method: maximum value composite method. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ (or $\mathit{EVI}_{d - w}$) &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ (or $\mathit{EVI}_{d - w}$) < 0 (i.e., green-up in wet seasons). (c) and (f) summarize their values by latitude, and the solid lines indicate the mean values. The shaded error bars in (c) and (f) indicate the mean ± standard deviation. TOA: top-of-atmosphere reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


![Figure A3](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx3_lrg.jpg)

<a id="elsevier-f0070"></a>Fig. A3. Spatial patterns of the differences in vegetation greenness (i.e., EVI) in 2019 between dry and wet seasons. The $\mathit{EVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) are calculated from daily EVI time series acquired from Himawari-8 SR, processed by the penalized cubic splines (SP) filter (a) and the maximum value composite (MVC) method (c). The pie in each sub-figure represents the proportions of $\mathit{EVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{EVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). Scatterplots of $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ are derived from Himawari-8 SR, processed by SP filter (b) and MVC method (d). The bright-yellow colour suggests a high kernel density. The red solid lines and black dotted lines represent the best linear fit of the data and the 1:1 reference lines. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


![Figure A4](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx4_lrg.jpg)

<a id="elsevier-f0075"></a>Fig. A4. Spatial patterns of the differences in vegetation greenness (i.e., NDVI) in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) are calculated from daily NDVI time series acquired from MODIS SR and BRDF-normalized SR (nadir view and solar zenith angle = 45°), processed by the penalized cubic splines (SP) filter (a) and the maximum value composite (MVC) method (c). The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). Scatterplots of $\mathit{NDVI}_{d - w}$ are derived from MODIS SR and BRDF-normalized SR, processed by SP filter (b) and MVC method (d). The bright-yellow colour suggests a high kernel density. The red solid lines and black dotted lines represent the best linear fit of the data and the 1:1 reference lines. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


![Figure A5](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx5_lrg.jpg)

<a id="elsevier-f0080"></a>Fig. A5. Spatial patterns of (a)-(h) climate anomalies and (i)-(p) climate sensitivities of vegetation greenness in dry and wet seasons. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ correspond to the climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry and wet seasons. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ refer to the climate sensitivities of vegetation greenness corresponding to each climate factor (see Materials and methods).


![Figure A6](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx6_lrg.jpg)

<a id="elsevier-f0085"></a>Fig. A6. Daily NDVI, LAI, GPP and precipitation time series in 5 specific flux sites. (a) BNS (101.20E, 21.95 N), (b) SKR (101.92E, 14.49 N), (c) MKL (98.84E, 14.58 N), (d) PSO (102.30E, 2.97 N) and (e) LHP (114.04E, 4.20 N). The blue shaded areas indicate the duration of the wet season. The LAI and GPP data for BNS, SKR, MKL and PSO sites are extracted by [Fig. 4](#elsevier-f0020), [Fig. 5](#elsevier-f0025) in ([Yang et al., 2023](#elsevier-rf0345)). (f) The average NDVI and GPP in dry and wet seasons. Please note the NDVI from the Himawari-8 SR in 2019 and all data for LHP site are also from 2019, while the LAI and GPP values for other sites were calculated from multiple years. Therefore, their seasonal patterns do not completely agree with each other. (p) and (q) are mean values of Himawari-8 SR NDVI and GPP in dry and wet seasons, respectively. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


![Figure A7](https://ars.els-cdn.com/content/image/1-s2.0-S0034425725000525-fx7_lrg.jpg)

<a id="elsevier-f0090"></a>Fig. A7. Spatial patterns of the differences in vegetation greenness (i.e., NDVI) derived from Himawari-8 SR products in 2019 between dry and wet months. The $\mathit{NDVI}_{d - w}$ values are the differences in vegetation greenness between dry and wet months. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry months) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet months). The dry and wet months are defined as the months with the lowest and highest total precipitation as the representative dry and wet months, respectively. (a) and (b) are spatial patterns of dry and wet months with the lowest and highest total precipitation, respectively. (e) and (f) are spatial patterns of total precipitation in dry and wet months, respectively. SP filter: penalized cubic splines filter. MVC method: maximum value composite method. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)


## Data availability

<a id="elsevier-st0020"></a><a id="elsevier-da0005"></a>

The Himawari-8 SR dataset can be downloaded via [https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L2/MAIAC/](https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L2/MAIAC/). The Himawari-8 TOA dataset can be found from [https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L1G/](https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L1G/). The MODIS MCD19A3CMG (v061) can be downloaded from [https://lpdaac.usgs.gov/products/mcd19a3cmgv061/](https://lpdaac.usgs.gov/products/mcd19a3cmgv061/). The ESA CCI (v2.1.1) can be downloaded from [https://www.esa-landcover-cci.org/?q=node/164](https://www.esa-landcover-cci.org/?q=node/164). The ERA5-Land product can be accessed from [https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview](https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview). The flux data can be downloaded via: [https://asiaflux.net/index.php?page\_id=76](https://asiaflux.net/index.php?page_id=76).

## References

1. <a id="elsevier-rf0005"></a>A. Baccini, S.J. Goetz, W.S. Walker, N.T. Laporte, M. Sun, D. Sulla-Menashe, J. Hackler, P.S.A. Beck, R. Dubayah, M.A. Friedl, S. Samanta, R.A. Houghton Estimated carbon dioxide emissions from tropical deforestation improved by carbon-density maps Nat. Clim. Chang., 2 (2012), pp. 182-185, 10.1038/nclimate1354 [Baccini et al., 2012]

2. <a id="elsevier-rf0010"></a>H.A. Barbosa, A.R. Huete, W.E. Baethgen A 20-year study of NDVI variability over the Northeast Region of Brazil J. Arid Environ., 67 (2006), pp. 288-307, 10.1016/j.jaridenv.2006.02.022 [Barbosa et al., 2006]

3. <a id="elsevier-rf0015"></a>A. Barkhordarian, S.S. Saatchi, A. Behrangi, P.C. Loikith, C.R. Mechoso A recent systematic increase in vapor pressure deficit over tropical South America Sci. Rep., 9 (2019), p. 15331, 10.1038/s41598-019-51857-8 [Barkhordarian et al., 2019]

4. <a id="elsevier-rf0020"></a>C. Beer, M. Reichstein, E. Tomelleri, P. Ciais, M. Jung, N. Carvalhais, C. Rödenbeck, M.A. Arain, D. Baldocchi, G.B. Bonan, A. Bondeau, A. Cescatti, G. Lasslop, A. Lindroth, M. Lomas, S. Luyssaert, H. Margolis, K.W. Oleson, O. Roupsard, E. Veenendaal, N. Viovy, C. Williams, F.I. Woodward, D. Papale Terrestrial gross carbon dioxide uptake: global distribution and covariation with climate Science, 329 (2010), pp. 834-838, 10.1126/science.1184984 [Beer et al., 2010]

5. <a id="elsevier-rf0025"></a>A. Behrangi, E.J. Fetzer, S.L. Granger Early detection of drought onset using near surface temperature and humidity observed from space Int. J. Remote Sens., 37 (2016), pp. 3911-3923, 10.1080/01431161.2016.1204478 [Behrangi et al., 2016]

6. <a id="elsevier-rf0030"></a>K. Bessho, K. Date, M. Hayashi, A. Ikeda, T. Imai, H. Inoue, Y. Kumagai, T. Miyakawa, H. Murata, T. Ohno, A. Okuyama, R. Oyama, Y. Sasaki, Y. Shimazu, K. Shimoji, Y. Sumida, M. Suzuki, H. Taniguchi, H. Tsuchiyama, D. Uesawa, H. Yokota, R. Yoshida An introduction to Himawari-8/9–Japan’s new-generation geostationary meteorological satellites J. Meteorol. Soc. Jpn. Ser II, 94 (2016), pp. 151-183, 10.2151/jmsj.2016-009 [Bessho et al., 2016]

7. <a id="elsevier-rf0035"></a>J. Bi, Y. Knyazikhin, S. Choi, T. Park, J. Barichivich, P. Ciais, R. Fu, S. Ganguly, F. Hall, T. Hilker, A. Huete, M. Jones, J. Kimball, A.I. Lyapustin, M. Mõttus, R.R. Nemani, S. Piao, B. Poulter, S.R. Saleska, S.S. Saatchi, L. Xu, L. Zhou, R.B. Myneni Sunlight mediated seasonality in canopy structure and photosynthetic activity of Amazonian rainforests Environ. Res. Lett., 10 (2015), Article 064014, 10.1088/1748-9326/10/6/064014 [Bi et al., 2015]

8. <a id="elsevier-rf0040"></a>R. Borchert Soil and stem water storage determine phenology and distribution of tropical dry forest trees Ecology, 75 (1994), pp. 1437-1449, 10.2307/1937467 [Borchert, 1994]

9. <a id="elsevier-rf0045"></a>P.M. Brando, S.J. Goetz, A. Baccini, D.C. Nepstad, P.S.A. Beck, M.C. Christman Seasonal and interannual variability of climate and vegetation indices across the Amazon Proc. Natl. Acad. Sci., 107 (2010), pp. 14685-14690, 10.1073/pnas.0908741107 [Brando et al., 2010]

10. <a id="elsevier-rf0050"></a>F.Q. Brearley, L.F. Banin, P. Saner The ecology of the Asian dipterocarps Plant Ecol. Divers., 9 (2016), pp. 429-436, 10.1080/17550874.2017.1285363 [Brearley et al., 2016]

11. <a id="elsevier-rf0055"></a>M. Cai, Y. Zhang, X. Guan, J. Qiu An adaptive spatiotemporal tensor reconstruction method for GIMMS-3g+ NDVI Remote Sens. Environ., 316 (2025), Article 114511, 10.1016/j.rse.2024.114511 [Cai et al., 2025]

12. <a id="elsevier-rf0060"></a>R. Cao, Y. Chen, M. Shen, J. Chen, J. Zhou, C. Wang, W. Yang A simple method to improve the quality of NDVI time-series data by integrating spatiotemporal information with the Savitzky-Golay filter Remote Sens. Environ., 217 (2018), pp. 244-257, 10.1016/j.rse.2018.08.022 [Cao et al., 2018]

13. <a id="elsevier-rf0065"></a>P.-Y. Chen, R. Srinivasan, G. Fedosejevs, J.R. Kiniry Evaluating different NDVI composite techniques using NOAA-14 AVHRR data Int. J. Remote Sens., 24 (2003), pp. 3403-3412, 10.1080/0143116021000021279 [Chen et al., 2003]

14. <a id="elsevier-rf0070"></a>X. Chen, F. Maignan, N. Viovy, A. Bastos, D. Goll, J. Wu, L. Liu, C. Yue, S. Peng, W. Yuan, A.C. Da Conceição, M. O’Sullivan, P. Ciais Novel representation of leaf phenology improves simulation of Amazonian Evergreen Forest photosynthesis in a land surface model J. Adv. Model. Earth Syst., 12 (2020), 10.1029/2018MS001565 e2018MS001565 [Chen et al., 2020]

15. <a id="elsevier-rf0075"></a>M.H. Costa, M.C. Biajoli, L. Sanches, A.C.M. Malhado, L.R. Hutyra, H.R. Da Rocha, R.G. Aguiar, A.C. De Araújo Atmospheric versus vegetation controls of Amazonian tropical rain forest evapotranspiration: are the wet and seasonally dry rain forests any different? J. Geophys. Res. Biogeosci., 115 (2010), 10.1029/2009JG001179 2009JG001179 [Costa et al., 2010]

16. <a id="elsevier-rf0080"></a>H.R. Da Rocha, M.L. Goulden, S.D. Miller, M.C. Menton, L.D.V.O. Pinto, H.C. De Freitas, A.M. E Silva Figueira Seasonality of water and heat fluxes OVER a tropical forest in eastern AMAZONIA Ecol. Appl., 14 (2004), pp. 22-32, 10.1890/02-6001 [Da Rocha et al., 2004]

17. <a id="elsevier-rf0085"></a>Y.M. De Moura, L.S. Galvão, T. Hilker, J. Wu, S. Saleska, C.H. Do Amaral, B.W. Nelson, A.P. Lopes, K.K. Wiedeman, N. Prohaska, R.C. De Oliveira, C.B. Machado, L.E.O.C. Aragão Spectral analysis of amazon canopy phenology during the dry season using a tower hyperspectral camera and modis observations ISPRS J. Photogramm. Remote Sens., 131 (2017), pp. 52-64, 10.1016/j.isprsjprs.2017.07.006 [De Moura et al., 2017]

18. <a id="elsevier-rf0090"></a>M. De Weirdt, H. Verbeeck, F. Maignan, P. Peylin, B. Poulter, D. Bonal, P. Ciais, K. Steppe Seasonal leaf dynamics for tropical evergreen forests in a process-based global ecosystem model Geosci. Model Dev., 5 (2012), pp. 1091-1108, 10.5194/gmd-5-1091-2012 [De Weirdt et al., 2012]

19. <a id="elsevier-rf0095"></a>C.M. Dunning, E.C.L. Black, R.P. Allan The onset and cessation of seasonal rainfall over Africa J. Geophys. Res.-Atmos., 121 (2016), 10.1002/2016JD025428 [Dunning et al., 2016]

20. <a id="elsevier-rf0100"></a>S. Elliott, P.J. Baker, R. Borchert Leaf Flushing during the dry season: the paradox of Asian monsoon forests Glob. Ecol. Biogeogr., 15 (2006), pp. 248-257 [Elliott et al., 2006]

21. <a id="elsevier-rf0105"></a>R.C. Estoque, M. Ooba, V. Avitabile, Y. Hijioka, R. DasGupta, T. Togawa, Y. Murayama The future of Southeast Asia’s forests Nat. Commun., 10 (2019), p. 1829, 10.1038/s41467-019-09646-4 [Estoque et al., 2019]

22. <a id="elsevier-rf0110"></a>H. Fang, W. Li, R. Myneni The impact of potential land cover misclassification on MODIS Leaf Area Index (LAI) estimation: a statistical perspective Remote Sens., 5 (2013), pp. 830-844, 10.3390/rs5020830 [Fang et al., 2013]

23. <a id="elsevier-or0005"></a>Gao, X., Huete, A.R., Ni, W., Miura, T., 2000. Optical–Biophysical Relationships of Vegetation Spectra without Background Contamination. Remote Sens. Environ. 74, 609–620. doi: https://doi.org/10.1016/S0034-4257(00)00150-4. [Gao et al., 2000]

24. <a id="elsevier-rf0115"></a>Si Gao, R. Zhong, K. Yan, X. Ma, X. Chen, J. Pu, Sicong Gao, J. Qi, G. Yin, R.B. Myneni Evaluating the saturation effect of vegetation indices in forests using 3D radiative transfer simulations and satellite observations Remote Sens. Environ., 295 (2023), Article 113665, 10.1016/j.rse.2023.113665 [Gao et al., 2023]

25. <a id="elsevier-rf0120"></a>J. Gomis-Cebolla, V. Rattayova, S. Salazar-Galán, F. Francés Evaluation of ERA5 and ERA5-land reanalysis precipitation datasets over Spain (1951–2020) Atmos. Res., 284 (2023), Article 106606, 10.1016/j.atmosres.2023.106606 [Gomis-Cebolla et al., 2023]

26. <a id="elsevier-rf0125"></a>N.B. Gonçalves, R. Dalagnol, J. Wu, A. Pontes-Lopes, S.C. Stark, B.W. Nelson Amazon forest spectral seasonality is consistent across sensor resolutions and driven by leaf demography ISPRS J. Photogramm. Remote Sens., 196 (2023), pp. 93-104, 10.1016/j.isprsjprs.2022.12.001 [Gonçalves et al., 2023]

27. <a id="elsevier-rf0130"></a>J.K. Green, J. Berry, P. Ciais, Y. Zhang, P. Gentine Amazon rainforest photosynthesis increases in response to atmospheric dryness Sci. Adv., 6 (2020), p. eabb7232, 10.1126/sciadv.abb7232 [Green et al., 2020]

28. <a id="elsevier-rf0135"></a>K. Guan, M. Pan, H. Li, A. Wolf, J. Wu, D. Medvigy, K.K. Caylor, J. Sheffield, E.F. Wood, Y. Malhi, M. Liang, J.S. Kimball, S.R. Saleska, J. Berry, J. Joiner, A.I. Lyapustin Photosynthetic seasonality of global tropical forests constrained by hydroclimate Nat. Geosci., 8 (2015), pp. 284-289, 10.1038/ngeo2382 [Guan et al., 2015]

29. <a id="elsevier-rf0140"></a>Y. Guan, J. Liu, P. Chen, Y. Wang, D. Liang, Y. Xue, H. Chen, Z. Liu, P. Pellikka Synergistic impact of complex topography and climate variability on the loss of microclimate heterogeneity in Southeast Asia Geophys. Res. Lett., 50 (2023), 10.1029/2023GL104965 e2023GL104965 [Guan et al., 2023]

30. <a id="elsevier-rf0145"></a>H. Hashimoto, W. Wang, J.L. Dungan, S. Li, A.R. Michaelis, H. Takenaka, A. Higuchi, R.B. Myneni, R.R. Nemani New generation geostationary satellite observations support seasonality in greenness of the Amazon evergreen forests Nat. Commun., 12 (2021), p. 684, 10.1038/s41467-021-20994-y [Hashimoto et al., 2021]

31. <a id="elsevier-rf0150"></a>T. Hilker, A.I. Lyapustin, F.G. Hall, R. Myneni, Y. Knyazikhin, Y. Wang, C.J. Tucker, P.J. Sellers On the measurability of change in Amazon vegetation from MODIS Remote Sens. Environ., 166 (2015), pp. 233-242, 10.1016/j.rse.2015.05.020 [Hilker et al., 2015]

32. <a id="elsevier-rf0155"></a>A. Huete, K. Didan, T. Miura, E.P. Rodriguez, X. Gao, L.G. Ferreira Overview of the radiometric and biophysical performance of the MODIS vegetation indices Remote Sens. Environ., 83 (2002), pp. 195-213, 10.1016/S0034-4257(02)00096-2 [Huete et al., 2002]

33. <a id="elsevier-rf0160"></a>A.R. Huete, K. Didan, Y.E. Shimabukuro, P. Ratana, S.R. Saleska, L.R. Hutyra, W. Yang, R.R. Nemani, R. Myneni Amazon rainforests green-up with sunlight in dry season Geophys. Res. Lett., 33 (2006), 10.1029/2005GL025583 2005GL025583 [Huete et al., 2006]

34. <a id="elsevier-rf0165"></a>A.R. Huete, N. Restrepo-Coupe, P. Ratana, K. Didan, S.R. Saleska, K. Ichii, S. Panuthai, M. Gamo Multiple site tower flux and remote sensing comparisons of tropical forest dynamics in Monsoon Asia Agric. For. Meteorol., 148 (2008), pp. 748-760, 10.1016/j.agrformet.2008.01.012 [Huete et al., 2008]

35. <a id="elsevier-rf0170"></a>T. Janssen, Y. Van Der Velde, F. Hofhansl, S. Luyssaert, K. Naudts, B. Driessen, K. Fleischer, H. Dolman Drought effects on leaf fall, leaf flushing and stem growth in the Amazon forest: reconciling remote sensing data and field observations Biogeosciences, 18 (2021), pp. 4445-4472, 10.5194/bg-18-4445-2021 [Janssen et al., 2021]

36. <a id="elsevier-rf0175"></a>Y. Jiang, Y. Liang, C. Li, F. Wang, Y. Sui, N. Suvannang, J. Zhou, B. Sun Crop rotations alter bacterial and fungal diversity in paddy soils across East Asia Soil Biol. Biochem., 95 (2016), pp. 250-261, 10.1016/j.soilbio.2016.01.007 [Jiang et al., 2016]

37. <a id="elsevier-rf0180"></a>Y. Jiang, L. Zhou, C.J. Tucker, A. Raghavendra, W. Hua, Y.Y. Liu, J. Joiner Widespread increase of boreal summer dry season length over the Congo rainforest Nat. Clim. Chang., 9 (2019), pp. 617-622, 10.1038/s41558-019-0512-y [Jiang et al., 2019]

38. <a id="elsevier-rf0185"></a>S.A. Kannenberg, W.R.L. Anderegg, M.L. Barnes, M.P. Dannenberg, A.K. Knapp Dominant role of soil moisture in mediating carbon and water fluxes in dryland ecosystems Nat. Geosci., 17 (2024), pp. 38-43, 10.1038/s41561-023-01351-8 [Kannenberg et al., 2024]

39. <a id="elsevier-rf0190"></a>R.D. Lasco, C.M.D. Habito, R.J.P. Delfino, F.B. Pulhin, R.N. Concepcion Climate Change Adaptation for Smallholder Farmers in Southeast Asia World Agroforestry Centre, Los Baños Philippines (2011) [Lasco et al., 2011]

40. <a id="elsevier-rf0195"></a>Z. Li, T. Huffman, B. McConkey, L. Townley-Smith Monitoring and modeling spatial and temporal patterns of grassland dynamics using time-series MODIS NDVI with climate and stocking data Remote Sens. Environ., 138 (2013), pp. 232-244, 10.1016/j.rse.2013.07.020 [Li et al., 2013]

41. <a id="elsevier-rf0200"></a>W. Li, N. MacBean, P. Ciais, P. Defourny, C. Lamarche, S. Bontemps, R.A. Houghton, S. Peng Gross and net land cover changes in the main plant functional types derived from the annual ESA CCI land cover maps (1992–2015) Earth Syst. Sci. Data, 10 (2018), pp. 219-234, 10.5194/essd-10-219-2018 [Li et al., 2018]

42. <a id="elsevier-rf0205"></a>B. Liebmann, I. Bladé, G.N. Kiladis, L.M.V. Carvalho, B. Senay, D. Allured, S. Leroux, C. Funk Seasonality of African precipitation from 1996 to 2009 J. Clim., 25 (2012), pp. 4304-4322, 10.1175/JCLI-D-11-00157.1 [Liebmann et al., 2012]

43. <a id="elsevier-rf0210"></a>A.P. Lopes, B.W. Nelson, J. Wu, P.M.L.D.A. Graça, J.V. Tavares, N. Prohaska, G.A. Martins, S.R. Saleska Leaf flush drives dry season green-up of the Central Amazon Remote Sens. Environ., 182 (2016), pp. 90-98, 10.1016/j.rse.2016.05.009 [Lopes et al., 2016]

44. <a id="elsevier-rf0215"></a>A. Lyapustin, Y. Wang, I. Laszlo, R. Kahn, S. Korkin, L. Remer, R. Levy, J.S. Reid Multiangle implementation of atmospheric correction (MAIAC): 2. Aerosol algorithm J. Geophys. Res., 116 (2011), p. D03211, 10.1029/2010JD014986 [Lyapustin et al., 2011]

45. <a id="elsevier-rf0220"></a>Y. Malhi The productivity, metabolism and carbon cycle of tropical forest vegetation J. Ecol., 100 (2012), pp. 65-75, 10.1111/j.1365-2745.2011.01916.x [Malhi, 2012]

46. <a id="elsevier-rf0225"></a>M. Moon, X. Zhang, G.M. Henebry, L. Liu, J.M. Gray, E.K. Melaas, M.A. Friedl Long-term continuity in land surface phenology measurements: a comparative assessment of the MODIS land cover dynamics and VIIRS land surface phenology products Remote Sens. Environ., 226 (2019), pp. 74-92, 10.1016/j.rse.2019.03.034 [Moon et al., 2019]

47. <a id="elsevier-rf0230"></a>D.C. Morton, J. Nagol, C.C. Carabajal, J. Rosette, M. Palace, B.D. Cook, E.F. Vermote, D.J. Harding, P.R.J. North Amazon forests maintain consistent canopy structure and greenness during the dry season Nature, 506 (2014), pp. 221-224, 10.1038/nature13006 [Morton et al., 2014]

48. <a id="elsevier-rf0235"></a>M. Nazeer, C.O. Ilori, M. Bilal, J.E. Nichol, W. Wu, Z. Qiu, B.K. Gayene Evaluation of atmospheric correction methods for low to high resolutions satellite remote sensing data Atmos. Res., 249 (2021), Article 105308, 10.1016/j.atmosres.2020.105308 [Nazeer et al., 2021]

49. <a id="elsevier-rf0240"></a>Ş. Procheş, S. Ramdhani, A.C. Hughes, L.P. Koh Southeast Asia as one of world’s primary sources of biotic recolonization following Anthropocene extinctions Front. Ecol. Evol., 9 (2021), Article 634711, 10.3389/fevo.2021.634711 [Procheş et al., 2021]

50. <a id="elsevier-rf0245"></a>S.R. Saleska, J. Wu, K. Guan, A.C. Araujo, A. Huete, A.D. Nobre, N. Restrepo-Coupe Dry-season greening of Amazon forests Nature, 531 (2016), pp. E4-E5, 10.1038/nature16457 [Saleska et al., 2016]

51. <a id="elsevier-rf0250"></a>T.W. Satriawan, X. Luo, J. Tian, K. Ichii, L. Juneng, M. Kondo Strong Green-up of tropical Asia during the 2015/16 El Niño Geophys. Res. Lett., 51 (2024), 10.1029/2023GL106955 e2023GL106955 [Satriawan et al., 2024]

52. <a id="elsevier-rf0255"></a>N.-H. Seong, D. Jung, J. Kim, K.-S. Han Evaluation of NDVI estimation considering atmospheric and BRDF correction through Himawari-8/AHI Asia-Pac. J. Atmos. Sci., 56 (2020), pp. 265-274, 10.1007/s13143-019-00167-0 [Seong et al., 2020]

53. <a id="elsevier-rf0260"></a>L. She, H. Zhang, W. Wang, Y. Wang, Y. Shi Evaluation of the Multi-Angle Implementation of Atmospheric Correction (MAIAC) aerosol algorithm for Himawari-8 data Remote Sens., 11 (2019), p. 2771, 10.3390/rs11232771 [She et al., 2019]

54. <a id="elsevier-rf0265"></a>T. Suepa, J. Qi, S. Lawawirojwong, J.P. Messina Understanding spatio-temporal variation of vegetation phenology and rainfall seasonality in the monsoon Southeast Asia Environ. Res., 147 (2016), pp. 621-629, 10.1016/j.envres.2016.02.005 [Suepa et al., 2016]

55. <a id="elsevier-rf0270"></a>A. Suprihatin, B.H. Purwanto, E. Hanudin, M. Nurudin Effect of cropping rotation patterns on rice productivity in irrigated rice fields IOP Conf. Ser. Earth Environ. Sci., 752 (2021), Article 012002, 10.1088/1755-1315/752/1/012002 [Suprihatin et al., 2021]

56. <a id="elsevier-rf0275"></a>J. Tian, X. Zhu, J. Chen, C. Wang, M. Shen, W. Yang, X. Tan, S. Xu, Z. Li Improving the accuracy of spring phenology detection by optimally smoothing satellite vegetation index time series based on local cloud frequency ISPRS J. Photogramm. Remote Sens., 180 (2021), pp. 29-44, 10.1016/j.isprsjprs.2021.08.003 [Tian et al., 2021]

57. <a id="elsevier-rf0280"></a>J. Tian, X. Luo, H. Xu, J.K. Green, H. Tang, J. Wu, S. Piao Slower changes in vegetation phenology than precipitation seasonality in the dry tropics Glob. Chang. Biol., 30 (2024), Article e17134, 10.1111/gcb.17134 [Tian et al., 2024]

58. <a id="elsevier-rf0285"></a>K.P. Vadrevu, T. Ohara Focus on land use cover changes and environmental impacts in South/Southeast Asia Environ. Res. Lett., 15 (2020), Article 100201, 10.1088/1748-9326/abb5cb [Vadrevu and Ohara, 2020]

59. <a id="elsevier-rf0290"></a>G. Vico, S.E. Thompson, S. Manzoni, A. Molini, J.D. Albertson, J.S. Almeida-Cortez, P.A. Fay, X. Feng, A.J. Guswa, H. Liu, T.G. Wilson, A. Porporato Climatic, ecophysiological, and phenological controls on plant ecohydrological strategies in seasonally dry ecosystems Ecohydrology, 8 (2015), pp. 660-681, 10.1002/eco.1533 [Vico et al., 2015]

60. <a id="elsevier-rf0295"></a>X. Wang, P. Ciais, Y. Wang, D. Zhu Divergent response of seasonally dry tropical vegetation to climatic variations in dry and wet seasons Glob. Chang. Biol., 24 (2018), pp. 4709-4717, 10.1111/gcb.14335 [Wang et al., 2018]

61. <a id="elsevier-rf0300"></a>W. Wang, S. Li, H. Hashimoto, H. Takenaka, A. Higuchi, S. Kalluri, R. Nemani An introduction to the geostationary-NASA earth exchange (GeoNEX) products: 1. Top-of-atmosphere reflectance and brightness temperature Remote Sens., 12 (2020), p. 1267, 10.3390/rs12081267 [Wang et al., 2020a]

62. <a id="elsevier-rf0305"></a>J. Wang, D. Yang, M. Detto, B.W. Nelson, M. Chen, K. Guan, S. Wu, Z. Yan, J. Wu Multi-scale integration of satellite remote sensing improves characterization of dry-season green-up in an Amazon tropical evergreen forest Remote Sens. Environ., 246 (2020), Article 111865, 10.1016/j.rse.2020.111865 [Wang et al., 2020b]

63. <a id="elsevier-rf0310"></a>J.L. Weiss, J.L. Betancourt, J.T. Overpeck Climatic limits on foliar growth during major droughts in the southwestern USA. J. Geophys. Res Biogeosciences, 117 (2012), 10.1029/2012JG001993 2012JG001993 [Weiss et al., 2012]

64. <a id="elsevier-rf0315"></a>A.M. Wilson, W. Jetz Remotely sensed high-resolution global cloud dynamics for predicting ecosystem and biodiversity distributions PLoS Biol., 14 (2016), Article e1002415, 10.1371/journal.pbio.1002415 [Wilson and Jetz, 2016]

65. <a id="elsevier-rf0320"></a>J. Wu, L.P. Albert, A.P. Lopes, N. Restrepo-Coupe, M. Hayek, K.T. Wiedemann, K. Guan, S.C. Stark, B. Christoffersen, N. Prohaska, J.V. Tavares, S. Marostica, H. Kobayashi, M.L. Ferreira, K.S. Campos, R. Da Silva, P.M. Brando, D.G. Dye, T.E. Huxman, A.R. Huete, B.W. Nelson, S.R. Saleska Leaf development and demography explain photosynthetic seasonality in Amazon evergreen forests Science, 351 (2016), pp. 972-976, 10.1126/science.aad5068 [Wu et al., 2016]

66. <a id="elsevier-rf0325"></a>H. Xu, X. Lian, I. Slette, H. Yang, Y. Zhang, A. Chen, S. Piao Rising ecosystem water demand exacerbates the lengthening of tropical dry seasons (preprint). In Review (2021), 10.21203/rs.3.rs-218770/v1 [Xu et al., 2021]

67. <a id="elsevier-rf0330"></a>H. Xu, X. Lian, I.J. Slette, H. Yang, Y. Zhang, A. Chen, S. Piao Rising ecosystem water demand exacerbates the lengthening of tropical dry seasons Nat. Commun., 13 (2022), p. 4093, 10.1038/s41467-022-31826-y [Xu et al., 2022]

68. <a id="elsevier-rf0335"></a>D. Yan, X. Zhang, Y. Yu, W. Guo A comparison of tropical rainforest phenology retrieved from geostationary (SEVIRI) and polar-orbiting (MODIS) sensors across the Congo Basin IEEE Trans. Geosci. Remote Sens., 54 (2016), pp. 4867-4881, 10.1109/TGRS.2016.2552462 [Yan et al., 2016]

69. <a id="elsevier-rf0340"></a>Y. Yang, P. Xiao, X. Feng, H. Li Accuracy assessment of seven global land cover datasets over China ISPRS J. Photogramm. Remote Sens., 125 (2017), pp. 156-173, 10.1016/j.isprsjprs.2017.01.016 [Yang et al., 2017]

70. <a id="elsevier-rf0345"></a>L.-Y. Yang, R. Yu, J. Wu, Y. Zhang, Y. Kosugi, N. Restrepo-Coupe, A. Huete, J. Zhang, Y.-H. Liu, X. Zhang, W.-J. Liu, J.-F. Zhao, J. Zeng, Q.-H. Song, Y.-J. Chen, L. Song, Z.-H. Tan Asian tropical forests assimilating carbon under dry conditions: water stress or light benefits? J. Plant Ecol., 16 (2023), p. rtac106, 10.1093/jpe/rtac106 [Yang et al., 2023]

71. <a id="elsevier-rf0350"></a>F. Yu, X. Wu Radiometric inter-calibration between Himawari-8 AHI and S-NPP VIIRS for the solar reflective bands Remote Sens., 8 (2016), p. 165, 10.3390/rs8030165 [Yu and Wu, 2016]

72. <a id="elsevier-rf0355"></a>W. Yuan, Y. Zheng, S. Piao, P. Ciais, D. Lombardozzi, Y. Wang, Y. Ryu, G. Chen, W. Dong, Z. Hu, A.K. Jain, C. Jiang, E. Kato, S. Li, S. Lienert, S. Liu, J.E.M.S. Nabel, Z. Qin, T. Quine, S. Sitch, W.K. Smith, F. Wang, C. Wu, Z. Xiao, S. Yang Increased atmospheric vapor pressure deficit reduces global vegetation growth Sci. Adv., 5 (2019), p. eaax1396, 10.1126/sciadv.aax1396 [Yuan et al., 2019]

73. <a id="elsevier-rf0360"></a>Y. Zeng, D. Hao, A. Huete, B. Dechant, J. Berry, J.M. Chen, J. Joiner, C. Frankenberg, B. Bond-Lamberty, Y. Ryu, J. Xiao, G.R. Asrar, M. Chen Optical vegetation indices for monitoring terrestrial ecosystems globally Nat. Rev. Earth Environ., 3 (2022), pp. 477-493, 10.1038/s43017-022-00298-5 [Zeng et al., 2022]

74. <a id="elsevier-rf0365"></a>Y. Zeng, D. Hao, T. Park, P. Zhu, A. Huete, R. Myneni, Y. Knyazikhin, J. Qi, R.R. Nemani, F. Li, J. Huang, Y. Gao, B. Li, F. Ji, P. Köhler, C. Frankenberg, J.A. Berry, M. Chen Structural complexity biases vegetation greenness measures Nat. Ecol. Evol., 7 (2023), pp. 1790-1798, 10.1038/s41559-023-02187-6 [Zeng et al., 2023]

75. <a id="elsevier-rf0370"></a>Y. Zhang, Z. Zhu, Z. Liu, Z. Zeng, P. Ciais, M. Huang, Y. Liu, S. Piao Seasonal and interannual changes in vegetation activity of tropical forests in Southeast Asia Agric. For. Meteorol., 224 (2016), pp. 1-10, 10.1016/j.agrformet.2016.04.009 [Zhang et al., 2016]

76. <a id="elsevier-rf0375"></a>D. Zhang, X. Jiao, Q. Du, X. Song, J. Li Reducing the excessive evaporative demand improved photosynthesis capacity at low costs of irrigation via regulating water driving force and moderating plant water stress of two tomato cultivars Agric. Water Manag., 199 (2018), pp. 22-33, 10.1016/j.agwat.2017.11.014 [Zhang et al., 2018]

77. <a id="elsevier-rf0380"></a>W. Zhang, Y. Li, X. Wu, Y. Chen, A. Chen, C.R. Schwalm, J.S. Kimball Divergent response of vegetation growth to soil water availability in dry and wet periods over Central Asia J. Geophys. Res. Biogeosci., 126 (2021), 10.1029/2020JG005912 e2020JG005912 [Zhang et al., 2021]

78. <a id="elsevier-rf0385"></a>X. Zhang, Y. Shen, S. Gao, W. Wang, C. Schaaf Diverse responses of multiple satellite-derived vegetation Greenup onsets to dry periods in the Amazon Geophys. Res. Lett., 49 (2022), 10.1029/2022GL098662 e2022GL098662 [Zhang et al., 2022]

79. <a id="elsevier-rf0390"></a>Z. Zhu, S. Piao, R.B. Myneni, M. Huang, Z. Zeng, J.G. Canadell, P. Ciais, S. Sitch, P. Friedlingstein, A. Arneth, C. Cao, L. Cheng, E. Kato, C. Koven, Y. Li, X. Lian, Y. Liu, R. Liu, J. Mao, Y. Pan, S. Peng, J. Peñuelas, B. Poulter, T.A.M. Pugh, B.D. Stocker, N. Viovy, X. Wang, Y. Wang, Z. Xiao, H. Yang, S. Zaehle, N. Zeng Greening of the earth and its drivers Nat. Clim. Chang., 6 (2016), pp. 791-795, 10.1038/nclimate3004 [Zhu et al., 2016]
