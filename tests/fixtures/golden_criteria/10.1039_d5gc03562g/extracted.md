---
title: "Photocatalytic upcycling of PET into methane, hydrogen and high-value liquid products"
authors: "Weisweiller, Madeline, Ertl, Adrian, von Baeckmann, Cornelia, Sihag, Anil Kumar, Pichler, Christian M., Kleitz, Freddy, Eder, Dominik, Cherevan, Alexey"
doi: "10.1039/d5gc03562g"
source: "rsc_html"
acquisition:
  provider: "rsc"
  route: "browser_html"
  representation: "html"
  transport: "browser"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 8954
---

# Photocatalytic upcycling of PET into methane, hydrogen and high-value liquid products

## Abstract

The harmful effects of daily plastic use are increasingly evident, with most waste burned or landfilled, leading to the formation of microplastics that pollute the environment and the food chain. While the full impact remains unclear, photoreforming of plastics has emerged as a promising sustainable abatement method. This study demonstrates the commercial potential of P25 TiO<sub>2</sub> towards photocatalytic upcycling of polyethylene terephthalate (PET) microplastics by systematic exploration of the effect of co-catalysts, reaction temperature and oxygen presence on the generation of solar fuels and high-value liquid products. We demonstrate that while neat P25 yields minimal H<sub>2</sub> evolution, increasing the reaction temperature enhances its production significantly, and the addition of Pt further boosts H<sub>2</sub> generation by four orders of magnitude, resulting in 15.35 µmol h<sup>−1</sup> of H<sub>2</sub> and apparent quantum yield (AQY) values up to 0.45%. On par with H<sub>2</sub>, we observe the generation of CH<sub>4</sub> from the reaction mixture, which we conclude to originate directly from PET rather than hydrogenation reactions. Liquid-phase analysis reveals diverse photoreforming products, including acetic acid, oxalic acid, formic acid and ethanol, with selectivity influenced by catalyst composition and reaction conditions. The feasibility of large-scale application of the process is further validated through prolonged irradiation tests using solar-simulated light and an upscaled setup, which demonstrate remarkable AQYs reaching 0.84%. These findings suggest PET photoreforming as a promising route for producing solar fuels and valuable chemicals, paving the way for sustainable plastic processing and upcycling.

## Visual Abstract

![Figure](body_assets/m_d5gc03562g-ga.png)

We systematically study the key process parameters of polyethylene terephthalate (PET) microplastic photoreforming. We uncover that not only hydrogen (H<sub>2</sub>) but also methane (CH<sub>4</sub>) is generated and provide valuable mechanistic insights into the process.

### Green foundation

1. Our study demonstrates a significant advancement in photoreforming PET microplastics using P25 TiO<sub>2</sub>, transforming plastic waste into valuable solar fuels and chemicals, thus promoting sustainable waste management.

2. We achieved a notable boost in hydrogen generation by up to four orders of magnitude through the addition of Pt to P25 TiO<sub>2</sub>, resulting in H<sub>2</sub> production rates of 15.35 μmol h<sup>−1</sup> and AQY values reaching 0.45%. Additionally, we observed significant CH<sub>4</sub> production and the conversion of PET into high-value liquid products such as acetic acid, oxalic acid, formic acid, and ethanol, demonstrating a viable route for converting plastic waste into valuable chemicals.

3. Future work should focus on optimizing the catalytic system to reduce noble metal use, exploring greener solvents, and conducting scalability studies to enhance sustainability and economic viability.

## Introduction

Plastics are ubiquitous materials, embedded in everyday life, bearing countless beneficial properties, such as light weight, cost-efficiency and aimed straightforward synthesis for various purposes.<sup>1</sup> Although used for a plethora of applications and representing a great part of the world's economy,<sup>2,3</sup> only a few abatement strategies are presently employed. A vast majority of plastic waste is simply discarded in landfills,<sup>4</sup> gradually degrading to microplastic particles, down to 1000 nm in size.<sup>5</sup> As a consequence, the environment and waters are contaminated<sup>6</sup> and the full ramifications are yet to be elucidated.<sup>7</sup> This issue has inspired the research community to investigate the applicability of photocatalysis for efficient conversion of microplastic, providing an opportunity to degrade the synthetic macromolecules and concurrently obtain green H<sub>2</sub> – a sustainable fuel promising high energy densities without the worry of greenhouse gas emission<sup>8,9</sup> – solely with the assistance of light. Initial success was already achieved in the early 1980s by Kawai and Sakata,<sup>10–12</sup> converting saccharose, starch and cellulose to H<sub>2</sub> with a mixture of RuO<sub>2</sub>/TiO<sub>2</sub>/Pt as a photocatalyst and in alkaline media.<sup>11</sup> Their research was subsequently expanded exploring a wide range of organic substrates, including insect remains, polyvinyl chloride, excrements, algae and various carbohydrates. The employed TiO<sub>2</sub>/Pt catalyst showed promising results, yielding up to 1130 µmol of H<sub>2</sub> in 10 hours.<sup>10</sup> This now revisited concept, also known as photoreforming,<sup>13</sup> has attracted a lot of interest in recent years, demonstrating successful photocatalytic valorisation of various organic compounds, such as cellulose<sup>14–18</sup> polylactic acid (PLA)<sup>19–21</sup> or polyethylene terephthalate (PET).<sup>19,20,22–24</sup> A lot of work appeared involving TiO<sub>2</sub> and its various polymorphs due to their commercial availability.<sup>25–28</sup> Many insights into the photoreforming process have been provided by the group of Reisner *et al.* who investigated different visible light active photocatalysts, setups and substrates.<sup>14,17,19,20,22,24,29</sup> In addition, a pretreatment methodology was established for an array of substrates ranging from microplastics to biomass constituents, oftentimes involving alkaline media, to enhance the degradation output and product yield of their studied systems.<sup>19</sup> However, the use of high pH represents a bottleneck for currently applied materials, as it may interfere with the photocatalyst's long-term stability and would demand more resources.<sup>13,30</sup> The extent of the impact of the strong basic conditions on the viability of the overall process is yet to be explored.

