---
title: "Sentinel-1 for offshore wind energy application"
authors: "C.B. Hasager, K. Dimitriadou"
doi: "10.1016/j.rse.2026.115369"
source: "elsevier_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 29459
---

# Sentinel-1 for offshore wind energy application

## Abstract

This review presents Sentinel-1 (S-1) SAR wind products that are being used in the offshore wind energy sector, motivated by the unique properties of SAR mapping ocean winds with high spatial detail. High spatial detail is significant as offshore wind farms operate in coastal zones with high spatial wind variability. The SAR products reviewed include wind speeds at 10 m height, wind farm wakes, wind resources, and the identification of wind turbine locations. Main findings from the literature indicate that the thoroughly tested scatterometer-based geophysical model functions (GMFs) for SAR wind speed, compared to buoys, have an RMSE of approximately 1.5 m/s and a bias of around ±0.5 m/s. CMOD5.N shows better statistics compared to other scatterometer-based GMFs and is applied in near-real-time SAR-based ocean wind mapping by Copernicus and DTU Wind. One recent SAR-calibrated model, called OPEN, outperforms CMOD5.N; however, OPEN has not been tested by other researchers. The literature review on SAR for wind energy applications reveals that SAR can detect wind farms and cluster wakes extending over 100 km. SAR winds contain greater spatial detail than mesoscale models. For offshore wind resource assessment based on SAR, the reviewed literature indicates that the required extrapolation of winds from 10 m to hub height using stability information from mesoscale models is accurate within a few percent. The limitations due to coverage and revisit times of S-1 are negligible according to the reviewed literature for wind energy applications in the studied regions; however, these limitations are unknown in other regions. The lack of common databases on offshore wind turbine locations, combined with the rapid growth in numbers, has prompted interest in using S-1 data hard-target identification methods. A standardized global coverage turbine location database has been achieved based on S-1. A key challenge and limitation of assessing wind resource performance based on S-1 is the limited number of comparison results for hub-height wind resource data. It is recommended to conduct systematic comparisons of wind resource assessment and wind farm wake to enhance trust, benefit, and future use of S-1 data within the offshore wind energy sector in the years ahead.

## Introduction

The paper is a review of Sentinel-1 SAR wind products in the context of offshore wind energy.

The Sentinel-1 (S-1) series monitors the environment as part of the EU Copernicus initiative to detect environmental parameters for multiple purposes. The European Space Agency (ESA) built S-1 and operates S-1. S-1A was launched in April 2014 and continues to observe the Earth. S-1B observed from April 2016 to December 2021, when a spacecraft anomaly created a data transmission loss. S-1C was launched in December 2024 (Copernicus, 2025).

In ascending and descending orbits, Europe and its surrounding seas are routinely observed in Interferometric Wide Swath (IW) co-polarization, vertical receive and vertical transmit (VV), and cross-polarization (VH) modes. Other continents and their coastal zones are also observed in IW mode, but less frequently. To detect sea ice, S-1 routinely monitors polar regions in Extra Wide swath (EW) co-polarization horizontal receive and horizontal transmit (HH) and cross-polarization (HV). S-1 operates in four modes (CDSE, 2025). The mode of primary interest for offshore wind energy applications is the IW, with a swath of 250 km and spatial resolution of 5 m by 20 m. Alternatively, EW with a 400 km swath and spatial resolution of 25 m by 200 m is useful.

Heritage missions include C-band SAR sensors on board the ESA missions ERS-1 and ERS-2, launched in 1991 and 1995, respectively, and Envisat, launched in 2002.

Other constellations with C-band include the Canadian satellite RADARSAT-1 (R-1), launched in late 1995; RADARSAT-2 (R-2), launched in 2007; and the RADARSAT Constellation Mission, which consists of three satellites launched in 2019. RADARSAT missions primarily record in HH for sea ice mapping.

The C-band VV is well-suited for providing ocean surface wind observations using the scatterometer-based Geophysical Model Function (GMF) for wind retrieval (Quilfen et al., 1998; Hersbach, 2010; Stoffelen et al., 2017). Ocean surface wind speed can be retrieved from HH data (Vachon and Dobson, 2000; Monaldo et al., 2001; Mouche et al., 2017). The ESA Sentinel SAR data are freely accessible, while RADARSAT is a commercial product, limiting their use beyond research studies. The accuracy of SAR-derived wind speeds is an overarching issue.

Satellite SAR is one of the data sources for offshore wind engineering. Since the early days of SAR application for wind energy, researchers have observed bright pixels in SAR images caused by high backscatter from wind turbines. In low winds, the turbines stand out very brightly against the dark surface with low backscatter. Thirty-five regional, national, or international databases listed the geographical position of wind turbines in 2019. However, there were inconsistencies, missing data in the databases, and a requirement for payment to access certain information (Zhang et al., 2021). A unified, complete picture of all offshore wind turbine locations globally was unavailable and can be produced from SAR (Zhang et al., 2021; Hoeser et al., 2022).

Satellite SAR has the advantage of covering large areas. In 2005, the first-ever evidence of long wind farm wakes was captured by SAR (Christiansen and Hasager, 2005). The assumption at the time that wind farm wakes would ‘dissolve’ at less than 10 km distance was proved wrong by analysis of SAR images from ERS-2 and Envisat showing wind farm wakes longer than 20 km. S-1 has enabled wind farm wake studies, with examples of cluster wakes extending over 100 km (Djath and Schulz-Stellenfleth, 2019).

SAR-based wind resource maps have been obtained from SAR since the early days of SAR, e.g., (Furevik and Espedal, 2002; Choisnard et al., 2004; Hasager et al., 2006), based on a limited number of samples. Since S-1 came into orbit, a significantly larger number of samples have paved the way for comprehensive offshore wind resource mapping, as demonstrated by studies such as those by Hasager et al. (2020), de Montera et al. (2022), and Cathelain et al. (2023).

For offshore wind energy planning, information about winds at sea is critically important. The winds are the foundation for the generation of electricity and income. The atmospheric flow in coastal areas differs between locations relevant to offshore wind energy (Veers et al., 2022). Satellite SAR provides wind speed observation over extensive coastal spatial areas relevant to the needs of wind engineering. Observations in the marine environment are necessary to validate numerical model results of the marine atmosphere, ranging from the microscale to the mesoscale (Shaw et al., 2022).

In the offshore environment, observations are costly and sparse. Buoy data are observed at low heights compared to wind turbine heights. Meteorological masts equipped with wind sensors are no longer a standard feature. It is a technical challenge to install masts that are tall enough. Floating platforms with installed wind profiling lidars have become the standard for measuring winds at altitudes ranging from 100 m to 200 m above sea level (Gottschall et al., 2017). Proprietary observations from floating lidar are often collected for one or two years by wind farm developers. In contrast, policy planning typically relies on numerical models of wind conditions, such as the United Nations Environment Programme-funded Global Wind Atlas, freely available at https://globalwindatlas.info (Davis et al., 2023).

Offshore wind energy has become a crucial component of the green transition, helping to reduce CO<sub>2</sub> emissions. There were over 2000 offshore wind farms in 53 countries at the end of 2023 (4C Offshore, 2025). The installed offshore wind capacity globally at the end of 2023 was 75 GW, distributed among 38 GW in China, 34 GW in Europe, and the remaining turbines in the Asia-Pacific and the US. Most are bottom-fixed turbines, while the capacity of floating turbines is 0.25 GW (GWEC, 2024). The locations of offshore wind farms globally, in operation, under construction, consented, and in early planning, can be viewed in (4C Offshore, 2025).

The offshore wind capacity is expected to reach 83 GW by 2025. Twelve times more offshore wind capacity is expected in 2050, totaling 1000 GW (IEA World Energy Outlook, 2024). Wind-generated electricity production in 2050 is expected to reach 28%, with approximately 5000 GW of onshore and 1000 GW of offshore wind capacity (DNV, 2024; IRENA World Energy Transition Outlook, 2024). By the end of 2025, wind-generated electricity is expected to cover 12% of the global market (WWEA, 2025).

Satellite SAR contributes valuable information for three specific topics in offshore wind energy. The geolocation identification of offshore wind turbines, the offshore wind farm wakes, and the offshore wind resource. Fig. 1 shows a sketch of SAR-based information for offshore wind farms.

![Figure 1](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr1_lrg.jpg?httpAccept=%2A%2F%2A)

SAR measurement contributions to offshore wind energy topics, including ocean winds for wind resource assessment and wind farm wake assessment, and the geographical location of wind turbine positions from high backscatter values. Please note that the graphic is not to scale.

The review paper is structured into sections, with background and methodologies for ocean surface wind retrieval from SAR in Section 2, wind farm wake in Section 3, wind resources in Section 4, and mapping turbine locations in Section 5. The results, based on SAR, cover wind retrievals in Section 6, mapping of turbine locations in Section 7, wind farm wake in Section 8, and wind resources in Section 9. Section 10 concludes the review.

## Background and methodologies on ocean surface wind speed retrieval from SAR

### The physical principle

The roughness of the sea consists of capillary waves riding on much longer waves; usually, the shorter waves are in balance with the near-instantaneous ocean surface wind field. The interaction of radar signals with the rough ocean surface can be used for wind retrieval using GMFs.

### Geophysical model functions and polarization ratio

GMFs include scatterometer-based, SAR-calibrated, and theoretical models.

Scatterometer-based GMFs established for scatterometers with C-band VV configuration identify the relationship of the Normalized Radar Cross Section (NRCS), *σ*<sub>*0*</sub>, to wind speed at 10 m, *u*<sub>*10*</sub>, as follows:

(1)

$$
\sigma_{0} = B_{0}\left({u_{10},\theta} \right)\left\lbrack {1 + B_{1}\left({u_{10},\theta} \right)\cos \varnothing + B_{2}\left({u_{10},\theta} \right)\cos \left({2\varnothing} \right)} \right\rbrack^{p}\hspace{0.25em}
$$

where *θ* is the incidence angle, *Φ* is the angle between the radar azimuth look direction and wind direction. *B<sub>0</sub>* describes the central dependence between wind speed and incidence angle.

*B<sub>1</sub>* and *B<sub>2</sub>* describe the dependence for upwind-downwind and upwind-crosswind effects, respectively. *p* is an adjustment factor. SAR wind speeds are retrieved at an average resolution of around 500 m to 1000 m, which appears sufficient to suppress speckle noise well (Yu et al., 2022). CMOD4 (Stoffelen and Anderson, 1997), CMOD5 (Hersbach et al., 2007), and CMOD7 (Stoffelen et al., 2017) provide stability-dependent wind speed, i.e., the wind speed observed with an anemometer. CMOD-IFR2 (Quilfen et al., 1998) and CMOD5.N (Hersbach, 2010) provide equivalent neutral wind speed, i.e., the wind speed corrected for the average stability effect. The difference globally is ∼0.2 m/s higher for equivalent neutral winds (Hersbach, 2010; Lu et al., 2018). CMOD7 can provide stress-equivalent wind using a correction for stability and air mass density (de Kloe et al., 2017).

SAR-calibrated GMFs based on collocated SAR NRCS and ASCAT wind measurements include C-SARMOD (Mouche and Chapron, 2015), C-SARMOD2 (Lu et al., 2018), and GMF OPEN, short for Ocean Projection and Extension neural Network (OPEN) (Yu et al., 2022).

Theoretical GMFs based on theoretical models are SSA + H-E and SSA + H-M (Radkani and Zakeri, 2020).

Wind speed derived from HH-polarized data requires the application of a polarization ratio (e.g., Thompson et al., 1998; Mouche et al., 2017) or the use of a GMF tuned to HH, such as CMODH (e.g., Lu et al., 2018; Zhang et al., 2019). Wind speeds retrieved from HH data typically have lower accuracy than those from VV data, according to the studies. VV polarization is preferred due to a higher signal-to-noise ratio than HH polarization.

### Wind direction sources

The wind direction is input into Eq. (1) in each average cell, ranging from 500 m to 1000 m. It may be derived from the SAR scene from the linear features of wind streaks in the spatial domain using a local gradient (Koch, 2004; Rana et al., 2016), in the spectral domain using the Fast Fourier Transform (FFT) (Gerling, 1986; Fetterer et al., 1998), or with deep learning (Zecchetto and Zanchetta, 2022). However, wind streaks are not found in all scenes (Radkani and Zakeri, 2020). Wind direction from other sources is typically derived from numerical model directions or, in the case of a very local area, from wind direction measurements from a meteorological mast or buoy.

### Operational systems

S-1 data are processed operationally by Copernicus to the Level-2 Ocean Wind Field (OWI) product in near-real time, available in (CDSE, 2025)). At DTU Wind and Energy Systems, the near-real-time SAR ocean wind archive includes S-1 and Envisat Level-2 products, available in (SATWINDS, 2025). DTU is using the SAR operational products system (SAROPS) (Monaldo et al., 2014; Monaldo et al., 2015). SAROPS was developed at the Applied Physics Laboratory (APL) at Johns Hopkins University (JHU) and the National Oceanic and Atmospheric Administration (NOAA) in the United States. The key info on near-real-time S-1 ocean wind data processing from the two platforms is listed in Table 1 .

Table 1

Near-real-time operational Sentinel-1 ocean surface wind processing.

| Provider       | Copernicus                                                 | DTU Wind and Energy Systems                                                                      |
| -------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Resolution (m) | 1000                                                       | 500                                                                                              |
| GMF            | CMOD5.N since July 2019 and before CMOD-IFR2               | CMOD5.N                                                                                          |
| Wind direction | European Centre for Medium-Range Weather Forecasts (ECMWF) | Global Forecasting System (GFS) since 2011, and before Climate Forecast System Reanalysis (CFSR) |
| Publications   | Mouche and Vincent, 2011                                   | Badger et al., 2022                                                                              |
| Access         | CDSE, 2025                                                 | SATWINDS, 2025                                                                                   |

There are alternatives to derive winds from SAR, e.g., supported by tools in ESA's Sentinel-Application Platform (SNAP, 2025).

### Methodologies to improve SAR-derived wind speeds beyond GMFs

Methodologies to improve SAR-derived wind speeds beyond the aforementioned GMFs include inter-calibration between several SAR sensors (Badger et al., 2019), post-processing with machine learning using buoy data and sensor geometry (de Montera et al., 2022), and calibration to ASCAT (Khan et al., 2023).

### Limitations

Bright targets, such as ships, oil rigs, and wind turbines, as well as sea ice and rain, can contaminate wind retrievals, requiring masking and correction methods.

## Background and methodologies on wind farm wake

### Physical background on wind farm wake

Wind turbines can produce energy during periods with wind speeds above the cut-in speed, typically in the range of 3 to 4 m/s at hub height. A wake will occur downwind of each turbine with reduced wind speed compared to the wind speed upwind of the turbine. Wake losses are pronounced for wind speeds ranging from 6 to 10 m/s, as all turbines operate with high thrust. Wake losses are less pronounced for wind speeds above the rated value, typically in the range of 10 to 12 m/s, as there is sufficient wind for all turbines.

Wind turbine wakes are spreading downwind. The wakes of individual turbines often merge and combine into a wind farm wake, i.e., merged from several turbines within the wind farm. Cluster wakes originate from merged wakes downwind of two or more wind farms. Atmospheric stability influences wake development, with unstable conditions exhibiting greater spreading and shorter wakes, while stable conditions favor less spreading and longer wakes.

In wind farm wake analysis, the metrics used to characterize wind farm wakes include the length and width of the wake and the velocity deficit. The length is typically measured in terms of rotor diameter (D). The velocity deficit (*VD*) is calculated from the reference wind speed (*u*<sub>*ref*</sub>) and the wind speed in the waked area (*u*<sub>*wake*</sub>) from:

(2)

$$
\mathit{VD} = \frac{u_{\mathit{ref}} - u_{\mathit{wake}}}{u_{\mathit{ref}}} \ast 100\%
$$

In wake modelling, the reference wind is often the wind speed at hub height upwind of the wind farm. The definition of wake is typically set at 95% recovery of the reference wind speed. For homogenous wind flow with negligible coastal wind speed gradients, the wind speed observed upstream of the wind farm is a suitable choice. There are two general wake modelling approaches: the engineering wake model and the complex flow model (Göçmen et al., 2016). The latter requires more computational time. Often, the flow is idealized, assuming there is no wind speed gradient across the wind farm but a constant flow.

### Measurement approaches on wind farm wake

Measurements of wakes can be performed at short distances, such as from one turbine to the next within a wind farm, typically at distances of 5D to 8D, using anemometers, nacelle-based wind lidar, or power data from individual turbines obtained from SCADA (Supervisory Control and Data Acquisition) systems. Observations of one wind farm's wake impact on neighboring wind farms are possible using SCADA data (Nygaard and Hansen, 2016). Alternative observations are dual-Doppler radar (Nygaard and Newcombe, 2018), scanning wind lidars (e.g., Schneemann et al., 2020), and airborne campaigns with atmospheric sensors on board (Cañadillas et al., 2020; Platis et al., 2020). The latter can also capture wind farm cluster effect, i.e., wind farm wakes merged from two or more wind farms.

### Methodology on SAR-based wind farm wake analysis

