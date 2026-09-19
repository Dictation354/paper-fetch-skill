---
title: "On-chip on-demand delivery of K+ for in vitro bioelectronics"
doi: "10.1063/5.0129134"
source: "aip_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 8170
---

# On-chip on-demand delivery of K+ for in vitro bioelectronics

#### ABSTRACT

Bioelectronic devices that interface electronics with biological systems can actuate and control biological processes. The potassium ion plays a vital role in cell membrane physiology, maintaining the cell membrane potential (Vmem) and generating action potentials. In this work, we present two bioelectronic ion pumps that use an electronic signal to modulate the potassium ion concentration in solution. The first ion pump is designed to integrate directly with six-well cell culture plates for optimal ease of integration with _in vitro_ cell culture, and the second on-chip ion pump provides high spatial resolution. These pumps offer increased ease of integration with _in vitro_ systems and demonstrate K<sup>+</sup> concentration distribution with high spatial resolution. We systematically investigate the ion pump’s performance using electrical characterization and computational modeling, and we explore closed-loop control of K<sup>+</sup> concentration using fluorescent dyes as indicators. As a proof-of-concept, we study the effects of modulating K<sup>+</sup> concentration on Vmem of THP-1 macrophages.

© _2022 Author(s). All article content, except where otherwise noted, is licensed under a Creative Commons Attribution (CC BY) license (http://creativecommons.org/licenses/by/4.0/)._ https://doi.org/10.1063/5.0129134

RESEARCH ARTICLE | DECEMBER 05 2022

## **On-chip on-demand delivery of K+ for** **_in vitro_ bioelectronics**

Harika Dechiraju; John Selberg; Manping Jia; Pattawong Pansodtee; Houpu Li; Hao-Chieh Hsieh; Cristian Hernandez; Narges Asefifeyzabadi; Tiffany Nguyen; Prabhat Baniya; Giovanny Marquez; Cody Rasmussen-Ivey; Carrie Bradley; Mircea Teodorescu; Marcella Gomez; Michael Levin; Marco Rolandi 

_AIP Advances_ 12, 125205 (2022) https://doi.org/10.1063/5.0129134

 View Export Online<sup></sup> Citation

### **Articles You May Be Interested In**

Bioelectronic control of chloride ions and concentration with Ag/AgCl contacts _APL Mater._ (September 2020)

Measuring cellular contraction: Current progress and a future in bioelectronics _APL Mater._ (April 2021) Soft bioelectronics for cardiac interfaces _Biophysics Rev._ (January 2022)

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

## On-chip on-demand delivery of K<sup>**+**</sup> for _in vitro_ bioelectronics

Cite as: AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 Submitted: 14 October 2022 • Accepted: 13 November 2022 • Published Online: 5 December 2022

Harika Dechiraju,<sup>1</sup> John Selberg,<sup>1</sup> Manping Jia,<sup>1</sup> Pattawong Pansodtee,<sup>1</sup> Houpu Li,<sup>1</sup> Hao-Chieh Hsieh,<sup>1</sup> Cristian Hernandez,<sup>1</sup> Narges Asefifeyzabadi,<sup>1</sup> Tiffany Nguyen,<sup>1</sup> Prabhat Baniya,<sup>1</sup> Giovanny Marquez,<sup>2</sup> Cody Rasmussen-Ivey,<sup>3</sup> Carrie Bradley,<sup>1</sup> Mircea Teodorescu,<sup>1,4</sup> Marcella Gomez,<sup>2,5</sup> Michael Levin,<sup>3</sup> and Marco Rolandi<sup>1,4,5,a)</sup>

#### I. INTRODUCTION

Bioelectronics bridges the gap between biology and electronics in sensing and actuation.<sup>1–4</sup> One of the main challenges for bioelectronic devices is translating ionic currents prevalent in biology to electronic signals and vice versa. This is because signal transmission in biological systems relies on the movement of ions and biomolecules instead of electrons and holes.<sup>5–7</sup> Ion pumps address this issue by translating currents to the flow of a particular species of ions and biomolecules at the device level.<sup>8–10</sup> They facilitate the movement of ions and molecules with an induced electric field<sup>11</sup> and have various applications, such as in reducing inflammation,<sup>1</sup>

treatment of epilepsy,<sup>2</sup> influencing cell differentiation,<sup>12</sup> and promoting wound healing.<sup>13</sup>

The potassium ion is of great significance in biological systems.<sup>14</sup> It plays a vital role in cell membrane physiology, particularly in maintaining the cell membrane potential (Vmem) and generating action potentials.<sup>15</sup> Propagating waves of potassium have also been shown to trigger the conductance of long-range electrical signals in bacterial colonies.<sup>16</sup> The active transport of potassium ions across the cell membrane is essential to nerve function.<sup>14,17</sup> Potassium ions are also important in maintaining cardiovascular function.<sup>18</sup>