It is common that a synthetic macromolecule featuring polar bonds, such as PET or PLA, is selected as a model waste plastic, as these structures contain heteroatoms in the main chain that facilitate hydrolysis and subsequent upcycling.<sup>31</sup> Although copious studies have investigated PET as a substrate,<sup>28,32–36</sup> and thus provided a good base of knowledge on product formation and potential mechanisms, the current insights are still limited, as no systematic studies have been presented thus far. Furthermore, the focus of previous research works was often set on H<sub>2</sub> production, rather than evaluating other gaseous products, such as CH<sub>4</sub>.<sup>15,16,34</sup> A detailed investigation of PET photoreforming would further enhance our comprehension of this type of photocatalytic conversion, enabling new possibilities for its commercialisation. Product selectivity and the choice of the optimal, cost-efficient and sustainable visible light active photocatalyst, yielding high conversion outputs, are challenges that yet remain.<sup>13</sup>

While the majority of studies in this field of plastic photoreforming rather develop novel visible light active materials,<sup>14,21,37</sup> we put our focus on the investigation of the very well-established TiO<sub>2</sub> material.<sup>38–41</sup> This photocatalyst has been studied for decades and provides a suitable model system, allowing us to investigate the process parameters and reaction mechanism. In the last few decades, numerous co-catalysts have been developed to address the challenges of direct water splitting.<sup>42–45</sup> The use of such an auxiliary is also expected to promote photoreforming and result in higher H<sub>2</sub> production rates.<sup>46</sup> In a similar manner, increased temperature has shown to facilitate hydrolysis of the plastic source and affect catalytic rates,<sup>47</sup> while control of the reaction atmosphere (aerobic *vs.* anaerobic) can be expected to impact reactive oxygen species generation and type. This study aims an in-depth exploration of each of these parameters on the photoreforming outcomes of PET microplastic powders exposed to 1 M NaOH and under UV irradiation. Our results highlight the beneficial effects of the noble metal co-catalyst Pt and elevated temperature on the formation of H<sub>2</sub> and CH<sub>4</sub>. We further elucidate the potential origin of CH<sub>4</sub> and examine the use of different light sources and process scales to provide a deeper understanding of underlying mechanisms and commercialisation prospects. Liquid phase analysis confirms successful photoconversion of ethylene glycol (EG) from PET to acetic acid (AA), oxalic acid (OA), formic acid (FA) and ethanol. This comprehensive investigation offers valuable insights to encourage implementation of this sustainable abatement strategy in the near future.

## Results and discussion

### Synthesis and characterisation

The P25-Pt photocatalyst was obtained by photodeposition of commercial P25 powder with H<sub>2</sub>PtCl<sub>6</sub> solution, aiming at 1 wt% of the noble metal loading (details in Experimental). After successful photodeposition, noticeable from a colour change from white to grey, the elemental composition of the photocatalyst was characterised *via* total X-ray fluorescence (TXRF) (Fig. 1a), revealing a Pt loading of 0.998 wt% with respect to TiO<sub>2</sub>. Scanning electron microscopy (SEM) (Fig. S3) and transmission electron microscopy (TEM) (Fig. 1d and e) analyses further demonstrate the prime particle size of TiO<sub>2</sub> nanoparticles to be ∼24.9 nm and confirm the homogeneous distribution of Pt nanoclusters with an average size of 4.05 nm – typically expected from the photodeposition process from \[PtCl<sub>4</sub>\]<sup>2−</sup> – on the titania surface.<sup>48</sup> Diffuse reflectance spectroscopy (DRS) measurements and subsequent Kubelka–Munk (KM) analysis *via* the Tauc function<sup>49</sup> (Fig. 1b and c) illustrate the expected absorption profile of P25, from which two band gap values of 3.08 and 3.18 eV – characteristic of the rutile–anatase mixed phase TiO<sub>2</sub> – can be extracted. Loading of P25 with Pt nanoparticles results in continuous increase of its absorption profile throughout the UV-Vis region; however, virtually unchanged band gap values (3.13 and 3.19 eV, respectively) can be derived using a modified Tauc method, suggesting that the deposition did not affect the structure or optoelectronic properties of the supporting TiO<sub>2</sub>.<sup>50</sup> The crystallinity of neat P25 and P25-Pt samples was investigated *via* powder X-ray diffraction (XRD) analysis (Fig. 1f). The diffractograms show virtually identical characteristic peaks of both anatase and rutile phases (89.3: 10.7% for P25 and 90: 10% for P25-Pt), whereas no additional peak related to Pt is visible in the pattern of P25-Pt expected from its low mass loading. We further note that Pt deposition on TiO<sub>2</sub> leads to expected photoluminescence (PL) quenching (Fig. S2), which is commonly attributed to the created heterojunction at which the metallic Pt extracts photoexcited charges from the semiconducting support.

![Figure 1](body_assets/m_d5gc03562g-f1.png)

**Fig. 1** Characterisation of the prepared photocatalysts: (a) TXRF spectrum of P25-Pt confirming successful deposition of 1 wt% Pt onto P25, depicting the characteristic peaks for Pt (L<sub>α</sub>: 9.44; L<sub>β</sub>: 11.07) and Ti (K<sub>α</sub>: 4.51; K<sub>β</sub>: 4.93), (b) UV-vis DRS and (c) KM analysis of neat P25 and P25 with 1 wt% Pt as the co-catalyst, (d and e) TEM images of P25-Pt, and (f) XRD patterns of the P25 powder before and after Pt photodeposition.

### Photoreforming experiments