In contrast to wind farm wake studies using meteorological data, SAR-based methodologies often aim to eliminate the effect of coastal gradients. Several studies (Christiansen and Hasager, 2006; Li and Lehner, 2013; Ahsbahs et al., 2018; Djath et al., 2018; Djath and Schulz-Stellenfleth, 2019; Owda and Badger, 2022; Heiberg-Andersen et al., 2022) have shown coastal wind speed gradients. Owda et al. (2022) found that even wind farms located very far from land had coastal wind speed gradients. Coastal wind speed gradients prevail and differ for onshore and offshore flow (Fig. 2 ).

![Figure 2](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr2_lrg.jpg?httpAccept=%2A%2F%2A)

Coastal gradients and offshore wind farm wakes, indicating onshore and offshore winds and wind speed variation along the horizontal transect lines.

SAR-based wake analysis methods encompass four key concepts to mitigate the impact of coastal gradients: transects, automatic detection, average wind climatology, and the rotation method.

Transects parallel to the wind farm are an alternative to using the reference wind speed upwind of the wind farm (Christiansen and Hasager, 2005, 2006).

Automatic detection of wake is based on a filter that identifies the background wind field, defined as the wind speed in the wake area that would exist if the wind farm did not exist. A priori knowledge about wind direction near wind farms and the width of the wind farm is used to outline where wakes are expected. The background wind speed is used as the reference wind speed, while the wind speed in the wake is used to calculate the velocity deficit. The method provides maps of meandering wind farm wakes, including their width and length, and is particularly well-suited for mapping in stable conditions with long wind farm wakes (Djath and Schulz-Stellenfleth, 2019).

The average wind climatology method quantifies the *average wind farm wake* using SAR wind speed maps observed before the wind farm was constructed, assuming the reference wind speed equals the offshore wind speeds prior to wind farm construction. The SAR wind speed map difference observed before and after commissioning quantifies the wind farm wakes. The method requires sufficient samples before and after the wind farm is commissioned. The output is the average wind farm wake for each wind direction sector (Ahsbahs et al., 2018; Owda and Badger, 2022).

The rotation method was developed to increase the number of available samples for quantifying the *average wind farm wake*. The first step was to rotate the SAR wind field maps to align the wind farm wake directions for all wind direction sectors. The second step was to average the wind farm wakes. This method increased the number of samples from between 7 and 30 SAR wind speed maps in each of 12 directional bins to more than 100 and up to 800 SAR wind speed maps for all directions combined for the studied wind farms. The number of samples varies primarily as a function of the installation time of each wind farm, with the older wind farms observed by SAR for several more years than the newer wind farms (Hasager et al., 2015c).

An advantage of SAR-based wake studies, compared to SAR-based wind resource assessment (section 2.3), is that the relative wind speed differences within a scene are more important than absolute values. Bias can be ignored, assuming they are constant within a scene (Christiansen and Hasager, 2005).

## Background and methodologies on wind resources

### Physical background on wind resources

Wind resources are defined as the energy from wind, assessing the potential electricity production from wind turbines.

Wind speed (*u*) is the driver for instantaneous power production (*P*) from a wind turbine for air density (*ρ*), power coefficient (*C*<sub>*p*</sub>), and rotor swept area (*A*<sub>*R*</sub>):

(3)

$$
P = \frac{1}{2}\rho C_{p}A_{R}u^{3}.
$$

More power will be produced for a larger rotor. This fact supports the development of larger rotors. Larger rotors require taller turbines, which means higher hub heights. At higher heights, the wind speeds are higher, following the wind profile equation (Landberg, 2015) in the simple form

(4)

$$
u_{z} = \frac{u_{\ast}}{\kappa}\mathit{ln}\left(\frac{z}{z_{0}} \right)
$$

where *u*<sub>*z*</sub> is the wind speed at the height *z*, *u*<sub>*⁎*</sub> is the friction velocity, *κ* is the von Kármán constant, and *z*<sub>*0*</sub> is the roughness length. For non-neutral conditions, a stability correction term is added.

Wind resource assessment was initially done using a time series of observations from a meteorological mast (Troen and Petersen, 1989). Long-term correction is necessary for wind resource assessment based on 1 or 2 years of data, as winds vary between years (Landberg, 2015). An alternative to observations is the use of a time series from a numerical model for offshore wind resource assessment (Hahmann et al., 2015). For either method, using observations or numerical output, the wind speed distribution is fitted to the Weibull function, which provides the scale parameter *A* and the shape parameter *k*. The wind power density, *E* (W/m<sup>2</sup>), is calculated from

(5)

$$
E = \frac{1}{2}\hspace{0.25em}\rho A^{3}\mathrm{Γ}\left({1 + \frac{3}{k}} \right)
$$

and Γ is the gamma function.

### Background on SAR-based wind resource assessment

The idea of using SAR for wind resource assessment started in 1999 (Johannessen and Bjorgo, 2000). The first results were derived from ERS-1 and ERS-2 (Hasager et al., 2002; Furevik and Espedal, 2002). An inspiring user guide on high-resolution wind monitoring using R-1 SAR showcased various wind conditions and revealed numerous offshore and coastal flow phenomena (Beal et al., 2005).

Besides the accuracy of SAR-derived winds (Section 6), the first research question regarding the use of SAR for wind resource assessment was how many samples are needed to estimate the Weibull *A* and *k* parameters from sparse data (Eq. 5) (Barthelmie and Pryor, 2003; Pryor et al., 2004). The most extended offshore wind speed time series from a meteorological mast was from the Vindeby project. Based on these offshore observations, the analysis concluded the statistics listed in Table 2 . The samples should be independent, random in time, and accurate. The results are specific to the geographical location. The meteorological mast data from the early offshore wind farms, Vindeby, Horns Rev 1, Alpha Ventus, and three FINO masts provided benchmark data for SAR-based methods. Fig. A.1 indicates locations.

Table 2

Number of samples needed for ±10% uncertainty at a 90% confidence level (Barthelmie and Pryor, 2003). Std. Dev. is the standard deviation.

| Parameter   | Mean | Std. Dev. | Weibull *A* | Weibull *k* | Energy density |
| ----------- | ---- | --------- | ----------- | ----------- | -------------- |
| Samples (−) | 56   | 150       | 1744        | 71          | 1744           |

In the earliest studies, fewer than 30 scenes were available in each study on wind resources using ERS-1/2 (Furevik and Espedal, 2002) and R-1 (Choisnard et al., 2004; Beaucage et al., 2008). Gradually, access to more scenes paved the way for detailed studies on the wind resource in the North Sea near the Horns Rev 1 wind farm (Hasager et al., 2006).

Envisat ASAR data became freely available for research in the late years of the mission (March 2002 to April 2012). The open research access to the Envisat ASAR archive sparked interest in estimating offshore wind resources for areas of great interest for offshore wind energy planning, such as the Baltic Sea, Japan, China, Korea, the Great Lakes, Iceland, and the North Sea. See Table A.1 for details.

Since the launch of S-1, the number of SAR scenes has increased significantly, and their value for wind resource assessment has been investigated.

### Methodology for SAR-based wind resource assessment

SAR-based wind resource assessment is based on overlapping samples in each grid cell, where the Weibull parameters are fitted to the wind speed time series within each grid cell. Overlapping samples are from different satellite acquisitions and cover the same grid cell. SAR contributes spatial sampling at low temporal resolution, while meteorological masts provide point measurements at high temporal resolution. SAR winds are available at 10 m height, and extrapolation is required to estimate hub-height winds.

Methods to extrapolate wind speed from 10 m to hub heights include three methods: neutral logarithmic profile, stability corrected profile using Monin-Obukhov similarity theory, and stability corrected profile using AI.

The early method is the logarithmic scaling valid for near-neutral conditions (Eq. 4).

The stability correction using Monin-Obukhov Similarity Theory (MOST) can be based on local observations or mesoscale models (Peña and Hahmann, 2012). However, using the latter is not sufficiently accurate for individual SAR wind maps. Badger et al. (2016) developed a vertical extrapolation method based on mesoscale stability input and the average stability term for heights up to 100 m, combining SAR-based friction velocity maps calculated from equivalent neutral SAR wind speed maps, and the long-term average stability derived from the WRF model.

Recently, AI-based extrapolation methods for wind resource assessment using mesoscale stability input have been developed (Optis et al., 2021; de Montera et al., 2022). In contrast, the AI-based method by Hatfield et al. (2023) was based on long-term local observations at FINO3 offshore meteorological masts.

Like the stability correction by Badger et al. (2016), the method by de Montera et al. (2022) is based on WRF model stability parameters. Instead of using the MOST theory, the parameters of WRF surface net heat flux, wind speed ratio between two heights (40 m and 200 m), and air-sea temperature difference are used in machine learning training. The analysis is with 80% data used for training and 20% used for validation using wind lidar profile data.

SAR samples are independent as the scenes are observed on different days. SAR samples are not random due to satellite orbital parameters, which are observed at specific time intervals during ascending and descending nodes. A correction may be relevant for sites with pronounced diurnal wind speed variation, which is not unusual in coastal zones with land-sea breezes. With a limited number of samples, the seasonal variation in wind speed can impact the results.

Methods to adjust for seasonal effects were developed by Ahsbahs et al. (2020a). The number of available overlapping samples within the area of interest can vary temporally. When fewer or more overlapping samples occur for one month than for other months, corrections are applied to ensure the mean wind speed is balanced for this variation in available SAR wind speed maps, thereby arriving at a representative mean wind speed. More weight is given to the wind speed in the under-represented months compared to the well-represented months.

Methods to adjust for diurnal effects were developed by de Montera et al. (2022). A time series from external sources is used.

The wind class sampling method aimed to provide a commercially viable service for optimal wind resource assessment based on a few carefully selected SAR scenes, while also limiting the cost of SAR scenes (in 2006, € 400 per scene) (Badger et al., 2010). The idea was to first assess the wind statistics locally from a meteorological mast or a numerical model, also suggested by Choisnard et al. (2004) and Furevik and Espedal (2002). Next, representative SAR samples were selected for the dominant wind directions and wind speed levels. Using the entire archive of DTU Wind and Energy Systems (open for research) was preferable to wind class sampling (Badger et al., 2010).

## Background and methodologies on mapping turbine locations

With the massive construction of wind turbines in China and Europe since 2015, and a lack of a common database on their locations, researchers have investigated the possibility of using S-1 to detect and map offshore wind turbine locations. The methods used include automatic adaptive threshold, semantic segmentation, and deep learning.

An automatic adaptive threshold method based on the backscatter coefficient separates high-backscatter objects from backgrounds with low backscatter values. During the processing, floating and temporary mobile objects are removed. Next, a morphological filter is applied to fill in or omit small-scale issues to enhance the bright pixels at the wind farm locations. Finally, large stationary bright objects (e.g., oil platforms) are removed (Zhang et al., 2021).

A semantic segmentation method for identifying wind turbines can detect turbine positions (de Carvalho et al., 2023).

Deep learning methods detecting turbine locations are available (Ding et al., 2024; Hoeser et al., 2022).

Validation of SAR-based wind turbine detection methods has been performed using databases, optical satellite data, and visual inspection of S-1 data by the researchers.

## Validation results on ocean surface wind speed retrieval from SAR

### S-1 ocean surface wind speeds compared to other sources

The accuracy of ocean surface wind speeds derived from S-1 has been reported in 25 studies listed in Table 3 , which presents the statistical output from linear correlation statistics, including root mean square error (RMSE), bias, correlation coefficient (R), and the number of collocated samples (N). Table 3 indicates the publication source, the data from S-1 and location, and the sources of reference wind speed from buoy, meteorological mast, wind turbine, ASCAT, and scanning lidar. The GMF model and the wind direction sources from the model, streaks, buoys, and masts are also mentioned.

Table 3

Geophysical model function wind speed accuracy results at 10 m. RMSE is the root mean square error, R is the correlation coefficient, and N is the number of collocated samples.

| Publication                   | Sentinel-1 Location                                                          | Reference              | GMF model                                                                | Wind direction           | RMSE (m/s)                                           | Bias (m/s)                                                 | R                                    | N                                        |
| ----------------------------- | ---------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------ | ------------------------ | ---------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------ | ---------------------------------------- |
| Dimitriadou et al., 2025      | S-1 IW VV Gulf of Lion                                                       | Buoy1                  | CMOD5.N                                                                  | GFS<br>ERA5<br>NEWA      | 1.60<br>1.40<br>1.71                                 | n.a.                                                       | 0.96<br>0.97<br>0.95                 | 228                                      |
|                               |                                                                              | Buoy 2                 | CMOD5.N                                                                  | GFS<br>ERA5<br>NEWA      | 2.09<br>2.10<br>1.86                                 | n.a.                                                       | 0.90<br>0.90<br>0.92                 | 77                                       |
| Khachatrian et al., 2024      | S-1A OWI<br>Norwegian Arctic                                                 | Mast                   | CMOD5.N                                                                  | ECMWF                    | 2.00                                                 | n.a.                                                       | 0.88                                 | 238                                      |
| Khan et al., 2023             | S-1A IW VV<br>S-1B IW VV<br>Australia                                        | ASCAT                  | CMOD5.N                                                                  | ECMWF                    | 1.49<br>1.30                                         | −0.51<br>−0.58                                             | 0.94<br>0.94                         | 3975<br>738                              |
| Owda et al., 2023             | S-1A/B IW VV<br>US                                                           | Buoys1<br>Buoys2       | CMOD5.N                                                                  | GFS                      | 1.60<br>1.50                                         | −0.3<br>−0.5                                               | 0.8<br>0.9                           | 119<br>463                               |
| Badger et al., 2023           | S-1A/B<br>North Sea                                                          | Mast                   | CMOD5.N                                                                  | GFS                      | 1.83                                                 | −1.02                                                      | 0.91                                 | 848                                      |
| Cathalain et al. 2023         | S-1A/B<br>France                                                             | Buoy 1<br>Buoy 2       | CMOD7                                                                    | ECMWF                    | 1.10<br>1.02                                         | −0.65<br>−0.45                                             | 0.96<br>0.96                         | 99<br>104                                |
| de Montera et al., 2022       | S-1A/B<br>North Sea                                                          | Buoy                   | CMOD7<br>CMOD7 + ML                                                      | ECMWF                    | n.a.<br>n.a.                                         | −0.44<br>0.02                                              | n.a.<br>n.a.                         | 883                                      |
| Zecchetto and Zanchetta, 2022 | Venice Lagoon                                                                | Buoy<br>ECMWF          | CMOD-IFR2                                                                | ECMWF                    | n.a.                                                 | −1.0<br>0.3                                                | 0.81<br>0.81                         | 163<br>1188                              |
|                               |                                                                              | Buoy<br>ECMWF<br>ASCAT | C-SARMOD2                                                                | Streaks                  | n.a.                                                 | −1.5<br>0.1<br>−1.5                                        | 0.77<br>0.66<br>0.70                 | 235<br>2105<br>249                       |
| Yu et al., 2022               | S-1 IW VV<br>Gulf of Mexico                                                  | Buoys1                 | CMOD4<br>CMOD5.N<br>CMOD-IFR2<br>CMOD7<br>OPEN                           | Buoys1                   | 1.54<br>1.50<br>1.48<br>1.49<br>1.15                 | 0.59<br>0.45<br>−0.41<br>−0.32<br>0.02                     | 0.83<br>0.84<br>0.85<br>0.84<br>0.91 | 1069                                     |
|                               |                                                                              | ASCAT                  | CMOD4<br>CMOD5.N<br>CMOD-IFR2<br>CMOD7<br>OPEN                           | Buoys1                   | 1.57<br>1.54<br>1.55<br>1.55<br>1.33                 | −0.59<br>0.44<br>−0.41<br>−0.32<br>0.02                    | 0.82<br>0.83<br>0.83<br>0.83<br>0.88 | 1069                                     |
|                               | Fujian                                                                       | Buoys2                 | CMOD4<br>CMOD5.N<br>CMOD-IFR2<br>CMOD7<br>OPEN                           | Buoys2                   | 2.07<br>2.50<br>2.09<br>2.05<br>1.74                 | 0.85<br>1.52<br>0.57<br>0.76<br>0.20                       | 0.85<br>0.77<br>0.85<br>0.85<br>0.90 | 71                                       |
| Tuy et al., 2022              | S-1 OWI<br>Cambodia                                                          | WRF                    | CMOD-IFR2                                                                | ECMWF                    | 0.79                                                 | 0.70                                                       | n.a.                                 | 515                                      |
| Li et al., 2021               | S-1 OWI<br>Fujian                                                            | Buoy                   | CMOD-IFR2                                                                | ECMWF                    | 1.53                                                 | 1.17                                                       | 0.81                                 | 14                                       |
| Majidi Nezhad et al., 2021    | S-1 IW VV<br>Baltic Sea                                                      | Turbine 1<br>Turbine 2 | CMOD5                                                                    | ECMWF                    | 1.38<br>1.82                                         | 0.26<br>0.92                                               | n.a.                                 | 25                                       |
| Shiyan et al., 2020           | S-1A/B<br>US                                                                 | Buoy                   | CMOD5<br>CMOD7                                                           | Buoy                     | 1.35<br>1.38                                         | 0.12<br>−0.07                                              | 0.9<br>0.9                           | 682                                      |
| Radkani and Zakeri, 2020      | S-1 IW VV<br>Caspian Sea                                                     | Mast                   | CMOD7<br>C-SARMOD2<br>SSA2 + H-E<br>SS2 + H-M                            | Mast                     | 1.67<br>1.74<br>1.82<br>1.77                         | 0.67<br>−0.44<br>0.48<br>0.49                              | n.a.                                 | 11                                       |
|                               |                                                                              | Mast                   | CMOD7<br>C-SARMOD2<br>SSA2 + H-E<br>SS2 + H-M                            | ERA5                     | 2.14<br>2.53<br>2.28<br>2.11                         | 0.80<br>0.00<br>0.62<br>0.56                               | n.a.                                 | 11                                       |
|                               |                                                                              | Mast                   | CMOD7<br>C-SARMOD2<br>SSA2 + H-E<br>SS2 + H-M                            | Streaks                  | 1.68<br>2.17<br>2.01<br>1.94                         | 0.68<br>−0.3<br>0.30<br>0.31                               | n.a.                                 | 7                                        |
| Ahsbahs et al., 2020a         | S-1A<br>S-1A c.<br>S-1B<br>S-1A i.<br>S-1A c. i.<br>S-1B i.<br>US East Coast | Buoy                   | CMOD5.N                                                                  | GFS                      | 1.54<br>1.29<br>1.39<br>1.34<br>1.28<br>1.38         | 0.82<br>0.00<br>0.02<br>−0.20<br>−0.17<br>−0.04            | n.a.                                 | 140<br>1322<br>315<br>140<br>1322<br>315 |
| de Montera et al., 2020       | S-1A/B OWI<br>Ireland                                                        | Buoy                   | CMOD-IFR2                                                                | ECMWF                    | 1.41                                                 | −0.42                                                      | 0.93                                 | 801                                      |
| Badger et al., 2019           | S-1A<br>S-1B<br>North Sea and Ireland                                        | Buoy                   | CMOD5.N                                                                  | GFS                      | 1.57<br>1.58                                         | 0.10<br>0.17                                               | n.a.                                 | 1660<br>1100                             |
|                               | S-1A<br>S-1B                                                                 |                        |                                                                          | Buoy                     | 1.30<br>1.26                                         | 0.16<br>0.17                                               | n.a.                                 | 1660<br>1100                             |
| Jang et al., 2019             | S-1 IW VV<br>Korea                                                           | Buoy                   | CMOD4<br>CMOD5<br>CMOD5.N<br>CMOD5.Na<br>CMOD-IFR2                       | ECMWF                    | 1.83<br>1.69<br>1.68<br>1.65<br>1.82                 | −0.64<br>−0.38<br>0.31<br>0.14<br>−0.59                    | 0.88<br>0.89<br>0.89<br>0.89<br>0.89 | 807                                      |
| Rana et al., 2019             | S-1 IW VV<br>North Sea                                                       | Mast                   | CMOD5.N                                                                  | Mast<br>ECMWF<br>Streaks | 1.4<br>2.4<br>2.2                                    | n.a.                                                       | n.a.                                 | 933                                      |
| Lu et al., 2018               | S-1A and RS-2<br>US                                                          | Buoy                   | CMOD4<br>CMOD5<br>CMOD5.N<br>CMOD-IFR2<br>C-SARMOD<br>C-SARMOD2<br>CMOD7 | Buoy                     | 2.22<br>1.98<br>1.86<br>1.97<br>1.92<br>1.84<br>1.93 | −1.27<br>−0.66<br>0.03<br>−0.77<br>−0.74<br>−0.04<br>−0.59 | n.a.                                 | 1452                                     |
| Zhang et al., 2018            | S-1 IW VV<br>US                                                              | Buoy                   | CMOD5                                                                    | Buoy                     | 1.17                                                 | −0.28                                                      | 0.96                                 | 448                                      |
| La et al., 2017               | S-1 IW + SM<br>France                                                        | Mast                   | CMOD5.N                                                                  | Streaks                  | 1.59                                                 | 0.078                                                      | 0.92                                 | 195                                      |
| Ahsbahs et al., 2017          | S-1A<br>North Sea                                                            | Scanning lidar         | CMOD5.N                                                                  | Mast                     | 1.31                                                 | n.a.                                                       | 0.99                                 | 11                                       |
| James, 2017                   | S1 IW VV<br>IJmuiden                                                         | Mast                   | CMOD5                                                                    | MERRA2<br>Mast           | n.a.                                                 | n.a.                                                       | 0.93<br>0.96                         | 25                                       |
| Monaldo et al., 2016          | S-1A VV<br>S-1A HH<br>US                                                     | ASCAT                  | CMOD5.N                                                                  | GFS                      | n.a.                                                 | 0.16<br>−0.43                                              | 0.97<br>0.96                         | 37,127<br>272,488                        |