Cell-based _in vitro_ studies are increasingly becoming popular, with applications in drug discovery, tissue engineering, and

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-1

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

regeneration, due to their lower cost and greater standardization than _in vivo_ studies.<sup>19</sup> There is a need to develop bioelectronic systems to interface with and control these _in vitro_ systems.<sup>20</sup>

This work presents two bioelectronic potassium ion pumps that modulate the ion concentration for _in vitro_ cell culture. The first ion pump is designed to integrate directly with six-well cell culture plates for optimal ease of integration with _in vitro_ cell culture and is fabricated using simple replica molding with polydimethylsiloxane (PDMS) and 3D printed molds. The second on-chip ion pump evolved from the first ion pump with an on-chip cell culture chamber and a 3 × 3 microchannel array to interact with cells with a high spatial resolution of K<sup>+</sup> delivery and is fabricated using photolithography with SU-8. The on-chip ion pump eliminates a cell culture plate and provides a continuous flow of cell culture media for long-term cell activity monitoring.

#### II. RESULTS AND DISCUSSION

The PDMS-based bioelectronic ion pump [Fig. 1(a)] is placed in a 3D-printed adapter that fits directly into a six-well cell culture plate. This increases the ease of integration of the ion pump with _in vitro_ cultures [Fig. 1(b)]. The ion pump transfers potassium ions from a reservoir to a target, with a voltage (VK+, typically between 0.5 and 2 V) applied between the working electrode (WE) and the reference electrode (RE). The target refers to the well in a six-well cell culture plate. A capillary filled with anionic hydrogel selectively transports cations between the target and the reservoir<sup>21,22</sup> [Fig. 1(c)]. In the reservoir, K<sup>+</sup> comes from the KCl salt (1M) that exists in the solution mainly as K<sup>+</sup> and Cl<sup>−</sup> (stability constant, log K = 0.10 at 25<sup>○</sup> C).<sup>23</sup> For a positive VK+, the negative Cl<sup>−</sup> is attracted

to the Ag surface of the WE. When Cl<sup>−</sup> reaches the Ag surface, it oxidizes to Cl. Subsequently, the Cl physisorbs onto the Ag surface to form AgCl. The resulting K<sup>+</sup> is then pushed by the electric field from the reservoir containing the WE into the target through the capillary [Fig. 1(d)]. Simultaneously, at the RE, the AgCl undergoes reduction to form Ag.

We set up the well plate under a fluorescence microscope (Keyence BZ-X710) to demonstrate and monitor K<sup>+</sup> delivery from the ion pump in real time [Fig. 2(a)]. The target now consists of a solution of ION Potassium Green-2 dye. This dye changes the fluorescence intensity linearly with changes in [K<sup>+</sup>] [Fig. 2(b)]. We applied 5 alternating pulses of VK+ of +1.5 and −1.5 V, with each voltage applied for 2 min at a time. The positive voltage is to push K<sup>+</sup> from the reservoir to the target, while the negative voltage is to move cations in the opposite direction. The current produced upon applying VK+ was recorded and is presented in Fig. 2(c). An electron is transferred from the RE to the WE for each ion being delivered. To measure the amount of K<sup>+</sup> delivered, we recorded the change in fluorescence intensity of the target during the course of actuation. An increase in [K<sup>+</sup>] is indicated by an increase in the fluorescence intensity of the dye [Fig. 2(d)]. We then calculated the amount of K<sup>+</sup> delivered to the target by calibrating the fluorescent dye with solutions of known [K<sup>+</sup>].

We use the current and fluorescence intensity to determine the amount of charge transferred and potassium ion delivered, respectively, to calculate the delivery efficiency. The efficiency is given by the following equation:

**FIG. 1.** (a) Image of the ion pump with the adapter. Scale bar—1 cm. (b) Image of the device and adapter in a six-well plate. Scale bar—1.5 cm. (c) Schematic of the ion pump. (d) Reactions taking place at the working electrode.

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-2

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

**FIG. 2.** (a) Experimental setup of the ion pump. The ion pump is inserted in a six-well cell culture plate containing fluorescent dyes as the target and is placed under a fluorescence microscope for real-time imaging during actuation. Scale bar—3.5 cm. (b) Fluorescence microscope image of the target area with working and reference electrodes. Scale bar—100 _μ_ m. (c) Current response of the device to an applied voltage. (d) Fluorescence response of the device to an applied voltage. (e) Current response of the device to a series of applied voltages. The reservoir contains 1M KCl. (f) Current response of the device to a series of applied voltages. The reservoir contains 100 mM KCl.

We calculated that the potassium ion was delivered with an efficiency of ∼33% across all devices tested.

