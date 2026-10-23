---
title: "Patterns and Trends in Northern Hemisphere River Ice Phenology from 2000 to 2021"
authors: "Xinchi Wang, Lian Feng"
doi: "10.1016/j.rse.2024.114346"
source: "elsevier_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 14045
---

# Patterns and Trends in Northern Hemisphere River Ice Phenology from 2000 to 2021

## Abstract

River ice plays a crucial role in hydrology, ecosystems, and socio-economic systems in mid-to-high latitude regions. However, there is a notable gap in the analysis of patterns and trends in river ice phenologies and their influence factors at the river level. In this study, we developed a practical method to identify river ice phenologies by leveraging Landsat observations from 2000 to 2021, and established a comprehensive dataset encompassing 7970 river segments across the entire Northern Hemisphere. Our results revealed that the mean freeze-up date, break-up date, and ice duration for these river segments were October 24, May 4, and 192.1 days, respectively. Notably, 56% of the river segments exhibited a warming trend, with the average freeze-up date delayed by 2.7 days per decade, break-up date advanced by 2.5 days per decade, and ice duration shortened by 5.5 days per decade—nearly five times the documented decrease rate over the past 150 years. Furthermore, high-latitude polar regions and the Qinghai-Tibet Plateau demonstrated the most pronounced decreases in ice duration, exceeding 7.0 days per decade on average. We observed a substantial relative contribution, reaching up to 70%, of surface air temperature (SAT) in middle and low latitude regions characterized by relatively high winter temperatures. However, as winter temperatures decrease, the relative influence of SAT diminishes, while the contributions of precipitation, solar radiation, and residuals increase. Our dataset provided essential baseline for further understanding the fundamental physical processes within river systems, offering crucial insights for river management, hydrological disaster risk control, climate change research, and ecosystem conservation efforts.

## Introduction

The freezing and thawing of rivers are fundamental phenological characteristics, with approximately 56% of rivers in the Northern Hemisphere experiencing varying lengths of ice cover periods (Bennett and Prowse, 2010; Prowse et al., 2006; Yang et al., 2020). River ice not only influences the river's morphology, hydrological processes and heat exchange but also affects solute transport, ecosystems, and socio-economic aspects (Beltaos et al., 2013; Blackadar et al., 2020; Gebre et al., 2013; Prowse and Beltaos, 2002). During ice formation, solutes are excluded, leading to increased concentrations in the water (DeGrandpre et al., 2021). Reduced vertical turbulent mixing and increased flow resistance during freezing decrease the sediment transport capacity of rivers (Beltaos and Burrell, 2021; Zhao et al., 2023). Additionally, the accumulation of ice and the formation of ice jams can destabilize infrastructure such as bridges (Burrell et al., 2024) and might block river channels, causing flooding (Huang and Shen, 2024; Prowse, 2001a). Thawing, characterized by increased flow, ice movement, and ice jam release, enhances the erosive potential of a river, resulting in higher suspended sediment concentrations in the water (Knack and Shen, 2018). These changes in solute concentration can impact the foraging ecology of aquatic organisms due to alterations in nutrient structure. Moreover, river ice is closely intertwined with human social activities such as safe travel, spiritual rituals, outdoor ice-skating competitions, and ice fishing contests (Brown et al., 2018; Knoll et al., 2019; Wazney et al., 2019). For example, hundreds of small communities of remote rural Alaska rely on frozen waterways to provide primary access via ice roads and trails in winter (Richards et al., 2023).

River ice phenologies typically refer to the freeze-up date, break-up date, and ice duration of a river (Benson et al., 2000; Magnuson et al., 2000). With the ongoing global climate warming, river ice phenologies are undergoing a warming trajectory marked by delayed freeze-up date, earlier break-up date, and a shortened duration of ice cover (Fukś, 2023; Newton and Mullan, 2021; Podkowa et al., 2023). Monitoring and assessing these changes in river ice phenologies become imperative in this context. Currently, the availability of field survey data for river ice phenologies is notably limited. For instance, The Global Lake and River Ice Phenology Database meticulously records freeze-up and break-up dates, along with other descriptive ice cover data, for over 800 inland water bodies; however, records for rivers are constrained to a few dozen (Benson et al., 2000). Despite the establishment of various mathematical and physical models to explain freezing-thawing processes of rivers, with the aim of deepening understanding and complementing observational data, these models heavily depend on river-specific parameters and meteorological factors (Rokaya et al., 2020; Shen, 2010; Sun et al., 2020; Sun and Trevor, 2018), which poses challenges in accurately simulating river ice phenologies on a global scale.

Fortuitously, long-term remote sensing observations, such as imagery from MODIS and Landsat, provide an alternative means of acquiring river ice information. However, despite operating for several decades, MODIS is limited to analyzing only a few of the largest rivers due to its coarse spatial resolution (250-m) (Cooley and Pavelsky, 2016; Pavelsky and Smith, 2004). In contrast, the 30-m resolution Landsat data enable the tracking of ice information for a greater number of smaller rivers. For example, river ice conditions have been assessed in regions, such as Alaska and the Qinghai-Tibet Plateau, using various Landsat series data or taking advantage of their overlapping areas with high-frequency observations (Brown et al., 2023; Li et al., 2023). Notably, Yang et al. employed multi-year Landsat imagery to study rivers in the Northern Hemisphere, establishing a universal correlation between ice phenology extent and surface air temperature (SAT), thereby providing predictions for future river ice conditions (Yang et al., 2020). However, as previously mentioned, the ice phenology of rivers—including freeze-up date, break-up date, and ice duration—is influenced by the unique characteristics of each river and prevailing ambient climatic conditions. Developing generic models for all observed rivers may overlook these individual nuances. To address this research gap and provide a comprehensive characterization of ice phenology across the entire Northern Hemisphere, we established, for the first time in this region, a detailed dataset documenting river ice phenology at the river level using 22 years of Landsat observations. Additionally, we investigated the impact of three meteorological factors on changes in river ice regimes observed over the past two decades.

## Data sources

### Landsat satellite images

We analyzed all Landsat 5, 7, and 8 Collection 1 Tier 1 calibrated Top of Atmosphere (TOA) reflectance images taken between August 1, 1999, and July 31, 2021. These images were used to study the river ice phenology in regions of the Northern Hemisphere potentially susceptible to ice (north of 23.5°N). The dataset consisted of a total of 2.49 million images, with 0.49 million from Landsat 5 Thematic Mapper (TM) (1999–2011), 1.25 million from Landsat 7 Enhanced Thematic Mapper Plus (ETM+) (1999–2021), and 0.75 million from the Landsat 8 Operational Land Imager (OLI) (2013−2021). All images were sourced from the Google Earth Engine.

### Sentinel-2 MultiSpectral instrument (MSI) satellite images

We utilized 10-m resolution MSI images to validate the accuracy of freeze-up and break-up dates determined by Landsat. The concurrent use of MSI instruments onboard Sentinel-2 A and Sentinel-2B, with their revisiting period extended to 5 days, allows for more accurate observation of river ice processes. All Sentinel-2 MSI satellite images used for validation were sourced from Google Earth Engine. The high spatial and temporal resolution of MSI images facilitated easy visualization of these dynamic processes.

### Global River widths from Landsat (GRWL)