The photocatalytic studies were carried out using P25 or P25-Pt as the photocatalyst and PET as the microplastic source. Both the catalyst powder and the model pollutant were first dispersed in 1 M NaOH to initiate cleavage of the polymer chain into EG and terephthalate (TP) blocks. The resulting suspension was next irradiated with a narrow band emitting LED source centred at 365 nm (details in Experimental and SI Note 2). In the course of the experiments, the temperature was either maintained at room temperature (RT, 25 °C) or increased to 70 °C. Furthermore, different reaction conditions were explored, assuming that an oxygen-rich (aerobic) atmosphere would expedite microplastic oxidation, whilst an inert (anaerobic) atmosphere would promote the utilisation of photoexcited electrons towards H<sup>+</sup> reduction (as no O<sub>2</sub> is present to compete for the electrons).<sup>13,51</sup> The following sections discuss the obtained results starting from H<sub>2</sub> generation rates of neat P25 and Pt-loaded P25, continuing with the discussion of CH<sub>4</sub> production.

### Hydrogen production

We observed quite low H<sub>2</sub> production rates of 0.001 µmol h<sup>−1</sup> when photoreforming PET using neat P25. The use of an elevated temperature (70 °C) boosted the hydrogen evolution reaction (HER) significantly, by a factor of ∼63 (Fig. 2a and Fig. S6a), leading to 0.071 µmol h<sup>−1</sup> of H<sub>2</sub> generated. Interestingly, in our reference experiments, we observed similar values for the HER and a similar effect of temperature when no PET was present in the reaction medium (Table S2). This result suggests that in the absence of a suitable co-catalyst, H<sub>2</sub> evolution is not affected by the presence of PET and the prime source for H<sub>2</sub> originates from the overall water splitting reaction. This is possible as the use of basic pH during the photoreforming favours water oxidation which often becomes the bottleneck of water splitting. We note, however, that the process runs with an unpractically low AQY of 0.00003% (Table S3).

![Figure 2](body_assets/m_d5gc03562g-f2.png)

**Fig. 2** Gas phase analysis: schematic illustration of the relative amounts of solar fuels generated as a function of the catalyst and temperature depicting (a) H<sub>2</sub> from P25, (b) H<sub>2</sub> from P25-Pt, (c) CH<sub>4</sub> from P25 and (d) CH<sub>4</sub> from P25-Pt. Production values in µmol h<sup>−1</sup> are presented in Table S2. Alternative bar graph view is shown in Fig. S6.

As schematically shown in Fig. 2b, the presence of Pt on the TiO<sub>2</sub> surface boosted the HER of neat TiO<sub>2</sub> by 4 orders of magnitude, resulting in 2.87 µmol h<sup>−1</sup> of H<sub>2</sub> generated (AQY of 0.08%). This high H<sub>2</sub> amount corresponds to approximately 20% of the PET being up-converted (Table S11 and SI Note 7) and indicates a very important role of Pt in realising efficient conversion of H<sup>+</sup> into H<sub>2</sub>. This role is likely dual: it provides suitable proton adsorption and catalytic sites as well as strongly facilitates charge extraction, resulting in more efficient charge utilisation. Analysis of liquid-phase photoreforming products that will be discussed later further emphasises this favourable effect of Pt on the efficiency of hole utilisation, as it appears to promote the generation of AA from EG. For the P25-Pt photosystem (at RT), only a minor part of the generated H<sub>2</sub> (∼40%) is produced in the absence of PET, suggesting that PET is essential for this high HER rate (Table S2). Besides this, similar to the effect of temperature on the HER performance of neat P25, we observed a further substantial increase of the H<sub>2</sub> generation rate of P25-Pt at 70 °C, reaching as high as 15.35 µmol h<sup>−1</sup> (Fig. 2b), corresponding to outstanding AQY values up to 0.45%.

### Methane production

Contrary to many other studies on PET photoreforming, we consistently observed generation of CH<sub>4</sub> from the reaction mixture, on par with H<sub>2</sub> production discussed above. CH<sub>4</sub> is a high-value product with a 117.07 billion US\$ <sup>52</sup> market share and a high price of €80 per MWh (similar to natural gas)<sup>53</sup> compared to €30 per MWh for H<sub>2</sub> from fossil fuels,<sup>54</sup> with both automotive<sup>52</sup> and energy sectors<sup>55</sup> being highly interested in green CH<sub>4</sub> sources. Photoreforming of PET using neat P25 yields a CH<sub>4</sub> generation rate of 0.01 µmol h<sup>−1</sup>, which is 10 times higher than that of H<sub>2</sub> production (Fig. 2c, Fig. S6b and Table S2). Increasing the temperature from RT to 70 °C further increases the CH<sub>4</sub> yield 3-fold. When using the P25-Pt photosystem, similar to its increased performance towards the HER, we observed significantly more CH<sub>4</sub> (3–7 fold increase, Fig. 2d) compared to neat P25. Our blank experiments performed in the absence of PET confirm that the majority of CH<sub>4</sub> (up to 91%) originates from PET, while only a minor CH<sub>4</sub> production in the absence of PET (as the only intentional C source) could be traced to carbon impurities (SI Note 4).

