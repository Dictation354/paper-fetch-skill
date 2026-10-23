---
title: "Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations"
authors: "Jiaqi Tian, Xiangzhong Luo, Weile Wang, Liyao Yu, Diane Tan Ting Ng, Kazuhito Ichii, Yao Zhang, Xiaoyang Zhang"
doi: "10.1016/j.rse.2025.114648"
source: "elsevier_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 13436
---

# Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations

## Abstract

Tropical forests in the Amazon are characterized by a dry-season green-up, indicating a light-dominated regime in the seasonal variation of ecosystem functions. Southeast Asia, which hosts some of the most carbon-dense and diverse ecosystems in the world, is also expected to green up in dry seasons, however, recent in-situ evidence suggests otherwise. Here, we utilized high-frequency observations from the Himawari-8 geostationary satellite to examine the seasonality of vegetation greenness across Southeast Asia and to investigate potential factors driving this seasonality. We found that evergreen forests in maritime Southeast Asia green up in dry seasons, which is linked to positive anomaly in incoming radiation, similar to the Amazon forests. However, deciduous forests, croplands, and evergreen forests in continental Southeast Asia tend to green up in wet seasons, which is associated with the changes in climate sensitivities of vegetation greenness between dry and wet seasons. Our study highlights seasonal differences in tropical vegetation across biomes and sheds light on the underlying mechanisms of climate-vegetation interactions in Southeast Asia.

## Introduction

Vegetation dynamics underline the variation in land-atmosphere carbon exchange and accordingly modulate many aspects of ecosystem functions. Tropical ecosystems, which host the largest land-atmosphere carbon exchange in the world (Beer et al., 2010; Malhi, 2012), demonstrate a unique seasonal dynamic referred to as dry-season green-up (Huete et al., 2006). Evidence from remote sensing and ground observations has shown an increase in canopy greenness and photosynthesis in Amazon forests during the periods of low rainfall (Guan et al., 2015; Huete et al., 2006; Wang et al., 2020b). Most studies attribute this phenomenon to a coordination of anomalous high sunlight in dry seasons and the flushing of new leaves at the same time (De Moura et al., 2017; Janssen et al., 2021; Lopes et al., 2016). The knowledge has been incorporated into Earth System Models to estimate the pan-tropical carbon cycle (Chen et al., 2020; De Weirdt et al., 2012). However, it remains unknown whether the dry-season green-up prevails in other parts of the tropics, such as Southeast Asia, where vegetation composition (Brearley et al., 2016; Procheş et al., 2021) and climate sensitivities (Satriawan et al., 2024) are reported to be different from those of the Amazon.

Southeast Asia hosts some of the most carbon-dense ecosystems in the world (Baccini et al., 2012) and is a global hotspot for biodiversity (Estoque et al., 2019; Procheş et al., 2021). Due to the complexity of topography (Guan et al., 2023), climate seasonality (e.g., continental and maritime monsoon seasons) (Suepa et al., 2016) and intense anthropogenic land use (e.g., cropland expansion) (Vadrevu and Ohara, 2020), vegetation in Southeast Asia demonstrate considerable variety and are likely to differ in its climatic dependencies. Several studies have examined the seasonality of vegetation in Southeast Asia using remote sensing or in-situ observations. However, they have reported contrasting results on the seasonality of greenness. For example, a remote sensing-based study (Zhang et al., 2016) suggests that evergreen forests in continental Southeast Asia exhibit higher greenness in dry seasons than wet seasons (i.e., dry-season green-up), while in-situ observations (Huete et al., 2008; Yang et al., 2023) indicate otherwise. These studies all noticed the differences in the seasonality of greenness among biomes (e.g., evergreen or deciduous forests), though there is no consensus on the specific nature of these differences. This highlights a large knowledge gap in our understanding of vegetation seasonality in Southeast Asia.

Although MODIS theoretically observes tropical land surfaces at least once a day and is suitable for detecting vegetation seasonality, persistent cloud cover severely limits the availability of clear-sky observations for analysis (Hashimoto et al., 2021; Wilson and Jetz, 2016). In recent years, thanks to the launch of geostationary satellites (e.g., Himawari-8/9, FY-4, and GOES-16/17) that monitor the land surface at very high observation frequencies (e.g., every 10–15 minutes), it has become possible to acquire more cloud-free observations of tropical vegetation (Wang et al., 2020a; Yan et al., 2016; Zhang et al., 2022). For example, the amount of cloud-free observations from GOES-16/17 is 21–35 times more than that from MODIS in the Amazon (Hashimoto et al., 2021). When it comes to monitoring vegetation in Southeast Asia using geostationary satellites, the Advanced Himawari Imager (AHI) onboard the Himawari-8 geostationary satellite, with its nadir point centered at 140.7°E of the equator, offers a suitable data source for this purpose. Himawari-8 became operational on 7 July 2015 (Bessho et al., 2016), which provides the longest continuous geostationary observations for Southeast Asia (She et al., 2019) and over 50 times more clear-sky data than MODIS based on a site analysis (Ichii et al., 2025, *in preparation*).

Motivated by the knowledge gap on vegetation seasonality in Southeast Asia and the availability of new observations from Himawari-8, we aim to address the following two questions: (i) does vegetation in Southeast Asia show dry-season green-up? and (ii) what are the climate drivers of vegetation greenness seasonality in Southeast Asia? To do so, we used the normalized difference vegetation index (NDVI) as a proxy for vegetation greenness, which was estimated from two versions of Himawari-8 reflectance: top-of-atmosphere (TOA) reflectance and surface reflectance (SR) retrieved by the Multi-Angle Implementation of Atmospheric Correction (MAIAC) algorithm. We investigated the differences in NDVI between dry and wet seasons and employed an advanced statistical framework to examine the contributions of climate anomalies and changes in climate sensitivities of vegetation to the detected green-up signals.

## Materials and methods

### Himawari-8 data

Himawari-8 is a geostationary satellite operated by the Japan Meteorological Agency (JMA), launched on October 7, 2014 (Bessho et al., 2016). The AHI onboard Himawari-8 captures TOA reflectance (hereafter named “Himawari-8 TOA”) in six visible and near infrared (VNIR) bands every 10 minutes (She et al., 2019; Yu and Wu, 2016). The six bands include 0.5 km resolution for B3 (0.64 μm), 1 km resolution for B1 (0.47 μm), B2 (0.51 μm) and B4 (0.86 μm), and 2 km resolution for B5 (1.6 μm) and B6 (2.3 μm) (Yu and Wu, 2016). TOA reflectance is influenced by complex atmospheric conditions (e.g., aerosols, water vapor and gases) (Nazeer et al., 2021). Meanwhile, we also used a version of SR from Himawari-8, produced by the Geostationary National Aeronautics and Space Administration (NASA) Earth exchange (GeoNEX) project using the MAIAC algorithm (hereafter named “Himawari-8 SR”). The MAIAC algorithm was developed to detect clouds and cloud shadows and retrieve aerosol optical depth (AOD) and SR simultaneously from MODIS data (She et al., 2019). It has been proven to be a robust method for remote sensing studies in tropical environment (Guan et al., 2015; Hilker et al., 2015). Its Quality Assurance (QA) bands provide the information on different confidence levels of cloud masks (e.g., clear, possibly cloudy, cloudy, and cloud shadow) (She et al., 2019). The Himawari-8 SR products utilized the highest confidence level of cloud masks to ensure the retention of the clearest possible observations.

### MODIS data

To provide a reference for the performance of Himawari-8 data, we also used MODIS NDVI in this study. The MODIS NDVI is retrieved from the MODIS MCD19A3CMG (v061), a daily cloud-cleared vegetation index product estimated from MODIS MAIAC reflectance at a spatial resolution of 0.05°. The MODIS MAIAC data undergo a series of processing procedures, including cloud screening, atmospheric correction, and bidirectional reflectance distribution function (BRDF) normalization applied to raw MODIS TOA reflectance (De Moura et al., 2017; Lyapustin et al., 2011), and have been widely used in tropical vegetation studies (Bi et al., 2015; De Moura et al., 2017; Hashimoto et al., 2021). In this study, we used two versions of MODIS products from MCD19A3CMG (v061): NDVI based on SR (hereafter named “MODIS SR”) and NDVI based on BRDF-normalized SR (nadir view and solar zenith angle = 45°) (hereafter named “MODIS BRDF-normalized SR”). We resampled all NDVI datasets (i.e., Himawari-8 TOA, Himawari-8 SR, MODIS SR and MODIS BRDF-normalized SR) to a uniform spatial resolution of 0.1° to match climate data using the Pixel Aggregation method.

### Land cover map

We used the land cover map from the European Space Agency Climate Change Initiative (ESA CCI) (v2.1.1) at a spatial resolution of 300 m, which was produced to ensure temporal consistency by merging multiple global reflectance products (Li et al., 2018). It comprises 37 categories based on the United Nations Land Cover Classification System and demonstrates the highest overall accuracy compared to other similar-resolution land cover products (e.g., MCD12Q1, GLC, IGBP, and UMD) (Yang et al., 2017). We further simplified the land cover map into 7 classes: evergreen forests, deciduous forests, croplands, mosaics (e.g., a mix of types not matching any of other definitions), others (e.g., shrublands and grasslands), non-vegetation (e.g., urban and built-up lands) and water bodies in our study (Fig. A1). To match the spatial resolution with the above-mentioned NDVI products and maintain the classification scheme, we resampled the land cover map into 0.1° using the Nearest Neighbour method. We did not use MODIS land cover product in this study due to its potential misclassification of a substantial portion of savanna and the underestimation of deciduous forest extent in tropical Asia (Fang et al., 2013).

### Climate data

ERA5-Land, a reanalysis dataset that combines model data from the Integrated Forecasting System (IFS) with observations, provides hourly climate variables at an enhanced resolution (0.1°) compared to ERA5 (Gomis-Cebolla et al., 2023). From the ERA5-Land dataset, we extracted hourly air temperature ($T$), dewpoint temperature ($T_{d}$), total precipitation ($\mathit{PRE}$), solar radiation ($\mathit{RAD}$), and volumetric soil water ($\mathit{VSW}$) in layers 1 (0–7 cm) and 2 (7–28 cm). The soil water content ($\mathit{SWC}$) was the weighted mean of the $\mathit{VSW}$ from two layers, and the vapor pressure deficit ($\mathit{VPD}$) was calculated using Eq. (1) (Barkhordarian et al., 2019; Behrangi et al., 2016; Weiss et al., 2012):

