---
title: "10.1098/rsta.2020.0108"
doi: "10.1098/rsta.2020.0108"
source: "royalsocietypublishing_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: false
token_estimate: 10284
---

# 10.1098/rsta.2020.0108

## Topics in the mathematical design of materials

royalsocietypublishing.org/journal/rsta

## Introduction

**Cite this article:** Chen X, Fonseca I, Ravnik M, Slastikov V, Zannoni C, Zarnescu A. 2021 Topics in the mathematical design of materials. _Phil. Trans.R.Soc.A_ **379**: 20200108. https://doi.org/10.1098/rsta.2020.0108

Accepted: 29 March 2021

One contribution of 10 to a theme issue ‘Topics in mathematical design of complex materials’.

###### **Subject Areas:**

materials science, applied mathematics, mechanical engineering, computer modelling and simulation

###### **Keywords:**

materials design, soft matter, alloys, epitaxy, liquid crystals, colloids, magnetic materials

**Author for correspondence:**

Arghir Zarnescu e-mail: azarnescu@bcamath.org

Xian Chen<sup>1</sup>, Irene Fonseca<sup>2</sup>, Miha Ravnik<sup>3,4</sup>,Valeriy Slastikov<sup>5</sup>, Claudio Zannoni<sup>6</sup> and Arghir Zarnescu<sup>7,8,9</sup>

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

demanding in terms of resources, it provides a test bench for microscopic and phenomenological theories of liquid crystals (like mean field and density functional theories) and in particular for the validity of assumptions like molecular uniaxiality and rigidity [145]. More importantly, atomistic simulations open exciting and to some extent unforeseen possibilities for the practical molecular design of novel mesogens with the prediction of their properties, also in advance of their chemical synthesis.

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