Since only a few early works have reported CH<sub>4</sub> evolution from PET photoreforming, the mechanism of CH<sub>4</sub> formation has not been investigated so far. Our datasets allow discussing possible pathways of CH<sub>4</sub> generation, including (i) hydrogenation of C<sub>1</sub> products of PET oxidation,<sup>56</sup>*e.g.*, *via* CO/CO<sub>2</sub>/HCO<sub>3</sub><sup>−</sup>/CO<sub>3</sub><sup>2−</sup> reduction by molecular H<sub>2</sub>,<sup>57–59</sup> or (ii) direct CH<sub>4</sub> formation as a side-product of PET photodegradation, *e.g.*, *via* coupling of CH<sub>3</sub> and H radicals. Regarding the first point: systematic analyses of both H<sub>2</sub> and CH<sub>4</sub> generation rates (Fig. 2 shows relative values, whereas Table S2 shows absolute values) reveal a strong but non-linear correlation between H<sub>2</sub>/CH<sub>4</sub> production ratio change (increase or drop) as a factor of system parameters. As such, in RT photoreforming experiments, loading of P25 with Pt results in a significant increase in both the HER (∼1000 times) and CH<sub>4</sub> production (∼4 times). In a similar manner, increasing the temperature from RT to 70 °C yields more H<sub>2</sub> (∼200 times) and more CH<sub>4</sub> (∼7 times). This disproportional increase of H<sub>2</sub> and CH<sub>4</sub> rates suggests that H<sub>2</sub> production is only poorly correlated with CH<sub>4</sub> generation, indicating that hydrogenation – path (i) – may not be the main mechanism of CH<sub>4</sub> formation. A similar conclusion can be reached when analysing relative H<sub>2</sub>/CH<sub>4</sub> generation ratios in P25 samples with and without Pt. In the absence of Pt, H<sub>2</sub> and CH<sub>4</sub> formation rates are on a similar level (size of the circles presented in Fig. 2a and c). When Pt is present, we see outstanding H<sub>2</sub> evolution; however, the presence of such large amounts of H<sub>2</sub> in the solution has a rather negligible effect on CH<sub>4</sub> production (Fig. 2b and d). To further validate this result, we conducted photoreforming studies using P25-Pt (both at RT and 70 °C) under a CO<sub>2</sub>/H<sub>2</sub> saturated atmosphere. Despite the availability of both H<sub>2</sub> and CO<sub>2</sub>, we observed only a marginal effect on CH<sub>4</sub> generation (SI Note 5), which corroborates that the hydrogenation pathway (i) plays a minor role in CH<sub>4</sub> formation and rather points to the (ii) mechanism.

### Liquid-phase products

While the generation of solar fuels, H<sub>2</sub> and CH<sub>4</sub>, constitutes an important milestone in the photoreforming process, elucidation of the liquid phase products provides complementary mechanistic insights and can further reveal the potential of the process to generate high-value compounds. The formation of PET photoreforming products in liquid phase was thus followed by high pressure liquid chromatography (HPLC) (Fig. 3a, d and e and Table S8) analysis and nuclear magnetic resonance (NMR) measurements (Fig. 3b). In addition, the accumulation of gaseous CO<sub>2</sub> production in the reactor headspace was quantified by means of GC; however, we note that at high pH levels, CO<sub>2</sub> is predominantly present in its mineralised forms as HCO<sub>3</sub><sup>−</sup> and CO<sub>3</sub><sup>2−</sup>, which is in line with the low amounts of gaseous CO<sub>2</sub> detected in our experiments<sup>24</sup> (Table S9).

![Figure 3](body_assets/m_d5gc03562g-f3.png)

**Fig. 3** Liquid phase analysis: (a) HPLC analysis of OA, (b) <sup>1</sup>H NMR spectrum of P25-Pt at 70 °C (inert, under a UV lamp), measured in D<sub>2</sub>O and 1 M NaOH (1: 5), without water suppression, (c) suggested pathways of EG conversion into the detected products: (1) OA pathway and (2) AA pathway, including HPLC results from samples obtained under air and under inert conditions, and (d and e) obtained yields of EG and AA *via* HPLC analysis.

A key component of the PET photoreforming reaction is the alkaline media employed to facilitate the hydrolysis of PET to its monomers TP and EG. Whilst TP is generally regarded as inactive towards the following photocatalytic conversion,<sup>60</sup> EG can be readily photoconverted, forming liquid products such as AA, FA, ethanol, OA, glyoxal and others (Fig. 3c).<sup>19–21,23,61</sup> Our HPLC results indicate that a range of these compounds (along with unconverted TP) were found in our PET photoreforming experiments; however, the exact mixture composition depended strongly on the catalyst and conditions used. Interestingly, we observed that the temperature of the photoreforming has a strong effect on the relative EG accumulation (from PET hydrolysis) and consumption (from its photoconversion) rates. As such, EG was predominantly detected in the P25 sample at 70 °C, while it was more readily transformed into OA at RT (Fig. 3a). We also observed that higher temperatures generally facilitate the dehydroxylation pathway of EG (Fig. 3c, pathway 2). The presence of the Pt co-catalyst, on the other hand, only affected the mechanism of the EG conversion at 70 °C, which is reflected in the accumulation of OA under these conditions (Fig. 3a and c, pathway 1). In the absence of Pt, OA got converted into other (C<sub>1</sub>) compounds, with no detectable generation of FA for samples irradiated at 365 nm (Table S8), suggesting that OA gets fully oxidized to CO<sub>2</sub>/CO<sub>3</sub><sup>2−</sup> under these photoreforming conditions.<sup>24</sup>

Our results also show that the mechanism and product selectivity of PET photoreforming can be tuned by controlling the reaction atmosphere (Fig. 3a, d and e). As such, purging the solution of P25-Pt (reaction at 70 °C) with He resulted in approximately 1.5 times higher yield of AA compared to aerobic conditions. This is in line with the conclusions of Han *et al.*<sup>23</sup> who suggested that less reductive conditions promote the dehydroxylation pathway (Fig. 3e and c, pathway 2) and convert EG predominantly into AA *via* ethanol and acetaldehyde. Our carbon balance calculations further indicate that around 30% of PET was successfully valorised to AA under these conditions, suggesting a very efficient photoreforming process (Table S10 and SI Note 6). The <sup>1</sup>H NMR spectrum of the reaction solution (Fig. 3b) complements these findings: apart from the characteristic peak for aromatic protons of TP, a peak at around 1.8 ppm corresponding to acetate ions is observed along with a triplet at around 1.1 ppm, which may indicate the formation of ethanol. A zoomed in inset further reveals the characteristic CH<sub>2</sub> quartet of ethanol (with *J* = 7 Hz) overlapping with the strong signal of the OH peak of EG at around 3.5 ppm. The absence of OA in the products obtained under an inert atmosphere (Fig. 3a) again suggests that it readily undergoes further oxidation. However, assuming that OA would eventually convert into CO<sub>2</sub>, it is surprising to see that P25-Pt produces much more CO<sub>2</sub> (a factor of ∼6) when photoreforming is run at RT *vs.* 70 °C (Table S9). This can be linked to the fact that elevated temperature results in a much stronger CH<sub>4</sub> production (refer to the discussion about solar fuels above) and suggests that CO<sub>2</sub> can be consumed by its hydrogenation to some extent.