(1)

$$
\mathit{VPD} = c_{1} \times \mathit{exp}\left(\frac{c_{2} \times T}{c_{3} + T} \right) - c_{1} \times \mathit{exp}\left(\frac{c_{2} \times T_{d}}{c_{3} + T_{d}} \right)
$$

where $c_{1}$, $c_{2}$, and $c_{3}$ are equal to 0.611, 17.5 and 240.978, respectively. $T$ and $T_{d}$ represent air temperature and dewpoint temperature in °C, and $\mathit{VPD}$ refers to the vapor pressure deficit in kPa. The first and second terms in Eq. (1) represent the saturated vapor pressure ($e_{s}$) and actual vapor pressure ($e_{a}$), respectively.

### Reconstructing daily and 16-day NDVI time series

To minimize the diurnal sun-angle variations, we calculated the daytime (i.e., 9 a.m. to 3 p.m. local time) 10-minute NDVI time series from Himawari-8 TOA and SR data using Eq. (2):

(2)

$$
\mathit{NDVI} = \frac{B_{4} - B_{3}}{B_{4} + B_{3}}
$$

where $B_{3}$ and $B_{4}$ represent the red (0.64 μm) and NIR (0.86 μm) reflectance of Himawari-8 TOA and SR, respectively. As one of the most common proxies of vegetation greenness, NDVI effectively captures and reflects vegetation characteristics (Zeng et al., 2022) and is not sensitive to both atmospheric effects (Chen et al., 2003) and seasonal changes in sun-sensor geometry in the tropics (Morton et al., 2014). We then resampled the 10-minute NDVI time series into the daily time series using the maximum value composite (MVC) method (Fig. 1a and c). The MVC method is conventionally used to minimize cloud and atmospheric effects on NDVI time series by outputting the highest NDVI value in a defined time interval (Hashimoto et al., 2021; Tian et al., 2021). We used the 95<sup>th</sup> percentile values instead of the highest NDVI values to reduce the impact of abnormally high outliers (e.g., highlighted in Fig. 1a). To assess the performance of Himawari-8 NDVI, we also extracted daily NDVI from the MODIS SR product. Since daily NDVI time series are still susceptible to cloud contamination and abnormal values, we further employed two common approaches to smooth the daily Himawari-8 and MODIS NDVI time series: penalized cubic splines (SP) filter and MVC method (Tian et al., 2021) (Fig. 1). The former generates a smoothed daily and gap-free NDVI time series and has been used to produce official phenology products (e.g., MODIS MCD12Q2) (Moon et al., 2019). The latter generates a smoothed 16-day NDVI time series and has also been incorporated into some official vegetation index datasets (e.g., MODIS MOD/MYD13) (Huete et al., 2002). Even so, it is worth noting that the 16-day MODIS NDVI time series may still contain the gaps when no data are available over a given 16-day period, in which cases we used linear interpolation to fill these gaps (Fig. 1b and d). Considering the potential saturation effects of NDVI (Gao et al., 2023, 2000; Zeng et al., 2023), we also calculated the enhanced vegetation index (EVI) from the Himawari-8 TOA and SR products using Eq. (3) and repeated the steps of the above NDVI processing.

![Figure 1](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr1_lrg.jpg?httpAccept=%2A%2F%2A)

The concept diagrams illustrate the processing of NDVI time series. (a) and (b) display the processing of Himawari-8 SR and MODIS SR NDVI time series for a specific pixel in continental Southeast Asia (104.9E, 15.1 N). (c) and (d) show the same processing for a specific pixel in maritime Southeast Asia (111.6E, 1.1S). The pale green shaded areas in the background indicate the dates with no available clear observations. SR: surface reflectance. SP filter: penalized cubic splines filter. MVC method: maximum value composite method. The red arrow in (a) points to an example of an abnormally high value. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

(3)

$$
\mathit{EVI} = 2.5 \times \frac{B_{4} - B_{3}}{B_{4} + 6 \times B_{3} - 7.5 \times B_{1} + 1}
$$

where $B_{1}$, $B_{3}$ and $B_{4}$ represent the blue (0.47 μm), red (0.64 μm) and NIR (0.86 μm) reflectance of Himawari-8, respectively.

### Defining dry and wet seasons

To define dry and wet seasons for each pixel, we first extracted the start and end of the wet season (i.e., SWS and EWS) from the ERA5-Land daily precipitation time series using Eq. (4) (Dunning et al., 2016; Jiang et al., 2019; Tian et al., 2024; Xu et al., 2021).

(4)

$$
C(d) = \sum_{i = 1\mathit{Jan}}^{d}Q_{i} - \overline{Q}
$$

where $C(d)$ is the cumulative daily precipitation anomaly. $Q_{i}$ refers to the daily precipitation, and $\overline{Q}$ represents the mean precipitation throughout the year. $C_{\mathit{min}}$ and $C_{\mathit{max}}$ dates are extracted from the smoothed $C(d)$ processed by a Gaussian filter, corresponding to the SWS and EWS, respectively. The period between SWS and EWS constituted the wet season, and the remaining period in each calendar year is considered the dry season (Fig. 2a). Considering that some tropical regions experience two alternations of dry-wet seasons, we employed harmonic analysis to quantify the number of dry-wet seasons each year by a Fourier transform of the entire daily precipitation time series (Liebmann et al., 2012; Tian et al., 2024; Xu et al., 2021). Regions with a harmonic ratio greater than one were identified as having two cycles of dry-wet seasons (Tian et al., 2024; Xu et al., 2021). For these regions, the dry and wet seasons of each alternation were defined, respectively (Fig. 2b).

![Figure 2](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr2_lrg.jpg?httpAccept=%2A%2F%2A)

The concept diagrams demonstrate the definitions of single and double dry-wet cycles for two specific pixels (a) (106.4E, 21.1 N) and (b) (101.9E, 2.7 N), respectively. The blue shaded areas indicate the duration of the wet season, and the yellow solid lines represent the mean precipitation. SWS: the start of the wet season. EWS: the end of the wet season. SWS1 and EWS1 denote the start and end of the first wet season, while SWS2 and EWS2 indicate the start and end of the second wet season. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

### Identifying the climate factors driving green-up of vegetation

To examine the green-up of vegetation in dry or wet seasons for each pixel, we calculated the NDVI anomaly (i.e., $\mathrm{\Delta}\mathit{NDVI}$) and its difference between dry and wet seasons (i.e., $\mathit{NDVI}_{d - w}$) using Eqs. (5) and (6).

(5)

$$
\mathrm{\Delta}\mathit{NDVI} = \mathit{NDVI} - \overline{\mathit{NDVI}}
$$

(6)

$$
\mathit{NDVI}_{d - w} = \overline{\mathit{NDVI}_{\mathit{dry}}} - \overline{\mathit{NDVI}_{\mathit{wet}}}
$$

where $\mathit{NDVI}$ refers to the NDVI time series processed by the SP filter or MVC method, and $\overline{\mathit{NDVI}}$ represents the mean of the NDVI time series throughout the entire year. $\overline{\mathit{NDVI}_{\mathit{dry}}}$ and $\overline{\mathit{NDVI}_{\mathit{wet}}}$ represent the mean of $\mathrm{\Delta}\mathit{NDVI}$ in dry and wet seasons, respectively. Positive $\mathit{NDVI}_{d - w}$ values indicate the green-up of vegetation in dry seasons, while negative $\mathit{NDVI}_{d - w}$ values suggest the green-up of vegetation in wet seasons. Subsequently, we further quantified the contribution of climate factors driving the seasonality of vegetation greenness for each pixel. Based on previous studies, we selected four underlying factors for the analysis: $T$ (Zhang et al., 2016), $\mathit{SWC}$ (Borchert, 1994; Vico et al., 2015), $\mathit{RAD}$ (Bi et al., 2015; Huete et al., 2006) and $\mathit{VPD}$ (Brando et al., 2010; Green et al., 2020). We used a multiple regression method (Wang et al., 2018; Zhu et al., 2016) to quantify the climate sensitivities of each factor. To minimize the effects of collinearity among climate factors, we conducted a reduced variable regression analysis (Wang et al., 2018) based on Eq. (7).

(7)

$$
Y_{\mathit{NDVI}} = \gamma_{T} \times \mathrm{\Delta}_{T} + \gamma_{\mathit{SWC}} \times \mathrm{\Delta}_{\mathit{SWC}} + \gamma_{\mathit{RAD}} \times \mathrm{\Delta}_{\mathit{RAD}} + \gamma_{\mathit{VPD}} \times \mathrm{\Delta}_{\mathit{VPD}} + \varepsilon
$$

where $Y_{\mathit{NDVI}}$ represents the standardized daily NDVI anomalies in dry or wet seasons using the z-score function, a statistical measure that centers and scales data (mean: 0 and standard deviation: 1) (Barbosa et al., 2006; Li et al., 2013). This process ensures that data from different distributions are directly comparable. $\mathrm{\Delta}_{T}$, $\mathrm{\Delta}_{\mathit{SWC}}$, $\mathrm{\Delta}_{\mathit{RAD}}$, and $\mathrm{\Delta}_{\mathit{VPD}}$ correspond to the standardized climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry or wet seasons using the z-score function. The $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients using least square (LSQ) estimates with a 95% confidence interval, and $\varepsilon$ refers to unexplained variation of regression models. For each reduced variable regression, the residuals ($e$), i.e., the differences between each observation and estimate from the regression models, were further employed to evaluate the climate sensitivity of the excluded variable using Eq. (8).

(8)

$$
e = \sigma \times \mathit{factor}
$$

