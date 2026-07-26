---
title: "10.1088/1748-9326/aa9f73"
doi: "10.1088/1748-9326/aa9f73"
source: "iop_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: false
token_estimate: 13231
---

# 10.1088/1748-9326/aa9f73

**LETTER • OPEN ACCESS**

Interactions between urban heat islands and heat

waves

To cite this article: Lei Zhao et al 2018 Environ. Res. Lett. 13 034003

View the <u>article online</u> for updates and enhancements.

You may also like

- <u>Urban climate effects on extreme temperatures in Madison, Wisconsin, USA</u> Jason Schatz and Christopher J Kucharik

- <u>Reduced Urban Heat Island intensity under warmer conditions</u> Anna A Scott, Darryn W Waugh and Ben F Zaitchik

- <u>Interaction of urban heat islands and heat waves under current and future climate conditions and their mitigation using green and cool roofs in New York City and Phoenix, Arizona</u>

- Mukul Tewari, Jiachuan Yang, Hiroyuki Kusaka et al.

This content was downloaded from IP address 162.105.199.211 on 27/05/2026 at 07:19

_Environ. Res. Lett._ **13** (2018) 034003

https://doi.org/10.1088/1748-9326/aa9f73

LETTER

###### **E-mail: lei.zhao@princeton.edu**

**Keywords:** heat wave, urban heat island, surface evaporation, surface biophysical processes, climate change

Supplementary material for this article is available online

#### **Abstract**

Heat waves (HWs) are among the most damaging climate extremes to human society. Climate models consistently project that HW frequency, severity, and duration will increase markedly over this century. For urban residents, the urban heat island (UHI) effect further exacerbates the heat stress resulting from HWs. Here we use a climate model to investigate the interactions between the UHI and HWs in 50 cities in the United States under current climate and future warming scenarios. We examine UHI2m (defined as urban-rural difference in 2m-height air temperature) and UHIs (defined as urban-rural difference in radiative surface temperature). Our results show significant sensitivity of the interaction between UHI and HWs to local background climate and warming scenarios. Sensitivity also differs between daytime and nighttime. During daytime, cities in the temperate climate region show significant synergistic effects between UHI and HWs in current climate, with an average of 0.4 K higher UHI2m or 2.8 K higher UHIs during HWs than during normal days. These synergistic effects, however, diminish in future warmer climates. In contrast, the daytime synergistic effects for cities in dry regions are insignificant in the current climate, but emerge in future climates. At night, the synergistic effects are similar across climate regions in the current climate, and are stronger in future climate scenarios. We use a biophysical factorization method to disentangle the mechanisms behind the interactions between UHI and HWs that explain the spatial-temporal patterns of the interactions. Results show that the difference in the increase of urban versus rural evaporation and enhanced anthropogenic heat emissions (air conditioning energy use) during HWs are key contributors to the synergistic effects during daytime. The contrast in water availability between urban and rural land plays an important role in determining the contribution of evaporation. At night, the enhanced release of stored and anthropogenic heat during HWs are the primary contributors to the synergistic effects.

### **1. Introduction**

Among the many damaging environmental extremes, including hurricanes, floods, and tornados, heat waves

(HWs) are the deadliest in the United States (Klinenberg 2015). Assuming no acclimatization and adaptation, extreme heat stress in a changing climate has the potential to cause a substantial increase in

© 2018 The Author(s). Published by IOP Publishing Ltd

_Environ. Res. Lett._ **13** (2018) 034003

human mortality (Anderson and Bell 2011, Huang _et al_ 2011, Patz _et al_ 2005), morbidity (McGeehin and Mirabelli 2001), energy demand (Isaac and van Vuuren 2009, Sailor and Pavlova 2003), and perhaps civil conflicts (Burke _et al_ 2009, Hsiang _et al_ 2011). Higher temperatures are also projected to result in a large reduction in agricultural yield (Lobell _et al_ 2011) and livestock production (Battisti and Naylor 2009, Fuquay 1981). In recognition of these concerns, better understanding is needed of the risks of future heatwaves including physical mechanisms, temporal structure (Horton _et al_ 2015, Oleson _et al_ 2015b, Seneviratne _et al_ 2006), and potential adaptation and mitigation strategies to better manage changing risks over time (Georgescu _et al_ 2014, Rosenzweig _et al_ 2009).

Global climate models agree on the projection of increasing frequency and severity of HWs over this century (Barriopedro _et al_ 2011, Horton _et al_ 2016, Sillmann _et al_ 2013). The Fifth Assessment Report of the Intergovernmental Panel on Climate Change concluded it is ‘very likely’ that HWs will occur more often and last longer due to climate change (Pachauri _et al_ 2014). Future HWs will become more intense, more frequent and longer lasting in North America in the second half of the 21st century (Gutowski _et al_ 2008, Meehl and Tebaldi 2004, Meehl _et al_ 2009, Orlowsky and Seneviratne 2012).

More than 50% of the world’s population are now urbanresidents,andthisnumberisexpectedtoincrease to 70% by the year 2050 (Heilig 2012). The risks of heatwaves are amplified by urban heat islands (UHI) (Patz _et al_ 2005, Tan _et al_ 2010)—a phenomenon of highertemperaturesinurbanareasthaninsurrounding ruralareas.Itsintensityisusuallydefinedasurban-rural difference in 2m-height air temperature (UHI2m) or in radiative surface temperature (UHIs).

Modeling and observational studies have demonstrated a synergistic effect between UHI and HWs (Li and Bou-Zeid 2013, Li _et al_ 2015, Ramamurthy and Bou-Zeid 2017, Ramamurthy _et al_ 2017). The computational demand of mesoscale weather forecast modeling and the length and sparsity of observations limit these studies to one high-impact event or a few HWs over a limited period over a single city or a metropolitan area. Whether this synergistic effect holds for other cities and endures in a future warming climate are important yet unresolved questions. Previous studies using global climate models have either been limited to grid cell-average HWs (Coumou and Robinson 2013, Diffenbaugh and Ashfaq 2010, Fischer _et al_ 2013, Gao _et al_ 2012) or focused on the urban HWs in general rather than their synergistic effects with UHIs (Oleson _et al_ 2015a). Neither observations nor numerical simulations have directly demonstrated UHI—HW interactions at the continental scale. Zhao _et al_ (2014) demonstrates a strong interaction between local background climate and UHI in the humid eastern United States, where the UHI is higher in drier and hotter years. This analysis motivates our examination of the

synergistic effects between UHI and HWs at a large geographic scale across a range of climate conditions.

