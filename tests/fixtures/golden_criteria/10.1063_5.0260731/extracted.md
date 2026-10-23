---
title: "A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density"
authors: "Tao, Zhen, Qiu, Tian, Bian, Xuezhi, Duston, Titouan, Bradbury, Nadine, Subotnik, Joseph E."
journal: "The Journal of Chemical Physics"
doi: "10.1063/5.0260731"
published: "2025/04/14"
source: "aip_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: false
token_estimate: 17547
---

# A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density

RESEARCH ARTICLE | APRIL 14 2025 



## **A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density** 

**Special Collection: Festschrift for Abraham Nitzan** 



Zhen Tao  ; Tian Qiu ; Xuezhi Bian ; Titouan Duston ; Nadine Bradbury ; Joseph E. Subotnik 



_J. Chem. Phys._ 162, 144111 (2025) https://doi.org/10.1063/5.0260731 

 View Export Online<sup></sup> Citation 

##### **Connected Content** 

A correction has been published: Erratum: “A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density” [J. Chem. Phys. 162, 144111 (2025)] 

#### **Articles You May Be Interested In** 

Practical phase-space electronic Hamiltonians for _ab initio_ dynamics 

_J. Chem. Phys._ (March 2024) 

Erratum: “A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density” [J. Chem. Phys. 162, 144111 (2025)] 

_J. Chem. Phys._ (September 2025) 

An electronic phase-space Hamiltonian approach for electronic current density and vibrational circular dichroism 

_J. Chem. Phys._ (November 2024) 



**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

# A basis-free phase space electronic Hamiltonian that recovers beyond Born–Oppenheimer electronic momentum and current density 

Cite as: J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Submitted: 26 January 2025 • Accepted: 21 March 2025 • Published Online: 14 April 2025 

Zhen Tao,<sup>a)</sup> Tian Qiu,<sup>b)</sup> Xuezhi Bian, Titouan Duston, Nadine Bradbury, and Joseph E. Subotnik<sup>c)</sup> 









##### AFFILIATIONS 

Department of Chemistry, Princeton University, Princeton, New Jersey 08544, USA 

Note: This paper is part of the JCP Special Topic, Festschrift for Abraham Nitzan. **a)** Author to whom correspondence should be addressed: zhen.tao@princeton.edu **b)** tq4143@princeton.edu **c)** js8441@princeton.edu 

##### ABSTRACT 

We present a phase-space electronic Hamiltonian _H_<sup>ˆ</sup> _PS_ (parameterized by both nuclear position **_X_** and momentum **_P_** ) that boosts each electron into the moving frame of the nuclei that are closest in real space. The final form for the phase space Hamiltonian does not assume the existence of an atomic orbital basis, and relative to standard Born–Oppenheimer theory, the newly proposed one-electron operators can be expressed directly as functions of electronic and nuclear positions and momentum. We show that ( _i_ ) quantum–classical dynamics along such a Hamiltonian maintains momentum conservation and that ( _ii_ ) diagonalizing such a Hamiltonian can recover the electronic momentum and electronic current density reasonably well. In conjunction with other reports in the literature that such a phasespace approach can also recover vibrational circular dichroism spectra, we submit that the present phase-space approach offers a testable and powerful approach to post-BO electronic structure theory. Moreover, the approach is inexpensive and can be immediately applied to simulations of chiral induced spin selectivity experiments (where the transfer of angular momentum between nuclei and electrons is considered critical). 

_Published under an exclusive license by AIP Publishing._ https://doi.org/10.1063/5.0260731 

##### I. INTRODUCTION 

Linear and angular momentum transfer between nuclear and electronic degrees of freedom underlies a wide range of nonadiabatic or non-Born–Oppenheimer (BO) phenomena, including paramagnetic spin lattice relaxation, vibrational circular dichroism (VCD), and perhaps chiral-induced spin-selectivity (CISS).<sup>1–3</sup> Indeed, in the context of recent CISS experiments by the Wasielewski group<sup>4</sup> in solution (i.e., not near a metal), it has become clear that there must be a non-trivial exchange of angular momentum between electronic spins and nuclear motion in some photoexcited processes. As such, there is at present an enormous push to develop nonadiabatic methods that can accurately incorporate such non-Born–Oppenheimer momentum transfer between electrons and nuclei.<sup>5</sup> 

Now, when studying momentum transfer between electrons and nuclei, especially with a focus on spin processes where angular momentum comes in small chunks of _~~h~~_ , one cannot emphasize enough that proper simulation methods must conserve the total momentum. Ironically, however, most modern dynamical techniques in chemistry fail to enforce such conservation. In particular, for standard mean-field (Ehrenfest) dynamics over a few electronic states, one breaks momentum conservation by using a truncated set of Born–Oppenheimer energy surfaces.<sup>6,7</sup> More generally, even for dynamics on a single surface, the true total momentum is usually not conserved.<sup>8</sup> The problem at bottom is that, within the BO approximation, electrons are treated at a very different level of theory from nuclei; electronic states are solved for fixed nuclei and then nuclei are allowed to move, an asymmetry that leads to problems. Most poignantly, for a system composed of nuclei and an even 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-1 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

number of electrons, no matter what flavor of Born–Oppenheimer dynamics one applies, the _electronic_ momentum will always have an expectation value of zero.<sup>9–12</sup> 

##### A. Quantum dynamics 

Let us now be more precise. To begin our analysis, suppose that one treats the nuclei in a purely quantum-mechanical fashion. For such simulations, one should recognize<sup>13</sup> that, within the Born–Oppenheimer representation, the total (nuclear plus electronic) momentum is actually represented by the nuclear momentum. This interpretation follows by noticing that if one constructs adiabatic electronic wavefunction Φ( **_x_** ; **_X_** ) relative to nuclear positions ( **_X_** ), so that 



then the matrix elements of the total momentum operator for the total wavefunction Φ( **_x_** ; **_X_** ) _χ_ ( **_X_** , _t_ ) are trivial, 



Equation (2)<sup>13</sup> follows from the definitions of the electronic and nuclear momentum operators, **_p_** ˆ = − _i_ ̵ _h ∂_<sup>_<u>∂</u>_</sup> **_x_**<sup>and</sup><sup>**_P_**ˆ = −</sup><sup>_i_̵</sup><sup>_h_</sup> _∂_<sup>_<u>∂</u>_</sup> **_X_**<sup>. The total</sup> angular momentum can be represented in a similar fashion. Moreover, because the BO potential energy surface is translationally and rotationally invariant to the position of the nuclei, it follows that the quantum mechanical nuclear momentum is conserved. In this vein, one can argue that, according to the mapping above, BO dynamics conserve the total momentum. 

At this point, there are two important nuances that must be mentioned. First, in principle, one can run two different flavors of quantum mechanical BO simulations. Namely, (i) one can ignore the gauge potential that arises from the electronic state, 



or (ii) one can include the gauge potential (i.e., the derivative coupling), 





Here, _V el_ ( **_X_** ) is the electronic energy. Both Eqs. (3) and (4) conserve the total nuclear momentum, but only with Eq. (4)—where the gauge potential represents the momentum of the electrons—can one interpret the conservation of the nuclear momentum to really represent the conservation of the total momentum. 

Second, and even more importantly, one must note that, even with Eq. (4), the notion that BO dynamics conserve the _total_ momentum of a system of nuclei and electrons is somewhat limiting. For example, note that for the case of a system composed of nuclei and an even number of electrons, the gauge potential is exactly zero (and there is no electronic momentum as stated above). Thus, although the “total” momentum is conserved, the BO approximation sometimes conserves momentum by setting the electronic momentum to zero—which is not very satisfying. 

##### B. Mixed quantum-classical dynamics 

Consider next the case where the nuclei are treated classically. For classical BO dynamics, it is standard to run simple Newtonian dynamics where one ignores any trace of the gauge potential, 



As a result, just as for quantum dynamics, such BO simulations conserve the nuclear momentum rather than the total nuclear plus electronic momentum.<sup>8</sup> Moreover, just as for quantum dynamics, one can partially rectify this lack of total momentum conservation by including the effect of the gauge potential. Within semiclassical theory, the relevant term that must be included<sup>14</sup> is the Berry pseudomagnetic force,<sup>8</sup> which depends on both nuclear velocity and Berry curvature (curl of the derivative coupling), 