To study the effect of VK+ on the delivery dosage of K<sup>+</sup>, we actuated the pump with various voltages from 0.2 to 1.2 V and recorded the current produced by actuation. The ion pump produced a steady state current of ∼8 _μ_ A for an actuation voltage of 1.2 V. In contrast, it produced a steady state current of ∼3 _μ_ A for an actuation voltage of 0.2 V [Fig. 2(e)]. This is consistent with our expectation that a higher VK+ would result in a higher current since the ion pump behaves as an ionic resistor. This higher current, in turn, results in more K<sup>+</sup> delivered from the reservoir to the target.

Another factor that could affect the amount of potassium ions delivered is the concentration of the solution used in the reservoir. To study the effect of reservoir concentration on potassium ion delivery, the reservoirs were filled with 100 mM KCl and 1M KCl. We applied a series of actuation voltages between 0.2 and 1.2 V to the ion pump with a 100 mM KCl reservoir. We observed that the currents produced by the ion pump with a 1M KCl reservoir are higher than the currents produced by the pump with a 100 mM KCl reservoir [Fig. 2(f)]. For an applied voltage of 0.2 V, the pump with a 1M KCl reservoir showed a current of ∼3 _μ_ A while the pump with a 100 mM KCl reservoir showed a current of 0.05 _μ_ A. This indicates

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-3

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

that having a higher concentration solution in the reservoir results in a higher current produced for the same applied VK+, which in turn increases the amount of K<sup>+</sup> delivered.

After successfully demonstrating K<sup>+</sup> delivery, in order to achieve spatial resolution of delivery, we developed another design of the ion pumps. This pump consists of two layers of SU-8 bonded together to create microfluidic channels on a glass substrate, which are then filled with the positive ion transporting hydrogel [Figs. 3(a) and 3(b)]. The channels create a 3 × 3 array of 100 _μ_ m diameter pixels set 250 _μ_ m apart at the center of the chip, opening up to a well (Fig. S3). Each of these pixels can be independently actuated and controlled, resulting in a high spatial resolution. A PDMS cap with an 8 × 1 × 0.1 mm<sup>3</sup> microfluidic chamber that inserts into this

well acts as our target (Fig. S4). The cap is used to externally culture cells in the fluidic chamber and can be inserted into the well on the device to integrate the cells with the device. The cap has an inlet and outlet to connect to flow systems for media access to the cells, thus maintaining continuous flow for long-term cell culture.

We characterize the pump by applying alternating pulses of +1 and −1 V between the WE and the RE. Upon applying a positive VK+, potassium ions are delivered from the reservoir to the target through the hydrogel. The pump produced a steady state current of ∼3 _μ_ A for the applied voltage [Fig. 3(c)]. The target was filled with ION Potassium Green-2 solution and imaged in real-time under a fluorescence microscope to observe the change in fluorescence intensity. As reported in Fig. 3(d), we observe an increase

**FIG. 3.** (a) Image of the device. Scale bar—5 mm. (b) Schematic of the ion pump. (c) Current response of the device to an applied voltage pulse. (d) Fluorescence response of the device to an applied voltage pulse. (e) COMSOL simulation result showing the change in concentration after 100 ms of delivery. (f) COMSOL simulation result showing the change in concentration after 10 s of delivery.

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-4

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

and decrease in fluorescence intensity corresponding to the applied voltage.

To further characterize the spatial resolution of the device, we used a COMSOL Multiphysics model to model the diffusion of K<sup>+</sup> from a 100 _μ_ m pixel over time (diffusion coefficient of K<sup>+</sup> = 1.9 × 10<sup>−9</sup> m<sup>2</sup> s<sup>−1</sup> at 25<sup>○</sup> C).<sup>24</sup> The COMSOL model describes the behavior of K<sup>+</sup> injected from a 1 _μ_ A current and assumes that diffusion is dominant in the system. This is expected because the voltage drop occurs primarily across the hydrogel channel. A 1 _μ_ A current was used since this current value was achievable by all the tested devices. A 10<sup>−4</sup> cm<sup>3</sup> volume describes the area in the cell-culture microfluidic immediately around the array where the diffusion is simulated.

Figure 3(e) shows the diffusion of K<sup>+</sup> concentration distribution after 100 ms. There is a high-resolution K<sup>+</sup> concentration gradient around the ion pump pixel from a 1 _μ_ A pulse for 100 ms. The area right above the pixel shows a [K<sup>+</sup>] of 2.5 mM, which gradually diffuses out to a concentration of 1 mM. Figure 3(f) shows the diffusion 10 s after actuation. The [K<sup>+</sup>] directly above the pixel has now dropped to 3.37 _μ_ M. We observe that the change is still the strongest right above the pixel and gradually diffuses out away from the pixel. This is consistent with our assumption that diffusion is dominant during pumping.