In this study, we use a sub-grid Earth system modeling strategy to investigate the spatial pattern of UHI—HW interactions. Earth system models (ESMs) are not constrained by a high computational burden, and thus can be applied over climatological timescales. In addition, ESMs capture the interactions between urban effects and the large-scale dynamics of the atmosphere. More importantly, ESMs can simulate the interactions between future greenhouse gas (GHG) warming scenarios and the biophysical drivers of UHI. These advantages of ESMs make them useful for the study of geographic patterns of the UHI—HW interactions across distinct climate regions and climate scenarios, despite their limited ability to capture some unresolved physical processes and reliance on parameterizations.

Our specific objectives include: (1) examining geospatial patterns of the synergistic interactions between UHI and HWs for cities in three climate regions in the United States under current and future climate scenarios; (2) investigating the biophysical drivers of these interactions under distinct climate regimes and different climate scenarios.

### **2. Methods**

##### **2.1. Model simulation**

We used the Community Earth System Model (CESM) (Hurrell _et al_ 2013) to simulate UHIs for 50 selected cities in the United States. We conducted simulations for present-day climate conditions (1972–2004) and two future Representative Concentration Pathway (RCP) scenarios (RCP 4.5 and 8.5 for 2005–2100) at a horizontal resolution of 0.9<sup>o</sup> latitude × 1.25<sup>o</sup> longitude. Please see the supplementary information for more details on the model simulations.

##### **2.2. UHI analysis**

We used thirty years of modeled outputs in the current-climate run (1975−2004) and two RCP runs (2071−2100) to represent the present-day and future climatology, respectively, and to analyze UHI intensity. Because the focus of this study is HWs, we restrict our analysis to summer months (June−August). We use hourly outputs at 13:00−15:00 (around midday) and 01:00−03:00 (around midnight) local time to represent daytime and nighttime conditions, respectively. These two sets of times were selected for two reasons. First, they are relatively close to the times of daily maximum and minimum temperature for most of the cities, giving a better representation of the diurnal range of the UHI. Second, the performance of the CLMand the biophysical factorization method (described in the next section) was validated against MODIS observations around these two times (close to the MODIS-Aqua overpassing times) in Zhao _et al_ (2014). We selected

2

_Environ. Res. Lett._ **13** (2018) 034003