Indeed, over the past several years, several research groups in the chemical<sup>15,16</sup> and physical communities<sup>17</sup> have explored _ab initio_ BO dynamics that include Berry forces, in or out of magnetic fields, both in gas and solid phases. Unfortunately, however, running such _ab initio_ dynamics has several limitations. ( _i_ ) First, in agreement with the quantum case, the Berry force is always exactly zero for a (nondegenerate) system with an even number of electrons; for a nonzero Berry force, one requires either the presence of an external magnetic field or a system with an odd number of electrons and spin–orbit coupling—although in the latter case, because of Kramers degeneracy, fixing an adiabatic state to walk along is difficult and not quite well-defined.<sup>7</sup> ( _ii_ ) Second, the cost of evaluating a Berry force can be quite large. ( _iii_ ) Third, there is no feedback from the nuclear dynamics on the single-state electronic dynamics, so that all electronic observables remain uncorrected. ( _iv_ ) Fourth, there is no way to apply a Berry force in a nonadiabatic context,<sup>18</sup> and thus, these simulations cannot be used to study momentum transfer during passage through curve crossings (which would represent a meaningful extension of Landau–Zener theory<sup>19</sup> ). 

Regarding the final criticism above, one can go beyond BO dynamics and, in principle, run Ehrenfest dynamics with a nonabelian force (as suggested by Takatsuka<sup>20,21</sup> and Krishna<sup>22</sup> ) so as to recover momentum conservation.<sup>7</sup> However, the cost of evaluating the non-abelian Berry curvature is enormous, and the introduction of mean-field dynamics introduces other approximations one would like to avoid (e.g., a lack of branching and the incorrect equilibrium distribution<sup>23,24</sup> ). Furthermore, the third criticism noted above for running BO dynamics with a Berry force (i.e., the lack of electronic feedback) remains a problem. 

##### C. Outlook 

For all the reasons above, developing inexpensive fully momentum-conserving nonadiabatic equations of motion for nuclei and electrons is a priority for chemical and condensed matter physics; for the most efficient approach, of course, mixed quantum–classical dynamics are ideal. Before concluding this introduction, we note that, so far, we have limited our discussion on mixed quantum–classical above to those techniques 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-2 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

that represent the quantum nuclear wavepacket with an ensemble of independent trajectories. It is worth noting that exact factorization techniques<sup>25–28</sup> offer a very different flavor of mixed quantum–classical dynamics, one where angular momentum is conserved.<sup>5</sup> That being said, despite advances in developing coupled trajectory approaches,<sup>29–31</sup> it will always be true that techniques utilizing independent trajectories will always allow one to study much larger systems than is possible with techniques utilizing ensembles of interacting trajectories. Thus, in this article, we focus on momentum-conservation within independent trajectories with an eye on large-scale future simulations. 

##### II. PHASE SPACE ELECTRONIC STRUCTURE METHODS 

In this vein, a very enticing alternative, inexpensive strategy to BO theory, is to run dynamics along what we will call phase-space adiabats. The notion of developing self-consistent approaches to electronic transitions through eikonal transformations goes back many decades,<sup>32,33</sup> and similar approaches with time-dependent Hamiltonians were derived by Berry in the 1980s (labeled superadiabats<sup>34,35</sup> ), but for our purposes, the cleanest notion of a phase space electronic Hamiltonian for quantum–classical dynamics was written down 15 years ago by Shenvi.<sup>36</sup> The basis idea of a phase-space electronic Hamiltonian is to diagonalize the electronic Hamiltonian that depends parametrically on both nuclear position ( **_X_** ) and momentum ( **_P_** ). Guided by the form of the Schrodinger equation in the usual BO basis (and the previous work or others<sup>32–35</sup> ), Shenvi diagonalized a phase-space Hamiltonian of the form 



A brief interlude about the notations is given as follows: Here, _A_ , _B_ , _. . ._ denote the index of atoms, **_P_** _A_ denotes the nuclear momentum of atom _A_ , and, more generally, all quantities that are **bold** represent vectors (or matrix when stated explicitly) in R<sup>3</sup> Euclidean space. **_X_** is shorthand for { **_X_** } = ( **_X_** _A_ , **_X_** _B_ , _. . ._ ), representing the collection of all nuclear positions, and **_P_** is shorthand for { **_P_** } = ( **_P_** _A_ , **_P_** _B_ , _. . ._ ), representing the collection of all nuclear momenta. _I_ , _J_ , _K_ index electronic states. **_d_**<sup>_A_</sup> _JK_<sup>= ⟨Φ</sup><sup>_J_∣</sup> _∂∂_ **_X_** _A_<sup>∣Φ</sup><sup>_K_⟩isthe</sup> derivative coupling vector between the eigenstates ∣Φ _J_ ⟩ and ∣Φ _K_ ⟩ of the conventional electronic Hamiltonian, where _H_<sup>ˆ</sup> _el_ ∣Φ _K_ ⟩= _EK_ ∣Φ _K_ ⟩. Although they do not appear in Eq. (8), **_x_** ˆ, **_p_** ˆ,<sup>ˆ</sup> **_l_** , and ˆ **_s_** will denote the electronic position, linear momentum, orbital angular momentum, and spin operators, respectively. All quantities with a hat are electronic operators. 

Trajectories propagated along the eigensurfaces from diagonalizing the Shenvi Hamiltonian in Eq. (8) do conserve total momentum.<sup>37</sup> Unfortunately, however, these dynamics also suffer from several problems. First, the derivative coupling vector is known to diverge near avoided crossings, leading to numerical instability during dynamics using the phase-space Hamiltonian in Eq. (8). Second, such derivative couplings are not even well-defined in the case of degenerate states. Third, building the phase-space Hamiltonian in Eq. (8) involves computing _N_ ( _N_ + 1)/2 derivative coupling vectors, 

each of which can be computationally expensive, and for dynamics, one would require the _derivatives_ of these vectors—which would be even more expensive. Motivated by these problems, in Ref. 38, we demonstrated that in an atomic orbital (AO) basis, one can construct many other phase-space Hamiltonians [where we approximate the derivative couplings **_d_**<sup>_A_</sup> _IJ_<sup>in Eq. (8) by a to-be determined</sup> operator **Γ**<sup>ˆ</sup><sup>_A_</sup> ] that can satisfy momentum conservation, provided the Hamiltonian is solved in an AO basis. In this article, we will now show that momentum conservation requires no such AO basis, and we will demonstrate that a meaningful Hamiltonian can indeed be constructed by boosting each electron into a frame of the local nucleus. 

If _H_<sup>ˆ</sup> _el_ is the usual electronic Hamiltonian, consider a phasespace electronic Hamiltonian of the form 



with eigenvalues and eigenvectors 



To simplify our notation, we drop the dependence of the phase space wavefunction on nuclear position and momentum from now on. The equations of motion for the corresponding Hamiltonian mechanics are 



Obviously, such Hamilton’s equations conserve energy. In what follows, we will prove that the dynamics in Eq. (11) conserve linear and angular momentum, provided that the **Γ**<sup>ˆ</sup> _A_ operator satisfies four constraints, 









where “×” represents the cross product between two vectors in R<sup>3</sup> . Note that Eqs. (12)–(15) are satisfied exactly by the derivative couplings [if we substitute **_d_** for **Γ** as in Eq. (8)].<sup>13</sup> In other words, here, we are approximating the derivative couplings by a **Γ**<sup>ˆ</sup> operator (which is to be determined). Intuitively, Eqs. (12) and (14) insist that the electronic eigenfunctions of _H_<sup>ˆ</sup> PS will be expressed in coordinates relative to the nuclei: when the nuclei translate, the electrons gain momentum [Eq. (12)]; when the nuclei rotate, the electrons gain angular momentum [Eq. (14)]. Equations (13) and (15) dictate that the form of the **Γ**<sup>ˆ</sup> _A_ operators is unchanged if we displace or reorient the molecule. 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-3 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

##### A. Translational and rotational invariance of the phase space energy 

Let us now demonstrate that, with Eqs. (13) and (15) satisfied, the phase space eigenenergy is translationally and rotationally invariant. 

If one plugs Eqs. (12), (14), and (26) into Eqs. (24) and (25), the result is **_P_**<sup>tot</sup> = ∑ _A_ **_P_** _A_ and **_L_**<sup>tot</sup> = ∑ _A_ **_L_** _A_ . Finally, momentum conservation follows from Eq. (11) by noting that the phase-space energy _E_ PS( **_X_** , **_P_** ) is invariant to translation and rotation, as proven in Sec. II A. 

To prove translational and rotational invariance, we need to 

show 





By the Hellmann–Feynman theorem, 



Using Eqs. (13) and (15), we have the commutation relations 



Equations (18) and (19) then become 





##### B. Momentum conservation 

To prove momentum conservation, we evaluate the total linear and angular momentum (which is the sum of the nuclear and electronic components), 





Now, using Eqs. (9) and (11), it follows that the nuclear kinetic momentum is 