The Level 2 ocean wind product (OWI) has been compared in Ireland (de Montera et al., 2020), Fujian (Li et al., 2021), Venice Lagoon (Zecchetto and Zanchetta, 2022), Cambodia (Tuy et al., 2022), and the Norwegian Arctic (Khachatrian et al., 2024). The first four studies are based on CMOD-IFR2, while the fifth is based on CMOD5.N. The wind direction input is from ECMWF. In Ireland, the study period was from 2017 to 2019. The study sites included Venice Lagoon (2018), Cambodia (2018–2019), and Fujian (2018–2021). In Ireland, RMSE was 1.41 m/s using 801 collocated samples with ocean buoy wind speeds. In Cambodia, RMSE was 0.79 m/s using 515 collocated samples to Weather Research & Forecasting Model (WRF) model wind speeds, while in Fujian, RMSE was 1.53 m/s using 14 collocated buoy samples. In the Norwegian Arctic, RMSE was 2.00 m/s based on 238 collocated mast samples. The mast was installed at a platform, causing flow distortion. The study concluded that SAR could compete with reanalysis products such as ERA5, NORA3, and CARRA (Copernicus Arctic Regional Reanalysis) (Khachatrian et al., 2024). OWI wind speeds observed at lakes in Europe, compared to those at coastal masts, show less accurate results (R was 0.71) than those from the oceans (Katona and Bartsch, 2018). The study on wind speeds in European lakes falls outside the validity range of the ocean wind product, which may be the reason for the less accurate results.

Three comprehensive studies have compared CMOD-IFR2 and CMOD5.N, focusing on US waters (Lu et al., 2018), Korea (Jang et al., 2019), and the Gulf of Mexico (Yu et al., 2022). Furthermore, all three studies compared CMOD4 and CMOD5, while two studies compared CMOD7 and two compared SAR-based GMFs. The studies are based on around 800 to 1450 collocated samples from buoy wind speeds. The results from the Gulf of Mexico, Korea, and the US are, respectively, for CMOD-IFR2 RMSE 1.48 m/s, 1.82 m/s, and 1.97 m/s, and bias −0.41 m/s, −0.59 m/s, and − 0.77 m/s, and CMOD5.N, RMSE 1.50 m/s, 1.68 m/s, and 1.86 m/s, and bias 0.45 m/s, 0.31 m/s, and 0.03 m/s. Wind direction input is from buoys (Yu et al., 2022; Lu et al., 2018) and a model (Jang et al., 2019). It is noted that the statistics from CMOD5.N have slightly lower RMSE values and lower biases than those from CMOD-IFR2. CMOD7 is the newest GMF of the CMOD family. Only two studies present comparison results from CMOD7 versus CMOD-IFR2 and CMOD5.N (Yu et al., 2022; Lu et al., 2018), and the statistics do not indicate that CMOD7 is superior to the other two GMFs in these studies.

Of the 25 studies (in Table 3), 14 compared CMOD5.N, seven compared CMOD-IFR2, and five compared CMOD7. Using mast or buoy wind direction generally outperformed model wind direction accuracy in terms of derived wind speeds (Radkani and Zakeri, 2020; Badger et al., 2019; Rana et al., 2019; James, 2017). A recent study compared SAR-derived wind speeds using CMOD5.N with wind direction input of three different models (GFS, ERA5, and NEWA), assuming the higher-resolution model would improve the SAR-derived wind speeds. Based on collocated samples at two buoys (one with 228 samples, the other with 77 samples) in the Gulf of Lion, ERA5 outperformed the other two models in terms of accuracy in wind direction compared to the buoy wind directions. However, ERA5 wind directions at only one of the two buoys (with 228 samples) resulted in the best wind speed retrieval, with an RMSE of 1.40 m/s (Dimitriadou et al., 2025). The results based on wind streaks as the input wind direction are slightly better than those using wind direction from models (Radkani and Zakeri, 2020; Rana et al., 2019). La et al. (2017) compared S-1 IW + SM to coastal mast data using wind direction from wind streaks, employing a local gradient method and CMOD5.N, with results comparable to those of two other studies that used streaks as input.

Five alternative SAR-based GMFs have been tested. Lu et al. (2018) found that wind speeds derived from C-SARMOD-2 perform better than those from C-SARMOD, while Radkani and Zakeri (2020) tested two theoretical new GMFs (SSA2 + H-E and SS2 + H-M) with results comparable to C-SARMOD-2. Common to the four alternative GMFs, C-SARMOD, C-SARMOD2, SSA2 + H-E, and SS2 + H-M, is that they have an RMSE higher than CMOD7. Yu et al. (2022) tested GMF OPEN and reported an RMSE of 1.15 m/s and a bias of nearly zero m/s. OPEN outperforms all other GMFs. OPEN was developed using ASCAT and a neural network and was subsequently tested with buoy data.

The geographical distribution of S-1 SAR wind speed comparison studies on the accuracy of the derived wind speeds covers four continents with the number of studies in brackets: Europe including North Sea (7), Ireland (2), France (2), Norwegian Arctic (1), Baltic Sea (1), Venice Lagoon (1), Gulf of Lion (1), and Caspian Sea (1); North America including the US waters (6) and Gulf of Mexico (1); Asia including Fujian (2), Korea (1), and Cambodia (1); and Australia (1). The references for the studies are listed in Table 3. The geographical coverage of the SAR-based wind validation studies is summarized in Fig. 3 .

![Figure 3](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr3_lrg.jpg?httpAccept=%2A%2F%2A)

Geographical distribution of Sentinel-1 SAR wind speed validation studies across the globe. The points do not represent the extent of the study domain but the mean latitude and longitude of the domain.

SAR wind speed retrieval accuracy from missions prior to S-1 is not systematically assessed here. Two papers present comprehensive summaries of SAR-derived wind speed accuracy from earlier missions, with RMSE values below 1.9 m/s and R values above 0.80 (Majidi Nezhad et al., 2019). The results of RMSE are comparable to those of S-1, but R is lower than most S-1 results. Dagestad et al. (2012) cited 24 comparison studies showing biases less than 0.5 m/s. Many but not all S-1 studies show lower bias.

### Results on SAR wind for spatial scales

The investigation of S-1 SAR wind speed at different spatial scales, ranging from 5 m to 5000 m (Zhang et al., 2018), reveals that a 500 m resolution is sufficient to suppress speckle noise. Ahsbahs et al. (2017) compared horizontally scanning lidar wind speed transects from the coastline to a distance of 5 km, showing that SAR-derived winds were reliable as close as 1 km from the coast. The result is satisfying as the GMFs are developed for the open ocean and appear trustworthy in near-coastal seas.

Analysis of spatial scales using spectral analysis of SAR and scatterometer revealed that SAR resolves features at approximately 4 km, while scatterometer resolves features at approximately 20 km. Furthermore, it was found that WRF from the New European Wind Atlas (NEWA) has a 3 km grid resolution, and the spatial scales are resolved at around 20 km (Karagali et al., 2013). Analysis of spectral scales comparing SAR with regional forecast models SKIRON and ECMWF demonstrated the higher effective resolution of SAR (Rana et al., 2019). Spectral analysis of SAR and the German weather model (DWD) confirmed that SAR resolves finer spatial details (Djath and Schulz-Stellenfleth, 2019). According to Frehlich and Sharman (2008), the effective model resolution is expected to be six times lower than the grid cell size in numerical models. Coastal wind speed gradients and spatial wind speed variability are significantly better resolved in SAR than in models such as NEWA, SKIRON, ECMWF, and DWD.

Coastal wind speed gradients are remarkable along the US East Coast. The wind speed variability in the 25 lease areas along the US East Coast showed significantly more variability in SAR-derived maps than in the WRF model for most lease areas. The WRF model results appear to underestimate the spatial gradients in mean wind speed, while the SAR-based mean wind speed map provided fine spatial details (Ahsbahs et al., 2020a).

### Results on inter-calibration, post-processing, and calibration

The absolute radiometric accuracy for S-1 is 0.43 dB (Yu et al., 2022; Schwerdt et al., 2016). The corresponding uncertainty is around 0.6 m/s of wind speed. Therefore, there is potential for improvement beyond SAR-derived wind speeds from the aforementioned GMF results, which could be achieved through inter-calibration between SAR sensors, post-processing with machine learning, and calibration to ASCAT.

The inter-calibration method to limit deviations between sensors was demonstrated based on S-1 A IW VV 2403 scenes, S-1 EW HH 27 scenes, and S-1B IW VV 51 scenes, and combined with Envisat WSM VV 2198 scenes, Envisat WSM HH 513 scenes, and R-1 WD1 HH 924 scenes. The wind retrieval was done using CMOD5.N and wind direction from GFS. The results were compared to buoy data near the US East Coast, and inter-calibrated wind speed statistics showed an RMSE of around 1.30 m/s and a bias of near zero m/s. Extending the S-1 data with data from past missions, such as Envisat, provides an extended time series relevant to wind resource assessment (Badger et al., 2019).

Post-processing of SAR winds from CMOD7 for the Southern North Sea, based on a machine learning algorithm, was applied to an S-1 A/B IW VV data set and wind direction input from ECMWF to address issues related to sea state and sensor geometry. A total of 80% of collocated SAR-buoy data were used for the machine learning training, while the remaining 20% (883 collocated samples) were used for comparison. The SAR wind speed statistics were improved using the surface correction post-processing method, reducing the bias from −0.48 m/s to 0.02 m/s, the mean absolute error (MAE) from 0.85 m/s to 0.57 m/s, and the standard deviation (SD) from 0.95 m/s to 0.74 m/s (de Montera et al., 2022). De Montera et al. (2022) did not report RMSE. Later, (Cathelain et al., 2023) applied the same post-processing correction for an S-1 data set near France using CMOD7 and wind direction from ECMWF and found reductions: bias from −1.18 m/s to 0.65 m/s, MAE from 1.37 m/s to 0.87 m/s, and SD from 1.12 m/s to 0.89 m/s. The RMSE was 1.10 m/s for the post-processed data, based on 99 collocated samples of buoy wind speeds. Currently, work is ongoing on a novel AI-based GMF using Norwegian Reanalysis (NORA3) wind data as input and testing it against buoy data in an ESA-funded project (ESAWAII, 2025).

Calibration of SAR wind speeds based on a large amount of S-1 A/B IW VV data (occasionally HH) using CMOD5·N and wind direction from ECMWF using ASCAT for calibration was performed by Khan et al. (2023) for the seas near Australia. The calibrated time series is homogeneous, as it uses the same processing throughout. An independent comparison of the calibrated S-1 wind with the altimeter, using 476 collocated samples, shows improved statistics compared to the OWI product (Khan et al., 2023).

### Summary on S-1 SAR ocean wind speed retrieval accuracy

In summary, the accuracy of S-1 SAR wind speed retrieval has been evaluated worldwide. Comparison studies are done in different ways. Therefore, the results from the many studies may not be directly comparable, e.g., collocation time, data types, and averaging method differ. It is advisable to compare different GMFs using large numbers of well-collocated samples for intercomparison (e.g., Lu et al., 2018; Jang et al., 2019; Yu et al., 2022). Most studies rely on ocean buoy data or meteorological mast data, and a height correction to 10 m is needed. Comparison of SAR ocean wind speed to mesoscale model wind speed data is not a reliable validation in areas with coastal wind speed gradients because SAR ocean winds resolve finer spatial detail than the models.

Massive SAR wind processing uses model wind direction. CMOD5.N is used in the OWI and DTU Wind and Energy Systems near-real-time products. The readily available SAR wind speed maps are relevant for end-users such as wind energy engineers. The thoroughly tested CMOD5.N appears to perform statistically the best among the scatterometer-based GMFs. The recent SAR-based GMF OPEN outperforms all other GMFs but has not been tested by other researchers.

Post-processing methods for SAR wind speeds (beyond the choice of GMFs) enhance the accuracy of wind speed estimates. The post-processing includes various algorithms to inter-calibrate between SAR systems and to calibrate against the ocean buoys data network or ASCAT. Common to the post-processing is that these are empirical and site (or region) dependent, and currently lack broader verification. A limitation is that post-processing methods are not compared comprehensively, and the sharing of these methods is limited. A recommendation is to conduct a comprehensive comparison analysis of post-processing methods, enabling optimal best practices and ensuring heterogeneity in the comparison method and validation datasets.

## Results based on S-1 for mapping offshore wind turbine locations

### Examples of turbine locations based on S-1