To demonstrate the application of these devices for _in vitro_ cell culture, THP-1 macrophages were cultured in the chamber of the PDMS caps, which were then inserted into the device and clamped to seal. This provides a closed path for the continuous flow of media and prevents leakage. THP-1 cells were chosen based on previous work carried out by Li _et al._ in demonstrating the effect

of potassium channels on macrophage polarization.<sup>25</sup> The setup (Fig. S4) was placed in an on-stage incubator on a fluorescence microscope and connected to an ElveFlow flow system for media. DiBAC4(3), a membrane voltage (Vmem) sensitive dye, was flown into the chamber. DiBAC changes its fluorescence intensity with a change in Vmem—an increase in intensity corresponds to increased cell depolarization.

Figure 4(a) shows an image of the macrophage cells distributed in the chamber before actuation. The cells were actuated by delivering K<sup>+</sup> using the ion pump. VK+ of 0.8 V was applied for 20 min, and 0 V was applied for 20 min over 2.5 h. This actuation protocol was selected based on results observed by Selberg _et al._<sup>12</sup> Over the course of actuation, the fluorescence intensity of DiBAC increased [Fig. 4(b)]. This indicates the depolarization of the cells. Figure 4(c) plots the fluorescence intensity of DiBAC at various time points during actuation, and we see that over time, there is an increase in the intensity of DiBAC, indicating a change in the membrane voltage, resulting in the depolarization of these cells.

To be able to apply these ion pumps effectively to biological systems, it is essential to be able to control the concentration of ions being delivered precisely.<sup>12,26–28</sup> As a proof of concept for integrating these ion pumps with closed-loop control, a machine-learning-based closed-loop control algorithm was implemented. The algorithm and architecture used are similar to the ones implemented in an earlier work by Jafari _et al._<sup>26</sup> Figure 4(d) shows a schematic of the controller architecture used. The algorithm is interfaced with the device through a Raspberry Pi control board. The fluorescence intensity response of the device serves as feedback to the algorithm, which then decides the next course of actuation for the device. Figure 4(e)

**FIG. 4.** (a) Fluorescence microscope image of the cells over the device before actuation (t = 0 s). Scale bar—150 _μ_ m. (b) Fluorescence microscope image of the cells over device after actuation (t = 150 min). Scale bar—150 _μ_ m. (c) Plot of change in fluorescence intensity of the cells over time. (d) Schematic of closed-loop control integrated with the device. (e) Plot of the device tracking a given sine wave using the control algorithm.

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-5

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

shows results from the device tracking a set sine wave. The control algorithm adjusts VK+, which is given as input to the device, for the fluorescence intensity to follow the set trajectory. The black trace is the value set by the algorithm, and the red trace is the device’s response to the set value.

Although the ion pumps presented here were developed for delivering potassium, the same design can be utilized to deliver several other positively charged ions such as protons,<sup>29</sup> calcium,<sup>11</sup> small molecules such as acetylcholine,<sup>22</sup> and GABA.<sup>30</sup> In order to deliver these species, the reservoir solution is switched out to a salt solution of the respective species, and the delivery mechanism remains the same. This also increases the ease of multiplexing delivery by allowing us to deliver more than one type of species simultaneously.

#### III. CONCLUSIONS

In this work, we presented two designs of an ion pump capable of modulating the potassium ion concentration in solution. The ion pumps shown here demonstrate the ease of integration with cells for _in vitro_ studies and can modulate the potassium ion concentration with a high spatial resolution. As a proof-of-concept, we integrate the ion pump with THP-1 macrophage cell culture and observe the effects that changing extracellular potassium ion concentration causes on these cells. We also demonstrate a proof-of-concept implementation of a closed-loop control algorithm to drive the device toward the outcome we wish to achieve. The integration of closedloop algorithms with the ion pump has great potential to be applied to the cells to study the effect of the potassium ion on them and enable long-term biological control of membrane voltage with high spatial resolution.

#### _1. Well-plate device (PDMS-based design)_

We designed and printed PDMS molds using Preform software and Form3 3D printers. The molds have two layers, with the bottom layer defining the reservoirs and the top layer defining the lid to seal these reservoirs. Once the PDMS is demolded, Ag and AgCl wires are inserted into the reservoirs to create the electrodes. We then bonded the two layers of PDMS; the contact interfaces were treated in 50 W oxygen plasma for 10 s and clamped together using custom-made aluminum clamps. After bonding, a 1.5 _μ_ m thick water-insulating layer of parylene-C was deposited (Specialty Coating Systems Labcoter) in the presence of an A174 adhesion promoter. This layer also prevents bubbles from being formed in the reservoir. We then inserted four 3 mm long hydrogel-filled capillaries through the PDMS, and the reservoirs were filled with 1M KCl solution using a syringe. The PCB board is soldered onto the PDMS device. Silver conductive paste and alloy dowel pins connect the PCB to the electrodes before soldering to complete the connections.

