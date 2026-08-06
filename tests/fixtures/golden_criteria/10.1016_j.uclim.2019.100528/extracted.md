---
title: "A methodological assessment of extreme heat mortality modeling and heat vulnerability mapping in Dallas, Texas"
authors: "Evan Mallen, Brian Stone, Kevin Lanza"
doi: "10.1016/j.uclim.2019.100528"
source: "elsevier_xml"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 10010
---

# A methodological assessment of extreme heat mortality modeling and heat vulnerability mapping in Dallas, Texas

## Abstract

Extreme temperatures pose a significant risk to human health and are projected to worsen in a warming climate with increased intensity, duration, and frequency of heat waves in the coming decades. To mitigate heat exposure and protect sensitive populations, urban planners are increasingly using heat vulnerability indices (HVIs) to identify high priority areas for intervention and investment. Relative HVI scores help identify which areas are at greatest risk of heat-related morbidity and mortality. Public health researchers are also increasingly using observation-driven exposure-response functions to estimate heat-related mortality. In this paper, we estimate the number and spatial distribution of heat-related deaths in Dallas in 2011 employing an exposure-response function and then assess the performance of different HVI techniques in assigning vulnerability to zones of high heat mortality. Our approach estimates that 112 Dallas residents died from heat-related causes in the summer of 2011 and finds wide variability in the performance of different HVI techniques in assessing heat vulnerability by district. The HVI is found to retain more useful information mapped as separate components of vulnerability than as a single composite score. While the exposure-response function is preferred, the methods can be used in conjunction to assess appropriate heat management strategies.

## Introduction

### Heat risk

Extreme temperatures already pose a significant threat to vulnerable urban populations, resulting in clinical syndromes of heat stroke, heat exhaustion, heat syncope, heat cramps, or even death (Bouchama and Knochel, 2002; Kovats and Hajat, 2008; Luber and McGeehin, 2008). Heat waves are responsible for more deaths annually than all other weather-related hazards combined, and are expected to increase in intensity, duration, and frequency in a warming climate (Habeeb et al., 2015; Luber and McGeehin, 2008). Studies estimate between 670 and 1300 deaths related to heat in the US every year (Berko et al., 2014; Bobb et al., 2014). Heat-related mortality could increase by as much as 95% by 2050 without proper risk mitigation steps (Knowlton et al., 2007). For the country as a whole, annual heat-related deaths may increase by 28,000–34,000 additional deaths by mid-century (Voorhees et al., 2011). Projections suggest that global temperatures could reach a “novel heat regime” resulting in unprecedented climate stresses worldwide (Diffenbaugh and Scherer, 2011). But the risks associated with heat exposure are not uniform across the urban landscape. The urban heat island (UHI) can further elevate air temperatures depending on the local microclimate, and spatially distributed heat-sensitive populations result in areas of high relative risk to heat exposure. Cities in the United States and Canada currently respond to extreme heat in the short-term through early warning systems and cooling centers (Luber and McGeehin, 2008; Sheridan, 2007). In the long term, research shows that UHI mitigation strategies can measurably reduce exposure (Stone et al., 2014). But locating areas of greatest heat risk and selecting appropriate mitigation strategies can present a significant challenge.

Urban planners and other urban decision makers play a key role in enhancing local resilience to the effects of climate change. Planners have the unique ability to modify the structure and composition of the built environment in the long term and to assist in planning for short-term emergency heat response (American Planning Association, 2011). With limited resources, planners need a framework to prioritize heat management strategies to respond to localized heat vulnerability. Planners must be able to locate areas of high priority for intervention, and identify which local strategies will be most effective to reduce heat vulnerability (Gamble et al., 2018). A variety of decision support tools exist to guide these planning efforts, with varying complexity (Manangan et al., 2015). Researchers are increasingly using exposure-response models driven by public health records on mortality to estimate and project heat-related mortality at high resolution within a city (Bobb et al., 2014; Gasparrini et al. (2015); Kalkstein et al., 2011; Stone et al., 2014). However, these models use costly and computationally-intensive methods that are often beyond the capability of the urban planning practitioner. A simpler tool is the heat vulnerability index (HVI), which aggregates indicators of vulnerability into a single score to highlight relative priority for intervention. This study seeks to determine to what extent a common HVI model can reproduce exposure-response model results in the City of Dallas, Texas.

### Heat vulnerability indices

Extreme urban temperatures pose a significant risk to human health. Exposure to high temperatures can result in clinical syndromes of heat stroke, heat exhaustion, heat syncope, heat cramps, or even death (Bouchama and Knochel, 2002; Kovats and Hajat, 2008; Luber and McGeehin, 2008). One study finds that heat-related mortality could increase by as much as 95% by 2050 in the New York region without proper risk mitigation steps (Knowlton et al., 2007). For the United States as a whole, annual heat-related deaths may increase by 28,000–34,000 additional deaths by mid-century (Voorhees et al., 2011).