In calm conditions, the high backscatter shows the location of wind turbines. An example from S-1, shown in Fig. 4 , illustrates the first, second, and third generation layouts of offshore wind farms at Horns Rev 1, Horns Rev 2, and Horns Rev 3, respectively. First-generation layout is arranged in rows and columns with short distances between turbines, second-generation layout is arranged in a curved layout with longer distances in some directions, and third-generation layout is arranged in a ‘random’ layout. The layout was modified to minimize wake loss and reduce cable costs. The number of turbines and their size changed from many smaller to fewer larger turbines, as shown in Table 4 .

![Figure 4](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr4_lrg.jpg?httpAccept=%2A%2F%2A)

Sentinel-1 wind field map from 15 March 2025 at 05:41 UTC covering the offshore wind farms Horns Rev 1, 2, and 3 in the Danish North Sea. Very low winds are coming from the east. The barbs showing wind direction and wind speed are from the GFS model.

Table 4

Information about the Horns Rev. wind farms.

| Wind farm                     | Horns Rev 1 | Horns Rev 2 | Horns Rev 3 |
| ----------------------------- | ----------- | ----------- | ----------- |
| Installation year             | 2002        | 2008        | 2018        |
| Generation of layout          | 1st         | 2nd         | 3rd         |
| Total wind farm capacity (MW) | 160         | 209         | 407         |
| Number of turbines (−)        | 80          | 91          | 49          |
| Turbine size (MW)             | 2.0         | 2.3         | 8.3         |
| Rotor diameter (m)            | 80          | 93          | 164         |
| Turbine hub height (m)        | 70          | 68          | 105         |
| Turbine upper tip height (m)  | 110         | 114         | 187         |

In the S-1 wind field map observed on the morning of 9 September 2024, covering part of the German Bight, the winds were below 2 m/s, and the wind farms are visible (Fig. 5 ). Most wind farms group in clusters. This example is shown to illustrate the presence of several clusters of wind farms, as observed by S-1, characterized by high backscatter in calm conditions.

![Figure 5](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr5_lrg.jpg?httpAccept=%2A%2F%2A)

Sentinel-1 wind field map from 9 September 2024 at 05:49 UTC covering the German Bight in the North Sea. Offshore wind farms are indicated.

### Validation results on mapping wind turbine locations

Results on mapping wind turbine locations based on S-1 include five studieslisted in Table 5 .

Table 5

List of publications on S-1-based offshore wind turbine location mapping.

| Reference                | S-1       | Location | #       | Period    | Method                          |
| ------------------------ | --------- | -------- | ------- | --------- | ------------------------------- |
| Ding et al., 2024        | S-1 IW VV | China    | ⁎       | 2015–2022 | Deep learning                   |
| Ma et al., 2024          | S-1 IW VH | Scotland | 95      | 2020–2022 | Adaptive threshold segmentation |
| de Carvalho et al., 2023 | S-1 IW VV | England  | 15      | 2022–2023 | Semantic segmentation           |
| Hoeser et al., 2022      | S-1 IW VH | Global   | ⁎⁎      | 2016–2021 | Deep learning                   |
| Zhang et al., 2021       | S-1 IW VV | Global   | 737,100 | 2015–2019 | Automatic adaptive threshold    |

⁎ S-1 data from December each year from 2015 to 2022.

⁎⁎ S-1 overlapping sample for three months globally was shown (and 20 quarterly sets were used).

The automatic adaptive threshold method, applied to S-1 IW VV data from 2015 to 2019, resulted in the identification of offshore wind turbines globally with 99% extraction accuracy. The validation was done for selected locations using optical satellite data, aerial photography, and databases. A total of 6924 offshore turbines were identified in 14 countries. The 1% of bright pixels not being turbines include meteorological masts and substations within or near the wind farms. The global offshore wind turbine database generated from S-1 scenes is available for free, and the code used to create this database can also be accessed (Zhang et al., 2021).

S-1 IW VV data were also used by de Carvalho et al. (2023) and Ding et al. (2024) to identify the location of offshore wind turbines. While de Carvalho et al. (2023) focused on the identification of wind turbines within wind farms in English waters and applied a semantic segmentation method based on S-1 data from 2022 to 2023, Ding et al. (2024) focused on the identification of wind turbines in China's coastal zones from 2015 to 2022 using deep learning methods. According to Ding et al. (2024), the number of offshore wind turbines in 2015 was 307, located in 7 wind farms across three provinces (Jiangsu, Shanghai, and Fujian), and had grown to 6451 wind turbines in 114 wind farms across 10 provinces by 2022. Jiangsu leads with 2900 offshore wind turbines, followed by Guangdong with 1296 turbines, and Fujian with 552. The validation was based on databases, optical satellite data, and visual inspection of S-1 data, yielding an accuracy of 93%.

Two studies were based on S-1 IW VH data. Ma et al. (2024) focused on providing the locations of turbines in Scottish waters from S-1 and optical satellite data from S-2. The location was achieved with 99.7% accuracy compared to other location results using an adaptive threshold segmentation method. Hoeser et al. (2022) expanded the list of turbine locations from Zhang et al. (2021) by incorporating two additional years of data. They discriminated between turbines in operation with 99% accuracy and in installation with 82% accuracy for the North Sea and East China Sea. The detection method was deep learning. The study focused on providing updates every 3 months; quarterly data is freely available globally. In 2021, there were 8885 offshore wind turbines, 852 platforms under construction, and 204 offshore wind farm substations (Hoeser et al., 2022).

### Summary on mapping turbine locations

In summary, detecting offshore wind turbine locations from S-1 VV and S-1 VH data is possible and can be applied globally. The optical data used for validation can be from satellites. An advantage of satellite SAR is its all-weather capability, which contrasts with optical satellite data that is limited by clouds. The benefit of SAR-based studies is the availability of homogeneous, open-access databases. The latest count included 8885 offshore wind turbines at the end of 2021. According to the US Department of Energy, the number of offshore wind turbines globally was over 11,900 in August 2023 (US DoE Departement of Energy Offshore Wind Market Report: 2023, 2023). A recommendation is to update the open database using S-1 at regular intervals.

## Wind farm wake analysis results based on SAR

### Studies on wind farm wake

There is a total of 18 studies, of which 11 are based on S-1, while seven studies are based on missions prior to S-1 (ERS, Envisat ASAR, TS-X, and R-2). The publications are listed in Table 6 . Out of the 18 studies, the length of wind farm wakes was published in 13 studies, and the velocity deficit in 12 studies. Seven studies examined the gradient in coastal winds, and four studies investigated atmospheric stability. Three studies investigated the counterintuitive speed-up of ocean surface winds downstream of wind farms. Six studies reported on the comparison of SAR-based wake observations and wake modelling results.

Table 6

List of publications on SAR-based offshore wind farm wake analysis for wind farms. VD is velocity deficit. Comparison includes comparison to other observations or to wake model results.

| Reference                             | SAR          | Wind farm                                                                                                                                                                                                                                           | VD  | Wake length | Topics                | Compa-rison |
| ------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ----------- | --------------------- | ----------- |
| Hasager et al., 2024                  | S-1<br>StriX | DanTysk                                                                                                                                                                                                                                             | +   |             | Stability<br>Speed-up | +           |
| (Heiberg-Andersen et al., 2022)       | S-1          | Sheringham Shoals, Dudgeon, Racebank                                                                                                                                                                                                                |     |             | Gradient              | +           |
| Owda and Badger, 2022                 | S-1          | Anholt, Horns Rev. cluster, Butendiek, Nordsee cluster, East Anglia One, Global Tech cluster, Greater Gabbard, Galloper, Hornse Project One                                                                                                         | +   | +           | Gradient              |             |
| Platis et al., 2020                   | S-1          | DanTysk, Sandbank,                                                                                                                                                                                                                                  |     | +           | Stability<br>Speed-up |             |
| Ahsbahs et al., 2020b                 | S-1          | Westermost Rough                                                                                                                                                                                                                                    | +   |             |                       | +           |
| Schneemann et al., 2020               | S-1          | BorWin, Global Tech1, Gemini, Dolwin                                                                                                                                                                                                                | +   | +           |                       |             |
| (Djath and Schulz-Stellenfleth, 2019) | S-1          | Alpha Ventus, Amrumbank West, Bard Offshore 1, Borkum Riffgrund,<br>Buitengaats, Buitendiek,<br>DanTysk, Global Tech, Gode Wind, Meerwind Sued/Ost,<br>Nordsee One, Nordsee Ost,<br>Riffgat, Sandbank, Trianel,<br>Veja Mate, ZeeEnergie, Veja Mate | +   | +           | Stability<br>Gradient |             |
| Djath et al., 2018                    | S-1<br>TS-X  | Alpha Ventus                                                                                                                                                                                                                                        | +   | +           | Speed-up<br>Gradient  |             |
| Ahsbahs et al., 2018                  | S-1<br>ASAR  | Anholt                                                                                                                                                                                                                                              | +   | +           | Gradient              |             |
| James, 2017                           | S-1          | Kentish Flats, Gunfleet Sands, London Array Phase 1, Thanet, Greater Gabbart, Galloper                                                                                                                                                              |     |             |                       |             |
| (Jacobsen et al., 2017b)              | S-1<br>TS-X  | Riffgat                                                                                                                                                                                                                                             |     | +           |                       |             |
| (Hasager et al., 2015c)               | R-2 ASAR     | Kentish Flats, Gunfleet Sands1 + 2, London Array Phase 1, Thanet, Greater Gabbard, Belwind1, Thornton Bank1 + 2 + 3, Horns Rev 1, Horns Rev 2                                                                                                       | +   | +           |                       | +           |
| (Jacobsen et al., 2017b)              | TS-X         | Alpha Ventus                                                                                                                                                                                                                                        | +   | +           |                       |             |
| Li and Lehner, 2013                   | TS-X         | Alpha Ventus                                                                                                                                                                                                                                        | +   | +           | Gradient              |             |
| Dagestad et al., 2012                 | TS-X<br>R-2  | Alpha Ventus, Sheringham Shoal                                                                                                                                                                                                                      |     |             |                       |             |
| Christiansen and Hasager, 2006        | ERS-2        | Horns Rev 1                                                                                                                                                                                                                                         | +   | +           |                       | +           |
| Hasager et al., 2006                  | ERS-2        | Horns Rev 1                                                                                                                                                                                                                                         |     | +           |                       | +           |
| Christiansen and Hasager, 2005        | ERS-2 ASAR   | Horns Rev 1, Nysted                                                                                                                                                                                                                                 | +   | +           | Stability<br>Gradient |             |

### Results on wind farm wake length

Many case studies based on SAR have quantified the wind farm wake length. The results of case studies include the wake length, names of wind farms and clusters:

- 10 km, Horns Rev 1(Christiansen and Hasager, 2006),
- 14 km, Thanet (Hasager et al., 2015c),
- 15 km, London Array (Hasager et al., 2015c),
- 18 km, Alpha Ventus (Li and Lehner, 2013),
- 20 km, Gemini (Schneemann et al., 2020),
- &gt;20 km, Horns Rev 1 (Christiansen and Hasager, 2005),
- 30 km, Alpha Ventus (Djath et al., 2018),
- 30 km, merged cluster wakes Dolwin2 and Global Tech1 (Schneemann et al., 2020).
- 40 km, DolWin1 (Schneemann et al., 2020),
- 40 km, cluster Bard Offshore 1 and Global Tech (Djath and Schulz-Stellenfleth, 2019),
- 45 km, Thornton Bank (Hasager et al., 2015c),
- 55 km, Belwind (Hasager et al., 2015c),
- 55 km, DolWin2 (Schneemann et al., 2020),
- 80 km, several wind farms in the German Bight (Jacobsen et al., 2017b),
- 85 km, Bard Offshore cluster (Fig. 6 )

![Figure 6](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr6_lrg.jpg?httpAccept=%2A%2F%2A)

  Sentinel-1 wind field map from 21 September 2024 at 05:50 UTC covering the German Bight in the North Sea. Moderate winds are coming from the east. The barbs showing wind direction and wind speed are from the GFS model. Wind farm and cluster wakes are seen downwind around 120 km long (transects A, B, C) and 85 km (transect D).
- &gt;100 km, merged cluster wakes Zee Energie, Buitengaats, and Borkum-Riffgrund (Djath and Schulz-Stellenfleth, 2019)
- 120 km, merged cluster Butendiek, DanTysk, and Sandbank (Fig. 6)
- 120 km, cluster Nordsee Ost (Fig. 6)
- 120 km, merged cluster Gode Wind cluster, Nordsee cluster, Trianel cluster, Borkum Riffgrund cluster, and Gemini (Fig. 6)

The listed wakes are from case studies on wind farms and cluster wakes in the North Sea. In the German Bight, more than 35 wind farms are in operation at present (4C Offshore, 2025).

In the S-1 wind field map observed on the morning of 21 September 2024, the winds were around 7 m/s from the east (Fig. 6). Note that the S-1 wind field maps shown in Fig. 5 and Fig. 6 cover the same area of the German Bight, and that the name of wind farms are provided in Fig. 5. Fig. 6. shows very long wind farm and cluster wakes. In the northern part of the German Bight, the wakes from Butendiek, DanTysk, and Sandbank merged and span around 120 km in length (transect A). In the middle of the German Bight, the Nordsee Ost cluster wake is around 120 km long (transect B). In the southern part, wakes from the Gode Wind cluster, Nordsee cluster, Trianel cluster, Borkum Riffgrund cluster, and Gemini merge and reach a length of around 120 km (transect C). In the eastern part, the Bard Offshore cluster wake reaches a length of around 85 km (transect D).

### Results on velocity deficit

The velocity deficit observed in SAR ranges up to 9% (Christiansen and Hasager, 2005), 10% (Christiansen and Hasager, 2006), 16% (Djath et al., 2018), 13% (Djath and Schulz-Stellenfleth, 2019), 24% (Li and Lehner, 2013), 25% (Schneemann et al., 2020), and 15% (Ahsbahs et al., 2020b). A comparison between SAR and dual-Doppler radar showed a velocity deficit of up to 27% in SAR at 10 m, while dual-Doppler radar showed a velocity deficit of up to 35% at hub height at Westernmost Rough; note these velocity deficit values were for two different cases (Ahsbahs et al., 2020b). Furthermore, the SAR vs. dual-Doppler radar analysis using crosswind transects showed a good correlation between SAR and dual-Doppler radar for most cases investigated. Schneemann et al. (2020) found a SAR velocity deficit of 25% at 24 km downstream and 21% at 55 km downstream, while scanning lidar showed a deficit of 41% at 24 km downstream. The cited results are case studies of wind farm wake conditions.

The *average velocity deficit* based on several SAR wind field maps was assessed by Christiansen and Hasager (2005). It showed an average velocity deficit of around 8% to 9% for wake recovery, defined as being within 2% of the reference wind speeds at Horns Rev. 1. The wind farm wake lengths were 5 km for unstable (average of three cases) and 20 km for near-neutral conditions (average of five cases). At Westermost Rough, the wind farm wake showed an average velocity deficit of 4% based on 12 wind field maps, while the average velocity deficit based on dual-Doppler radar ranged from 6% to 7.5% at hub height (Ahsbahs et al., 2020b).

Quantifying the *average velocity deficits* using SAR wind fields has been performed by assessing the average wind speeds observed before the installation of the turbines, and then subtracting these from the average wind speeds observed after commissioning. At Anholt, the average maximum deficit was 0.7 m/s based on 35 SAR scenes before wind farm installation and 24 scenes afterward (Ahsbahs et al., 2018). Owda and Badger (2022) studied several wind farms. Their results for the Nordsee cluster, specifically for flow from the east, showed a 3% velocity deficit reaching 21 km downstream, based on 148 scenes prior to and 84 scenes after. For westerly flow, a 3% velocity deficit was observed reaching 10 km downstream, based on 320 scenes prior to and 196 scenes after. The longer wakes for easterly compared to westerly flow at the Nordsee cluster can be explained by the lower average wind speeds from the east (0.8 m/s lower than the average wind speeds from the west), which cause more pronounced wakes.

To increase the number of samples for *average velocity deficit* analysis, Hasager et al. (2015c) suggested rotating and aligning the wind field maps with the wake direction. The average wind farm wakes from Alpha Ventus (245 scenes), Belwind 1 (97 scenes), Gunfleet Sand 1 + 2 (153 scenes), Thanet (128 scenes), Horns Rev 1 (835 scenes), and Horns Rev 2 (303 scenes) were calculated. The results consistently showed more significant velocity deficits near the wind farms and lesser velocity deficits at longer distances (Hasager et al., 2015c).

S-1 has been in operation for more than 10 years, and the number of samples has increased significantly since 2015. At the same time, many more wind farms were built. Thus, the method could be revisited with a much larger dataset for further verification.

### Results on the impact of atmospheric stability on wake

Four studies investigated the effect of stability on wakes observed from SAR (Christiansen and Hasager, 2005; Djath and Schulz-Stellenfleth, 2019; Platis et al., 2020; Hasager et al., 2024). In SAR-based studies, during unstable or neutral conditions, wind farm wakes, ranging from 5 to 10 km in length, were identified. For stable conditions, more extended wind farm wakes were observed (Christiansen and Hasager, 2005; Jacobsen et al., 2017a; Djath et al., 2018). However, Schneemann et al. (2020) reported slightly unstable conditions for many long wind farm wakes and noted that the wind farm wakes had the same width as the wind farms for a long distance and narrowed downstream based on SAR. Airborne campaigns with meteorological sensors on board have demonstrated wake lengths of up to 50 to 55 km for stable conditions and 10 to 15 km for unstable conditions (Cañadillas et al., 2020; Platis et al., 2020). All studies confirm that wakes are shorter in unstable and neutral conditions and longer in stable conditions.