The device is sealed into a custom-made 3D printed adapter, specifically designed to anchor the device in six-well cell culture plates, and a layer of uncured PDMS is applied at the interface and left to cure for 48 h at room temperature to form a water-tight seal (Fig S1).

#### _2. High spatial resolution device (SU-8-based design)_

The ion pumps offering spatial resolution are fabricated on a glass substrate using photolithography techniques. Gold electrodes are patterned onto the substrate using an S1813 photoresist followed by e-beam evaporation and liftoff processes using acetone/IPA. The surface of the electrodes is modified by electrochemically depositing Ag/AgCl nanoparticles on the surface of the electrodes. A 2 _μ_ m thick SU-8 2002 layer is spin-coated onto the device, which acts as an insulating layer, following which a 40 _μ_ m thick SU-8 3050 layer is spun and patterned to create microfluidic channels on the substrate.

On a second glass wafer, we spin coat a layer of OmniCoat (Kayaku Advanced Materials Inc.) as a sacrificial layer. A 40 _μ_ m thick layer of SU-8 3050 is now spun and patterned to form the features that act as a cap to the microfluidic channels previously patterned. The two glass substrates are now aligned and bonded using a wafer bonder and ramp baked together. The SU-8 layers fuse and bond, thereby creating closed microfluidic channels. Once the bonding is complete, the wafers are sonicated in a bath containing MF319 to dissolve the sacrificial OmniCoat, releasing the two wafers.

Stereolithography techniques are used to create PDMS fluidics that form the ports for the SU-8 microfluidic channels. FormLabs 3D printers are used to print out molds that are then filled with PDMS (10:1 w/w base: curing agent) and left to cure at 60<sup>○</sup> C for 48 h. The PDMS is then demolded and thoroughly cleaned by sonicating in IPA and drying with N2. This PDMS is then chemically bonded onto the SU-8 layer using a 20% v/v solution of (3-aminopropyl) triethoxysilane (APTES) (Sigma-Aldrich, Burlington, Massachusetts, US) in water. The PDMS and SU-8 surface to be bonded are treated with 50 W O2 plasma in a reactive ion etcher for 30 s and then soaked in the APTES solution for 20 min. The surfaces are then rinsed with DI water and dried using N2. The two surfaces are aligned, brought in contact, clamped using custom-made aluminum clamps, and baked at 110<sup>○</sup> C for 30 min. The clamps are then left to cool to room temperature, and the device is removed from them.

Figure S2 shows the detailed fabrication schematic for these devices.

#### _1. Precursor solution_

We used an anionic hydrogel consisting of 2-acrylamido2-methylpropane sulfonic acid (AMPSA) and poly(ethylene glycol) diacrylate (PEGDA). This solution consists of the acrylate monomer mixed with PEGDA and a photo initiator (2-hydroxy4’-(2-hydroxyethoxy)-2-methylpropiophenone), which promotes crosslinking in the presence of UV light. The protocols for making the solution have been previously reported.<sup>21</sup> All chemicals were purchased from Sigma-Aldrich.

#### _2. Capillary preparation (for the PDMS based well plate device)_

Glass capillaries are etched with 1M NaOH solution followed by flushing with DI water. Silane A-174(3-(trimethoxysilyl)propyl methacrylate) (2530-85-0, Sigma-Aldrich, Burlington, Massachusetts, US) in toluene is used to treat the capillaries for 1 h, after

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-6

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

which they are rinsed with ethanol. The hydrogel precursor is now flown into the capillaries and crosslinked under UV at 8 mW/cm<sup>2</sup> (wavelength 306 nm) for 5 min.

#### _3. Hydrogel in SU-8 channels (for the SU-8 based high spatial resolution device)_

Before filling, the device is treated using silane A-174 to promote adhesion between the hydrogel and the SU-8 walls of the channels. To perform the silane treatment, the SU-8 is first treated with O2 plasma for 10 minutes, following which it is placed in a chamber at 90<sup>○</sup> C where A-174 is deposited via chemical vapor deposition. The silane is baked onto the inner walls of the channels on a hotplate at 110<sup>○</sup> C for 10 min.

After the silane has been deposited, the hydrogel precursor solution is flown into the channels and crosslinked under UV at 8 mW/cm<sup>2</sup> (wavelength 306 nm) for 5 min.

#### C. Cell culture