A population's vulnerability to environmental hazards can be characterized as a function of their exposure, sensitivity, and adaptive capacity (Eq. (1)). In the case of heat-related deaths, exposure refers to the intensity and spatial distribution of elevated temperatures. Extreme heat exposure can vary temporally through a warming climate, as temperatures steadily rise over time, or spatially through the urban heat island effect, through which some zones of a city may be significantly hotter than others. Sensitivity refers to how well a population can cope with increased exposure, or the extent to which increased exposure will affect them physically. For example, those with heat-sensitive pre-existing conditions like diabetes will have greater sensitivity to heat than those without an underlying health condition (Reid et al., 2009). A city's climate also influences local sensitivity due to acclimatization. For example, a southern city will be less sensitive to heat than a northern city, as these locations closer to the equator are more regularly exposed to higher temperatures (Curriero et al., 2002). Lastly, adaptive capacity is the ability of a population to actively mitigate or cope with increased personal exposure (Cutter et al., 2008; USGCRP, 2016). Individuals with access to mechanical air conditioning, for example, exhibit a greater adaptive capacity than those without air conditioning, independent of their sensitivity to heat. These three components of vulnerability have been shown to influence heat-related morbidity and mortality, and can be useful predictors of heat risk.

(1)

![Formula](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-fx1_lrg.jpg?httpAccept=%2A%2F%2A)

Equation 1: Components of heat vulnerability (Cutter et al., 2003; Cutter et al., 2008).

Heat Vulnerability Indices (HVIs) are one method used to determine heat vulnerability, focusing on these three components of risk. HVIs can provide a more in-depth analysis of specific risk factors associated with heat, allowing urban planners to identify areas of higher relative heat vulnerability. This tool is generally accessible to the planning practitioner, often using familiar datasets and analysis techniques. Much of the data used in HVIs are publicly available, such as through the National Land Cover Database or in the US Census (Bao et al., 2015; Wolf et al., 2015). Analysis and mapping techniques can often be run in a geographic information system.

While HVIs incorporate indicators of heat exposure, sensitivity, and adaptive capacity, they typically do not incorporate estimates of actual health outcomes, such as historical heat-related mortality counts by zone. Examples of such indicators of vulnerability include the heat island intensity by zone (exposure), proportion of elderly residents or those with pre-existing health conditions like diabetes by zone (sensitivity), or the proportion of residents living below the poverty line by zone (adaptive capacity) (Bao et al., 2015; Wolf et al., 2015).

HVIs often combine these indicators using various statistical methods into a single “score” that indicates relative risk within the study area (Bao et al., 2015; Reid et al., 2009). This score is commonly derived from a statistical procedure called principal components analysis (PCA). PCA is a variable-reduction technique that can take many potentially collinear indicators and reduce them to mutually independent factors. Each factor may be characterized depending on the indicators with which they are most strongly associated. For example, one factor may be associated with impervious surfaces, thereby characterizing the factor as “exposure.” Each geographic unit of analysis, such as a census tract, is assigned a score for each factor, often based on its z-score (i.e., statistical deviation from a mean value), and each factor score is combined to create the composite HVI score. This score is then mapped, displaying relative vulnerability across a defined geographic domain.

### Exposure-response function models

Researchers are increasingly using exposure-response functions to estimate the health impacts of environmental exposures than are difficult to directly measure (Bobb et al., 2014; Gasparrini et al. (2015); Kalkstein et al., 2011; Stone et al., 2014). For example, the number of deaths resulting from a heat wave is hard to determine directly, as the cause of death recorded on death certificates may be attributed to an underlying health condition exacerbated by extreme heat, such as a cardiovascular or respiratory illness (Harlan et al., 2013; USGCRP, 2016). As an alternative to such direct attribution approaches to quantifying heat-related mortality, health researchers are increasingly developing heat exposure-response functions, based on the established association between observed temperature and all-cause mortality over time (Bobb et al., 2014; Kalkstein et al., 2011). As illustrated in Fig. 1, all-cause mortality is often found to increase significantly during heat wave events, such as in Paris during the summer of 2003. Exposure-response functions for heat mortality are statistically derived from the association between temperature and total mortality over a fixed period of time.

![Figure 1](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-gr1_lrg.jpg?httpAccept=%2A%2F%2A)

Number of deaths during Paris heat wave (Dousset et al., 2010).

Eq. (2) summarizes how a change in mortality for a population can be predicted based on a change in heat exposure, the historical rate of all-cause mortality for a location, and an established health-response function for heat, represented as the additional mortality expected per unit change in temperature.

(2)

![Formula](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-fx2_lrg.jpg?httpAccept=%2A%2F%2A)

Equation 2: Exposure-response function applied to heat-related mortality (USGCRP, 2016).

The recent development of global datasets on the association between temperature and mortality enables both historical and projected heat mortality to be estimated for many large cities around the world. For example, Gasparrini et al. (2015) analyzed daily death counts and temperatures from 384 locations over several years to determine the relationship between mortality and temperature. From these observations, the authors determined the excess mortality per degree temperature change across the range of temperatures experienced by the locality for which the response function is derived, the third component in Eq. (2). By determining a unique exposure-response function for each location, this procedure already takes into account any behavioral and physiological acclimatization to heat and cold in the local population. Such acclimatization characteristics are well established in the literature as critical components of a local population's sensitivity to extreme temperatures (Boeckmann and Rohn, 2014; Davis et al., 2003; Hondula et al., 2014; Kalkstein and Davis, 1989; Knowlton et al., 2007; Robinson, 2001; Toloo et al., 2013). Using location-specific mortality rates and response functions provides a complete picture of a population's sensitivity to extreme temperatures and their adaptive capacity to cope with them.