### Results on the speed-up effect in the wake

Three studies reported speed-up effects in the waked area observed from SAR (Djath et al., 2018; Platis et al., 2020; Hasager et al., 2024). This counterintuitive observation has been ignored in earlier SAR-based studies.

Based on 180 S-1 scenes at Alpha Ventus, a surprising effect of negative velocity deficit, i.e., speed-up effect, was observed in around 25% of all cases by Djath et al. (2018). At first, it appears to be a paradox that wind speed can be higher downwind than upwind of the wind farm in the first 10 km. Djath et al. (2018) proposed a theory to explain higher backscatter due to mechanical turbulence generation in the wake area, which accounts for their counterintuitive observations. Platis et al. (2020) presented a case study based on S-1 at DanTysk and Sandbank, showing a speed-up downstream of around 10 km under stable conditions. DanTysk is located near the FINO3 meteorological mast, which provides stability information.

Later, a study on speed-up was done using S-1 and the Japanese StriX SAR data from Synspective (Hasager et al., 2024). First, FINO3 meteorological data were used to assess the accuracy of wind speed retrieval from StriX SAR data and S-1. StriX operates in X-band. XMOD-2 was used. Wind direction from FINO3 was used for both StriX and S-1 wind retrieval. The comparison showed comparable accuracy for StriX and S-1 (Badger et al., 2023). StriX has a higher spatial resolution than S-1, and wind farm wakes are visible in StriX imagery, including speed-up effects at DanTysk. Subsequently, an assessment of wind farm speed-up effects was conducted based on 67 StriX scenes and 1171 Sentinel-1 scenes for DanTysk (Hasager et al., 2024). For StriX, 48% showed a velocity deficit, 48% showed speed-up, and 4% of scenes showed neither (the wind speed difference was less than 0.1 m/s). For S-1, 54% showed a velocity deficit, 34% showed speed-up, and 11% showed neither. Based on FINO3 data, the potential temperature gradient was calculated. It was found that speed-up occurred in both stable and unstable conditions but prevailed more often in unstable conditions. StriX and S-1 gave similar statistics on the velocity deficit and speed-up percentage for stable and unstable conditions. The results underscore that S-1 is suitable for detecting wind farm wake speed-up effects, even though its spatial resolution is lower than that of StriX.

From a modelling perspective, the topic of speed-up effects has not attracted much attention either. Large-eddy simulation studies on speed-up effects have been conducted; however, they have not included SAR-based data (Yang et al., 2014; Vanderwende et al., 2016). Mesoscale modelling with a wind farm wake parametrization considered speed-up effects and included one SAR-based case (Larsén and Fischereit, 2021) and three SAR-based cases (Hasager et al., 2024).

### Results on very high-resolution SAR mapping wake

Very high-resolution SAR data have been applied in wake studies. The wake effect inside a wind farm was observed in very high-resolution TS-X SAR at Alpha Ventus (Li and Lehner, 2013). Wind speeds observed from SAR between wind turbines, i.e., inside the wind farm, are possible thanks to the very high-resolution SAR. Li and Lehner (2013) found a case at Alpha Ventus where the wakes did not merge until far downstream (20D). The case was characterized by wind direction parallel to the four wind turbine rows, and the wake showed four wakes that remained distinct much further downwind than in a case where the wind direction was not aligned with the turbine layout (Li and Lehner, 2013). Jacobsen et al. (2017b) suggested that von Kármán vortex street was located along the edge of the wind farm wake at Riffgat. The wind farm wake was observed using airborne C-band SAR with very high resolution at Horns Rev 1 and compared to satellite SAR. Both SAR data sources showed limited dispersion of the wind farm wake and similar velocity deficits (Christiansen and Hasager, 2006). The velocity deficit from airborne SAR was around 10% (Hasager et al., 2018).

### Comparison results of wake observed by SAR vs. wake models

Several studies have compared SAR-based wind farm wake results to results from wake models. An engineering wake model with added roughness was used for one case with a wind speed of around 7 m/s at Horns Rev. 1. The wake observed from SAR and results from the wake model compared well from the wind farm to 9 km downstream at 10 m height along the horizontal transect line in the wake direction (Hasager et al., 2006). Another engineering wake model was used for a case involving long wind farm wakes observed by SAR at Gunfleet Sands, Kentish Flats, London Array Phase 1, Greater Gabbard, Thanet, Belwind 1, and Thornton Bank 1, 2, and 3 in the North Sea. The engineering wake model provided comparable results in qualitative terms, as the SAR provided 10 m height data, and the engineering wake model provided 70 m height results. The wind speed was approximately 9 m/s, and the wind direction remained consistent throughout the entire domain, enabling the engineering wake model to capture the velocity deficits and lengths of the wakes accurately (Hasager et al., 2015c). For the same case, the WRF model, coupled with a parametrization for wind farm impact on the flow, was applied, and results at a 10 m height were retrieved. The model run calculation without wind farm was subtracted from the model run, including the wind farms, and the difference map showed the velocity deficits and lengths of wind farm wakes, which compared well to the SAR-derived wind farm wakes.

Three cases with speed-up effects in the wake area at DanTysk observed by StriX and one by S-1 were compared to results from the WRF model coupled with two parametrizations for wind farm impact (Hasager et al., 2024). The wind farm velocity deficits are found from the subtraction of results from WRF runs without and with the wind farms included. Interestingly, the speed-up effects at 10 m could be resolved by WRF for the three cases observed by StriX. However, in one case, the result was slightly offset in time, meaning the atmospheric condition with wind farm wake speed-up appeared to prevail 30 min before the SAR-based wake was observed. The WRF model adjusts to ambient conditions, and a slight time offset was occasionally seen in the model results. In the case showing the speed-up observed by S-1, the speed-up was not resolved by WRF. WRF showed a velocity deficit at 10 m. Note, for all cases, WRF showed a velocity deficit at hub height.

Only one study compared the *average wind farm wake* observed by SAR versus the average wind farm wake from wake model results. The results are from Horns Rev 1 and 2 and include an engineering wake model and WRF with a wind farm parametrization. The SAR-based average wakes compare well to the wake model results at both farms (Hasager et al., 2015c).

### Summary on wake studies based on SAR

Satellite SAR is uniquely well-suited to quantify the length of wind farm wakes. SAR has provided ground-breaking evidence of very long wind farm and cluster wakes. Observations from dual-Doppler radar, scanning wind lidar, and airborne sensors are limited in range and duration, and are costly compared to SAR, and have not been able to map the long wind farm wakes to the full extent.

Satellite SAR provided the first-ever evidence of long offshore wind farm wakes. Later, the extended offshore wind farm wakes were confirmed by other sources such as wake modelling, SCADA data, scanning lidar, dual-Doppler radar, an airborne campaign with SAR, and an airborne campaign with atmospheric sensors. SAR captures the full extent of wind farm wakes, such as lengths of 100 km, a distance difficult to match by other observations. SAR first observed the counterintuitive speed-up downwind of wind farms at 10 m height. Speed-up downwind of wind farms has been reproduced by WRF wake.

Cluster wakes were also observed first and most detailed by SAR. Many countries plan to scale up offshore wind capacity in the coming years. Hence, the effects of wind farm clusters attract attention to the wind energy sector. SAR holds an extraordinarily valuable source of information on ocean surface winds, past and present, at a high spatial resolution that can be effectively used to compare the wake effects of new wind farms and clusters with the conditions prior to them. SAR unique allows monitoring of the impact of wind farms on offshore winds.

A recommendation for the applied use of SAR for wind farm wake studies is to conduct studies comparing different wind farm wake methods utilizing the S-1 archive. Furthermore, additional information from wind farms on their operational status and meteorological observations would be relevant to include in these studies, providing further insight into wind farm wake and cluster effects. Modelling of wakes using LES could be relevant for comparing with SAR-based wake observations, providing fine details.

## Wind resource assessment results based on SAR

### Studies on wind resources

Studies on applying SAR wind fields for assessing offshore wind resources and energy potential vary. Many focus on the mean wind speed, energy density, Weibull *A* and *k* parameters, and calculate maps for the area of interest based on the available SAR wind fields. Some extract wind resource statistics at one or more local sites of interest within the maps. The site-specific analysis often includes wind roses retrieved from SAR and the probability density function (pdf) of wind speeds. The impact of diurnal wind speed variations on SAR-derived wind resources, which prevail as observed by SAR at specific local times, has been quantified in some studies. Some investigate seasonal and monthly wind speed variations either in the form of maps or at specific local sites (Tuy et al., 2022; Caligiuri et al., 2022; Li et al., 2021; Ahsbahs et al., 2020a; de Montera et al., 2020; Majidi Nezhad et al., 2019; Doubrawa et al., 2015; Furevik and Espedal, 2002). Most studies compare SAR-based wind resource results to other data sources. Comparison with local observations include observations from meteorological masts, wind profiling lidar, and wind turbines. Comparisons with numerical model output are reported and performed. Numerous studies have noted that horizontal wind speed gradients are more detailed in SAR data than in models.

There are 16 studies on offshore wind resources based on S-1, of which 14 include wind resource comparison analysis to other data sources. Seven of the 16 studies report wind resources at hub height, while the others report them at 10 m. The wind resource studies based on S-1 are listed in Table 7 . Three studies combine S-1 and Envisat. One study combines S-1, Envisat, and R-1. Fig. 7 illustrates the number of studies on offshore wind resources based on S-1 and prior missions, categorized by continent. Most studies were done in Europe.

![Figure 7](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr7_lrg.jpg?httpAccept=%2A%2F%2A)

Number of studies on offshore wind resource studies based on Sentinel-1 and prior SAR missions.

Table 7

List of publications on SAR-based wind resources using S-1. Note that the number of scenes does not necessarily overlap but can cover a large area.

| Reference                  | SAR                | Location         | # scenes   | Height (m) | U (m/s) | Weibull | E (W/m<sup>2</sup>) | Pdf | Wind rose | Season | Site | Map | Comparison |
| -------------------------- | ------------------ | ---------------- | ---------- | ---------- | ------- | ------- | ------------------- | --- | --------- | ------ | ---- | --- | ---------- |
| Khachatrian et al., 2024   | S-1                | Norwegian Arctic | 238        | 10         | +       | +       |                     | +   |           |        | +    |     | +          |
| Cathelain et al., 2023     | S-1<br>ASAR        | South Brittany   | 4000⁎      | 10<br>140  | +       |         |                     |     |           |        | +    | +   | +          |
| Badger et al., 2023        | S-1<br>StriX       | North Sea        | 1445       | 10         | +       | +       | +                   |     |           |        | +    |     | +          |
| de Montera et al., 2022    | S-1                | North Sea        | ?          | 10<br>120  | +       |         | +                   |     |           |        | +    | +   | +          |
| Tuy et al., 2022           | S-1                | Cambodia         | 515        | 10         | +       |         |                     |     | +         | +      | +    | +   | +          |
| Caligiuri et al., 2022     | S-1                | Ionian Sea       | 54         | 10<br>90   |         |         |                     |     |           | +      |      | +   |            |
| (Hadjipetrou et al., 2022) | S-1                | Cyprus           | 475        | 10         | +       | +       | +                   |     |           |        | +    | +   | +          |
| Majidi Nezhad et al., 2021 | S-1                | Baltic Sea       | 25         | 65         | +       |         |                     |     |           |        | +    |     | +          |
| Li et al., 2021            | S-1                | Fujian           | 102        | 10<br>90   | +       |         | +                   |     |           | +      |      | +   | +          |
| Ahsbahs et al., 2020a      | S-1<br>ASAR<br>R-1 | US East Coast    | 6582       | 10         | +       | +       | +                   | +   | +         | +      | +    | +   | +          |
| de Montera et al., 2020    | S-1                | Ireland          | 5509       | 10         | +       | +       | +                   | +   |           | +      | +    | +   | +          |
| Majidi Nezhad et al., 2020 | S-1                | Sardinia         | 54         | 10         | +       |         |                     |     |           |        |      | +   |            |
| Hasager et al., 2020       | S-1<br>ASAR        | Europe           | &gt;20,000 | 10<br>100  | +       | +       | +                   |     |           |        |      | +   | +          |
| Badger et al., 2019        | S-1<br>ASAR        | North Sea        | 10000⁎     | 10         | +       | +       | +                   | +   |           |        | +    |     | +          |
| Majidi Nezhad et al., 2019 | S-1                | Sicily           | 96         | 10         | +       |         |                     | +   |           | +      |      | +   |            |
| Ahsbahs et al., 2018       | S-1                | Denmark          | 47         | 10<br>82   | +       |         |                     |     |           |        | +    |     | +          |

⁎ Estimates.

SAR-derived wind resource studies prior to S-1 are based on ASAR (12 studies), ESR-1/2 (four studies), and R-1 (three studies), listed in Table A.1 in Appendix A. Only nine of these studies include a comparison of wind resources to other data sources (but many compared wind speed accuracy at 10 m). Two studies reported wind resources at hub height, while all others reported them at 10 m. The geographical distribution of studies prior to Sentinel-1 is shown in Fig. 7, with 11 studies in Europe, 4 in North America, and 4 in Asia.

### Impact of SAR wind truncation and number of samples

SAR does not resolve wind speed well below 2 m/s. Based on observations in the North Sea, the truncation of SAR winds below 2 m/s was found to cause an overestimation of 3% in mean wind speed and 2% in energy density. Despite the low data quality in SAR winds for weak winds, it is strongly advisable to maintain the low SAR wind speed data when performing SAR-based Weibull fitting to assess energy density (Eq. 5) to avoid overestimation (Badger et al., 2023).

Many areas of interest for offshore wind farm planning were investigated based on S-1. In Northern Europe: North Sea (Badger et al., 2019; de Montera et al., 2023; Badger et al., 2023), Ireland (de Montera et al., 2020), inner Danish Seas (Ahsbahs et al., 2020a), Baltic Sea (Majidi Nezhad et al., 2021), South Brittany (Cathelain et al., 2023), and Norwegian Arctic (Khachatrian et al., 2024). In the Mediterranean Sea: Sicily (Majidi Nezhad et al., 2019), Sardinia (Majidi Nezhad et al., 2020), Cyprus (Hadjipetrou et al., 2022), and the Ionian Sea (Caligiuri et al., 2022). One study covered offshore Europe (Hasager et al., 2020). In Asia, Fujian (Li et al., 2021) and Cambodia (Tuy et al., 2022) are notable examples, while in US waters, the seas along the East Coast (Ahsbahs et al., 2020a) are also affected.

A study in South Brittany, based on sparse and dense sampling using model results for the long term, showed that the correction was, on average, 0.084 m/s for wind speed within the area of interest (Cathelain et al., 2023). A study in the Norwegian Arctic based on sparse and dense sampling using a model for long-term showed differences for Weibull *A* around 2% and for Weibull *k* around 2.5%, while using sparse and dense sampling from mast data showed differences for Weibull *A* around 2% and for Weibull *k* around 8% (Khachatrian et al., 2024).

To increase the number of samples, in three European studies, S-1 was combined with Envisat (Badger et al., 2019; Hasager et al., 2020; Cathelain et al., 2023), and in the US East Coast study, S-1 was combined with Envisat and R-1 (Ahsbahs et al., 2020a).

In 2023, the number of overlapping samples from SAR combining S-1 and Envisat was approximately 1500 in the Mediterranean Sea and 4000 in the Barents Sea (Badger et al., 2023). Five years prior, the available samples counted around 500 in the Mediterranean Sea and 2500 in Northern Europe (Hasager et al., 2020). Many studies show maps of the number of overlapping samples. The number varies across the areas of interest (e.g., Cathelain et al., 2023; Ahsbahs et al., 2020; Hasager et al., 2020).

The currently available number of samples from S-1 for Europe is presented in Fig. 8 , and the mean wind speed at 10 m based on the data set in Fig. 9 . Fig. 10 shows number of samples from S-1 at FINO1. More than 400 samples per year is available with two operating S-1 missions (2017–2021).

![Figure 8](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr8_lrg.jpg?httpAccept=%2A%2F%2A)

Number of overlapping samples from Sentinel-1 from 2014 to 2024 based on data from the SAR wind archive at DTU Wind and Energy Systems.

![Figure 9](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr9_lrg.jpg?httpAccept=%2A%2F%2A)

Sentinel-1 average wind speed at 10 m from 2014 to 2024 based on DTU Wind and Energy Systems archive.

![Figure 10](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-gr10_lrg.jpg?httpAccept=%2A%2F%2A)

Sentinel-1 number of samples per year from 2014 to 2024 at FINO1 based on DTU Wind and Energy archive.

### The effect of non-random sampling and seasons