##### III. FORM OF **Γ** IN EQ. (9) 

At this stage, the only remaining questions are ( _i_ ) how to properly choose the **Γ**<sup>ˆ</sup> _A_ operators in Eq. (9) and ( _ii_ ) how to judge the merit of that choice. We will address question ( _i_ ) shortly, but as for question ( _ii_ ), we are aware of two means for evaluating the accuracy of a phase-space Hamiltonian and its advantages over a BO electronic Hamiltonian. First, as is well known,<sup>11,39</sup> one can show that if one properly includes non-Born–Oppenheimer effects to first order, an electronic eigenstate (∣Φ⟩) with zero momentum (⟨Φ∣ **_p_** ˆ∣Φ⟩= **0** ) is perturbed into an electronic eigenstate (∣Ψ<sup>˜</sup> ⟩) with non-zero momentum, equal to ⟨Ψ<sup>˜</sup> ∣ **_p_** ˆ∣Ψ<sup>˜</sup> ⟩= _md_ / _dt_ ⟨Φ∣ **_x_** ˆ∣Φ⟩. See more discussion below in Sec. IV B. Second, a strong phase-space electronic approach should yield a good estimate for the electronic current density, which is essential for recovering the missing velocity-form of the electronic dipole moment and the magnetic dipole moment within BO theory.<sup>11,40</sup> These quantities contribute directly to the electronic component of the rotational strength that is observed in vibrational circular dichroism.<sup>12,41</sup> These two constraints will allow us to verify the validity of any phase space Hamiltonian. In the present article, we will investigate how well one recovers electronic momentum and electronic current density according to the continuity equation; in a separate paper, we have already demonstrated that accurate VCD signals can indeed be recovered with this phase space approach.<sup>42,43</sup> 

The simplest physical model for the **Γ** -couplings in Eq. (9) arises from the realization that in an AO basis, whenever a nucleus moves, that nuclear motion drags along an electronic orbital that leads to a trivial derivative coupling. As an example, consider a hydrogen atom moving in free space in the _x_ -direction with an electron occupying a hydrogenic 3 _px_ orbital that translates with the nucleus. If one evaluates the derivative coupling between the hydrogenic 3 _px_ and 1 _s_ orbitals, one finds a nonzero value—even though such a value is clearly eliminated by moving to a center of mass frame. This trivial component of the derivative coupling was recognized long ago and is often labeled a “Bates factor”<sup>44</sup> or “electron translation factor” (ETF).<sup>45–50</sup> Moreover, although translations are much easier to evaluate than rotations, the same physical mechanism also occurs whenever the nuclei of a given molecule rotate, and one can also identify “electron rotation factors” (ERFs)<sup>51,52</sup> . 

Thus, a natural choice for the **Γ** -couplings is to set 



where the sum over _i_ represents a sum over electrons, **Γ**<sup>ˆ</sup> _A_<sup>′isan</sup> ETF operator, and **Γ**<sup>ˆ′′</sup> _A_<sup>is an ERF operator. Encouragingly, within the</sup> context of quantum chemistry calculations in an AO basis (where explicit forms for ETFs and ERFs are known), we have recently demonstrated that phase-space dynamics using Eq. (27) recovers the correct electronic momentum<sup>38</sup> as well as quite accurate VCD signals for three small chiral molecules.<sup>42</sup> Unfortunately, however, all previous phase-space calculations relied on an AO basis (in order 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-4 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

to construct **Γ**<sup>ˆ</sup> ) and, thus, could not probe solid state systems in a plane wave basis (which is very limiting). Furthermore, empirically one finds that using the **Γ**<sup>ˆ</sup> from Ref. 52, it is difficult to converge VCD results<sup>43</sup> and satisfy the electronic continuity equation (shown in Sec. IV) as a function of basis set size (which is both a theoretical and a practical limitation). 

##### A. Basis-free form of **Γ**<sup>ˆ</sup><sup>**′**</sup> from ETF operators 

To move beyond an AO basis, let us make the ansatz that we divide up all free space according to regions labeled by the closest nucleus (in the spirit of a Voronoi diagram<sup>53</sup> ), and electrons are boosted relative to the motion of the nucleus that labels their location. Mathematically, we imagine constructing a space-partitioning operator Θ _A_ ( ˆ **_x_** ) ( Θ<sup>ˆ</sup> _A_ as a shorthand) that satisfies the following: 

1. Θˆ _A_ ≡ Θ _A_ ( ˆ **_x_** ) is positive definite. 

2. ∑ _A_ Θ _A_ ( ˆ **_x_** ) = 1. 

3. Θ _A_ ( **_x_** ) ≫ Θ _B_ ( **_x_** ) for ∥ **_x_** − **_X_** _A_ ∥≪∥ **_x_** − **_X_** _B_ ∥. 

One example of this kind is to define Θ _A_ ( ˆ **_x_** ) as 



where _QA_ is the bare nuclear charge of atom _A_ and _σ_ is a parameter that determines the length scale over which we partition unity (and can be determined empirically). Alternatively, one can also imagine using the nuclear mass _MA_ as a prefactor, 



Note that for most systems, the nuclear mass _MA_ is usually proportional to the nuclear charge _QA_ , so that the differences between Eqs. (28) and (29) need not be enormous. Note also that any positive prefactor will preserve conditions 1–3 above, so one can also employ combinations of mass and charge, etc., in the choice of Θ _A_ ( ˆ **_x_** ). 

For linear momentum conservation, one must satisfy Eq. (12). We distribute this condition as follows (between ETFs and ERFs): 



Let us multiply the R.H.S. of Eq. (30) on the left (and then on the right) by ∑ _A_ Θ<sup>ˆ</sup> _A_ and then take the average. The result is 



which suggests the following expression for **Γ**<sup>ˆ</sup> _A_<sup>′:</sup> 



It can be shown easily that **Γ**<sup>ˆ</sup> _A_<sup>′defined by Eq. (33) is anti-Hermitian</sup> (note that both Θ<sup>ˆ</sup> _A_ and **_p_** ˆ are Hermitian), which is crucial for constructing a phase-space electronic Hamiltonian. 

##### B. Basis-free form of **Γ**<sup>ˆ</sup><sup>**′′**</sup> from ERF operators 

Given the definition of **Γ**<sup>ˆ</sup> _A_<sup>′in Eq. (33), Eq. (14) becomes</sup> 



If one defines 



Equation (34) can be written succinctly as 





both Eqs. (31) and (36) can be satisfied, given a proper choice of the unknown vector **_X_**<sup>0</sup> _B_<sup>and a to-be-determined 3 × 3 matrix</sup><sup>**_K_**</sup><sup>_B_. In</sup> Eq. (37), in order to ensure that **Γ**<sup>′′</sup> _A_ is localized around atom _A_ , we introduce a weighting factor _ζAB_ . Here, the function _ζAB_ = _ζ_ ( **_X_** _A_ , **_X_** _B_ ) is a function of ∣ **_X_** _A_ − **_X_** _B_ ∣ (although not necessarily a symmetric function of _A_ and _B_ ), and **_X_**<sup>0</sup> _B_<sup>isintuitivelyalocalcenterofmass</sup> around atom _B_ . In practice, for **Γ**<sup>ˆ′′</sup> _A_<sup>tooperatelocallyonelectrons</sup> near atom _A_ , we require _ζAB_ to vanish for large separations of **_X_** _A_ and **_X_** _B_ , and we set 



Equation (38) enforces locality through a parameter _βAB_ . The importance of the mass prefactor _MA_ can be understood as follows: if we ignore the exponential in Eq. (38) and set _ζAB_ = _MA_ , then **_X_** _B_<sup>0</sup> becomes the nuclear center of mass, and **_K_** _B_ is the total nuclear moment of inertia matrix relative to the center of mass; see the discussion below. 

Inserting Eq. (37) into Eq. (31), one can rewrite the necessary constraint as 



The simplest way to satisfy Eq. (39) [and therefore Eq. (31)] is to set 



which suggests that we define a local average position, 



J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-5 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

### **The Journal of Chemical Physics** 

Next, inserting Eq. (37) into Eq. (36), one finds that the constraint has the form 



The most natural way to satisfy the above equation is to set 



This ansatz suggests that we define the matrix **_K_** _B_ such that for any arbitrary vector **_v_** and in particular, **_v_** ≡ **_K_** _B_<sup>−1</sup><sup>**_J_**ˆ</sup><sup>_B_, one has</sup> 



where _I_ 3 is a 3 by 3 identity matrix. Note that we have invoked Eq. (40) in deriving Eq. (46). 