Such functions can also be applied within cities to pinpoint areas that may be at risk of higher heat-related mortality, such as those with a greater urban heat island intensity. A significant impediment to developing such intra-urban scale estimates of heat mortality is an insufficient number of weather stations across cities to measure how heat exposure varies over space. While satellites provide accurate measurements of land surface temperatures, these surface temperatures have not been found to correlate highly with the near-surface air temperatures employed in heat exposure-response functions (Ho et al., 2016; Weng et al., 2011).

To address this data limitation, regional scale climate models have been used to construct a gridded surface of air temperature estimates across large urbanized regions (Stone et al., 2014). Most commonly, the Weather Research & Forecasting (WRF) model, the model often employed to develop local weather forecasts in the United States, can reliably estimate a wide range of meteorological variables including temperature, humidity, and wind speed, at a high spatial and temporal resolution (e.g., hourly estimates for every ½ kilometer grid cell).

In combination with regional climate model output on heat exposure, a heat health-response function can be used to estimate annual or event-specific heat-related mortality across a city. Stone et al. (2014) used this method to analyze heat-related mortality under various heat mitigation scenarios such as increased vegetation or albedo across three metropolitan regions, finding heat-related mortality to decrease by 50 to 99% in response to specific heat mitigation strategies. Such scenario modeling provides a decision support tool to help planning and public health practitioners design targeted interventions to reduce heat exposure and mortality in vulnerable neighborhoods, but often requires more advanced tools, such as numeric climate models, than local planners have the capacity to employ.

### Literature gaps

While HVIs can provide a low-cost approach to mapping heat vulnerability, they may not well represent actual heat risk. As a result, researchers in urban planning, public health, social vulnerability, and risk management are increasingly seeking to validate HVI methods using heat-related morbidity and mortality observations (Bao et al., 2015; Wolf et al., 2015). Exposure-response functions can provide high-resolution mortality estimates based on local observations to fill this model validation gap. However, these functions are generally less accessible to the planning practitioner because of technical demands and processing costs (Measham et al., 2011; Winkler et al., 2011). Alternatively, HVI construction is much less technically demanding and can provide useful insights into which areas have higher relative risk.

In light of these observations, this paper seeks to answer the following questions:
1.
How effective are HVIs in identifying zones of high heat-related mortality as estimated by a health-response function? Can HVIs be employed as a reliable surrogate for statistical attribution approaches to estimating heat risk?
2.
Which components of HVIs are most useful for assessing heat risk?

## Methods

### Overview

Our approach compares heat vulnerability scores from a principal components analysis (PCA) –derived HVI (Eq. (1)) to response function-driven heat-related mortality estimates (Eq. (2)). We then assess the extent to which HVIs can reproduce heat-related mortality via bivariate and multivariate regressions. We generated these models for the City of Dallas, Texas. High-resolution land cover datasets were provided by the City of Dallas and the Texas Trees Foundation to drive a regional climate model for the warm season of 2011, chosen for its unusually warm temperatures for the city.

### Mortality estimates

In order to obtain a spatially comprehensive air temperature dataset, we ran a WRF climate model at ½ km resolution over the period of May 1 through September 30 in the year 2011 over Dallas, TX. To increase model accuracy within the city, we used high-resolution land cover datasets created from classified aerial photography provided by the City of Dallas. Fig. 4 shows the results of the air temperature modeling and the population distribution used to drive the mortality calculations.

![Figure 4](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-gr4_lrg.jpg?httpAccept=%2A%2F%2A)

Vulnerability maps depicting total heat-related deaths (left), PCA HVI Score (right). Hollow tracts indicate incomplete data for HVI construction.

Mortality estimates were created using published Dallas-specific relative risk curves from a distributed lag non-linear model relating observed temperature and mortality rates from all causes over time (Gasparrini et al., 2015). Heat-related deaths are derived from excess deaths in the Dallas region for every one-degree increase in temperature in the warm season. Populations were stratified by age and sex and were assigned for each grid cell based on American Community Survey 2011–2015 5-year estimates at the census tract-level. Death rates were similarly separated into age and sex group rates, collected from 2009 to 2013 mortality data from the CDC. The populations were split between each grid cell with a centroid inside the tract. We applied the Dallas-specific exposure-response function and baseline mortality to the gridded populations as modified by the WRF-modeled mean daily temperature within each grid cell. Grid cells were assigned to census tracts by centroid and gridded mortality estimates were summed for tract-level mortality estimates.

### Heat vulnerability index

We reconstructed a heat vulnerability index using the Reid et al. (2009) PCA HVI procedure for Dallas. The vulnerability indicators are summarized in Table 1. Social vulnerability data were collected from the American Community Survey 5-year estimates (2011–2015) at the tract level from the Social Explorer website. These vulnerability indicators include population over age 65, living alone, over 65 and living alone, living below the poverty line, race other than white, and those with less than a high school education. Each variable was normalized by tract population to be used as a proportion of the tract population ranging from 0 to 1, with larger numbers implying higher vulnerability. All tracts with zero population were removed.

Table 1

Vulnerability indicators used in the principal components analysis.