where $\sigma$ is the regression coefficient using LSQ with a 95% confidence interval and reflects the sensitivity of NDVI to each climate factor. Positive and negative $\sigma$ values represent the positive and negative climate sensitivities of vegetation greenness to climate factors, respectively. The $\mathit{factor}$ means $\mathrm{\Delta}_{T}$, $\mathrm{\Delta}_{\mathit{SWC}}$, $\mathrm{\Delta}_{\mathit{RAD}}$, and $\mathrm{\Delta}_{\mathit{VPD}}$. Eq. (7) suggests that climate anomalies and climate sensitivities jointly contribute to NDVI seasonality. Therefore, we decomposed and quantified the contributions of seasonal greenness changes (i.e., $\mathit{NDVI}_{d - w}$) into ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by changes in climate sensitivities) using Eqs. (9)–(12).

(9)

$$
{\mathit{NDVI}_{d - w}}_{\mathit{cli}} = \mathit{NDVI}_{\mathit{dry}}' - \mathit{NDVI}_{\mathit{wet}}
$$

(10)

$$
{\mathit{NDVI}_{d - w}}_{\mathit{sen}} = {\mathit{NDVI}_{d - w}}_{\mathit{total}} - {\mathit{NDVI}_{d - w}}_{\mathit{cli}}
$$

(11)

$$
\mathit{NDVI}_{\mathit{dry}}' = \gamma_{T_{\mathit{wet}}} \times \mathrm{\Delta}_{T_{\mathit{dry}}} + \gamma_{\mathit{SWC}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{SWC}_{\mathit{dry}}} + \gamma_{\mathit{RAD}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{RAD}_{\mathit{dry}}} + \gamma_{\mathit{VPD}_{\mathit{wet}}} \times \mathrm{\Delta}_{\mathit{VPD}_{\mathit{dry}}} + \varepsilon
$$

(12)

$$
{\mathit{NDVI}_{d - w}}_{\mathit{total}} = \mathit{NDVI}_{\mathit{dry}} - \mathit{NDVI}_{\mathit{wet}}
$$

where ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ are $\mathit{NDVI}_{d - w}$ values induced by climate anomalies and the changes in climate sensitivities, respectively. Considering that both climate anomalies and climate sensitivities to vegetation greenness are different between dry and wet seasons, we introduced an intermediate variable (i.e., $\mathit{NDVI}_{\mathit{dry}}'$). $\mathit{NDVI}_{\mathit{dry}}'$ refers to the NDVI anomalies in dry seasons when climate sensitivities to vegetation greenness are assumed to be consistent with those in wet seasons (i.e., using climate sensitivities of vegetation greenness in wet seasons: $\gamma_{T_{\mathit{wet}}}$, $\gamma_{\mathit{SWC}_{\mathit{wet}}}$, $\gamma_{\mathit{RAD}_{\mathit{wet}}}$ and $\gamma_{\mathit{VPD}_{\mathit{wet}}}$). $\mathrm{\Delta}_{T_{\mathit{dry}}}$, $\mathrm{\Delta}_{\mathit{SWC}_{\mathit{dry}}}$, $\mathrm{\Delta}_{\mathit{RAD}_{\mathit{dry}}}$ and $\mathrm{\Delta}_{\mathit{VPD}_{\mathit{dry}}}$ are standardized climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry seasons, and $\varepsilon$ refers to unexplained variation of regression models. ${\mathit{NDVI}_{d - w}}_{\mathit{total}}\hspace{0.25em}$represents the total NDVI anomalies between dry and wet seasons.

## Results

### The length of dry and wet seasons in Southeast Asia

Considering the complexity of dry-wet seasonality across Southeast Asia, we used a harmonic analysis on daily precipitation time series to determine whether each pixel experiences a single or double cycles of dry-wet seasons (Fig. 2) (see Materials and methods). We found that 83.3% of regions in Southeast Asia, including continental Southeast Asia, southern maritime Southeast Asia and the majority of New Guinea, experienced a single dry-wet cycle annually (Fig. 3e). In comparison, 16.7% of regions in Southeast Asia, distributed along the equator, experienced double dry-wet cycles each year (harmonic ratio &gt; 1) (Fig. 3d-f) (see Materials and methods). Across Southeast Asia, the dry season (mean: 195.1 days) was typically longer than that of the wet season (mean: 169.9 days) (Fig. 3a-c).

![Figure 3](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr3_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the length of dry and wet seasons in 2019 in Southeast Asia. Spatial patterns of (a) dry-season length and (b) wet-season length, (d) harmonic ratio and (e) cycles of dry-wet seasons. Regions with a harmonic ratio greater than one were identified as having double cycles of dry-wet seasons (see Materials and methods). (c) Histograms summarize the length of dry and wet seasons, and dotted lines indicate their mean values. (f) Histogram summarizes the values of the harmonic ratio, and dotted lines indicate the reference line of one. The numbers 1 and 2 in (e) indicate the locations of Fig. 2 (a) and (b).

### The differences in vegetation greenness between dry and wet seasons

Himawari-8 SR NDVI and MODIS SR NDVI showed substantial spatial differences in the seasonality of vegetation greenness, especially in maritime Southeast Asia (Figs. 4 and 5 ). We found that Himawari-8 SR NDVI showed 42.1% positive $\mathit{NDVI}_{d - w}$ (i.e., green-up in dry seasons) and 57.9% negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons), with dry-season green-up prevailing in the majority of maritime Southeast Asia and wet-season green-up occurring in continental Southeast Asia (Fig. 4a and c). On the contrary, MODIS SR NDVI exhibited negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons) in the majority of Southeast Asia, accounting for 82.1% of the regions (Fig. 4b and c). To test the robustness of the green-up signals, we replaced the SP smoothing method with the MVC method to reconstruct the NDVI time series and repeated the analysis. We found that the difference between Himawari-8 SR NDVI and MODIS SR NDVI in greenness seasonality remained (Figs. 4 and 5), i.e., Himawari-8 SR NDVI can capture more dry-season green-up signals than MODIS SR NDVI. Based on the robustness of the high-frequency observations from Himawari-8 SR products across processing methods (Figs. 4 and 5 and Fig. A2), we opted to use the results from SP-processed Himawari-8 SR NDVI (Fig. 4a) for our subsequent analysis.

![Figure 4](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr4_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the differences in vegetation greenness (i.e., NDVI) in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) were calculated from daily NDVI time series acquired from (a) Himawari-8 SR and (b) MODIS SR, processed by the penalized cubic splines (SP) filter. The $\mathit{NDVI}_{d - w}$ values were calculated from the 16-day NDVI time series acquired from (d) Himawari-8 SR and (e) MODIS SR, processed by the maximum value composite (MVC) method. (c) and (f) summarize their values by latitude, and the solid lines indicate the mean values. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). The shaded error bars in (c) and (f) indicate the mean ± standard deviation. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

![Figure 5](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr5_lrg.jpg?httpAccept=%2A%2F%2A)

The glyph-maps of NDVI time series in 2019 derived from Himawari-8 and MODIS for each sub-region in Southeast Asia. (a) and (c) are the glyph-maps of regional average NDVI processed by the penalized cubic splines (SP) filter and the maximum value composite (MVC) method (see Materials and methods). (b) and (d) are zoom-in regions corresponding to the sub-regions in (a) and (c), and the colour of the box border indicates the location of the regions. Each grid cell covers a 6° × 9° space. Grid cells marked with crosses indicate no available data or no land surface in the cell.

Considering the potential saturation effects of NDVI, we also calculated the differences in the EVI between dry and wet seasons (see Materials and methods). We found that $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ derived from Himawari-8 SR products showed high agreement for both data processing methods (Fig. A3). Additionally, to examine the potential effects of BRDF on NDVI, we have also validated our results by comparing MODIS SR NDVI and MODIS BRDF-normalized SR NDVI (nadir view and solar zenith angle = 45°) (see Materials and methods). As expected, our results confirmed their high consistencies (R-squared: 0.86 for the SP filter and 0.80 for the MVC method) (Fig. A4). This analysis, in combination with a preliminary examination of the BRDF effects on geostationary-derived NDVI (Seong et al., 2020), suggested that the BRDF has limited impacts on NDVI seasonality, though it might affect the magnitude of NDVI values.

### Climate drivers for the seasonality of greenness

Across Southeast Asia, the climate anomalies and climate sensitivities of vegetation greenness between dry and wet seasons differ considerably (Fig. 6 and Fig. A5). Wet seasons exhibited higher $T$ (air temperature) and $\mathit{SWC}$ (soil water content), but lower $\mathit{RAD}$ (solar radiation) and $\mathit{VPD}$ (vapor pressure deficit) compared to dry seasons (Fig. 6a-d). On average, the differences in $T$, $\mathit{SWC}$, $\mathit{RAD}$ and $\mathit{VPD}$ between dry and wet seasons were −0.83 °C, −0.09 m<sup>3</sup>m<sup>−3</sup>, 1.74\*10<sup>6</sup> Jm<sup>−2</sup>, and 0.34 kPa, respectively. We also found significant latitude-based differences in the climate sensitivities of vegetation greenness between dry and wet seasons (Fig. 6e-h). Specifically, across Southeast Asia, the sensitivity of vegetation greenness to temperature ($\gamma_{T}$) was weaker in dry seasons compared to wet seasons (Fig. 6e and Fig. A5i and m), suggesting that vegetation greenness decreased faster with temperature in wet seasons. The sensitivities of vegetation greenness to water stress (i.e., $\mathit{SWC}$ and $\mathit{VPD}$), $\gamma_{\mathit{SWC}}$ and $\gamma_{\mathit{VPD}}$ showed more significant differences in continental and maritime Southeast Asia, respectively (Fig. 6f and h, and Fig. A5j, n, l and p), especially for $\gamma_{\mathit{SWC}}$. This indicates that vegetation greenness is more sensitive to $\mathit{SWC}$ in continental Southeast Asia in dry seasons. The sensitivity of vegetation greenness to solar radiation ($\gamma_{\mathit{RAD}}$) also exhibited clear differences in continental Southeast Asia, with the $\gamma_{\mathit{RAD}}$ changing from positive in wet seasons to negative in dry seasons (Fig. 6g and Fig. A5k and o). Our analysis suggested that climate sensitivities of vegetation greenness between dry and wet seasons played important roles in modulating the seasonality of vegetation greenness across Southeast Asia.

