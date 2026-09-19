---
title: "Decoupling
the Cation-Induced Vibrational Responses
at the Graphdiyne–Water Interface via In Situ Surface-Enhanced
Raman Spectroscopy"
authors: "Wang, Xiao-Ting, Wan, Jin-Long, Zhong, Han-Liang, Wang, Yao-Hui, Zhang, Xin-Yue, Peng, Zeyu, Hu, Ling-Yun, A, Yao-Lin, Cheng, Shimiao, Yang, Shuliang, Zhang, Hua, Yu, Jia, Li, Jian-Feng"
journal: "Journal of the American
Chemical Society"
doi: "10.1021/jacs.6c10062"
published: "2026-9-14"
source: "acs"
acquisition:
  provider: "acs"
  route: "browser_html"
  representation: "html"
  transport: "browser"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 7177
---

# Decoupling
the Cation-Induced Vibrational Responses
at the Graphdiyne–Water Interface via In Situ Surface-Enhanced
Raman Spectroscopy

## Abstract

Graphdiyne (GDY), featuring subnanometer pores and diacetylenic linkages, provides a platform for probing electrified carbon interfaces. Although the organization of cations and interfacial water governs electric double layer (EDL) structure and charge-transfer kinetics, tracking their reorganization and coupling with GDY remains challenging. Here, cation-dependent interfacial responses at Au–GDY electrodes were characterized using *in situ* surface-enhanced Raman spectroscopy and *ab initio* molecular dynamics (AIMD) simulations. A nonmonotonic cation dependence separates Li<sup>+</sup>/K<sup>+</sup> from Na<sup>+</sup>/Cs<sup>+</sup> rather than following a bare- or hydrated-ion size sequence. Under cathodic polarization, LiOH/KOH retain a single red-shifting diacetylenic band, while NaOH/CsOH develop an additional low-frequency band. This grouping coincides with distinct potential-dependent vibrational responses of cation-coordinated water and the GDY framework. AIMD indicates that Li<sup>+</sup>/K<sup>+</sup> access GDY sublayer regions, whereas Na<sup>+</sup>/Cs<sup>+</sup> remain mainly near the outer interface within the simulated time window. Combined analyses support a synergistic ion-sieving mechanism governed by hydration-shell reorganization, pore confinement, and cation–GDY interactions. This distribution is accompanied by interfacial-water reorganization and changes in local vibrational environments of the GDY framework. Together, these findings provide a molecular-level framework for understanding cation-specific EDL behavior at porous carbon interfaces, with implications for ion-selective electrochemical interfaces.

## Introduction

Graphdiyne (GDY) is a two-dimensional carbon allotrope built from sp<sup>2</sup>-hybridized benzene nodes and sp-hybridized diacetylenic linkages, forming a π-conjugated lattice with intrinsic triangular subnanometer pores and chemically accessible active sites. (1) By overcoming the structural ambiguity of amorphous porous carbons and the impermeability of the pristine graphene basal plane, (2, 3) GDY offers a structurally defined carbon platform for fundamental electrochemical research. At electrified solid–liquid interfaces, the spatiotemporal configurations of ions and solvent molecules (particularly interfacial-water networks) shape electric double layer (EDL) architectures and charge-transfer kinetics. (4, 5) Given its well-defined atomic topology, GDY provides a platform for linking macroscopic EDL phenomena to molecular-level processes, enabling studies of ion electrosorption, interfacial-water reorganization, and their interplay with the local electronic structure of the substrate. (6)

Building on these structural features, macroscopic studies have shown that GDY can regulate ion and solvent dynamics. (7) In electrochemical energy storage, GDY delivers high alkali-metal ion capacities and rapid kinetics, (8, 9) ascribed to reversible cation−π interactions and the strong spatial confinement within its uniform pores. Similarly, ordered GDY nanofilms in membrane separations facilitate rapid selective water permeation with near-ideal ion rejection, (10) through steric confinement, which restricts water to one-dimensional hydrogen-bonded chains while imposing thermodynamic barriers on hydrated ions. However, current understanding remains largely limited to steady-state macroscopic observations. Further understanding under *in situ* conditions is needed, particularly regarding cation configurations at the electrified interface, (11, 12) reorganization of the adjacent interfacial-water network, (13, 14) and the resulting changes in the local electric field and GDY vibrational response.

Probing these interfacial changes presents two experimental challenges. First, studying intrinsic interfacial electrochemistry requires well-defined crystalline GDY films, (15, 16) because defects and morphological variations can complicate spectroscopic signatures. (17) Preparing such films remains challenging, because the high reactivity of terminal alkyne monomers and the conformational disorder arising from C–C bond rotation can disrupt the molecular alignment required for crystallization. Second, signals originating from the ultrathin EDL, particularly those associated with changes in interfacial water, are weak relative to the background from the bulk solution. (18) An *in situ* method is therefore needed to track the carbon framework and adjacent water network on crystalline GDY electrodes under applied potentials and to distinguish the coupled effects of potential, ion, water, and electronic structure. (19−21)

Surface-enhanced Raman spectroscopy (SERS), with its surface sensitivity and reduced contribution from bulk water, is well suited for probing the GDY–water interface. (22, 23) By synthesizing crystalline GDY directly on Au substrates, we used the plasmonic enhancement of the reconstructed Au surface to monitor the potential-dependent Raman responses of the GDY framework and interfacial water. Combined with *ab initio* molecular dynamics (AIMD) simulations and cation-retention measurements, the spectroscopic results support a synergistic ion-sieving mechanism in which hydration-shell reorganization, GDY pore confinement, and cation–GDY interactions jointly determine interfacial cation distribution within the GDY interfacial region. AIMD trajectories show that Li<sup>+</sup>/K<sup>+</sup> access GDY sublayer regions, whereas Na<sup>+</sup>/Cs<sup>+</sup> remain mainly near the outer interface within the simulated time window. These cation-dependent configurations are accompanied by interfacial-water reorganization, local charge redistribution, and distinct potential-dependent vibrational responses of cation-coordinated water and the GDY framework. The low-frequency diacetylenic band observed in NaOH and CsOH is further supported by the calculated vibrational response. This work links cation distribution, interfacial-water structure, and GDY vibrational response at an electrified porous carbon interface, providing a framework for understanding cation-specific EDL behavior in low-dimensional porous materials.

