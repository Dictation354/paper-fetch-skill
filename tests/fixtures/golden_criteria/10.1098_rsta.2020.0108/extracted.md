---
title: "royalsocietypublishing.org/journal/rsta"
doi: "10.1098/rsta.2020.0108"
source: "royalsocietypublishing_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: false
token_estimate: 19309
---

# royalsocietypublishing.org/journal/rsta

# Topics in the mathematical design of materials 

royalsocietypublishing.org/journal/rsta 

## Introduction 

**Cite this article:** Chen X, Fonseca I, Ravnik M, Slastikov V, Zannoni C, Zarnescu A. 2021 Topics in the mathematical design of materials. _Phil. Trans.R.Soc.A_ **379** : 20200108. https://doi.org/10.1098/rsta.2020.0108 

Accepted: 29 March 2021 

One contribution of 10 to a theme issue ‘Topics in mathematical design of complex materials’. 

###### **Subject Areas:** 

materials science, applied mathematics, mechanical engineering, computer modelling and simulation 

###### **Keywords:** 

materials design, soft matter, alloys, epitaxy, liquid crystals, colloids, magnetic materials 

**Author for correspondence:** 

Arghir Zarnescu e-mail: azarnescu@bcamath.org 

Xian Chen<sup>1</sup> , Irene Fonseca<sup>2</sup> , Miha Ravnik<sup>3,4</sup> ,Valeriy Slastikov<sup>5</sup> , Claudio Zannoni<sup>6</sup> and Arghir Zarnescu<sup>7,8,9</sup> 

1Department of Mechanical and Aerospace Engineering, Hong Kong University of Science and Technology, Pokfulam, Hong Kong 2Carnegie Mellon University, 5000 Forbes Avenue, Pittsburgh, PA 15213, USA 

3University of Ljubljana, Jadranska, 19, 1000 Ljubljana, Slovenia 4Jozef Stefan Insitute, Jamova cesta, 39, 1000 Ljubljana, Slovenia 5School of Mathematics, University of Bristol, Bristol BS8 1TW, UK 6Dipartimento di Chimica Industriale ‘Toso Montanari’ and INSTM, Università di Bologna, Viale Risorgimento, 4, 40136 Bologna, Italy 7BCAM, Basque Center for Applied Mathematics, Alameda Mazarredo, 14 Bilbao 48009, Spain 

8IKERBASQUE, Basque Foundation for Science, Plaza Euskadi, 

5 48009 Bilbao, Bizkaia, Spain 

9‘Simion Stoilow’ Institute of the Romanian Academy, 

21 Calea Grivitei, 010702 Bucharest, Romania 



XC, 0000-0002-0114-4642; MR, 0000-0001-8883-9318; CZ, 0000-0002-7977-1005; ADZ, 0000-0002-3620-6196 

We present a perspective on several current research directions relevant to the mathematical design of new materials. We discuss: (i) design problems for phase-transforming and shape-morphing materials, (ii) epitaxy as an approach of central importance in the design of advanced semiconductor materials, (iii) selected design problems in soft matter, (iv) mathematical <u>problems</u> in magnetic materials, <u>(v)</u> some open problems in liquid crystals and soft materials and (vi) mathematical problems on liquid crystal colloids. The presentation combines topics from soft and hard condensed matter, with specific focus on those design themes where mathematical approaches could possibly lead to exciting progress. 

This article is part of the theme issue ‘Topics in mathematical design of complex materials’. 

~~2021 The Author(s) Published by the Royal Society. All rights reserved.~~ 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~2~~** 

### 1. Introduction 

Many recent and spectacular advances in the world of materials are related to complex materials having extraordinary and unique features. The last few decades have seen the discovery and development of a large number of such materials, both hard and soft, including shape memory alloys, carbon nanotubes, graphene, nematic elastomers, liquid crystals, colloids, polymeric fluids, to name just a few. Such materials are key to much technology appearing in our daily lives: they are in liquid crystal displays, in miniaturized phones, special steels in cars, plastics and composites in the construction of modern aeroplanes, in biological implants in human bodies, and so on. However, despite the impressive use of these materials, their theoretical understanding and modelling are in many ways still in their infancy. 

The development of materials with novel properties is the foundation of modern technologies. Human intelligence, or more precisely the engineering heuristics, guides the discovery of new materials, but the transitioning of the property from the initial discovery to the optimized one for practical use usually takes more than a decade. For examples, the discovery of the magnetocaloric effect [1] of magnetic materials reforms the idea of modern refrigeration, and the discovery of the photovoltaic effect in semiconductors [2] revolutionizes power generation technologies. More than a century after, physicists and chemists are still working on the improvement of performance using those novel materials. Property optimization by experiment is much more time consuming than the optimization of software, algorithms and simulation models. 

A common feature in the successful development of the existing models of complex materials has been the presence of genuine contributions from many different scientific and technological disciplines, all under the umbrella of mathematical models attempting to provide a manageable theoretical framework for describing them as well as predicting their properties. This mathematical framework allows, for instance, to combine and optimize mixtures of existing materials, and provides the theoretical tools for identifying necessary conditions for the existence of new classes of materials, with _a priori_ desired properties. Thus, the mathematical models are not only needed for describing complex materials, but are also the key to something much more creative, the mathematical design of new materials having prescribed or unusual properties. In the following, we present a selection of directions for which mathematics could play a significant role in the design of new materials. The list of topics is by no means exhaustive, but inevitably rather based on the experience and preferences of the authors. 

### 2. Design problems for phase-transforming and shape-morphing materials 

Conventional strategies for the design of materials are inherited from the traditional metallurgy. Take the shape memory alloy with applications to medical devices and smart actuators as an example. The discovery of the superelasticity of the Nickel – Titanium (NiTi) alloy was in the 1960s [3] but optimized products for replacing steels in stents were delayed by 30 years. During those 30 years, a large body of work was done to refine the processing parameters of synthesis, precipitation and heat treatment [4]. The discussions of the effects of the delicate alloying procedure, the thermomechanical processing, the sizes of precipitates, the temperature and duration of heat treatments resulted in more than 10 000 publications and patents [4–12]. Thanks to all the predecessors’ efforts, the mechanical properties of polycrystalline NiTi were improved by a large margin. NiTi has become the most successful shape memory alloy and is widely commercialized for the biomedical industry. By 2015, NiTi had contributed to more than a 50% market share among all metallic materials, with a market size of USD 33 billion. The Cu-based shape memory alloys, such as CuAlNi and CuAlZn, exhibit even higher superelastic strain compared to NiTi [13,14]. An almost equal amount of experimental efforts were paid to improve their mechanical properties, but the outcomes are not satisfactory, especially the poor thermomechanical reversibility under cyclic loading conditions for polycrystals [11,15,16]. 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~3~~** 

These material development procedures can be rationalized under mathematical guidance. Recent advances in developing the low-hysteresis and/or high-resilience shape memory alloys are successful material design cases [17–20] based on the geometric nonlinear theory and crystallographic compatibility conditions. It is theorized that the satisfaction of the cofactor conditions [18] allows for spectacular new microstructures and results in a dramatic enhancement of the functionalities in phase-transforming metals [17–19] and ceramics [20]. As a mathematical foundation, the cofactor conditions underlie a tuning direction of lattice parameters and symmetries of phase transforming materials for achieving lower thermal hysteresis and higher phase reversibility. The martensitic material can be theorized by a transformation stretch tensor, which determines the interface morphology and represents the microstructure related properties. When this tensor satisfies the mechanics criteria, the material will show tremendous enhancement in functionalities. Conceptually, it enlightens a design strategy for new shape memory alloys. 

Another emerging mathematical design problem is to seek various folding modes for the origami flexible electronics [21,22]. Most engineering designs [23–26] are based on the simplest Miura-Ori algorithm [27], which uses a one-parameter family of deformations to fold along the crease and form repeated mountains and valleys. It is worth noting that the Miura-Ori is a basic example in the class of rigidly and flat-foldable quadrilateral mesh origami (RFFQM). The mathematical understanding of RFFQM has progressed notably since the 1990s [28,29]. Algorithms are developed to parameterize the configuration space of RFFQM [30,31], which inspire new ideas on flat crease pattern design for the achievement of abundant shape-morphing capabilities with practical use in engineering. 

### 3. Epitaxy: design of advanced materials 

The study of the epitaxial deposition process of a thin film onto a substrate is of central importance in the manufacturing of semiconductor electronic and optoelectronic devices (e.g. [32–39]). Energetically, in hetero-systems such as InGaAs/GaAs or Si Ge/Si, the profile of the film is flat until a critical thickness is reached, after which the competition between elastic and surface energies, due to the mismatch between the lattice constants in the film and the substrate, leads to a release of energy, and the profile becomes corrugated, creating clusters or isolated islands (quantum dots) on the substrate surface. These self-assembled quantum-dots have proven to be useful in many technological applications, including optical and optoelectronic devices like quantum dot lasers (see [40]). 

In recent years, there has been extensive study of existence, regularity and stability of equilibrium configurations obtained by energy minimization. In [41], the authors extended to the three-dimensional setting what was previously obtained in two dimensions (see [42–48]), although in [49,50] the three-dimensional case was considered in the geometrically nonlinear setting and with linear elasticity under antiplane-shear assumption. 

Interesting questions to be addressed are the extension to three dimensions of results previously obtained in two dimensions concerning the design and shapes of the quantum dots (see [51]), and the onset and distribution of dislocations (see [52]) as they influence the performance of these material systems. Furthermore, the mathematical analysis of the phenomenon of capping in epitaxy is untouched to date. 