![Figure 6](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr6_lrg.jpg?httpAccept=%2A%2F%2A)

Comparison of (a)-(d) climate anomalies and (e)-(h) climate sensitivities of vegetation greenness in dry and wet seasons across different latitudes. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ correspond to the climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry and wet seasons. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients (i.e., climate sensitivities of vegetation greenness) corresponding to each climate factor (see Materials and methods). The solid lines represent the mean values, while the dotted lines indicate reference lines of zero. The cross symbols (×) at each degree of latitude denote statistical significance between dry and wet seasons (*p* ≤ 0.001, *t*-test). The shaded error bars indicate the mean ± standard deviation.

### Differences among different vegetation types

To assess the contributions of climate anomalies and changes in climate sensitivities to greenness seasonality, we decomposed changes in NDVI (i.e., $\mathit{NDVI}_{d - w}$) into ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by the changes in climate sensitivities) (see Materials and methods). We found a positive contribution of climate anomalies to vegetation greenness (i.e., positive ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$) in maritime Southeast Asia (Fig. 7a and c), while the changes in climate sensitivities mostly exhibited a negative impact on NDVI (i.e., negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$) in continental Southeast Asia (Fig. 7b and c). We further examined the differences in $\mathit{NDVI}_{d - w}$, ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ across main vegetation types in Southeast Asia, including evergreen forests, deciduous forests and croplands (Fig. A1). We found that $\mathit{NDVI}_{d - w}$ for maritime evergreen forests tended to be positive (i.e., green-up in dry seasons), but $\mathit{NDVI}_{d - w}$ for deciduous forests, croplands and continental evergreen forests were mostly negative (i.e., green-up in wet seasons) (Fig. 7d). The maritime evergreen forests showed positive ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$, while others vegetation types showed negative ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ at different levels (Fig. 7e and f). The sum of ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ determined the observed seasonality. Specifically, for maritime evergreen forests, we found that climate anomalies drove the green-up in dry seasons, though this effect was partly offset by changes in climate sensitivities (Fig. 7d-f). For deciduous forests, croplands and continental evergreen forests, due to stronger effects of the changes in climate sensitivities, they appeared to green up in wet seasons (Fig. 7d-f).

![Figure 7](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr7_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of $\mathit{NDVI}_{d - w}$ induced by climate anomalies and the changes in climate sensitivities. (a) and (b) are spatial patterns of ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by climate anomalies) and ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ (i.e., $\mathit{NDVI}_{d - w}$ induced by the changes in climate sensitivities), respectively. (c) summarizes the values by latitude. The solid lines indicate the mean values, and the shaded error bars indicate the mean ± standard deviation. Violin and box plots summarize the values of (d) $\mathit{NDVI}_{d - w}$, (e) ${\mathit{NDVI}_{d - w}}_{\mathit{cli}}$ and (f) ${\mathit{NDVI}_{d - w}}_{\mathit{sen}}$ for four vegetation types. EF<sub>con</sub>: continental evergreen forests. EF<sub>mar</sub>: maritime evergreen forests. DF: deciduous forests. CL: croplands. \*\*\*: *p* ≤ 0.001. non-significance (ns): *p* &gt; 0.05. *n*: number of pixels.

## Discussion

In this study, we examined the seasonality of vegetation greenness in Southeast Asia using new observations from a geostationary satellite (i.e., Himawari-8). We found that across Southeast Asia, 42.1% of the regions (mainly maritime evergreen forests) showed positive $\mathit{NDVI}_{d - w}$ (i.e., green-up in dry seasons), while 57.9% of the regions (mainly deciduous forests, croplands and continental evergreen forests) showed negative $\mathit{NDVI}_{d - w}$ (i.e., green-up in wet seasons) (Fig. 7d). Meanwhile, we found that both climate anomalies and the changes in climate sensitivities of vegetation greenness between dry and wet seasons imposed impacts on $\mathit{NDVI}_{d - w}$, with climate anomalies driving green-up in dry seasons but changes in climate sensitivities of vegetation greenness driving green-up in wet seasons (Fig. 7). We found that the seasonality of vegetation greenness in Southeast Asia was governed by the interplay of these two processes.

We utilized new observations from the geostationary Himawari-8 satellite to detect the seasonality of vegetation greenness in Southeast Asia and found spatially inconsistent results compared to those from MODIS (Fig. 4). The difference likely arises from the numbers of clear observations from two sensors, as optical sensors are often obscured by persistent cloud cover in the tropics (Hashimoto et al., 2021; Wilson and Jetz, 2016). We further analyzed the ratios of clear observations from the Himawari-8 and MODIS products. The numbers of clear observations from Himawari-8 SR and MODIS SR were extracted from their respective cloud mask bands. We found that on an annual basis, Himawari-8 provided 43.5% more clear daily observations and 18.4% more clear 16-day observations than those of MODIS (Fig. 8i). Based on this, we further found that in the regions where Himawari-8 and MODIS reported conflicting seasonality, there were greater differences in the number of clear observations between the two sensors (Fig. 9 ). The increase in the availability of clear observations enables geostationary satellites (e.g., Himawari-8) to capture the seasonality of tropical vegetation greenness more effectively than optical polar-orbit satellites (e.g., MODIS). Meanwhile, we also acknowledge recent progress in using spatiotemporal observations from polar-orbit satellites to statistically address the cloud issues in the tropics and reconstruct long-term vegetation index series (Cai et al., 2025; Cao et al., 2018). These methods can complement geostationary observations, which often have shorter temporal coverage.