### Sunlight-driven photoreforming

The possibility of employing sunlight for PET photoreforming was explored by conducting experiments using solar-simulated light (details in Experimental and SI Note 8). The formation of both gas phase (Table S14) and liquid phase products (Fig. S9 and Table S8) was followed. In contrast to our results obtained under UV light, photoreforming of PET under solar light using neat P25 at 70 °C yielded only negligible amounts of H<sub>2</sub> (a factor of ∼300 lower) and CH<sub>4</sub> (a factor of ∼15 lower). Considering that both HPLC (Table S8) and NMR (Fig. S9) analyses only showed the monomers TP and EG and a negligible quantity of FA in the product mixture, we can effectively conclude that the photoreforming was largely unsuccessful under these conditions, presumably due to low conversion rates and insufficient intensity of incoming light. In contrast, solar-driven photoreforming of PET using P25-Pt at RT resulted in much stronger generation of both solar fuels, yielding 0.209 µmol h<sup>−1</sup> of H<sub>2</sub> and 0.009 µmol h<sup>−1</sup> CH<sub>4</sub>. These rates are lower compared to those obtained under a UV LED source (a factor of ∼14 for H<sub>2</sub> and ∼4.5 for CH<sub>4</sub> compared to Table S2); however, considering the low proportion of UV photons in the solar spectrum, one arrives at a UV-based AQY value of 0.84% for P25-Pt based on the H<sub>2</sub> generation rates. As expected, P25-Pt also produced a number of liquid phase compounds with a composition similar to that obtained under UV light. These results and respectable AQY obtained for P25-Pt under solar-simulated light highlight the important role of Pt in solar-driven PET photoreforming and further showcase the commercial potential of the process (SI Note 8).

### Degradation pathways and long-term performance

SEM images of the neat and photoreformed PET powders are shown in Fig. 4. The unmodified PET (Fig. 4d) depicts a smooth surface with well-defined edges characteristic of soft matter, whereas micrographs of PET particles after reaction (Fig. 4e and f) illustrate a less distinct structure and reveal sharp edges indicating that some form of decay and physical degradation has taken place upon irradiation. SEM images also indicate that a close contact between TiO<sub>2</sub> particles and PET particles is established during the photoreforming process, although zeta potential measurements (Fig. S11 and Table S17) revealed that both the powders (photocatalyst and microplastic) exposed to alkali medium show negative charge values well below −20 mV. This suggests that van der Waals attraction between PET and TiO<sub>2</sub> still dominates in the solution,<sup>62</sup> leading to the close interface between the two. Photoluminescence spectroscopy studies employing ˙OH scavengers were conducted to elaborate on the contributions of indirect and direct oxidation pathways towards the PET degradation process with P25-Pt (details in SI Note 10).<sup>20,63,64</sup> The results in Fig. 4c indicate that the generation of ˙OH is impeded in the presence of PET, thus confirming that direct hole transfer through the TiO<sub>2</sub>/PET interface established in the reaction suspension plays an important role in the process of PET particle activation and conversion. Besides this, we also conducted photocatalytic experiments in the presence of radical quenchers (SI Note 10) capable of selectively trapping various reactive oxygen species. Fig. S13 shows that only benzoquinone resulted in a strong activity drop (99.7% less H<sub>2</sub> and 94.3% less CH<sub>4</sub> was produced in its presence), which hints to the importance of superoxide radicals in the process of PET oxidation.

![Figure 4](body_assets/m_d5gc03562g-f4.png)

**Fig. 4** Mechanism, long-term stability and microplastic degradation: generated H<sub>2</sub> (a) and CH<sub>4</sub> (b) in the course of 32 h (1 mg mL<sup>−1</sup> PET, 0.5 mg mL<sup>−1</sup> P25-Pt (1 wt%), 100 mL of 1 M NaOH, RT); (c) PL emission spectrum of P25-Pt (1 wt%) with and without PET, under He and at RT; SEM images of (d) unmodified PET, (e) PET particles after irradiation with P25 (at RT), and (f) after irradiation with P25-Pt (at 70 °C).