## Results and Discussion

### Preparation

and Structural Characterization of the Au–GDY
Platform

Crystalline GDY films were synthesized directly on Au electrodes using an electrochemical Glaser–Hay coupling system composed of an Au anode and a glassy carbon (GC) cathode in acetone containing the terminal alkyne precursor and Cu–TMEDA (*N*, *N*, *N*′, *N*′-tetramethylethylenediamine) catalyst (Figure 1 a, see Synthesis of Au–GDY Electrode in the Supporting Information). (15, 24) In this asymmetric configuration, the Au electrode serves as the anodic growth substrate, while the GC cathode completes the electrochemical circuit. The electric double layer enriches the alkynyl species near the Au surface and confines the Cu–mediated coupling reaction to the electrode interface. (25) Stabilization of Cu–alkynyl intermediates by Cu–TMEDA further limits solution-phase oligomerization and favors two-dimensional GDY growth. (26)

![Figure 1](10.1021_jacs.6c10062_assets/ja6c10062_0001.png)

**Figure 1.** Synthesis and structural characterization of the GDY electrode. (a) Schematic of the Glaser-Hay coupling synthesis of graphdiyne (GDY) on the Au substrate and the *in situ* SERS configuration. (b) HRTEM image (*d* = 0.47 nm) and (c) SAED pattern of GDY. Insets in panel (b) show the filtered lattice image and fast Fourier transform (FFT) pattern. (d) Raman spectrum featuring characteristic D, G, and diacetylenic stretching bands.

The *in situ* Raman sensitivity of Au–GDY arises from electrochemically induced reconstruction of the Au electrode. The anodic growth conditions promote surface roughening and generate SERS-active sites. (27) Atomic force microscope (AFM) and electrochemical roughness measurements confirm the successful reconstruction of the Au platform, while optical scattering and 4-ATP (4-aminothiophenol) measurements demonstrate its enhanced and relatively uniform Raman response (Figures S1–S4). Because the reconstructed Au surface is rough rather than ideally planar, the local surface orientations vary and the simple surface-selection rule associated with a uniform surface-normal field does not strictly apply. Morphological characterization further shows that the as-grown GDY forms a continuous and dense multilayer coating on Au, while the absence of an Au–O peak indicates no discernible electrolyte-accessible Au sites within the SERS-probed regions (Figures S5–S7). Accordingly, the measured SERS signal is treated as a depth-weighted response of the multilayer Au–GDY film.

The crystallinity of GDY was further examined after exfoliation from the Au substrate (Figure S8a). High-resolution transmission electron microscopy (HRTEM) images show continuous lattice fringes with an interlayer spacing of 0.36 nm, consistent with the reported π–π stacking distance of GDY (Figures S8b and S10). (17) The selected-area electron diffraction (SAED) pattern exhibits sharp sixfold-symmetric reflections (Figure 1 c), while the lattice spacing of 0.47 nm obtained from HRTEM is assigned to the (110) plane (Figure 1 b, inset; Figure S9). Indexing along the [001] zone axis supports the in-plane order and proposed ABC-stacking sequence (Figure S8c). (15, 16)

The composition of the synthesized GDY films was examined by X-ray photoelectron spectroscopy (XPS) and scanning transmission electron microscopy coupled with energy-dispersive X-ray spectroscopy (STEM–EDS), while the bonding structure was further analyzed by high-resolution XPS. The C 1s spectrum was deconvoluted into four components (28) at 284.5 eV (aromatic sp<sup>2</sup>-C), 285.1 eV (diacetylenic sp-C), 286.4 eV (C–O), and 287.7 eV (C═O). The integrated sp/sp<sup>2</sup> area ratio is 1.9, close to the theoretical value of 2.0 for ideal GDY, (15) supporting the diacetylenic framework. No Cu was detected by XPS, STEM–EDS, or inductively coupled plasma optical emission spectroscopy (ICP–OES) within their respective detection limits (Figures S11–S13 and Table S1).

Raman spectroscopy further confirms the characteristic vibrational features of GDY (Figure 1 d). The band at 2125 cm<sup>–1</sup> is assigned to the stretching vibration of the conjugated diacetylenic linkages (−C≡C–C≡C−). A weaker band near 1992 cm<sup>–1</sup> is also observed but is not assigned here. Comparison of the Raman spectra of HEB (hexaethynylbenzene), Cu–TMEDA, and GDY shows that the characteristic GDY bands are not dominated by precursor- or catalyst-related species (Figure S14). (29)

### Cation-Dependent

Evolution of the GDY Framework

The potential-dependent response of the GDY framework was monitored by *in situ* SERS in 0.1 M LiOH, NaOH, KOH, and CsOH (Figure 2 a–d). Because all four electrolytes contain the same 0.1 M OH<sup>–</sup> concentration, the comparison focuses on cation-dependent differences under a common alkaline condition. Relative to the *ex situ* diacetylenic band near 2125 cm<sup>–1</sup>, the *in situ* band appears near 2117 cm<sup>–1</sup> at +0.6 V (versus the reversible hydrogen electrode, RHE). This difference is associated with the transition from the *ex situ* state to the electrified solid–liquid environment. During cathodic polarization from +0.6 V to −0.7 V, this band weakens and red-shifts in all four electrolytes. (30, 31)

![Figure 2](10.1021_jacs.6c10062_assets/ja6c10062_0002.png)

**Figure 2.** Potential-dependent SERS evolution and apparent Stark tuning of the GDY framework. (a–d) *In situ* SERS spectra of the diacetylenic stretching region of GDY recorded in 0.1 M (a) LiOH, (b) NaOH, (c) KOH, and (d) CsOH electrolytes during cathodic polarization (from 0.6 V to −0.7 V). (e) Corresponding apparent Stark tuning plots (d *ν*/d *E*) for the diacetylenic linkages. Numbers denote the apparent Stark tuning rates in cm<sup>–1</sup>/V.