THP-1 macrophages (TIB-202™; ATCC, Manassas, Virginia USA) were grown in an RPMI 1640 medium (30-2001™; ATCC, Manassas, Virginia USA) supplemented with 10% fetal bovine serum (Corning™ 35011CV; Fisher Scientific, Cambridge, Massachusetts, USA) and 100 _μ_ g/ml penicillin-streptomycin (Gibco™ 15140122; Fisher Scientific, Cambridge, Massachusetts USA). Liquid nitrogen cryopreserved stocks (passage four) were seeded into the above-mentioned complete media at an initial seeding density of 200 000 cells/ml. After four days, cells were counted using a hemocytometer and trypan blue solution (T8154; Sigma-Aldrich, Burlington, Massachusetts, USA). Instead of media replacement, cells were either expanded or reduced to a resultant density of 200 000 cells/ml every 48 h. After one week post-resuspension, cells were transferred to the PDMS cell culture cap (Fig. S4), and M0 macrophages were generated by supplementing the media with 100 ng/ml phorbol-12-myristate-13-acetate (524400; SigmaAldrich, Burlington, Massachusetts, USA) for 24 h. Once M0 macrophages were generated, complete media replacements were performed. For M0 macrophages, the subsequent media consisted of complete RPMI (described in detail above). For M1 macrophage generation, complete RPMI media were supplemented with 100 ng/ml of lipopolysaccharide from _Escherichia coli_, serotype O55:B5 (TLRGRADE<sup>®</sup>) (ALX-581-013-L001; Enzo Life Sciences, Farmingdale, New York, USA), and 20 ng/ml recombinant human IFN- _γ_ (300-02; PeproTech, Cranbury, New Jersey, USA) for 24 h and then replaced with complete RPMI. For M2 macrophage generation, complete RPMI media were supplemented with 20 ng/ml of recombinant human interleukin 4 (IL-4) (200-04; PeproTech, Cranbury, New Jersey, USA) and 20 ng/ml of recombinant human interleukin 13 (IL-13) (200-13; PeproTech, Cranbury, New Jersey, USA) for 24 h and then replaced with complete RPMI. After induction of polarization, all polarization states were maintained for 72 h and then used in time-synchronized experiments. All cell culture and experimentation were performed at 37<sup>○</sup> C in a humidified incubator maintained at 5% CO2.

#### D. Control board

The control board is a 16-channel potentiostat interfaced to a Raspberry Pi single board computer, based on the design demonstrated by Pansodtee _et al._<sup>31</sup> Each channel can provide an actuation

voltage of ±4 V and an output current of ±20 _μ_ A. Using an instrumental amplifier, the controller measures real-time current by first measuring the voltage across a high-precision (0.1%) 1 kΩ shunt resistor. The onboard ADS1115 analog-to-digital converters (ADCs) then measure the amplifiers’ output voltages and determine the currents. The actuation voltages are set using the onboard MCP4728 digital-to-analog converters (DACs). The I2C communication bus of the Raspberry Pi is utilized to send commands to the DACs and retrieve data from the ADCs. A Python program running on the Raspberry Pi listens for commands from a client and changes the actuation voltages and measures currents. The Raspberry Pi is put into soft Access Point (AP) mode so that a laptop running the closeloop control program can connect to it via Wi-Fi and provide the necessary course of action based on the current readings.

#### E. Fluorescence probes

We used microscope-based real-time imaging to monitor the change in ion concentration. The fluorescent probe ION Potassium Green-2 (IPG-2) TMA+ salt (3013F, ION Biosciences, Texas) is a yellow-green fluorescent, intracellular potassium ion indicator with λexcitation/λemission of 525/545 nm, respectively, and has high sensitivity to detect small changes in K<sup>+</sup> concentration. It exhibits a linear relationship between fluorescence intensity and K<sup>+</sup> concentration. The dye was made to 3 _μ_ M dispensed in 0.1M Tris buffer. All fluorescence images were analyzed using ImageJ software.

To observe the changes in cell membrane voltage, we used DiBAC4(3) (bis-(1,3-dibutylbarbituric acid) trimethine oxonol) (B438; Thermo Fisher, Waltham, Massachusetts, USA). This dye is a slow-response potential-sensitive probe that enters depolarized cells where it binds to intracellular proteins and/or the cell membrane; increased depolarization results in an increase in fluorescence intensity, whereas hyperpolarization is indicated by a decrease in fluorescence intensity at an λexcitation/λemission of 493/516 nm, respectively. Staining of cells was performed by exposing the cells for 30 min to complete (defined above) the phenol-red-free formula of RPMI (11835030; Thermo Fisher, Waltham, Massachusetts, USA), containing a 10 _μ_ M solution of the dye, followed by imaging (note: the dye was left in the media during image acquisition). All cell images were analyzed using ImageJ software.

#### ACKNOWLEDGMENTS