##### C. A demonstration that the **Γ**<sup>**′**</sup> and **Γ**<sup>**′′**</sup> operators transform correctly under translations and rotations 

Let us now demonstrate that the **Γ**<sup>ˆ</sup> _A_ operators defined in Eqs. (33) and (37) satisfy Eqs. (13) and (15). 

##### _1. Proof of Eq. (13)_ 

Equation (13) can be proven in many ways. For purposes below, the most natural approach is to notice that because the **Γ**<sup>ˆ</sup> operators in Eqs. (33) and (37) are defined in terms of the electronic positions relative to the nuclei, 







Given that _d_ **_s_** is arbitrary, this final equality implies Eq. (13). 

##### _2. Proof of Eq. (15)_ 

Equation (15) can be proved in an analogous fashion. Let _R_ ( _d_ **_θ_** ) be an infinitesimal rotation of _d_ **_θ_** , and let us begin by showing that the **Γ**<sup>ˆ</sup> operators in Eqs. (33) and (37) satisfy 



To prove Eq. (54), the first two things to note are that the dot product between two vectors is invariant under _R_ and that the cross product between two vectors rotates with the vectors, i.e., 





it follows that the matrix representing **Γ** must be the same in any electronic basis of states that moves with the nuclear coordinates (e.g., the adiabatic basis<sup>13,54</sup> ). Thus, if _d_ **_s_** denotes an infinitesimal translation of all atoms, the following identity holds 



in any basis that satisfies 



Equation (49) is the standard phase relationship chosen for adiabats in Born–Oppenheimer theory.<sup>13,54</sup> 

Now, Eq. (48) is trivial to zeroth order in _d_ **_s_** , so let us evaluate the left hand side (LHS) of Eq. (48) to first order in _d_ **_s_** (which must vanish), 



where **_v_** _i_ , **_v_** _j_ are any vectors. It follows that 





Next, let **_V_** ˆ _B_ = **_K_**<sup>−</sup> _B_<sup>1(</sup><sup>**_X_**)</sup><sup>**_J_**ˆ</sup><sup>_B_.Asimplederivationshowsthat[or</sup> alternatively see Eq. (43)] 







J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-6 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

### **The Journal of Chemical Physics** 

from which one finds 



Clearly, Eqs. (57) and (64) imply (54). 

Equation (54) dictates that the matrix elements of the **Γ**<sup>ˆ</sup> operators in Eqs. (33) and (37) are invariant to rotations in a basis that rotates with the system. Mathematically, Eq. (54) implies that 



in a basis that rotates with the molecule and has the standard phase convention, 





Again, this phase convention is the standard choice of phase for the adiabatic states within the Born–Oppenheimer approximation.<sup>13,54</sup> 

At this point, let us expand Eq. (65) in powers of _θ_ . Note that 



so that the Taylor series of the ket is 



Therefore, Eq. (65) is equivalent to 



Thus, Eqs. (33) and (37) satisfy Eq. (15). 

##### D. Parameterization 

At this point, working with the ansatz in Eqs. (28), (29), and (38), there are only two parameters of interest: _σ_ and _βAB_ . These two locality parameters determine the length scale over which the electrons are coupled to the nuclear translation and rotation. Given the huge parameter space possible, we test below the effect of different _σ_ parameters by calculating the electronic momentum ⟨ΨPS∣ **_p_** ˆ∣ΨPS⟩ for different nuclear vibrations. In principle, one would like to find that the electronic momentum matches _md_ / _dt_ ⟨Φ∣ **_x_** ˆ∣Φ⟩, an equality that otherwise would require a non-BO treatment and a sum-over-states expansion [as shown through Eqs. (97)–(101)].<sup>11</sup> As for the choice of the other parameter, _βAB_ , for now, we choose _βAB_ = 2 ~~√~~ 2 _σ_ in order to explore the effect of locality together with _σ_ . Exploring _βAB_ for larger systems will be essential in the future. 

##### IV. RESULTS 



Subtracting ⟨Φ _I_ ( **_X_** )∣ **Γ**<sup>ˆ</sup> _A_ ( **_X_** )∣Φ _J_ ( **_X_** )⟩ from both sides of Eq. (65), the L.H.S. gives (to the first order in _d_ **_θ_** ) ⟨Φ _I_ ( _R_ ( _d_ **_θ_** ) **_X_** )∣ **Γ**<sup>ˆ</sup> _A_ ( _R_ ( _d_ **_θ_** ) **_X_** )∣Φ _J_ ( _R_ ( _d_ **_θ_** ) **_X_** )⟩−⟨Φ _I_ ( **_X_** )∣ **Γ**<sup>ˆ</sup> _A_ ( **_X_** )∣Φ _J_ ( **_X_** )⟩ 







Rearranging the R.H.S of Eq. (65), one can express the result in explicit Cartesian indices, 



##### A. Electronic momentum 

The power of a phase-space approach [and the **Γ**<sup>ˆ</sup> operator defined in Eqs. (33) and (37)] is highlighted in Fig. 1, where we show that a sizable amount of the electronic momentum that is missing in the BO approximation can be recovered with the phase-space approach. Here, we calculate the electronic momentum ⟨ΨPS∣ **_p_** ˆ∣ΨPS⟩ with the phase-space Hamiltonian in Eq. (9), with nuclear momentum **_P_** corresponding to the three vibrational modes of water and the six vibrational modes of formaldehyde. We also calculate _md_ / _dt_ ⟨Φ∣ **_x_** ˆ∣Φ⟩ by finite difference and plot the ratio of the electronic momentum over the finite-difference calculations. For these calculations, we probe the effect of making each atomic radius smaller (1/ _σ_<sup>2</sup> → 18 bohr<sup>−2</sup> ) or larger (1/ _σ_<sup>2</sup> → 0 bohr<sup>−2</sup> ). As noted above, if one uses a complete set of states and diagonalizes Shenvi’s phase space Hamiltonian in Eq. (8), one recovers the exact relationship ⟨ **_p_** ˆ⟩= _md_ ⟨ **_x_** ˆ⟩/ _dt_ , which also corresponds to the horizontal dotted line ( _y_ = 1) in Fig. 1. The electronic momentum calculated with the phase space approach in Fig. 1 includes both the ETF ( **Γ**<sup>ˆ′</sup> ) and ERF ( **Γ**<sup>ˆ′′</sup> ) contributions. In practice, we find that the effect of the ERFs ( **Γ**<sup>ˆ′′</sup> ) is more important for bending modes than for the stretching modes. 

To generate the data in Fig. 1 in the main body of the paper, the geometries of the water and the formaldehyde molecules are optimized at a standard restricted Hartree–Fock (RHF) level with a ccpVTZ basis set. The vibrational modes in Fig. 1 are computed from the corresponding Hessian calculations. The benchmarks _md_ ⟨ **_x_** ˆ⟩/ _dt_ 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-7 

**The Journal of Chemical Physics** 

**pubs.aip.org/aip/jcp** 

##### **ARTICLE** 



**FIG. 1.** A plot of the ratio of the dominant Cartesian component of the electronic momentum ⟨ **_p_** ˆ⟩ with respect to the finite difference benchmark. The results with nuclear charges and masses as the weights in Eqs. (28) and (29) are shown in (a) and (b), respectively. The upper panels show plots for a full range of _σ_ values, while the bottom two panels zoom in on the large _σ_ range, i.e., the orange shaded zone in the upper panels. The results for water (H2O) and formaldehyde (CH2O) are shown in blue and red, respectively. In principle, if one were to use **Γ** = **_d_** as in Eq. (8) together with a complete electronic basis, one would find the standard Ehrenfest result (⟨ **_p_** ˆ⟩= _md_ ⟨ **_x_** ˆ⟩/ _dt_ ), which corresponds to the black dotted horizontal line at _y_ = 1. This graph highlights that a simple phase space approach can recover a strong estimate of the electronic momentum (with the correct sign) using only an approximate **Γ** . 

are computed from finite-difference standard RHF calculations, and the linear momentum ⟨ **_p_** ˆ⟩ is computed from phase space RHF calculations, implemented in a developmental version of the Q-Chem electronic structure package.<sup>55</sup> The **Γ** -couplings are evaluated on Lebedev grids. To ensure numerical accuracy, an unpruned (250, 974) grid is used to generate data in Fig. 1, so that constraints in Eqs. (12) and (14) are satisfied to at least less than 10<sup>−4</sup> a.u. for the matrix elements in the atomic orbital basis. In all cases, we assume that the nuclei are moving with momentum in directions corresponding to different vibrational modes and with magnitudes corresponding to the average momentum at temperature 100 K. The finite-difference benchmark calculations use a time step of 0.0242 fs. 