| Exposure       | Sensitivity                  | Adaptive capacity               |
| -------------- | ---------------------------- | ------------------------------- |
| No green space | Over age 65                  | Living below poverty line       |
| No green space | Living alone                 | Less than high school education |
| No green space | Over age 65 and living alone | No AC access                    |
| No green space | Diabetes prevalence          | NO full AC access               |
| No green space | Race other than white        |                                 |

The primary pre-existing health variable, an indicator of population sensitivity, was diabetes prevalence. These data were downloaded from the CDC Chronic Disease and Health Promotion Open Data portal. The latest available diabetes prevalence data (2014) were used in this analysis. These data were only available for Dallas County, so tracts in the City of Dallas that lie outside Dallas County were removed from this analysis.

In following with the Reid et al. (2009) procedure, lack of green space was used as a primary heat exposure indicator. Several HVI studies include direct measures of heat exposure, such as land surface temperature or hot days (Wolf et al., 2015). However, green space has been correlated with reduced air temperatures, so lack of green space can be used as a proxy for higher heat exposure risk (Bowler et al., 2010). These data were collected from the 2011 National Land Cover Database categorical land cover data file. This dataset classifies landcover in a 30-m grid across the United States into predominant land cover classes, Including both urban and vegetative land cover types. Based on the Reid et al. (2009) method, we included the following land cover types as green space: deciduous forest, evergreen forest, mixed forest, dwarf scrub, shrub/scrub, grassland/herbaceous, sedge/herbaceous, pasture/hay, cultivated crops, woody wetlands, and emergent herbaceous wetlands. The proportion of green space coverage was determined for each tract in ArcGIS using zonal statistics. Lack of green space was defined as the reciprocal of total green space area proportion in each census tract to meet the convention of increasing indicator value implying increasing vulnerability.

Additionally, lack of access to air conditioning (AC) is an important exposure factor in this analysis. AC data was available at the parcel level from the Dallas Central Appraisal District for the year 2015. All parcels with “unassigned” AC classification were removed from the analysis (representing about 8% of all residential parcels). Any census tracts with less than a 33% complete record of residential parcel AC designation or with no residential parcels were removed from the analysis. We include two exposure indicators in our analysis: proportion of households with no AC access and proportion of households with no full AC access. Proportion of households with no AC access at all is defined as parcels within a tract with no AC divided by the total parcels for which we have data. Proportion of households with no full AC access is defined as parcels with window, wall, central, partial, or no AC divided by the total parcels for which data were available.

Principal components analysis (PCA) was employed to reduce the total number of variables to three statistically independent components, following the Reid et al. (2009) procedure. The marginal explanatory power of each component dropped significantly after three components, so three were used for this analysis. These three components explain 71.3% of the variance in the model. The PCA uses a varimax rotation to ensure orthogonality between the components. This transformation ensures that the components are statistically independent of one another and maximizes the variance of the component loadings on each variable. This process makes it easier to identify each variable with a single component, thereby enhancing the ability to classify each component as a component of vulnerability (i.e. sensitivity, exposure, or adaptive capacity) using its associated variables. All PCA processing was conducted using IBM SPSS 22. Component scores were created for each tract and were converted to z-scores to indicate vulnerability relative to other tracts. Each tract was assigned an HVI score based on the z-score for each component according to the scheme in Table 2. Since an increase in each variable implies an increase in vulnerability, higher component scores also imply higher vulnerability. Therefore, a higher z-score means greater relative vulnerability relative to the Dallas average. The composite HVI score was then defined as the sum of the HVI scores for each component.

Table 2

HVI scores assigned to each component in the PCA.

| Range of *Z*-score | Assigned HVI component score |
| ------------------ | ---------------------------- |
| −2 or lower        | 1                            |
| −2 to −1           | 2                            |
| −1 to 0            | 3                            |
| 0 to 1             | 4                            |
| 1 to 2             | 5                            |
| 2 or higher        | 6                            |

### Model comparison