This research was sponsored by the Defense Advanced Research Projects Agency (DARPA) through Cooperative Agreement No. D20AC00003 awarded by the U.S. Department of the Interior (DOI), Interior Business Center. The content of the information does not necessarily reflect the position or the policy of the Government, and no official endorsement should be inferred. This research is also sponsored by the Army Research Office (ARO) through Contract No. W911NF2210058 issued by US ARMY ACC-APGRTP W911NF. Microfabrication was performed using equipment sponsored by the W. M. Keck Center for Nanoscale Optofluidics, the California Institute for Quantitative Biosciences (QB3), and the Army Research Office, Award No. W911NF-17-1-0460. This work

AIP Advances **12**, 125205 (2022); doi: 10.1063/5.0129134 © Author(s) 2022

**12**, 125205-7

**AIP Advances**

**ARTICLE**

**scitation.org/journal/adv**

was performed in part at the Montana Nanotechnology Facility, an NNCI member supported by NSF Grant No. ECCS-2025391. This work also made use of the University of Utah’s shared facilities of the Micron Technology Foundation Inc. Microscopy Suite sponsored by the College of Engineering, Health Sciences Center, Office of the Vice President for Research, and the Utah Science Technology and Research (USTAR) initiative of the State of Utah.

#### Conflict of Interest

The authors have no conflicts to disclose.

#### Author Contributions

H.D. fabricated the ion pumps with help from M.J., H.L., and H.C.H. H.D., H.-C.H., H.L., C.R.-I., and C.B. developed processes required for fabrication. J.S. designed the ion pumps. P.P. and P.B. developed microcontrollers and interfaces for the assembly. H.D. characterized the devices. C.R.-I. and H.D. performed experiments with cells. G.M. and H.D. performed closed-loop experiments. N.A. and T.N. helped with characterization experiments of the well plate device.

H.D. drafted the manuscript with inputs from H.L., H.-C.H., C.L.-I., P.B., M.G., and M.R. M.R. directed and designed the overall research with M.T., M.L., and M.G.

**Harika Dechiraju**: Investigation (lead); Writing – original draft (lead). **John Selberg**: Investigation (equal); Writing – original draft (equal). **Manping Jia**: Investigation (equal); Writing – original draft (equal). **Pattawong Pansodtee**: Investigation (equal); Writing – original draft (equal). **Houpu Li**: Investigation (equal); Writing – original draft (equal). **Hao-Chieh Hsieh**: Investigation (equal); Writing – original draft (equal). **Cristian Hernandez**: Investigation (equal). **Narges Asefifeyzabadi**: Investigation (equal); Writing – original draft (equal). **Tiffany Nguyen**: Investigation (equal). **Prabhat Baniya**: Investigation (equal); Writing – original draft (equal). **Giovanny Marquez**: Investigation (equal); Writing – original draft (equal). **Cody Rasmussen-Ivey**: Investigation (equal); Writing – original draft (equal). **Carrie Bradley**: Investigation (equal). **Mircea Teodorescu**: Supervision (equal); Writing – review & editing (equal). **Marcella Gomez**: Supervision (equal); Writing – review & editing (equal). **Michael Levin**: Supervision (equal); Writing – review & editing (equal). **Marco Rolandi**: Conceptualization (equal); Supervision (equal); Writing – review & editing (equal).

#### DATA AVAILABILITY

The data that support the findings of this study are available from the corresponding author upon reasonable request.

## Unparsed PDF references

See the supplementary material for Figs. S1–S4 and the supplementary text.

## References (31 total, showing 31)