We utilized the GRWL vector product (Allen and Pavelsky, 2018) (dataset link: https://zenodo.org/records/1297434#.W8JkshNKh24), which includes over 58 million river centerlines, to identify and locate each river or river segment in this study. Each river can be distinctly identified using a combination of tile ID and segment ID. Specifically, the following properties from the GRWL database were employed: geometry, tile location, “segmentID”, “lakeFlag,”, “width\_m”, and “nchannels”. The detailed process of using these attributes is described in the subsequent sections where the model is established.

### JRC surface water occurrence

This dataset utilizes pixel values ranging from 0 to 100 to describe the frequency of water occurrence on the Earth's surface from 1984 to 2021 (Pekel et al., 2016) (dataset link: https://developers.google.com/earth-engine/datasets/catalog/JRC\_GSW1\_4\_GlobalSurfaceWater). It was generated by classifying water and non-water areas using an export system from a total of 4,716,475 Landsat 5, 7, and 8 images. By employing specific thresholds, this dataset can be used to filter static datasets, allowing the exclusion of seasonal inundation and water bodies undergoing significant spatial changes over multiple years.

### Merit DEM

In this study, the MERIT DEM was primarily utilized in conjunction with solar azimuth angles from Landsat images to remove pixels that might be affected by interference caused by terrain shadows (dataset link: https://developers.google.com/earth-engine/datasets/catalog/MERIT\_DEM\_v1\_0\_3). The MERIT Digital Elevation Model (DEM) is a high-precision global DEM dataset with a spatial resolution of 3 arc *sec*. This dataset has eliminated biases and noise by integrating multiple remote sensing data sources.

### In situ river ice data

We utilized the River Ice Phenology dataset provided by the Global Lake and River Ice Phenology Database (GLRIPD, version 1) (Benson et al., 2000) to evaluate the performance of the river ice phenologies determined from Landsat images (as described below) (dataset link: https://nsidc.org/data/g01377/versions/1). This dataset offers information on freeze-up and break-up dates for lakes and rivers, spanning from a few years to several decades.

### ERA5-land data

We utilized SAT, precipitation, and solar radiation data from the ERA5-Land dataset to attribute the long-term changes in river ice phenology. ERA5-Land data is a reanalysis grid dataset covering global land areas, providing a long-term record of various land surface and atmospheric parameters at a spatial resolution of 0.5°. Precipitation and solar radiation data were provided at monthly scales (dataset link: https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land-monthly-means). For each river, we calculated the cumulative precipitation and solar radiation from September to the following May, typically covering the entire ice period in the Northern Hemisphere. Previous studies have highlighted large spatial and numerical differences in long-term SAT changes when examining different months within the same period (Wang et al., 2022). To investigate the impact of SAT on river ice periods, we utilized more temporally detailed ERA5 hourly data (dataset link: https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land). By utilizing freeze-up and break-up dates derived from Landsat images, we calculated the average SAT within the freezing period. This calculation involved considering daily SAT averages at 0:00, 6:00, 12:00, and 18:00 for the corresponding days.

### Circum-Arctic map of permafrost and ground-ice conditions

The circumpolar permafrost and ground ice data constitute a comprehensive international dataset depicting the distribution and characteristics of permafrost and ground ice across the Northern Hemisphere (dataset link: https://nsidc.org/data/ggd318/versions/2) (Brown et al., 2002). We utilize this dataset to locate regions of permafrost in Siberia, North America, and the Qinghai-Tibet Plateau, in order to examine the influence of permafrost on river ice phenologies.

## Methods

### Determination of examined rivers

Our study focused on 7970 ice-covered river segments located in the Northern Hemisphere (Fig. 1a). River network components were first segmented and ordered through hierarchical and discrete ordering method by Horton to quantify their features (Horton, 1945). Examined river segments were similarly established derived from the GRWL river centerline points, and further processed through the following steps (Fig. 1b):

![Figure 1](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr1_lrg.jpg?httpAccept=%2A%2F%2A)

(a) Study area located in the Northern Hemisphere. The orange regions indicate ice-free area, the gray regions indicate areas lacking ice observations from Landsat, and the blue lines depict the locations of the examined river segments in this study. (b) Workflow for determination of examined river segments. (c) Latitude distribution of the number of overall iced rivers with water occurrence &gt;50% and width &gt; 90 m (black line), and the number of examined rivers in this study (red line). (For interpretation of the references to color in this figure legend, the reader is referred to the web version of this article.)

First, we conservatively excluded ice-free areas using a criterion of winter average temperatures above 0 °C (Fig. 1a, regions in orange color). These extents closely matched the regions identified by Landsat imagery potentially susceptible to ice (Fig. S1). We excluded river centerline points located in regions where the JRC surface water occurrence was below a 50% threshold. These excluded rivers typically exhibit significant dynamic changes, such as seasonal variations or multi-year fluctuations (e.g., newly formed rivers). Additionally, some points with inaccurate geographical location in the GRWL, particularly in multi-channeled rivers (e.g., centerline points positioned on island), were also removed from the dataset. River segments located in areas with insufficient valid Landsat observations (i.e., pixels unaffected by clouds or shadows) and scarce ice observations were challenging to depict patterns and trends accurately. Therefore, centerline points situated in area with ice observations less than a total of 20 times in the first 11 years during the study period were not considered (Fig. 1a, regions in gray color). The remaining river centerline points underwent further filtering based on the following attributes:

- Type of waterbody: Points with “lakeFlag” = 0 were chosen, indicating that the centerline points belonged to a river rather than a lake/reservoir, tidal river, or canal.
- River width: Rivers with a width &gt;90 m (“width\_m” &gt; 90) were selected. This criterion aimed to prevent interference from land signals observed by Landsat, ensuring a focus on water bodies.
- Single-channel rivers: Only points with “nchannels” = 1 were included, ensuring that the data represents rivers with a single channel, as multi-channel rivers often have inaccurate centerlines.

Furthermore, for centerline points of river segments with longitude or latitude spans exceeding 0.5°, we divided them into multiple shorter segments with an average coverage of <0.5°. This division was implemented to ensure a more spatial homogeneous representation of river segments for the analysis.

For the remaining river segments, we proceeded to identify the ice phenology annually from 2000 to 2021 (See details in section 3.2 of this paper). River segments with long-term, reliable ice phenological observations were included in the subsequent analysis, amounting to a total of 7970 segments. These river segments covered the vast majority of the potentially iced areas in the Northern Hemisphere, including Asia, North America, and the Qinghai-Tibet Plateau, experiencing varying lengths of freezing periods almost every year. It was worth noting that almost all of the world's iced rivers wider than 90 m are located in the Northern Hemisphere, with exceptions being Antarctica and high-latitude islands. Comparing the number of all iced rivers with water occurrence &gt;50% and width &gt; 90 m to the rivers in this study, we obtained a relatively similar distribution in latitude (Fig. 1c). As such, our characterizations of ice phenology well represented those of the Northern Hemisphere.

After rigorous filtering of river centerline points, very few river segments in the study were retained for study from Europe, mainly due to limited valid observations and ice observations, particularly during the period from 2004 to 2013 (attributed to the Scan Line Corrector of Landsat-7 failed, sparse ground base stations, polar night, etc.) (Arvidson et al., 2006; Ju and Roy, 2008; Loveland and Dwyer, 2012) (Fig. S2 & S3). Europe experienced relatively warmer winter temperatures, resulting in shorter ice periods (Seneviratne et al., 2006; Sippel et al., 2020). Therefore, the exclusion of these rivers might have an impact on global assessment. We considered this to be not notable in our study because the dataset encompassed a comprehensive range of rivers from various other regions, ensuring a robust representation of global river ice phenology.

### Identification of river ice phenologies using Landsat

The logistic model has been frequently employed to fit ice periods or to remove misclassifications outside of ice periods (Giroux-Bougard et al., 2023; Wang et al., 2022). We first developed a river ice phenology determination model based on a novel dual logistic regression approach, akin to the lake ice model dual logistic regression model (DLRM) (Wang et al., 2022), referred to as improved DLRM (IDLRM). The workflow and corresponding diagrams of IDLRM model were depicted in Fig. 2 , with the key steps outlined as follows:

![Figure 2](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr2_lrg.jpg?httpAccept=%2A%2F%2A)

(a) Workflow and (b) corresponding diagrams for the key steps of IDLRM model in determining river ice phenologies.

1. For each river segment selected from Section 3.1, we extracted the time series observations from three Landsat missions that covered the segment. These observations included N<sub>valid</sub> and N<sub>iced</sub>, where N<sub>valid</sub> represented the number of center points within the segment that were considered valid observations in a given Landsat image. Valid observations were defined as those unaffected by cloud cover, cirrus cover, cloud shadows, or terrain shadows. N<sub>iced</sub> represented the number of centerline points within the segment that were determined to be ice-covered (i.e., identified as ice or snow, both can be considered as ice-covered for river pixels), based on valid observations. All these categories were classified using the Quality Assessment (QA) band from Landsat images via the Fmask algorithm (Zhu and Woodcock, 2012). Next, the per-image fraction of valid observartion (F<sub>valid</sub>) and ice observation (F<sub>iced</sub>) were calculated as the ratios of N<sub>valid</sub> to the total number of selected center points within the river segment after filtering (N<sub>total</sub>), and the ratios of N<sub>iced</sub> to N<sub>valid</sub>, respectively (i.e., F<sub>valid</sub> = N<sub>valid</sub> / N<sub>total</sub>, F<sub>iced</sub> = N<sub>iced</sub> / N<sub>valid</sub>).
2. The preprocessing of the time series data F<sub>iced</sub> obtained from Landsat observations involved using a specific threshold to determine whether the river segment was ice covered. Through inspection of series around the world, we identified a threshold of 0.2 for identifying ice cover. (That is, approximately 20% of centerline points are observed to be covered by ice). Excessively high thresholds might lead to omitted identification, while overly low thresholds might not effectively eliminate noise interference. When the value exceeded 0.2, it was considered a high probability of ice occurrence, and F<sub>iced</sub> was set to 1 for that specific time point. Conversely, if the value was below the threshold, it was set to 0, resulting in new time series data F<sub>iced</sub>’. It should be noted that, although we defined the freeze-up and break-up dates using a 20% threshold, which might imply the onset and end of the season when a river was affected by ice, this differed from the previous definition (e.g., freeze-up date is defined as the date the river is first observed to be completely frozen over) (Beltaos et al., 2013). However, since we identified river ice phenologies using the centerline points of a river, where freezing usually occurred last (i.e., the river can be considered completely frozen over if the center of the river is frozen), and considering that the break-up process typically completed in a short period (Prowse and Beltaos, 2002), the identified results of IDLRM model aligned well with the generally defined freeze-up and break-up dates (Fig. 3b). Therefore, we did not emphasize the inconsistency between the model identification process and the previous definitions of ice periods, and we presented the results as the generally defined freeze-up and break-up dates.

![Figure 3](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr3_lrg.jpg?httpAccept=%2A%2F%2A)

   Validation of the satellite-detected river ice phenologies using in situ data. (a) Spatial distribution of the in situ data sourced from GLRIPD. (b) Comparisons of in situ and satellite-detected river ice phenologies.
3. The time series data for F<sub>valid</sub> and F<sub>iced</sub>’ were segmented into one-year periods commencing on August 1 and concluding on July 31. For each river segment, it might not be possible to obtain valid river ice phenology information in an ice-free year or due to insufficient valid observations from satellite. Therefore, we proceed to calculate river ice phenologies only when the number of observations in a given year was no less than ten, there were at least two river ice observations (i.e., F<sub>iced</sub> &gt; 0.2), and the F<sub>valid</sub> of these two ice observations was not <50%.
4. We assumed that that the rivers were unfrozen on the initial day (i.e., August 1) and the final day (i.e., July 31). Thus, F<sub>valid</sub> was set to 1 and F<sub>iced</sub>’ was set to 0 for these days. Subsequent to segmentation, the data from each river segment underwent fitting using formula Eq. (1) with a weighted approach. This approach was particularly useful when dealing with outliers in the time series data (e.g., data with a low valid observation ratio due to cloud and shadow interference), as it helped improve the accuracy and robustness of the fit. In this equation, ‘y’ represents the time series data of F<sub>iced</sub>’ for a particular year in a river segment, ‘x’ represents the date in DOY corresponding to the ‘y’, starting from August 1 of the preceding year (i.e., x = 1). The weights employed for fitting were the squares of F<sub>valid</sub>. The resulting fitted values were denoted as F′ and B′. We used the Curve Fitting Toolbox in MATLAB to carry out the weighted fitting process.

(1)

$$
y = - \frac{1}{e^{5 \bullet {({F' - x})}} + 1} + \frac{1}{e^{5 \bullet {({B' - x})}} + 1}
$$

5. Although this study integrated various Landsat mission data, and the overlapping regions between adjacent images in ice-covered high-latitude areas could enhance the number of valid observations to some extent (Feng and Wang, 2024; Li et al., 2023), Landsat has a longer revisiting period and significantly lower observation frequency compared to MODIS daily observational data. Therefore, in this study, not only were the freeze-up date F (DOY) and break-up date B (DOY) of the year calculated using Eq. (2) and Eq. (3), but the potential maximum errors of the fitted results F (PE<sub>F</sub>) and B (PE<sub>B</sub>) were also separately evaluated for assessing uncertainty and retaining results that meet an minor error threshold (i.e., 8 days). The calculation formulas for the evaluation are as shown in Eq. (4) and Eq. (5).

(2)

$$
F = \frac{x_{F + ,1} + x_{F - ,0}}{2}
$$

(3)

$$
B = \frac{x_{B + ,0} + x_{B - ,1}}{2}
$$

(4)

$$
PE_{F} = \frac{x_{F + ,1} - x_{F - ,0}}{2}
$$

(5)

$$
PE_{B} = \frac{x_{B + ,0} - x_{B - ,1}}{2}
$$

Where $x_{F - ,0}$ represents the last ice-free observation not exceeding F′; $x_{F + ,1}$ denotes the first observation not less than F′; $x_{B + ,0}$ indicates the initial ice-free observation not less than B′; and $x_{B - ,1}$ signifies the last freezing observation not exceeding B′.

By obtaining long-term river ice phenological observations from Landsat images and applying the river ice phenology-determined IDLRM, this study has established, for the first time, a dataset of annual river ice phenologies (i.e., annual freeze-up dates, break-up date, and ice duration) for 7970 examined river segments in the Northern Hemisphere during 2000 to 2021, covering a span of 22 years. We did not study changes before 2000, as the global average valid observation frequency of Landsat was <10 times per year before 2000, making it difficult to track global river ice phenology information (Feng and Wang, 2024). Even after 2000, due to limited observations or sporadic icing events, certain river segments might exhibit missing observation data for specific years, especially during the initial years of the study period. This could potentially introduce uncertianties in the mean ice phenologies and multi-year trends. To reduce these uncertianties, only river segments with freeze-up and break-up observations for at least half of the years during the first 8 years of the study period were retained.

For 7970 examined river segments, we employed the Theil–Sen slope and Mann-Kendall test to evaluate the linear trends and their significance in the ice duration throughout the study period. Based on Theil–Sen slopes, we defined river segments that exhibited significant elongation (i.e., slope×22 &gt; 8 days), significant reduction (i.e., slope×22 < 8 days), or remained stable (i.e., −8 days ≤ slope×22 ≤ 8 days) in ice duration over the 22-year study period.

### Validations of the satellite identified ice phenologies

Although the above-mentioned DLRM model has been proven to be applicable for extracting ice phenologies in inland lakes (Wang et al., 2022), in contrast to the daily time series of the 500-m resolution MODIS/Terra level-3 snow cover product MOD10A1, images from Landsat, while possessing a higher spatial resolution of 30 m that allowed for the observation of smaller rivers, came with a much longer revisiting period of 16 days. Additionally, due to the impact of clouds, cloud shadows, and terrain shadows, almost half of the observations were not able to offer reliable information (Feng and Wang, 2024; Wylie et al., 2005), potentially introducing errors in determining river ice phenologies. Therefore, we performed two types of validations to evaluate the performance of IDLRM model on inland river segments:

First, we conducted validations using in situ river ice phenology observations recorded in GLRIPD database (Benson et al., 2000). For observation sites with complete freeze-up and break-up dates, we randomly generated 50 points along the same river to serve as “river centerline points” in the model. This process was adopted because information obtained from observation points typically represents only a small area of the river, not the entire watercourse. Using random points near the observation sites provided a better match with on-site conditions and ensured that the model's simulation results accurately reflected the accuracy of both the Fmask algorithm and IDLRM model.

Furthermore, we compared the detected river ice phenologies from IDLRM model with observations from high-resolution Sentinel-2 MSI images. We presented three specific examples to illustrate the consistency between the freeze-up and break-up dates determined by IDLRM model and those depicted in Sentinel-2 MSI images.

### Exploring the major factors contributing to river ice changes

The temporal extent of river ice periods is intricately shaped by a myriad of influential factors, encompassing SAT, precipitation, solar radiation, river depth, slope, friction, bed sediments, and groundwater inflows (Beltaos et al., 2013). Of particular significance, SAT, solar radiation, and precipitation emerge as pivotal climatic elements warranting meticulous attention (Beltaos et al., 2013). Hence, we employed a multiple generalized linear model (GLM) (Borja, 2009; Tao et al., 2015) to investigate the relative contributions within a latitude-longitude grid of 5° × 5° of these three meteorological factors to the interannual variations in river ice duration.

For precipitation and solar radiation, we calculated the cumulative values from September of the previous year to May of the current year, nearly covering the entire freezing period in the Northern Hemisphere, practically consistent with the river ice periods in the Northern Hemisphere. As for SAT, its multi-year trends exhibit significant spatial heterogeneity even for different months (Cohen et al., 2012; Wang et al., 2022). Therefore, for each river, we first calculated the median freeze-up and break-up dates from 2000 to 2021. Subsequently, we determined the average SAT between the median freeze-up and break-up dates to explore the relative contributions of SAT changes to ice duration variations.

We used the above-mentioned averages of the three climate factors (SAT, precipitation, and solar radiation) as independent variables and the corresponding annual ice duration as the dependent variable in the GLM modeling. Analysis of variance (ANOVA) was conducted using the R-package. The relative contributions in our study were calculated by dividing the Mean Squared value of each climate factor by the total Mean Squared sum of all three factors (Feng et al., 2019; Pi et al., 2020). Based on Yang et al. (Yang et al., 2020), we also attempted to use 20, 30, and 40-day periods prior to freeze-up and break-up dates to quantify their impact on ice duration (Fig. S4). However, possibly due to the high correlation between air temperatures over these periods or the more significant influence of cumulative temperature on river ice duration, the average temperature during the freezing period demonstrated a higher relative contribution. Therefore, in this study, we used the average temperature during the freezing period, which showed stronger correlation, for calculating relative contributions.

To highlight the geographical patterns of three factors, relative contributions of river segments were integrated as mean values within a latitude-longitude grid of 5° × 5°, and only grid cells with &gt;50 river segments were retained. It's important to note that we excluded rivers with <5 complete ice phenological observations within 22 years. This exclusion was made to avoid potential estimation bias caused by short-term fluctuations in ice phenology, and data availability improved after 2013 when Landsat 8 began acquiring more abundant imagery.

## Results

### Performance of satellite determined river ice phenologies

First, we evaluated the performance of IDLRM model on inland river segments using in situ river ice data from GLRIPD database (see Methods). There are 249 records for river freeze-up dates and 113 records for break-up dates, primarily located in North America and Europe (Fig. 3a). The validation results demonstrate a high level of consistency between the algorithm-extracted freeze-up dates (R<sup>2</sup> = 0.71, MAE = 9.5 days) and break-up dates (R<sup>2</sup> = 0.89, MAE = 8.9 days) compared to the in situ observations (Fig. 3b). It is important to note that the incomplete consistency between field measurements and remote sensing data could also be attributed to differences between the two observation methods; while field measurements were point-based, remote sensing data were based on the entire river segment (Wang et al., 2022).

Second, high-resolution Sentinel-2 MSI images were used to evaluate the freeze-up date and break-up date determined by IDLRM model. The complete freezing-thawing cycle of the Colville River within one year was shown as examples (Fig. 4 ). The example of Colville River and several other rivers in sparsely observed regions of Asia (Table S1) indicated a promising agreement between the freeze-up and break-up dates identified by the model and those depicted in high-resolution imagery. It was important to note that in Fig. 4c&g, due to the Scan Line Corrector failure of Landsat-7, observed data was limited to the upper half of the river areas. Despite these specific circumstances, the IDLRM model continues to show robust and accurate results.

![Figure 4](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr4_lrg.jpg?httpAccept=%2A%2F%2A)

An example showing river ice phenologies determined by IDLRM and comparisons between the detected river ice phenologies from Landsat and high-resolution Sentinel-2 MSI images. (a) Geographical location of a segment of the Colville River centerline in Umiat, Alaska, with Google Earth Base Map. (b) An example demonstrating how IDLRM was employed to identify freeze-up date, break-up date, and ice duration using Landsat observations. Darker points indicate a higher proportion of valid observations in the river centerline. The results show that during the winter of 2017–2018, the freeze-up date for the Colville River was October 7, 2017, and the break-up date was May 21, 2018. The potential maximum errors for freeze-up and break-up dates are 4.0 days and 7.0 days, respectively. (c-d) Landsat RGB displays the freeze-up process of the Colville River. (e-f) Freeze-up process corresponding to Landsat images with Fmask determination results. (g-h) Sentinel-2 MSI images at a 10-m resolution display the freeze-up process of the Colville River, confirming that the model-determined freeze-up and break-up dates are within the realistic range. (i-n) Break-up process displays similar to the freeze-up process in (c-h).

### Patterns and trends of river ice phenology

We present the spatial patterns of ice phenological indicators for 7970 examined river segments, including freeze-up dates (Fig. 5a), break-up dates (Fig. 5b), and ice duration (Fig. 5c), and we provide statistical analyses for Asia, North America, the Qinghai-Tibet Plateau, and the overall Northern Hemisphere region throughout the period from 2000 to 2021 (Table 1 ). The mean freeze-up date, break-up date, and ice duration for 7970 river segments in Northern Hemisphere rivers are October 24 (i.e., day of year \[DOY\] 297.5), May 4 (i.e., \[DOY\] 124.8), and 192.1 days, respectively (Fig. 5b & Table 1). The freezing regions in North America are located above latitude 35°N, with an average freeze-up date of October 20 (i.e., \[DOY\] 293.5), break-up date of May 12 (i.e., DOY 132.6), and average ice duration of 203.9 days (Table 1). In Asia, due to the presence of the Qinghai-Tibet Plateau, the southernmost latitude of freezing areas reaches 28°N, with an average freeze-up date of October 28 (i.e., DOY 301.2), break-up date of April 27 (i.e., DOY 117.7), and average ice duration of 181.4 days (Table 1). Excluding the Qinghai-Tibet Plateau region (Latitude <39°N), the ice duration of Asian and North American rivers shows a significant linear relationship with latitude (Asia: Duration = 6.4 × Lat-180.9 days, R<sup>2</sup> = 0.98; North America: Duration = 5.5 × Lat-109.6 days, R<sup>2</sup> = 0.98). At the same latitude, the ice duration of Asian rivers is slightly (An average of ∼20.0 days) longer than that of North American rivers (Fig. 5c).

![Figure 5](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr5_lrg.jpg?httpAccept=%2A%2F%2A)

River ice phenologies were identified using Landsat 5, 7, and 8 images during 2000 to 2021. The spatial distribution of the (a) mean freeze-up dates, (b) mean break-up dates, and (c) mean ice duration for the 7970 examined river segments. Gray shaded areas represent rivers with insufficient Landsat observations for effective river ice monitoring. Within these regions, the total number of ice/snow observations from 2000 to 2010 is <20 times. (d) Geographical distribution of ice duration for the 7970 river segments across latitudes, divided into two regions: Asia and North America (NA). The shaded areas indicate standard deviations at each latitude. (e) Histogram of freeze-up dates, break-up dates, and (f) ice duration for the 7970 examined river segments.

Table 1

Ice phenological indicators for rivers in Asia, North America (NA), the Qinghai-Tibet Plateau (QTP), and the overall Northern Hemisphere region (Total) throughout the period from 2000 to 2021. The indicators represent the mean values for rivers within each region. The mean multi-year linear trends (found in the “Trend” column) of the indicators are calculated using Theil–Sen Slope method, expressed in days per decade. It's important to note that when computing mean value for indicators in the Asia region, rivers from the Qinghai-Tibet Plateau are included.

| Region                | Freeze-up date / Mean value (DOY) | Freeze-up date / Trend (days per decade) | Break-up date / Mean value (DOY) | Break-up date / Trend (days per decade) | Ice duration / Mean value (days) | Ice duration / Trend (days per decade) |
| --------------------- | --------------------------------- | ---------------------------------------- | -------------------------------- | --------------------------------------- | -------------------------------- | -------------------------------------- |
| Asia<br>(*n* = 4166)  | 301.2<br>(Oct. 28)                | +3.1                                     | 117.7<br>(Apr. 27)               | −3.2                                    | 181.4                            | −6.4                                   |
| NA<br>(*n* = 3804)    | 293.5<br>(Oct. 20)                | +2.3                                     | 132.6<br>(May. 12)               | −1.8                                    | 203.9                            | −4.5                                   |
| QTP<br>(*n* = 614)    | 321.4<br>(Nov. 17)                | +4.0                                     | 94.3<br>(Apr. 4)                 | −3.6                                    | 136.7                            | −7.8                                   |
| Total<br>(*n* = 7970) | 297.5<br>(Oct. 24)                | +2.7                                     | 124.8<br>(May. 4)                | −2.5                                    | 192.1                            | −5.5                                   |

The linear trends and their significance in the ice duration of the 7970 examined river segments throughout the study period were illustrated in Fig. 6 and detailed in Table 1. More than half of the rivers (56%) exhibit a warming trend. Specifically, the average freeze-up date for the 7970 rivers is delayed by 2.7 days per decade, the break-up date is advanced by 2.5 days per decade, and the ice duration shortens by 5.5 days per decade (Table 1). Among the river segments, a number of 1229 exhibits significant linear trend changes (*P* < 0.05), with a staggering 95% of them showing a warming trend (Fig. 6a&b). About 30% of river segments demonstrate relatively stable ice duration over the 22-year period, while 14% exhibit a cooling trend, representing 5% of rivers with significant changes. Specifically, at high latitudes (i.e., latitude &gt;60°N), rivers exhibited a pronounced decrease in ice duration, surpassing 7.0 days per decade. The region of the Qinghai-Tibet Plateau showed a marked average trend of −7.8 days per decade for ice duration. River segments with a cooling trend are primarily located near 50°N and 70°N in North America, with an average extension in ice duration of 11.4 days per decade (Fig. 6c), which is likely due to ocean energy redistribution (often termed the “global warming hiatus”) (Karl et al., 2015; Medhaug et al., 2017; Sung et al., 2023).

![Figure 6](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr6_lrg.jpg?httpAccept=%2A%2F%2A)

Linear trends for 7970 river segments covering the Northern Hemisphere during 2000 to 2021. (a) The spatial distribution of the linear trend in river ice duration over 22 years, employing the Mann-Kendall test to detect significant trends and Theil–Sen Slope method to estimate the rate of change. Blue, red, and gray color represent river segments with a extension, reduction, and stable of ice duration, respectively (see detail in Methods). Dark blue and dark red respectively indicate river segments with a significantly extended and reduced ice duration (*P* < 0.05). Black indicates river segments that experienced ice cover (ice cover occurrence, i.e., ICO ≥ 2%) in the first 11 years (2000−2010) but did not observe ice cover in the last four years (ICO < 2% in 2018–2021), representing river segments that lost their ice during the study period (*n* = 181). (b) Proportion of total river segments and those with significant trends in ice duration. (c) Latitude distribution of mean linear trends in river ice duration, discussed separately for Asia and North America (NA). Shaded areas represent standard deviations at each latitude. (For interpretation of the references to color in this figure legend, the reader is referred to the web version of this article.)

Our results reveal that temperature played a dominant role during the study period, especially in regions where the winter average SAT is near 0 °C (Fig. 7a&e). The mean relative contribution of SAT is around 55%, reaching up to 70%, while the relative contributions of precipitation, solar radiation, and residuals (refer to “unexplained variation”) remain low, around 10% (Fig. 7b-d). As the winter temperature decreases, the contribution of SAT to ice duration diminishes, and relatively, the contributions of other climate factors increase (Fig. 7f). This phenomenon occurs in both Asia and North America (Fig. S5). In regions where the winter temperature is below −26 °C, the average relative contributions of SAT, solar radiation, and precipitation are around 20%, while the average relative contribution of residuals is as high as 30%.

![Figure 7](https://api.elsevier.com/content/object/eid/1-s2.0-S003442572400364X-gr7_lrg.jpg?httpAccept=%2A%2F%2A)

The impact of meteorological factors on river ice duration varies across different winter temperatures. The spatial distributions of the relative contributiuons of factors: (a) SAT, (b) Precipitation, (c) SR, and (d) residuals. All factors were averaged over a 5° × 5° grid in latitude and longitude. Only grids with sufficient river segments (i.e., &gt;5) are shown in figures. The spatial distribution of winter average temperature within the 5° × 5° grid is presented in (e). Additionally, (f) illustrates the relationship between the mean relative contributions of various factors for 7970 examined river segments and ambient temperature, with colored shadow areas representing the standard deviation of relative contributions.

## Discussion

### Analysis of river ice phenology changes and influencing factors

Our study, based on Landsat observations, provides the first comprehensive annual river ice phenology dataset for the Northern Hemisphere spanning from 2000 to 2021. Throughout the study period, we found a notable reduction in the Northern Hemisphere river ice duration at an average rate of 5.5 days per decade (freeze-up date delayed by 2.7 days per decade, break-up date advanced by 2.5 days per decade). While there may have been periods suggesting a slowdown in global warming trends (often referred to as the “global warming hiatus”) (Medhaug et al., 2017), the observed average trend in ice duration of 7970 examined river segments during this time remain nearly five times higher than those documented over the past 150 years (∼1.2 days per decade, with the freeze-up date delayed by 0.58 days per decade and the break-up date advanced by 0.65 days per decade) (Magnuson et al., 2000). Comparatively, the rate of change in river ice duration over the past two decades is more than twice that of lake ice phenology in the Northern Hemisphere (lake ice duration shortened by 2.1 days per decade, freeze-up delayed by 0.9 days per decade, and break-up advanced by 2.0 days per decade) (Wang et al., 2022). This may be attributed to the fact that lakes generally have larger water storage capacities than rivers, and their slower flow rates. A more static condition results in a comparatively more heat uptake and weaker response to climate change (Vanderkelen et al., 2020).

The Arctic Pole and Tibetan Plateau regions exhibits a more pronounced warming trend compared to other areas, which is likely associated with warming amplification. This association is potentially linked to water vapor feedback, radiative flux feedback, anthropogenic greenhouse gas emission, cloud-radiation interactions, and poleward heat/moisture transport from lower latitudes, including surface albedo feedback and increasing radiation emission (Francis and Vavrus, 2012; Pithan and Mauritsen, 2014; You et al., 2021). This is particularly evident in the strong impact of polar amplification on river freezing period during the autumn and winter seasons (Francis and Vavrus, 2012).

While we analyzed the relative contributions of three meteorological factors to river ice duration changes using the GLM and found significant variations among different rivers, the spatial partitioning based on the winter average SAT showed that in regions with higher winter SAT in the Northern Hemisphere, the relative contribution of SAT to ice duration is significantly higher than that of other meteorological factors. In high-latitude or high-altitude regions with lower winter SAT, the relative contribution of SAT decreases, and the relative contributions of precipitation and solar radiation relatively increase, along with an increase in Residuals. One plausible explanation for this phenomenon is the compensatory effect of river ice thickness, mechanical strength, and cover composition during ice cover period (Prowse et al., 2006). Numerous studies have validated the ongoing thinning of river ice thickness in response to increasing temperatures (Liu et al., 2023; Prowse et al., 2011). However, this thinning is not discernible in Landsat images. Another possibility is that in high-latitude or high-altitude regions (e.g., the Qinghai-Tibet Plateau in Asia), other predominant factors may exist beyond the three meteorological factors mentioned earlier. For example, rivers could be impacted by the influx of meltwater from glaciers, influencing both the temperature and flow of rivers (Biemans et al., 2019; Lutz et al., 2014; Xiang et al., 2018). (A basic comparison of the differences in residuals between the permafrost and non-permafrost regions are illustrated in Fig. S6).

Our results indicate that in regions with colder winter temperatures (i.e., <25 °C), the relative contributions of three meteorological factors and residuals to river ice phenologies remain at similar levels (approximately 20–30%, with a standard deviation of about 10%). This suggests that in these areas, relying solely on SAT or a few factors to determine river ice phenologies would lead to substential uncertainties. Additionally, with the intensification of global climate warming, the contribution of SAT as a factor may further increase.

### Limitations and uncertainties

The uncertainties in this study stem from mainly five sources. Firstly, uncertainties arise from the Fmask algorithm used for classifying ice pixels in Landsat imagery. Wang et al. reported an overall accuracy of 93.90% and a Kappa coefficient of 0.83 for the Fmask algorithm based on in situ records, indicating its relatively high accuracy in identifying ice pixels (Wang et al., 2021). However, due to the high reflectance characteristics of ice, the algorithm may still misclassify pixels with similar spectral signatures, such as clouds (Jeppesen et al., 2019).

Secondly, the designed revisiting period of Landsat satellites is 16 days, which may pose challenges in determining river ice phenologies. This limitation could be mitigated by utilizing combined Landsat data and large ratio of east-west overlaps (Feng and Wang, 2024). Moreover, we employed a potential maximum error threshold (i.e., 8 days) for freeze-up/break-up date to exclude results with significant uncertainties.

Thirdly, due to insufficient observations or intermittent icing, some river segments may lack observation results for certain years, particularly in the earlier years of the study period and in high-latitude regions of Europe, potentially introducing estimation biases in mean ice phenologies and multi-year trends. Consequently, only river segments with freeze-up and break-up observations for at least half of the years during the initial 8 years of the study period were included to ensure the accuracy of the analyzed dataset.

Fourthly, the limitations in the design of the IDLRM model may introduce uncertainties. On one hand, to facilitate capturing the dynamic process of freeze-up and break-up, a threshold of 0.2 was applied for snow/ice identification in Landsat imagery. Despite multiple experiments determining that 0.2 is a relatively suitable threshold, with excessively high thresholds leading to identification failure and overly low thresholds failing to eliminate noise interference, the use of this threshold may still result in slight advances or delays in extracting ice phenologies compared to previous standards (e.g., freeze-up date is defined as the date on which the water body is first observed to be completely frozen over (Beltaos et al., 2013)). On the other hand, the IDLRM model simulates the basic single freeze-up and break-up process of rivers in the Northern Hemisphere. Therefore, in special cases where there are repeated freeze-thaw cycles, the model may fail (i.e., only one freeze-up and break-up period is determined based on the weighted least squares error fit). However, this is only a possibility because the fitting in the IDLRM model uses the effective observation ratio of river centerline points as weights. Only in cases of large-scale multiple freeze-thaw events, such as when a river completely freezes in winter, then nearly completely melts, and then refreezes (i.e., two freeze-thaw cycles occur), might the model overlook the intermediate refreezing period. Nonetheless, similar to the ice phenology records in the GLRIPD database, we believe that the majority of rivers undergo a single freeze-thaw cycle, and our global river ice phenologies data can be considered an extension of the GLRIPD database.

Fifthly, there are uncertainties associated with the GRWL river dataset and its usage. RivWidth (version 0.4) was used to calculate centerline points in the GRWL database (Allen and Pavelsky, 2018; Pavelsky and Smith, 2008). This included islands and various river channels as the channel mask, which may result in inaccurate placed points and the loss of numerous centerline points through the 50% water occurrence threshold. However, this also ensured that the remaining centerline points were accurately positioned on the river, eliminating non-water body interference. Additionally, due to the 30-m spatial resolution limitation of Landsat satellites, this study only includes rivers with widths &gt;90 m, providing more accurate observations. Nonetheless, this selection criterion excludes many smaller rivers, particularly in mountainous regions (e.g., the Qinghai-Tibet Plateau). Furthermore, some of the river segments included in this study might unintentionally encompass reservoirs rather than natural river channels.

### Future perspectives

To date, certain studies have concentrated on the correlation between river ice phenologies and surface air temperature, extending their focus to the 0-degree isotherm and establishing temperature-ice relationships for simulating current or future river ice scenarios (Bennett and Prowse, 2010; Brooks et al., 2013; Prowse et al., 2010; Yang et al., 2020). In this study, we also discovered that for river segments experiencing higher winter temperatures, the relative contribution of SAT changes to ice duration variations can reach up to 80%. However, for river segments in lower winter temperature conditions, such as those near the Arctic Circle or in the Qinghai-Tibet Plateau, the relative contribution of SAT significantly decreases, while the relative contributions of precipitation, SR, and residuals increase, averaging 20%–30%, and sometimes exceeding SAT. This suggests that past simulation models for river ice cover relying solely on temperature or a few parameters may not be sufficient in some cases. Considering other meteorological factors in the models holds the potential to further optimize river ice phenological simulation results.

Due to the limitation of available Landsat data, our study utilized 22 years of observations. Despite this limitation, we believe that our findings provide valuable insights into recent trends and changes in river ice phenology. By building longer-term river ice phenology datasets using our provided methods, future research can verify our conclusions and achieve a deeper understanding.

The comprehensive river ice phenological dataset generated here provides essential parameters for fundamental physical processes within river systems, offering crucial insights for river management, hydrological disaster risk control, climate change research, and ecosystem conservation efforts. For example, through comparative analysis of ice phenologies across rivers located in diverse geographic regions, this dataset could facilitate the exploration of the impacts of varying geographical, climatic, and river-specific characteristics on ice phenology, thereby revealing underlying patterns and trends. Additionally, our dataset could also be used for the prediction of ice periods on water resource supply and hydrological disaster risks, such as low winter flows caused by water storage during freezing period, floods caused by ice jams, and sharp waves generated by ice-jam releases (Beltaos and Prowse, 2009; Cunderlik and Ouarda, 2009). This information could inform the development of corresponding management strategies. Moreover, our dataset could potentially contribute to the assessment of river ice-associated changes in correlated water environmental parameters (e.g., suspended sediment concentrations, dissolved oxygen levels, carbon dioxide emissions), especially in the context of climate change (Kämäri et al., 2015; Prowse, 2001b; Raymond et al., 2013). In addition, the dataset could further support the investigations into the effects of river ice period variations on aquatic organisms, their habitats, and ecosystem (Blackadar et al., 2020; Prowse, 2001b; Scrimgeour et al., 1994). It is also important to note that with the advancement of remote sensing technology, improvements in temporal and spatial resolution (e.g., Sentinel-2 MSI images), and increased accuracy in ice classification algorithm, the IDLRM river ice identification model proposed in this study holds promising prospects for broader applications.

## Conclusion

Using Landsat observations, our study delivered a comprehensive annual dataset on river ice phenology across the Northern Hemisphere from 2000 to 2021 at river-level for the first time. Utilizing this dataset, we analyzed the long-term variations in river ice duration and explored the relative contributions of three climate factors (surface air temperature, precipitation, and solar radiation) to interannual variations in ice duration of 7970 examined rivers. We found that, except for regions between 50°N and 70°N in North America, river ice duration has decreased across nearly all other areas, at nearly five times the documented decrease rate over the past 150 years. Notably, high-latitude polar regions and the Qinghai-Tibet Plateau experienced the most pronounced reductions in ice duration. Our results reveal significant roles of all these climate factors in shaping the multi-year trends of river ice duration. The increasing relative contribution of residuals with latitude suggested the presence of additional controlling factors beyond the three mentioned meteorological factors, such as permafrost thawing. This challenged previous approaches that focused solely on the 0-degree isotherm or used a few factors like SAT to predict river ice cover. The river ice phenology data we provide here offer an important baseline dataset to understand how climate change could affect the river system, and our proposed method holds promising prospects for future river ice identifications with higher temporal and spatial resolution satellite observations.

## CRediT authorship contribution statement

**Xinchi Wang:** Writing – original draft, Visualization, Software, Methodology, Investigation, Formal analysis. **Lian Feng:** Writing – review & editing, Supervision, Funding acquisition, Conceptualization.

## Acknowledgements

The authors thank Google Earth Engine for providing large-scale data sets and processing power. L.F. was supported by the National Natural Science Foundation of China (NOs: 42271322 and 42321004), the Guangdong Basic and Applied Basic Research Foundation (2023B1515120061) and the Shenzhen Science and Technology Program (No. KCXFZ20201221173007020). We also acknowledge the extensive comments and suggestions from three anonymous reviewers.

## Data availability

The river ice phenological dataset established in this study is available here: doi: https://doi.org/10.6084/m9.figshare.25288810.v2, including annual freeze-up date, break-up date, and ice duration for 7970 examined river segments from 2000 to 2021. The code for extracting river ice information drawing on Landsat observations spanning from 2000 to 2021 on Google Earth Engine is available here: doi: https://doi.org/10.6084/m9.figshare.25288903.v1. All other data used in this study are mentioned in section 2 of this paper and are accompanied by available links.

## References (73 total, showing 73)

1. G.H. Allen, T.M. Pavelsky. 2018. Global extent of rivers and streams. Science, 361: 585-587 [Allen and Pavelsky, 2018]

2. T. Arvidson, S. Goward, J. Gasch, D. Williams. 2006. Landsat-7 long-term acquisition plan: development and validation. Photogramm. Eng. Remote. Sens., 72: 1137-1146 [Arvidson et al., 2006]

3. S. Beltaos, B.C. Burrell. 2021. Effects of river-ice breakup on sediment transport and implications to stream environments: A review. Water, 13 [Beltaos and Burrell, 2021]

4. S. Beltaos, T. Prowse. 2009. River-ice hydrology in a shrinking cryosphere. Hydrol. Process., 23: 122-144 [Beltaos and Prowse, 2009]

5. S. Beltaos, B. Burrell, G. Ashton, S. Clark, S. Daly, J. Malenchak, R. Ettema, E. Kempema, B. Morse, T. Buffin-Bélanger, N. Bergeron, J. Dubé, A. Tuthill. 2013. River Ice Formation. (Committee on River Ice Processes and the Environment) [Beltaos et al., 2013]

6. K.E. Bennett, T.D. Prowse. 2010. Northern hemisphere geography of ice-covered rivers. Hydrol. Process., 24: 235-240 [Bennett and Prowse, 2010]

7. B. Benson, J. Magnuson, S. Sharma. 2000. Global Lake and River Ice Phenology Database, Version 1 [Data Set]. National Snow and Ice Data Center, Boulder, Colorado USA. 10.7265/n5w66hp8.dateaccessed02-20-2024 [Benson et al., 2000]

8. H. Biemans, C. Siderius, A.F. Lutz, S. Nepal, B. Ahmad, T. Hassan, W. von Bloh, R.R. Wijngaard, P. Wester, A.B. Shrestha, W.W. Immerzeel. 2019. Importance of snow and glacier meltwater for agriculture on the indo-Gangetic plain. Nature Sustainability, 2: 594-601 [Biemans et al., 2019]

9. R.J. Blackadar, C.V. Baxter, J.M. Davis, H.E. Harris. 2020. Effects of river ice break-up on organic-matter dynamics and feeding ecology of aquatic insects. River Res. Appl., 36: 480-491 [Blackadar et al., 2020]

10. M.C. Borja. 2009. An introduction to generalized linear models, 3rd edition. J. R. Stat. Soc. Ser. A Stat. Soc., 172: 695-696 [Borja, 2009]

11. R.N. Brooks, T.D. Prowse, I.J. O'Connell. 2013. Quantifying northern hemisphere freshwater ice. Geophys. Res. Lett., 40: 1128-1131 [Brooks et al., 2013]

12. J. Brown, O. Ferrians, Heginbottom, & J. A. & Melnikov, E. 2002. Circum-Arctic Map of Permafrost and Ground-Ice Conditions, Version 2. National Snow and Ice Data Center, In [Brown et al., 2002]

13. D.R.N. Brown, T.J. Brinkman, D.L. Verbyla, C.L. Brown, H.S. Cold, T.N. Hollingsworth. 2018. Changing river ice seasonality and impacts on interior Alaskan communities. Weather Climate and Society, 10: 625-640 [Brown et al., 2018]

14. D.R.N. Brown, C.D. Arp, T.J. Brinkman, B.A. Cellarius, M. Engram, M.E. Miller, K.V. Spellman. 2023. Long-term change and geospatial patterns of river ice cover and navigability in southcentral Alaska detected with remote sensing. Arct. Antarct. Alp. Res., 55 [Brown et al., 2023]

15. B.C. Burrell, G. Comfort, S. Beltaos. 2024. Considerations in the planning and design of bridges in ice-affected rivers: a review. Can. J. Civ. Eng., 51: 109-124 [Burrell et al., 2024]

16. J.L. Cohen, J.C. Furtado, M. Barlow, V.A. Alexeev, J.E. Cherry. 2012. Asymmetric seasonal temperature trends. Geophys. Res. Lett., 39 [Cohen et al., 2012]

17. S.W. Cooley, T.M. Pavelsky. 2016. Spatial and temporal patterns in Arctic river ice breakup revealed by automated ice detection from MODIS imagery. Remote Sens. Environ., 175: 310-322 [Cooley and Pavelsky, 2016]

18. J.M. Cunderlik, T. Ouarda. 2009. Trends in the timing and magnitude of floods in Canada. J. Hydrol., 375: 471-480 [Cunderlik and Ouarda, 2009]

19. E.L. DeGrandpre, M.D. DeGrandpre, B.P. Colman, H.M. Valett. 2021. Observations of river solute concentrations during ice formation. Acs Es&T Water, 1: 1695-1701 [DeGrandpre et al., 2021]

20. L. Feng, X. Wang. 2024. Quantifying cloud-free observations from Landsat missions: implications for water environment analysis. Journal of Remote Sensing, 4: 0110 [Feng and Wang, 2024]

21. L. Feng, X. Hou, Y. Zheng. 2019. Monitoring and understanding the water transparency changes of fifty large lakes on the Yangtze plain based on long-term MODIS observations. Remote Sens. Environ., 221: 675-686 [Feng et al., 2019]

22. J.A. Francis, S.J. Vavrus. 2012. Evidence linking Arctic amplification to extreme weather in mid-latitudes. Geophys. Res. Lett., 39 [Francis and Vavrus, 2012]

23. M. Fukś. 2023. Changes in river ice cover in the context of climate change and dam impacts: a review. Aquat. Sci., 85: 113 [Fukś, 2023]

24. S. Gebre, K. Alfredsen, L. Lia, M. Stickler, E. Tesaker. 2013. Review of ice effects on hydropower systems. J. Cold Reg. Eng., 27: 196-222 [Gebre et al., 2013]

25. X. Giroux-Bougard, E. Fluet-Chouinard, M.A. Crowley, J.A. Cardille, M.M. Humphries. 2023. Multi-sensor detection of spring breakup phenology of Canada's lakes. Remote Sens. Environ., 295 [Giroux-Bougard et al., 2023]

26. R.E. Horton. 1945. Erosional development of streams and their drainage basins - Hydrophysical approach to quantitative morphology. Geol. Soc. Am. Bull., 56: 275-370 [Horton, 1945]

27. F. Huang, H.T. Shen. 2024. Dam removal effect on the lower St. Regis river ice-jam floods. Can. J. Civ. Eng., 51: 215-227 [Huang and Shen, 2024]

28. J.H. Jeppesen, R.H. Jacobsen, F. Inceoglu, T.S. Toftegaard. 2019. A cloud detection algorithm for satellite imagery based on deep learning. Remote Sens. Environ., 229: 247-259 [Jeppesen et al., 2019]

29. J. Ju, D.P. Roy. 2008. The availability of cloud-free Landsat ETM+ data over the conterminous United States and globally. Remote Sens. Environ., 112: 1196-1211 [Ju and Roy, 2008]

30. M. Kämäri, P. Alho, N. Veijalainen, J. Aaltonen, M. Huokuna, E. Lotsari. 2015. River ice cover influence on sediment transportation at present and under projected hydroclimatic conditions. Hydrol. Process., 29: 4738-4755 [Kämäri et al., 2015]

31. T.R. Karl, A. Arguez, B. Huang, J.H. Lawrimore, J.R. McMahon, M.J. Menne, T.C. Peterson, R.S. Vose, H.-M. Zhang. 2015. Possible artifacts of data biases in the recent global surface warming hiatus. Science, 348: 1469-1472 [Karl et al., 2015]

32. I.M. Knack, H.T. Shen. 2018. A numerical model for sediment transport and bed change with river ice. J. Hydraul. Res., 56: 844-856 [Knack and Shen, 2018]

33. L.B. Knoll, S. Sharma, B.A. Denfeld, G. Flaim, Y. Hori, J.I. Magnuson, D. Straile, G.A. Weyhenmeyer. 2019. Consequences of lake and river ice loss on cultural ecosystem services. Limnology and Oceanography Letters, 4: 119-131 [Knoll et al., 2019]

34. H.J. Li, H.Y. Li, J. Wang, X.H. Hao. 2023. Revealing the river ice phenology on the Tibetan plateau using Sentinel-2 and Landsat 8 overlapping orbit imagery. J. Hydrol., 619 [Li et al., 2023]

35. B. Liu, H.L. Ji, Y.G. Zhai, H.C. Luo. 2023. Estimation of river ice thickness in the Shisifenzi reach of the Yellow River with remote sensing and air temperature data. Ieee Journal of Selected Topics in Applied Earth Observations and Remote Sensing, 16: 5645-5659 [Liu et al., 2023]

36. T.R. Loveland, J.L. Dwyer. 2012. Landsat: building a strong future. Remote Sens. Environ., 122: 22-29 [Loveland and Dwyer, 2012]

37. A.F. Lutz, W.W. Immerzeel, A.B. Shrestha, M.F.P. Bierkens. 2014. Consistent increase in high Asia's runoff due to increasing glacier melt and precipitation. Nat. Clim. Chang., 4: 587-592 [Lutz et al., 2014]

38. J.J. Magnuson, D.M. Robertson, B.J. Benson, R.H. Wynne, D.M. Livingstone, T. Arai, R.A. Assel, R.G. Barry, V. Card, E. Kuusisto, N.G. Granin, T.D. Prowse, K.M. Stewart, V.S. Vuglinski. 2000. Historical trends in lake and river ice cover in the northern hemisphere. Science, 289: 1743-1746 [Magnuson et al., 2000]

39. I. Medhaug, M.B. Stolpe, E.M. Fischer, R. Knutti. 2017. Reconciling controversies about the ‘global warming hiatus’. Nature, 545: 41-47 [Medhaug et al., 2017]

40. A.M.W. Newton, D.J. Mullan. 2021. Climate change and northern hemisphere lake and river ice phenology from 1931-2005. Cryosphere, 15: 2211-2234 [Newton and Mullan, 2021]

41. T.M. Pavelsky, L.C. Smith. 2004. Spatial and temporal patterns in Arctic river ice breakup observed with MODIS and AVHRR time series. Remote Sens. Environ., 93: 328-338 [Pavelsky and Smith, 2004]

42. T.M. Pavelsky, L.C. Smith. 2008. RivWidth: A software tool for the calculation of river widths from remotely sensed imagery. IEEE Geosci. Remote Sens. Lett., 5: 70-73 [Pavelsky and Smith, 2008]

43. J.F. Pekel, A. Cottam, N. Gorelick, A.S. Belward. 2016. High-resolution mapping of global surface water and its long-term changes. Nature, 540. 418-+. [Pekel et al., 2016]

44. X. Pi, L. Feng, W. Li, D. Zhao, X. Kuang, J. Li. 2020. Water clarity changes in 64 large alpine lakes on the Tibetan plateau and the potential responses to lake expansion. ISPRS J. Photogramm. Remote Sens., 170: 192-204 [Pi et al., 2020]

45. F. Pithan, T. Mauritsen. 2014. Arctic amplification dominated by temperature feedbacks in contemporary climate models. Nat. Geosci., 7: 181-184 [Pithan and Mauritsen, 2014]

46. A. Podkowa, Z. Kugler, S.V. Nghiem, G.R. Brakenridge. 2023. Ice freeze-up and break-up in Arctic Rivers observed with satellite L-band passive microwave data from 2010 to 2020. Water Resour. Res., 59 [Podkowa et al., 2023]

47. T.D. Prowse. 2001. River-ice ecology. I: hydrologic, geomorphic, and water-quality aspects. J. Cold Reg. Eng., 15: 1-16 [Prowse, 2001a]

48. T.D. Prowse. 2001. River-ice ecology. II: biological aspects. J. Cold Reg. Eng., 15: 17-33 [Prowse, 2001b]

49. T.D. Prowse, S. Beltaos. 2002. Climatic control of river-ice hydrology: a review. Hydrol. Process., 16: 805-822 [Prowse and Beltaos, 2002]

50. T.D. Prowse, B.R. Bonsal, C.R. Duguay, M.P. Lacroix. 2006. River-ice break-up/freeze-up: A review of climatic drivers, historical trends and future predictions. International Symposium on Cryospheric Indicators of Global Climate Change (pp. 443-+). Cambridge, ENGLAND [Prowse et al., 2006]

51. T. Prowse, R. Shrestha, B. Bonsal, Y. Dibike. 2010. Changing spring air-temperature gradients along large northern rivers: implications for severity of river-ice floods. Geophys. Res. Lett., 37 [Prowse et al., 2010]

52. T. Prowse, K. Alfredsen, S. Beltaos, B. Bonsal, C. Duguay, A. Korhola, J. McNamara, R. Pienitz, W.F. Vincent, V. Vuglinsky, G.A. Weyhenmeyer. 2011. Past and future changes in Arctic Lake and river ice. Ambio, 40: 53-62 [Prowse et al., 2011]

53. P.A. Raymond, J. Hartmann, R. Lauerwald, S. Sobek, C. McDonald, M. Hoover, D. Butman, R. Striegl, E. Mayorga, C. Humborg, P. Kortelainen, H. Dürr, M. Meybeck, P. Ciais, P. Guth. 2013. Global carbon dioxide emissions from inland waters. Nature, 503: 355-359 [Raymond et al., 2013]

54. E. Richards, S. Stuefer, R.C. Rangel, C. Maio, N. Belz, R. Daanen. 2023. An evaluation of GPR monitoring methods on varying river ice conditions: A case study in Alaska. Cold Reg. Sci. Technol., 210: 103819 [Richards et al., 2023]

55. P. Rokaya, L. Morales-Marin, K.E. Lindenschmidt. 2020. A physically-based modelling framework for operational forecasting of river ice breakup. Adv. Water Resour., 139 [Rokaya et al., 2020]

56. G.J. Scrimgeour, T.D. Prowse, J.M. Culp, P.A. Chambers. 1994. Ecological effects of river ice break-up - A review and perspective. Freshw. Biol., 32: 261-275 [Scrimgeour et al., 1994]

57. S.I. Seneviratne, D. Lüthi, M. Litschi, C. Schär. 2006. Land-atmosphere coupling and climate change in Europe. Nature, 443: 205-209 [Seneviratne et al., 2006]

58. H.T. Shen. 2010. Mathematical modeling of river ice processes. Cold Reg. Sci. Technol., 62: 3-13 [Shen, 2010]

59. S. Sippel, E.M. Fischer, S.C. Scherrer, N. Meinshausen, R. Knutti. 2020. Late 1980s abrupt cold season temperature change in Europe consistent with circulation variability and long-term warming. Environ. Res. Lett., 15: 094056 [Sippel et al., 2020]

60. W. Sun, B. Trevor. 2018. A stacking ensemble learning framework for annual river ice breakup dates. J. Hydrol., 561: 636-650 [Sun and Trevor, 2018]

61. W. Sun, Y. Lv, G.C. Li, Y.M. Chen. 2020. Modeling River ice breakup dates by k-nearest neighbor ensemble. Water, 12 [Sun et al., 2020]

62. M.-K. Sung, S.-I. An, J. Shin, J.-H. Park, Y.-M. Yang, H.-J. Kim, M. Chang. 2023. Ocean fronts as decadal thermostats modulating continental warming hiatus. Nat. Commun., 14: 7777 [Sung et al., 2023]

63. S.L. Tao, J.Y. Fang, X. Zhao, S.Q. Zhao, H.H. Shen, H.F. Hu, Z.Y. Tang, Z.H. Wang, Q.H. Guo. 2015. Rapid loss of lakes on the Mongolian plateau. Proc. Natl. Acad. Sci. USA, 112: 2281-2286 [Tao et al., 2015]

64. I. Vanderkelen, N.P.M. van Lipzig, D.M. Lawrence, B. Droppers, M. Golub, S.N. Gosling, A.B.G. Janssen, R. Marcé, H.M. Schmied, M. Perroud, D. Pierson, Y. Pokhrel, Y. Satoh, J. Schewe, S.I. Seneviratne, V.M. Stepanenko, Z. Tan, R.I. Woolway, W. Thiery. 2020. Global heat uptake by inland waters. Geophys. Res. Lett., 47. e2020GL087867 [Vanderkelen et al., 2020]

65. X. Wang, L. Feng, L. Gibson, W. Qi, J. Liu, Y. Zheng, J. Tang, Z. Zeng, C. Zheng. 2021. High-resolution mapping of ice cover changes in over 33,000 lakes across the north temperate zone. Geophys. Res. Lett., 48 [Wang et al., 2021]

66. X.C. Wang, L. Feng, W. Qi, X.B. Cai, Y. Zheng, L. Gibson, J. Tang, X.P. Song, J.G. Liu, C.M. Zheng, B.A. Bryan. 2022. Continuous loss of global Lake ice across two centuries revealed by satellite observations and numerical modeling. Geophys. Res. Lett., 49 [Wang et al., 2022]

67. L. Wazney, S.P. Clark, J. Malenchak, I. Knack, H.T. Shen. 2019. Numerical simulation of river ice cover formation and consolidation at freeze-up. Cold Reg. Sci. Technol., 168 [Wazney et al., 2019]

68. D. Wylie, D.L. Jackson, W.P. Menzel, J.J. Bates. 2005. Trends in global cloud cover in two decades of HIRS observations. J. Clim., 18: 3021-3031 [Wylie et al., 2005]

69. Y. Xiang, T.D. Yao, Y. Gao, G.Q. Zhang, W.C. Wang, L.D. Tian. 2018. Retreat rates of debris-covered and debris-free glaciers in the Koshi River basin, Central Himalayas, from 1975 to 2010. Environ. Earth Sci., 77 [Xiang et al., 2018]

70. X. Yang, T.M. Pavelsky, G.H. Allen. 2020. The past and future of global river ice. Nature, 577. 69-+. [Yang et al., 2020]

71. Q.L. You, Z.Y. Cai, N. Pepin, D.L. Chen, B. Ahrens, Z.H. Jiang, F.Y. Wu, S.C. Kang, R.N. Zhang, T.H. Wu, P.L. Wang, M.C. Li, Z.Y. Zuo, Y.H. Gao, P.M. Zhai, Y.Q. Zhang. 2021. Warming amplification over the Arctic pole and third pole: trends, mechanisms and consequences. Earth Sci. Rev., 217 [You et al., 2021]

72. S.X. Zhao, Q.C. Zhou, W.J. Wang, Y.J. Wu, C. Li, Q. Quan, P. Radan, Y. Tuo, T. Kolerski. 2023. Suspended-sediment transport related to ice-cover conditions during cold and warm winters, Toudaoguai stretch of the Yellow River, Inner Mongolia, China. Ecol. Indic., 153 [Zhao et al., 2023]

73. Z. Zhu, C.E. Woodcock. 2012. Object-based cloud and cloud shadow detection in Landsat imagery. Remote Sens. Environ., 118: 83-94 [Zhu and Woodcock, 2012]