Mortality estimates and HVI results were compared using two methods. Bivariate regression between mortality estimates and composite HVI scores were used to analyze the correlation between the two models across the tracts. Through a second approach, multivariate regression between mortality estimates as the dependent variable and each HVI indicator prior to the PCA analysis was used to show which indicators are statistically significant predictors of heat-related mortality as derived by the exposure-response function. In the multivariate regression, the indicator “over age 65 and living alone” was removed for potential threats of multicollinearity with “over age 65” and “living alone.” Similarly, “no AC” was removed to reduce threats of multicollinearity with “no full AC.” Regressions were run in the free software package GeoDa. Each variable in the multivariate regression were checked for threats of spatial autocorrelation by first running a bivariate regression using the OLS tool in ArcGIS of the individual variable and the total heat-related deaths, followed by the Spatial Autocorrelation (Moran's I) tool on the residuals. Each variable resulted in a statistically significant Moran's I, indicating that there is no threat of spatial autocorrelation and a spatial regression is not necessary.

## Results

### Heat-related mortality estimates

Fig. 2 shows the gridded air temperature dataset produced by the WRF model alongside the population distribution in Dallas. The model shows that on average across the warm season, some areas of Dallas are regularly over 3.5 °F (1.9 °C) warmer than the coolest areas of the city. These areas are mostly downtown in the south-central section of the city, or in the industrial corridor on the west side. The cooler areas are more indicative of the less populated areas in the south and east. This clearly shows the thermal impacts of the urban heat island. These differences in warm season average temperature translate into much greater differences in temperatures on single hot days, exceeding 15 °F (8.3 °C) on some days.

![Figure 2](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-gr2_lrg.jpg?httpAccept=%2A%2F%2A)

WRF-generated gridded air temperature (left) and total population (right) used to estimate heat-related mortality.

By adding the mortality estimates across all grid cells, the results of this analysis indicate that 112 deaths can be attributed to heat across the City of Dallas during the 2011 warm season. Fig. 3 shows the gridded heat-related mortality estimates. This shows the influence of temperature on mortality, with warmer areas estimated to have higher heat-related mortality. These results are aggregated by census tract for comparison with the HVI results. Note that the mortality is heavily influenced by the population, but is modified by air temperature. This effect can be seen in the northwestern corridor that has very low population, but high heat. This means that though the population is low, the extreme temperatures put that population at much greater risk of heat exposure.

![Figure 3](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-gr3_lrg.jpg?httpAccept=%2A%2F%2A)

Gridded heat-related mortality estimate results, reported as number of deaths per grid cell.

### Heat vulnerability index

The PCA grouped the vulnerability indicators into three independent components, shown in Table 3. The components can be roughly characterized by the strength of their correlations with each indicator. We characterized the components by any variable that has a 0.6 or higher correlation coefficient with that component. Component 1 can be characterized by lack of AC access, diabetes, and living below the poverty line. Component 2 can be characterized by elderly populations, living alone, and having less than high school education. Component 3 can be characterized by nonwhite populations and lack of green space.

Table 3

Component loading results from the principal components analysis.

| Variable                  | Component / 1 | Component / 2 | Component / 3 |
| ------------------------- | ------------- | ------------- | ------------- |
| No Full AC                | **0.866**     | −0.165        | −0.043        |
| Diabetes                  | **0.825**     | −0.094        | 0.404         |
| No AC                     | **0.800**     | 0.056         | 0.084         |
| Living Below Poverty Line | **0.641**     | −0.388        | 0.399         |
| Over 65 and Living Alone  | 0.062         | **0.903**     | −0.110        |
| Over 65                   | 0.033         | **0.843**     | −0.140        |
| Less than HS Education    | 0.568         | **−0.690**    | 0.013         |
| Living Alone              | −0.262        | 0.595         | −0.014        |
| Nonwhite                  | 0.429         | 0.008         | **0.763**     |
| No Greenspace             | 0.026         | 0.148         | **−0.744**    |

Bold indicates each component which is characterized by variables with a correlation of magnitude 0.6 or greater with that component.

While components 1 and 2 are strongly aligned with indicators of sensitivity and adaptive capacity, the third component is more characterized by our exposure variable. These components were assigned scores in accordance with Table 2, and were summed to create the final HVI score.

Fig. 4 shows the PCA HVI results in comparison with the response function mortality estimates. Note that the HVI does not always track the population distribution shown in Fig. 2. Rather, the HVI highlights new areas of the city that have a high proportion of vulnerable populations or a lack of green space. The HVI and response function results indicate different areas of the city as highly vulnerable to heat-related deaths. While the HVI results indicate greatest vulnerability in the south central areas of Dallas, the response function also includes areas in the north and east side of the city.

Table 4 shows the strength of the correlation between the two models. The bivariate spatial regressions show very little correlation between the total deaths from the response function and the HVI score, with an R<sup>2</sup> of 0.03. The multivariate regression that does not use PCA analysis shows greater correlation with the response function method with an R<sup>2</sup> of 0.4.

Table 4

Resulting R<sup>2</sup> from bivariate and multivariate regressions.

|               | Total deaths |
| ------------- | ------------ |
| Bivariate HVI | 0.03         |
| Multivariate  | 0.4          |

The multivariate regression identifies several significant predictors of total deaths, as shown in Table 5. Elderly population and less than high school education are highly significant, and no full AC and diabetes prevalence were are also significant. However, the sign of some coefficients were unexpected, including those of diabetes and no full AC. All indicators were expected to have a positive correlation with mortality estimates, but these two indicators showed a negative correlation. This could be an artifact of the aggregation of mortality estimates to the tract level. This may also be a factor not well captured by the mortality estimates, as they account for only age and sex, not pre-existing conditions that can occur at any age. Additionally, it could be that no full AC at home may not accurately predict true exposures, as residents are not always at home.

Table 5

Multivariate spatial regression results using total deaths as dependent variable.

| Variable                            | Coefficient | Std. error | t-Statistic | Probability |
| ----------------------------------- | ----------- | ---------- | ----------- | ----------- |
| Constant                            | 0.15        | 0.10       | 1.52        | 0.13        |
| No greenspace                       | 0.01        | 0.08       | 0.16        | 0.87        |
| Over 65<sup>⁎⁎</sup>                | 2.66        | 0.29       | 9.05        | 0.00        |
| Nonwhite                            | 0.13        | 0.09       | 1.42        | 0.16        |
| Living alone                        | −0.24       | 0.17       | −1.35       | 0.18        |
| Less than HS education<sup>⁎⁎</sup> | 0.30        | 0.13       | 2.32        | 0.02        |
| Living below poverty line           | −0.01       | 0.15       | −0.07       | 0.94        |
| Diabetes<sup>⁎</sup>                | −1.14       | 0.67       | −1.71       | 0.09        |
| No Full AC<sup>⁎</sup>              | −0.12       | 0.07       | −1.77       | 0.08        |

⁎⁎
Significant at ⍺ =0.05.

⁎
Significant at ⍺ =0.1.

## Discussion

This analysis resulted in substantial differences in resulting vulnerability maps. The PCA HVI had little success in predicting total mortality estimates, with very low correlation between the models. If total heat-related mortality is a primary driver of intervention priority, then this HVI may not be an appropriate decision support tool. Furthermore, multivariate regression performed much better than bivariate using only the HVI scores as shown by the much higher R(Bao et al., 2015), implying that the HVI scores may not be an adequate replacement for an exposure-response approach. The multivariate regression retained more useful information to explain why a particular area may be vulnerable, while the HVI score alone does not offer this insight. While the HVI score is designed to quickly and simply highlight areas of relative priority, the appropriate response strategy is not clear. Since all the indicators have been aggregated, no single indicator can be used to inform the type intervention for a particular area. The multivariate model found that elderly populations, those without a high school education, and those without access to full AC were significant indicators of heat-related mortality. This implies that for the City of Dallas, these dimensions are the most appropriate targets for intervention.

The multivariate model did not find lack of vegetation to be a significant predictor of heat-related mortality. This may imply that in Dallas, heat sensitivity and adaptive capacity may be more important than heat exposure in preventing heat deaths. These results suggest that caring for elderly populations and those with preexisting conditions that could be exacerbated by heat should be a high priority for intervention in Dallas. This is consistent with research encouraging elderly care during periods of high temperatures. Strategies such as daily checks by government staff, friends, or family can ensure safety of the elderly during heat events (Habeeb et al., 2015; Luber and McGeehin, 2008). Some studies recommend providing transportation to AC-equipped cooling centers, enacting a “buddy system” or hotline for heat-related health questions, and directly notifying nursing homes and senior centers (Luber et al., 2008; Sheridan, 2007).

This study shows that vulnerability assessment and model selection is critical in determining where to direct heat mitigation resources and which interventions to employ. While there was some overlap between the HVI and exposure-response function maps in identifying the most vulnerable neighborhoods, the models often greatly diverged. This shows that using one model over another as a decision support tool can direct these limited resources into completely different neighborhoods, and thus recommend that assessments of urban heat risk make use of heat exposure-response functions.

This study uses only one HVI method of many, but it highlights some important aspects of the approach for efficient heat mitigation planning. The PCA HVI method is readily accessible to planning practitioners, but the PCA itself may confound some critical information to inform planning response. In this HVI model, the variables are equally weighted and therefore assumed to be of equal importance. In reality, this may not be the case. Similarly, the equally weighted components may also be less useful in aggregate. By combining all components, the HVI shows which areas may be vulnerable, but loses the ability to answer why they are vulnerable. Additionally, the HVI method used in this paper is only one of many construction methods in the literature. Some studies have weighted the indicators prior to aggregation based on expert advice or empirical relationships in the data to local health outcomes (Bao et al., 2015). The findings in this study are therefore not intended to represent all HVI methods, but rather, highlight that the method is critical to the utility of the HVI in guiding policy and investment through an illustrative example. Furthermore, this study found that not all indicators significantly predict heat-related mortality as derived from the exposure-response method in Dallas, implying that not all indicators were necessary to include in the HVI. When assessing local vulnerability, cities should carefully consider which indicators may be most important to include for their city that can imply specific response strategies, and whether to weight them equally or with greater emphasis on particular indicators or components. We argue that keeping the indicators separate and validating with a mortality metric such as the one used in this study, planners can ascertain which specific vulnerability indicators are most important for their city and respond accordingly, and the findings may be different for each city depending on local vulnerabilities, opportunities, and needs.

One possible solution to retain this valuable information is to keep these components separate. Fig. 5 shows the exposure and sensitivity/adaptive capacity components mapped separately, as each implies a different response strategy. The areas of highest exposure may need long-term planning strategies like tree planting or encouraging lighter building materials like white roofing as found by Stone et al., (2014). In areas of high sensitivity, it may be more appropriate to focus short-term emergency response strategies like opening cooling centers or distributing water during extreme heat events. This type of mapping exercise could be effectively employed in concert with an exposure-response function to assess the magnitude of heat risk by zone and the most suitable intervention.

![Figure 5](https://api.elsevier.com/content/object/eid/1-s2.0-S2212095518300610-gr5_lrg.jpg?httpAccept=%2A%2F%2A)

HVI exposure (left) and sensitivity (right) components mapped separately.

## Conclusions

This analysis showed that a PCA HVI approach had only moderate success in aligning with the exposure-response approach. Ideally, all cities with elevated risk of heat-related mortality should establish a heat surveillance system like that of the Maricopa County Department of Public Health to identify where, when, and why vulnerable populations are dying of heat exposure and illness (Harlan et al., 2013). But this can be expensive to establish and maintain. Therefore, we recommend that in lieu of such a system, large cities should pursue the exposure-response method. This method provides a useful view of not only the unique UHI distribution for a particular city but also observation-driven insights into where vulnerable populations are most impacted by the UHI.

Absent this, the multivariate approach was found in Dallas to be superior to the bivariate HVI score, but neither are adequate in predicting total heat-related mortality. To this end, planners should utilize these approaches in tandem, using the total mortality estimates to highlight where heat intervention is most strongly recommended, but at the same time running a multivariate model of vulnerability indicators to inform which strategies may be most appropriate. Additionally, mapping factors separately can retain more useful information than a full aggregate score when utilizing PCA HVI mapping techniques. As the factors are characterized by multiple vulnerability indicators, these can highlight multiple overlapping vulnerabilities within the city. It may be more appropriate to target strategies like tree planting in an area with overlapping vulnerabilities of elderly and no greenspace, as compared to areas with elderly populations living in poverty without access to AC that may best be best served by opening cooling centers. In this way, the city can devise strategies unique to their local distribution of vulnerabilities and where they overlap the most. Together, these models can help guide both short- and long-term planning decisions to enhance local resilience to heat waves and protect vulnerable urban populations.

## Declarations of Competing Interest

None.

## References (36 total, showing 36)

1. American Planning Association. 2011. Policy Guide on Climate Change [American Planning Association, 2011]
2. J. Bao, X. Li, C. Yu. 2015. The Construction and Validation of the Heat Vulnerability Index, a Review. 7220-7234. 10.3390/ijerph120707220 [Bao et al., 2015]
3. J. Berko, D. Ingram, S. Saha, J. Parker. 2014. Deaths Attributed to Heat, Cold, and Other Weather Events in the United States, 2006–2010. National Health Statistics Reports no. 76 [Berko et al., 2014]
4. J. Bobb, R. Peng, M. Bell, F. Dominici. 2014. Heat-related mortality and adaptation to heat in the United States. Environ. Health Perspect., 122: 811-816. 10.1289/ehp.1307392 [Bobb et al., 2014]
5. M. Boeckmann, I. Rohn. 2014. Is planned adaptation to heat reducing heat-related mortality and illness? A systematic review. BMC Public Health, 13(1112): 1-13 [Boeckmann and Rohn, 2014]
6. A. Bouchama, J. Knochel. 2002. Heat stroke. N. Engl. J. Med., 346(25): 1978-1988 [Bouchama and Knochel, 2002]
7. D.E. Bowler, L. Buyung-Ali, T.M. Knight, A.S. Pullin. 2010. Urban greening to cool towns and cities: a systematic review of the empirical evidence. Landsc. Urban Plan., 97(3): 147-155. 10.1016/j.landurbplan.2010.05.006 [Bowler et al., 2010]
8. F.C. Curriero, K.S. Heiner, J.M. Samet, S.L. Zeger, L. Strug, J.A. Patz. 2002. Temperature and mortality in 11 cities of the Eastern United States. Am. J. Epidemiol., 155(1): 80-87 [Curriero et al., 2002]
9. S. Cutter, B. Boruff, W. Shirley. 2003. Social Vulnerability to Environmental Hazards. Social Science Quarterly, 84(2): 242-261 [Cutter et al., 2003]
10. S.L. Cutter, L. Barnes, M. Berry, C. Burton, E. Evans, E. Tate, J. Webb. 2008. A place-based model for understanding community resilience to natural disasters. Glob. Environ. Chang., 18(4): 598-606. 10.1016/j.gloenvcha.2008.07.013 [Cutter et al., 2008]
11. R. Davis, P. Knappenberger, P. Michaels, W. Novicoff. 2003. Changing heat-related mortality in the United States. Environ. Health Perspect., 111(14): 1712-1718. 10.1289/ehp.6336 [Davis et al., 2003]
12. N.S. Diffenbaugh, M. Scherer. 2011. Observational and model evidence of global emergence of permanent, unprecedented heat in the 20th and 21st centuries. Clim. Chang., 107(3): 615-624. 10.1007/s10584-011-0112-y [Diffenbaugh and Scherer, 2011]
13. B. Dousset, F. Gourmelon, K. Laaidi, A. Zeghnoun, E. Giraudet, P. Bretin, E. Mauri, S. Vandentorren. 2010. Satellite monitoring of summer heat waves in the Paris metropolitan area. Int. J. Climatol., 31(2): 313-323. 10.1002/joc.2222 [Dousset et al., 2010]
14. J. Gamble, M. Schmeltz, B. Hurley, J. Hseih, G. Jette, H. Wagner. 2018. Mapping the Vulnerability of Human Health to Extreme Heat in the US [Gamble et al., 2018]
15. A. Gasparrini, Y. Guo, M. Hashizume, E. Lavigne, A. Zanobetti, J. Schwartz, B. Armstrong. 2015. Mortality risk attributable to high and low ambient temperature: a multicountry observational study. Lancet, 386(9991): 369-375. 10.1016/s0140-6736(14)62114- [Gasparrini et al., 2015]
16. D. Habeeb, J. Vargo, B. Stone. 2015. Rising heat wave trends in large US cities. Nat. Hazards, 76(3): 1651-1665. 10.1007/s11069-014-1563-z [Habeeb et al., 2015]
17. Sharon L. Harlan, Juan H. Declet-Barreto, William L. Stefanov, Sarah Santana, D. Petitti. 2013. Neighborhood effects on heat deaths: social and environmental determinants of vulnerable places. Environ. Health Perspect., 121(2): 197-204. 10.1289/ehp.1104625 [Harlan et al., 2013]
18. H. Ho, A. Knudby, Y. Xu, M. Hodul, M. Aminipouri. 2016. A comparison of urban heat islands mapped using skin temperature, air temperature, and apparent temperature (Humidex), for the greater Vancouver area. Sci. Total Environ., 544: 929-938. 10.1016/j.scitotenv.2015.12.021 [Ho et al., 2016]
19. D. Hondula, J. Vanos, S. Gosling. 2014. The SSC: a decade of climate–health research and future directions. Int. J. Biometeorol., 58: 109-120. 10.1007/s00484-012-0619-6 [Hondula et al., 2014]
20. L. Kalkstein, R. Davis. 1989. Weather and human mortality: an evaluation of demographic and interregional responses in the United States. Ann. Assoc. Am. Geogr., 71(1): 44-64 [Kalkstein and Davis, 1989]
21. L. Kalkstein, S. Greene, D. Mills, J. Samenow. 2011. An evaluation of the progress in reducing heat-related human mortality in major US cities. Nat. Hazards, 56: 113-129. 10.1007/s11069-010-9552-3 [Kalkstein et al., 2011]
22. K. Knowlton, B. Lynn, R. Goldberg, C. Rosenzweig, C. Hogrefe, J. Rosenthal, P. Kinney. 2007. Projecting heat-related mortality impacts under a changing climate in the New York City region. Am. J. Public Health, 97(11): 2028-2034. 10.2105/ajph.2006.102947 [Knowlton et al., 2007]
23. R. Kovats, S. Hajat. 2008. Heat stress and public health: a critical review. Annu. Rev. Public Health, 29: 41-55. 10.1146/annurev.publhealth.29.020907.090843 [Kovats and Hajat, 2008]
24. G. Luber, M. McGeehin. 2008. Climate change and extreme heat events. Am. J. Prev. Med., 35(5): 429-435. 10.1016/j.amepre.2008.08.021 [Luber and McGeehin, 2008]
25. A.P. Manangan, C.K. Uejio, S. Saha, P.J. Schramm, G.D. Marinucci, C.L. Brown, George Luber. 2015. Assessing Health Vulnerability to Climate Change: A Guide for Health Departments [Manangan et al., 2015]
26. T.G. Measham, B.L. Preston, T.F. Smith, C. Brooke, R. Gorddard, G. Withycombe, C. Morrison. 2011. Adapting to climate change through local municipal planning: barriers and challenges. Mitig. Adapt. Strateg. Glob. Chang., 16(8): 889-909. 10.1007/s11027-011-9301-2 [Measham et al., 2011]
27. C. Reid, M. O'Neill, C. Gronlund, S. Brines, D. Brown, A. Diez-Roux, J. Schwartz. 2009. Mapping community determinants of heat vulnerability. Environ. Health Perspect., 117(11): 1730-1736. 10.1289/ehp.0900683 [Reid et al., 2009]
28. P. Robinson. 2001. On the definition of a heat wave. J. Appl. Meteorol., 40: 762-775 [Robinson, 2001]
29. S.C. Sheridan. 2007. A survey of public perception and response to heat warnings across four North American cities: an evaluation of municipal effectiveness. Int. J. Biometeorol., 52: 3-15. 10.1007/s00484-006-0052-9 [Sheridan, 2007]
30. B. Stone, J. Vargo, P. Liu, D. Habeeb, A. DeLucia, M. Trail, Y. Hu, A. Russell. 2014. Avoided heat-related mortality through climate adaptation strategies in three US cities. PLoS One, 9(6). 10.1371/journal.pone.0100852 [Stone et al., 2014]
31. G. Toloo, G. Fitzgerald, P. Aitken, K. Verrall, S. Tong. 2013. Are heat warning systems effective?. Environ. Health(27): 12. 10.1186/1476-069x-12-27 [Toloo et al., 2013]
32. US Global Change Research Program. 2016. The Impacts of Climate Change on Human Health in the United States: A Scientific Assessment. Washington DC [US Global Change Research Program, 2016]
33. A. Voorhees, N. Fann, C. Fulcher, P. Dolwick, B. Hubbell, B. Bierwagen, P. Morefield. 2011. Climate change-related temperature impacts on warm season heat mortality: a proof-of-concept methodology using BenMAP. Environ. Sci. Technol., 45: 1450-1457. 10.1021/es102820y [Voorhees et al., 2011]
34. Q. Weng, U. Rajasekar, X. Hu. 2011. Modeling urban heat islands and their relationship with impervious surface and vegetation abundance by using ASTER images. IEEE Trans. Geosci. Remote Sens., 49(10): 4080-4089 [Weng et al., 2011]
35. J.A. Winkler, G.S. Guentchev, M. Liszewska, Perdinan, P.-N. Tan. 2011. Climate scenario development and applications for local/regional climate change impact assessments: an overview for the non-climate scientist. Part II: considerations when using climate change scenarios. Geogr. Compass, 5(6): 301-328. 10.1111/j.1749-8198.2011.00426.x [Winkler et al., 2011]
36. T. Wolf, W. Chuang, G. Mcgregor. 2015. On the science-policy bridge : do spatial heat vulnerability assessment studies influence policy?. Int. J. Environ. Res. Public Health, 12: 13321-13349. 10.3390/ijerph121013321 [Wolf et al., 2015]