With increasing cathodic polarization, a cation-dependent divergence emerges. LiOH and KOH retain a single resolved diacetylenic band, whereas an additional low-frequency band initially near 2026 cm<sup>–1</sup> appears in NaOH and CsOH below approximately −0.2 V (Figure 2 a–d). The appearance of this new band may reflect a new local diacetylenic environment. Its microscopic origin is examined in the theoretical analysis below.

Control measurements confirm that these spectral changes are reversible and potential-dependent. Raman spectra before and after the electrochemical measurements show no persistent new diacetylenic feature, while potential cycling in NaOH shows that the low-frequency band disappears and the band near 2117 cm<sup>–1</sup> recovers upon returning to +0.6 V (Figure S15). Continuous irradiation produces no resolvable shift or splitting over 1800 s (Figure S16). These results exclude irreversible structural transformation or cumulative laser irradiation as the origin of the observed spectral evolution.

To quantify the potential-dependent vibrational response, components evolving from the diacetylenic band were tracked across the four electrolytes, and the potential dependence of their peak positions was analyzed (d *ν*/d *E*, Figure 2 e). Because the diacetylenic vibration can be influenced by potential-induced polarization and charging of the GDY framework, (30, 31) local electrostatics, (32) interfacial solvation, (33, 34) and cation-specific interactions, (35, 36) the fitted slopes are referred to as apparent Stark tuning rates and are not interpreted as direct measures of either the electric-field contribution or the cation effect. (37, 38)

All four systems exhibit a change in tuning regime during cathodic polarization. In the more negative-potential region, LiOH and KOH show apparent tuning rates of 36 and 34 cm<sup>–1</sup>/V, respectively, whereas NaOH and CsOH show values of 41 and 42 cm<sup>–1</sup>/V. The additional low-frequency bands in NaOH and CsOH exhibit apparent tuning rates of 43 and 46 cm<sup>–1</sup>/V, respectively. These differences indicate a clear cation dependence in both the magnitude and spectral evolution of the GDY vibrational response.

Cation-dependent vibrational tuning has also been reported at planar electrochemical interfaces. (39, 40) Direction-resolved vibrational density of states (VDOS) further shows that the diacetylenic vibration is mainly in-plane (Figure S44b), indicating that the observed shifts cannot be explained by the surface-normal EDL field alone. Consistently, the tetraethylammonium hydroxide (TEAOH) and open-circuit concentration controls show that neither potential-induced polarization of GDY nor cation–GDY interactions alone account for the spectral evolution observed in the alkali-metal electrolytes (Figures S17–S18). The following sections further examine the connections among this vibrational response, interfacial-water reorganization, and cation distribution within the GDY interfacial region.

### Cation-Dependent

Reorganization of Interfacial Water

To examine whether the cation-dependent vibrational response of GDY is accompanied by changes in interfacial-water structure, in situ SERS measurements were extended to the water vibrational region in all four electrolytes. Because low-frequency water vibrations and the H–O–H bending mode overlap with GDY bands in the 300–1800 cm<sup>–1</sup> region, analysis focused on the 3000–3800 cm<sup>–1</sup> O–H stretching region (Figure S20). The O–H envelope differs markedly from that of bulk water, (13, 14) indicating that bulk water is not the dominant contributor under the thin-layer electrochemical configuration (Figure S19). Accordingly, interfacial water here refers to the SERS-weighted water population adjacent to the electrolyte-accessible GDY surfaces and intrinsic pores. (13, 18)