In [51], the authors studied a two-dimensional fully faceted model as developed in spectrophotometry [38,53], which takes into account the miscut angle between the substrate and the film as has been observed experimentally, for example in the growth of Germanium (Ge) on Silicon (Si) substrates (see [54]). Relevant to optical applications (see [38]), and as it was validated in two dimensions, it would be interesting in three dimensions to mathematically rigorously explain the hierarchy of quantum dots shapes and geometric properties as depending of the film volume fraction (see [38,44], and explain why a non-zero miscut angle favours asymmetric island shapes (see [54–56]). 

As mentioned in [52], experiments indicate that the nucleation of dislocations is a further mode of strain relief after some critical thickness has been reached. When cusp-like morphologies 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~4~~** 

are formed, the resulting configuration has greater energy than that exhibiting the nucleation of dislocations. Furthermore, once dislocations are formed they migrate to the film/substrate interface, and the film surface relaxes towards a planar-like morphology (e.g. [33,57–60]). In [52], this was demonstrated for two-dimensional configurations corresponding to three-dimensional morphologies with planar symmetry. The next task is now to extend this analysis to fully three-dimensional configurations. 

The study of the phenomenon of capping in epitaxy is still unexplored from the analytical viewpoint. Capping of quantum dots has been extensively studied experimentally (e.g. [61]; see also [62] for capping of GaAs dots by Ga1− _x_ In _x_ As), but there is very little known that theoretically validates these experimental results. As capping proceeds with substrate material, dot material is driven from the quantum dots onto the wetting layer by capillary-like forces, and as a result the size of the dots is reduced. In the end, a few dots remain and these are surrounded by a ring-shaped capping material; these dots are elastically compressed by the capping material that surrounds them and often it is energetically favourable to release this energy by ejecting dot material from the centre of the dot and forming ring-like structures (see [63]). As shown in [46], it is energetically favourable to keep a wetting layer of dot material between islands since it has lower surface energy density. At lower temperature (below 725 K), the morphology of dots remains unchanged during capping, and at a much higher temperature almost all dots are completely eroded. The mathematical explanation and reconciliation of this phenomenon with the fact that, by contrast, during the formation of the dots increasing the temperature enhances their onset, remain open. 

### 4. Selected design problems in soft matter 

Soft matter encompasses a range of materials from bio and active matter to elastomers, foams, fluids, polymers and colloids, that furthermore are subjected to and controlled by diverse material equilibrium and dynamic mechanisms [64–73]. Here, we give only very selected examples where material design is seen to be highly relevant, and moreover more formal, mathematical, approaches could possibly lead to exciting progress. 

#### (a) Self-assembly 

The concept of self-assembly is today widely used to create diverse soft materials [74–76]. In self-assembly, the material organizes, assembles at large scale by itself with only limited or no external active interference, as the actual material design is effectively embedded already in the local interactions and properties of the basic material building blocks. 

The variety of building blocks that self-assemble into complex structures include particles [76], nanoparticles [77], block copolymers [78], cellulose [79] or macromolecules [80]. These are rich and diverse material systems with exciting, sometimes unique, material properties and phenomena which could be improved with formal guidance from mathematics like: how to formulate the full design phase space, how robust are different self assembly pathways, could these pathways be branched to formulate different materials, what are relative energy barriers between energy states and is there multi-stability? An impressive example of designed selfassembly is DNA self-assembly [81,82], where designed DNA base pair sequences is used to control and create highly controlled nanostructures. 

#### (b) Topological defects 

A range of soft matter materials inherently can embed non-trivial topology, usually through formation of diverse topological defects. Examples include topological defects in liquid crystals [83–85], polymer knots [86], knotted fluid vortex lines [87] and DNA knots [88]. 

These systems can create diverse topological matter as they crucially depend on combined control over the topology as well as the energetics of the material under consideration or material 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~5~~** 

field(s). Therefore, it is an underlying question how to guide the system to form a general, i.e. designed-topological state, notably subjected to different equilibrium (free) energy or dynamic conditions and constraints. 

#### (c) Shape-morphing 

Shape-morphing has diverse modern applications, ranging from printed artificial cilia [89], morphing wind turbine blades [90], to wearable haptic communicators [91] and self-cleaning surfaces [92], and being able to design the changes in the shape rather than observe them can bring fundamental change in the possible use of such materials. 

Multiple approaches for realizing soft morphing materials today include three-dimensional [93] and four-dimensional printing [94]. Especially, the focus on soft matter shape morphing materials is due to its prevalence in nature, compatibility with users and potential for novel design [95–97]. For example, the possible role of mathematics is to perform as the model tool between the designed macroscopic shape and the actual microstructure that is encoded/written into the material. Prominent shape-morphing materials explored today are nematic elastomers which are capable of large expansion or shrinkage [98,99]. In nematic elastomers, it was recently demonstrated that the shape morphing can be designed by the internal structure (spatial profile) of the molecular orientational order, leading to diverse targeted geometrical shape changes [99]. More generally, liquid crystal polymer networks and elastomers can be used for diverse programmable and adaptive mechanics [100] with efficient engineering and reverse-engineering approaches. 

### 5. Mathematical problems in magnetic materials 

Magnetic materials are a good source of many fundamental problems in energy-driven pattern formation [101]. In particular, ferromagnets embody at the same time three subtle and challenging characteristics, namely topologically protected structures [102–105], nonlocal (i.e., long-range) interactions [106,107], and the breaking of chiral (or mirror) symmetry [108,109]. The interplay between these features influences the equilibrium and dynamical properties of magnetic microstructures in thin ferromagnetic films, generates a rich variety of intricate spatio-temporal patterns and opens up the opportunity to design novel magnetic devices [110–112]. 

The appropriate theoretical model for magnetic phenomena depends on the length scale of interest. For scales down to a few nanometres, there is a well established and extremely successful continuum theory of magnetism, the micromagnetic variational principle [106]. At the nanoscale, the contributions of interfaces between different materials and effects of a ferromagnet geometry become progressively more important and lead to novel physical effects and mathematical models [109,113]. Below we present several interesting research directions and some open mathematical problems, focusing on ultrathin ferromagnetic layers. 

#### (a) Ground states in curved thin layers 

Ferromagnetic curved layers provide the means to design specific properties of magnetic nanostructure by tailoring its geometry formation [114,115]. One of the important consequences of non-trivial curvature is the appearance of anti-symmetric exchange [116], leading to novel magnetization patterns [114,117]. The properties of these newly observed ground states are of interest from both the physical and mathematical points of view. One of the important questions is related to the symmetry of the ground states or global minimizers of the micromagnetic energy. Even in the case of simple symmetric curved layers like the cylinders or spheres there is no complete classification of the ground states of a basic local version of the micromagnetic energy [118]. Developing suitable mathematical tools to address the questions of symmetry for harmonic-type maps on symmetric surfaces is a non-trivial problem in the calculus of variations and PDEs. 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~6~~** 

#### (b) Magnetoelasticity 

Magneto-elastic materials are used in many applications due to their ability to change shape in response to applied electric or magnetic fields. Multiple examples of such applications include programmable magnetic materials [119], shapeable magnetoelectronics [120] and magnetic colloids [121] used in micro- and nano-robotics, engineering smart materials and biomedical devices (e.g. [120,122,123]). Although magneto-elastic materials have been studied for some time, their theoretical understanding and modelling in the context of flexible ferromagnetic nanostructures and ferromagnetic colloids is still in progress (e.g. [121,124,125]). Obtaining appropriate reduced models for thin magneto-elastic films, stripes and wires and investigating magnetization patterns and elastic response due to applied fields is an interesting and challenging task. 

#### (c) Two-dimensional magnetic materials and multilayers 

Atomically thin magnetic layers exhibit a range of new phenomena not present in conventional thin magnetic films or bulk magnets, for instance, anti-symmetric exchange, perpendicular magnetic anisotropy, etc (e.g. [109,113,126–128]). This is due to the fact that interfacial and material boundary effects become increasingly dominant, resulting in new physical phenomena and leading to the appearance of novel magnetic microstructures such as edge domain walls and vortices, chiral skyrmions, etc. Use of atomically thin layers to assemble magnetic heterostructures opens up an opportunity to create magnetic materials with prescribed properties [128]. Understanding the physics of these multilayered structures leads to a range of new problems including derivation of physically sound and analytically accessible models, and their investigation using mathematical tools of modern analysis. 

#### (d) Magnetic skyrmions 

Skyrmions are topologically protected spin textures which have been observed in ultrathin ferromagnetic films with non-zero interfacial Dzyaloshinskii–Moria interaction [109,113,129]. Using skyrmions as information carriers holds great promise to revolutionize spintronic devices (e.g. [130,131]). The investigation of magnetic skyrmions was initiated by Bogdanov & Yablonskii [132]. From the rigorous mathematical point of view, existence, stability and profiles of skyrmions of degree one have been investigated in the whole plane using local and nonlocal versions of micromagnetic energy (e.g. [133,134]). The questions on existence and profiles of skyrmions of other degrees still remain open (in both bounded domains and the whole plane) even though numerical simulations and experiments provide a good intuition [109,135,136]. Another interesting direction is related to the formation and internal structure of skyrmion lattices [129,137], where so far no significant progress has been made in explaining the formation of skyrmion lattices and their properties using rigorous analysis. 

### 6. Some open problems in liquid crystals and soft materials 

Bottom up modelling and simulations of liquid crystals have been tackled with various approaches, starting from the simplest lattice models, where molecules are represented by spins positioned on a regular lattice, to off lattice molecular models where anisotropic particles endowed with a certain pair potential mimic mesogens and their shape, to atomistic approaches where molecules are represented as connected set of atoms with the geometry and flexibility appropriate to their chemical composition [138]. In particular, atomistic approaches have demonstrated the predictive potential of present-day modelling and molecular dynamics simulations, including the possibility of reproducing transition temperatures [139] as well as their variation when the chemical structure undergoes even small changes [140], elastic constants [141] and surface alignment on various substrates [142–144]. Even though this approach is very 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~7~~** 

demanding in terms of resources, it provides a test bench for microscopic and phenomenological theories of liquid crystals (like mean field and density functional theories) and in particular for the validity of assumptions like molecular uniaxiality and rigidity [145] . More importantly, atomistic simulations open exciting and to some extent unforeseen possibilities for the practical molecular design of novel mesogens with the prediction of their properties, also in advance of their chemical synthesis. 

A few interesting open problems within the modelling approaches mentioned above, are: 

#### (a) Simulating non-equilibrium systems 

The vast majority of atomistic or molecular simulations involve, and indeed are based on, systems at thermodynamic equilibrium, while many systems, particularly formed of complex molecules like polymers, are intrinsically out of equilibrium, at least during their fabrication process, and their properties often strongly depend on their thermal history and fabrication technology. This is particularly relevant for soft materials for Organic Electronic applications like Field Effect Transistors (OFET), Organic Light Emitting Diodes OLED or Organic Solar Cells, where some fabrication processes like shearing [146] may be used to generate and stabilize certain out-ofequilibrium structures with favourable properties (e.g. charge transport [147]). The fabrication processes can be very different and should be accounted for, instead of being neglected, in numerical simulations. For instance, vapour deposition and molecular beam epitaxy are often employed with low molar mass molecules [148,149] while thin films of polymers and block copolymers are instead usually produced by wet deposition techniques, including spin-coating, inkjet or roll-to-roll printing [150,151]. In all cases, the process parameters and post-deposition treatments (e.g. solvent evaporation and annealing) can have a major effect on the final structure and properties of the films and should be accounted for by simulations. The development of novel suitable techniques would be very welcome. 

#### (b) Active systems 

An important class of non-equilibrium systems are those formed by active particles [152,153], of great interest now, particularly as they provide models for colonies of living systems (from bacteria to fish schools, etc.) that involve the feeding of energy or nutrients. Rigorous ways of defining and computing temperature and other important variables whose definition is based on equilibrium would be of help, particularly for particle or molecular-based simulations (while continuum, hydrodynamic type theories [152,154] are more well developed). 

#### (c) Force fields and artificial intelligence techniques 

As already mentioned, atomistic molecular dynamics simulations have proved to be capable of realistically predicting transition temperatures and material properties for low molar mass liquid crystals like, for instance, the popular cyanobiphenyls [139,155]. However, their success critically depends on the development of suitable sets of interaction potentials between atoms or groups of atoms, the so-called force fields (FF), without which the transition temperatures can be mistaken by tens of degrees or, even, some of the mesophases experimentally observed risk of being missed altogether [156–158]. A major problem, after having obtained the proof of principle that these realistic predictions can be performed, is now to develop automated, effective and rapid methods to produce FFs. Artificial Intelligence Machine Learning techniques [159] that have been recently promisingly investigated for metals, alloys, and generally ‘hard’ materials [160] would seem an interesting and timely approach that should be seriously explored also for the more difficult case of soft materials [161,162] and liquid crystals in particular. 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~8~~** 

#### (d) Simulating mixtures 

The overwhelming majority of systems simulated, until now, using Monte Carlo [163] or Molecular Dynamics [164] techniques, consist of pure, one component, materials, although some recent exceptions exist [165]. However, particularly in industrial application, the materials employed are mixtures of various components. As an example, liquid crystals used in the display industry are often mixtures of ten or more components, so as to tune their nematic-isotropic transition temperature into the desired range for operation as well as to optimize their physical properties [166]. A major ensuing problem for simulations is the need for sample sizes with a number of particles sufficiently large to ensure that all components of the mixture, even minority ones, contain enough molecules to ensure that the results are statistically meaningful. At the moment, no clever method to deal with samples with unequal population, albeit desirable, is available, and brute force simulation of sufficiently large systems is the only option. 

#### (e) Microscopic, molecular interpretation of parameters in Landau type theories 

Landau-de Gennes theories based on an expansion of the free energy of a liquid crystal in terms of order parameters and their gradients have been put on a rigorous basis [167]. The parameters in the theory should be amenable, at least for simple lattice or possibly off-lattice molecular models, to being obtained by a detailed analysis of computer simulated results for the distribution of order parameters at various temperatures across the transition. This has proved too challenging until now, even for large scale Monte Carlo simulations [168], but should provide an important link between rigorous theories and simulations. 

### 7. Mathematical problems on liquid crystal colloids 

Liquid crystal colloids are a subject of intense research in the current physics literature [169] while being largely untouched from a mathematical point of view. The existing mathematical studies focus on either the presence and qualitative properties of a defect-type structure around a single particle [170–172] or many particles and the homogenization effects [173–176]. 

Nevertheless, the physics literature raises a significant number of intriguing issues which are well within the range of applicability of existing mathematical techniques. Understanding these will require interpolating between existing studies and attempting to understand the interplay between the well-studied defects and the presence of many particles. In the following, we present two relevant directions: 

#### (a) Optimal shape and distribution for colloidal mixtures 

We consider the issue of minimizing an energy functional over a domain with periodic holes and surface energy on the holes, in the space of functions taking values into order parameter manifolds. From a physical point of view this amounts to considering an ambient complex material with nanoparticles in it (the holes). Working with functions taking values into manifolds is expected to create significant challenges, as there will be topological effects generated by this constraint on the target of the functions. 

Some natural design questions emerge: 

##### (i) Allow the shape of the holes to vary, being the element to be optimized 

For a given distribution of the holes (namely the type of lattices on which the holes will be arranged) obtain qualitative information on the optimal local minimizers. Are the holes symmetric, and if so in what sense and how does their symmetry vary when changing the intensity of the surface energy (this is a parameter that can be controlled in a physical context by suitable treating of the nanoparticle surface)? 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~9~~** 

- (ii) Considertopologically constrainedboundary conditions(ontheboundary ofthenematicsampleonly, not on the colloids) 

Fix the shape of the holes but not their position. It is important to understand how the defects created in the liquid crystal distribute inside the domain and how this is related to the topological constraints. This is a particularly interesting issue allowing us to obtain a rigorous understanding of various papers in the physics literature in which the defects are claimed to localize around nanoparticles and generate mechanisms for moving around the nanoparticles. 

#### (b) Colloidal alignment through surface energy manipulation 

The objective of aligning the colloidal particles appears again and again in the physics literature, being related to nanoparticles transport, self-assembly or photonic crystals. Currently, the most common way of obtaining this alignment is through active manipulation of each colloidal particle, for instance by using lasers, see [177]. 

A physically more natural and less expensive approach would be to treat the boundaries of either the ambient liquid crystal sample or the boundaries of the immersed colloidal particles to obtain an _a priori_ predefined pattern of arrangement (such as hexagonal, rectangular latices, or linear arrangement of colloid particles) _without external interventions, just by using_ the natural gradient dynamics of the system, and its expected evolution towards a stable state under the equation of motion and energy minimization. We discuss separately each case: 

##### (i) Manipulation of the sample boundary 

It is well understood by now in the physics literature that topological frustration imposed at the boundary creates defects within the nematics and these defects can act as anchors for trapping colloidal particles. There exist a number of works within the physical literature that provide a number of empirically determined, yet experimentally checked recipes for achieving predetermined patterns of energy-minimizing configurations [178–180]. These use for instance dimension reduction through choosing suitably simple geometries or by combining periodic patterns. These can provide valuable starting points for obtaining various types of lattice-periodic patterns of energy minimizers. 

##### (ii) Manipulation of the colloids boundary 

The surface energy imposed at the boundary of the colloidal particles describes at a macroscopic level how the particle interacts with the surrounding nematic host. Depending on its strength it can locally produce various types of defect patterns around the colloidal particle [171]. A secondorder effect concerns the interaction between various particles through their surface energies. This is a small effect, yet significant in determining the localizations of the particles through mutual interactions. An example of the interplay between the boundary conditions and the localization of the particles is available in the classical work [181] where the notion of minimal connection encodes the interaction between particles due to the topological frustration at the boundaries. 

One also has interactions between the surface energy at the boundary of the colloids and the boundary conditions imposed on the sample. It was noted in the physics literature, for instance in [178], that one can consider locally convex or concave deformation at the sample boundary and then put tangential or normal boundary conditions on the colloidal particles to achieve an attraction or repulsion of the particles towards the boundary. Of course, it should be noted though that generically the interaction between the particles and the boundary of the sample is even weaker than the interactions between the particles themselves, simply because the boundary of the sample is, generically, further away from the particle than are the neighbouring particles. Thus while the interaction between particles is a second-order effect, the interaction between particles and boundary-data on the sample can be seen as a third-order effect (in generic geometries and 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~10~~** 

boundary conditions). Understanding and quantifying these in a mathematically rigorous fashion should be within reach of current variational techniques. 

### 8. Conclusion 

Mathematical design of new materials is relevant in a range of hard and soft matter material systems, including memory alloys, semiconductors, complex fluids, liquid crystals, colloids and elastomers. This work identifies selected topics where advances in the mathematical design indicate potential for exciting progress. In memory alloys, we comment on the general approaches to enhancement in material functionalities, such as hysteresis behaviour and material resilience, and discuss emerging mathematical design problems in folding modes of flexible material origami. In the case of epitaxial deposition of thin films onto a substrate, we point out questions of extension of material performance understanding from two-dimensional to three-dimensional, such as the design of shapes, and the onset and distribution of dislocations. In soft matter, mathematical design is discussed from the perspective of self-assembly, topological defects and shape-morphing, with open questions including the design of the full phase space, robustness of self-assembly pathways, multi-stability, guiding the system to a specific, i.e. a designed, topological state and development of efficient engineering and reverse-engineering approaches, that couple the material morphing with the material micro structure. In magnetic materials, the proposed research directions concern the understanding of ground states in curved thin layers, magnetoelasticity issues, aspects in two-dimensional magnetic materials and multilayers and problems concerning magnetic skyrmions. In liquid crystal and soft materials, open problems also include simulating non-equilibrium systems, defining and computing material and system variables in active matter systems, possible determination of simulation force fields using artificial intelligence techniques, development of clever methods to deal with simulation of mixtures with unequal populations of components, and microscopic, molecular interpretation of parameters in Landau type theories. Additionally, selected mathematical problems in liquid crystal colloids include optimal shape and distribution for colloidal mixtures and colloidal alignment through surface energy manipulation. 

To generalize, many recent and spectacular advances in the world of materials are related to complex materials having extraordinary and unique features, usually determined by their specific microstructure. Such materials are key to much technology appearing in our daily lives: they are in liquid crystal displays, in miniaturized phones, special steels in cars, plastics and composites in the construction of modern aeroplanes, in biological implants in human bodies, and so on. However, despite the impressive technological applications of these materials, the theoretical understanding and modelling of them are still inadequate. The need for models and basic understanding is not just of theoretical interest, but indeed a key requirement for being able to access and further develop the true potential of these materials, to optimize them, to combine them into new materials, and to use them for creating new devices, with predefined abilities and behaviours. Mathematical areas that are directly relevant to the scientific questions of interest include optimization and calculus of variations, geometry and topology, continuum mechanics and partial differential equations. Finally, the aim of this perspective and review paper is to underlie and highlight the importance of using mathematics as the guiding tool in the optimal and novel design of materials. 

Data accessibility. This article has no additional data. 

Authors’ contributions. A.Z. coordinated and compiled the paper. All authors contributed to the writing and correcting of the manuscript. All authors read and approved the manuscript. The authors are listed in alphabetical order. 

Competing interests. We declare we have no competing interests. 

Funding. X.C. thanks the financial support by HK Research Grants Council of Hong Kong through the grant no. 16201019. M.R. acknowledges funding from the Slovenian Research Agency ARRS under contracts P10099, J1-2462 and J1-1697 and EU ERC Advanced grant LOGOS. I.F. was partially supported by the National Science Foundation (NSF) under grants no. DMS-1411646 and DMS-1906238. V.S. acknowledges support by 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~11~~** 

Leverhulme grant no. RPG-2018-438. The work of A.Z. is supported by the Basque Government through the BERC 2018-2021 program, by Spanish Ministry of Economy and Competitiveness MINECO through BCAM Severo Ochoa excellence accreditation SEV-2017-0718 and through project MTM2017-82184-R funded by (AEI/FEDER, UE) and acronym ‘DESFLU’. 

Acknowledgements. The authors gratefully acknowledges the Isaac Newton Institute for Mathematical Sciences for support and hospitality during the programme ‘The design of new materials’ when work on this paper was undertaken. This work was supported by: EPSRC grant nos. EP/K032208/1 and EP/R014604/1. X.C., M.R., V.S. and A.Z. gratefully acknowledge a Simons Fellowship during this programme. I.F. gratefully acknowledges a Kirk Distinguished Visiting Fellowship during this programme. 

### References 

1. Warburg E. 1881 Magnetische untersuchungen. _Annalen der Physik_ **249** , 141–164. (doi:10. 1002/andp.18812490510) 

2. Millikan RA. 1916 A direct photoelectric determination of Planck’s" h". _Phys. Rev._ **7** , 355. (doi:10.1103/PhysRev.7.355) 

3. Buehler WJ, Gilfrich JV, Wiley R. 1963 Effect of low-temperature phase changes on the mechanical properties of alloys near composition TiNi. _J. Appl. Phys._ **34** , 1475–1477. (doi:10.1063/1.1729603) 

4. Otsuka K, Ren X. 2005 Physical metallurgy of Ti–Ni-based shape memory alloys. _Prog. Mater Sci._ **50** , 511–678. (doi:10.1016/j.pmatsci.2004.10.001) 

5. Abujudom D, Thoma P, Fariabi S. 1990 The effect of cold work and heat treatment on the phase transformations of near equiatomic NiTi shape memory alloy. In _Materials Science Forum_ , vol. 56, pp. 565–570. Trans Tech Publ. 

6. Yeung K, Cheung K, Lu W, Chung C. 2004 Optimization of thermal treatment parameters to alter austenitic phase transition temperature of NiTi alloy for medical implant. _Mater. Sci. Eng.: A_ **383** , 213–218. (doi:10.1016/j.msea.2004.05.063) 

7. Frick CP, Ortega AM, Tyber J, Maksound AEM, Maier HJ, Liu Y, Gall K. 2005 Thermal processing of polycrystalline NiTi shape memory alloys. _Mater. Sci. Eng.: A_ **405** , 34–49. (doi:10.1016/j.msea.2005.05.102) 

8. Gall K, Tyber J, Wilkesanders G, Robertson SW, Ritchie RO, Maier HJ. 2008 Effect of microstructure on the fatigue of hot-rolled and cold-drawn NiTi shape memory alloys. _Mater. Sci. Eng.: A_ **486** , 389–403. (doi:10.1016/j.msea.2007.11.033) 

9. Pereira E, Peixoto I, Viana A, Oliveira I, Gonzalez B, Buono V, Bahia M. 2012 Physical and mechanical properties of a thermomechanically treated NiTi wire used in the manufacture of rotary endodontic instruments. _Int. Endod. J._ **45** , 469–474. (doi:10.1111/j.1365-2591.2011.01998.x) 

10. Elahinia MH, Hashemi M, Tabesh M, Bhaduri SB. 2012 Manufacturing and processing of NiTi implants: a review. _Prog. Mater Sci._ **57** , 911–946. (doi:10.1016/j.pmatsci.2011.11.001) 

11. Duerig TW, Melton K, Stöckel D. 2013 _Engineering aspects of shape memory alloys_ . Tiptree, UK: Butterworth-Heinemann. 

12. Saedi S, Turabi AS, Andani MT, Haberland C, Karaca H, Elahinia M. 2016 The influence of heat treatment on the thermomechanical response of Ni-rich NiTi alloys manufactured by selective laser melting. _J. Alloys Compd._ **677** , 204–210. (doi:10.1016/j.jallcom.2016.03.161) 

13. Otsuka K, Wayman C, Nakai K, Sakamoto H, Shimizu K. 1976 Superelasticity effects and stress-induced martensitic transformations in CuAlNi alloys. _Acta Metall._ **24** , 207–226. (doi:10.1016/0001-6160(76)90071-7) 

14. Dutkiewicz J, Kato H, Miura S, Messerschmidt U, Bartsch M. 1996 Structure changes during pseudoelastic deformation of CuAIMn single crystals. _Acta Mater._ **44** , 4597–4609. (doi:10.1016/1359-6454(96)00086-9) 

15. Miyazaki S, Otsuka K. 1989 Development of shape memory alloys. _ISIJ Int._ **29** , 353–377. (doi:10.2355/isijinternational.29.353) 

16. Tadaki T. 1998 Cu-based shape memory alloys. In _Shape memory alloys_ (eds K Otsuka, CM Wayman eds), pp. 97–116. Cambridge, UK: Cambridge University Press. 

17. Song Y, Chen X, Dabade V, Shield TW, James RD. 2013 Enhanced reversibility and unusual microstructure of a phase-transforming material. _Nature_ **502** , 85–88. (doi:10.1038/ nature12532) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~12~~** 

18. Chen X, Srivastava V, Dabade V, James RD. 2013 Study of the cofactor conditions: conditions of supercompatibility between phases. _J. Mech. Phys. Solids_ **61** , 2566–2587. (doi:10.1016/j.jmps.2013.08.004) 

19. Chluba C, Ge W, de Miranda RL, Strobel J, Kienle L, Quandt E, Wuttig M. 2015 Ultralowfatigue shape memory alloy films. _Science_ **348** , 1004–1007. (doi:10.1126/science.1261164) 

20. Jetter J, Gu H, Zhang H, Wuttig M, Chen X, Greer JR, James RD, Quandt E. 2019 Tuning crystallographic compatibility to enhance shape memory in ceramics. _Phys. Rev. Mater._ **3** , 093603. (doi:10.1103/PhysRevMaterials.3.093603) 

21. Overvelde JT, De Jong TA, Shevchenko Y, Becerra SA, Whitesides GM, Weaver JC, Hoberman C, Bertoldi K. 2016 A three-dimensional actuated origami-inspired transformable metamaterial with multiple degrees of freedom. _Nat. Commun._ **7** , 1–8. (doi:10.1038/ncomms10929) 

22. Cai J, Deng X, Feng J, Zhou Y. 2015 Geometric design and mechanical behavior of a deployable cylinder with Miura origami. _Smart Mater. Struct._ **24** , 125031. (doi:10.1088/ 0964-1726/24/12/125031) 

23. Silverberg JL, Evans AA, McLeod L, Hayward RC, Hull T, Santangelo CD, Cohen I. 2014 Using origami design principles to fold reprogrammable mechanical metamaterials. _Science_ **345** , 647–650. (doi:10.1126/science.1252876) 

24. Wei ZY, Guo ZV, Dudte L, Liang HY, Mahadevan L. 2013 Geometric mechanics of periodic pleated origami. _Phys. Rev. Lett._ **110** , 215501. (doi:10.1103/PhysRevLett.110.215501) 

25. Schenk M, Guest SD. 2013 Geometry of Miura-folded metamaterials. _Proc. Natl Acad. Sci. USA_ **110** , 3276–3281. (doi:10.1073/pnas.1217998110) 

26. Na JH, Evans AA, Bae J, Chiappelli MC, Santangelo CD, Lang RJ, Hull TC, Hayward RC. 2015 Programming reversibly self-folding origami with micropatterned photo-crosslinkable polymer trilayers. _Adv. Mater._ **27** , 79–85. (doi:10.1002/adma.201403510) 

27. Miura K. 1985 Method of packaging and deployment of large membranes in space. _The Institute of Space and Astronautical Science report_ **618** , 1–9. 

28. Hull T. 1994 On the mathematics of flat origamis. _Congressus numerantium_ pp. 215–224. 

29. Hull TC _et al._ 2002 Modelling the folding of paper into three dimensions using affine transformations. _Linear Algebra Appl._ **348** , 273–282. (doi:10.1016/S0024-3795(01)00608-5) 

30. Lang RJ, Howell L. 2018 Rigidly foldable quadrilateral meshes from angle arrays. _J. Mech. Rob._ **10** , 021004. (doi:10.1115/1.4038972) 

31. Feng F, Dang X, James RD, Plucinsky P. 2020 The designs and deformations of rigidly and flat-foldable origami. _J. Mech. Phys. Solids_ **142** , 104018. (doi:10.1016/j.jmps.2020.104018) 

32. Asaro R, Tiller W. 1972 Interface morphology development during stress corrosion cracking: Part I. Via surface diffusion. _Metall. Mater. Trans. B_ **3** , 1789–1796. (doi:10.1007/BF02642562) 

33. Gao H, Nix WD. 1999 Surface roughening of heteroepitaxial thin films. _Annu. Rev. Mater. Sci._ **29** , 173–209. (doi:10.1146/annurev.matsci.29.1.173) 

34. Kukta R, Freund L. 1997 Minimum energy configuration of epitaxial material clusters on a lattice-mismatched substrate. _J. Mech. Phys. Solids_ **45** , 1835–1860. (doi:10.1016/ S0022-5096(97)00031-8) 

35. Spencer B. 1999 Asymptotic derivation of the glued-wetting-layer model and contactangle condition for Stranski-Krastanow islands. _Phys. Rev. B_ **59** , 2011–2017. (doi:10.11 03/PhysRevB.59.2011) 

36. Spencer B, Meiron D. 1994 Nonlinear evolution of the stress-driven morphological instability in a 2-dimensional semi-infinite solid. _Acta Metall. Mater._ **42** , 3629–3641. (doi:10.1016/0956-7151(94)90429-4) 

37. Spencer B, Tersoff J. 1997 Equilibrium shapes and properties of epitaxially strained islands. _Phys. Rev. Lett._ **79** , 4858–4861. (doi:10.1103/PhysRevLett.79.4858) 

38. Spencer B, Tersoff J. 2010 Asymmetry and shape transitions of epitaxially strained islands on vicinal surfaces. _Appl. Phys. Lett._ **96** , 073114. (doi:10.1063/1.3318256) 

39. Xiang Y, Weinan E. 2004 Misfit elastic energy and a continuum model for epitaxial growth with elasticity on vicinal surfaces. _Phys. Rev. B_ **69** , 035409. (doi:10.1103/PhysRevB.69.035409) 

40. Stangl J, Hol`y V, Bauer G. 2004 Structural properties of self-organized semiconductor nanostructures. _Rev. Mod. Phys._ **76** , 725. (doi:10.1103/RevModPhys.76.725) 

41. Crismale V, Friedrich M. 2020 Equilibrium configurations for epitaxially strained films and material voids in three-dimensional linear elasticity. _Arch. Ration. Mech. Anal._ **237** , 1041–1098. (doi:10.1007/s00205-020-01525-3) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~13~~** 

42. Bella P, Goldman M, Zwicknagl B. 2015 Study of island formation in epitaxially strained films on unbounded domains. _Arch. Ration. Mech. Anal._ **218** , 163–217. (doi:10.1007/ s00205-015-0858-x) 

43. Bonacini M. 2013 Epitaxially strained elastic films: the case of anisotropic surface energies. _ESAIM Control Optim. Calc. Var._ **19** , 167–189. (doi:10.1051/cocv/2012003) 

44. Bonnetier E, Chambolle A. 2002 Computing the equilibrium configuration of epitaxially strained crystalline films. _SIAM J. Appl. Math._ **62** , 1093–1121. (doi:10.1137/ S0036139900368571) 

45. Fonseca I, Leoni G, Morini M. 2017 Equilibria and dislocations in epitaxial growth. _Nonlinear Anal._ **154** , 88–121. (doi:10.1016/j.na.2016.10.013) 

46. Fonseca I, Fusco N, Leoni G, Morini M. 2007 Equilibrium configurations of epitaxially strained crystalline films: existence and regularity results. _Arch. Ration. Mech. Anal._ **186** , 477–537. (doi:10.1007/s00205-007-0082-4) 

47. Fusco N, Morini M. 2012 Equilibrium configurations of epitaxially strained elastic films: second order minimality conditions and qualitative properties of solutions. _Arch. Ration. Mech. Anal._ **203** , 247–327. (doi:10.1007/s00205-011-0451-x) 

48. Goldman M, Zwicknagl B. 2014 Scaling law and reduced models for epitaxially strained crystalline films. _SIAM J. Math. Anal._ **46** , 1–24. (doi:10.1137/120897250) 

49. Kreutz LC, Piovano P. 2021 Microscopic validation of a variational model of epitaxially strained crystalline films. _SIAM J. Math. Anal._ **53** , 453–490. (doi:10.1137/19M1240010) 

50. Chambolle A, Solci M. 2007 Interaction of a bulk and a surface energy with a geometrical constraint. _SIAM J. Math. Anal._ **39** , 77–102. (doi:10.1137/060649173) 

51. Fonseca I, Pratelli A, Zwicknagl B. 2014 Shapes of epitaxially grown quantum dots. _Arch. Ration. Mech. Anal._ **214** , 359–401. (doi:10.1007/s00205-014-0767-4) 

52. Fonseca I, Fusco N, Leoni G, Morini M. 2018 A model for dislocations in epitaxially strained elastic films. _J. Math. Pures Appl. (9)_ **111** , 126–160. (doi:10.1016/j.matpur.2017.09.001) 

53. Tersoff J, Tromp R. 1993 Shape transition in growth of strained islands: spontaneous formation of quantum wires. _Phys. Rev. Lett._ **70** , 2782. (doi:10.1103/PhysRevLett.70.2782) 

54. Sutter P, Sutter E, Vescan L. 2005 Barrierless self assembly of Ge quantum dots on Si (001) substrates with high local vicinality. _Appl. Phys. Lett._ **87** , 161916. (doi:10.1063/1.2108133) 

55. Denker U _et al._ 2005 Lateral motion of SiGe islands driven by surface-mediated alloying. _Phys. Rev. Lett._ **94** , 216103. (doi:10.1103/PhysRevLett.94.216103) 

56. Ross FM, Tromp R, Reuter M. 1999 Transition states between pyramids and domes during Ge/Si island growth. _Science_ **286** , 1931–1934. (doi:10.1126/science.286.5446.1931) 

57. Elder KR, Provatas N, Berry J, Stefanovic P, Grant M. 2007 Phase-field crystal modeling and classical density functional theory of freezing. _Phys. Rev. B_ **75** , 064107. (doi:10.1103/PhysRevB.75.064107) 

58. Haataja M, Müller J, Rutenberg A, Grant M. 2002 Dislocations and morphological instabilities: continuum modeling of misfitting heteroepitaxial films. _Phys. Rev. B_ **65** , 165414. (doi:10.1103/PhysRevB.65.165414) 

59. Jesson D, Pennycook S, Baribeau JM, Houghton D. 1993 Direct imaging of surface cusp evolution during strained-layer epitaxy and implications for strain relaxation. _Phys. Rev. Lett._ **71** , 1744. (doi:10.1103/PhysRevLett.71.1744) 

60. Tersoff J, LeGoues F. 1994 Competing relaxation mechanisms in strained layers. _Phys. Rev. Lett._ **72** , 3570. (doi:10.1103/PhysRevLett.72.3570) 

61. Gong Q, Offermans P, Notzel R, Koenraad PM, Wolter JH. 2004 Capping process of InAs/GaAs quantum dots studied by cross-sectional scanning tunneling microscopy. _Appl. Phys. Lett._ **85** , 5697–5699. (doi:10.1063/1.1831564) 

62. Berbezier I, Ronda A, Volpi F, Portavoce A. 2003 Morphological evolution of SiGe layers. _Surf. Sci._ **531** , 231–243. (doi:10.1016/S0039-6028(03)00488-6) 

63. Schulze TP, Smereka P. 2012 Kinetic Monte Carlo simulation of heteroepitaxial growth: wetting layers, quantum dots, capping, and nanorings. _Phys. Rev. B_ **86** , 235313. (doi:10.1103/PhysRevB.86.235313) 

64. De Gennes PG. 1992 Soft matter. _Rev. Mod. Phys._ **64** , 645. (doi:10.1103/RevModPhys.64.645) 

65. Lubensky T. 1997 Soft condensed matter physics. _Solid State Comm._ **102** , 187–197. (doi:10.1016/S0038-1098(96)00718-1) 

66. Pochan D, Kumar S, Hammond N. 2019 Celebrating soft matter’s 15th Anniversary. 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~14~~** 

67. Marchetti MC, Joanny JF, Ramaswamy S, Liverpool TB, Prost J, Rao M, Simha RA. 2013 Hydrodynamics of soft active matter. _Rev. Mod. Phys._ **85** , 1143. (doi:10.1103/ RevModPhys.85.1143) 

68. Aloi A, Voets IK. 2018 Soft matter nanoscopy. _Curr. Opin. Colloid & Interface Sci._ **34** , 59–73. (doi:10.1016/j.cocis.2018.03.001) 

69. Shibayama M, Li X, Sakai T. 2018 Gels: from soft matter to biomatter. _Ind. Eng. Chem. Res._ **57** , 1121–1128. (doi:10.1021/acs.iecr.7b04614) 

70. Assenza S, Mezzenga R. 2019 Soft condensed matter physics of foods and macronutrients. _Nat. Rev. Phys._ **1** , 551–566. (doi:10.1038/s42254-019-0077-8) 

71. McKenna GB. 2018 Soft matter: rubber and networks. _Rep. Prog. Phys._ **81** , 066602. (doi:10.1088/1361-6633/aaafe2) 

72. Lagerwall JP, Scalia G. 2012 A new era for liquid crystal research: applications of liquid crystals in soft matter nano-, bio-and microtechnology. _Curr. Appl. Phys._ **12** , 1387–1412. (doi:10.1016/j.cap.2012.03.019) 

73. Menzel AM. 2015 Tuned, driven, and active soft matter. _Phys. Rep._ **554** , 1–45. (doi:10.1016/j.physrep.2014.10.001) 

74. Whitesides GM, Grzybowski B. 2002 Self assembly at all scales. _Science_ **295** , 2418–2421. (doi:10.1126/science.1070821) 

75. Pelesko JA. 2007 _Self assembly: the science of things that put themselves together_ . Boca Raton, FL: CRC Press. 

76. Nagarajan R. 2019 _Self assembly: from surfactants to nanoparticles_ . Hoboken, NJ: John Wiley & Sons. 

77. Grzelczak M, Vermant J, Furst EM, Liz-Marzán LM. 2010 Directed self assembly of nanoparticles. _ACS Nano_ **4** , 3591–3605. (doi:10.1021/nn100869j) 

78. Li C, Li Q, Kaneti YV, Hou D, Yamauchi Y, Mai Y. 2020 Self assembly of block copolymers towards mesoporous materials for energy storage and conversion systems. _Chem. Soc. Rev._ **49** , 4681–4736. (doi:10.1039/D0CS00021C) 

79. Habibi Y, Lucia LA, Rojas OJ. 2010 Cellulose nanocrystals: chemistry, self assembly, and applications. _Chem. Rev._ **110** , 3479–3500. (doi:10.1021/cr900339w) 

80. Stephanopoulos N. 2020 Hybrid nanostructures from the self assembly of proteins and DNA. _Chem_ **6** , 364–405. (doi:10.1016/j.chempr.2020.01.012) 

81. Rothemund PW. 2006 Folding DNA to create nanoscale shapes and patterns. _Nature_ **440** , 297–302. (doi:10.1038/nature04586) 

82. Zhang T, Hartl C, Frank K, Heuer-Jungemann A, Fischer S, Nickels PC, Nickel B, Liedl T. 2018 3D DNA origami crystals. _Adv. Mater._ **30** , 1800273. (doi:10.1002/adma.201800273) 

83. Chaikin PM, Lubensky TC, Witten TA. 1995 _Principles of condensed matter physics_ . Cambridge, UK: Cambridge University Press. 

84. Kleman M, Laverntovich OD. 2007 _Soft matter physics: an introduction_ . Berlin, Heidelberg: Springer-Verlag. 

85. Alexander GP. 2018 Topology in liquid crystal phases. In _The Role of Topology in Materials_ , pp. 229–257. Springer. 

86. Michieletto D, Marenduzzo D, Orlandini E, Turner MS. 2017 Ring polymers: threadings, knot electrophoresis and topological glasses. _Polymers_ **9** , 349. (doi:10.3390/polym9080349) 

87. Kleckner D, Irvine WT. 2013 Creation and dynamics of knotted vortices. _Nat. Phys._ **9** , 253– 258. (doi:10.1038/nphys2560) 

88. Orlandini E. 2017 Statics and dynamics of DNA knotting. _J. Phys. A: Math. Theor._ **51** , 053001. (doi:10.1088/1751-8121/aa9a4c) 

89. Van Oosten CL, Bastiaansen CW, Broer DJ. 2009 Printed artificial cilia from liquid crystal network actuators modularly driven by light. _Nat. Mater._ **8** , 677–682. (doi:10.1038/nmat 2487) 

90. Lachenal X, Daynes S, Weaver PM. 2013 Review of morphing concepts and materials for wind turbine blade applications. _Wind Energy_ **16** , 283–307. (doi:10.1002/we.531) 

91. Zhao H, Hussain AM, Israr A, Vogt DM, Duduta M, Clarke DR, Wood RJ. 2020 A wearable soft haptic communicator based on dielectric elastomer actuators. _Soft Rob._ **7** , 451–461. (doi:10.1089/soro.2019.0113) 

92. Kim S, Cheung E, Sitti M. 2009 Wet self-cleaning of biologically inspired elastomer mushroom shaped microfibrillar adhesives. _Langmuir_ **25** , 7196–7199. (doi:10.1021/ la900732h) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~15~~** 

93. Truby RL, Lewis JA. 2016 Printing soft matter in three dimensions. _Nature_ **540** , 371–378. (doi:10.1038/nature21003) 

94. Gladman AS, Matsumoto EA, Nuzzo RG, Mahadevan L, Lewis JA. 2016 Biomimetic 4D printing. _Nature Mater._ **15** , 413–418. (doi:10.1038/nmat4544) 

95. Oliver K, Seddon A, Trask RS. 2016 Morphing in nature and beyond: a review of natural and synthetic shape-changing materials and mechanisms. _J. Mater. Sci._ **51** , 10 663–10 689. (doi:10.1007/s10853-016-0295-8) 

96. Jeon SJ, Hauser AW, Hayward RC. 2017 Shape-morphing materials from stimuli-responsive hydrogel hybrids. _Acc. Chem. Res._ **50** , 161–169. (doi:10.1021/acs.accounts.6b00570) 

97. Modes C, Warner M. 2016 Shape-programmable materials. _Phys. Today_ **69** , 32. (doi:10.1063/PT.3.3051) 

98. Warner M, Terentjev EM. 2007 _Liquid Crystal Elastomers_ , vol. 120. Oxford, UK: Oxford University Press. 

99. Ula SW, Traugutt NA, Volpe RH, Patel RR, Yu K, Yakacki CM. 2018 Liquid crystal elastomers: an introduction and review of emerging technologies. _Liq. Cryst. Rev._ **6** , 78–107. (doi:10.1080/21680396.2018.1530155) 

100. White TJ, Broer DJ. 2015 Programmable and adaptive mechanics with liquid crystal polymer networks and elastomers. _Nat. Mater._ **14** , 1087–1098. (doi:10.1038/nmat4433) 

101. Kohn R. 2007 Energy-driven pattern formation. In _Int. congress of mathematicians_ , volume 1, pp. 359–383. European Mathematical Society Zürich, Switzerland. 

102. Roessler UK, Bogdanov A, Pfleiderer C. 2006 Spontaneous skyrmion ground states in magnetic metals. _Nature_ **442** , 797–801. (doi:10.1038/nature05056) 

103. Braun HB. 2012 Topological effects in nanomagnetism: from superparamagnetism to chiral quantum solitons. _Adv. Phys._ **61** , 1–116. (doi:10.1080/00018732.2012.663070) 

104. Donnelly C _et al._ 2020 Experimental observation of vortex rings in a bulk magnet. _Nat. Phys._ **17** , 1–6. (doi:10.1038/s41567-020-01057-3) 

105. Miltat J, Thiaville A. 2002 Vortex cores–smaller than small. _Science_ **298** , 555–555. (doi:10.1126/science.1077704) 

106. Brown W. 1963 _Micromagnetics_ . New York, NY: John Wiley & Sons. 

107. Di Fratta G, Muratov CB, Rybakov FN, Slastikov VV. 2020 Variational principles of micromagnetics revisited. _SIAM J. Math. Anal._ **52** , 3580–3599. (doi:10.1137/19M1261365) 

108. Bode M _et al._ 2007 Chiral magnetic order at surfaces driven by inversion asymmetry. _Nature_ **447** , 190–193. (doi:10.1038/nature05802) 

109. Soumyanarayanan A, Reyren N, Fert A, Panagopoulos C. 2016 Emergent phenomena induced by spin–orbit coupling at surfaces and interfaces. _Nature_ **539** , 509–517. (doi:10.1038/nature19820) 

110. Hubert A, Schäfer R. 1998 _Magnetic domains: the analysis of magnetic microstructures_ . New York, NY: Springer. 

111. Zutic I, Fabian J, Das Sarma S. 2004 Spintronics: fundamentals and applications. _Rev. Mod. Phys._ **76** , 323–410. (doi:10.1103/RevModPhys.76.323) 

112. Bhatti S, Sbiaa R, Hirohata A, Ohno H, Fukami S, Piramanayagam SN. 2017 Spintronics based random access memory: a review. _Mater. Today_ **20** , 530–548. (doi:10.1016/j.mattod.2017.07.007) 

113. Hellman F _et al._ 2017 Interface-induced phenomena in magnetism. _Rev. Mod. Phys._ **89** , 025006. (doi:10.1103/RevModPhys.89.025006) 

114. Streubel R, Fischer P, Kronast F, Kravchuk VP, Sheka DD, Gaididei Y, Schmidt OG, Makarov D. 2016 Magnetism in curved geometries. _J. Phys. D: Appl. Phys._ **49** , 363001. (doi:10.1088/0022-3727/49/36/363001) 

115. Fernández-Pacheco A, Streubel R, Fruchart O, Hertel R, Fischer P, Cowburn RP. 2017 Threedimensional nanomagnetism. _Nat. Commun._ **8** , 15756. (doi:10.1038/ncomms15756) 

116. Moriya T. 1960 Anisotropic superexchange interaction and weak ferromagnetism. _Phys. Rev._ **120** , 91–98. (doi:10.1103/PhysRev.120.91) 

117. Gaididei Y, Kravchuk VP, Sheka DD. 2014 Curvature effects in thin magnetic shells. _Phys. Rev. Lett._ **112** , 257203. (doi:10.1103/PhysRevLett.112.257203) 

118. Di Fratta G, Slastikov V, Zarnescu A. 2019 On a sharp poincaré-type inequality on the 2-sphere and its application in micromagnetics. _SIAM J. Math. Anal._ **51** , 3373–3387. (doi:10.1137/19M1238757) 

119. Lum GZ, Ye Z, Dong X, Marvi H, Erin O, Hu W, Sitti M. 2016 Shape-programmable magnetic `Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf` soft matter. _Proc. Natl Acad. Sci. USA_ **113** , E6007. (doi:10.1073/pnas.1608193113) `by Peking University Library user on 22 May 2026` 

**~~16~~** 

120. Makarov D, Melzer M, Karnaushenko D, Schmidt OG. 2016 Shapeable magnetoelectronics. _Appl. Phys. Rev._ **3** , 011101. (doi:10.1063/1.4938497) 

121. Kaiser A, Snezhko A, Aranson IS. 2017 Flocking ferromagnetic colloids. _Sci. Adv._ **3** , e1601469. (doi:10.1126/sciadv.1601469) 

122. Xie H, Sun M, Fan X, Lin Z, Chen W, Wang L, Dong L, He Q. 2019 Reconfigurable magnetic microrobot swarm: multimode transformation, locomotion, and manipulation. _Sci. Rob._ **4** , eaav8006. (doi:10.1126/scirobotics.aav8006) 

123. Issa B, Obaidat IM, Albiss BA, Haik Y. 2013 Magnetic nanoparticles: surface effects and properties related to biomedicine applications. _Int. J. Mol. Sci._ **14** , 21 266–21 305. (doi:10.3390/ijms141121266) 

124. Gaididei Y, Yershov KV, Sheka DD, Kravchuk VP, Saxena A. 2019 Magnetizationinduced shape transformations in flexible ferromagnetic rings. _Phys. Rev. B_ **99** , 014404. (doi:10.1103/PhysRevB.99.014404) 

125. Brisbois CA, Tasinkevych M, Vázquez-Montejo P, Olvera de la Cruz M. 2019 Actuation of magnetoelastic membranes in precessing magnetic fields. _Proc. Natl Acad. Sci. USA_ **116** , 2500. (doi:10.1073/pnas.1816731116) 

126. Gong C _et al._ 2017 Discovery of intrinsic ferromagnetism in two-dimensional van der Waals crystals. _Nature_ **546** , 265–269. (doi:10.1038/nature22060) 

127. Novoselov KS, Mishchenko A, Carvalho A, Castro Neto AH. 2016 2d materials and van der Waals heterostructures. _Science_ **353** , aac9439. (doi:10.1126/science.aac9439) 

128. Gibertini M, Koperski M, Morpurgo AF, Novoselov KS. 2019 Magnetic 2d materials and heterostructures. _Nat. Nanotechnol._ **14** , 408–419. (doi:10.1038/s41565-019-0438-6) 

129. Mühlbauer S, Binz B, Jonietz F, Pfleiderer C, Rosch A, Neubauer A, Georgii R, Böni P. 2009 Skyrmion lattice in a chiral magnet. _Science_ **323** , 915. (doi:10.1126/science.1166767) 

130. Back C _et al._ 2020 The 2020 skyrmionics roadmap. _J. Phys. D: Appl. Phys._ **53** , 363001. (doi:10.1088/1361-6463/ab8418) 

131. Zhang X, Zhou Y, Song KM, Park TE, Xia J, Ezawa M, Liu X, Zhao W, Zhao G, Woo S. 2020 Skyrmion-electronics: writing, deleting, reading and processing magnetic skyrmions toward spintronic applications. _J. Phys.: Condens. Matter_ **32** , 143001. (doi:10.1088/1361-648X/ ab5488) 

132. Bogdanov AN, Yablonskii D. 1989 Thermodynamically stable ‘vortices’ in magnetically ordered crystals. the mixed state of magnets. _Zh. Eksp. Teor. Fiz_ **95** , 178. 

133. Melcher C. 2014 Chiral skyrmions in the plane. _Proc. R. Soc. A._ **470** , 20140394. (doi:10.1098/rspa.2014.0394) 

134. Bernand-Mantel A, Muratov CB, Simon TM. 2021 A quantitative description of skyrmions in ultrathin ferromagnetic films and rigidity of degree±1 harmonic maps from R<sup>2</sup> to S<sup>2</sup> . _Arch. Ration. Mech. Anal._ **239** , 219–299. (doi:10.1007/s00205-020-01575-7) 

135. Foster D, Kind C, Ackerman PJ, Tai JSB, Dennis MR, Smalyukh II. 2019 Twodimensional skyrmion bags in liquid crystals and ferromagnets. _Nat. Phys._ **15** , 655–659. (doi:10.1038/s41567-019-0476-x) 

136. Rybakov FN, Kiselev NS. 2019 Chiral magnetic skyrmions with arbitrary topological charge. _Phys. Rev. B_ **99** , 064437. (doi:10.1103/PhysRevB.99.064437) 

137. Yu XZ, Onose Y, Kanazawa N, Park JH, Han JH, Matsui Y, Nagaosa N, Tokura Y. 2010 Real-space observation of a two-dimensional skyrmion crystal. _Nature_ **465** , 901–904. (doi:10.1038/nature09124) 

138. Zannoni C. 2018 From idealised to predictive models of liquid crystals. _Liq. Cryst._ **45** , 1–14. (doi:10.1080/02678292.2018.1512170) 

139. Tiberio G, Muccioli L, Berardi R, Zannoni C. 2009 Towards _in silico_ liquid crystals. Realistic transition temperatures and physical properties for _n_ -cyanobiphenyls via Molecular Dynamics simulations. _ChemPhysChem_ **10** , 125–136. (doi:10.1002/cphc.2008 00231) 

140. Berardi R, Muccioli L, Zannoni C. 2004 Can nematic transitions be predicted by atomistic simulations? A computational study of the odd-even effect. _ChemPhysChem_ **5** , 104–111. (doi:10.1002/cphc.200300908) 

141. Shi J, Sidky H, Whitmer JK. 2020 Automated determination of _n_ -cyanobiphenyl and _n_ - cyanobiphenyl binary mixtures elastic constants in the nematic phase from molecular simulation. _Mol. Syst. Des. Eng._ **5** , 1131–1136. (doi:10.1039/C9ME00065H) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~17~~** 

142. Roscioni OM, Muccioli L, Della Valle RG, Pizzirusso A, Ricci M, Zannoni C. 2013 Predicting the anchoring of liquid crystals at a solid surface: 5-cyanobiphenyl on cristobalite and glassy silica surfaces of increasing roughness. _Langmuir_ **29** , 8950–8958. (doi:10.1021/la400857s) 

143. Roscioni OM, Muccioli L, Zannoni C. 2017 Predicting the conditions for homeotropic anchoring of liquid crystals at a soft surface. 4-n-pentyl-4–cyanobiphenyl on alkylsilane self-assembled monolayers. _ACS Appl. Mater. Interfaces_ **9** , 11 993–12 002. (doi:10.1021/ acsami.6b16438) 

144. Palermo MF, Bazzanini F, Muccioli L, Zannoni C. 2017 Is the alignment of nematics on a polymer slab always along the rubbing direction? A molecular dynamics study. _Liq. Cryst._ **44** , 1764–1774. 

145. Olivier Y, Muccioli L, Zannoni C. 2014 Quinquephenyl: the simplest rigid-rod-like nematic liquid crystal, or is it? An atomistic simulation. _ChemPhysChem_ **15** , 1345–1355. (doi:10.1002/cphc.201301126) 

146. Giri G _et al._ 2011 Tuning charge transport in solution-sheared organic semiconductors using lattice strain. _Nature_ **480** , U504–U124. (doi:10.1038/nature10683) 

147. Noriega R, Salleo A, Spakowitz AJ. 2013 Chain conformations dictate multiscale charge transport phenomena in disordered semiconducting polymers. _Proc. Natl Acad. Sci. USA_ **110** , 16 315–16 320. (doi:10.1073/pnas.1307158110) 

148. Sassella A, Campione M, Papagni A, Goletti C, Bussetti G, Chiaradia P, Marcon V, Raos G. 2006 Strategies for two-dimensional growth of organic molecular films. _Chem. Phys._ **325** , 193–206. (doi:10.1016/j.chemphys.2005.12.008) 

149. Muccioli L, D’Avino G, Zannoni C. 2011 Simulation of vapor-phase deposition and growth of a pentacene thin film on c-60 (001). _Adv. Mater._ **23** , 4532–4536. (doi:10.1002/adma.2011 01652) 

150. Krebs FC. 2009 Fabrication and processing of polymer solar cells: a review of printing and coating techniques. _Sol. Energy Mater. Sol. Cells_ **93** , 394–412. (doi:10.1016/j. solmat.2008.10.004) 

151. Rossander LH, Dam HF, Carlé JE, Helgesen M, Rajkovic I, Corazza M, Krebs FC, Andreasen JW. 2017 In-line, roll-to-roll morphology analysis of organic solar cell active layers. _Energy Environ. Sci._ **10** , 2411–2419. (doi:10.1039/C7EE01900A) 

152. Marchetti MC, Joanny JF, Ramaswamy S, Liverpool TB, Prost J, Rao M, Simha RA. 2013 Hydrodynamics of soft active matter. _Rev. Mod. Phys._ **85** , 1143–1189. (doi:10.1103/RevModPhys.85.1143) 

153. Majumdar A, Marchetti MC, Virga EG. 2014 Perspectives in active liquid crystals. _Phil. Trans. R. Soc. A_ **372** , 20130373. (doi:10.1098/rsta.2013.0373) 

154. Yeomans JM. 2016 The hydrodynamics of active systems. In _Soft Matter Self-Assembly_ (eds CN Likos, F Sciortino, P Ziherl, E Zaccarelli), vol. 193 of _Proc. of the Int. School of Physics Enrico Fermi_ , pp. 383–416. IOS Press Ebooks. 

155. Palermo MF, Pizzirusso A, Muccioli L, Zannoni C. 2013 An atomistic description of the nematic and smectic phases of 4- _n_ -octyl-4’ cyanobiphenyl (8CB). _J. Chem. Phys._ **138** , 204901. (doi:10.1063/1.4804270) 

156. Chami F, Wilson MR, Oganesyan VS. 2012 Molecular dynamics and EPR spectroscopic studies of 8CB liquid crystal. _Soft Matter_ **8** , 6823–6833. (doi:10.1039/c2sm25429h) 

157. Yan F, Earl DJ. 2012 Atomistic simulations of liquid crystal mixtures of alkoxy substituted phenylpyrimidines 2PhP and PhP14. _J. Chem. Phys._ **136** , 124506. (doi:10.1063/1.36 92731) 

158. Mukherjee B, Delle Site L, Kremer K, Peter C. 2012 Derivation of coarse grained models for multiscale simulation of liquid crystalline phase transitions. _J. Phys. Chem. B_ **116** , 8474–8484. (doi:10.1021/jp212300d) 

159. Botu V. 2017 Machine learning force fields: construction, validation, and outlook. _J. Phys. Chem. C._ **121** , 511–522. (doi:10.1021/acs.jpcc.6b10908) 

160. Zhang LF, Lin DY, Wang H, Car R, Weinan E. 2019 Active learning of uniformly accurate interatomic potentials for materials simulation. _Phys. Rev. Mater._ **3** , 023804. (doi:10.1103/PhysRevMaterials.3.023804) 

161. Jackson NE, Webb MA, de Pablo JJ. 2019 Recent advances in machine learning towards multiscale soft materials design. _Curr. Opin. Chem. Eng._ **23** , 106–114. (doi:10.1016/ j.coche.2019.03.005) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```

**~~18~~** 

162. Bedolla E, Padierna LC, Castaneda-Priego R. 2021 Machine learning for condensed matter physics. _J. Phys. Cond. Matter_ **33** , 053001. (doi:10.1088/1361-648X/abb895) 

163. Allen MP, Tildesley DJ. 2017 _Computer Simulation of Liquids_ , 2nd edn. Oxford, UK: Oxford University Press. 

164. Zannoni C. 2016 The molecular dynamics method. an introduction. In _The WSPC Reference on Organic Electronics: Organic Semiconductors_ , vol. 1 (eds JL Bredas, SR Marder) pp. 53–92. World Scientific. 

165. Rahimi M, Ramezani-Dakhel H, Zhang R, Ramirez-Hernandez A, Abbott NL, de Pablo JJ. 2017 Segregation of liquid crystal mixtures in topological defects. _Nat. Commun._ **8** , 15064. (doi:10.1038/ncomms15064) 

166. Li FH, West J, Glushchenko A, Il Cheon C, Reznikov Y. 2006 Ferroelectric nanoparticle/liquid crystal colloids for display applications. _J. Soc. Inform. Display_ **14** , 523–527. (doi:10.1889/1.2210802) 

167. Ball JM. 2017 Liquid crystals and their defects. In _Mathematical Thermodynamics of Complex Fluids_ (eds E Feireisl, E Rocca), Lecture Notes in Mathematics, pp. 1–46. Cham: Springer. 

168. Skaˇcej G, Zannoni C. 2021 The nematic-isotropic transition of the Lebwohl–Lasher model revisited. _Phil. Trans. R. Soc. A_ **379** , 20200117. (doi:10.1098/rsta.2020.0117) 

169. Smalyukh II. 2018 Liquid crystal colloids. _Annu. Rev. Condens. Matter Phys._ **9** , 207–226. (doi:10.1146/annurev-conmatphys-033117-054102) 

170. Wang Y, Zhang P, Chen JZ. 2017 Topological defects in an unconfined nematic fluid induced by single and double spherical colloidal particles. _Phys. Rev. E_ **96** , 042702. (doi:10.1103/PhysRevE.96.042702) 

171. Alama S, Bronsard L, Lamy X. 2016 Minimizers of the Landau–de Gennes energy around a spherical colloid particle. _Arch. Ration. Mech. Anal._ **222** , 427–450. (doi:10.1007/ s00205-016-1005-z) 

172. Alama S, Bronsard L, Lamy X. 2018 Spherical particle in nematic liquid crystal under an external field: the saturn ring regime. _J. Nonlinear Sci._ **28** , 1443–1465. (doi:10.1007/ s00332-018-9456-z) 

173. Bennett TP, D’Alessandro G, Daly KR. 2014 Multiscale models of colloidal dispersion of particles in nematic liquid crystals. _Phys. Rev. E_ **90** , 062505. (doi:10.1103/ PhysRevE.90.062505) 

174. Berlyand L, Cioranescu D, Golovaty D. 2005 Homogenization of a Ginzburg–Landau model for a nematic liquid crystal with inclusions. _J. de mathématiques pures et appliquées_ **84** , 97–136. 

175. Calderer MC, DeSimone A, Golovaty D, Panchenko A. 2014 An effective model for nematic liquid crystal composites with ferromagnetic inclusions. _SIAM J. Appl. Math._ **74** , 237–262. (doi:10.1137/130910348) 

176. Canevari G, Zarnescu A. 2020 Design of effective bulk potentials for nematic liquid crystals via colloidal homogenisation. _Math. Models and Methods Appl. Sci._ **30** , 309–342. (doi:10.1142/S0218202520500086) 

177. Muševiˇc I. 2017 _Liquid crystal colloids_ . New York, NY: Springer. 

178. Eskandari Z, Silvestre N, Ejtehadi M. 2014 Particle selection through topographic templates in nematic colloids. _Soft Matter_ **10** , 9681–9687. (doi:10.1039/C4SM02231A) 

179. Li X _et al._ 2017 Directed self assembly of colloidal particles onto nematic liquid crystalline defects engineered by chemically patterned surfaces. _ACS Nano_ **11** , 6492–6501. (doi:10.1021/acsnano.7b03641) 

180. Varghese B, Cheong FC, Sindhu S, Yu T, Lim CT, Valiyaveettil S, Sow CH. 2006 Size selective assembly of colloidal particles on a template by directed self assembly technique. _Langmuir_ **22** , 8248–8252. (doi:10.1021/la060732q) 

181. Brezis H, Coron JM, Lieb EH. 1986 Harmonic maps with defects. _Commun. Math. Phys._ **107** , 649–705. (doi:10.1007/BF01205490) 

```
Downloaded from http://royalsocietypublishing.org/rsta/article-pdf/doi/10.1098/rsta.2020.0108/373338/rsta.2020.0108.pdf
by Peking University Library user
on 22 May 2026
```