##### _1. Limit_ **_σ_ →∞** 

In Figs. 1(a) and 1(b), we show results using the nuclear charges [Eq. (28)] and nuclear masses [Eq. (29)] as weights, respectively. Note that, as 1/ _σ_<sup>2</sup> → 0, the electronic momentum vanishes when we use nuclear masses as the weights [as in Eq. (29)]. This feature follows by construction from Eqs. (28) and (38) because, in this limit, 1/ _βAB_<sup>2→0, and all the Θ</sup><sup>_A_terms become</sup><sup>_MA_/</sup><sup>_M_tot, where</sup> _M_ tot = ∑ _A MA_ . In such a case 



It then follows that (with **Γ**<sup>ˆ</sup> _A_ and **Γ**<sup>ˆ2</sup> _A_<sup>as second quantized operators)</sup> 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-8 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 





Here, **_X_** NCM is the nuclear center of mass, **_I_** NCM is the total nuclear moment of inertia matrix relative to the nuclear center of mass, and<sup>ˆ</sup> **_l_** NCM is the electronic angular momentum relative to the nuclear center of mass. Thus, in this limit, four terms appear: (i) the kinetic energy of the atoms relative to the center of nuclear mass, (ii) the total kinetic energy of the nuclear center of mass (recognizing that ∑ _A_ **_P_** _A_ now represents the total nuclear plus electronic momentum, from which one must subtract the electronic momentum),<sup>13</sup> (iii) a Coriolis potential from aligning the electronic frame of the electrons to the nuclei,<sup>56</sup> and (iv) a centrifugal potential that captures the inertia of electrons in a rotating frame.<sup>57</sup> 

Next, let us address the electronic momentum of normal modes in this same limit. Let ∣ΨPS( **_X_** , **_P_** )⟩ be the electronic wavefunction associated with an internal normal mode, such that ∑ _A_ **_P_** _A_ = ∑ _A_ **_X_** _A_ × **_P_** _A_ = 0. In this limit, the Hamiltonian becomes 



Note that, as an electronic operator, _H_<sup>ˆ</sup> _PS_ commutes with the timereversal operator. Therefore, provided that the ground state is electronically nondegenerate, it follows that 



Note that despite the physical appeal of Eq. (79), the vanishing of the electronic momentum in this limit _σ_ , _βAB_ →∞ makes clear that this limit is unphysical. As the simplest problematic example, consider the vibration of a hydrogen–deuterium molecule. If the center of mass is unchanged, then because of the mass difference between hydrogen and deuterium, each atom must move at a different speed. That being said, each atom has the same charge and is equally attracted to electrons, which means one electron must be moving faster than the other electron, and there must be a total nonzero electron momentum that can be captured only by viewing the internal motion of the system from each atom’s individual 

body frame; in other words, _σ_ must be finite. Note also that if we use charge instead of mass as a weight [Eq. (28) instead of Eq. (29)], we do recover a non-zero electronic momentum even at the limit of _σ_ →∞, as shown in Fig. 1(a); that being said, the robust and correct solution for large simulations is to set _σ_ to be finite. 

Before concluding, let us write down the form of the phase space electronic Hamiltonian in first quantization. If we index the electrons by _j_ , the phase space electronic Hamiltonian in this limit becomes 



This form makes clear that the product **Γ**<sup>ˆ2</sup> _A_<sup>operators in Eq. (9) are</sup> indeed one-electron operators (just like **Γ**<sup>ˆ</sup> _A_ ). 

##### _2. Limit_ **_σ_ → 0** 

Second, in the opposite limit (small _σ_ ), the values of the electronic momentum become relatively constant (and always have the correct sign), which is extremely encouraging. Note that if _σ_ gets too small, numerical convergence can become difficult unless one uses a tight grid. At present, we evaluate Θ on a Lebedev grid designed to sample density near that atomic nucleus for density functional theory (DFT) calculations, but there is no reason we could not build a new grid to best sample Θ _A_ . Thus, as long as the partitioning is not too flat and provided we have enough grid points to model the switching region, there is a large range of parameters whereby the electronic momentum is robust. 

Importantly, one should not be very disheartened insofar as the fact that we do not recover exactly ⟨ **_p_** ˆ⟩= _md_ / _dt_ ⟨Φ∣ **_x_** ˆ∣Φ⟩ in Fig. 1 because, as shown in Ref. 38, this result follows exactly (analytically) if we set **Γ** = **_d_** and sum over all excited states. Our goal in this article is to generate **Γ** by approximating the derivative coupling, which, by construction, will violate the above condition. In particular, one can divide the electronic momentum into two contributions, 





Here, _Dμν_ is the electronic density matrix elements in atomic orbital basis indexed by _μ_ , _ν_ , 



where _Cμi_ is the matrix of molecular orbital coefficients, and we sum over all occupied orbitals _i_ in Eq. (86). 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-9 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

According to Eq. (85), the electronic momentum arises from two terms: one term captures how the basis moves and the other term captures how the molecular orbitals change in a moving basis. For the approximate **Γ**<sup>ˆ</sup> ansatz in Eqs. (33) and (37) above, the aim is to capture only the first term in Eq. (85), the movement of the basis functions; this goal is to be achieved by partitioning real space (with **Θ**<sup>ˆ</sup> ) into regions centered around each nucleus. By contrast, one cannot expect our approximate **Γ**<sup>ˆ</sup> to capture the second term in Eq. (85), which represents the full, nonlocal electronic orbital response to nuclear motion. In particular, an electron transfer event that occurs when one moves through a curve crossing (which is the entire rationale for Marcus theory<sup>58</sup> ) represents an obvious case where nuclear motion leads to a quick change in orbitals and a massive redistribution of electronic density in a given adiabatic electronic state. Obviously, we cannot account for such nonlocal changes here, although we do find that some moderate fraction of the local orbital response can be captured partially by the approximate **Γ**<sup>ˆ</sup> operator. For the case of electron transfer, however, one must go beyond the singlet surface approximation made here and explicitly account for nonadiabatic transitions; the most straightforward approach is to run surface hopping within the current phase-space framework.<sup>37,59</sup> 

Nevertheless, despite the above nonadiabatic limitation, the most striking conclusion from Fig. 1 is that in the adiabatic limit (when adiabatic states are well separate energetically), our simple phase-space approach can capture so much of the electronic momentum. Moreover, in Sec. IV B, we show that our phase space electronic Hamiltonian can even recover the electronic current density (which is a resolution of the electronic momentum over three dimensional space). 

##### B. Electronic continuity equation 

Besides agreeing with VCD experiments<sup>43</sup> and capturing a nonvanishing electronic momentum, one of the essential validations of a phase space electronic Hamiltonian is the capacity to recover the missing continuity equation for the electronic motion. Before showing results, let us review how the continuity equations for the current density can be recovered using wavefunctions corrected for non-BO effects.<sup>11,40</sup> Thereafter, we will perform a simple numerical test for an H2 molecule translating and stretching, from which we will observe that the continuity equation can be reasonably satisfied using the **Γ** expression presented in Eqs. (33) and (37)—although far worse results are recovered using a previously defined phase-space electronic Hamiltonian (from Refs. 38 and 52) based on an atomic orbital basis. 

##### _1. Theory_ 

For a system of electrons and nuclei, let us begin by defining the electronic charge and the current density operators, 





where _ψ_ ˆ<sup>†</sup> ( **_r_** )/ _ψ_ ˆ ( **_r_** ) is the creation and annihilation operator for an electron at position **_r_** . As is well known, there is a 

continuity equation for the electron based on the electronic Schrodinger’s equation, 



Here, we have written the electronic Hamiltonian operator in terms of the creation and annihilation operators, 



Equation (89) is an operator equation that holds for exact quantum dynamics. One means of checking the accuracy of approximate dynamics, (e.g., for a trajectory moving along the eigensurface of a phase space electronic Hamiltonian) is to test whether or not this continuity equation still holds during such approximate dynamics. Equation (89) clearly does not hold for BO motion because, in such a case, the electronic current operator will always have an expectation value of zero. 



Next, we can evaluate the electronic current density missing in the BO approximation, 



One notices immediately that if we include the first-order non-BO correction, a non-zero current density arises. 

The next step is to evaluate the electronic flux for this current density. From the commutation relationship in Eq. (89), it follows that ( _EI_ − _EJ_ )⟨Φ _I_ ∣ **_ρ_** ˆ _e_ ( **_r_** )∣Φ _J_ ⟩= _i_ ̵ _h_ ⟨Φ _I_ ∣∇⋅ **_j_**<sup>ˆ</sup> _e_ ( **_r_** )∣Φ _J_ ⟩. (93) 