NaOH was selected as the representative system in Figure 3, with LiOH, KOH, and CsOH shown in Figures S22–S27. Isotopic substitution with 0.1 M NaOD/D<sub>2</sub>O was used to verify the spectral assignment (Figure S21). The diacetylenic stretching mode (−C≡C–C≡C−) exhibited no discernible isotopic shift, whereas the broad solvent envelope shifted to the O–D stretching region (2200–2800 cm<sup>–1</sup>). The frequency ratio (*ν*<sub>OD</sub>/*ν*<sub>OH</sub> ≈ 0.74) supports the assignment to interfacial water.

![Figure 3](10.1021_jacs.6c10062_assets/ja6c10062_0003.png)

**Figure 3.** Potential-dependent structural evolution and deconvolution of interfacial water in 0.1 M NaOH. (a) *In situ* SERS spectral evolution and deconvolution of the O–H stretching envelope into 4HB·H<sub>2</sub>O, 2HB·H<sub>2</sub>O, and Na·H<sub>2</sub>O components. (b) Apparent Stark tuning plots of the corresponding interfacial-water components. (c) Corresponding populations estimated from the fitted Raman area fractions. The numbers denote the apparent Stark tuning rates in cm<sup>–1</sup>/V, and the shaded regions indicate the potential windows used for linear fitting.

The O–H envelope was deconvoluted into four-hydrogen-bonded water (4HB·H<sub>2</sub>O, ∼3225 cm<sup>–1</sup>), two-hydrogen-bonded water (2HB·H<sub>2</sub>O, ∼3450 cm<sup>–1</sup>), and cation-coordinated water (Na·H<sub>2</sub>O, ∼3600 cm<sup>–1</sup>). (14, 41) The same component assignments were used throughout each potential series, with the fitting constraints in Table S2. The fitted Raman area fractions are used here as SERS-weighted populations.

The fitted peak positions show distinct potential-dependent tuning regimes for the interfacial-water components (Figure 3 b). (42) In particular, the apparent Stark tuning rate of Na·H<sub>2</sub>O decreases from 105 to 80 cm<sup>–1</sup>/V toward more negative potentials. The corresponding populations also evolve systematically with potential (Figure 3 c). From +0.6 V to 0 V, the decrease in 4HB·H<sub>2</sub>O and increase in 2HB·H<sub>2</sub>O are consistent with a shift toward less extensively hydrogen-bonded configurations. (43) Below 0 V, the emergence of Na·H<sub>2</sub>O coincides with a partial recovery of 4HB·H<sub>2</sub>O and a decrease in 2HB·H<sub>2</sub>O, indicating redistribution among the interfacial hydrogen-bonding environment upon Na<sup>+</sup> coordination. (44, 45) At potentials more negative than −0.4 V, the Na·H<sub>2</sub>O population continues to increase, while its apparent tuning rate decreases to 80 cm<sup>–1</sup>/V, indicating concurrent changes in its population and vibrational response.

As M·H<sub>2</sub>O represents the cation-coordinated water, its apparent tuning behavior and potential-dependent population were compared across the four electrolytes (Figure 4 a–b). In the more negative-potential region, the magnitudes of the apparent Stark tuning rates of M·H<sub>2</sub>O follow the order Li<sup>+</sup> > K<sup>+</sup> > Na<sup>+</sup> > Cs<sup>+</sup>, with values of 100, 90, 80, and 58 cm<sup>–1</sup>/V, respectively. This order differs from that of the GDY diacetylenic band (Figure 2 e), showing distinct potential-dependent vibrational responses of cation-coordinated water and the GDY framework.

![Figure 4](10.1021_jacs.6c10062_assets/ja6c10062_0004.png)

**Figure 4.** Cation-dependent interfacial-water reorganization and cation distributions at the GDY–water interface. (a) Comparative apparent Stark tuning plots and (b) potential-dependent populations of cation-coordinated water (M·H<sub>2</sub>O) across the four electrolytes. Numbers in panel (a) denote the apparent tuning rates in cm<sup>–1</sup>/V for the corresponding linear-fitting regions. (c) Representative AIMD configurations showing cation-dependent distributions within the simulated time window: Li<sup>+</sup> and K<sup>+</sup> access GDY sublayer regions, whereas Na<sup>+</sup> and Cs<sup>+</sup> remain mainly near the outer interface, together with the corresponding interfacial-water structures.

The M·H<sub>2</sub>O population trends also differ among the electrolytes (Figure 4 b). In LiOH and KOH, the M·H<sub>2</sub>O population increases and approaches a plateau. In NaOH, it continues to increase at more negative potentials. In CsOH, it reaches a maximum near 0 V and then decreases toward a plateau. Both the apparent tuning behavior and population evolution of M·H<sub>2</sub>O therefore depend on cation identity. (46)

Despite these differences, changes in M·H<sub>2</sub>O occur within the potential range in which the GDY diacetylenic band enters a different apparent tuning regime (Figure S28). For NaOH and CsOH, the low-frequency band also emerges within this range. Thus, the GDY framework and cation-coordinated interfacial water respond over correlated potential ranges, although their detailed evolutions are not identical. Their frequency shifts are not attributed to a common microscopic mechanism. The O–H stretching response can couple more directly to the local interfacial field and is also sensitive to hydrogen bonding and cation coordination, whereas the predominantly in-plane GDY response may reflect combined contributions from framework polarization and charging, local electrostatics, cation-specific interactions, and solvation.

Representative AIMD configurations and *z*-axis atomic number-density profiles show that Li<sup>+</sup> and K<sup>+</sup> access GDY sublayer regions, whereas Na<sup>+</sup> and Cs<sup>+</sup> remain predominantly near the outer interface within the simulated time window (Figure 4 c and Figure S30). These distinct spatial distributions provide a structural basis for the cation-dependent interfacial-water response. Despite their different definitions, the experimental Raman area fractions and AIMD molecular number fractions show consistent cation- and potential-dependent trends for 4HB·H<sub>2</sub>O, 2HB·H<sub>2</sub>O, and M·H<sub>2</sub>O (Figure S29).

To assess cation retention experimentally, inductively coupled plasma mass spectrometry (ICP-MS) measurements were performed after 20 min of potentiostatic polarization. The area-normalized retained amounts of Li<sup>+</sup>, Na<sup>+</sup>, and K<sup>+</sup> were 1.82, 1.25, and 3.02 μmol cm<sup>–2</sup>, respectively, whereas Cs<sup>+</sup> was not detected (Table S3). The preferential retention of Li<sup>+</sup> and K<sup>+</sup> and the absence of detectable Cs<sup>+</sup> are qualitatively consistent with the AIMD results, although the Na<sup>+</sup> value is interpreted cautiously because of possible background contributions. As ICP-MS does not provide spatial information, these measurements are used only as complementary evidence for cation-dependent retention.

### Theoretical Analysis of the Cation-Regulated Electrified Interface

To identify the factors underlying the Li<sup>+</sup>/K<sup>+</sup> and Na<sup>+</sup>/Cs<sup>+</sup> grouping, cation size and hydration, free-energy changes associated with pore access, and the corresponding charge, electric field, and vibrational responses were analyzed.

Figure 5 a compares the bare cation diameters (47) and AIMD-derived hydrated diameters with the ∼2.6 Å effective GDY pore opening. (15, 48) All hydrated cations are larger than the pore opening, with Li<sup>+</sup> showing the largest hydrated diameter because of its persistent second hydration shell (Figure S37 and Table S4), indicating that pore access requires partial dehydration or hydration-shell reorganization. (49, 50) For K<sup>+</sup>, the small mismatch between its bare diameter (2.76 Å) and the pore opening may be accommodated by local framework relaxation. (51) Thus, neither bare-ion size nor hydration structure alone explains the Li<sup>+</sup>/K<sup>+</sup> and Na<sup>+</sup>/Cs<sup>+</sup> grouping.

![Figure 5](10.1021_jacs.6c10062_assets/ja6c10062_0005.png)

**Figure 5.** Theoretical analysis of the synergistic ion-sieving mechanism and cation-dependent interfacial responses. (a) Schematic comparison of the bare and effective hydrated diameters of Li<sup>+</sup>, Na<sup>+</sup>, K<sup>+</sup>, and Cs<sup>+</sup> with the effective GDY pore opening. (b) Relative free-energy profiles obtained from restrained AIMD along the cation *Z* coordinate, defined from the innermost GDY layer (*Z* = 0 Å); decreasing *Z* denotes motion toward the GDY sublayer. The free energy at *Z* = 8.5 Å is set to zero. (c) Representative two-dimensional charge-density-difference maps for the Li<sup>+</sup> (left) and Na<sup>+</sup> (right) systems at the outermost GDY plane. (d) Depth-dependent electric-field profiles obtained by Poisson integration of the planar-averaged charge-density differences. (e) Vibrational density of states of the GDY diacetylenic carbon atoms in the four cation systems.

Figure 5 b shows the free-energy changes associated with cation migration toward the GDY sublayer, obtained from restrained AIMD. The cation position is defined relative to the innermost GDY layer (*Z* = 0 Å), with the outer pore entrance located at *Z* ≈ 7.0 Å. At this entrance, Li<sup>+</sup> and K<sup>+</sup> show no uphill free-energy change, whereas Na<sup>+</sup> and Cs<sup>+</sup> encounter increases of ∼1.4 and ∼5.1 kcal mol<sup>–1</sup>, respectively. The energetic differences are consistent with the distinct pore-access behaviors in AIMD and rationalize the Li<sup>+</sup>/K<sup>+</sup> and Na<sup>+</sup>/Cs<sup>+</sup> grouping.

The cation-dependent configurations are accompanied by distinct interfacial charge redistribution. Two-dimensional maps for Li<sup>+</sup> and Na<sup>+</sup> show different patterns around the outermost GDY layer (Figure 5 c), while complementary three-dimensional and layer-resolved analyses show that the perturbations associated with Li<sup>+</sup> and K<sup>+</sup> extend into the GDY sublayers, whereas those associated with Na<sup>+</sup> and Cs<sup>+</sup> remain closer to the outer interface (Figures S39–S41). These patterns provide qualitative evidence of cation-dependent local polarization at the cation–GDY interface. Together, these analyses indicate that hydration-shell reorganization, pore confinement, (52) and cation–GDY interactions jointly govern cation accessibility within the GDY interfacial region.

Planar averaging and one-dimensional Poisson integration yield the depth-dependent electric-field profiles in Figure 5 d, with the corresponding Δρ(z) profiles shown in Figure S42. (53, 54) For Li<sup>+</sup> and K<sup>+</sup>, the field variation extends into the GDY sublayer region, whereas that for Na<sup>+</sup> and Cs<sup>+</sup> is more localized near the outer interface. This spatial differentiation parallels the experimental grouping: LiOH and KOH exhibit higher apparent Stark tuning rates for M·H<sub>2</sub>O but lower rates for the GDY diacetylenic band, whereas NaOH and CsOH show the reverse trend.

The AIMD-derived vibrational density of states (VDOS) shows cation-dependent features in the diacetylenic stretching region (Figure 5 e). Further analysis assigns the low-frequency feature near 2018 cm<sup>–1</sup> mainly to in-plane vibrations of outer-layer diacetylenic linkages (Figure S44). Density function theory (DFT) calculations for a representative Na<sup>+</sup> interfacial configuration identify several Raman-active modes in the 2000–2100 cm<sup>–1</sup> region (Table S5). Normal-mode analysis shows larger displacement amplitudes on diacetylenic linkages within the local region associated with Na<sup>+</sup> in the 2013.6 cm<sup>–1</sup> mode, whereas the 2086.1 cm<sup>–1</sup> mode shows more pronounced displacements on linkages farther from Na<sup>+</sup> (Figure S45). This spatial differentiation is consistent with a distinct local diacetylenic environment within the outer GDY layer and supports the assignment of the experimental low-frequency band near 2026 cm<sup>–1</sup> to locally perturbed outer-layer diacetylenic linkages.

Overall, the experimental and theoretical results support a synergistic ion-sieving mechanism and link the resulting cation distribution to interfacial charge redistribution, electric-field profiles, and vibrational responses.

## Conclusions

In summary, by combining *in situ* SERS and AIMD simulations, we characterized the potential-dependent responses of diacetylenic linkages and interfacial water at electrified GDY interfaces. The results support a synergistic ion-sieving mechanism in which hydration-shell reorganization, pore confinement, and cation–GDY interactions jointly influence the cation-dependent spatial distribution. Within the simulated time window, Li<sup>+</sup> and K<sup>+</sup> access GDY sublayer regions, whereas Na<sup>+</sup> and Cs<sup>+</sup> remain mainly near the outer interface. This spatial distribution is accompanied by distinct interfacial charge redistribution and electric-field profiles, consistent with the contrasting apparent Stark tuning behaviors of M·H<sub>2</sub>O and the GDY diacetylenic band. VDOS and Raman-mode analyses further support the assignment of the low-frequency diacetylenic band to outer-layer diacetylenic linkages in a distinct local environment. These results link cation distribution, interfacial-water reorganization, and GDY vibrational response at an electrified porous carbon interface.

## References (54 total, showing 54)

1. Fang, Y.; Liu, Y.; Qi, L.; Xue, Y.; Li, Y. 2D graphdiyne: an emerging
carbon material. Chem. Soc. Rev. 2022, 51, 2681–2709, https://doi.org/10.1039/D1CS00592H.
2. Salanne, M.; Rotenberg, B.; Naoi, K.; Kaneko, K.; Taberna, P. L.; Grey, C. P.; Dunn, B.; Simon, P. Efficient storage mechanisms
for building better supercapacitors. Nat. Energy 2016, 1, 16070 https://doi.org/10.1038/nenergy.2016.70.
3. Bunch, J. S.; Verbridge, S. S.; Alden, J. S.; van der Zande, A. M.; Parpia, J. M.; Craighead, H. G.; McEuen, P. L. Impermeable Atomic
Membranes from Graphene Sheets. Nano Lett. 2008, 8, 2458–2462, https://doi.org/10.1021/nl801457b.
4. Shi, G.; Lu, T.; Zhang, L. Understanding
the interfacial water structure in electrocatalysis. Natl. Sci. Rev. 2024, 11, nwae241 https://doi.org/10.1093/nsr/nwae241.
5. Elliott, J. D.; Papaderakis, A. A.; Dryfe, R. A. W.; Carbone, P. The Electrochemical
Double Layer at the Graphene/Aqueous Electrolyte Interface: What We
Can Learn from Simulations, Experiments, and Theory. J. Mater. Chem. C 2022, 10, 15201–15227, https://doi.org/10.1039/D2TC01631A.
6. Chen, X.; Jiang, X.; Yang, N. Graphdiyne
Electrochemistry: Progress
and Perspectives. Small 2022, 18, 2201135 https://doi.org/10.1002/smll.202201135.
7. Fu, X.; Huang, C.; Wang, Y.; Gao, J.; Wu, R.; Zhang, Z.; Yang, J.; Chang, Q.; Li, Y. Graphdiyne:
The Emerging Energy Conversion Material. Adv.
Funct. Mater. 2025, 35, 2424691 https://doi.org/10.1002/adfm.202424691.
8. An, J.; Zhang, H.; Qi, L.; Li, G.; Li, Y. Self-Expanding
Ion-Transport Channels on Anodes for Fast-Charging Lithium-Ion Batteries. Angew. Chem., Int. Ed. 2022, 61, e202113313 https://doi.org/10.1002/anie.202113313.
9. Li, J.; Yi, Y.; Zuo, X.; Hu, B.; Xiao, Z.; Lian, R.; Kong, Y.; Tong, L.; Shao, R.; Sun, J.; Zhang, J. Graphdiyne/Graphene/Graphdiyne
Sandwiched Carbonaceous Anode for
Potassium-Ion Batteries. ACS Nano 2022, 16, 3163–3172, https://doi.org/10.1021/acsnano.1c10857.
10. Li, J.; Zhou, K.; Liu, Q.; Tian, B.; Liu, X.; Cao, L.; Cao, H.; Li, G.; Zhang, X.; Han, Y.; Lai, Z. Synthesis of two-dimensional
ordered graphdiyne membranes for highly
efficient and selective water transport. Nat.
Water 2025, 3, 307–318, https://doi.org/10.1038/s44221-025-00397-9.
11. Xu, P.; Wang, R.; Zhang, H.; Carnevale, V.; Borguet, E.; Suntivich, J. Cation Modifies
Interfacial Water
Structures on Platinum during Alkaline Hydrogen Electrocatalysis. J. Am. Chem. Soc. 2024, 146, 2426–2434, https://doi.org/10.1021/jacs.3c09128.
12. Tian, Y.; Huang, B.; Song, Y.; Zhang, Y.; Guan, D.; Hong, J.; Cao, D.; Wang, E.; Xu, L.; Shao-Horn, Y.; Jiang, Y. Effect of Ion-Specific Water Structures
at Metal Surfaces on Hydrogen Production. Nat.
Commun. 2024, 15, 7834 https://doi.org/10.1038/s41467-024-52131-w.
13. Li, C.-Y.; Le, J.-B.; Wang, Y.-H.; Chen, S.; Yang, Z.-L.; Li, J.-F.; Cheng, J.; Tian, Z.-Q. In Situ Probing
Electrified Interfacial Water Structures at Atomically Flat Surfaces. Nat. Mater. 2019, 18, 697–701, https://doi.org/10.1038/s41563-019-0356-x.
14. Wang, Y. H.; Zheng, S.; Yang, W. M.; Zhou, R. Y.; He, Q. F.; Radjenovic, P.; Dong, J. C.; Li, S.; Zheng, J.; Yang, Z. L.; Attard, G.; Pan, F.; Tian, Z. Q.; Li, J. F. In situ Raman spectroscopy reveals
the structure and dissociation
of interfacial water. Nature 2021, 600, 81–85, https://doi.org/10.1038/s41586-021-04068-z.
15. Li, G.; Li, Y.; Liu, H.; Guo, Y.; Li, Y.; Zhu, D. Architecture
of graphdiyne nanoscale films. Chem. Commun. 2010, 46, 3256–3258, https://doi.org/10.1039/b922733d.
16. Matsuoka, R.; Sakamoto, R.; Hoshiko, K.; Sasaki, S.; Masunaga, H.; Nagashio, K.; Nishihara, H. Crystalline
Graphdiyne Nanosheets
Produced at a Gas/Liquid or Liquid/Liquid Interface. J. Am. Chem. Soc. 2017, 139, 3145–3152, https://doi.org/10.1021/jacs.6b12776.
17. Bao, H.; Wang, L.; Li, C.; Luo, J. Structural Characterization
and Identification of Graphdiyne and Graphdiyne-Based Materials. ACS Appl. Mater. Interfaces 2019, 11, 2717–2729, https://doi.org/10.1021/acsami.8b05051.
18. Wang, Y.-H.; Jin, X.; Xue, M.; Cao, M.-F.; Xu, F.; Lin, G.-X.; Le, J.-B.; Yang, W.-M.; Yang, Z.-L.; Cao, Y.; Zhou, Y.; Cai, W.; Zhang, Z.; Cheng, J.; Guo, W.; Li, J.-F. Characterizing
surface-confined interfacial water at
graphene surface by in situ Raman spectroscopy. Joule 2023, 7, 1652–1662, https://doi.org/10.1016/j.joule.2023.06.008.
19. Lin, X.-M.; Sun, Y.-L.; Chen, Y.-X.; Li, S.-X.; Li, J.-F. Insights
into Electrocatalysis through In Situ Electrochemical Surface-Enhanced
Raman Spectroscopy. eScience 2025, 5, 100352 https://doi.org/10.1016/j.esci.2024.100352.
20. Yang, Z.-L.; Zhu, Y.-Z.; Zhang, Y.-J.; Li, J.-F. Applications of
Surface-Enhanced Raman Spectroscopy in Mechanistic Studies of Fuel
Cells and Lithium Batteries. Chin. J. Light
Scatt. 2023, 35, 97–107.
21. Yin, X.-T.; You, E.-M.; Zhou, R.-Y.; Zhu, L.-H.; Wang, W.-W.; Li, K.-X.; Wu, D.-Y.; Gu, Y.; Li, J.-F.; Mao, B.-W.; Yan, J.-W. Unraveling the Energy
Storage Mechanism
in Graphene-Based Nonaqueous Electrochemical Capacitors by Gap-Enhanced
Raman Spectroscopy. Nat. Commun. 2024, 15, 5624 https://doi.org/10.1038/s41467-024-49973-9.
22. Li, J.-F.; Huang, Y.-F.; Ding, Y.; Yang, Z. L.; Li, S. B.; Zhou, X. S.; Fan, F. R.; Zhang, W.; Zhou, Z. Y.; Wu, D. Y.; Ren, B.; Wang, Z. L.; Tian, Z.-Q. Shell-isolated
nanoparticle-enhanced Raman spectroscopy. Nature 2010, 464, 392–395, https://doi.org/10.1038/nature08907.
23. Ding, S. Y.; Yi, J.; Li, J.-F.; Ren, B.; Wu, D.-Y.; Panneerselvam, R.; Tian, Z.-Q. Nanostructure-based
plasmon-enhanced Raman spectroscopy
for surface analysis of materials. Nat. Rev.
Mater. 2016, 1, 16021 https://doi.org/10.1038/natrevmats.2016.21.
24. Li, J.; Zhang, Z.; Kong, Y.; Yao, B.; Yin, C.; Tong, L.; Chen, X.; Lu, T.; Zhang, J. Synthesis
of wafer-scale ultrathin graphdiyne for flexible optoelectronic memory
with over 256 storage levels. Chem 2021, 7, 1284–1296, https://doi.org/10.1016/j.chempr.2021.01.021.
25. Tang, S.; Liu, Y.; Lei, A. Electrochemical
Oxidative Cross-coupling with Hydrogen
Evolution: A Green and Sustainable Way for Bond Formation. Chem 2018, 4, 27–45, https://doi.org/10.1016/j.chempr.2017.10.001.
26. Hu, G.; He, J.; Li, Y. Controllable Synthesis of Two-Dimensional Graphdiyne
Films Catalyzed by a Copper (II) Trichloro Complex. ACS Catal. 2022, 12, 6712–6721, https://doi.org/10.1021/acscatal.1c05967.
27. Wang, W.; Huang, Y.-F.; Liu, D.-Y.; Wang, F.-F.; Tian, Z.-Q.; Zhan, D. Electrochemically roughened gold
microelectrode for surface-enhanced
Raman spectroscopy. J. Electroanal. Chem. 2016, 779, 126–130, https://doi.org/10.1016/j.jelechem.2016.04.008.
28. Huang, C.; Li, Y.; Wang, N.; Xue, Y.; Zuo, Z.; Liu, H.; Li, Y. Progress in Research
into 2D Graphdiyne-Based Materials. Chem. Rev. 2018, 118, 7744–7803, https://doi.org/10.1021/acs.chemrev.8b00288.
29. Zhang, S.; Wang, J.; Li, Z.; Zhao, R.; Tong, L.; Liu, Z.; Zhang, J.; Liu, Z. Raman Spectra and Corresponding Strain
Effects in Graphyne and Graphdiyne. J. Phys.
Chem. C 2016, 120, 10605–10613, https://doi.org/10.1021/acs.jpcc.5b12388.
30. Pisana, S.; Lazzeri, M.; Casiraghi, C.; Novoselov, K. S.; Geim, A. K.; Ferrari, A. C.; Mauri, F. Breakdown of the Adiabatic
Born–Oppenheimer Approximation in Graphene. Nat. Mater. 2007, 6, 198–201, https://doi.org/10.1038/nmat1846.
31. Das, A.; Pisana, S.; Chakraborty, B.; Piscanec, S.; Saha, S. K.; Waghmare, U. V.; Novoselov, K. S.; Krishnamurthy, H. R.; Geim, A. K.; Ferrari, A. C.; Sood, A. K. Monitoring Dopants
by Raman Scattering in an Electrochemically Top-Gated Graphene Transistor. Nat. Nanotechnol. 2008, 3, 210–215, https://doi.org/10.1038/nnano.2008.67.
32. Goldsmith, Z. K.; Secor, M.; Hammes-Schiffer, S. Inhomogeneity of Interfacial Electric
Fields at Vibrational Probes on Electrode Surfaces. ACS Cent. Sci. 2020, 6, 304–311, https://doi.org/10.1021/acscentsci.9b01297.
33. Zhu, Q.; Wallentine, S. K.; Deng, G.-H.; Rebstock, J. A.; Baker, L. R. The Solvation-Induced
Onsager Reaction Field Rather than the Double-Layer Field Controls
CO 2 Reduction on Gold. JACS Au 2022, 2, 472–482, https://doi.org/10.1021/jacsau.1c00512.
34. Rebstock, J. A.; Zhu, Q.; Baker, L. R. Comparing
Interfacial Cation Hydration at Catalytic
Active Sites and Spectator Sites on Gold Electrodes: Understanding
Structure-Sensitive CO 2 Reduction Kinetics. Chem. Sci. 2022, 13, 7634–7643, https://doi.org/10.1039/D2SC01878K.
35. Yasuda, S.; Tamura, K.; Kato, M.; Asaoka, H.; Yagi, I. Electrochemically
Driven Specific Alkaline Metal Cation Adsorption on a Graphene Interface. J. Phys. Chem. C 2021, 125, 22154–22162, https://doi.org/10.1021/acs.jpcc.1c03322.
36. Zhan, C.; Cerón, M. R.; Campbell, P. G.; Pham, T. A.; Otani, M.; Wood, B. C.; Biener, J.; Kucheyev, S. O.; Wang, Y. M. Specific
Ion Effects at Graphitic Interfaces. Nat. Commun. 2019, 10, 4858 https://doi.org/10.1038/s41467-019-12854-7.
37. Andrews, S. S.; Boxer, S. G. Vibrational Stark
Effects of Nitriles I. Methods and
Experimental Results. J. Phys. Chem. A 2000, 104, 11853–11863, https://doi.org/10.1021/jp002242r.
38. Fried, S. D.; Boxer, S. G. Measuring electric
fields and noncovalent interactions
using the vibrational stark effect. Acc. Chem.
Res. 2015, 48, 998–1006, https://doi.org/10.1021/ar500464j.
39. Malkani, A. S.; Li, J.; Oliveira, N. J.; He, M.; Chang, X.; Xu, B.; Lu, Q. Understanding the Electric and Nonelectric Field Components of the
Cation Effect on the Electrochemical CO Reduction Reaction. Sci. Adv. 2020, 6, eabd2569 https://doi.org/10.1126/sciadv.abd2569.
40. Lee, S. Y.; Kim, J.; Bak, G.; Lee, E.; Kim, D.; Yoo, S.; Kim, J.; Yun, H.; Hwang, Y. J. Probing Cation Effects on *CO Intermediates
from Electroreduction of CO 2 through Operando Raman Spectroscopy. J. Am. Chem. Soc. 2023, 145, 23068–23075, https://doi.org/10.1021/jacs.3c05799.
41. Chen, X.; Wang, X.-T.; Le, J.-B.; Li, S.-M.; Wang, X.; Zhang, Y.-J.; Radjenovic, P.; Zhao, Y.; Wang, Y.-H.; Lin, X.-M.; Dong, J.-C.; Li, J.-F. Revealing the role
of interfacial water and key intermediates at ruthenium surfaces in
the alkaline hydrogen evolution reaction. Nat.
Commun. 2023, 14, 5289 https://doi.org/10.1038/s41467-023-41030-1.
42. Zhao, Y.; Li, Q.-Q.; He, Q.-F.; Ren, P.-W.; Zhang, D.-A.; Wang, Y.-H.; Dong, J.-C.; Zheng, S.; Zhang, Y.-J.; Yang, Z.-L.; Li, J.-F. In Situ
Raman Spectroscopy Reveals
the Multifunctional Role of Interfacial Water in CO 2 -to-C 2 Electroreduction on Cu(hkl) Surfaces. J. Am. Chem. Soc. 2025, 147, 30230–30238, https://doi.org/10.1021/jacs.5c08922.
43. Gomes, R. J.; Kumar, R.; Fejzić, H.; Sarkar, B.; Roy, I.; Amanchukwu, C. V. Modulating Water Hydrogen Bonding within a Non-Aqueous
Environment Controls Its Reactivity in Electrochemical Transformations. Nat. Catal. 2024, 7, 689–701, https://doi.org/10.1038/s41929-024-01162-z.
44. Marcus, Y. Effect of
Ions on the Structure of Water: Structure Making and Breaking. Chem. Rev. 2009, 109, 1346–1370, https://doi.org/10.1021/cr8003828.
45. Tang, B.; Fang, Y.; Zhu, S.; Bai, Q.; Li, X.; Wei, L.; Li, Z.; Zhu, C. Tuning hydrogen bond network connectivity
in the electric double layer with cations. Chem.
Sci. 2024, 15, 7111–7120, https://doi.org/10.1039/D3SC06904D.
46. Men, Y.; Men, X.; Li, P.; Li, L.; Wang, X.; Su, X.; Zhang, L.; Chen, S.; Luo, W. Cation-Driven Modulation
of Interfacial Solvation Structures for Enhanced Alkaline Hydrogen
Oxidation Kinetics. J. Am. Chem. Soc. 2025, 147, 21672–21685, https://doi.org/10.1021/jacs.5c03433.
47. Shannon, R. D. Revised
Effective Ionic Radii and Systematic Studies of Interatomic Distances
in Halides and Chalcogenides. Acta Crystallogr.,
Sect. A 1976, 32, 751–767, https://doi.org/10.1107/S0567739476001551.
48. Pakdel, S.; Erfan-Niya, H.; Azamat, J.; Hasanzadeh, A. Highly Efficient
Helium Purification through a Dual-Membrane System: Insights from
Molecular Dynamics Simulations. Phys. Chem.
Chem. Phys. 2023, 25, 30572–30582, https://doi.org/10.1039/D3CP04797K.
49. Abraham, J.; Vasu, K. S.; Williams, C. D.; Gopinadhan, K.; Su, Y.; Cherian, C. T.; Dix, J.; Prestat, E.; Haigh, S. J.; Grigorieva, I. V.; Carbone, P.; Geim, A. K.; Nair, R. R. Tunable
sieving of ions using graphene oxide membranes. Nat. Nanotechnol. 2017, 12, 546–550, https://doi.org/10.1038/nnano.2017.21.
50. Rigo, E.; Dong, Z.; Park, J. H.; et al. Measurements of the
Size and Correlations between Ions Using an Electrolytic Point Contact. Nat. Commun. 2019, 10, 2382 https://doi.org/10.1038/s41467-019-10265-2.
51. Bartolomei, M.; Carmona-Novillo, E.; Hernández, M. I.; Campos-Martínez, J.; Pirani, F.; Giorgi, G. Graphdiyne Pores: ″ Ad Hoc ″ Openings for Helium Separation Applications. J. Phys. Chem. C 2014, 118, 29966–29972, https://doi.org/10.1021/jp510124e.
52. Merlet, C.; Rotenberg, B.; Madden, P. A.; Taberna, P.-L.; Simon, P.; Gogotsi, Y.; Salanne, M. On the Molecular Origin of Supercapacitance
in Nanoporous Carbon Electrodes. Nat. Mater. 2012, 11, 306–310, https://doi.org/10.1038/nmat3260.
53. Bhattacharyya, D.; Videla, P. E.; Palasz, J. M.; Tangen, I.; Meng, J.; Kubiak, C. P.; Batista, V. S.; Lian, T. Sub-Nanometer Mapping
of the Interfacial Electric Field Profile Using a Vibrational Stark
Shift Ruler. J. Am. Chem. Soc. 2022, 144, 14330–14338, https://doi.org/10.1021/jacs.2c05563.
54. Le, J. B.; Fan, Q. Y.; Li, J. Q.; Cheng, J. Molecular origin of
negative component of Helmholtz capacitance at electrified Pt (111)/water
interface. Sci. Adv. 2020, 6, eabb1219 https://doi.org/10.1126/sciadv.abb1219.