Long-term performance stability was next evaluated over the course of 32 hours of irradiation and *via* a large-scale implementation by around 5-fold (SI Note 11). Fig. 4a and b show the rates of H<sub>2</sub> and CH<sub>4</sub> generation as a function of time. While we observed strong hour-to-hour fluctuations in activity, which might be related to bubble evolution dynamics, an overall stable generation of both solar fuels can be concluded. Selected catalytic suspensions were further recovered by filtration and analysed using XRD. The obtained XRD pattern of the recovered solid (Fig. S14) shows the characteristic peaks of rutile and anatase phases of P25 (suggesting the catalyst's stability), along with additional peaks corresponding to unprocessed PET. No morphological or phase change has been observed, which is in line with the stable catalytic performance of the P25-Pt photocatalyst.

## Conclusions

In this study, we explored the potential of P25-based photosystems towards PET photoreforming and highlighted several outcomes that are of interest for further development of the process. We found that photoreforming PET using neat P25 results in marginal H<sub>2</sub> production, which can be increased by 1–2 orders of magnitude by elevating the reaction temperature. In contrast to this, the addition of Pt significantly boosted hydrogen evolution of P25 by 4 orders of magnitude, which highlights the crucial role of Pt in promoting the reaction of interest. A mixed use of Pt and elevated temperatures yielded synergistic HER improvement, resulting in more than 15 µmol h<sup>−1</sup> of H<sub>2</sub> corresponding to AQY values up to 0.45%. Besides detecting H<sub>2</sub>, we observed significant CH<sub>4</sub> production during PET photoreforming, with rates exceeding H<sub>2</sub> generation using neat P25 and further increasing with temperature and Pt addition. Mechanistic investigations suggest that CH<sub>4</sub> primarily originates from PET degradation rather than hydrogenation of PET oxidation products, as CH<sub>4</sub> production remains largely independent of H<sub>2</sub> concentration. Liquid phase analysis revealed that reaction conditions and the catalyst type significantly influence product distribution, with EG photoconversion leading to various intermediates such as AA, OA, FA and ethanol. Some product selectivity was observed, with high AA yields further enhanced by the presence of Pt and OA production preferred under aerobic conditions. Furthermore, the possibility of large-scale implementation was demonstrated through irradiation in a 100 mL setup for 32 hours and experiments simulating the solar spectrum for 24 hours. The promising AQY values indicate the potential of this technology, as P25-Pt yielded significant amounts of both solar fuels and remained stable for the prolonged irradiation period in the larger setup. It is clear that PET not only acts as a sacrificial agent for the formation of H<sub>2</sub> but also shows great potential for the generation of valuable chemicals and green CH<sub>4</sub>. While this investigation offers useful new insights for the development of large-scale application, further in-depth mechanistic studies are crucial for advancing this sustainable abatement method and realising the selective photoconversion process.

## Experimental

### Pt photodeposition on P25 TiO<sub>2</sub>

For the photodeposition of 1 wt% Pt on P25 TiO<sub>2</sub>, 1 g of the support was transferred to a round bottom flask containing 200 mL of a 1: 1 MeOH: H<sub>2</sub>O solution. Then 12.5 mL of a 20 mmol H<sub>2</sub>PtCl<sub>6</sub> precursor solution was added. The suspension was purged with Ar for 5 minutes, before starting double sided illumination (top and side) with two UV light sources (365 nm SOLIS LED and Lumatec LED lamps), with wavelengths in the range of 190–400 nm for 135 minutes. Subsequently, the MeOH: H<sub>2</sub>O mixture was removed and the photocatalyst was dried overnight at 60 °C.

### Photoreforming experiments

In a standard run, the generation of solar fuels was investigated by adding 18 mg of PET powder (1.0 mg mL<sup>−1</sup>) and 9 mg (0.5 mg mL<sup>−1</sup>) of the respective photocatalyst (either neat P25 or P25-Pt) to a 20 mL vial with a septum, containing 18 mL of 1 M NaOH solution. The suspension was sonicated for a total of 12 minutes to achieve good dispersion of the powders. The employed setup did not include a water cooling system and increased temperature was achieved with a predetermined setting of the hot plate. Before irradiating the respective sample, the solution was purged with either helium or air for 10 minutes – closing the system to achieve inert conditions or continuing purging with air for the entire duration of the experiment. Illumination was performed with a 365 nm SOLIS LED lamp, with a measured intensity of 69.7 mW cm<sup>−2</sup>, for 5 hours under magnetic stirring. The generated quantities of both H<sub>2</sub> and CH<sub>4</sub> were detected by GC. The liquids and solids were separated *via* filtration and kept for further analysis.

### Solar-simulated photoreforming experiments

The general procedure of these two samples is identical to the aforementioned description, with the exception of decreasing the suspension from 18 mL to 16 mL and thus altering the mass of PET and the photocatalyst to use the same concentrations as used in our standard photoreforming studies. Irradiation was performed for 24 hours, implementing a broad band Xe lamp with an IR filter and an intensity of 21.3 mW cm<sup>−2</sup>.

### Scale-up experiment

Herein, the suspension volume was increased to 100 mL and irradiation was performed in a round bottom flask equipped with a septum. The suspension was sonicated for 17 minutes and purged with He for 30 minutes. The concentration of PET and P25-Pt remained at 1.0 mg ml<sup>−1</sup> and 0.5 mg mL<sup>−1</sup>, respectively. The sample was illuminated under magnetic stirring at 365 nm (SOLIS LED) with an intensity of 69.7 mW cm<sup>−2</sup> for 32 hours, extracting and measuring gaseous samples every hour within the first 5 hours of the experiment and then every 2 hours between the 24 and 32 hours, to investigate the activity and long-term performance of the photocatalytic system. The solution was separated from the remaining solids and stored for further characterisation.

## Author contributions

Conceptualisation: MW and AC; methodology: MW and AC; investigation: MW, AE, CvB, and AK; resources: CP, FK, DE, and AC; data curation: MW; writing—original draft preparation: MW and AC; writing—review and editing: MW, AE, CvB, AK, CP, FK, DE and AC; visualisation: MW; supervision: AC; project administration: AC; funding acquisition: AC. All authors have read and agreed to the published version of the manuscript.

## Conflicts of interest

There are no conflicts to declare.

## Data availability

The data supporting the findings of this study, including characterization results (microscopy, XRD, NMR, UV-vis DRS, PL, GC, HPLC, TXRF, zeta-potential), and supplementary analysis protocols (*e.g.*, AQY calculations), are provided in supplementary information (SI). See DOI: [https://doi.org/10.1039/d5gc03562g](https://doi.org/10.1039/d5gc03562g). The raw research data supporting the main text figures have been deposited in TU Wien Research Data Repository and are openly available at [https://researchdata.tuwien.ac.at/records/k185m-c6a84](https://researchdata.tuwien.ac.at/records/k185m-c6a84).

Any additional information will be provided upon request.

## Acknowledgements

This research was funded in part by the Austrian Science Fund (FWF) \[10.55776/COE5\] (Cluster of Excellence MECS). For open access purposes, the author has applied a CC BY public copyright license to any author accepted manuscript version arising from this submission. Funding support by the Austrian Research Promotion Agency (FFG, Project Nr. 896659 AMAGADE) and the Gesellschaft für Forschungsförderung Niederösterreich (GFF, Project Nr. FTI21-I-004) is gratefully acknowledged. The authors would also like to acknowledge the facilities of the Technische Universität Wien (TU Wien) for technical support and fruitful discussions: X-Ray Center (XRC), especially Werner Artner and Peter Kregsamer; Analytical Instrumentation Center (AIC); and Electron Microscopy Center (USTEM). We are also grateful to Stephen Nagaraju Myakala for supporting us with SEM measurements, Jürgen Gratzl for providing us with the PET microplastic powders and Nevzat Yigit for making a gas mixture available for additional experiments.

## Supplementary Materials

- [Supplementary information (PDF)](https://pubs.rsc.org/gc/article-supplement/894100/pdf/d5gc03562g1_suppl/)

## References (64 total, showing 64)

1. R. Siddique, J. Khatib and I. Kaur, *Waste Manage.*, 2008, 28, 1835–1852.

2. R. H. Faraj, H. F. Hama Ali, A. F. H. Sherwani, B. R. Hassan and H. Karim, *J. Build. Eng.*, 2020, 30, 101283.

3. G. Wu, J. Li and Z. Xu, *Waste Manage.*, 2013, 33, 585–597.

4. R. Tiwari, N. Azad, D. Dutta, B. R. Yadav and S. Kumar, *Sci. Total Environ.*, 2023, 881, 163433.

5. R. C. Hale, M. E. Seeley, M. J. La Guardia, L. Mai and E. Y. Zeng, *J. Geophys. Res.:Oceans*, 2020, 125, e2018JC014719.

6. C. H. Ng, M. A. Mistoh, S. H. Teo, A. Galassi, A. Ibrahim, C. S. Sipaut, J. Foo, J. Seay, Y. H. Taufiq-Yap and J. Janaun, *Front. Environ. Sci.*, 2023, 11, 1142071.

7. O. A. Alabi, K. Ologbonjaye, O. Awosolu, O. Alalade, O. A. Alabi, K. I. Ologbonjaye and O. E. Alalade, *J. Toxicol. Risk Assess.*, 2019, 5, 21.

8. M. Aljohani, H. Daly, L. Lan, A. Mavridis, M. Lindley, S. J. Haigh, C. D′agostino, X. Fan and C. Hardacre, *ChemPlusChem*, 2024, 89, e202300411.

9. P. Miao, J. Zhao, P. Wang, R. Shi and T. Zhang, *ACS Materials Lett.*, 2024, 6, 590–597.

10. T. Kawai and T. Sakata, *Chem. Lett.*, 1981, 10, 81–84.

11. T. Kawai and T. Sakata, *Nature*, 1980, 286, 474–476.

12. T. Sakata and T. Kawai, *J. Synth. Org. Chem., Jpn.*, 1981, 39, 589–602.

13. S. Chu, B. Zhang, X. Zhao, H. S. Soo, F. Wang, R. Xiao and H. Zhang, *Adv. Energy Mater.*, 2022, 12, 2200435.

14. D. W. Wakerley, M. F. Kuehnel, K. L. Orchard, K. H. Ly, T. E. Rosser and E. Reisner, *Nat. Energy*, 2017, 2, 17021.

15. H. Kasap, D. S. Achilleos, A. Huang and E. Reisner, *J. Am. Chem. Soc.*, 2018, 140, 11604–11607.

16. D. S. Achilleos, W. Yang, H. Kasap, A. Savateev, Y. Markushyna, J. R. Durrant and E. Reisner, *Angew. Chem., Int. Ed.*, 2020, 59, 18184–18188.

17. E. Lam and E. Reisner, *Angew. Chem., Int. Ed.*, 2021, 60, 23306–23312.

18. S. Batool, M. Y. S. Ibrahim, F. Ehrlich-Sommer, S. N. Myakala, S. Naghdi and A. Cherevan, *Sustainable Energy Fuels*, 2025, 9, 555–564.

19. T. Uekert, M. F. Kuehnel, D. W. Wakerley and E. Reisner, *Energy Environ. Sci.*, 2018, 11, 2853–2857.

20. T. Uekert, H. Kasap and E. Reisner, *J. Am. Chem. Soc.*, 2019, 141, 15201–15210.

21. M. Du, Y. Zhang, S. Kang, X. Guo, Y. Ma, M. Xing, Y. Zhu, Y. Chai and B. Qiu, *ACS Catal.*, 2022, 12, 12823–12832.

22. T. Uekert, M. A. Bajada, T. Schubert, C. M. Pichler and E. Reisner, *ChemSusChem*, 2021, 14, 4190–4197.

23. M. Han, S. Zhu, C. Xia and B. Yang, *Appl. Catal. B*, 2022, 316, 121662.

24. S. Linley and E. Reisner, *Adv. Sci.*, 2023, 10, 2207314.

25. M. Han, M. Han, J. Ma, M. Du, Q. Zhu and B. Qiu, *Electron*, 2025, 3, e70005.

26. E. M. N. T. Edirisooriya, P. S. Senanayake, P. Xu and H. Wang, *Catalysts*, 2025, 15, 334.

27. Z. Li, Y. Yang, C. Zhang, W. Fan, G. Li, J. Fang and L. Lu, *Chem Catal.*, 2024, 4(3), https://doi.org/10.1016/j.checat.2024.100902.

28. T. T. Nguyen and K. Edalati, *Chemosphere*, 2024, 355, 141785.

29. T. Uekert, C. M. Pichler, T. Schubert and E. Reisner, *Nat. Sustain.*, 2021, 4, 383–391.

30. Y. Miao, Y. Zhao, J. Gao, J. Wang and T. Zhang, *J. Am. Chem. Soc.*, 2024, 146, 4842–4850.

31. K. Hu, W. Tian, Y. Yang, G. Nie, P. Zhou, Y. Wang, X. Duan and S. Wang, *Water Res.*, 2021, 198, 117144.

32. S. Guo, Y. Huang, D. Li, Z. Xie, Y. Jia, X. Wu, D. Xu and W. Shi, *Chem. Commun.*, 2023, 59, 7791.

33. X. Gong, F. Tong, F. Ma, Y. Zhang, P. Zhou, Z. Wang, Y. Liu, P. Wang, H. Cheng, Y. Dai, Z. Zheng and B. Huang, *Appl. Catal. B*, 2022, 307, 121143.

34. S. Zhang, H. Li, L. Wang, J. Liu, G. Liang, K. Davey, J. Ran and S. Z. Qiao, *J. Am. Chem. Soc.*, 2023, 145, 6410–6419.

35. T. T. Nguyen, J. Hidalgo-Jiménez, X. Sauvage, K. Saito, Q. Guo and K. Edalati, *Chem. Eng. J.*, 2025, 504, 158730.

36. H. Truong, N. Hai, T. T. Nguyen, M. Nishibori, T. Ishihara and K. Edalati, *Appl. Catal., B*, 2025, 365, 124968.

37. J. Wang, H. Zhao, L. Chen, J. Björk, J. Rosen, P. Kumar, L. Jing, J. Chen, G. Kibria and J. Hu, *Appl. Catal. B*, 2024, 344, 123665.

38. A. Fujishima and K. Honda, *Nature*, 1972, 238, 37–38.

39. G. R. Bamwenda, S. Tsubota, T. Nakamura and M. Haruta, *J. Photochem. Photobiol., A*, 1995, 89, 177–189.

40. J. J. Velázquez, R. Fernández-González, L. Díaz, E. Pulido Melián, V. D. Rodríguez and P. Núñez, *J. Alloys Compd.*, 2017, 721, 405–410.

41. E. Pulido Meliá, C. R. López, A. Ortega Méndez, O. González Díaz, M. Nereida Suárez, J. M. Doña Rodríguez, J. A. Navío and D. Fernández Hevia, *Int. J. Hydrogen*, 2013, 38, 11737–11748.

42. J. S. Schubert, E. Doloszeski, P. Ayala, S. N. Myakala, J. Rath, B. Fickl, A. Giesriegl, D. H. Apaydin, B. C. Bayer, S. Kashiwaya, A. Cherevan and D. Eder, *Adv. Mater. Interfaces*, 2024, 11, 2300695.

43. J. S. Schubert, L. Kalantari, A. Lechner, A. Giesriegl, S. P. Nandan, P. Alaya, S. Kashiwaya, M. Sauer, A. Foelske, J. Rosen, P. Blaha, A. Cherevan and D. Eder, *J. Mater. Chem. A*, 2021, 9, 21958–21971.

44. P. Ayala, A. Giesriegl, S. P. Nandan, S. N. Myakala, P. Wobrauschek and A. Cherevan, *Catalysts*, 2021, 11, 417.

45. S. Cao, C.-J. Wang, W.-F. Fu, Y. Chen and C.-H. Tung, *ChemSusChem*, 2017, 10, 4306–4323.

46. M. Ni, M. K. H. Leung, D. Y. C. Leung and K. Sumathy, *Renewable Sustainable Energy Rev.*, 2007, 11, 401–425.

47. H. Nagakawa and M. Nagata, *ACS Appl. Mater. Interfaces*, 2021, 13, 47511–47519.

48. G. M. Haselmann and D. Eder, *ACS Catal.*, 2017, 7, 4668–4675.

49. J. Tauc, R. Grigorovici and A. Vancu, *Phys. Status Solidi*, 1966, 15, 627.

50. P. Makuła, M. Pacia and W. Macyk, *J. Phys. Chem. Lett.*, 2018, 9, 6814–6817.

51. S. Kampouri and K. C. Stylianou, *ACS Catal.*, 2019, 9, 4247–4270.

52. Methane Market Report 2024-Methane Market Growth, Segments And Drivers, https://www.thebusinessresearchcompany.com/report/methane-global-market-report, (accessed 15 November 2024)

53. Biomethane produced in Europe today is 30% cheaper than natural gas|Bioenergy Insight Magazine, https://www.bioenergy-news.com/news/biomethane-produced-in-europe-today-is-30-cheaper-than-natural-gas/, (accessed 18 November 2024)

54. S. Furfari and A. Clerici, *Eur. Phys. J. Plus*, 2021, 136, 509.

55. R. Tichler and A. Zauner, *RELP*, 2018, 8, 42–48.

56. A. Ongen, *Clean Technol. Environ. Policy*, 2016, 18, 915–924.

57. A. Banerjee and M. W. Kanan, *ACS Cent. Sci.*, 2018, 4, 606–613.

58. Z. Xie, Z. Sun, B. Shao, Y. Zhu, R. Ma, S. Li, J. Li, Y. Chen, H. Liu and J. Hu, *Chem. Eng. J.*, 2024, 495, 153465.

59. N. A. Fiore, A. J. Kohtz, D. N. Miller, S. Antony-Babu, D. Pan, C. Lahey, X. Huang, Y. Lu, N. R. Buan and K. A. Weber, *Commun. Earth Environ.*, 2025, 6, 85.

60. T. T. Nguyen and K. Edalati, *J. Catal.*, 2024, 440, 115808.

61. M. Li and S. Zhang, *ACS Catal.*, 2024, 14, 2949–2958.

62. S. Bhattacharjee, *J. Controlled Release*, 2016, 235, 337–351.

63. S. Batool, J. S. Schubert, P. Ayala, H. Saito, M. J. Sampaio, E. S. Da Silva, C. G. Silva, J. L. Faria, D. Eder and A. Cherevan, *Sustainable Energy Fuels*, 2024, 8, 1225–1235.

64. S. P. Nandan, N. I. Gumerova, J. S. Schubert, H. Saito, A. Rompel, A. Cherevan and D. Eder, *ACS Mater. Au*, 2022, 2, 505–515.