Using Eq. (93), we now evaluate 







J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-10 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 



**FIG. 2.** A test of the continuity equation for a translating H2 molecule. We plot the charge density differences (left panel) and the negative of the divergence of the current density [with basis free (BF) **Γ**<sup>ˆ</sup> from Eqs. (33) and (37), right panel] projected on the _xy_ plane for different basis sets (small at the top, large at the bottom). The positions of the two H atoms are at ±0.693 83 bohr along the _x_ axis (indicated by the cross symbol in white). The strong agreement of these figures is a good validation of a phase-space electronic Hamiltonian. 

Equation (97) was a key result proven previously by Nafie<sup>11</sup> and Hanasaki and Takatsuka.<sup>40</sup> According to Eq. (89), in order to recover the electronic continuity equation, we do not need to run exact quantum dynamics; we need only the first-order corrections to BO theory. We will now show that a phase space electronic Hamiltonian also recovers a meaningful electronic current density by plotting the left and right hand sides of Eq. (97). 

As a side note, we mention that, from Eq. (97), one can derive the standard, beyond-Born–Oppenheimer electronic momentum. In particular, we can multiply both LHS and RHS of Eq. (97) by position and electronic mass and integrate over all space. In particular, the LHS becomes 



Here, in Eq. (98), we used integration by parts. The RHS of Eq. (97) becomes 





Combining Eqs. (99) and (101), we recover the expression for the electronic momentum. In Fig. 1, we benchmarked our phase space results against the result above [Eq. (101)] for electronic momentum. In Figs. 2 and 3, an even more strenuous test is used to benchmark against the current density. 

##### _2. Numerical examples_ 

To test if and how a phase-space electronic Hamiltonian approach obeys the continuity equation for the current density [Eq. (97)], we first look at the translational motion of a H2 molecule along the positive x axis. In Fig. 2, we plot the difference in charge densities as computed by finite difference [left panel, the right hand side of Eq. (97)] vs the divergence of the current densities [right panel, the left hand side of Eq. (97)]. We make this comparison for several different basis sets from small to large. Details of the basis sets used are listed in Table I. The phase-space approach reproduces the correct nodal structures as we increase the size of the basis sets [in principle, a complete set of basis is assumed in Eq. (89)], which is a good first validation of the method. However, a stronger test of the method is to investigate an internal motion (rather a total translation). 

To that end, next, we look at results when we move one H atom closer to the other one, and we show how a poor electronic structure method can produce very low quality, non-physical current densities. In the spirit of the previous figure, on the left panel of Fig. 3, we plot the differences in electronic charge densities computed by finite difference, and in the middle panel, we plot the divergence of the current densities as computed from the **Γ**<sup>ˆ</sup> operator presented in the main body of our paper (BF = basis free). Finally, on the right panel, we plot the divergence of the current density as found using the previous **Γ**<sup>ˆ</sup> defined explicitly in atomic orbital basis (from Refs. 38 and 52). Clearly, the left and middle panels do not depend strongly on basis; however, the right panel depends critically (and incorrectly) on basis, and very bizarre nodal structures are found for the aug-ccpVQZ results in Fig. 3. Altogether, these data highlight the power of the method proposed in the main body of this article and also demonstrate why a basis free approach for **Γ**<sup>ˆ</sup> is essential when modeling coupled nuclear-electronic dynamics. For the basis-free **Γ**<sup>ˆ</sup> results shown in Fig. 3, we use 1/ _σ_<sup>2</sup> = 4 bohr<sup>−2</sup> . As a side note, we note that further tuning of the parameters (e.g., 1/ _σ_<sup>2</sup> = 1 bohr<sup>−2</sup> ) can even 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-11 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 



**FIG. 3.** A test of the continuity equation for a stretching H2 molecule, where we move the H atom located at the negative _x_ axis closer to the other H atom with a velocity corresponding to the room temperature. We plot the charge density differences (left panel) and the negative of the divergence of the current density (middle and right panels) projected on the _xy_ plane as computed with different basis sets (small at the top, large at the bottom). The positions of the two H atoms are at ±0.693 83 bohr along the _x_ axis (indicated by the cross symbol in white). The agreement between the left and middle panels [with basis free (BF) **Γ**<sup>ˆ</sup> from Eqs. (33) and (37)] offers a resounding validation of the approach taken in this paper. Here, we set _σ_ = 0.5 bohr; note that even better results can be found by tuning _σ_ in Eq. (28). By contrast, one finds much worse results using the phase-space electronic Hamiltonian approach using a **Γ**<sup>ˆ</sup> operator built from an atomic orbital (AO) basis (from Refs. 38 and 52, right panel); the latter can clearly predict quite unphysical results for large basis sets. 

**TABLE I.** Different basis sets for H2. 

||Num. and type|Num. of basis|
|---|---|---|
|Basis set|of shell|functions per H|
|STO-3G|1s|1|
|cc-pVDZ (DZ)|2s1p|5|
|cc-pVTZ(TZ)|3s2p1d|14|
|aug-cc-pVTZ (aTZ)|4s3p2d|23|
|cc-pVQZ (QZ)|4s3p2d1f|30|
|aug-cc-pVQZ (aQZ)|5s4p3d2f|46|



remove the small extra nodal structures in the divergences of the current densities when computed with basis-free **Γ**<sup>ˆ</sup> , as shown in Fig. S1. A quantitative analysis is also provided in Table S1. A more careful parameterization of the Θ function in Eq. (28) for a diverse group of molecules will be very fruitful for future work. 

##### V. DISCUSSION AND CONCLUSIONS 

Our phase approach above is summed up by Eqs. (9), (33), and (37). From a bird’s eye view, this approach can be viewed as a local strategy to remove the local center of mass from a messy quantum mechanical problem with many nuclei and electrons. For calculations of a small isolated molecule, such a procedure is wellknown and can be found in just about any quantum textbook: one 

transforms from a system of lab coordinates to a new set of coordinates where the electrons are expressed relative to the nuclear center of mass.<sup>13,60</sup> While this approach is quite logical for an isolated system, upon reflection, this approach is suboptimal in the context of electronic structure theory in the condensed phase. Indeed, within electronic structure theory, one paradigm has always been that calculations of isolated systems should remain separate (which necessarily leads to size-consistency of the total energy).<sup>61</sup> The approach above would seem to break such a paradigm because, for one molecule on earth and another on the moon, the standard separation would express all electronic coordinates relative to some point beyond the exosphere. By contrast, in some senses, the intuition of a phase space approach is that in solving the electronic Schrodinger equation, one can effectively choose different electronic coordinates as relative to the closest nucleus. Put differently, every electron experiences the motion of the nuclei close by such that each composite (nuclear plus electronic) subsystem attempts to conserve the local momentum. When the nuclei are not moving, the phase space electronic Hamiltonian becomes effectively a BO Hamiltonian (with the **Γ**<sup>ˆ2</sup> terms as an approximation to the diagonal BO correction). 

Looking forward, the data in Fig. 1 are extremely encouraging as an initial step toward a new and more powerful (but still very inexpensive) approach to electronic structure theory beyond BO theory. As far as developing a practical method, clearly the next step is to generate a large set of data, with many molecules at many different geometries, from which we can generate an optimal Θ partitioning 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-12 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

of space [Eq. (28)] and _ζ_ localizing functions [Eq. (38)]. The target is clear: we wish to optimize (i) the predicted electronic momenta as well as (ii) VCD spectra<sup>12,62,63</sup> and potentially (iii) vibrational and rotational energies. For point (ii), note that the present method has already been validated against experimental VCD signals for (2S,3S)-oxirane-d2.<sup>43</sup> For point (iii), note that we have recently demonstrated that the present phase-space approaches can yield improved vibrational energies<sup>64</sup> for a model problem where exact eigenstates can be calculated numerically. Comparisons to experimental rotational energies<sup>65</sup> should also be possible in the future. Altogether, so far, we have found a great deal of success with the Θ function in Eq. (28), but future work will benefit greatly by performing a more thorough optimization. After all, we have guessed the Gaussian kernel density form of Θ in Eq. (28), but there are many other localization function and length scales available; the form of _ζ_ is equally fungible. Altogether, further benchmarking against highly accurate, perhaps rotationally refined, vibrational and rotational spectra may allow for further development of a meaningful set of parameters. 

Armed with a meaningful phase space approach to electronic structure theory, one can imagine a wide swath of potentially exciting applications. As mentioned in the Introduction, phase space dynamics conserve angular momentum, and one immediate application will be to investigate what can be learned by including spin–orbit coupling in our simulations and then running dynamics along phase space adiabats. Indeed, in the context of a curve crossing, it is possible that one will recover new spin physics during an electron transfer event, when changes in the electronic orbital angular momentum must be balanced by changes in the nuclear and/or electronic spin. In particular, there is some hope that the present simulations will offer a new approach toward understanding the CISS effect.<sup>66</sup> 