Based on 7 years of meteorological observations at FINO3 in the North Sea, Badger et al. (2023) reproduced the results by Barthelmie and Pryor (2003) on the effect of non-random observation times. The recent results confirmed the findings of the previous study. Badger et al. (2023) quantified the impact of a fixed sampling time, which resulted in a slight underestimation of energy density at FINO3. de Montera et al. (2022) reported comparable results and quantified the correction for diurnal wind speed variation as 0.5% on mean wind speed and below 1% on energy density in the North Sea. A study in Ireland showed the diurnal effect on energy density to be less than 7% (de Montera et al., 2020). The impact of fixed sampling time on wind resource assessment, based on a combination of S-1, Envisat, and R-1, was found to be more pronounced near the shore than further offshore, where it was negligible (Ahsbahs et al., 2020a). Diurnal wind speed variations are site-dependent, and studies are lacking in other seas.

Numerous SAR-based wind resource studies list the number of available samples per month to consider the representation of seasonal wind variability.

A correction method to mitigate the seasonal effects was developed and applied to the US East Coast by Ahsbahs et al. (2020a). The number of available overlapping samples within the area of interest varied temporally and spatially. With the seasonal correction applied in SAR-based wind speed, RMSE was reduced from 0.63 m/s to 0.39 m/s, and the bias was reduced from 0.34 m/s to 0.09 m/s compared to buoy wind speed data. The correction summed to ±0.8 m/s on the mean wind speed and was shown as mean wind speed maps and seasonally corrected difference. Interestingly, in the northern part of the area of interest, the correction was −0.8 m/s, near-zero in the central part, and positive 0.8 m/s in the southern part (Ahsbahs et al., 2020a).

### Hub height wind resources

SAR-based wind fields are retrieved at 10 m height. Assessing the wind resource at hub height is preferable for wind energy applications. Three studies report SAR-based wind resource statistics at hub height without comparison to other sources: One study used the power law in the Ionian Sea (Caligiuri et al., 2022). Two studies used the neutral logarithmic profile covering the Great Lakes (Doubrawa et al., 2015) and Fujian (Li et al., 2021).

Majidi Nezhad et al. (2021) employed the neutral profile and compared wind speed data with wind turbine data at 65 m at the Lillgrund wind farm in the Baltic Sea. In the inner Danish Seas at the Anholt wind farm with a hub height of 82 m, Ahsbahs et al. (2018) used the neutral wind profile and compared S-1 wind speed to wind turbine data for free stream turbines (first row) and for waked turbines (last row) and found RMSE at 2.23 m/s and 2.12 m/s, respectively. In the same study, the wind turbine data were also extrapolated to 10 m, and the comparisons resulted in RMSE values of 1.80 m/s and 1.70 m/s for free-stream and waked conditions, respectively. Hadjipetrou et al. (2022)used the neutral logarithmic wind profile to provide hub-height winds. They compared it to the model UERRA (10-year reanalysis product), Weibull *A* and *k*, and found good agreement at most of the six stations investigated in Cyprus.

The stability-dependent extrapolation method developed by Badger et al. (2016) was applied in the Southern Baltic Sea. The results showed an increase in wind speed of 0.5 m/s at 100 m compared to the neutral wind profile extrapolation and significant variability in the Southern Baltic Sea. The SAR-based wind resource statistics, compared with the FINO2 meteorological mast data from the tall mast, were of similar statistical quality to the WRF model results. SAR provided higher spatial details than WRF (Badger et al., 2016).

The extrapolation method by Badger et al. (2016) was applied to the European Seas, using the combined S-1 and Envisat archives (Hasager et al., 2020). The difference in wind speed at 100 m, using long-term stability correction and the neutral wind profile, shows significant spatial variability in the European Seas. For most locations, an increase in mean wind speed was observed following the stability correction. There is much higher spatial detail in the mean wind speed at 100 m based on SAR-based observations compared to the WRF model and Advanced Scatterometer (ASCAT) results. It was shown that the error distributions of the wind speed difference at 100 m are broad for SAR minus WRF and SAR minus ASCAT. In contrast, the error distribution for ASCAT minus WRF is narrow as they resolve similar spatial scales at a lower resolution than SAR (Hasager et al., 2020).

Extrapolation of 10 m SAR-based winds to hub height using a machine learning approach was developed, applied, and tested in the Southern North Sea by de Montera et al. (2022). The results from a round-robin validation using wind lidar data showed errors in mean wind speed within ±3% and errors in energy density within ±7% from the SAR-derived assessment at 120 m. SAR resolved the coastal wind speed gradient better than WRF did. The extrapolation method applied to individual SAR wind maps revealed that SAR-based 120 m wind speeds, when compared to lidar data, had significantly lower scatter than those obtained using the power law for SAR-based 120 m wind speeds (de Montera et al., 2022). SAR resolved the coastal gradients much better than WRF, and the variability in winds in the coastal zone is significant for wind energy (de Montera et al., 2022).

The machine learning extrapolation method by de Montera et al. (2022) was applied in South Brittany using S-1 and Envisat combined. The results at 140 m were compared to wind lidar data, showing a bias between −0.07 and 0.18 m/s in wind speed (Cathelain et al., 2023).

### Summary on wind resource assessment based on SAR

In summary, SAR can map offshore wind resources. The spatial resolution of S-1 SAR is adequate to resolve the spatial variations in wind speed in the areas of interest for offshore wind farms. S-1 is providing observations of significant coastal wind speed gradients in the European Seas. SAR maps spatial wind speed variations and coastal gradients better than mesoscale models at 10 m.

S-1 contributes the massive temporal and spatial resolution over Europe needed for wind resource assessment based on SAR. There are more than 1000 overlapping samples in all European Seas of interest for offshore wind farms from S-1. Combined with SAR from prior missions, the number of overlapping samples is beyond 1500. Combining SAR winds from missions prior to S-1 requires inter-calibration to achieve optimal results.

The effect of diurnal wind speed variation has a negligible implication for wind resource assessment based on SAR in the investigated regions. Studies in other regions might show non-negligible results. A method to alleviate diurnal effects is to use external sources.

SAR-based wind resource statistics at hub height are comparable to those from mesoscale models, according to recent studies conducted at locations in the Northern European Seas. The input for vertical extrapolation – whether based on physical modelling or AI-based methods – relies on stability information from mesoscale modelling. Mesoscale model output of relevant parameters is not a limitation for the method. Mesoscale model output is available globally.

However, a limitation of entrusting SAR-based wind resource assessment at wind turbine hub height is that only a limited number of comparison studies on vertical extrapolation from 10 m to hub height exist. A recommendation is to address this in future work. Wind speed observations at hub height are often collected by developers and not made publicly available. If data sharing agreements are established, a comprehensive validation could be performed, and optimal processing methods for SAR-based wind resource assessment could be verified.

## Conclusion

Sentinel-1 (S-1) for offshore wind energy applications relies on accurate ocean surface wind fields. From 25 studies evaluating the accuracy of wind speed derived from S-1, it is noted that CMOD5.N is most commonly used, and wind direction input is from global numerical forecast models. Most studies on SAR wind speeds compared to buoy wind speeds showed RMSE around 1.5 m/s and bias around ±0.5 m/s. Post-processing SAR wind fields using inter-calibration between SAR sensors, buoy data, or correction of geometrical effects using buoy data and machine learning improved the statistics, showing an RMSE of around 1.1 to 1.3 m/s and a bias of around 0 m/s. Based on a neural network, the GMF OPEN provided statistics at the same order of magnitude, making it a promising method.

The location of wind turbines globally, derived from S-1, provided the first homogeneous, free-access archive. In five studies, methods for achieving reliable mapping of wind turbine locations from SAR yield results with an accuracy above 99%. With the growth in new wind turbines, updates would be relevant, as the latest assessment, based on S-1, was from the end of 2021, showing 8885 offshore wind turbines globally. At present, the number is likely above 13,000. A recommendation is to refresh the S-1-based free access archive regularly to provide up-to-date, homogeneous information.

Wind farm wake studies included eleven studies based on S-1 and seven on SARs before S-1. SAR provided the first-ever observation on long offshore wind farm wakes. Later, other data sources and wake modelling confirmed the wind farm wake length. S-1 showed wakes from clusters reaching longer than 100 km. SAR captured the full extent of wind farm wakes in greater detail and at distances that were not easily matched from other observations. SAR ocean surface winds were used to quantify the wake effects of wind farms and clusters, including length and velocity deficits. Interestingly, a speed-up effect was first observed downwind of wind farms by SAR. Speed-up within the first 10 km downwind of a wind farm is counterintuitive. However, the speed-up downwind of wind farms at 10 m height was reproduced by WRF wake modelling using advanced parametrization for the wind farm impact on the atmospheric flow.

Along with the plans for more offshore wind farms, the need for more information on wind farm cluster wakes increases. SAR-based studies using S-1 could support this. A current limitation is the lack of comprehensive comparison studies on wake detection methods based on SAR to ensure optimal analysis. A recommendation is to compare different SAR-based wind farm wake detection methods and utilize information on wind farm operational status and meteorological observations combined.

There are sixteen studies evaluating wind resource assessment based on S-1, and eighteen studies based on SARs prior to S-1. Key learnings showed that wind resource assessment relies on enough samples currently accessible in European and the US waters. The fixed observation times and uneven distribution of SAR wind fields can be alleviated by using longer-term statistics from external sources, such as buoy data, to adjust wind resource calculations and achieve more representative values. S-1 provided significantly greater spatial detail than mesoscale models and resolved the coastal wind speed gradients excellently. Even the wind farms located the farthest offshore were subject to coastal wind speed gradients. S-1 provides more than 1000 overlapping samples in the European Seas of areas relevant for offshore wind energy. The number of samples is adequate for wind resource assessment.

The hub height S-1-based wind resource statistics were comparable in accuracy to mesoscale models. The wind resource statistics at hub height are accurate within a few percent. The achievements were based on extrapolating from 10 m to hub height using longer-term average stability from mesoscale models, in a physical context, utilizing Monin-Obukhov similarity theory or machine learning. Mesoscale model output is not limited by geography; thus, it is possible everywhere. Sentinel-1 can support the green transition in offshore wind energy with spatial assessment of the wind resource.

The trust in SAR-based wind resource assessment at wind turbine hub height could increase from comprehensive comparison studies on vertical extrapolation from 10 m to hub height. Limited access to wind speed observations at hub height is another reason. If data sharing agreements are established with wind farm developers to share their hub height wind speed data, a comprehensive validation could be performed, and processing methods for SAR-based wind resource assessment could be further verified.

The Copernicus long-term monitoring program secures the future for C-band SAR. S-1A has been operational since 2024, with consumables expected to last for 12 years. S-1C was launched in 2024 with a planned end of life in 2034, while S-1D was launched November 2025 with a planned end of life in 2035. The Copernicus product will include the ocean wind field level 1 and level 2 products. The orbit parameters are suitable for offshore wind energy applications. Offshore wind engineering has already gained substantially from two decades of SAR observations and stands to benefit even more in the years ahead.

## CRediT authorship contribution statement

**C.B. Hasager:** Writing – original draft, Visualization, Methodology, Funding acquisition, Data curation, Conceptualization. **K. Dimitriadou:** Writing – review & editing, Visualization, Funding acquisition, Data curation.

## Acknowledgements

We thank JHU APL and NOAA for the use of the SAROPS system. We acknowledge Copernicus for public access to Sentinel-1 data. ESA Φ-lab partly funds this work as part of the Future EO Foresight element and contract ESAWAAI (Explainable SAR measurements for Wind Assessment with Artificial Intelligence) project with Contract No. 4000142170/23/DT. We thank Abhiram Vinod for preparing Figure 2. We thank the reviewers for their help.

## Appendix

