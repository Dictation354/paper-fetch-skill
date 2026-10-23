---
title: "Embedding machine-learnt sub-grid variability improves climate model precipitation patterns"
authors: "Daniel Giles, James Briant, Cyril J. Morcrette, Serge Guillas"
journal: "Communications Earth & Environment"
doi: "10.1038/s43247-024-01885-8"
published: "2024/11/18"
source: "springer_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 12380
---

# Embedding machine-learnt sub-grid variability improves climate model precipitation patterns

## Abstract

Parameterisation schemes within General Circulation Models are required to capture cloud processes and precipitation formation but exhibit long-standing known biases. Here, we develop a hybrid approach that tackles these biases by embedding a Multi-Output Gaussian Process trained to predict high resolution variability within each climate model grid box. The trained multi-output Gaussian Process model is coupled in-situ with a simplified Atmospheric General Circulation Model named SPEEDY. The temperature and specific humidity profiles of SPEEDY are perturbed at fixed intervals according to the variability predicted from the Gaussian Process. Ten-year predictions are generated for both control and machine learning hybrid models. The hybrid model reduces the global precipitation area-weighted root-mean squared error by up to 17% and over the tropics by up to 20%. Hybrid techniques have been known to introduce non-physical states therefore physical quantities are explored to ensure that climatic drift is not observed. Furthermore, to understand the drivers of the precipitation improvements the changes to thermodynamic profiles and the distribution of lifted index values are investigated.

## Introduction