<!-- Start of picture text -->
50<br>45<br>40<br>35<br>Local Background Climate<br>Temperate<br>30 Continental<br>Dry<br>25<br>120 110 100 90 80 70<br>Longitude (o)<br>o)<br>Latitude (<br><!-- End of picture text -->

**Figure 1.** Map of selected cities in the United States. Blue: cities in the Köppen–Geiger temperate climate region; green: cities in the Köppen–Geiger continental region; red: cities in the Köppen–Geiger dry climate region.

50 cities in the United States (figure 1) representing three Köppen–Geiger climate zones: temperate climate (21 cities, eastern and southern US), continental climate (14 cities; northeastern US) and dry climate (15 cities; arid and semiarid western US). We focus on temperate and dry regions to draw out the humidity contrasts between these two distinct zones. We also selected cities in the continental climate because they experience deadly heat as well, despite residing in an annual average colder climate (Semenza _et al_ 1996, Whitman _et al_ 1997, Houser _et al_ 2015).

We computed UHI2m (Δ _T_ 2m) and UHIs (Δ _T_ s) from the variables generated by the urban and rural sub-grids in the grid cells where our selected cities are located (please see the supplementary information for more details). Although the UHI2m and UHIs differ in various aspects and their magnitudes are not directly comparable (Arnfield 2003), the two UHIs show consistency in terms of the linear supposition property of their biophysical contributions (Zhao _et al_ 2017). One merit of UHIs compared to UHI2m is that the former has a firm and yet simple theoretical basis derived from the surface energy balance principle that underpins the biophysical factorization (described in the next section). In this study, we use this biophysical factorization method to disentangle the mechanism underlying the UHI–HW interactions.

There are multiple ways to define HWs (Perkins 2015, Perkins and Alexander 2013, Robinson 2001, Smith _et al_ 2013). We use the definition from the US National Weather Service (NWS): three or more consecutivedaysofmaximumtemperaturereachingatleast 90<sup>◦</sup> F (32.2<sup>◦</sup> C). We consider that, in each grid cell (a size on the order of 100 × 100 km), its rural sub-grid represents a local background environment for the city. Therefore, for each city we use its rural 2m-height temperature (_T_ 2m _,_ rural) to define HWs. This is consistent

with weather station observations, as weather stations are mostly located in an open landscape (World Meteorological Organization standard) similar to a rural environment. Using this definition, we divided the 30 years of daily data in each run into two groups: (i) for each city, all sets of three or more consecutive days of modeled midday _T_ 2m _,_ rural larger than 32.2<sup>◦</sup> C were defined as HW days, and their UHI intensities were denoted as UHIHW, while (ii) the remaining days were considered as normal days and hence their UHIs were denoted as UHINM.

To ensure the robustness of our analysis to the variations in HW definition, we examine two additional HW definitions (chosen arbitrarily to some extent), one absolute and one relative. The relative definition uses a relative threshold for each city to define HWs (denoted as Def-95Q) rather than a fixed number. Specifically, based on the histogram of summer daily _T_ 2m _,_ rural for each grid cell in each simulation, we define all days whose _T_ 2m _,_ rural are larger than the 95th percentile as HW days. The absolute one relaxes the minimum number of consecutive days of high temperature (90<sup>◦</sup> F) to two days (denoted as Def-2Day). We repeated our analysis for these two HW definitions to check the consistency of patterns identified in the main analysis.

##### **2.3. Biophysical factorization analysis**

Total UHIs (Δ _T_ s) can be approximated by linear supposition of various biophysical contributions: urban-rural changes in radiation balance, aerodynamic resistance, Bowen ratio, heat storage and anthropogenic heat (Zhao _et al_ 2014). More details on the calculation can be found in the supplementary information. We quantified each biophysical contribution to Δ _T_ s and compared them between normal and HW days. These evaluations were performed using 30 years

3

_Environ. Res. Lett._ **13** (2018) 034003

<!-- Start of picture text -->
(a) Daytime: present climate (c) Daytime: 2071-2100 RCP 8.5<br>(b) Nighttime: present climate (d) Nighttime: 2071-2100 RCP 8.5<br>Zone Temperate Continental Dry Sign neg. pos.<br>Magnitude (K) 0.6 1.2 1.8 2.4<br><!-- End of picture text -->

**Figure 2.** Maps of mean differences between UHI2m _,_ HW and UHI2m _,_ NM (UHI2m _,_ HW–UHI2m _,_ NM) during 1975−2004 and 2071−2100 under RCP 8.5 scenario for all selected cities. (_a_), (_b_): current climate (1975−2004); (_c_), (_d_): 2071−2100 RCP 8.5. (_a_), (_c_): daytime; (_b_), (_d_): nighttime. Blue, green and red symbols denote cities in the temperate, continental and dry climate zones, respectively. Solid and open symbols denote positive and negative values, respectively.

**Table 1.** The mean differences between UHIHW and UHINM (UHIHW–UHINM) for the selected cities in the three climate zones in current − − climate (1975 2004) and future RCP 8.5 scenario (2071 2100). (Units: K)

|||Def-N|WS|||Def-|95Q|||Def-|2Day||
|---|---|---|---|---|---|---|---|---|---|---|---|---|
||Diff in U|HI2m|Diff in|UHIs|Diff in|UHI2m|Diff in|UHIs|Diff in|UHI2m|Diff in|UHIs|
||Current|RCP85|Current|RCP85|Current|RCP85|Current|RCP85|Current|RCP85|Current|RCP85|
||||||**D**|**aytime**|||||||
|**Temperate**|0.4|−0.4|2.8|−1.1|0.3|−0.2|1.4|−0.4|0.4|−0.4|2.7|−1.2|
|**Continental**|0.2|−0.4|0.4|−1.7|0.1|−0.2|0.6|−0.4|0.3|−0.4|0.6|−1.8|
|**Dry**|0.1|0.3|−0.1|0.7|0.1|0.1|0.1|0.5|0.1|0.2|−0.4|0.7|
||||||**Ni**|**ghttime**|||||||
|**Temperate**|0.6|1.2|1.8|1.5|0.1|0.3|0.4|0.3|0.6|1.2|1.8|1.5|
|**Continental**|0.7|1.0|1.0|1.2|0.1|0.2|0.1|0.4|0.7|0.9|1.7|1.2|
|**Dry**|0.4|1.2|1.0|1.7|0.2|0.3|0.5|0.7|0.4|1.2|1.0|1.7|

of midday and midnight data from the three simulations (current: 1975–2004; RCP 4.5 and RCP 8.5: 2071–2100) over all selected cities. These analyses allow us to contrast the biophysical drivers between normal and HW days across climate conditions and scenarios.

### **3. Results and discussion**

##### **3.1. Interactions between UHI** 2m **and HWs**

We find strong diurnal and climatological signals in the interactions between UHI2m and HWs (figure 2 and table 1). During daytime, UHI2m is 0.4 ± 0.05 K (mean ± 1 standard error) or 80% higher during HW days than during normal days for cities in the

temperate climate zone (humid eastern United States) under current climate (figure 2(_a_) and 3(_a_)). UHI2m for these cities are significantly enhanced during HWs, indicating a significant synergistic effect between UHI2m and HWs. This is consistent with previous findings in Baltimore/Washington metropolitan area in the US (Li and Bou-Zeid 2013) and Beijing in China (Li _et al_ 2015). It is interesting that this synergistic effect is diminishing in future warmer climates. Near the end of this century, the average UHI2m for cities in this region is projected to be 0.3 ± 0.08 K and 0.4 ± 0.09 K lower during HWs than during normal days under RCP 4.5 and RCP 8.5, respectively (figure 3(_a_) and 2(_c_)). This indicates negative feedbacks between UHI2m and HWs in a future warmer world. Although our analysis and previous studies

4

_Environ. Res. Lett._ **13** (2018) 034003

<!-- Start of picture text -->
Daytime Nighttime<br>(a) 5 (c) 5<br>4 4<br>3 3<br>2 2<br>1 1<br>0 0<br>(b) 8 (d) 8<br>7 7<br>6 6<br>5 5<br>4 4<br>3 3<br>2 2<br>1 1<br>0 0<br>-1 -1<br>1975-2004 2071-2100 2071-2100 1975-2004 2071-2100 2071-2100<br>RCP 4.5 RCP 8.5 RCP 4.5 RCP 8.5<br>(K) (K)<br>2m 2m<br>T T<br>(K)Ts (K)Ts<br><!-- End of picture text -->

**Figure 3.** Air (ΔT2m) and surface UHI (Δ _T_ s) in summer during heat wave and normal days in current climate and future RCP scenarios. Open bars denote temperate region; solid bars denote dry region. Blue bars denote UHI in normal days; red bars denote UHI in heat wave days. (_a_), (_b_): daytime; (_c_), (_d_): nighttime. The error bar denotes ± 1 standard error.

(Oleson 2012, Zhao _et al_ 2017) have shown that different RCP scenarios have different impacts on the UHI, we find only slight difference in UHI2m–HW interactions between the two climate scenarios (figure 3(_a_)). The reason might lie in the calculation of the synergistic effects of HW and UHI. A warming scenario affects the UHI intensity in both normal and HW days, and thus part of the impacts are cancelled whenthedifferencebetweenUHI2m _,_ HW andUHI2m _,_ NM is calculated for a given warming scenario.

An opposite pattern occurs in the dry region. We ∼ find only a slight (0.06 K) higher UHI2m during HWs compared to normal days in the present-day climate during daytime (figure 2(_a_) and 3(_a_)). This difference is statistically insignificant (_p_ value _>_ 0.38), indicating anindiscerniblesynergisticeffectforcitiesinthisregion under current conditions. However, unlike those in the temperate region, the cities in the dry group show a stronger synergistic effect in future scenarios (figure 3(_a_) and 2(_c_)). Near the end of this century, the average HW exacerbation of UHI2m is projected to increase to 0.2 ± 0.06 K and 0.3 ± 0.05 K under RCP 4.5 and RCP 8.5, respectively. These numbers are statistically significant (_p_ value _<_ 0.01).

The diurnal pattern is asymmetric as well. At night, despite significant UHI2m–HW synergistic effects across climate zones and scenarios, demonstrated by solid circles in figures 2(_b_) and (_d_) and consistent higher red bars than blue bars in figure 3(_c_), there are no discernible impacts of local background climate on the effects. In the present-day climate, the nighttime UHI2m are intensified during HWs compared to normal conditions in temperate as well as dry region. Specifically, the average nighttime UHI2m

is 0.6 ± 0.2 K and 0.4 ± 0.1 K larger during HWs than during normal conditions in the temperate and dry region, respectively. These numbers are projected to increase to 1.1 ± 0.1 K (temperate) and 1.0 ± 0.0 K (dry) under RCP 4.5, and 1.2 ± 0.2 K (temperate) and 1.2 ± 0.1 K (dry) under RCP 8.5. These results indicate that the GHG warming scenarios exacerbate the nighttime UHI2m—HW synergistic effects and that these effects remain minimally impacted by the background local climate in future scenarios.

##### **3.2. Interactions between surface UHI** s **and HWs**

We also analyzed the interactions between UHIs and HWs. This indicator is important since the radiant temperature is a key component of thermal comfort to urban residents. Moreover, it is closely related to the surface energy balance and hence quite informative as a metric of the city-scale microclimate for the purposeofcomparingdifferentcitiesacrossdiverseclimate conditions.

We find that UHIs and UHI2m generally show consistent spatiotemporal patterns in their interaction with HWs, despite differing in magnitude. Figures 3(_b_) and (_d_) demonstrate the UHIs—HW interactions for cities in the two regions during daytime and nighttime under current and future climates. In the daytime, the average UHIs for temperate cities is 2.8 ± 0.8 K or 78% higher during HWs than during normal days in the present-day climate (figure 3(_b_)), indicating a significant synergistic effect. The magnitude of the effect is much larger than that estimated using UHI2m. This is as expected because UHIs is generally by nature larger than UHI2m (Nichol _et al_ 2009, Roth _et al_ 1989). Consistent with the UHI2m-HW interaction, the daytime

5

_Environ. Res. Lett._ **13** (2018) 034003

**Table 2.** Biophysical contributions to UHIs during heat wave and normal days at daytime and nighttime in present-day and future climates. (Unit: K)

||||Present-|day climate (1975−20|04)|||
|---|---|---|---|---|---|---|---|
||CLM|Calc.|<br>Radiative|<br>Convective|Evaporative|Storage|Anthropogenic|
|||||Daytime||||
|**Temperate**|2.8|1.8|−0.2|0.8|1.0|−0.7|1.0|
|**Dry**|−0.1|−0.1|0.4|0.1|−0.6|−0.5|0.5|
|||||Nighttime||||
|**Temperate**|1.8|1.0|0.0|−0.3|−0.2|0.3|1.3|
|**Dry**|1.0|0.9|0.0|0.0|0.0|0.7|0.2|
||||**RC**|**P 8.5 (2071**−**2100)**||||
||**CLM**|**Calc.**|**Radiative**|**Convective**|**Evaporative**|**Storage**|**Anthropogenic**|
|||||Daytime||||
|**Temperate**|−1.1|−0.4|−0.1|0.2|−0.9|−0.3|0.7|
|**Dry**|0.7|0.3|0.0|0.4|−1.0|−1.1|1.9|
|||||Nighttime||||
|**Temperate**|1.5|0.7|0.0|−0.4|−0.1|0.3|0.9|
|**Dry**|1.7|0.9|0.0|0.1|0.1|0.3|0.5|

synergistic effect in this region is projected to reverse in future warmer climates. Near the end of this century, the average UHIs is 0.7 ± 0.3 K and 1.0 ± 0.4 K lower during HWs than during normal days under the RCP 4.5 and RCP 8.5, respectively (figure 3(_b_)).

Cities in the dry region do not show any daytime synergistic effects under current climate. The average daytime UHIs is marginally lower during HWs than during normal days for the period 1975–2004 (figure 3(_b_)). Similar with the UHI2m-HW interaction in this region,thesynergisticeffectdevelopsinfuturewarming scenarios. The UHIs is 0.7 ± 0.2 K larger during HWs than during normal days near the end of this century under RCP 8.5 (figure 3(_b_)). At night, the synergistic effect is spatially consistent across climate regions. Undercurrentclimate,thedifferencebetweenUHIs _,_ HW and UHIs _,_ NM is 1.8 ± 0.3 K and 1.0 ± 0.2 K for cities in the temperate and dry region respectively. These numbers are projected to be 1.4 ± 0.2 K and 1.7 ± 0.1 K near the end of this century under RCP 8.5.

##### **3.3.**

Our analysis demonstrates that the spatiotemporal patterns of UHI-HW interactions are robust to different HW definitions (table 1). Although defining HW in the other two ways (Def-95Q and Def-2Day) affects the magnitude of the HW-UHI interactions, the spatiotemporal patterns agree well with results using Def-NWS. The consistency is confirmed for UHI2m and UHIs (table 1), strongly supporting the robustness of the aforementioned spatiotemporal patterns of the UHI-HW interactions.

##### **3.4. Biophysical drivers**

Although UHIs and UHI2m are fundamentally distinct concepts (Arnfield 2003), they demonstrate consistent spatiotemporal patterns in terms of their interactions with HWs (figure 3). An important advantage of UHIs is that it has a theoretical basis derived from

the surface energy balance principle that explains the contributions of the biophysical properties of urban surfaces (Zhao _et al_ 2014). Therefore, utilizing this biophysical factorization method, we can disentangle the relative importance of processes that contribute to the UHIs–HW interactions. Because of the consistency between UHIs and UHI2m, and the physical links between surface and air temperature, the physical mechanism behind the UHI2m–HW interactions can be inferred from this analysis of UHIs, but not necessarily in a direct way. For example, a large contribution of convection to the cooling of the surface (reduced UHIs–HW) would imply increased heating of the air (increased UHI2m–HW).

##### _3.4.1. Daytime_

Figure 4 illustrates the biophysical drivers of daytime UHIs during HWs and normal days in current climate and RCP 8.5. Because UHIs–HW interactions show slight differences between RCP 8.5 and RCP 4.5 (figure 3), we present the results of biophysical factorization for RCP 8.5 only. The bars of CLM-modeled ΔTs are shown in figure 4 for comparison as a validation of our biophysical factorization. Under current climate, the positive UHIs–HW synergistic effect in the temperate region primarily comes from the urban-rural difference in the contribution of evaporation (term 3 in supplementary equation (4)) and enhanced anthropogenic heat release (term 5 in equation (4)) during HWs compared to normal days (figure 4(_a_), compare the bars during HWs and normal conditions; and table 2). The contribution from evaporation to UHIs is increased by 1.0 ± 0.1 K during HWs compared to normal days and anthropogenic heat by 1.0 ± 0.2 K in the current climate. This elevated contribution of evaporation during HWs is consistent with observational (Li _et al_ 2015) and modeling studies (Li and BouZeid 2013). Over a water-sufficient surface, an increase of air temperature favors increasing latent heat flux

6

_Environ. Res. Lett._ **13** (2018) 034003

<!-- Start of picture text -->
Temperate: present climate Dry: present climate<br>(c)<br>(a) 8 3<br>Heatwave<br>Normal<br>6 2<br>4 1<br>2 0<br>0 -1<br>-2 -2<br>(b) 8 Temperate: 2071-2100 RCP 8.5 (d) 3 Dry: 2071-2100 RCP 8.5<br>6 2<br>4 1<br>2 0<br>0 -1<br>-2 -2<br>CLM Calc. Radiative Convection Evaporation Storage Anthropogenic CLM Calc. Radiative Convection Evaporation Storage Anthropogenic<br>T (K) T (K)<br>T (K) T (K)<br><!-- End of picture text -->

**Figure 4.** Biophysical contributions to UHIs during heat wave and normal days during daytime. (_a_), (_b_): temperate region; (_c_), (_d_): dry region. (_a_), (_c_): current climate; (_b_), (_d_): 2071–2100 RCP 8.5.

rather than increasing sensible heat flux (Bateni and Entekhabi 2012). In temperate climates, cities are usuallywaterlimitedduetothelargefractionofimpervious surfaces; whereas their surrounding rural surfaces are considered as water sufficient because of ample precipitation in this region. During HWs (i.e. temperature increases) evaporation is increased over urban surfaces but not increased as much as over rural surfaces, thus resulting in an enhanced contribution from evaporation to UHIs compared to normal days. The opposite occurs in the dry region under the present-day climate where urban and rural surfaces are water limited. Therefore, the enhanced evaporative contribution to UHIs is weaker for cities in this region (figure 4(_c_) and table 2). The enhanced anthropogenic heat release during HWs, present in temperate and dry climate region (figures 4(_a_)and(_c_)andtable 2),areprimarilytheresult of higher air-conditioning (AC) energy use to cope with the heat extremes (see supplementary information available at stacks.iop.org/ERL/13/034003/mmedia).

Figures 4(_b_) and (_d_) explain the future trends of UHIs–HW interactions under RCP 8.5. For cities in the temperate region, the synergistic effect is diminished in future scenarios. This is because the enhancement of evaporative contribution to the urban-rural difference during HWs compared to normal days is diminished near the end of this century under RCP 8.5 (figure 4(_b_) and table 2). The reason lies in the projected increase of precipitation in this region in future warmer climates by CESM (supplementary figure S1(_a_)). The increase of precipitation, to some extent, turns cities into watersufficient surfaces assuming that future cities have the same impervious fractions (see section 3.6), so that evaporation over cities can increase as much as over their surrounding rural surfaces when HWs come in.

The situation is relatively different in the dry region. The synergistic effect becomes stronger in future warmer climates, mainly a result of the significantly elevated anthropogenic heat release during HWs. The source of the increase in anthropogenic heat is again primarily from higher AC energy consumption to cope with the extreme heat during HWs. The evaporative contribution to ΔTs is increased during normal and HW days under future warmer climates compared to the current climate. The reason again lies in the projected increase of precipitation in future scenarios (figure S1(_b_)). In the current climate, cities and their surrounding rural areas largely lack water in this region. In future warmer climates, the water availability of rural surfaces is increased due to the increase in precipitation. The current version of CESM captures the dynamic feedbacks of vegetation to a changing climate state via its biogeochemical component (Oleson _et al_ 2010). The moisturized soil, combined with the CO2 fertilization effect and increasing air temperature, helps vegetation in rural areas develop rapidly in future climates. Rural surfaces in the dry region are no longer ‘dry’ in the future in the model. Therefore, the total rural evapotranspiration is generally increased in this region in the future. The water availability of urban surfaces, however, is much less increased than rural surfaces by the increased precipitation because of the lack of permeable surfaces in cities. Thus, the urban surfaces will remain water-limited to some extent. The lack of surface evaporative cooling over urban surfaces compared to over rural surfaces is intensified in future warmer climates. Therefore, the evaporative contributionto ΔTs isincreasedduringnormalandHW days by the end of century under RCP 8.5 compared to current climate.

7

_Environ. Res. Lett._ **13** (2018) 034003

<!-- Start of picture text -->
Temperate: present climate Dry: present climate<br>(a) (c)<br>5 5<br>Heatwave<br>Normal<br>4 4<br>3 3<br>2 2<br>1 1<br>0 0<br>-1 -1<br>(b) 5 Temperate: 2071-2100 RCP 8.5 (d) 5 Dry: 2071-2100 RCP 8.5<br>4 4<br>3 3<br>2 2<br>1 1<br>0 0<br>-1 -1<br>CLM Calc. Radiative Convection Evaporation Storage Anthropogenic CLM Calc. Radiative Convection Evaporation Storage Anthropogenic<br>T (K) T (K)<br>T (K) T (K)<br><!-- End of picture text -->

**Figure 5.** Biophysical contributions to UHIs during heat wave and normal days during nighttime. (_a_), (_b_): temperate region; (_c_), (_d_): dry region. (_a_), (_c_): current climate; (_b_), (_d_): 2071−2100 RCP 8.5.

##### _3.4.2. Nighttime_

At night, the UHIs—HWs synergistic effects are consistent across climate regions and scenarios. Figure 5 shows that this behavior is primarily the result of significantly elevated anthropogenic heat addition (term 5 in equation (4)) and increased release of stored heat (term 4 in equation (4)) during HWs. Absent solar radiation, convectiveandevaporativeprocessesarerelativelyweak at night. Therefore, contributions from these processes are in general low. This reaffirms the well-established theory that the stored heat in the urban structures and materials, and anthropogenic heat release are the dominant contributors to the UHI at night (Oke 1982). The contribution of evaporation at night comes primarily from soil evaporation (plant stomata are closed at night). Because of the comparative lack of evaporative water in the human-made urban land, soil evaporative cooling in the rural areas contributes a significant fraction to the nighttime UHI in the temperate climate (figure 5). In the dry climate, evaporation contribution to the nighttime UHI is very small (figures 5(_c_) and (_d_)) due to the fact that this term is proportional to the inverse of _𝛽_<sup>2</sup> (_𝛽_ is the Bowen ratio; see supplementary equation (4)). The enhancement of anthropogenic heat addition during HWs is again because of the higher heat released by AC cooling. The elevated release of heat storage at night is from two sources. First, it is from larger increases in heat stored during daytime in urban areas that have much higher thermal admittance compared to rural areas (Ramamurthy _et al_ 2014). The secondsourceliesinthechangesinruralthermaladmittance, which can be sensitive to soil moisture, during HWs. Urban thermal admittance is usually less subject to soil condition change because of the use of humanmade materials. Therefore, if rural soil moisture drops

during HWs (as HWs are usually accompanied by droughtsduetoaprecipitation-temperaturefeedback), theurban-ruraldifferenceinthermaladmittancewould becomelargerandthuscontributepositivelytotheUHI (Oke _et al_ 1991, Runnalls and Oke 2000).

The model captured the lag in the release of the elevated heat storage during HWs, that is, the accumulation of stored heat in urban areas in the HW period is gradually released after the atmospheric HW subsides. We find that the heat storage at daytime (stored) and nighttime (released) in the days immediately after the HWs (1−2 d after HW) are on average 5–20 W m<sup>−2</sup> greater than that in normal days. This lag effect lasts up to 2 d in the model. These results are consistent with the previous observational and modeling studies (Li and Bou-Zeid 2013, Li _et al_ 2015).

##### **3.5. Limitations**

We note four limitations of this study. First, urban land use is not dynamically represented in the current version of CESM. In other words, the urban fraction and geometry in every grid cell are fixed over time. Given that the nighttime UHI shows dependence on the morphological aspects of the city (Oke 1982, Oleson _et al_ 2008), nighttime UHI is likely to increase with urbanization in the future, unless the mitigation of UHI is explicitly taken into account in urban planning. Therefore, the simulated nighttime UHI in the two RCP scenarios in this study are likely lower bounds of the potential nighttime heat stress for growing cities in future climates. Second, although CESM can simulate the dynamic response of building energy use to the environment, its parameterization scheme in the current version is still primitive. The total anthropogenic heat in the model includes only fluxes

8

_Environ. Res. Lett._ **13** (2018) 034003

related to heating and AC, but not traffic-related heat fluxes, potentially causing a slight underestimate in anthropogenic heat. Third, local-scale processes such as advection between adjacent urban and rural land in the same grid cell are not resolved in the CESM. Therefore, impacts of changes in wind speed on the synergistic effects cannot be simulated. According to Li _et al_ (2016), an increase in urban wind speed from 0.1 to 10 m s<sup>−1</sup> during daytime under HWs would increase UHI by less than 0.3 K. Last, our results are based on simulations from one ESM under two RCP scenarios rather than multi-model ensembles. CESM is currently the only ESM that has a sufficiently detailed physicallybased urban land parameterization in CMIP5 (Phase 5 of the Coupled Model Inter-comparison Project) models. If other ESMs or future scenarios show a different trend in precipitation, the outcomes could be different.

### **4. Conclusions and implications**

This study investigated the interactions between urban heat islands (UHI) and heat waves (HWs) at a large scale under current and future warmer climates (RCP 4.5 and RCP 8.5) using a global climate model. We examined UHI2m (urban-rural difference in 2m-height air temperature) and UHIs (urban-rural difference in radiativesurfacetemperature),showingconsistentspatiotemporalpatternsbetweenUHI2m andUHIs intheir interactions with HWs. We find strong diurnal and climatologicalsignalsintheinteractions.During daytime, cities in the temperate region show significant UHI— HW synergistic effects in the current climate. These effects are projected to diminish in future scenarios (both RCP 4.5 and RCP 8.5). The opposite occurs in the dry region, where cities show no discernible synergistic effects in the current climate but significant effects in the future. Our biophysical factorization analysis demonstrates that the difference in the increase of urban-rural evaporation and enhanced anthropogenic heat during HWs are key contributors to the synergistic effects during daytime. The contrast in degree of water availability between urban and rural land plays an important role in determining the contribution of evaporation. At night, our results show similar synergistic effects across climate regions and scenarios. The enhanced release of heat storage and anthropogenic heat during HWs are the primary contributors to the synergistic effects at nighttime.

Our results underscore that, besides anthropogenic heat release, the degree of water limitation in the city plays a key role in determining the daytime UHI– HW synergistic effects in temperate and dry region under current and future climates. Urban adaptation and mitigation strategies that involve increasing the green fraction/water availability such as green roof and street vegetation (Georgescu _et al_ 2014, Li _et al_ 2014, Zhao _et al_ 2017) could help reduce

the synergistic effects. Increasing and maintaining the greenness in cities demands freshwater supply, especially for those in dry climates. Freshwater is not a free resource and is projected to become scarcer (McDonald _et al_ 2011). Additionally, HWs are usually accompanied by droughts (Fischer and Schar 2010, Seneviratne _et al_ 2006). Therefore, the cost of such strategies is a crucial consideration.

This study highlights the heat risks that urban residents face now and in the projected future. HWs have detrimental impacts on human society and natural ecosystems.TheUHI,anadditionalhotanomalyonthe climatological HW, has already aggravated heat stress on urban residents (Patz _et al_ 2005, Tan _et al_ 2010). These risks are even greater if HWs interact synergistically with UHIs. The synergistic effect that we found in thecurrentclimateexplainscontributionstothegreater risks in urban areas during HWs (Le Tertre _et al_ 2006, Vandentorren _et al_ 2004).

Healthimpactsareakeymotivationforourstudyof UHI—HW interactions on a large scale. Heat extremes have adverse impacts on human health and increase the likelihood of heat-related mortality across different regions in the world (Bobb _et al_ 2014, Huang _et al_ 2011, Kovats and Ebi 2006, O’Neill and Ebi 2009, Wu _et al_ 2014, Zanobetti _et al_ 2012). Our results can be interpreted in the context of HW mortality risk. A study based on 43 communities in the United States found that mortality risk increases as temperature increases during a HW (Anderson and Bell 2011). Using their estimates (7.9% increase in mortality risk for every 1<sup>◦</sup> C increase in average temperature during a HW), and assuming this relationship stays constant in the future, the synergistic effect alone leads to a 3.2% increase in mortality risk in the current climate for temperate cities where risk is fundamentally higher due to humid conditions (Smith _et al_ 2013). Although our results show a diminishing daytime synergistic effect in future warmer climates in this region, urban heat risk will nevertheless increase because the background climatological temperature is rising (GHG warming) and UHI and GHG warming are additive, in addition to factors thatareexpectedtoincreasevulnerabilitysuchaspopulation aging and larger numbers of people with chronic conditions that increase their susceptibility.

The nighttime synergistic effects are consistent across climate zones and scenarios. This raises greater concern as extreme high temperatures at night may be morecloselyassociatedwiththemortalityriskthandaytime (Kusaka _et al_ 2012), possibly because of the lack of relief during cooler nights (Schwartz 2005), as well as higherrelativehumidityatnight,leavingresidentswithoutair-conditioningsubjecttoextremeindoorheatand humidity. Based on the nighttime estimates in Anderson and Bell (2011), the nighttime synergistic effect in the temperate region in this study leads to an increase of 2.2% in mortality risk in current climate; this number is projected to increase to 4.3% by the end of this century under RCP 8.5.

9

_Environ. Res. Lett._ **13** (2018) 034003

### **Acknowledgments**

This research was supported by the Carbon Mitigation Initiative and a High Meadows Foundation Fellowship in the Program in Science, Technology and Environmental Policy at Princeton University (to L Z). Q Z is supported by the Director, Office of Science, Office of Biological and Environmental Research of the US Department of Energy under Contract No. DE-AC02-05CH11231 as part of their Regional and Global Climate Modeling program RUBISCO SFA project. E B Z is supported by the US National Science Foundation’s Sustainability Research Network Cooperative Agreement # 1444758 and grant # ICER 1664091. We acknowledge high-performance computing support from Yellowstone (ark:/85065/d7wd3xhc) provided by NCAR’s Computational and Information Systems Laboratory, sponsored by the US National Science Foundation. The authors declare that they have no

### **ORCID iDs**

Lei Zhao https://orcid.org/0000-0002-6481-3786 Kristie L Ebi https://orcid.org/0000-0003-4746-8236 Kaiyu Guan https://orcid.org/0000-0002-3499-6382

### **References**

- Anderson G B and Bell M L 2011 Heat waves in the United States: mortality risk during heat waves and effect modification by heat wave characteristics in 43 US communities _Environ. Health Persp._ **119** 210

- Arnfield A J 2003 Two decades of urban climate research: a review of turbulence, exchanges of energy and water, and the urban heat Island _Int. J. Climatol._ **23** 1–26

- Barriopedro D, Fischer E M, Luterbacher J, Trigo R M and Garc´ıa-Herrera R 2011 The hot summer of 2010: redrawing the temperature record map of Europe _Science_ **332** 220–4

- Bateni S and Entekhabi D 2012 Relative efficiency of land surface energy balance components _Water Resour. Res._ **48** W04510

- Battisti D S and Naylor R L 2009 Historical warnings of future food insecurity with unprecedented seasonal heat _Science_ **323** 240–4

- Bobb J F, Peng R D, Bell M L and Dominici F 2014 Heat-related mortality and adaptation to heat in the United States _Environ. Health Persp._ **122** 811–6

- Burke M B, Miguel E, Satyanath S, Dykema J A and Lobell D B 2009 Warming increases the risk of civil war in Africa _Proc. Natl Acad. Sci. USA_ **106** 20670–4

- Coumou D and Robinson A 2013 Historic and future increase in the global land area affected by monthly heat extremes _Environ. Res. Lett._ **8** 034018

- Diffenbaugh N S and Ashfaq M 2010 Intensification of hot extremes in the United States _Geophys. Res. Lett._ **37** L15701

- Fischer E M and Schar C 2010 Consistent geographical patterns of changes in high-impact European heatwaves _Nat. Geosci._ **3** 398–403

- Fischer E M, Beyerle U and Knutti R 2013 Robust spatially aggregated projections of climate extremes _Nat. Clim. Change_ **3** 1033–8

- Fuquay J W 1981 Heat-stress as it affects animal production _J. Anim. Sci._ **52** 164–74

- Gao Y, Fu J S, Drake J B, Liu Y and Lamarque J F 2012 Projected changes of extreme weather events in the eastern United States based on a high resolution climate modeling system _Environ. Res. Lett._ **7** 044025

- Georgescu M, Morefield P E, Bierwagen B G and Weaver C P 2014 Urban adaptation can roll back warming of emerging megapolitan regions _Proc. Natl Acad. Sci. USA_ **111** 2909–14

- Gutowski J _et al_ 2008 Causes of observed changes in extremes and projections of future changes _Weather and Climate Extremes in a Changing Climate, CCSP Synthesis and Assessment Product 3.3_ vol 3 (Washington, DC: US Climate Change Science Program) pp 81–116

- Heilig G K 2012 _World Urbanization Prospects: The 2011 Revision_ (New York: United Nations, Department of Economic and Social Affairs (DESA), Population Division, Population Estimates and Projections Section)

- Horton D E, Johnson N C, Singh D, Swain D L, Rajaratnam B and Diffenbaugh N S 2015 Contribution of changes in atmospheric circulation patterns to extreme temperature trends _Nature_ **522** 465

- Horton R M, Mankin J S, Lesk C, Coffel E and Raymond C 2016 A review of recent advances in research on extreme heat events _Curr. Clim. Change Rep._ **2** 242–59

- Houser T, Hsiang S, Kopp R and Larsen K 2015 _Economic Risks of Climate Change: An American Prospectus_ (New York: Columbia University Press)

- Hsiang S M, Meng K C and Cane M A 2011 Civil conflicts are associated with the global climate _Nature_ **476** 438–41

- Huang C R, Barnett A G, Wang X M, Vaneckova P, FitzGerald G and Tong S L 2011 Projecting future heat-related mortality under climate change scenarios: a systematic review _Environ. Health Persp._ **119** 1681–90

- Hurrell J W _et al_ 2013 The community earth system model a framework for collaborative research _Bull. Am. Meteorol. Soc._ **94** 1339–60

- Isaac M and van Vuuren D P 2009 Modeling global residential sector energy demand for heating and air conditioning in the context of climate change _Energ. Policy_ **37** 507–21

- Klinenberg E 2015 _Heat Wave: A Social Autopsy of Disaster in Chicago_ (Chicago, IL: University of Chicago Press)

- Kovats R S and Ebi K L 2006 Heatwaves and public health in Europe _Eur. J. Public Health_ **16** 592–9

- Kusaka H, Hara M and Takane Y 2012 Urban climate projection by the WRF model at 3 km horizontal grid increment: dynamical downscaling and predicting heat stress in the 2070’s August for Tokyo, Osaka, and Nagoya Metropolises _J. Meteorol. Soc. Japan_ **90b** 47–63

- Le Tertre A _et al_ 2006 Impact of the 2003 heatwave on all-cause mortality in 9 French cities _Epidemiology_ **17** 75–9

- Li D and Bou-Zeid E 2013 Synergistic interactions between Urban heat Islands and heat waves: the impact in cities is larger than the sum of its parts _J. Appl. Meteorol. Climatol._ **52** 2051–64

- Li D, Bou-Zeid E and Oppenheimer M 2014 The effectiveness of cool and green roofs as urban heat island mitigation strategies _Environ. Res. Lett._ **9** 055002

- Li D, Sun T, Liu M F, Wang L L and Gao Z Q 2016 Changes in wind speed under heat waves enhance Urban heat islands in the Beijing Metropolitan area _J. Appl. Meteorol. Climatol._ **55** 2369–75

- Li D, Sun T, Liu M F, Yang L, Wang L L and Gao Z Q 2015 Contrasting responses of urban and rural surface energy budgets to heat waves explain synergies between urban heat islands and heat waves _Environ. Res. Lett._ **10** 054009

- Lobell D B, Schlenker W and Costa-Roberts J 2011 Climate trends and global crop production since 1980 _Science_ **333** 616–20

- McDonald R I, Green P, Balk D, Fekete B M, Revenga C, Todd M and Montgomery M 2011 Urban growth, climate change, and freshwater availability _Proc. Natl Acad. Sci. USA_ **108** 6312–7

- McGeehin M A and Mirabelli M 2001 The potential impacts of climate variability and change on temperature-related morbidity and mortality in the United States _Environ. Health Persp._ **109** 185

- Meehl G A and Tebaldi C 2004 More intense, more frequent, and longer lasting heat waves in the 21st century _Science_ **305** 994–7

- Meehl G A, Tebaldi C, Walton G, Easterling D and McDaniel L 2009 Relative increase of record high maximum temperatures compared to record low minimum temperatures in the US _Geophys. Res. Lett._ **36** L23701

10

_Environ. Res. Lett._ **13** (2018) 034003

Nichol J E, Fung W Y, Lam K S and Wong M S 2009 Urban heat island diagnosis using ASTER satellite images and ‘ _in situ_ ’ air temperature _Atmos. Res._ **94** 276–84

- O’Neill M S and Ebi K L 2009 Temperature extremes and health: impacts of climate variability and change in the United States _J. Occup. Environ. Med._ **51** 13–25

- Oke T R 1982 The energetic basis of the Urban heat-island _Q. J. R. Meteorolog. Soc._ **108** 1–24

- Oke T R, Johnson G T, Steyn D G and Watson I D 1991 Simulation of surface Urban heat islands under Ideal conditions at night. 2. Diagnosis of causation. _Bound. Lay. Meteorol._ **56** 339–58

- Oleson K 2012 Contrasts between Urban and rural climate in

   - CCSM4 CMIP5 climate change scenarios _J. Clim._ **25** 1390–412

- Oleson K, Bonan G B, Feddema J and Vertenstein M 2008 An urban parameterization for a global climate model. Part II: sensitivity to input parameters and the simulated urban heat island in offline simulations _J. Appl. Meteorol. Climatol._ **47** 1061–76

- Oleson K _et al_ 2010 _Technical description of version 4.0 of the Community Land Model (CLM)_ NCAR Tech. Note NCAR/TN-478+STR p 257

- Oleson K W, Anderson G B, Jones B, McGinnis S A and Sanderson B 2015a Avoided climate impacts of urban and rural heat and cold waves over the US using large climate model ensembles for RCP8.5 and RCP4.5 _Clim. Change_ (https://doi.org/ 10.1007/s10584-015-1504-1)

- Oleson K W _et al_ 2015b Interactions between urbanization, heat stress, and climate change _Clim. Change_ **129** 525–41

- Orlowsky B and Seneviratne S I 2012 Global changes in extreme events: regional and seasonal dimension _Clim. Change_ **110** 669–96

- Pachauri R K _et al_ 2014 _Climate Change 2014: Synthesis Report. Contribution of Working Groups I, II and III to the Fifth Assessment Report of the Intergovernmental Panel on Climate Change_ (Geneva: IPCC)

- Patz J A, Campbell-Lendrum D, Holloway T and Foley J A 2005 Impact of regional climate change on human health _Nature_ **438** 310–7

- Perkins S E 2015 A review on the scientific understanding of heatwaves-their measurement, driving mechanisms, and changes at the global scale _Atmos. Res._ **164** 242–67

- Perkins S E and Alexander L V 2013 On the measurement of heat waves _J. Clim._ **26** 4500–17

- Ramamurthy P and Bou-Zeid E 2017 Heatwaves and urban heat islands: a comparative analysis of multiple cities _J. Geophys. Res.-Atmos._ **122** 168–78

- Ramamurthy P, Li D and Bou-Zeid E 2017 High-resolution simulation of heatwave events in New York City _Theor. Appl. Climatol._ **128** 89–102

- Ramamurthy P _et al_ 2014 Influence of subfacet heterogeneity and material properties on the Urban surface energy budget _J. Appl. Meteorol. Climatol._ **53** 2114–29

- Robinson P J 2001 On the definition of a heat wave _J. Appl. Meteorol._ **40** 762–75

- Rosenzweig C _et al_ 2009 Mitigating New York city’s heat island—integrating stakeholder perspectives and scientific evaluation _Bull. Am. Meteorol. Soc._ **90** 1297–312

- Roth M, Oke T R and Emery W J 1989 Satellite-derived urban heat islands from 3 coastal cities and the utilization of such data in urban climatology _Int. J. Remote Sens._ **10** 1699–720

- Runnalls K E and Oke T R 2000 Dynamics and controls of the near-surface heat island of Vancouver, British Columbia _Phys. Geogr._ **21** 283–304

- Sailor D J and Pavlova A 2003 Air conditioning market saturation and long-term response of residential cooling energy demand to climate change _Energy_ **28** 941–51

- Schwartz J 2005 Who is sensitive to extremes of temperature? A case-only analysis _Epidemiology_ **16** 67–72

- Semenza J C, Rubin C H, Falter K H, Selanikio J D, Flanders W D, Howe H L and Wilhelm J L 1996 Heat-related deaths during the July 1995 heat wave in Chicago _N. Engl. J. Med._ **335** 84–90

- Seneviratne S I, Luthi D, Litschi M and Schar C 2006

   - Land-atmosphere coupling and climate change in Europe _Nature_ **443** 205–9

- Sillmann J, Kharin V V, Zwiers F W, Zhang X and Bronaugh D 2013 Climate extremes indices in the CMIP5 multimodel ensemble: Part 2. Future climate projections _J. Geophys. Res.: Atmos._ **118** 2473–93

- Smith T T, Zaitchik B F and Gohlke J M 2013 Heat waves in the United States: definitions, patterns and trends _Clim. Change_ **118** 811–25

- Tan J _et al_ 2010 The urban heat island and its impact on heat waves and human health in Shanghai _Int. J. Biometeorol._ **54** 75–84

- Vandentorren S, Suzan F, Medina S, Pascal M, Maulpoix A, Cohen J C and Ledrans M 2004 Mortality in 13 French cities during the August 2003 heat wave _Am. J. Public Health_ **94** 1518–20

- Whitman S, Good G, Donoghue E R, Benbow N, Shou W and Mou S 1997 Mortality in Chicago attributed to the July 1995 heat wave _Am. J. Public Health_ **87** 1515–8

- Wu J Y _et al_ 2014 Estimation and uncertainty analysis of impacts of future heat waves on mortality in the Eastern United States _Environ. Health Persp._ **122** 10–6

- Zanobetti A, O’Neill M S, Gronlund C J and Schwartz J D 2012 Summer temperature variability and long-term survival among elderly people with chronic disease _Proc. Natl Acad. Sci. USA_ **109** 6608–13

- Zhao L, Lee X, Smith R B and Oleson K 2014 Strong contributions of local background climate to urban heat islands _Nature_ **511** 216–9

- Zhao L, Lee X, Schultz N M and Oppenheimer M 2017 A wedge strategy for mitigation of urban warming in future climate scenarios _Atmos. Chem. Phys._ **17** 9067–80

11