Beyond coupled nuclear–electronic-spin simulations, another very promising avenue is to investigate superconductivity. The underlying physics for many superconductive systems is electron–phonon coupling.<sup>67</sup> Thus, it might be very interesting to investigate the behavior of a phase-space Hamiltonian that directly couples phonons to electrons for low-gap systems, especially solid-state or otherwise extended systems, where the role of electron–electron correlation is critical and becomes entangled with electron–nuclear correlation.<sup>68–70</sup> 

##### SUPPLEMENTARY MATERIAL 

In the supplementary material, we include a test of the electronic continuity equation using _σ_ = 1 bohr for the basis-free results and a table showing the sum of squares error for the electronic continuity equation. 

##### ACKNOWLEDGMENTS 

This work was supported by the National Science Foundation under Grant No. CHE-2422858. We thank Mansi Bhati for helpful discussions. J.E.S. thanks Daniel Ezra Subotnik for a lifetime of probing questions. 

##### AUTHOR DECLARATIONS 

##### Conflict of Interest 

The authors have no conflicts to disclose. 

##### Author Contributions 

Zhen Tao and Tian Qiu contributed equally to this work. 

**Zhen Tao** : Conceptualization (equal); Data curation (equal); Investigation (equal); Methodology (equal); Writing – original draft (equal); Writing – review & editing (equal). **Tian Qiu** : Conceptualization (equal); Data curation (equal); Investigation (equal); Methodology (equal); Writing – original draft (equal); Writing – review & editing (equal). **Xuezhi Bian** : Conceptualization (supporting); Data curation (supporting); Investigation (supporting); Methodology (supporting); Writing – original draft (supporting); Writing – review & editing (supporting). **Titouan Duston** : Investigation (supporting); Methodology (supporting); Writing – review & editing (supporting). **Nadine Bradbury** : Investigation (supporting); Methodology (supporting); Writing – review & editing (supporting). **Joseph E. Subotnik** : Conceptualization (equal); Data curation (equal); Funding acquisition (lead); Investigation (equal); Methodology (equal); Writing – original draft (equal); Writing – review & editing (equal). 

##### DATA AVAILABILITY 

The data that support the findings of this study are available within the article and its supplementary material. 

##### REFERENCES 

1R. Naaman and D. H. Waldeck, “Chiral-induced spin selectivity effect,” J. Phys. Chem. Lett. **3** , 2178 (2012). 

> 2J. Fransson, “Vibrational origin of exchange splitting and chiral-induced spin selectivity,” Phys. Rev. B **102** , 235416 (2020). 

> 3J. Gersten, K. Kaasbjerg, and A. Nitzan, “Induced spin filtering in electron transmission through chiral molecular layers adsorbed on metals with strong spin–orbit coupling,” J. Chem. Phys. **139** , 114111 (2013). 

> 4H. J. Eckvahl, N. A. Tcyrulnikov, A. Chiesa, J. M. Bradley, R. M. Young, S. Carretta, M. D. Krzyaniak, and M. R. Wasielewski, “Direct observation of chirality-induced spin selectivity in electron donor–acceptor molecules,” Science **382** , 197 (2023). 

> 5C. Li, R. Requist, and E. K. U. Gross, “Energy, momentum, and angular momentum transfer between electrons and nuclei,” Phys. Rev. Lett. **128** , 113001 (2022). 

> 6Y. Shu, L. Zhang, Z. Varga, K. A. Parker, S. Kanchanakungwankul, S. Sun, and D. G. Truhlar, “Conservation of angular momentum in direct nonadiabatic dynamics,” J. Phys. Chem. Lett. **11** , 1135 (2020). 

7Z. Tao, X. Bian, Y. Wu, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “Total angular momentum conservation in Ehrenfest dynamics with a truncated basis of adiabatic states,” J. Chem. Phys. **160** , 054104 (2024). 

8X. Bian, Z. Tao, Y. Wu, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “Total angular momentum conservation in _ab initio_ Born–Oppenheimer molecular dynamics,” Phys. Rev. B **108** , L220304 (2023). 9N. V. Cohan and H. F. Hameka, “Isotope effects in optical rotation,” J. Am. Chem. Soc. **88** , 2136 (1966). 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-13 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

10A. D. Buckingham, P. W. Fowler, and P. A. Galwas, “Velocity-dependent property surfaces and the theory of vibrational circular dichroism,” Chem. Phys. **112** , 1 (1987). 

> 11L. A. Nafie, “Adiabatic molecular properties beyond the Born–Oppenheimer approximation. Complete adiabatic wave functions and vibrationally induced electronic current density,” J. Chem. Phys. **79** , 4950 (1983). 

> 12P. J. Stephens, “Theory of vibrational circular dichroism,” J. Phys. Chem. **89** , 748 (1985). 

13R. Littlejohn, J. Rawlinson, and J. Subotnik, “Representation and conservation of angular momentum in the Born–Oppenheimer theory of polyatomic molecules,” J. Chem. Phys. **158** , 104302 (2023). 14M. V. Berry and J. M. Robbins, “Chaotic classical and half-classical adiabatic reactions: Geometric magnetism and deterministic friction,” Proc. R. Soc. A **442** , 659 (1993). 

> 15T. Culpitt, L. D. M. Peters, E. I. Tellgren, and T. Helgaker, “Ab initio molecular dynamics with screened Lorentz forces. I. Calculation and atomic charge interpretation of berry curvature,” J. Chem. Phys. **155** , 024104 (2021). 

> 16L. D. M. Peters, T. Culpitt, E. I. Tellgren, and T. Helgaker, “Magnetictranslational sum rule and approximate models of the molecular berry curvature,” J. Chem. Phys. **157** , 134108 (2022). 17S. Ren, J. Bonini, M. Stengel, C. E. Dreyer, and D. Vanderbilt, “Adiabatic dynamics of coupled spins and phonons in magnetic insulators,” Phys. Rev. X **14** , 011041 (2024). 

18Y. Wu and J. E. Subotnik, “Semiclassical description of nuclear dynamics moving through complex-valued single avoided crossings of two electronic states,” J. Chem. Phys. **154** , 234101 (2021). 19C. Wittig, “The Landau–Zener formula,” J. Phys. Chem. B **109** , 8428 (2005). 20M. Amano and K. Takatsuka, “Quantum fluctuation of electronic wave-packet dynamics coupled with classical nuclear motions,” J. Chem. Phys. **122** , 084113 (2005). 21K. Takatsuka and T. Yonehara, “Exploring dynamical electron theory beyond the Born–Oppenheimer framework: From chemical reactivity to non-adiabatically coupled electronic and nuclear wavepackets on-the-fly under laser field,” Phys. Chem. Chem. Phys. **13** , 4987 (2011). 22V. Krishna, “Path integral formulation for quantum nonadiabatic dynamics and the mixed quantum classical limit,” J. Chem. Phys. **126** , 134107 (2007). 23P. V. Parandekar and J. C. Tully, “Mixed quantum-classical equilibrium,” J. Chem. Phys. **122** , 094102 (2005). 24J. R. Schmidt, P. V. Parandekar, and J. C. Tully, “Mixed quantum-classical equilibrium: Surface hopping,” J. Chem. Phys. **129** , 044104 (2008). 

> 25A. Abedi, N. T. Maitra, and E. K. U. Gross, “Exact factorization of the time-dependent electron-nuclear wave function,” Phys. Rev. Lett. **105** , 123002 (2010). 26A. Abedi, N. T. Maitra, and E. K. U. Gross, “Correlated electron-nuclear dynamics: Exact factorization of the molecular wavefunction,” J. Chem. Phys. **137** , 22A530 (2012). 27A. Scherrer, F. Agostini, D. Sebastiani, E. K. U. Gross, and R. Vuilleumier, “On the mass of atoms in molecules: Beyond the Born–Oppenheimer approximation,” Phys. Rev. X **7** , 031035 (2017). 

28F. Talotta, D. Lauvergnat, and F. Agostini, “Describing the photo-isomerization of a retinal chromophore model with coupled and quantum trajectories,” J. Chem. Phys. **156** , 184104 (2022). 

> 29C. C. Martens, “Surface hopping by consensus,” J. Phys. Chem. Lett. **7** , 2610 (2016). 

> 30C. C. Martens, “Surface hopping without momentum jumps: A quantumtrajectory-based approach to nonadiabatic dynamics,” J. Phys. Chem. A **123** , 1110 (2019). 