![Figure 8](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr8_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the ratio of clear observations for the daily and 16-day time series in 2019. Spatial patterns of the ratio of Himawari-8-derived clear observations for the (a) daily and (d) 16-day time series in 2019. Spatial patterns of the ratio of MODIS-derived clear observations for the (b) daily and (e) 16-day time series in 2019. Spatial patterns of the differences in the ratio of Himawari-8- and MODIS-derived clear observations for the (g) daily and (h) 16-day time series in 2019. (c), (f) and (i) summarize their values by latitude, and the solid lines indicate the mean values. The shaded error bars in (c), (f) and (i) indicate the mean ± standard deviation.

![Figure 9](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr9_lrg.jpg?httpAccept=%2A%2F%2A)

The relationship between the number of conflicting $\mathit{NDVI}_{d - w}$ pixels (i.e., opposite seasonality detected by Himawari-8 SR NDVI and MODIS SR NDVI) and their differences in the ratio of clear observations. The pie in each sub-figure represents the number of conflicting $\mathit{NDVI}_{d - w}$ pixels. SP filter: penalized cubic splines filter. MVC method: maximum value composite method.

Our study reported that the green-up of maritime evergreen forests in dry seasons is primarily driven by relatively higher radiation levels (Fig. 10g). This result is consistent with earlier evidence of the green-up in Amazon forests in dry seasons (Huete et al., 2006). Several recent studies have suggested that this apparent impact of radiation is due to the coincidence of radiation patterns with the emergence of new leaf flushing. Specifically, young leaves have been found to exhibit higher reflectance in the near infrared band compared to old leaves. This change in leaf quality has been identified as the driving factor behind the shift in greenness (Gonçalves et al., 2023; Saleska et al., 2016; Wu et al., 2016). This coordination between radiation and leaf flushing is likely a main mechanism for the green-up of evergreen forests in maritime Southeast Asia in dry seasons. While our study is unable to provide direct observations of the coordination between leaf quality and radiation, there are some pieces of local evidence from Southeast Asia showing the leaf flushing of trees in dry seasons (Elliott et al., 2006). We propose that the radiation drives the green-up of evergreen forests in maritime Southeast Asia in dry seasons through a mechanism similar to that in the Amazon. Meanwhile, we found that for maritime evergreen forests, dry seasons show greater water stress (i.e., lower $\mathit{SWC}$ and higher $\mathit{VPD}$) than wet seasons (Fig. 10f and h), which may suppress vegetation productivity and growth in dry seasons (Kannenberg et al., 2024; Yuan et al., 2019). However, compared to deciduous forests, croplands and continental evergreen forests, the differences in $\mathit{SWC}$ and $\mathit{VPD}$ between dry and wet seasons are minor for maritime evergreen forests (Fig. 10), suggesting that deciduous forests, croplands and continental evergreen forests may experience greater growth suppression in dry seasons than maritime evergreen forests.

![Figure 10](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr10_lrg.jpg?httpAccept=%2A%2F%2A)

The climate anomalies in dry and wet seasons for different vegetation types. Violin and box plots summarize the values of climate anomalies in dry and wet seasons for (a)-(d) EF<sub>con</sub>: continental evergreen forests, (e)-(h) EF<sub>mar</sub>: maritime evergreen forests, (i)-(l) DF: deciduous forests and (m)-(p) CL: croplands. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ are anomalies of air temperature, soil water content, solar radiation, and vapor pressure deficit, respectively. \*\*\* *p* ≤ 0.001.

In contrast to the seasonality of maritime evergreen forests, we found that deciduous forests, croplands and continental evergreen forests in Southeast Asia tended to green up in wet seasons (Fig. 7d). Our statistical analysis indicated that this phenomenon was mainly driven by the changes in their climate sensitivities between dry and wet seasons (Fig. 7e and f). Specifically, in dry seasons, deciduous forests, croplands and continental evergreen forests exhibited greater sensitivities to temperature and soil moisture, but lower sensitivities to radiation compared to wet seasons (Fig. 11 ). The mechanisms underlying the changes in climate sensitivities for different vegetation types in Southeast Asia may differ. For deciduous forests and continental evergreen forests, the changes in climate sensitivities were also noted in previous studies (Wang et al., 2018; Zhang et al., 2021), where they reported that vegetation become more sensitive to temperature and water in dry seasons, compared to wet seasons, though their results are based on an analysis at the interannual time scale. The enhanced sensitivity to temperature in dry seasons was attributed to enhanced evapotranspiration and thus leaf cooling in dry seasons, making the thermoregulation less effective in dry seasons and emerging as a stronger temperature sensitivity (Wang et al., 2018). This seems to be consistent with flux site observations where evapotranspiration was higher in dry seasons (Costa et al., 2010; Da Rocha et al., 2004). The enhanced sensitivity to water in dry seasons is related to the increased evaporative demand of the atmosphere, which may cause the higher sensitivity of deciduous forests and continental evergreen forests to water stress (Zhang et al., 2018, 2021) (Fig. 11). Meanwhile, for croplands, the changes in climate sensitivities are likely driven by variations in plant species or crop rotations. In continental Southeast Asia, the wet seasons typically span from May to the end of October (Fig. 5) (Suepa et al., 2016; Xu et al., 2021), during which rice is the prevailing crop, with the growing season extending from March to November (Suepa et al., 2016). Outside of the wet seasons, the main land use types vary substantially, with maize being common or fallow land used for the growth of natural vegetation (Lasco et al., 2011). In some places, the same crops (e.g., rice) are planted for the second round in dry seasons, and the differences in crop varieties may contribute to changes in climate sensitivities (Jiang et al., 2016; Suprihatin et al., 2021).

![Figure 11](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-gr11_lrg.jpg?httpAccept=%2A%2F%2A)

The climate sensitivities of vegetation greenness in dry and wet seasons for different vegetation types. Violin and box plots summarize the values of climate sensitivities in dry and wet seasons for (a)-(d) EF<sub>con</sub>: continental evergreen forests, (e)-(h) EF<sub>mar</sub>: maritime evergreen forests, (i)-(l) DF: deciduous forests and (m)-(p) CL: croplands. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ are regression coefficients of air temperature, soil water content, solar radiation, and vapor pressure deficit, respectively (see Materials and methods). \*\*\* *p* ≤ 0.001. \* *p* ≤ 0.05.

We also note that a recent study reported higher gross primary productivity (GPP) in wet seasons at four eddy covariance sites in Southeast Asia (Yang et al., 2023). Therefore, we further examined the relationship between the seasonality of NDVI and GPP using flux data from five available sites located in Southeast Asia, namely four evergreen forest sites (BNS, SKR, PSO and LHP) and a deciduous forest site (PSO) (Fig. A1). We found that the Himawari-8 SR-derived NDVI time series and leaf area index (LAI) time series calculated based on light transmittance (Yang et al., 2023) generally exhibited similar seasonal patterns, although some differences were observed (Fig. A6). Note that the method for calculating LAI based on light transmittance relies on assumptions about canopy structure and is subject to uncertainty. We found that all continental sites exhibited higher GPP in wet seasons compared to dry seasons, consistent with NDVI patterns we observed (Fig. A6p and q). This phenomenon can be attributed to the ample water supply in wet seasons, which enhances canopy conductance and photosynthesis, resulting in higher GPP compared to dry seasons (Fig. A6q) (Yang et al., 2023).

We also acknowledge that previous studies reporting the green-up of tropical vegetation in dry seasons were based on representative dry and wet months (Morton et al., 2014; Saleska et al., 2016). Here, we defined the dry and wet seasons using daily precipitation time series (Tian et al., 2024; Xu et al., 2022), which provides fine information on the dry-wet seasons transition (Fig. 2). To test the robustness of our results regarding the definition of dry and wet seasons, we calculated $\mathit{NDVI}_{d - w}$ values between representative dry and wet months, which were defined as the months with the locally lowest and highest total precipitation in Southeast Asia (Fig. A7a-d). We found that the results derived from this conventional definition showed highly similar spatial patterns in greenness seasonality to our main results (Fig. 4a and d and Fig. A7e and f), suggesting the robustness of our results.

## Conclusions

In conclusion, we used new observations from the Himawari-8 geostationary satellite to examine the seasonality of vegetation greenness in Southeast Asia. We found that across Southeast Asia, maritime evergreen forests typically green up in dry seasons, while deciduous forests, croplands and continental evergreen forests tend to green up in wet seasons. The positive anomaly in solar radiation is the primary reason behind the dry-season green-up of maritime evergreen forests, while the changes in the sensitivities to climate between dry and wet seasons contribute to the wet-season green-up of deciduous forests, croplands and continental evergreen forests. Our study offers novel insights into vegetation dynamics in Southeast Asia and critical knowledge to support the estimation of the carbon cycle and other ecosystem functions in the region.

## Code availability

The codes used for data processing and analysis in this study are available at https://zenodo.org/records/14847742.

## CRediT authorship contribution statement

**Jiaqi Tian:** Writing – review & editing, Writing – original draft, Visualization, Software, Methodology, Investigation, Formal analysis, Data curation, Conceptualization. **Xiangzhong Luo:** Writing – review & editing, Writing – original draft, Supervision, Methodology, Funding acquisition, Conceptualization. **Weile Wang:** Writing – review & editing, Methodology, Data curation, Conceptualization. **Liyao Yu:** Writing – review & editing, Methodology, Data curation, Conceptualization. **Diane Tan Ting Ng:** Writing – review & editing, Conceptualization. **Kazuhito Ichii:** Writing – review & editing, Methodology, Funding acquisition, Conceptualization. **Yao Zhang:** Writing – review & editing, Conceptualization. **Xiaoyang Zhang:** Writing – review & editing, Methodology, Conceptualization.

## Acknowledgements

J.T. and X.L. are supported by the NUS Presidential Young Professorship awarded to X.L. (A-0003625-01-00) and a Tier 2 Academic Research Fund from Singapore Ministry of Education (MOE-T2EP50222-0006). K.I. is supported by the JSPS KAKENHI, JP22H05004, and JP20K20487, and JSPS Core-to-Core Program (grant number: JPJSCCA20220008).

## Appendix

![Figure A1](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx1_lrg.jpg?httpAccept=%2A%2F%2A)

Land cover map in Southeast Asia. This map is from the European Space Agency Climate Change Initiative (ESA CCI) (v2.1.1) product in 2019. The flux sites include BNS (101.20E, 21.95 N), SKR (101.92E, 14.49 N), MKL (98.84E, 14.58 N), PSO (102.30E, 2.97 N) and LHP (114.04E, 4.20 N).

![Figure A2](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx2_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the differences in vegetation greenness (i.e., NDVI and EVI) derived from Himawari-8 TOA products in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ values are the differences in vegetation greenness between dry and wet seasons (see Materials and methods). SP filter: penalized cubic splines filter. MVC method: maximum value composite method. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ (or $\mathit{EVI}_{d - w}$) &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ (or $\mathit{EVI}_{d - w}$) < 0 (i.e., green-up in wet seasons). (c) and (f) summarize their values by latitude, and the solid lines indicate the mean values. The shaded error bars in (c) and (f) indicate the mean ± standard deviation. TOA: top-of-atmosphere reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

![Figure A3](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx3_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the differences in vegetation greenness (i.e., EVI) in 2019 between dry and wet seasons. The $\mathit{EVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) are calculated from daily EVI time series acquired from Himawari-8 SR, processed by the penalized cubic splines (SP) filter (a) and the maximum value composite (MVC) method (c). The pie in each sub-figure represents the proportions of $\mathit{EVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{EVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). Scatterplots of $\mathit{NDVI}_{d - w}$ and $\mathit{EVI}_{d - w}$ are derived from Himawari-8 SR, processed by SP filter (b) and MVC method (d). The bright-yellow colour suggests a high kernel density. The red solid lines and black dotted lines represent the best linear fit of the data and the 1:1 reference lines. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

![Figure A4](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx4_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the differences in vegetation greenness (i.e., NDVI) in 2019 between dry and wet seasons. The $\mathit{NDVI}_{d - w}$ values (i.e., the differences in vegetation greenness between dry and wet seasons; see Materials and methods) are calculated from daily NDVI time series acquired from MODIS SR and BRDF-normalized SR (nadir view and solar zenith angle = 45°), processed by the penalized cubic splines (SP) filter (a) and the maximum value composite (MVC) method (c). The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry seasons) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet seasons). Scatterplots of $\mathit{NDVI}_{d - w}$ are derived from MODIS SR and BRDF-normalized SR, processed by SP filter (b) and MVC method (d). The bright-yellow colour suggests a high kernel density. The red solid lines and black dotted lines represent the best linear fit of the data and the 1:1 reference lines. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

![Figure A5](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx5_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of (a)-(h) climate anomalies and (i)-(p) climate sensitivities of vegetation greenness in dry and wet seasons. $T$, $\mathit{SWC}$, $\mathit{RAD}$, and $\mathit{VPD}$ correspond to the climate anomalies of daily air temperature, soil water content, solar radiation, and vapor pressure deficit in dry and wet seasons. $\gamma_{T}$, $\gamma_{\mathit{SWC}}$, $\gamma_{\mathit{RAD}}$, and $\gamma_{\mathit{VPD}}$ refer to the climate sensitivities of vegetation greenness corresponding to each climate factor (see Materials and methods).

![Figure A6](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx6_lrg.jpg?httpAccept=%2A%2F%2A)

Daily NDVI, LAI, GPP and precipitation time series in 5 specific flux sites. (a) BNS (101.20E, 21.95 N), (b) SKR (101.92E, 14.49 N), (c) MKL (98.84E, 14.58 N), (d) PSO (102.30E, 2.97 N) and (e) LHP (114.04E, 4.20 N). The blue shaded areas indicate the duration of the wet season. The LAI and GPP data for BNS, SKR, MKL and PSO sites are extracted by Figs. 4 and 5 in (Yang et al., 2023). (f) The average NDVI and GPP in dry and wet seasons. Please note the NDVI from the Himawari-8 SR in 2019 and all data for LHP site are also from 2019, while the LAI and GPP values for other sites were calculated from multiple years. Therefore, their seasonal patterns do not completely agree with each other. (p) and (q) are mean values of Himawari-8 SR NDVI and GPP in dry and wet seasons, respectively. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

![Figure A7](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425725000525-fx7_lrg.jpg?httpAccept=%2A%2F%2A)

Spatial patterns of the differences in vegetation greenness (i.e., NDVI) derived from Himawari-8 SR products in 2019 between dry and wet months. The $\mathit{NDVI}_{d - w}$ values are the differences in vegetation greenness between dry and wet months. The pie in each sub-figure represents the proportions of $\mathit{NDVI}_{d - w}$ &gt; 0 (i.e., green-up in dry months) and $\mathit{NDVI}_{d - w}$ < 0 (i.e., green-up in wet months). The dry and wet months are defined as the months with the lowest and highest total precipitation as the representative dry and wet months, respectively. (a) and (b) are spatial patterns of dry and wet months with the lowest and highest total precipitation, respectively. (e) and (f) are spatial patterns of total precipitation in dry and wet months, respectively. SP filter: penalized cubic splines filter. MVC method: maximum value composite method. SR: surface reflectance. (For interpretation of the references to colour in this figure legend, the reader is referred to the web version of this article.)

## Data availability

The Himawari-8 SR dataset can be downloaded via https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L2/MAIAC/. The Himawari-8 TOA dataset can be found from https://data.nas.nasa.gov/geonex/geonexdata/HIMAWARI8/GEONEX-L1G/. The MODIS MCD19A3CMG (v061) can be downloaded from https://lpdaac.usgs.gov/products/mcd19a3cmgv061/. The ESA CCI (v2.1.1) can be downloaded from https://www.esa-landcover-cci.org/?q=node/164. The ERA5-Land product can be accessed from https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=overview. The flux data can be downloaded via: https://asiaflux.net/index.php?page\_id=76.

## References (79 total, showing 79)

1. A. Baccini, S.J. Goetz, W.S. Walker, N.T. Laporte, M. Sun, D. Sulla-Menashe, J. Hackler, P.S.A. Beck, R. Dubayah, M.A. Friedl, S. Samanta, R.A. Houghton. 2012. Estimated carbon dioxide emissions from tropical deforestation improved by carbon-density maps. Nat. Clim. Chang., 2: 182-185. 10.1038/nclimate1354 [Baccini et al., 2012]

2. H.A. Barbosa, A.R. Huete, W.E. Baethgen. 2006. A 20-year study of NDVI variability over the Northeast Region of Brazil. J. Arid Environ., 67: 288-307. 10.1016/j.jaridenv.2006.02.022 [Barbosa et al., 2006]

3. A. Barkhordarian, S.S. Saatchi, A. Behrangi, P.C. Loikith, C.R. Mechoso. 2019. A recent systematic increase in vapor pressure deficit over tropical South America. Sci. Rep., 9: 15331. 10.1038/s41598-019-51857-8 [Barkhordarian et al., 2019]

4. C. Beer, M. Reichstein, E. Tomelleri, P. Ciais, M. Jung, N. Carvalhais, C. Rödenbeck, M.A. Arain, D. Baldocchi, G.B. Bonan, A. Bondeau, A. Cescatti, G. Lasslop, A. Lindroth, M. Lomas, S. Luyssaert, H. Margolis, K.W. Oleson, O. Roupsard, E. Veenendaal, N. Viovy, C. Williams, F.I. Woodward, D. Papale. 2010. Terrestrial gross carbon dioxide uptake: global distribution and covariation with climate. Science, 329: 834-838. 10.1126/science.1184984 [Beer et al., 2010]

5. A. Behrangi, E.J. Fetzer, S.L. Granger. 2016. Early detection of drought onset using near surface temperature and humidity observed from space. Int. J. Remote Sens., 37: 3911-3923. 10.1080/01431161.2016.1204478 [Behrangi et al., 2016]

6. K. Bessho, K. Date, M. Hayashi, A. Ikeda, T. Imai, H. Inoue, Y. Kumagai, T. Miyakawa, H. Murata, T. Ohno, A. Okuyama, R. Oyama, Y. Sasaki, Y. Shimazu, K. Shimoji, Y. Sumida, M. Suzuki, H. Taniguchi, H. Tsuchiyama, D. Uesawa, H. Yokota, R. Yoshida. 2016. An introduction to Himawari-8/9–Japan’s new-generation geostationary meteorological satellites. J. Meteorol. Soc. Jpn. Ser II, 94: 151-183. 10.2151/jmsj.2016-009 [Bessho et al., 2016]

7. J. Bi, Y. Knyazikhin, S. Choi, T. Park, J. Barichivich, P. Ciais, R. Fu, S. Ganguly, F. Hall, T. Hilker, A. Huete, M. Jones, J. Kimball, A.I. Lyapustin, M. Mõttus, R.R. Nemani, S. Piao, B. Poulter, S.R. Saleska, S.S. Saatchi, L. Xu, L. Zhou, R.B. Myneni. 2015. Sunlight mediated seasonality in canopy structure and photosynthetic activity of Amazonian rainforests. Environ. Res. Lett., 10: 064014. 10.1088/1748-9326/10/6/064014 [Bi et al., 2015]

8. R. Borchert. 1994. Soil and stem water storage determine phenology and distribution of tropical dry forest trees. Ecology, 75: 1437-1449. 10.2307/1937467 [Borchert, 1994]

9. P.M. Brando, S.J. Goetz, A. Baccini, D.C. Nepstad, P.S.A. Beck, M.C. Christman. 2010. Seasonal and interannual variability of climate and vegetation indices across the Amazon. Proc. Natl. Acad. Sci., 107: 14685-14690. 10.1073/pnas.0908741107 [Brando et al., 2010]

10. F.Q. Brearley, L.F. Banin, P. Saner. 2016. The ecology of the Asian dipterocarps. Plant Ecol. Divers., 9: 429-436. 10.1080/17550874.2017.1285363 [Brearley et al., 2016]

11. M. Cai, Y. Zhang, X. Guan, J. Qiu. 2025. An adaptive spatiotemporal tensor reconstruction method for GIMMS-3g+ NDVI. Remote Sens. Environ., 316: 114511. 10.1016/j.rse.2024.114511 [Cai et al., 2025]

12. R. Cao, Y. Chen, M. Shen, J. Chen, J. Zhou, C. Wang, W. Yang. 2018. A simple method to improve the quality of NDVI time-series data by integrating spatiotemporal information with the Savitzky-Golay filter. Remote Sens. Environ., 217: 244-257. 10.1016/j.rse.2018.08.022 [Cao et al., 2018]

13. P.-Y. Chen, R. Srinivasan, G. Fedosejevs, J.R. Kiniry. 2003. Evaluating different NDVI composite techniques using NOAA-14 AVHRR data. Int. J. Remote Sens., 24: 3403-3412. 10.1080/0143116021000021279 [Chen et al., 2003]

14. X. Chen, F. Maignan, N. Viovy, A. Bastos, D. Goll, J. Wu, L. Liu, C. Yue, S. Peng, W. Yuan, A.C. Da Conceição, M. O’Sullivan, P. Ciais. 2020. Novel representation of leaf phenology improves simulation of Amazonian Evergreen Forest photosynthesis in a land surface model. J. Adv. Model. Earth Syst., 12. 10.1029/2018ms001565. e2018MS001565 [Chen et al., 2020]

15. M.H. Costa, M.C. Biajoli, L. Sanches, A.C.M. Malhado, L.R. Hutyra, H.R. Da Rocha, R.G. Aguiar, A.C. De Araújo. 2010. Atmospheric versus vegetation controls of Amazonian tropical rain forest evapotranspiration: are the wet and seasonally dry rain forests any different?. J. Geophys. Res. Biogeosci., 115. 10.1029/2009jg001179. 2009JG001179 [Costa et al., 2010]

16. H.R. Da Rocha, M.L. Goulden, S.D. Miller, M.C. Menton, L.D.V.O. Pinto, H.C. De Freitas, A.M. E Silva Figueira. 2004. Seasonality of water and heat fluxes OVER a tropical forest in eastern AMAZONIA. Ecol. Appl., 14: 22-32. 10.1890/02-6001 [Da Rocha et al., 2004]

17. Y.M. De Moura, L.S. Galvão, T. Hilker, J. Wu, S. Saleska, C.H. Do Amaral, B.W. Nelson, A.P. Lopes, K.K. Wiedeman, N. Prohaska, R.C. De Oliveira, C.B. Machado, L.E.O.C. Aragão. 2017. Spectral analysis of amazon canopy phenology during the dry season using a tower hyperspectral camera and modis observations. ISPRS J. Photogramm. Remote Sens., 131: 52-64. 10.1016/j.isprsjprs.2017.07.006 [De Moura et al., 2017]

18. M. De Weirdt, H. Verbeeck, F. Maignan, P. Peylin, B. Poulter, D. Bonal, P. Ciais, K. Steppe. 2012. Seasonal leaf dynamics for tropical evergreen forests in a process-based global ecosystem model. Geosci. Model Dev., 5: 1091-1108. 10.5194/gmd-5-1091-2012 [De Weirdt et al., 2012]

19. C.M. Dunning, E.C.L. Black, R.P. Allan. 2016. The onset and cessation of seasonal rainfall over Africa. J. Geophys. Res.-Atmos., 121. 10.1002/2016jd025428 [Dunning et al., 2016]

20. S. Elliott, P.J. Baker, R. Borchert. 2006. Leaf Flushing during the dry season: the paradox of Asian monsoon forests. Glob. Ecol. Biogeogr., 15: 248-257 [Elliott et al., 2006]

21. R.C. Estoque, M. Ooba, V. Avitabile, Y. Hijioka, R. DasGupta, T. Togawa, Y. Murayama. 2019. The future of Southeast Asia’s forests. Nat. Commun., 10: 1829. 10.1038/s41467-019-09646-4 [Estoque et al., 2019]

22. H. Fang, W. Li, R. Myneni. 2013. The impact of potential land cover misclassification on MODIS Leaf Area Index (LAI) estimation: a statistical perspective. Remote Sens., 5: 830-844. 10.3390/rs5020830 [Fang et al., 2013]

23. Gao, X., Huete, A.R., Ni, W., Miura, T., 2000. Optical–Biophysical Relationships of Vegetation Spectra without Background Contamination. Remote Sens. Environ. 74, 609–620. doi: https://doi.org/10.1016/S0034-4257(00)00150-4 . [Gao et al., 2000]

24. Si Gao, R. Zhong, K. Yan, X. Ma, X. Chen, J. Pu, Sicong Gao, J. Qi, G. Yin, R.B. Myneni. 2023. Evaluating the saturation effect of vegetation indices in forests using 3D radiative transfer simulations and satellite observations. Remote Sens. Environ., 295: 113665. 10.1016/j.rse.2023.113665 [Gao et al., 2023]

25. J. Gomis-Cebolla, V. Rattayova, S. Salazar-Galán, F. Francés. 2023. Evaluation of ERA5 and ERA5-land reanalysis precipitation datasets over Spain (1951–2020). Atmos. Res., 284: 106606. 10.1016/j.atmosres.2023.106606 [Gomis-Cebolla et al., 2023]

26. N.B. Gonçalves, R. Dalagnol, J. Wu, A. Pontes-Lopes, S.C. Stark, B.W. Nelson. 2023. Amazon forest spectral seasonality is consistent across sensor resolutions and driven by leaf demography. ISPRS J. Photogramm. Remote Sens., 196: 93-104. 10.1016/j.isprsjprs.2022.12.001 [Gonçalves et al., 2023]

27. J.K. Green, J. Berry, P. Ciais, Y. Zhang, P. Gentine. 2020. Amazon rainforest photosynthesis increases in response to atmospheric dryness. Sci. Adv., 6: eabb7232. 10.1126/sciadv.abb7232 [Green et al., 2020]

28. K. Guan, M. Pan, H. Li, A. Wolf, J. Wu, D. Medvigy, K.K. Caylor, J. Sheffield, E.F. Wood, Y. Malhi, M. Liang, J.S. Kimball, S.R. Saleska, J. Berry, J. Joiner, A.I. Lyapustin. 2015. Photosynthetic seasonality of global tropical forests constrained by hydroclimate. Nat. Geosci., 8: 284-289. 10.1038/ngeo2382 [Guan et al., 2015]

29. Y. Guan, J. Liu, P. Chen, Y. Wang, D. Liang, Y. Xue, H. Chen, Z. Liu, P. Pellikka. 2023. Synergistic impact of complex topography and climate variability on the loss of microclimate heterogeneity in Southeast Asia. Geophys. Res. Lett., 50. 10.1029/2023gl104965. e2023GL104965 [Guan et al., 2023]

30. H. Hashimoto, W. Wang, J.L. Dungan, S. Li, A.R. Michaelis, H. Takenaka, A. Higuchi, R.B. Myneni, R.R. Nemani. 2021. New generation geostationary satellite observations support seasonality in greenness of the Amazon evergreen forests. Nat. Commun., 12: 684. 10.1038/s41467-021-20994-y [Hashimoto et al., 2021]

31. T. Hilker, A.I. Lyapustin, F.G. Hall, R. Myneni, Y. Knyazikhin, Y. Wang, C.J. Tucker, P.J. Sellers. 2015. On the measurability of change in Amazon vegetation from MODIS. Remote Sens. Environ., 166: 233-242. 10.1016/j.rse.2015.05.020 [Hilker et al., 2015]

32. A. Huete, K. Didan, T. Miura, E.P. Rodriguez, X. Gao, L.G. Ferreira. 2002. Overview of the radiometric and biophysical performance of the MODIS vegetation indices. Remote Sens. Environ., 83: 195-213. 10.1016/s0034-4257(02)00096-2 [Huete et al., 2002]

33. A.R. Huete, K. Didan, Y.E. Shimabukuro, P. Ratana, S.R. Saleska, L.R. Hutyra, W. Yang, R.R. Nemani, R. Myneni. 2006. Amazon rainforests green-up with sunlight in dry season. Geophys. Res. Lett., 33. 10.1029/2005gl025583. 2005GL025583 [Huete et al., 2006]

34. A.R. Huete, N. Restrepo-Coupe, P. Ratana, K. Didan, S.R. Saleska, K. Ichii, S. Panuthai, M. Gamo. 2008. Multiple site tower flux and remote sensing comparisons of tropical forest dynamics in Monsoon Asia. Agric. For. Meteorol., 148: 748-760. 10.1016/j.agrformet.2008.01.012 [Huete et al., 2008]

35. T. Janssen, Y. Van Der Velde, F. Hofhansl, S. Luyssaert, K. Naudts, B. Driessen, K. Fleischer, H. Dolman. 2021. Drought effects on leaf fall, leaf flushing and stem growth in the Amazon forest: reconciling remote sensing data and field observations. Biogeosciences, 18: 4445-4472. 10.5194/bg-18-4445-2021 [Janssen et al., 2021]

36. Y. Jiang, Y. Liang, C. Li, F. Wang, Y. Sui, N. Suvannang, J. Zhou, B. Sun. 2016. Crop rotations alter bacterial and fungal diversity in paddy soils across East Asia. Soil Biol. Biochem., 95: 250-261. 10.1016/j.soilbio.2016.01.007 [Jiang et al., 2016]

37. Y. Jiang, L. Zhou, C.J. Tucker, A. Raghavendra, W. Hua, Y.Y. Liu, J. Joiner. 2019. Widespread increase of boreal summer dry season length over the Congo rainforest. Nat. Clim. Chang., 9: 617-622. 10.1038/s41558-019-0512-y [Jiang et al., 2019]

38. S.A. Kannenberg, W.R.L. Anderegg, M.L. Barnes, M.P. Dannenberg, A.K. Knapp. 2024. Dominant role of soil moisture in mediating carbon and water fluxes in dryland ecosystems. Nat. Geosci., 17: 38-43. 10.1038/s41561-023-01351-8 [Kannenberg et al., 2024]

39. R.D. Lasco, C.M.D. Habito, R.J.P. Delfino, F.B. Pulhin, R.N. Concepcion. 2011. Climate Change Adaptation for Smallholder Farmers in Southeast Asia. World Agroforestry Centre, Los Baños Philippines [Lasco et al., 2011]

40. Z. Li, T. Huffman, B. McConkey, L. Townley-Smith. 2013. Monitoring and modeling spatial and temporal patterns of grassland dynamics using time-series MODIS NDVI with climate and stocking data. Remote Sens. Environ., 138: 232-244. 10.1016/j.rse.2013.07.020 [Li et al., 2013]

41. W. Li, N. MacBean, P. Ciais, P. Defourny, C. Lamarche, S. Bontemps, R.A. Houghton, S. Peng. 2018. Gross and net land cover changes in the main plant functional types derived from the annual ESA CCI land cover maps (1992–2015). Earth Syst. Sci. Data, 10: 219-234. 10.5194/essd-10-219-2018 [Li et al., 2018]

42. B. Liebmann, I. Bladé, G.N. Kiladis, L.M.V. Carvalho, B. Senay, D. Allured, S. Leroux, C. Funk. 2012. Seasonality of African precipitation from 1996 to 2009. J. Clim., 25: 4304-4322. 10.1175/jcli-d-11-00157.1 [Liebmann et al., 2012]

43. A.P. Lopes, B.W. Nelson, J. Wu, P.M.L.D.A. Graça, J.V. Tavares, N. Prohaska, G.A. Martins, S.R. Saleska. 2016. Leaf flush drives dry season green-up of the Central Amazon. Remote Sens. Environ., 182: 90-98. 10.1016/j.rse.2016.05.009 [Lopes et al., 2016]

44. A. Lyapustin, Y. Wang, I. Laszlo, R. Kahn, S. Korkin, L. Remer, R. Levy, J.S. Reid. 2011. Multiangle implementation of atmospheric correction (MAIAC): 2. Aerosol algorithm. J. Geophys. Res., 116: D03211. 10.1029/2010jd014986 [Lyapustin et al., 2011]

45. Y. Malhi. 2012. The productivity, metabolism and carbon cycle of tropical forest vegetation. J. Ecol., 100: 65-75. 10.1111/j.1365-2745.2011.01916.x [Malhi, 2012]

46. M. Moon, X. Zhang, G.M. Henebry, L. Liu, J.M. Gray, E.K. Melaas, M.A. Friedl. 2019. Long-term continuity in land surface phenology measurements: a comparative assessment of the MODIS land cover dynamics and VIIRS land surface phenology products. Remote Sens. Environ., 226: 74-92. 10.1016/j.rse.2019.03.034 [Moon et al., 2019]

47. D.C. Morton, J. Nagol, C.C. Carabajal, J. Rosette, M. Palace, B.D. Cook, E.F. Vermote, D.J. Harding, P.R.J. North. 2014. Amazon forests maintain consistent canopy structure and greenness during the dry season. Nature, 506: 221-224. 10.1038/nature13006 [Morton et al., 2014]

48. M. Nazeer, C.O. Ilori, M. Bilal, J.E. Nichol, W. Wu, Z. Qiu, B.K. Gayene. 2021. Evaluation of atmospheric correction methods for low to high resolutions satellite remote sensing data. Atmos. Res., 249: 105308. 10.1016/j.atmosres.2020.105308 [Nazeer et al., 2021]

49. Ş. Procheş, S. Ramdhani, A.C. Hughes, L.P. Koh. 2021. Southeast Asia as one of world’s primary sources of biotic recolonization following Anthropocene extinctions. Front. Ecol. Evol., 9: 634711. 10.3389/fevo.2021.634711 [Procheş et al., 2021]

50. S.R. Saleska, J. Wu, K. Guan, A.C. Araujo, A. Huete, A.D. Nobre, N. Restrepo-Coupe. 2016. Dry-season greening of Amazon forests. Nature, 531: E4-E5. 10.1038/nature16457 [Saleska et al., 2016]

51. T.W. Satriawan, X. Luo, J. Tian, K. Ichii, L. Juneng, M. Kondo. 2024. Strong Green-up of tropical Asia during the 2015/16 El Niño. Geophys. Res. Lett., 51. 10.1029/2023gl106955. e2023GL106955 [Satriawan et al., 2024]

52. N.-H. Seong, D. Jung, J. Kim, K.-S. Han. 2020. Evaluation of NDVI estimation considering atmospheric and BRDF correction through Himawari-8/AHI. Asia-Pac. J. Atmos. Sci., 56: 265-274. 10.1007/s13143-019-00167-0 [Seong et al., 2020]

53. L. She, H. Zhang, W. Wang, Y. Wang, Y. Shi. 2019. Evaluation of the Multi-Angle Implementation of Atmospheric Correction (MAIAC) aerosol algorithm for Himawari-8 data. Remote Sens., 11: 2771. 10.3390/rs11232771 [She et al., 2019]

54. T. Suepa, J. Qi, S. Lawawirojwong, J.P. Messina. 2016. Understanding spatio-temporal variation of vegetation phenology and rainfall seasonality in the monsoon Southeast Asia. Environ. Res., 147: 621-629. 10.1016/j.envres.2016.02.005 [Suepa et al., 2016]

55. A. Suprihatin, B.H. Purwanto, E. Hanudin, M. Nurudin. 2021. Effect of cropping rotation patterns on rice productivity in irrigated rice fields. IOP Conf. Ser. Earth Environ. Sci., 752: 012002. 10.1088/1755-1315/752/1/012002 [Suprihatin et al., 2021]

56. J. Tian, X. Zhu, J. Chen, C. Wang, M. Shen, W. Yang, X. Tan, S. Xu, Z. Li. 2021. Improving the accuracy of spring phenology detection by optimally smoothing satellite vegetation index time series based on local cloud frequency. ISPRS J. Photogramm. Remote Sens., 180: 29-44. 10.1016/j.isprsjprs.2021.08.003 [Tian et al., 2021]

57. J. Tian, X. Luo, H. Xu, J.K. Green, H. Tang, J. Wu, S. Piao. 2024. Slower changes in vegetation phenology than precipitation seasonality in the dry tropics. Glob. Chang. Biol., 30: e17134. 10.1111/gcb.17134 [Tian et al., 2024]

58. K.P. Vadrevu, T. Ohara. 2020. Focus on land use cover changes and environmental impacts in South/Southeast Asia. Environ. Res. Lett., 15: 100201. 10.1088/1748-9326/abb5cb [Vadrevu and Ohara, 2020]

59. G. Vico, S.E. Thompson, S. Manzoni, A. Molini, J.D. Albertson, J.S. Almeida-Cortez, P.A. Fay, X. Feng, A.J. Guswa, H. Liu, T.G. Wilson, A. Porporato. 2015. Climatic, ecophysiological, and phenological controls on plant ecohydrological strategies in seasonally dry ecosystems. Ecohydrology, 8: 660-681. 10.1002/eco.1533 [Vico et al., 2015]

60. X. Wang, P. Ciais, Y. Wang, D. Zhu. 2018. Divergent response of seasonally dry tropical vegetation to climatic variations in dry and wet seasons. Glob. Chang. Biol., 24: 4709-4717. 10.1111/gcb.14335 [Wang et al., 2018]

61. W. Wang, S. Li, H. Hashimoto, H. Takenaka, A. Higuchi, S. Kalluri, R. Nemani. 2020. An introduction to the geostationary-NASA earth exchange (GeoNEX) products: 1. Top-of-atmosphere reflectance and brightness temperature. Remote Sens., 12: 1267. 10.3390/rs12081267 [Wang et al., 2020a]

62. J. Wang, D. Yang, M. Detto, B.W. Nelson, M. Chen, K. Guan, S. Wu, Z. Yan, J. Wu. 2020. Multi-scale integration of satellite remote sensing improves characterization of dry-season green-up in an Amazon tropical evergreen forest. Remote Sens. Environ., 246: 111865. 10.1016/j.rse.2020.111865 [Wang et al., 2020b]

63. J.L. Weiss, J.L. Betancourt, J.T. Overpeck. 2012. Climatic limits on foliar growth during major droughts in the southwestern USA. J. Geophys. Res. Biogeosciences, 117. 10.1029/2012jg001993. 2012JG001993 [Weiss et al., 2012]

64. A.M. Wilson, W. Jetz. 2016. Remotely sensed high-resolution global cloud dynamics for predicting ecosystem and biodiversity distributions. PLoS Biol., 14: e1002415. 10.1371/journal.pbio.1002415 [Wilson and Jetz, 2016]

65. J. Wu, L.P. Albert, A.P. Lopes, N. Restrepo-Coupe, M. Hayek, K.T. Wiedemann, K. Guan, S.C. Stark, B. Christoffersen, N. Prohaska, J.V. Tavares, S. Marostica, H. Kobayashi, M.L. Ferreira, K.S. Campos, R. Da Silva, P.M. Brando, D.G. Dye, T.E. Huxman, A.R. Huete, B.W. Nelson, S.R. Saleska. 2016. Leaf development and demography explain photosynthetic seasonality in Amazon evergreen forests. Science, 351: 972-976. 10.1126/science.aad5068 [Wu et al., 2016]

66. H. Xu, X. Lian, I. Slette, H. Yang, Y. Zhang, A. Chen, S. Piao. 2021. Rising ecosystem water demand exacerbates the lengthening of tropical dry seasons. 10.21203/rs.3.rs-218770/v1. (preprint). In Review [Xu et al., 2021]

67. H. Xu, X. Lian, I.J. Slette, H. Yang, Y. Zhang, A. Chen, S. Piao. 2022. Rising ecosystem water demand exacerbates the lengthening of tropical dry seasons. Nat. Commun., 13: 4093. 10.1038/s41467-022-31826-y [Xu et al., 2022]

68. D. Yan, X. Zhang, Y. Yu, W. Guo. 2016. A comparison of tropical rainforest phenology retrieved from geostationary (SEVIRI) and polar-orbiting (MODIS) sensors across the Congo Basin. IEEE Trans. Geosci. Remote Sens., 54: 4867-4881. 10.1109/tgrs.2016.2552462 [Yan et al., 2016]

69. Y. Yang, P. Xiao, X. Feng, H. Li. 2017. Accuracy assessment of seven global land cover datasets over China. ISPRS J. Photogramm. Remote Sens., 125: 156-173. 10.1016/j.isprsjprs.2017.01.016 [Yang et al., 2017]

70. L.-Y. Yang, R. Yu, J. Wu, Y. Zhang, Y. Kosugi, N. Restrepo-Coupe, A. Huete, J. Zhang, Y.-H. Liu, X. Zhang, W.-J. Liu, J.-F. Zhao, J. Zeng, Q.-H. Song, Y.-J. Chen, L. Song, Z.-H. Tan. 2023. Asian tropical forests assimilating carbon under dry conditions: water stress or light benefits?. J. Plant Ecol., 16: rtac106. 10.1093/jpe/rtac106 [Yang et al., 2023]

71. F. Yu, X. Wu. 2016. Radiometric inter-calibration between Himawari-8 AHI and S-NPP VIIRS for the solar reflective bands. Remote Sens., 8: 165. 10.3390/rs8030165 [Yu and Wu, 2016]

72. W. Yuan, Y. Zheng, S. Piao, P. Ciais, D. Lombardozzi, Y. Wang, Y. Ryu, G. Chen, W. Dong, Z. Hu, A.K. Jain, C. Jiang, E. Kato, S. Li, S. Lienert, S. Liu, J.E.M.S. Nabel, Z. Qin, T. Quine, S. Sitch, W.K. Smith, F. Wang, C. Wu, Z. Xiao, S. Yang. 2019. Increased atmospheric vapor pressure deficit reduces global vegetation growth. Sci. Adv., 5: eaax1396. 10.1126/sciadv.aax1396 [Yuan et al., 2019]

73. Y. Zeng, D. Hao, A. Huete, B. Dechant, J. Berry, J.M. Chen, J. Joiner, C. Frankenberg, B. Bond-Lamberty, Y. Ryu, J. Xiao, G.R. Asrar, M. Chen. 2022. Optical vegetation indices for monitoring terrestrial ecosystems globally. Nat. Rev. Earth Environ., 3: 477-493. 10.1038/s43017-022-00298-5 [Zeng et al., 2022]

74. Y. Zeng, D. Hao, T. Park, P. Zhu, A. Huete, R. Myneni, Y. Knyazikhin, J. Qi, R.R. Nemani, F. Li, J. Huang, Y. Gao, B. Li, F. Ji, P. Köhler, C. Frankenberg, J.A. Berry, M. Chen. 2023. Structural complexity biases vegetation greenness measures. Nat. Ecol. Evol., 7: 1790-1798. 10.1038/s41559-023-02187-6 [Zeng et al., 2023]

75. Y. Zhang, Z. Zhu, Z. Liu, Z. Zeng, P. Ciais, M. Huang, Y. Liu, S. Piao. 2016. Seasonal and interannual changes in vegetation activity of tropical forests in Southeast Asia. Agric. For. Meteorol., 224: 1-10. 10.1016/j.agrformet.2016.04.009 [Zhang et al., 2016]

76. D. Zhang, X. Jiao, Q. Du, X. Song, J. Li. 2018. Reducing the excessive evaporative demand improved photosynthesis capacity at low costs of irrigation via regulating water driving force and moderating plant water stress of two tomato cultivars. Agric. Water Manag., 199: 22-33. 10.1016/j.agwat.2017.11.014 [Zhang et al., 2018]

77. W. Zhang, Y. Li, X. Wu, Y. Chen, A. Chen, C.R. Schwalm, J.S. Kimball. 2021. Divergent response of vegetation growth to soil water availability in dry and wet periods over Central Asia. J. Geophys. Res. Biogeosci., 126. 10.1029/2020jg005912. e2020JG005912 [Zhang et al., 2021]

78. X. Zhang, Y. Shen, S. Gao, W. Wang, C. Schaaf. 2022. Diverse responses of multiple satellite-derived vegetation Greenup onsets to dry periods in the Amazon. Geophys. Res. Lett., 49. 10.1029/2022gl098662. e2022GL098662 [Zhang et al., 2022]

79. Z. Zhu, S. Piao, R.B. Myneni, M. Huang, Z. Zeng, J.G. Canadell, P. Ciais, S. Sitch, P. Friedlingstein, A. Arneth, C. Cao, L. Cheng, E. Kato, C. Koven, Y. Li, X. Lian, Y. Liu, R. Liu, J. Mao, Y. Pan, S. Peng, J. Peñuelas, B. Poulter, T.A.M. Pugh, B.D. Stocker, N. Viovy, X. Wang, Y. Wang, Z. Xiao, H. Yang, S. Zaehle, N. Zeng. 2016. Greening of the earth and its drivers. Nat. Clim. Chang., 6: 791-795. 10.1038/nclimate3004 [Zhu et al., 2016]