![Figure A.1](https://api.elsevier.com/content/object/eid/1-s2.0-S0034425726001392-fx1_lrg.jpg?httpAccept=%2A%2F%2A)

Map of the locations of the offshore wind farms Vindeby, Horns Rev. 1, and Alpha Ventus, and three FINO meteorological masts.

Table A.1

List of publications on SAR-based wind resources using Envisat ASAR, ERS, and R-1. Note that the number of scenes does not necessarily overlap but can cover a large area.

| Reference                 | SAR  | Location          | # scenes | Height (m) | U (m/s) | Weibull | E (W/m<sup>2</sup>) | pdf | Wind rose | Season | Site | Map | Comparison |
| ------------------------- | ---- | ----------------- | -------- | ---------- | ------- | ------- | ------------------- | --- | --------- | ------ | ---- | --- | ---------- |
| (Hasager et al., 2008)    | ASAR | Baltic Sea        | 239      | 10         | +       |         |                     |     |           |        |      | +   |            |
| Badger et al., 2016       | ASAR | Baltic Sea        | 7000     | 10<br>100  | +       | +       | +                   |     |           |        | +    | +   | +          |
| (Hasager et al., 2015b)   | ASAR | North Sea         | 9256     | 10         | +       | +       | +                   |     | +         |        | +    | +   |            |
| Doubrawa et al., 2015     | ASAR | Great Lakes       | 764      | 10<br>90   | +       |         |                     |     |           | +      |      | +   |            |
| Chang et al., 2015        | ASAR | South China Sea   | 460      | 10         | +       | +       |                     | +   | +         |        | +    |     | +          |
| (Hasager et al., 2015a)   | ASAR | Iceland           | 2581     | 10         | +       | +       | +                   |     | +         |        | +    | +   | +          |
| Monaldo et al., 2014      | R-1  | Maryland          | ?        | 10         | +       |         |                     | +   |           |        |      | +   | +          |
| Kim et al., 2014          | ASAR | Korea             | 4        | 10         | +       |         |                     |     |           |        |      | +   |            |
| Chang et al., 2014        | ASAR | East China Sea    | 181      | 10         | +       | +       | +                   |     | +         |        | +    | +   | +          |
| Takeyama et al., 2013     | ASAR | Japan             | 106      | 10         | +       |         |                     |     |           |        |      | +   | +          |
| Dagestad et al., 2012     | ASAR | Northern Seas     | 9000     | 10         | +       |         |                     |     | +         |        |      | +   |            |
| Hasager et al., 2011      | ASAR | Baltic Sea        | 1009     | 10         | +       | +       | +                   |     |           |        | +    | +   | +          |
| Badger et al., 2010       | ASAR | North Sea         | 627      | 10         | +       | +       | +                   |     | +         |        | +    | +   | +          |
| Beaucage et al., 2008     | R-1  | St. Lawrence Gulf | 14       | 10         | +       |         |                     |     |           |        |      | (+) | +          |
| Christiansen et al., 2006 | ERS  | North Sea         | 91       | 10         | +       | +       | +                   |     |           |        |      |     |            |
| Hasager et al., 2006      | ERS  | North Sea         | 85       | 10         | +       | +       | +                   |     | +         |        |      |     |            |
| Schneiderhan et al., 2005 | ERS  | North Sea         | 35       | 10         | +       |         |                     |     |           |        | +    |     |            |
| Choisnard et al., 2004    | R-1  | St. Lawrence Gulf | 16       | 10         | +       |         |                     |     |           |        |      | +   |            |
| Furevik and Espedal, 2002 | ERS  | Bergen            | 26       | 10         | +       |         |                     |     |           | +      |      |     |            |

## Data availability

Data will be made available on request.

## References (126 total, showing 126)

1. 4C Offshore. 2025. https://www.4coffshore.com. (last access November 2025) [4C Offshore, 2025]

2. T. Ahsbahs, M. Badger, I. Karagali, X.G. Larsén. 2017. Validation of sentinel-1A SAR coastal wind speeds against scanning LiDAR. Remote Sens., 9. 10.3390/rs9060552 [Ahsbahs et al., 2017]

3. T. Ahsbahs, M. Badger, P. Volker, K.S. Hansen, C.B. Hasager. 2018. Applications of satellite winds for the offshore wind farm site Anholt. Wind Energy Sci., 3: 573-588. 10.5194/wes-2018-2 [Ahsbahs et al., 2018]

4. T. Ahsbahs, G. Maclaurin, C. Draxl, C.R. Jackson, F. Monaldo, M. Badger. 2020. US east coast synthetic aperture radar wind atlas for offshore wind energy. Wind Energ. Sci., 5: 1191-1210. 10.5194/wes-5-1191-2020 [Ahsbahs et al., 2020a]

5. T. Ahsbahs, N.G. Nygaard, A. Newcombe, M. Badger. 2020. Wind farm wakes from SAR and Doppler radar. Remote Sens., 12. 10.3390/rs12030462 [Ahsbahs et al., 2020b]

6. M. Badger, J. Badger, M. Nielsen, C.B. Hasager, A. Peña. 2010. Wind class sampling of satellite SAR imagery for offshore wind resource mapping. J. Appl. Meteorol. Climatol. 10.1175/2010jamc2523.1 [Badger et al., 2010]

7. M. Badger, A. Peña, A.N. Hahmann, A.A. Mouche, C.B. Hasager. 2016. Extrapolating satellite winds to turbine operating heights. J. Appl. Meteorol. Climatol., 55. 10.1175/jamc-d-15-0197.1 [Badger et al., 2016]

8. M. Badger, T.T. Ahsbahs, P. Maule, I. Karagali. 2019. Inter-calibration of SAR data series for offshore wind resource assessment. Remote Sens. Environ., 232. 10.1016/j.rse.2019.111316 [Badger et al., 2019]

9. M. Badger, I. Karagali, D. Cavar. 2022. Offshore Wind Fields in near-Real-Time. Technical University of Denmark. 10.11583/dtu.19704883.v1. Dataset [Badger et al., 2022]

10. M. Badger, A. Fujita, K. Orzel, D. Hatfield, M. Kelly. 2023. Wind retrieval from constellations of small SAR satellites: potential for offshore wind resource assessment. Energies, 16. 10.3390/en16093819 [Badger et al., 2023]

11. R.J. Barthelmie, S.C. Pryor. 2003. Can satellite sampling of offshore wind speeds realistically represent wind speed distributions. J. Appl. Meteorol., 42: 83-94. 10.1175/2096.1 [Barthelmie and Pryor, 2003]

12. Beal, R.C., Young, G.S, Monaldo, F.M., Thompson, D.R., Winstead, N.S., Scott, C.A., 2005. High Resolution Wind Monitoring with Wide Swath SAR: A User's Guide. US. Department of Commerce, NOAA, Washington DC. [Beal et al., 2005]

13. P. Beaucage, M. Bernier, G. Lafrance, J. Choisnard. 2008. Regional mapping of the offshore wind resource: towards a significant contribution from space-borne synthetic aperture radars. IEEE J. Sel. Top. Appl. Earth Observ. Remote Sens., 1: 10.1109/JSTARS.2008.2001760. 10.1109/jstars.2008.2001760 [Beaucage et al., 2008]

14. C. Caligiuri, L. Stendardi, M. Renzi. 2022. The use of Sentinel-1 OCN products for preliminary deep offshore wind energy potential estimation: a case study on Ionian Sea. Eng. Sci. Technol. Int. J., 35. 10.1016/j.jestch.2022.101117 [Caligiuri et al., 2022]

15. B. Cañadillas, R. Foreman, V. Barth, S. Siedersleben, A. Lampert, A. Platis, B. Djath, J. Schulz-Stellenfleth, J. Bange, S. Emeis, T. Neumann. 2020. Offshore wind farm wake recovery: airborne measurements and its representation in engineering models. Wind Energy, 23: 1249-1265. 10.1002/we.2484 [Cañadillas et al., 2020]

16. M. Cathelain, R. Husson, H. Berger, M. Fragoso. 2023. Estimation of wind resource assessment at high-resolution using SAR observations, validated with lidar measurements. Offshore Technology Conference, Houston, Texas, USA. 10.4043/32164-ms [Cathelain et al., 2023]

17. CDSE. 2025. Copernicus Data Space Ecosystem. European Commission. https://dataspace.copernicus.eu/data-collections/sentinel-data/sentinel-1. (last access November 2025) [CDSE, 2025]

18. R. Chang, R. Zhu, M. Badger, C.B. Hasager, R. Zhou, D. Ye, X. Zhang. 2014. Applicability of synthetic aperture radar wind retrievals on offshore wind resources assessment in Hangzhou Bay, China. Energies, 7: 3339-3354. 10.3390/en7053339 [Chang et al., 2014]

19. R. Chang, R. Zhu, M. Badger, C.B. Hasager, X. Xing, Y. Jiang. 2015. Offshore wind resources assessment from multiple satellite data and WRF modeling over South China Sea. Remote Sens., 7: 467-487. 10.3390/rs70100467 [Chang et al., 2015]

20. J. Choisnard, G. Lafrance, M. Bernier. 2004. SAR-satellite for offshore and coastal wind resource analysis, with examples from St. Lawrence Gulf, Canada. Wind Eng., 28: 367-382. 10.1260/0309524042886432 [Choisnard et al., 2004]

21. M.B. Christiansen, C.B. Hasager. 2005. Wake effects of large offshore wind farms identified from satellite SAR. Remote Sens. Environ., 98. 10.1016/j.rse.2005.07.009 [Christiansen and Hasager, 2005]

22. M.B. Christiansen, C.B. Hasager. 2006. Using airborne and satellite SAR for wake mapping offshore. Wind Energy, 9: 437-455. 10.1002/we.196 [Christiansen and Hasager, 2006]

23. M.B. Christiansen, W. Koch, J. Horstmann, C.B. Hasager, M. Nielsen. 2006. Wind resource assessment from C-band SAR. Remote Sens. Environ., 105: 68-81. 10.1016/j.rse.2006.06.005 [Christiansen et al., 2006]

24. Copernicus. 2025. https://www.copernicus.eu/en. (last access November 2025) [Copernicus, 2025]

25. K.-F. Dagestad, J. Horstmann, A. Mouche, W. Perrie, H. Shen, B. Zhang, X. Li, F. Monaldo, W. Pichel, S. Lehner, M. Badger, C.B. Hasager, B. Furevik, R.C. Foster, S. Falchetti, M. Caruso, P. Vachon. 2012. Wind retrieval from synthetic aperture radar - an overview. Proceedings of SEASAR 2012 Advances in SAR Oceanography, (Tromsø Norway) [Dagestad et al., 2012]

26. N.N. Davis, J. Badger, A.N. Hahmann, B.O. Hansen, N.G. Mortensen, M. Kelly, X.G. Larsén, B.T. Olsen, R. Floors, G. Lizcano, P. Casso, O. Lacave, A. Bosch, I. Bauwens, O.J. Knight, A.P.V. Loon, R. Fox, T. Parvanyan, S.B.K. Hansen, R. Drummond. 2023. The global wind atlas: a high-resolution dataset of climatologies and associated web-based application. Bull. Am. Meteorol. Soc., 104: E1507-E1525. 10.1175/bams-d-21-0075.1 [Davis et al., 2023]

27. O.L.F. de Carvalho, O.A. de Carvalho Júnior, A.O. de Albuquerque, D.G. e Silva. 2023. Offshore Wind Plant Instance Segmentation Using Sentinel-1 Time Series, GIS, and Semantic Segmentation Models. 10.48550/arxiv.2312.08773 [de Carvalho et al., 2023]

28. J. de Kloe, A. Stoffelen, A. Verhoef. 2017. Improved use of scatterometer measurements by using stress-equivalent reference winds. IEEE J. Sel. Top. Appl. Earth Observ. Remote Sens., 10: 2340-2347. 10.1109/jstars.2017.2685242 [de Kloe et al., 2017]

29. L. de Montera, T. Remmers, R. O'Connell, C. Desmond. 2020. Validation of Sentinel-1 offshore winds and average wind power estimation around Ireland. Wind Energ. Sci., 5: 1023-1036. 10.5194/wes-5-1023-2020 [de Montera et al., 2020]

30. L. de Montera, H. Berger, R. Husson, P. Appelghem, L. Guerlou, M. Fragoso. 2022. High-resolution offshore wind resource assessment at turbine hub height with Sentinel-1 synthetic aperture radar (SAR) data and machine learning. Wind Energ. Sci., 7: 1441-1453. 10.5194/wes-7-1441-2022 [de Montera et al., 2022]

31. K. Dimitriadou, B.T. Olsen, M. Badger, C.B. Hasager. 2025. Sar offshore wind fields in the Gulf of Lion. J. Appl. Meteorol. Climatol.: 353-364. 10.1175/jamc-d-24-0156.1 [Dimitriadou et al., 2025]

32. Q. Ding, B. Tian, C. Chen, Y. Hu, X. Li. 2024. Identifying the spatio-temporal distribution characteristics of offshore wind turbines in China from Sentinel-1 imagery using deep learning. Gisci. Rem. Sens., 61. 10.1080/15481603.2024.2407389 [Ding et al., 2024]

33. B. Djath, J. Schulz-Stellenfleth. 2019. Wind speed deficits downstream offshore wind parks – a new automised estimation technique based on satellite synthetic aperture radar data. Meteorol. Z., 28: 499-515. 10.1127/metz/2019/0992 [Djath and Schulz-Stellenfleth, 2019]

34. B. Djath, J. Schulz-Stellenfleth, B. Cañadillas. 2018. Impact of atmospheric stability on X-band and C-band synthetic aperture radar imagery of offshore Windpark wakes. J. Renew. Sustain. Energy, 10. 10.1063/1.5020437 [Djath et al., 2018]

35. DNV. 2024. Energy Transition Outlook 2024. A Global and Regional Forecast to 2025: 261. https://www.dnv.com/energy-transition-outlook/ [DNV, 2024]

36. P. Doubrawa, R.J. Barthelmie, S.C. Pryor, C.B. Hasager, M. Badger, I. Karagali. 2015. Satellite winds as a tool for offshore wind resource assessment: the Great Lakes Wind Atlas. Remote Sens. Environ., 168. 10.1016/j.rse.2015.07.008 [Doubrawa et al., 2015]

37. ESAWAII. 2025. https://www.eotdl.com/datasets/ESAWAAI. (latest access November 2025) [ESAWAII, 2025]

38. F. Fetterer, D. Gineris, C.C. Wackerman. 1998. Validating a scatterometer wind algorithm for ERS-1 SAR. IEEE Trans. Geosci. Remote Sens., 36: 479-492. 10.1109/36.662731 [Fetterer et al., 1998]

39. R.G. Frehlich, R. Sharman. 2008. The use of structure functions and spectra from numerical model output to determine effective model resolution. Mon. Weather Rev., 136: 1537-1553. 10.1175/2007mwr2250.1 [Frehlich and Sharman, 2008]

40. B.R. Furevik, H.A. Espedal. 2002. Wind energy mapping using synthetic aperture radar. Can. J. Remote. Sens., 28: 196-204. 10.5589/m02-024 [Furevik and Espedal, 2002]

41. T.W. Gerling. 1986. Structure of the surface wind field from the SEASAT SAR. J. Geophys. Res., 91: 2308-2320. 10.1029/jc091ic02p02308 [Gerling, 1986]

42. T. Göçmen, P. van der Laan, P.-E. Réthoré, A. Peña, G.C. Larsen, S. Ott. 2016. Wind turbine wake models developed at the Technical University of Denmark: a review. Renew. Sust. Energ. Rev., 60: 752-769. 10.1016/j.rser.2016.01.113 [Göçmen et al., 2016]

43. J. Gottschall, B. Gribben, D. Stein, I. Würth. 2017. Floating lidar as an advanced offshore wind speed measurement technique: current technology status and gap analysis in regard to full maturity. WIREs Energy Environ., 6. 10.1002/wene.250 [Gottschall et al., 2017]

44. GWEC. 2024. Global Wind Energy Council, Global Offshore Wind Report 2024. https://www.gwec.net/reports [GWEC, 2024]

45. S. Hadjipetrou, S. Liodakis, A. Sykioti, L. Katikas, N.W. Park, S. Kalogirou, E. Akylas, P. Kyriakidis. 2022. Evaluating the suitability of Sentinel-1 SAR data for offshore wind resource assessment around Cyprus. Renew. Energy, 182: 1228-1239. 10.1016/j.renene.2021.10.100 [Hadjipetrou et al., 2022]

46. A.N. Hahmann, C.L. Vincent, A. Peña, J. Lange, C.B. Hasager. 2015. Wind climate estimation using WRF model output: method and model sensitivities over the sea. Int. J. Climatol., 35: 3422-3439. 10.1002/joc.4217 [Hahmann et al., 2015]

47. C.B. Hasager, H.P. Frank, B.R. Furevik. 2002. On offshore wind energy mapping using satellite SAR. Can. J. Remote. Sens., 28: 80-89. 10.5589/m02-008 [Hasager et al., 2002]

48. C.B. Hasager, R.J. Barthelmie, M.B. Christiansen, M. Nielsen, S.C. Pryor. 2006. Quantifying offshore wind resources from satellite wind maps: study area, the North Sea. Wind Energy, 9: 63-74. 10.1002/we.190 [Hasager et al., 2006]

49. C.B. Hasager, A. Peña, M.B. Christiansen, P. Astrup, M. Nielsen, F.M. Monaldo, D. Thompson. 2008. Remote sensing observation used in offshore wind energy. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 1: 67-79. 10.1109/jstars.2008.2002218 [Hasager et al., 2008]

50. C.B. Hasager, M. Badger, A. Peña, X.G. Larsén, F. Bingöl. 2011. SAR-based wind resource statistics in the Baltic Sea. Remote Sens., 3. 10.3390/rs3010117 [Hasager et al., 2011]

51. C.B. Hasager, M. Badger, N. Nawri, B.R. Furevik, G.N. Petersen, H. Bjornsson, N.-E. Clausen. 2015. Mapping offshore winds around Iceland using satellite synthetic aperture radar and mesoscale model simulations. IEEE J. Sel. Top. Appl. Earth Observ. Remote Sens., 8. 10.1109/jstars.2015.2443981 [Hasager et al., 2015a]

52. C.B. Hasager, A. Mouche, M. Badger, F. Bingöl, I. Karagali, T. Driesenaar, A. Stoffelen, A. Peña, N. Longépé. 2015. Offshore wind climatology based on synergetic use of Envisat ASAR, ASCAT and QuikSCAT. Remote Sens. Environ., 156: 247-263. 10.1016/j.rse.2014.09.030 [Hasager et al., 2015b]

53. C.B. Hasager, P. Vincent, J. Badger, M. Di Badger, A. Bella, A. Peña, R. Husson, P. Volker. 2015. Using satellite SAR to characterize the wind flow around offshore wind farms. Energies, 8: 5413-5439. 10.3390/en8065413 [Hasager et al., 2015c]

54. C.B. Hasager, A.N. Hahmann, T. Ahsbahs, I. Karagali, T. Sile, M. Badger, J. Mann. 2020. Europe’s offshore winds assessed with synthetic aperture radar, ASCAT and WRF. Wind Energ. Sci., 5: 375-390. 10.5194/wes-5-375-2020 [Hasager et al., 2020]

55. C.B. Hasager, J. Imber, J. Fischereit, A. Fujita, K. Dimitriadou, M. Badger. 2024. Wind speed-up in wind farm wakes quantified from satellite SAR and mesoscale modeling. Wind Energy. 10.1002/we.2943 [Hasager et al., 2024]

56. D. Hatfield, C.B. Hasager, I. Karagali. 2023. Vertical extrapolation of advanced Scatterometer (ASCAT) ocean surface winds using machine-learning techniques. Wind Energy Sci., 8: 621-637. 10.5194/wes-8-621-2023 [Hatfield et al., 2023]

57. H. Heiberg-Andersen, H.Y. Hindberg, J.H. Mæland, H. Johnsen. 2022. Comparison of simulated offshore wind farm wakes and SAR images. Int. J. Offshore Polar, 32: 81-86. 10.17736/ijope.2022.aj11 [Heiberg-Andersen et al., 2022]

58. H. Hersbach. 2010. Comparison of C-band Scatterometer CMOD5.N equivalent neutral winds with ECMWF. J. Atmos. Ocean. Technol., 27: 721-736. 10.1175/2009jtecho698.1 [Hersbach, 2010]

59. H. Hersbach, A. Stoffelen, S. de Haan. 2007. An improved C-band scatterometer ocean geophysical model function: CMOD5. J. Geophys. Res., 112. 10.1029/2006jc003743 [Hersbach et al., 2007]

60. T. Hoeser, S. Feuerstein, C. Kuenzer. 2022. DeepOWT: a global offshore wind turbine data set derived with deep learning from Sentinel-1 data. Earth Syst. Sci. Data, 14: 4251-4270. 10.5194/essd-14-4251-2022 [Hoeser et al., 2022]

61. IEA World Energy Outlook. 2024. https://www.iea.org/reports/world-energy-outlook-2024 [IEA World Energy Outlook, 2024]

62. IRENA World Energy Transition Outlook. 2024. https://www.irena.org/Publications/2024/Nov/World-Energy-Transitions-Outlook-2024 [IRENA World Energy Transition Outlook, 2024]

63. S. Jacobsen, S. Lehner, J. Hieronimus, J. Schneemann, M. Kühn. 2017. Joint offshore wind field monitoring with spaceborne Sar and platform-based doppler lidar measurements. ISPRS Int. Arch. Photogramm. Remote. Sens. Spat. Inf. Sci., 2015(7): 959-966. 10.5194/isprsarchives-xl-7-w3-959-2015 [Jacobsen et al., 2017a]

64. S. Jacobsen, A. Pleskachevsky, S. Singha, A. Frost, D. Velotto. 2017. SAR-based wind fields over offshore wind farms — A valuable tool for planning, monitoring and optimization. IEEE International Geoscience and Remote Sensing Symposium (IGARSS), Fort Worth, TX, USA: 1611-1613. 10.1109/igarss.2017.8127281 [Jacobsen et al., 2017b]

65. S.F. James. 2017. Using Sentinel-1 SAR satellites to map wind speed variation across offshore wind farm clusters. J. Phys. Conf. Ser., 926. 10.1088/1742-6596/926/1/012004 [James, 2017]

66. J.-C. Jang, K.-A. Park, A.A. Mouche, B. Chapron, J.-H. Lee. 2019. Validation of sea surface wind from sentinel-1A/B SAR data in the coastal regions of the Korean peninsula. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 12: 2513-2529. 10.1109/jstars.2019.2911127 [Jang et al., 2019]

67. O.M. Johannessen, E. Bjorgo. 2000. Cover. Wind energy mapping of coastal zones by synthetic aperture radar (SAR) for siting potential windmill locations. Int. J. Remote Sens., 21: 1781-1786. 10.1080/014311600209733 [Johannessen and Bjorgo, 2000]

68. I. Karagali, X. Larsén, M. Badger, A. Peña, C. Hasager. 2013. Spectral properties of ENVISAT ASAR and QuikSCAT surface winds in the North Sea. Remote Sens., 5: 6096-6115. 10.3390/rs5116096 [Karagali et al., 2013]

69. T. Katona, A. Bartsch. 2018. Estimation of wind speed over lakes in Central Europe using spaceborne C-band SAR. Euro. J. Rem. Sens., 51: 921-931. 10.1080/22797254.2018.1516516 [Katona and Bartsch, 2018]

70. E. Khachatrian, P. Asemann, L. Zhou, Y. Birkelund, I. Esau, B. Ricaud. 2024. Exploring the potential of Sentinel-1 ocean wind field product for near-surface offshore wind assessment in the Norwegian Arctic. Atmosphere, 15: 146. 10.3390/atmos15020146 [Khachatrian et al., 2024]

71. S. Khan, I. Young, A. Ribal, M. Hemar. 2023. High-resolution calibrated and validated synthetic aperture Radar Ocean surface wind data around Australia. Sci. Data, 10: 163. 10.1038/s41597-023-02046-w [Khan et al., 2023]

72. H.-G. Kim, H.-J. Hwang, S.-W. Lee, H.-W. Lee. 2014. Evaluation of SAR wind retrieval algorithms in offshore areas of the Korean peninsula. Renew. Energy, 65: 161-168. 10.1016/j.renene.2013.08.013 [Kim et al., 2014]

73. W. Koch. 2004. Directional analysis of SAR images aiming at wind direction. IEEE Trans. Geosci. Remote Sens., 42: 702-710. 10.1109/tgrs.2003.818811 [Koch, 2004]

74. V. La, A. Khenchaf, F. Comblet, C. Nahum. 2017. Exploitation of C-band Sentinel-1 images for high-resolution wind field retrieval in coastal zones (Iroise coast, France). IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 10: 5458-5471. 10.1109/jstars.2017.2746349 [La et al., 2017]

75. L. Landberg. 2015. Meteorology for Wind Energy: An Introduction. John Wiley and Sons: 224 [Landberg, 2015]

76. X.G. Larsén, J. Fischereit. 2021. A case study of wind farm effects using two wake parameterizations in the weather research and forecasting (WRF) model (V3.7.1) in the presence of low-level jets. Geosci. Model Dev., 14, 5: 3141-3158. 10.5194/gmd-14-3141-2021 [Larsén and Fischereit, 2021]

77. X. Li, S. Lehner. 2013. Observation of TerraSAR-X for studies on offshore wind turbine wake in near and far fields. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 5: 1757-1768. 10.1109/jstars.2013.2263577 [Li and Lehner, 2013]

78. D. Li, P. Yu, W. Yang, Y. He. 2021. SAR-based wind resource assessment near the coast of Fujian. Proceedings of the 2021 4th International Conference on Computing And Big Data. 10.1145/3507524.3507532 [Li et al., 2021]

79. Y. Lu, B. Zhang, W. Perrie, A. Mouche, X. Li, H. Wang. 2018. A C-band geophysical model function for determining coastal wind speed using synthetic aperture radar. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 11: 2417-2428. 10.1109/jstars.2018.2836661 [Lu et al., 2018]

80. P. Ma, M. Macdonald, S. Rouse, J. Ren. 2024. Automatic geolocation and measuring of offshore energy infrastructure with multimodal satellite data. IEEE J. Ocean. Eng., 49: 66-79. 10.1109/joe.2023.3319741 [Ma et al., 2024]

81. M. Majidi Nezhad, D. Groppi, P. Marzialetti, L. Fusilli, G. Laneve, F. Cumo, D. Astiaso Garcia. 2019. Wind energy potential analysis using Sentinel-1 satellite: a review and a case study on Mediterranean islands. Renew. Sust. Energ. Rev., 109: 499-513. 10.1016/j.rser.2019.04.059 [Majidi Nezhad et al., 2019]

82. M. Majidi Nezhad, A. Heydari, D. Groppi, F. Astiaso Cumo, D. Garcia. 2020. Wind source potential assessment using sentinel 1 satellite and a new forecasting model based on machine learning: a case study Sardinia islands. Renew. Energy, 155: 212-222. 10.1016/j.renene.2020.03.148 [Majidi Nezhad et al., 2020]

83. M. Majidi Nezhad, M. Neshat, A. Heydari, A. Razmjoo, G. Astiaso Piras, D. Garcia. 2021. A new methodology for offshore wind speed assessment integrating Sentinel-1, ERA-interim and in-situ measurement. Renew. Energy, 172: 1301-1313. 10.1016/j.renene.2021.03.026 [Majidi Nezhad et al., 2021]

84. F.M. Monaldo, D.R. Thompson, R.C. Beal, W.G. Pichel, P. Clemente-Colón. 2001. Comparison of SAR-derived wind speed with model predictions and ocean buoy measurements. IEEE Trans. Geosci. Remote Sens., 39: 2587-2600. 10.1109/36.974994 [Monaldo et al., 2001]

85. F.M. Monaldo, X. Li, W.G. Pichel, C.R. Jackson. 2014. Ocean wind speed climatology from spaceborne SAR imagery. Bull. Am. Meteorol. Soc., 95: 565-569. 10.1175/bams-d-12-00165.1 [Monaldo et al., 2014]

86. F.M. Monaldo, C. Jackson, X. Li. 2015. A weather eye on coastal winds. Eos, 96: 16-19 [Monaldo et al., 2015]

87. F.M. Monaldo, C. Jackson, X. Li, W.G. Pichel. 2016. Preliminary evaluation of sentinel-1A wind speed retrievals. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 9: 2638-2642. 10.1109/jstars.2015.2504324 [Monaldo et al., 2016]

88. A.A. Mouche, B. Chapron. 2015. Global C-band Envisat, RADARSAT-2 and Sentinel-1 SAR measurements in copolarization and cross-polarization. J. Geophys. Res. Oceans, 120: 7195-7207. 10.1002/2015jc011149 [Mouche and Chapron, 2015]

89. A.A. Mouche, P. Vincent. 2011. Sentinel-1 Ocean Wind Fields (OWI) Algorithm Definition (2011). https://sentinel.esa.int/documents/247904/3861173/Sentinel-1-Ocean-Wind-Fields-OWI-ATBD.pdf [Mouche and Vincent, 2011]

90. A.A. Mouche, B. Chapron, B. Zhang, R. Husson. 2017. Combined co- and cross-polarized SAR measurements under extreme wind conditions. IEEE Trans. Geosci. Remote Sens., 55: 6476-6755. 10.1109/tgrs.2017.2732508 [Mouche et al., 2017]

91. N.G. Nygaard, S.D. Hansen. 2016. Wake effects between two neighbouring wind farms. J. Phys. Conf. Ser., 753. 10.1088/1742-6596/753/3/032020 [Nygaard and Hansen, 2016]

92. N.G. Nygaard, A.C. Newcombe. 2018. Wake behind an offshore wind farm observed with dual-Doppler radars. J. Phys. Conf. Ser., 1037. 10.1088/1742-6596/1037/7/072008 [Nygaard and Newcombe, 2018]

93. M. Optis, N. Bodini, M. Debnath, P. Doubrawa. 2021. New methods to improve the vertical extrapolation of near-surface offshore wind speeds. Wind Energ. Sci., 6: 935-948. 10.5194/wes-6-935-2021 [Optis et al., 2021]

94. A. Owda, M. Badger. 2022. Wind speed variation mapped using SAR before and after commissioning of offshore wind farms. Remote Sens., 14: 1464. 10.3390/rs14061464 [Owda and Badger, 2022]

95. A. Owda, J. Dall, M. Badger, D. Cavar. 2023. Improving SAR wind retrieval through automatic anomalous pixel detection. Int. J. Appl. Earth Obs. Geoinf., 122: 103444. 10.1016/j.jag.2023.103444 [Owda et al., 2023]

96. A. Peña, A.N. Hahmann. 2012. Atmospheric stability and turbulence fluxes at horns rev—an intercomparison of sonic, bulk and WRF model data. Wind Energy, 15: 717-731. 10.1002/we.500 [Peña and Hahmann, 2012]

97. A. Platis, J. Bange, K. Bärfuss, B. Cañadillas, M. Hundhausen, B. Djath, A. Lampert, J. Schulz-Stellenfleth, S. Siedersleben, T. Neumann, S. Emeis. 2020. Long-range modifications of the wind field by offshore wind parks results of the project WIPAFF. Meteorol. Z., 11: 355-376. 10.1127/metz/2020/1023 [Platis et al., 2020]

98. Y. Quilfen, B. Chapron, T. Elfouhaily, K. Katsaros, J. Tournadre. 1998. Observation of tropical cyclones by high-resolution scatterometry. J. Geophys. Res., 103: 7767-7786. 10.1029/97jc01911 [Quilfen et al., 1998]

99. N. Radkani, B.G. Zakeri. 2020. Southern Caspian Sea wind speed retrieval from C-band sentinel-1A SAR images. Int. J. Remote Sens., 41: 3511-3534. 10.1080/01431161.2019.1706201 [Radkani and Zakeri, 2020]

100. F.M. Rana, M. Adamo, G. Pasquariello, G. De Carolis, S. Morelli. 2016. LG-mod: a modified local gradient (LG) method to retrieve SAR Sea surface wind directions in marine coastal areas. J. Sens.: 9565208. 10.1155/2016/9565208 [Rana et al., 2016]

101. F.M. Rana, M. Adamo, R. Lucas, P. Blonda. 2019. Sea surface wind retrieval in coastal areas by means of Sentinel-1 and numerical weather prediction model data. Remote Sens. Environ., 225: 379-391. 10.1016/j.rse.2019.03.019 [Rana et al., 2019]

102. SATWINDS. 2025. Technical University of Denmark. Science Global Wind Atlas: Satellite-Derived Near-Real-Time Offshore Wind Fields. https://science.globalwindatlas.info/#/map/satwinds. (last access November 2025) [SATWINDS, 2025]

103. J. Schneemann, A. Rott, M. Dörenkämper, G. Steinfeld, M. Kühn. 2020. Cluster wakes impact on a far-distant offshore wind farm's power. Wind Energ. Sci., 5: 29-49. 10.5194/wes-5-29-2020 [Schneemann et al., 2020]

104. T. Schneiderhan, S. Lehner, J. Schulz-Stellenfleth, J. Horstmann. 2005. Comparison of offshore wind park sites using SAR wind measurement techniques. Meteorol. Appl., 12: 101-110. 10.1017/s1350482705001659 [Schneiderhan et al., 2005]

105. M. Schwerdt, K. Schmidt, N.T. Ramon, G.C. Alfonzo, B.J. Döring, M. Zink, P. Prats-Iraola. 2016. Independent verification of the sentinel-1A system calibration. IEEE J. Sel. Top. Appl. Earth Obs. Remote Sens., 9. 10.1109/jstars.2015.2449239 [Schwerdt et al., 2016]

106. W.J. Shaw, L.K. Berg, M. Debnath, G. Deskos, C. Draxl, V.P. Ghate, C.B. Hasager, R. Kotamarthi, J.D. Mirocha, P. Muradyan, W.J. Pringle, D.D. Turner, J.M. Wilczak. 2022. Scientific challenges to characterizing the wind resource in the marine atmospheric boundary layer. Wind Energy Sci., 7: 2307-2334. 10.5194/wes-7-2307-2022 [Shaw et al., 2022]

107. W. Shiyan, Y. Sheng, X. Dewei. 2020. On accuracy of SAR wind speed retrieval in coastal area. Appl. Ocean Res., 95: 102012. 10.1016/j.apor.2019.102012 [Shiyan et al., 2020]

108. SNAP. 2025. https://earth.esa.int/eogateway/tools/snap. (last accessed November 2025) [SNAP, 2025]

109. A. Stoffelen, D.L.T. Anderson. 1997. Scatterometer data interpretation: estimation and validation of the transfer function CMOD4. J. Geophys. Res., 102: 5767-5780. 10.1029/96jc02860 [Stoffelen and Anderson, 1997]

110. A. Stoffelen, J.A. Verspeek, J. Vogelzang, A. Verhoef. 2017. The CMOD7 geophysical model function for ASCAT and ERS wind retrievals. IEEE J. Sel. Top. Appl. Earth Observ. Remote Sens., 10: 2123-2134. 10.1109/jstars.2017.2681806 [Stoffelen et al., 2017]

111. Y. Takeyama, T. Ohsawa, K. Kozai, C.B. Hasager, M. Badger. 2013. Comparison of geophysical model functions for SAR wind speed retrieval in Japanese coastal waters. Remote Sens., 5: 1956-1973. 10.3390/rs5041956 [Takeyama et al., 2013]

112. D. Thompson, T. Elfouhaily, B. Chapron. 1998. Polarization ratio for microwave backscattering from the ocean surface at low to moderate incidence angles. Proc. Int. Geoscience and Remote Sensing Symp., Seattle, WA: 1671-1673. 10.1109/igarss.1998.692411 [Thompson et al., 1998]

113. I. Troen, E.L. Petersen. 1989. European Wind Atlas. Risø National Laboratory, Roskilde, Denmark. https://orbit.dtu.dk/en/publications/european-wind-atlas [Troen and Petersen, 1989]

114. S. Tuy, H.S. Lee, K. Chreng. 2022. Integrated assessment of offshore wind power potential using weather research and forecast (WRF) downscaling with Sentinel-1 satellite imagery, optimal sites, annual energy production and equivalent CO2 reduction. Renew. Sust. Energ. Rev., 163: 112501. 10.1016/j.rser.2022.112501 [Tuy et al., 2022]

115. US DoE Departement of Energy Offshore Wind Market Report: 2023 2023. Edition Offshore Wind Powering Up https://www.energy.gov/eere/wind/articles/offshore-wind-market-report-2023-edition#:∼:text=Offshore%20Wind%20Powering%20Up ,over%2011%2C900%20operating%20wind%20turbines. [US DoE Departement of Energy Offshore Wind Market Report: 2023, 2023]

116. P.W. Vachon, F.W. Dobson. 2000. Wind retrieval from RADARSAT SAR images: selection of a suitable C-band HH polarization wind retrieval model. Can. J. Remote. Sens., 26: 306-313. 10.1080/07038992.2000.10874781 [Vachon and Dobson, 2000]

117. B.J. Vanderwende, B. Kosović, J.K. Lundquist, J.D. Mirocha. 2016. Simulating effects of a wind-turbine array using LES and RANS. J. Adv. Model. Earth Syst., 8: 1376-1390. 10.1002/2016ms000652 [Vanderwende et al., 2016]

118. P. Veers, K. Dykes, S. Basu, A. Bianchini, A. Clifton, P. Green, H. Holttinen, L. Kitzing, B. Kosovic, J.K. Lundquist, J. Meyers, M. O’Malley, W.J. Shaw, B. Straw. 2022. Grand challenges: wind energy research needs for a global energy transition. Wind Energy Sci., 7: 2491-2496. 10.5194/wes-7-2491-2022 [Veers et al., 2022]

119. WWEA World Wind Energy Association https://www.wwindea.org/ (last access November 2025). [WWEA, 2025]

120. D. Yang, C. Meneveau, L. Shen. 2014. Large-eddy simulation of offshore wind farm. Phys. Fluids, 26: 025101. 10.1063/1.4863096 [Yang et al., 2014]

121. P. Yu, W. Xu, X. Zhong, J.A. Johannessen, X.-H. Yan, X. Geng, Y. He, W. Lu. 2022. A neural network method for retrieving sea surface wind speed for C-band SAR. Remote Sens., 14: 2269. 10.3390/rs14092269 [Yu et al., 2022]

122. S. Zecchetto, A. Zanchetta. 2022. Structure of high-resolution SAR winds over the Venice lagoon area. IEEE Trans. Geosci. Remote Sens., 60: 1-9. 10.1109/tgrs.2022.3170705 [Zecchetto and Zanchetta, 2022]

123. K. Zhang, J. Huang, X. Xu, Q. Guo, Y. Chen, L. Mansaray, Z. Li, X. Wang. 2018. Spatial scale effect on wind speed retrieval accuracy using Sentinel-1 copolarization SAR. IEEE Geosci. Remote Sens. Lett., 15: 882-886. 10.1109/lgrs.2018.2811397 [Zhang et al., 2018]

124. B. Zhang, A. Mouche, Y. Lu, W. Perrie, G. Zhang, H. Wang. 2019. A geophysical model function for wind speed retrieval from C-band HH-polarized synthetic aperture radar. IEEE Geosci. Remote Sens. Lett., 16: 1521-1525. 10.1109/lgrs.2019.2905578 [Zhang et al., 2019]

125. T. Zhang, B. Tian, D. Sengupta, L. Zhang, Y. Si. 2021. Global offshore wind turbine dataset. Sci. Data, 8: 191. 10.1038/s41597-021-00982-z [Zhang et al., 2021]

126. C.B. Hasager, M. Nielsen, P. Astrup, R. Barthelmie, E. Dellwik, N.O. Jensen, B.H. Jørgensen, S.C. Pryor, O. Rathmann, B.R. Furevik. 2005. Offshore wind resource estimation from satellite SAR wind field maps. Wind Energ., 8: 403-419. 10.1002/we.150 [Hasager et al., 2005]