> 31G. H. Gossel, F. Agostini, and N. T. Maitra, “Coupled-trajectory mixed quantum-classical algorithm: A deconstruction,” J. Chem. Theory Comput. **14** , 4513 (2018). 

> 32D. A. Micha, “A self-consistent eikonal treatment of electronic transitions in molecular collisions,” J. Chem. Phys. **78** , 7138 (1983). 

> 33S. Weinberg, “Eikonal method in magnetohydrodynamics,” Phys. Rev. **126** , 1899 (1962). 

> 34M. V. Berry, “Quantum phase corrections from adiabatic iteration,” Proc. R. Soc. A **414** , 31 (1987). 

> 35M. V. Berry, “Histories of adiabatic quantum transitions,” Proc. R. Soc. A **429** , 61 (1990). 36N. Shenvi, “Phase-space surface hopping: Nonadiabatic dynamics in a superadiabatic basis,” J. Chem. Phys. **130** , 124117 (2009). 

> 37Y. Wu, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “Linear and angular momentum conservation in surface hopping methods,” J. Chem. Phys. **160** , 024119 (2024). 

> 38Z. Tao, T. Qiu, M. Bhati, X. Bian, T. Duston, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “Practical phase-space electronic Hamiltonians for _ab initio_ dynamics,” J. Chem. Phys. **160** , 124101 (2024). 

> 39S. Patchkovskii, “Electronic currents and Born–Oppenheimer molecular dynamics,” J. Chem. Phys. **137** , 084109 (2012). 

> 40K. Hanasaki and K. Takatsuka, “On the molecular electronic flux: Role of nonadiabaticity and violation of conservation,” J. Chem. Phys. **154** , 164112 (2021). 

> 41L. A. Nafie, “Velocity-gauge formalism in the theory of vibrational circular dichroism and infrared absorption,” J. Chem. Phys. **96** , 5687 (1992). 

42T. Duston, Z. Tao, X. Bian, M. Bhati, J. Rawlinson, R. G. Littlejohn, Z. Pei, Y. Shao, and J. E. Subotnik, “A phase-space electronic Hamiltonian for vibrational circular dichroism,” J. Chem. Theory Comput. **20** , 7904 (2024). 

> 43Z. Tao, T. Duston, Z. Pei, Y. Shao, J. Rawlinson, R. Littlejohn, and J. E. Subotnik, “An electronic phase-space Hamiltonian approach for electronic current density and vibrational circular dichroism,” J. Chem. Phys. **161** , 204107 (2024). 

> 44D. R. Bates and R. McCarroll, “Electron capture in slow collisions,” Proc. R. Soc. A **245** , 175 (1958). 

45W. R. Thorson and J. B. Delos, “Theory of near-adiabatic collisions. I. Electron translation factor method,” Phys. Rev. A **18** , 117 (1978). 46L. F. Errea, C. Harel, H. Jouini, L. Mendez, B. Pons, and A. Riera, “Common translation factor method,” J. Phys. B: At., Mol. Opt. Phys. **27** , 3603 (1994). 47E. Deumens, A. Diz, R. Longo, and Y. Öhrn, “Time-dependent theoretical treatments of the dynamics of electrons and nuclei in molecular systems,” Rev. Mod. Phys. **66** , 917 (1994). 

> 48T. G. Winter, “Electron transfer in _p_ –He+ and He2+-H collisions using a Sturmian basis,” Phys. Rev. A **25** , 697 (1982). 

49S. B. Schneiderman and A. Russek, “Velocity-dependent orbitals in proton-onhydrogen-atom collisions,” Phys. Rev. **181** , 311 (1969). 50S. Fatehi, E. Alguire, Y. Shao, and J. E. Subotnik, “Analytic derivative couplings between configuration-interaction-singles states with built-in electrontranslation factors for translational invariance,” J. Chem. Phys. **135** , 234105 (2011). 

51V. Athavale, X. Bian, Z. Tao, Y. Wu, T. Qiu, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “Surface hopping, electron translation factors, electron rotation factors, momentum conservation, and size consistency,” J. Chem. Phys. **159** , 114120 (2023). 

52T. Qiu, M. Bhati, Z. Tao, X. Bian, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “A simple one-electron expression for electron rotational factors,” J. Chem. Phys. **160** , 124102 (2024). 

> 53M. Senechal, “Mathematical structures: _Spatial Tessellations_ . Concepts and applications of voronoi diagrams. Atsuyuki Okabe, Barry Boots, and Kokichi Sugihara. Wiley, New York, 1992. xii, 532 pp., illus. $89.95. Wiley series in probability and mathematical statistics,” Science **260** , 1170–1173 (1993). 

> 54R. Littlejohn, J. Rawlinson, and J. Subotnik, “Diagonalizing the Born–Oppenheimer Hamiltonian via Moyal perturbation theory, nonadiabatic corrections, and translational degrees of freedom,” J. Chem. Phys. **160** , 114103 (2024). 

> 55E. Epifanovsky, A. T. B. Gilbert, X. Feng, J. Lee, Y. Mao, N. Mardirossian, P. Pokhilko, A. F. White, M. P. Coons, A. L. Dempwolff _et al._ , “Software for the frontiers of quantum chemistry: An overview of developments in the Q-Chem 5 package,” J. Chem. Phys. **155** , 084801 (2021). 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-14 

**The Journal of Chemical Physics** 

**ARTICLE** 

**pubs.aip.org/aip/jcp** 

56R. G. Littlejohn and W. G. Flynn, “Geometric phases in the asymptotic theory of coupled wave equations,” Phys. Rev. A **44** , 5239 (1991). 

57I. A. Aucar, S. S. Gómez, M. C. R. de Azúa, and C. G. Giribet, “Theoretical study of the nuclear spin-molecular rotation coupling for relativistic electrons and nonrelativistic nuclei,” J. Chem. Phys. **136** , 204119 (2012). 

> 58A. Nitzan, _Chemical Dynamics in Condensed Phases_ (Oxford University Press, 2006). 

> 59X. Bian, Y. Wu, T. Qiu, Z. Tao, and J. E. Subotnik, “A semiclassical nonadiabatic phase-space approach to molecular translations and rotations: Surface hopping with electronic inertial effects,” J. Chem. Phys. **161** , 234114 (2024). 

> 60F. Jensen, _Introduction to Computational Chemistry_ (Wiley, 1999). 

61David Sherrill CIS notes, http://vergil.chemistry.gatech.edu/notes/ci.pdf. 

> 62A. Scherrer, F. Agostini, D. Sebastiani, E. K. U. Gross, and R. Vuilleumier, “Nuclear velocity perturbation theory for vibrational circular dichroism: An approach based on the exact factorization of the electron-nuclear wave function,” J. Chem. Phys. **143** , 074106 (2015). 

63E. Ditler, T. Zimmermann, C. Kumar, and S. Luber, “Implementation of nuclear velocity perturbation and magnetic field perturbation theory in CP2K and their 

application to vibrational circular dichroism,” J. Chem. Theory Comput. **18** , 2448 (2022). 

> 64X. Bian, C. Khan, T. Duston, J. Rawlinson, R. G. Littlejohn, and J. E. Subotnik, “A phase-space view of vibrational energies without the Born–Oppenheimer framework,” J. Chem. Theory Comput. **21** (6), 2880–2893 (2025). 

> 65S. Davis, D. T. Anderson, G. Duxbury, and D. J. Nesbitt, “Jet-cooled molecular radicals in slit supersonic discharges: Sub-Doppler infrared studies of methyl radical,” J. Chem. Phys. **107** , 5661 (1997). 

> 66B. P. Bloom, Y. Paltiel, R. Naaman, and D. H. Waldeck, “Chiral induced spin selectivity,” Chem. Rev. **124** , 1950 (2024). 

> 67J. R. Schrieffer, _Theory of Superconductivity_ (CRC Press, 2018). 

> 68T. Helgaker and P. Jorgensen, _Molecular Electronic Structure Theory_ (Wiley, New York, 2013). 

> 69G. P. Chen, V. K. Voora, M. M. Agee, S. G. Balasubramani, and F. Furche, “Random-phase approximation methods,” Annu. Rev. Phys. Chem. **68** , 421 (2017). 

70J. A. Parkhill and M. Head-Gordon, “A tractable and accurate electronic structure method for static correlations: The perfect hextuples model,” J. Chem. Phys. **133** , 024103 (2010). 

J. Chem. Phys. **162** , 144111 (2025); doi: 10.1063/5.0260731 Published under an exclusive license by AIP Publishing 

**162** , 144111-15 