1. M. Seitanidou, R. Blomgran, G. Pushpamithran, M. Berggren, and D. T. Simon, Adv. Healthcare Mater. **8** (19), 1900813 (2019).
2. A. Williamson, J. Rivnay, L. Kergoat, A. Jonsson, S. Inal, I. Uguz, M. Ferro,
A. Ivanov, T. A. Sjöström, D. T. Simon, M. Berggren, G. G. Malliaras, and
C. Bernard, Adv. Mater. **27** (20), 3138–3144 (2015).
3. A. Zhang and C. M. Lieber, Chem. Rev. **116** (1), 215–257 (2016).
4. M. Berggren and A. Richter-Dahlfors, Adv. Mater. **19** (20), 3201–3213 (2007).
5. M. Jia, J. Kim, T. Nguyen, T. Duong, and M. Rolandi, Biopolymers **112** (7), e23433 (2021).
6. J. Selberg, M. Jia, and M. Rolandi, PloS One **14** (3), e0202713 (2019).
7. H. Chun and T. D. Chung, Annu. Rev. Anal. Chem. **8** (1), 441–462 (2015).
8. D. T. Simon, E. O. Gabrielsson, K. Tybrandt, and M. Berggren, Chem. Rev. **116** (21), 13009–13041 (2016).
9. D. J. Poxson, E. O. Gabrielsson, A. Bonisoli, U. Linderhed, T. Abrahamsson, I. Matthiesen, K. Tybrandt, M. Berggren and D. T. Simon, ACS Appl. Mater. Interfaces **11** (15), 14200–14207 (2019).
10. T. Arbring Sjöström, M. Berggren, E. O. Gabrielsson, P. Janson, D. J. Poxson, M. Seitanidou, and D. T. Simon, Adv. Mater. Technol. **3** (5), 1700360 (2018).
11. J. Isaksson, P. Kjäll, D. Nilsson, N. Robinson, M. Berggren, and A. RichterDahlfors, Nat. Mater. **6** (9), 673–679 (2007).
12. J. Selberg, M. Jafari, J. Mathews, M. Jia, P. Pansodtee, H. Dechiraju, C. Wu,
S. Cordero, A. Flora, and N. Yonas, Adv. Intell. Syst. **2** (12), 2000140 (2020).
13. A. G. Guex, D. J. Poxson, D. T. Simon, M. Berggren, G. Fortunato, R. M.
Rossi, K. Maniura-Weber, and M. Rottmar, Appl. Mater. Today **22** , 100936 (2021).
14. U. K. Udensi and P. B. Tchounwou, Int. J. Clin. Exp. Physiol. **4** (3), 111–122 (2017).
15. C. Svensen, in _Pharmacology and Physiology for Anesthesia_ , 2nd ed., edited by H. C. Hemmings and T. D. Egan (Elsevier, Philadelphia, 2019), pp. 814–835.
16. A. Prindle, J. Liu, M. Asally, S. Ly, J. Garcia-Ojalvo, and G. M. Süel, Nature **527** (7576), 59–63 (2015).
17. G. G. Somjen, Annu. Rev. Physiol. **41** (1), 159–177 (1979).
18. C. Fisch, S. B. Knoebel, H. Feigenbaum, and K. Greenspan, Prog. Cardiovasc. Dis. **8** (5), 387–418 (1966).
19. S. K. Doke and S. C. Dhawale, Saudi Pharm. J. **23** (3), 223–229 (2015).
20. C. Pitsalidis, A.-M. Pappa, A. J. Boys, Y. Fu, C.-M. Moysidou, D. van Niekerk,
J. Saez, A. Savva, D. Iandolo, and R. M. Owens, Chem. Rev. **122** (4), 4700–4790 (2022).
21. M. Jia, L. Luo, and M. Rolandi, Macromol. Rapid Commun. **43** (6), 2100687 (2022).
22. M. Seitanidou, K. Tybrandt, M. Berggren, and D. T. Simon, Lab Chip **19** (8), 1427–1435 (2019).
23. V. A. Pokrovskii and H. C. Helgeson, Geochim. Cosmochim. Acta **61** (11), 2175–2183 (1997).
24. V. M. M. Lobo, A. C. F. Ribeiro, and L. M. P. Verissimo, J. Mol. Liq. **78** (1), 139–149 (1998).
25. C. Li, M. Levin, and D. L. Kaplan, Sci. Rep. **6** (1), 21044 (2016).
26. M. Jafari, G. Marquez, J. Selberg, M. Jia, H. Dechiraju, P. Pansodtee, M. Teodorescu, M. Rolandi, and M. Gomez, IEEE Control Syst. Lett. **5** (4), 1133–1138 (2021).
27. M. Jia, H. Dechiruji, J. Selberg, P. Pansodtee, J. Mathews, C. Wu, M. Levin, M. Teodorescu, and M. Rolandi, APL Mater. **8** (9), 091106 (2020).
28. A. D. Mickle, S. M. Won, K. N. Noh, J. Yoon, K. W. Meacham, Y. Xue, L. A. McIlvried, B. A. Copits, V. K. Samineni, K. E. Crawford, D. H. Kim, P. Srivastava, B. H. Kim, S. Min, Y. Shiuan, Y. Yun, M. A. Payne, J. Zhang, H. Jang, Y. Li, H. H. Lai, Y. Huang, S.-I. Park, R. W. Gereau, and J. A. Rogers, Nature **565** (7739), 361–365 (2019).
29. X. Strakosas, J. Selberg, X. Zhang, N. Christie, P. H. Hsu, A. Almutairi, and M. Rolandi, Adv. Sci. **6** (7), 1800935 (2019).
30. A. Jonsson, Z. Song, D. Nilsson, B. A. Meyerson, D. T. Simon, B. Linderoth, and M. Berggren, Sci. Adv. **1** (4), e1500039 (2015).
31. P. Pansodtee, J. Selberg, M. Jia, M. Jafari, H. Dechiraju, T. Thomsen, M. Gomez, M. Rolandi, and M. Teodorescu, PLoS One **16** (9), e0257167 (2021).