General Circulation Models (GCMs) play a vital role in our understanding of climate dynamics and how it is changing worldwide. The state-of-the-art GCMs are used to investigate the effects of different forcing pathways on the evolving climate and the simulation results have formed the key basis of the Intergovernmental Panel on Climate Change (IPPC) reports<sup>[1](https://www.nature.com/articles/s43247-024-01885-8#ref-CR1)</sup>. Despite the state-of-the-art GCMs being optimised to run on some of the largest high performance computing infrastructures, the need for long integration periods limits the spatial resolution afforded. Climate simulations are typically carried out using spatial resolutions of **O**(100 km), which is coarser than those used for global **O**(10 km) and regional **O**(1 km) weather forecasting. The afforded resolution of GCMs has contributed to some of their long standing biases, in particular biases associated with cloud formation, convection, precipitation and interactions between the water cycle and the large-scale dynamics. In contrast higher-resolution kilometre-scale atmospheric models are better at representing these atmospheric processes<sup>[2](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR2),[3](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR3),[4](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR4),[5](https://www.nature.com/articles/s43247-024-01885-8#ref-CR5)</sup>. Furthermore, there are now cloud- and storm-resolving GCMs being tested, but their temporal integration window is limited.

The size of a grid-box within a GCM defines the scales at which meteorological dynamics can be modelled. Indeed, only one value is used as the point estimate for each atmospheric variable in each grid-box. There are many atmospheric processes, such as radiative transfer, precipitation growth, cloud formation, and convective development that have an effect on the resolved scale, but that are modulated by interactions occurring on scales smaller than the grid. Parametrization schemes have been developed to represent these processes \[e.g. ref. <sup>[6](https://www.nature.com/articles/s43247-024-01885-8#ref-CR6)</sup>\]. Although many schemes include some representation of sub-grid variability in calculating how a given atmospheric process will modify the thermodynamic state of the column, the inputs to the schemes consist of the vertical profiles of variables representing a horizontal mean over the size of the grid-box \[e.g. refs. <sup>[7](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR7),[8](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR8),[9](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR9),[10](https://www.nature.com/articles/s43247-024-01885-8#ref-CR10)</sup>\]. Our approach builds upon these methods by explicitly capturing the sub-grid variability.

Improving the known biases in climate model simulations is an area of ongoing research with extensive efforts placed on improving parameterization schemes, introducing stochastic components, pushing the resolution envelop by leveraging the latest in high-performance computing and/or by integrating data-driven approaches in a hybrid mode \[e.g. refs. <sup>[11](https://www.nature.com/articles/s43247-024-01885-8#ref-CR11),[12](https://www.nature.com/articles/s43247-024-01885-8#ref-CR12)</sup>\]. As our work focuses on the hybrid climate modelling set up, relevant work is presented here. Beucler er al.<sup>[13](https://www.nature.com/articles/s43247-024-01885-8#ref-CR13)</sup> provides a recent overview of machine learning methods being developed for cloud and climate modelling applications. Brenowitz and Bretherton<sup>[14](https://www.nature.com/articles/s43247-024-01885-8#ref-CR14),[15](https://www.nature.com/articles/s43247-024-01885-8#ref-CR15)</sup> used kilometre-scale aqua-planet simulations, and the spatial averaging of their data to the scale of a climate model grid-box, to infer the temperature and humidity tendencies that would need to be added to the coarse model to make it behave more like the high resolution one. They used machine learning techniques to predict the corrections and then coupled these to their global model leading to notable improvements in its fidelity. This work was extended by Bretherton et al.<sup>[16](https://www.nature.com/articles/s43247-024-01885-8#ref-CR16)</sup> using more realistic high-resolution simulations, that included land and orography, but for up to 40 days ahead forecasts, not climate simulations. Shamekh et al.<sup>[17](https://www.nature.com/articles/s43247-024-01885-8#ref-CR17)</sup> captured sub-grid cell cloud structure and organisation by training a neural network which is informed by an organisation metric to predict the parameterised coarse-grained precipitation. This results in an improved prediction skill of precipitation statistics and extremes in a coarse climate model. Arcomano et al.<sup>[18](https://www.nature.com/articles/s43247-024-01885-8#ref-CR18),[19](https://www.nature.com/articles/s43247-024-01885-8#ref-CR19)</sup> coupled a low resolution GCM with a reservoir computing machine learning model, which improved systematic errors and enabled the low-resolution climate model to produce a realistic El Niño-Southern Oscillation signal. Kochkov et al.<sup>[20](https://www.nature.com/articles/s43247-024-01885-8#ref-CR20)</sup> have consolidated and built upon these hybrid approaches by developing an atmospheric GCM which enables the integration of machine-learned parameterisation schemes within an auto-differential dynamical core. They showcase stable long-term climate simulations with bias reductions when compared to state-of-the-art models.

This study explores the use of coarse-grained high-resolution simulations and machine learning to improve the fidelity of a coarse-resolution climate model. Differing from refs. <sup>[14](https://www.nature.com/articles/s43247-024-01885-8#ref-CR14),[15](https://www.nature.com/articles/s43247-024-01885-8#ref-CR15)</sup>, the high-resolution simulation data is not used here to infer and learn a thermodynamic tendency that is applied to the coarse model. Instead, an alternative approach to stochastic parametrization is explored: rather than perturbing the temperature (*T*) and specific humidity (*Q*) tendencies coming out of a parametrization scheme \[e.g. refs. <sup>[21](https://www.nature.com/articles/s43247-024-01885-8#ref-CR21),[22](https://www.nature.com/articles/s43247-024-01885-8#ref-CR22)</sup>\] or perturbing uncertain parameters within a certain scheme \[e.g. refs. <sup>[23](https://www.nature.com/articles/s43247-024-01885-8#ref-CR23),[24](https://www.nature.com/articles/s43247-024-01885-8#ref-CR24)</sup>\], the high-resolution data is used as training data to quantify the temperature and humidity variability that occurs on scales smaller than the coarse-model grid and the thermodynamic profiles are perturbed within that predicted envelope. A Multi-Output Gaussian Process (MOGP) is used to predict the profiles of temperature and humidity variability. Key benefits of MOGP models over traditional neural network based approaches are: more stability when sampling outside of training distribution, fewer training samples and crucially the inherent uncertainty estimate<sup>[25](https://www.nature.com/articles/s43247-024-01885-8#ref-CR25)</sup>. The MOGP model is trained on coarse-grained high-resolution outputs from the UK Met Office’s Unified Model<sup>[26](https://www.nature.com/articles/s43247-024-01885-8#ref-CR26)</sup>. Eighty regional models, which sample the globe evenly, are used to run simulations for 10 days with a spatial resolution of 1.5 km<sup>[27](https://www.nature.com/articles/s43247-024-01885-8#ref-CR27)</sup>. Details on the high-resolution model runs and the coarse-graining procedures are outlined in Section “Data generation, coarse-graining and training design”. Further, validation results of the trained MOGP are outlined in Section “MOGP”. Figure [1](https://www.nature.com/articles/s43247-024-01885-8#Fig1) showcases the patterns of variation that the trained MOGP model predicts in the temperature and specific humidity fields at 925 hPa at two different time points which fall within the 10 year experimental window (00 UTC 1st January and 12 UTC 1st June 1987). For both time points, the MOGP predicts larger variability in temperature over land than the ocean and the effect of the seasons can be seen in the specific humidity variability estimates. Synoptic wave patterns can also be seen for both variables. It should be noted that the MOGP model operates on a GCM column-by-column basis and therefore has not explicitly learned these spatial covariances but can clearly predict spatially coherent patterns that vary in time and space.

![Figure 1](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig1_HTML.png)

**Figure 1.** **Spatio-temporal predictions of temperature and specific humidity standard deviations.**

Examples of MOGP predictions of temperature and humidity standard deviation at 00 UTC 1 January and 12 UTC 1 June 1987 at 925 hPa.

In this work, the trained MOGP model is two-way coupled with a simplified GCM, SPEEDY. SPEEDY (Simplified Parameterizations primitivE-Equation DYnamics) is an atmospheric GCM which consists of a spectral primitive-equation dynamic core along with a set of simplified physical parametrization schemes<sup>[28](https://www.nature.com/articles/s43247-024-01885-8#ref-CR28)</sup> and is the same GCM used in the hybrid studies of Arcomano et al.<sup>[18](https://www.nature.com/articles/s43247-024-01885-8#ref-CR18),[19](https://www.nature.com/articles/s43247-024-01885-8#ref-CR19)</sup>. The prognostic variables are the zonal and meridional components of wind (*u*, *v*), temperature (*T*), specific humidity (*Q*) and surface pressure (*p*<sub><em>s</em></sub>). A T30 grid resolution is used yielding an approximate grid length of 333 km at the equator. The model has 8 vertical layers, defined by sigma levels, where the pressure is normalized by the surface pressure (*p*/*p*<sub><em>s</em></sub>). SPEEDY is used here to explore the feasibility and impact of two-way coupling of machine-learnt elements into a GCM in order to affect its dynamical evolution and provides motivation for extending this work within a fully-fledged GCM.

Details on the two-way coupling of SPEEDY with the trained MOGP can be found in Section “Two-way coupling of GCM and MOGP”. The resultant impact of this fusion of data-science techniques to represent sub-grid thermodynamic variability within a climate model is further explored here. To showcase the improvements of the proposed technique, the precipitation outputs from a 10-year hybrid and control simulation are compared to the satellite-derived monthly precipitation data from the Global Precipitation Climatology Project (GPCP)<sup>[29](https://www.nature.com/articles/s43247-024-01885-8#ref-CR29)</sup> (Section “Global mean precipitation over 10-year simulation (1982–1992)”). Details on the experimental set-up can be found in Section “Experimental set up”. The stability of the method, influence on climatic drift and physical justifications for the observed improvement in precipitation errors are explored in Section “Assessment of long-term drift and physical explanation for precipitation changes”. Finally, future directions and concluding remarks are outlined in Section “Discussion”.

## Results

### Data generation, coarse-graining and training design

The data used for training are generated using the Met Office Unified Model (MetUM). Global model hindcasts are run from analyses to produce initial and lateral boundary conditions for some limited-area models (LAMs). The global driving model uses the Global Atmosphere 6 package of physical parametrizations \[GA6<sup>[30](https://www.nature.com/articles/s43247-024-01885-8#ref-CR30)</sup>\], with gridboxes 0.09° × 0.14° in latitude and longitude, a configuration which has been used for operational global forecasting.

The LAMs use a regional configuration which has also been used for operational forecasting<sup>[31](https://www.nature.com/articles/s43247-024-01885-8#ref-CR31)</sup>. The LAMs have a horizontal gridsize of 1.5 km. The vertical level set is the same as the driving global model, consisting of 70 levels on a stretched grid, with a model top at 80 km and 50 of the levels located in the troposphere, below 20 km. The key difference between the LAMs and the driving model is that the LAMs are run without a convection scheme. This configuration has been shown to perform better than the coarser model, using a convective parametrization, when simulating convection over the United Kingdom<sup>[3](https://www.nature.com/articles/s43247-024-01885-8#ref-CR3)</sup> or over tropical western Africa<sup>[32](https://www.nature.com/articles/s43247-024-01885-8#ref-CR32)</sup>.

This combination of a global and regional versions of the MetUM is known to perform well when located in various regions around the world and has been used to investigate severe weather in New Zealand<sup>[33](https://www.nature.com/articles/s43247-024-01885-8#ref-CR33)</sup>, and convective systems over the continental United States and South Africa<sup>[34](https://www.nature.com/articles/s43247-024-01885-8#ref-CR34),[35](https://www.nature.com/articles/s43247-024-01885-8#ref-CR35)</sup>.

In this study, the nesting suite is extended to cope with 80 separate LAMs, each defined to be 512 × 512 grid-points in the horizontal with a grid-length of 1.5 km<sup>[27](https://www.nature.com/articles/s43247-024-01885-8#ref-CR27)</sup>. The locations of the 80 nested LAMs are shown by the black polygons in Fig. [2](https://www.nature.com/articles/s43247-024-01885-8#Fig2) and these were chosen to ensure an even distribution over the Earth’s sphere. For consistency, all the LAMs use the same Regional Atmosphere and Land configuration \[RAL1-T<sup>[31](https://www.nature.com/articles/s43247-024-01885-8#ref-CR31)</sup>\]. The global driving model is re-initialised every 24 h using 00Z operational MetUM atmospheric analyses and each of the 80 nests is free-running, with 3-hourly updated lateral boundary conditions, for 10 days covering the start of January 2020. Global daily sea surface temperatures are provided by the OSTIA system<sup>[36](https://www.nature.com/articles/s43247-024-01885-8#ref-CR36)</sup>. The LAM diagnostics are outputted 4 times per day (00, 06, 12 and 18 UTC).

![Figure 2](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig2_HTML.png)

**Figure 2.** **Nested limited-area models used to generate the training data.**

**a** Location of the 80 limited-area models (LAMs) across the globe. Each LAM is then split into a 2 × 2 array of patches where coarse-graining is performed. An average or a standard deviation can be calculated over these patches, as shown by the shading which, as an example, represents the standard deviation of near-surface temperature \[K\] at 00 UTC on 1 Jan 2020. Examples of the 1.5 km surface temperature data are shown for (**b**) the Arabian Sea and (**c**) Southern India and Sri Lanka, while examples of their standard deviation are shown in (**d**) and (**e**).

Within each 512 × 512 LAM, the outer 32 grid-points are treated as a spin-up region and ignored. The remaining 448 × 448 region is cut up into 4 patches each of 224 × 224 grid-points. With the LAM grid-size of 1.5 km, these are 336 km wide. The SPEEDY model has a latitude-longitude grid consisting of 48 × 96 points so that the square root of the mean grid-box area is 333 km. Therefore the grid-box sizes in SPEEDY are very similar in size to the LAM patches.

Temperature, specific humidity, and pressure data from each of the 4 patches, in each of the 80 LAMs, are processed to produce profiles at all available times (4 times per day for 10 days). This processing consists of calculating horizontal means and standard deviation at each height in the vertical. The sub-grid variability in temperature and humidity in the training data varies due to the local meteorology from place to place. As an example, the standard deviation of temperature for each patch at the model level nearest to the surface is shown by the shading in Fig. [2](https://www.nature.com/articles/s43247-024-01885-8#Fig2)a.

Figure [2](https://www.nature.com/articles/s43247-024-01885-8#Fig2)b–e provide examples of the high-resolution simulations that form the training data by focussing on the temperature at the model level nearest to the surface in two contrasting but nearby locations. Panel (b and d) are for the LAM in the Arabian Sea (located off the north-east coast of Somalia) while panels (c and e) are for the LAM covering southern India and parts of Sri Lanka. The colour shading in panels (b) and (c) shows the original high-resolution fields, and the squares (located 32 grid-boxes in from the lateral edges) indicate the patches over which the horizontal mean and standard deviations are calculated. Panels (d) and (e) showcase the standard deviation of the temperature calculated over the patches.

The data selected to train the MOGP are sampled using a design which enforces equal coverage globally. Dividing each of the 80 LAMs into 4 patches yields 320 patches in total. Each patch is sampled exactly twice randomly in time to form a training dataset of 640 vertical profiles. This approach ensures the training dataset is (i) evenly distributed spatially by exploiting the equidistant structure of the LAMs, (ii) evenly distributed temporally by sampling uniformly across time, (iii) and ensures every land-sea mask ratio that is available within the dataset is used to train the MOGP. The vertical profiles are sampled at sigma coordinates which correspond to the 8 levels defined in SPEEDY. Full details on the training and validation of the MOGP model can be found in Section “MOGP”.

### Global mean precipitation over 10-year simulation (1982–1992)

A 10-year simulation of the global atmosphere is carried out using both the SPEEDY control and hybrid (SPEEDY and MOGP) models. The 10-year period covers 1st January 1982 to 1st January 1992. The resultant mean precipitation is then compared to the precipitation data from the GPCP<sup>[29](https://www.nature.com/articles/s43247-024-01885-8#ref-CR29)</sup> for the same period. To ensure robustness in the results three independent hybrid simulations are carried out, details on the experimental set-up are outlined in Section “Experimental set up”. Figure [3](https://www.nature.com/articles/s43247-024-01885-8#Fig3) shows the 10-year mean precipitation from the SPEEDY control and one of the hybrid runs (randomly selected) (top row), note the reduction in the presence of the double Inter-Tropical Convergence Zone (ITCZ). The double ITCZ is a vexing problem in atmospheric GCM models where erroneous precipitation bands in the southern hemisphere are present.

![Figure 3](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig3_HTML.png)

**Figure 3.** **Precipitation comparisons.**

Top row: Maps of the 10 year mean precipitation for the SPEEDY control (left) and hybrid experiment (right). Middle row: Precipitation error for the SPEEDY control (left) and the hybrid experiment (right) versus GPCP data for the same period. The area weighted RMSE values are included in the titles. Bottom row: The difference in the absolute errors of the SPEEDY control and hybrid runs (left) and the difference in precipitation standard deviation (*σ*<sub>Hybrid</sub> − *σ*<sub>SPEEDY</sub>) (right).

Differences between the control and hybrid runs against the GPCP data are shown in the middle row. A 17% reduction in the global area-weighted root means squared error (RMSE) and a 19.9% reduction in the area-weighted RMSE within the tropics region (±23.5° latitude) are calculated for the time-mean over the 10-year simulation (Table [1](https://www.nature.com/articles/s43247-024-01885-8#Tab1)). Figure [3](https://www.nature.com/articles/s43247-024-01885-8#Fig3) (bottom left) shows the difference in the absolute errors between the hybrid and control run, note the difference in positive and negative range. As a whole, the hybrid model improves upon the RMSE of the control run. In the bottom right of Fig. [3](https://www.nature.com/articles/s43247-024-01885-8#Fig3), the difference in precipitation standard deviation are plotted with the tropics in the hybrid model exhibiting larger standard deviations.

**Table 1.** Area-weighted root-mean-squared-errors (RMSE)

| Ground truth source / Data field | Global area-weighted RMSE / IPCP / Precipitation / \[mm/day\] | Global area-weighted RMSE / ERA5 / T / \[K\] | Global area-weighted RMSE / ERA5 / Q / \[kg/kg\] / ×10<sup>−3</sup> | Tropics area-weighted RMSE / IPCP / Precipitation / \[mm/day\] | Tropics area-weighted RMSE / ERA5 / T / \[K\] | Tropics area-weighted RMSE / ERA5 / Q / \[kg/kg\] / ×10<sup>−3</sup> |
| -------------------------------- | ------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------------- |
| SPEEDY control                   | 1.702                                                         | 3.352                                        | 1.657                                                               | 3.104                                                          | 3.450                                         | 2.489                                                                |
| Hybrid                           | 1.412 (17.01%)                                                | 3.397                                        | 1.638                                                               | 2.487 (19.87%)                                                 | 3.691                                         | 2.474                                                                |
| Hybrid                           | 1.411 (17.06%)                                                | 3.394                                        | 1.637                                                               | 2.495 (19.61%)                                                 | 3.691                                         | 2.469                                                                |
| Hybrid                           | 1.420 (16.50%)                                                | 3.410                                        | 1.637                                                               | 2.514 (19.01%)                                                 | 3.688                                         | 2.467                                                                |
| Naive (*ϵ* = 0.01)               | 1.584 (6.92%)                                                 | 3.520                                        | 1.580                                                               | 2.860 (7.87%)                                                  | 3.991                                         | 2.316                                                                |
| Naive (*ϵ* = 0.01)               | 1.590 (6.56%)                                                 | 3.538                                        | 1.583                                                               | 2.872 (7.48%)                                                  | 3.995                                         | 2.318                                                                |
| Naive (*ϵ* = 0.01)               | 1.580 (7.16%)                                                 | 3.534                                        | 1.582                                                               | 2.857 (7.96%)                                                  | 3.996                                         | 2.321                                                                |
| Naive (*ϵ* = 0.05)               | 5.049                                                         | 3.563                                        | 1.213                                                               | 8.917                                                          | 4.811                                         | 2.111                                                                |
| Naive (*ϵ* = 0.05)               | 5.044                                                         | 3.577                                        | 1.213                                                               | 8.902                                                          | 4.842                                         | 2.115                                                                |
| Naive (*ϵ* = 0.05)               | 5.037                                                         | 3.574                                        | 1.204                                                               | 8.885                                                          | 4.849                                         | 2.095                                                                |
| Naive (*ϵ* = 0.1)                | N/A                                                           | N/A                                          | N/A                                                                 | N/A                                                            | N/A                                           | N/A                                                                  |

Global and tropics area weighted precipitation, temperature (*T* at 925 hPa) and specific humidity (*Q* at 925 hPa) RMSE values against GPCP and ERA5 data for the control SPEEDY, hybrid and naively perturbed runs. For cases of improvement the percentage relative error against the SPEEDY control run are also calculated. Note that for *ϵ* = 0.05 there is a large degradation in the precipitation RMSE despite having lower RMSE values for *Q*.

To test the utility of the MOGP predictions, naively perturbed runs form a baseline model. Stochastic noise is introduced at the same time intervals as the hybrid model and various levels of noise are trialled. Full details on the implementation of the naive stochastic models can be found in Section “Naive stochastic perturbations”. At 1% noise level, the global and tropical area-weighted RMSE improvement is up to 7.2% and 8%, respectively (Table [1](https://www.nature.com/articles/s43247-024-01885-8#Tab1)) when compared to the control run. Note that selecting 5% noise level for the naively perturbed runs results in a degradation in the performance. To give a sense of the magnitude of these RMSE reductions, the massive update from CESM1 to CESM2<sup>[37](https://www.nature.com/articles/s43247-024-01885-8#ref-CR37)</sup> resulted in a reduction of the RMSE in precipitation of around 20%, with all atmospheric parameterizations updated across several teams over October 2015 to April 2018. Areas of particular change in Fig. [3](https://www.nature.com/articles/s43247-024-01885-8#Fig3) are the reduction in error in the Arabian Sea, Western Pacific Ocean, and off the west coast of Central America.

To further explore these results Fig. [4](https://www.nature.com/articles/s43247-024-01885-8#Fig4) highlights the differences between mean precipitation, outgoing long-wave radiation, top-of-the-atmosphere net downward solar radiation and cloud cover between the hybrid and SPEEDY control run. In all four subplots a pixel-wise Welch’s *t*-test (2<em>σ</em> level) has been used to mask regions (shaded white) that exhibit statistically insignificant changes. This operation ensures the subsequent analyses consider only the true signal of the changes made by our hybrid method. Welch’s method is chosen over Student’s *t*-test as Welch’s allows for unequal variance between the distributions.

![Figure 4](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig4_HTML.png)

**Figure 4.** **Field differences between the Hybrid and SPEEDY control model (Hybrid minus SPEEDY).**

Differences in mean precipitation, top-of-atmosphere outgoing long-wave radiation, top-of-atmosphere net downward short-wave radiation and cloud cover between the hybrid and SPEEDY control simulations. Statistically insignificant results are masked. The red star and box mark out areas of particular interest in the top left sub-figure.

The areas over land with increased precipitation correspond to an increase in cloud cover, a reduction in top-of-the-atmosphere net downward solar radiation (more reflection) and less outgoing long-wave radiation. This points towards more optically thick and deep clouds being produced in the hybrid set-up.

### Assessment of long-term drift and physical explanation for precipitation changes

Informed by the high-resolution variability training data, the perturbations the hybrid model introduces to the temperature and humidity fields are on average zero. However, the online coupling of hybrid approaches can lead to climatic drift in atmospheric GCM models<sup>[38](https://www.nature.com/articles/s43247-024-01885-8#ref-CR38)</sup> therefore an assessment on the long-term behaviour is carried out here. In addition, the physical drivers for the observed precipitation improvements are explored.

To assess the climatic stability of this hybrid approach, the monthly means of the temperature and specific humidity fields at each level of the atmosphere are plotted through time in Fig. [5](https://www.nature.com/articles/s43247-024-01885-8#Fig5). The different pressure levels in the atmosphere are denoted by the colour scale. There is no climatic drift when comparing the SPEEDY control and hybrid runs. The hybrid model does however introduce both higher temperatures and specific humidity values in the mid-levels (700 hPa and 500 hPa). The lack of overall climatic drift is further validated by comparing the temperature and specific humidity fields at 925 hPa with data from ERA5<sup>[39](https://www.nature.com/articles/s43247-024-01885-8#ref-CR39)</sup> for the same ten-year period, see Table [1](https://www.nature.com/articles/s43247-024-01885-8#Tab1) for area-weighted RMSE values. The global area weighted RMSE values exhibit on the order of 1% difference when comparing the hybrid to SPEEDY control run.

![Figure 5](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig5_HTML.png)

**Figure 5.** **Comparison of monthly global averages.**

Monthly global averages of temperature (top) and specific humidity (bottom) across the different vertical levels for the SPEEDY control and hybrid simulations. In both panels the higher values are near the surface and the lines are ordered top to bottom with data at 925, 850, 700, 500, 300, 200, 100 and 30 hPa.

Turning to the physical explanations for the precipitation changes, Fig. [6](https://www.nature.com/articles/s43247-024-01885-8#Fig6) shows a skew-T log-p diagram<sup>[40](https://www.nature.com/articles/s43247-024-01885-8#ref-CR40)</sup> for the tropical Pacific off the coast of Central America where the precipitation has reduced in the hybrid simulation (region highlighted as a red box in the top left sub-figure of Fig. [4](https://www.nature.com/articles/s43247-024-01885-8#Fig4)). In the boundary layer, the temperatures and humidities are similar leading to similar lifting condensation levels for the SPEEDY control (black dot) and hybrid experiment (cyan cross) and similar moist adiabats for the ascents. However, as a result of the different tropospheric temperature profiles, the fates of the two ascents are quite different.

![Figure 6](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig6_HTML.png)

**Figure 6.** **Comparison of thermodynamic profiles and lifted index/precipitation histograms.**

Left panel: Skew-T log-p diagram for the thermodynamic profiles in the tropical east Pacific (1.856°N and zonally-averaged from 168.75°W to 78.75°W) for the SPEEDY control (solid) and hybrid (dashed) simulations. Dry-bulb temperature in blue, dew-point in green and surface-parcel ascent in orange. Right panels, top row: Lifted index histograms for both the SPEEDY control and hybrid simulation in central Africa (33.75°E, −1.856°S) and, bottom row, precipitation histograms with the zero counts removed.

In the SPEEDY control these parcel ascents can rise to 520 hPa, corresponding to a convective cloud top of around 5.3 km where the environment temperature is −2 °C. The shaded pink area, the Convective Available Potential Energy (CAPE), is 122 J/kg. In contrast, the hybrid run has a moister troposphere (dashed green line to right of solid green) and importantly a warmer troposphere (dashed blue line to right of solid blue from within the boundary layer to 400 hPa). Due to the warmer mid-troposphere the hybrid experiment has a parcel than can only rise as far as 645 hPa. This is a height of around 3.6 km where the temperature is +7 °C. The CAPE is now only 25 J/kg (and the black shading can hardly be seen).

The reduced precipitation in the eastern tropical Pacific in the hybrid run can be explained by two factors. Firstly, the perturbed simulation leads to an increased mid-tropospheric temperature. This limits the height of rising convective parcels, limiting the amount of condensation and hence surface precipitation. Secondly, the hybrid ascents remain “warm” preventing latent heat of fusion from releasing additional latent heat, which would drive more buoyancy, a higher ascent and more precipitation. By contrast, the SPEEDY control run in this location has a mean convective cloud top located above the freezing level implying that latent heat of fusion will have contributed to some deeper ascents, more condensation and more precipitation.

In Fig. [6](https://www.nature.com/articles/s43247-024-01885-8#Fig6) histograms of calculated lifted index values and precipitation are also shown. The lifted index (LI<sup>[41](https://www.nature.com/articles/s43247-024-01885-8#ref-CR41)</sup>) quantifies the temperature difference between a rising surface-based parcel and the environment in the mid-troposphere. As such it is a measure of the potential vigour of convection. The lifted index is calculated every 6 h for both the hybrid and SPEEDY control run for a point in central Africa (denoted as a red star in the top left sub-figure of Fig. [4](https://www.nature.com/articles/s43247-024-01885-8#Fig4)). This point is chosen as it exhibits an increase in mean precipitation for the hybrid run. The histograms of the lifted index for this point are plotted in the top right subplot in Fig. [6](https://www.nature.com/articles/s43247-024-01885-8#Fig6). There are clear differences in the histograms obtained. The presence of a larger number of negative LI values, where LI ≤ −4, points towards a larger number of unstable atmospheric conditions. The unstable atmospheric conditions result in a larger number of extreme precipitation events, as can be seen in the bottom right subplot of Fig. [6](https://www.nature.com/articles/s43247-024-01885-8#Fig6). These histograms reveal the effect that the perturbations have on the nonlinear characteristics of the parameterization schemes. Despite the perturbations being mean zero, the nonlinear nature of convection results in a large change in the time-averaged thermodynamics and in the precipitation coming from these systems. As seen in Fig. [3](https://www.nature.com/articles/s43247-024-01885-8#Fig3) (bottom right), this behaviour plays a role in the larger standard deviation of precipitation in the tropics.

## Discussion

SPEEDY is a simplified model. As such, it would be relatively easy to improve its fidelity by increasing its horizontal and vertical resolution or by using a more sophisticated set of parametrization schemes. Although SPEEDY is a simplified model, it is interesting to note that in terms of precipitation, it has a wet bias over the Arabian Sea and a dry bias over the Bay of Bengal. This bias, in addition to the presence of the double ITCZ, are both very common in GCMs and long-standing. They can be seen in the multi-model mean over several iterations of climate model inter-comparison studies<sup>[42](https://www.nature.com/articles/s43247-024-01885-8#ref-CR42)</sup>. They are also patterns of precipitation bias which have been present in several versions of the Met Office global climate model \[ref. <sup>[43](https://www.nature.com/articles/s43247-024-01885-8#ref-CR43)</sup>\].

The goal here is to use SPEEDY, which is much cheaper to run than state-of-the-art GCMs, but which exhibits some biases common to those more expensive GCMs, as a testbed for how the introduction of machine-learnt thermodynamic variability can impact on a model’s climate. The 17% reduction in area-weighted RMSE we observed with the hybrid SPEEDY is an illustration of the potential that results from our approach, here for SPEEDY and later for other models.

In these simulations, the perturbations have zero mean, do not cause climatic drift but do have a non-zero impact on the precipitation patterns. Specifically, in situations of tropical weather, if the profile is neutral, and hence on the cusp of stable or unstable, then a small perturbation can push it to being stable, leading to no rain, while a similar magnitude perturbation in the opposite direction can lead to an unstable situation which would lead to a lot of precipitation. It is shown here that despite being zero on average, the perturbations do change the patterns of precipitation. These changes occur both through the immediate, local, changes due to whether convection occurs, but also as a result of the feedback that this change in convective activity has on the synoptic scale and hence the large-scale flow.

Several avenues present themselves for future work. Firstly, the MOGP could be retrained using a larger dataset, which has been extended to consist of more high-resolution simulations from more locations and for longer periods. This could include data from kilometre-scale global simulations<sup>[5](https://www.nature.com/articles/s43247-024-01885-8#ref-CR5)</sup>.

Secondly, the MOGP could be coupled to more complex GCMs to confirm that the approach described here leads to similar changes in the global distributions of simulated precipitation.

Finally, the manner in which the predicted uncertainty is sampled should be investigated. At present, the mean profiles of *T* and *Q* are perturbed based on the predicted standard deviation, with a correlation imposed on the samples drawn at each height. In this study, the perturbations between levels are independent whereas within any given vertical level the *T* and *Q* perturbations are perfectly correlated. That is they use the same quantile in their samples. This ensures the temperature and humidity changes within the given cell do not deviate from each other in a non-physical manner. Although some coherence between *T* and *Q* perturbations at each height is possible and some vertical coherence is also likely, it is also reasonable to assume that *T* and *Q* perturbations may not always be perfectly correlated or that some vertical decorrelation should be allowed. As a result, it would be interesting to study how these correlations affect the results. These correlations are likely to depend on the details of the local meteorology. Most interestingly, it would be useful to investigate how to make these correlations be something that is learnt from the high-resolution training data.

## Methods

### MOGP

Profiles of the standard deviations of the temperature and specific humidity are predicted using a MOGP emulator<sup>[44](https://www.nature.com/articles/s43247-024-01885-8#ref-CR44)</sup>, which is an efficient implementation of the standard Gaussian Process (GP) regression method that takes advantage of the sharing of inputs (and thus requires only one matrix of distances for the covariance computations and others). A GP is a random function *f*. A certain level of smoothness, and correlation between nearby locations is assumed. It is a continuous extension of multidimensional normal distribution, defined by the mean function *m*(*x*) and the covariance function $c(x,x^{\prime} )$:

$$
f(x) \sim GP(m(x),c(x,{x}^{{\prime} })),
$$

(1)

$$
{{\rm{where}}}\,\,\,\,\,m(x)={\mathbb{E}}[\,f(x)],
$$

(2)

$$
{{\rm{and}}}\,\,\,\,\,c(x,{x}^{{\prime} })={\mathbb{E}}\left[\left(f(x)-m(x)\right)\left(f({x}^{{\prime} })-m({x}^{{\prime} })\right)\right].
$$

(3)

The mean function is often set to zero (as here) so the variations in the data are explained by the covariance function. Using a sample of the true function, parameters of the covariance function are estimated to fit a GP to the sample, and predictions (with uncertainties) can be made by the GP. Details can be found in ref. <sup>[45](https://www.nature.com/articles/s43247-024-01885-8#ref-CR45)</sup>. Examples of the successful applications of MOGPs to geophysics can be found in refs. <sup>[46](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR46),[47](https://www.nature.com/articles/s43247-024-01885-8?error=cookies_not_supported&code=f799b99f-ff4a-48bd-aa7d-01443cd48778#ref-CR47),[48](https://www.nature.com/articles/s43247-024-01885-8#ref-CR48)</sup>.

The MOGP predicts the standard deviations on a column by column basis and takes as input the land-sea fraction, mean orography, standard deviation of the orography, mean surface-level pressure and mean air temperature and mean specific humidity at each of the 8 height levels used in SPEEDY.

The training dataset consists of 12,800 profiles: 80 × 4 = 320 patches, 4 times each day (00, 06, 12 and 18 UTC) for 10 days. The training profiles are chosen randomly over the time dimension but with exactly 2 training points for each patch. This approach ensures an even coverage globally of all the available orographies in the training dataset. Sophisticated experimental design algorithms and sampling methods cannot be easily implemented here as the sampling space is discrete and the notion of a space-filling design is not obvious.

The training is carried out using a workstation (16x Intel(R) Core(TM) i7-9800X CPU), with the hyperparameters estimated using a LFBGS solver. A Matérn-5/2 kernel function is chosen to train the MOGP due to its versatility. As there is a large difference in the scales of the predicted outputs (the standard deviation of temperature is order of magnitudes larger than the standard deviation of the specific humidity) the specific humidity standard deviation is scaled by 1000.

To ensure the MOGP has been trained successfully, its predictions are compared to ground truth values on a test dataset. In Figs. [7](https://www.nature.com/articles/s43247-024-01885-8#Fig7) and [8](https://www.nature.com/articles/s43247-024-01885-8#Fig8) the predicted versus ground truth values can be seen. The uncertainty on the MOGP predictions are included as error bars. Included in these figures are also the performance of the naive perturbation approach at differing noise level as outlined in Section “Naive stochastic perturbations”. It can be seen that the MOGP captures the overall trend the best but is over confident in its predictions, especially for the specific humidity estimates.

![Figure 7](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig7_HTML.png)

**Figure 7.** **Multi-output Gaussian process and naive approach validation for temperature.**

MOGP validation and predictions from the naive perturbations on the test dataset. The predicted temperature standard deviation is plotted against the ground truth value for each level of the SPEEDY atmosphere. The MOGP uncertainty is denoted by the red error bars.

### Two-way coupling of GCM and MOGP

The two-way coupling of SPEEDY and the trained MOGP relies on I/O and is implemented as follows. After each 6-h forward integration of SPEEDY all the column profiles of *T* and *Q* are written to disk. These grid-box mean profiles, the land-sea mask, the grid-box mean surface pressure and the grid-box mean and standard deviation of orography form the inputs to the MOGP. The MOGP then predicts profiles of the standard deviations of *T* and *Q*. The mean profiles of *T* and *Q* are perturbed based on the predicted standard deviation, with a correlation imposed on the samples drawn at each height. The new profiles of *T* and *Q* are then written back to disk. The perturbed profiles are read in by SPEEDY, where another forward integration occurs and the cycle repeats. The coupling of the two models is managed by a python wrapper, the code for which is available (see code availability statement).

Using the model-predicted profiles of *T* and *Q* as inputs, the MOGP is able to produce a range of different predictions of *T* and *Q* variability. Figure [1](https://www.nature.com/articles/s43247-024-01885-8#Fig1) shows maps of this variability at 925 hPa, as an exmaple. There is generally more sub-grid *T* variability predicted over land than over sea and in the summer hemisphere than in the winter hemisphere. This makes sense as increased insolation and variable land surfaces and orography will naturally lead to more variability in lower-tropospheric temperature in the summer and over land. However, there are also regions of increased *T* variability over the ocean, especially in the storm track regions. Humidity variability is larger in the tropics, where humidity is generally larger, but this is not uniform. Synoptic variability is also apparent as waves patterns in the both *T* and *Q* variability. Figure [1](https://www.nature.com/articles/s43247-024-01885-8#Fig1) illustrates that the MOGP is able to produce a range of predictions and that it generates *T* and *Q* variability that is itself variable in space and time.

### Experimental set up

A 1-year control simulation starting from 1st January 1981 provides spin-up initial conditions for the SPEEDY control and hybrid runs. The control and hybrid runs are then integrated forward for a further 10 years (1st January 1982 to 1st January 1992). The hybrid experiment consists of SPEEDY two-way coupled to the MOGP. SPEEDY’s predicted *T* and *Q* profiles are perturbed within their predicted standard deviation at 6 hourly intervals and various diagnostic fields are outputted. The hybrid simulations are repeated three times to ensure that the results are robust, with different random draws in each case. The area-weighted RMSEs are calculated against GPCP precipitation data covering the same period. Further, to ensure that no climatic drift occurs RMSE calculations are carried out for the 10-year mean of *T* and *Q* at 925 hPa against the ERA5 fields<sup>[39](https://www.nature.com/articles/s43247-024-01885-8#ref-CR39)</sup>. The breakdown of the RMSE values are displayed in Table [1](https://www.nature.com/articles/s43247-024-01885-8#Tab1).

### Naive stochastic perturbations

Perturbing the profiles in a naive manner acts as the baseline model to compare against. In this naive approach the profiles are perturbed by using the same coupling framework as in Section “Two-way coupling of GCM and MOGP”. However, instead of predicting the standard deviation of *T* and *Q* at each level using the MOGP model the profiles are perturbed by additive Gaussian noise given by ${{\mathcal{N}}}(0,\,\epsilon {\mu }_{T/Q})$, where *μ*<sub><em>T</em>/<em>Q</em></sub> is the mean values and *ϵ* ∈ \{0.01, 0.05, 0.1\}. The stochastically perturbed simulation with *ϵ* = 0.1 fails to run due to non-physical profiles being produced. To assess the skill of this approach Figs. [7](https://www.nature.com/articles/s43247-024-01885-8#Fig7) and [8](https://www.nature.com/articles/s43247-024-01885-8#Fig8) showcase the predicted standard deviation of temperature and specific humidity against the ground truth for the different *ϵ* values. Further, the area-weighted RMSE values are given in Table [1](https://www.nature.com/articles/s43247-024-01885-8#Tab1).

![Figure 8](https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs43247-024-01885-8/MediaObjects/43247_2024_1885_Fig8_HTML.png)

**Figure 8.** **Multi-output Gaussian process and naive approach validation for specific humidity.**

MOGP validation and predictions from the naive perturbations on the test dataset. The predicted specific humidity standard deviation is plotted against the ground truth value for each level of the SPEEDY atmosphere. The MOGP uncertainty is denoted by the red error bars.

## Data availability

The coarse grained high resolution Met Office Unified Model data used to train the MOGP can be accessed at the following public repository: [https://zenodo.org/records/7611474](https://zenodo.org/records/7611474).

## Code availability

All code used to produce the results presented is available at the following public repository: [https://zenodo.org/records/13968979](https://zenodo.org/records/13968979).

## References (48 total, showing 48)

1. IPCC. *Summary for Policymakers*, 3–32 (Cambridge University Press, 2021).

2. Krueger, S. K. *Cloud System Modeling*, 605–640 (Academic Press, 2000).

3. Lean, H. W. et al. Characteristics of high-resolution versions of the Met Office Unified Model for forecasting convection over the United Kingdom. *Mon. Weather Rev.* **136**, 3408–3424 (2008).

4. Kendon, E. J. et al. Do convection-permitting regional climate models improve projections of future precipitation change? *Bull. Am. Meteorol. Soc.* **98**, 79–93 (2017).

5. Slingo, J. et al. Ambitious partnership needed for reliable climate prediction. *Nat. Clim. Change* **12**, 499–503 (2022).

6. Stensrud, D. J. *Parameterization Schemes: Keys to Understanding Numerical Weather Prediction Models* (Cambridge University Press, 2007).

7. Smith, R. N. B. A scheme for predicting layer clouds and their water content in a general circulation model. *Q. J. R. Meteorol. Soc.* **116**, 435–460 (1990).

8. Pincus, R., Barker, H. W. & Morcrette, J.-J. A fast, flexible, approximate technique for computing radiative transfer in inhomogeneous cloud fields. *J. Geophys. Res*. **108**, 4376 (2003).

9. Tompkins, A. M. The parametrization of cloud cover. *European Centre for Medium-Range Weather Forecasts, Numerical Weather Prediction Course: Parameterization of Diabatic Processes*, (ECMWF Technical Memoranda, 2005).

10. Van Weverberg, K., Boutle, I. A., Morcrette, C. J. & Newsom, R. K. Towards retrieving critical relative humidity from ground-based remote-sensing observations. *Q. J. R. Meteorol. Soc.* **142**, 2867–2881 (2016).

11. Ukkonen, P., Pincus, R., Hogan, R. J., Nielsen, K. P. & Kaas, E. Accelerating radiation computations for dynamical models with targeted machine learning and code optimization. *J. Adv. Model. Earth Syst.* **12**, e2020MS002226 (2020).

12. Lagerquist, R., Turner, D., Ebert-Uphoff, I., Stewart, J. & Hagerty, V. Using deep learning to emulate and accelerate a radiative transfer model. *J. Atmos. Ocean. Technol.* **38**, 1673–1696 (2021).

13. Beucler, T., Ebert-Uphoff, I., Rasp, S., Pritchard, M. & Gentine, P. *Machine Learning for Clouds and Climate*, Ch. 16, 325–345 (American Geophysical Union (AGU), 2023).

14. Brenowitz, N. D. & Bretherton, C. S. Prognostic validation of a neural network unified physics parameterization. *Geophys. Res. Lett.* **45**, 6289–6298 (2018).

15. Brenowitz, N. D. & Bretherton, C. S. Spatially extended tests of a neural network parametrization trained by coarse-graining. *J. Adv. Model. Earth Syst.* **11**, 2728–2744 (2019).

16. Bretherton, C. S. et al. Correcting coarse-grid weather and climate models by machine learning from global storm-resolving simulations. *J. Adv. Model. Earth Syst.* **14**, e2021MS002794 (2022).

17. Shamekh, S., Lamb, K. D., Huang, Y. & Gentine, P. Implicit learning of convective organization explains precipitation stochasticity. *Proc. Natl Acad. Sci. USA* **120**, 1–11 (2023).

18. Arcomano, T. et al. A hybrid approach to atmospheric modeling that combines machine learning with a physics-based numerical model. *J. Adv. Model. Earth Syst.* **14**, 1–21 (2022).

19. Arcomano, T., Szunyogh, I., Wikner, A., Hunt, B. R. & Ott, E. A hybrid atmospheric model incorporating machine learning can capture dynamical processes not captured by its physics-based component. *Geophys. Res. Lett.* **50**, 1–10 (2023).

20. Kochkov, D. et al. Neural general circulation models for weather and climate. *Nature* **632**, 1060–1066 (2024).

21. Buizza, R., Miller, M. & Palmer, T. N. Stochastic representation of model uncertainties in the ECMWF ensemble prediction system. *Q. J. R. Meteorol. Soc.* **125**, 2887–2908 (1999).

22. Christensen, H. M., Lock, S.-J., Moroz, I. M. & Palmer, T. N. Introducing independent patterns into the Stochastically Perturbed Parametrization Tendencies (SPPT) scheme. *Q. J. R. Meteorol. Soc.* **143**, 2168–2181 (2017).

23. Bowler, N. E., Arribas, A., Mylne, K. R., Robertson, K. B. & Beare, S. E. The MOGREPS short-range ensemble prediction system. *Q. J. R. Meteorol. Soc.* **134**, 703–722 (2008).

24. Jankov, I. et al. Stochastically perturbed parameterizations in an HRRR-based ensemble. *Mon. Weather Rev.* **147**, 153–173 (2019).

25. Watson-Parris, D. Machine learning for weather and climate are worlds apart. *Philos. Trans. R. Soc. A* **379**, 20200098 (2021).

26. Walters, D. N. et al. The met office unified model global atmosphere 3.0/3.1 and JULES Global Land 3.0/3.1 configurations. *Geosci. Model Dev.* **4**, 919–941 (2011).

27. Morcrette, C. J. et al. Scale-aware parameterization of cloud fraction and condensate for a global atmospheric model machine-learnt from coarse-grained kilometer-scale simulations. *ESS Open Arch.* (2024). https://doi.org/10.22541/essoar.172462453.32373495/v1.

28. Molteni, F. Atmospheric simulations using a GCM with simplified physical parametrizations. I: model climatology and variability in multi-decadal experiments. *Clim. Dyn.* **20**, 175–191 (2003).

29. Adler, R. et al. *Global Precipitation Climatology Project (GPCP)*. (Climate Data Record (cdr), 2016).

30. Walters, D. et al. The met office unified model global atmosphere 6.0/6.1 and JULES global land 6.0/6.1 configurations. *Geosci. Model Dev.* **10**, 1487–1520 (2017).

31. Bush, M. et al. The first met office unified model/JULES regional atmosphere and land configuration, RAL1. *Geosci. Model. Dev.* **13**, 1999–2029 (2019).

32. Stein, T. H. M. et al. The representation of the West African monsoon vertical cloud structure in the Met Office Unified Model: an evaluation with CloudSat. *Q. J. R. Meteorol. Soc.* **141**, 3312–3324 (2015).

33. Webster, S., Uddstrom, M., Oliver, H. & Vosper, S. A high resolution modelling case study of a severe weather event over New Zealand. *Atmos. Sci. Lett.* **9**, 119–128 (2008).

34. Kain, J. S. et al. Collaborative efforts between the United States and United Kingdom to advance prediction of high-impact weather. *Bull. Am. Meteorol. Soc.* **98**, 937–948 (2017).

35. Keat, W. J. et al. Convective initiation and storm life cycles in convection-permitting simulations of the Met Office Unified Model over South Africa. *Q. J. R. Meteorol. Soc.* **145**, 1323–1336 (2019).

36. Donlon, C. J. et al. The operational sea surface temperature and sea ice analysis (OSTIA) system. *Remote Sens. Environ.* **116**, 140–158 (2012).

37. Danabasoglu, G. et al. The community earth system model version 2 (CESM2). *J. Adv. Model. Earth Syst.* **12**, e2019MS001916 (2020).

38. de Burgh-Day, C. O. & Leeuwenburg, T. Machine learning for numerical weather and climate modelling: a review. *Geosci. Model Dev.* **16**, 6433–6477 (2023).

39. Hersbach, H. et al. The ERA5 global reanalysis. *Q. J. R. Meteorol. Soc.* **146**, 1999–2049 (2020).

40. May, R. M. et al. Metpy: A meteorological python library for data analysis and visualization. *Bull. Am. Meteorol. Soc.* **103**, E2273–E2284 (2022).

41. Galway, J. G. The lifted index as a predictor of latent instability. *Bull. Am. Meteorol. Soc.* **37**, 528–529 (1956).

42. Tian, B. & Dong, X. The Double-ITCZ bias in CMIP3, CMIP5 and CMIP6 models based on annual mean precipitation. *Geophys. Res. Lett.* **47**, e2020GL087232 (2020).

43. Walters, D. N. et al. The met office unified model global atmosphere 7.0 and JULES global land 7.0 configurations. *Geosci. Model Dev.* **12**, 1909–1963 (2019).

44. Daub, E., Strickson, O. & Barlow, N. Multi-output Gaussian process emulator https://github.com/alan-turing-institute/mogp-emulator (2022).

45. Rasmussen, C. E. & Williams, C. K. I. *Gaussian Processes for Machine Learning (Adaptive Computation and Machine Learning)* (The MIT Press, 2005).

46. Gopinathan, D., Heidarzadeh, M. & Guillas, S. Probabilistic quantification of tsunami current hazard using statistical emulation. *Proc. R. Soc. A* **477**, 20210180 (2021).

47. Salmanidou, D. M., Beck, J., Pazak, P. & Guillas, S. Probabilistic, high-resolution tsunami predictions in northern Cascadia by exploiting sequential design for efficient emulation. *Nat. Hazards Earth Syst. Sci.* **21**, 3789–3807 (2021).

48. Giles, D., Gopinathan, D., Guillas, S. & Dias, F. Faster than real time tsunami warning with associated hazard uncertainties. *Front. Earth Sci.* **8**, 597865 (2021).
