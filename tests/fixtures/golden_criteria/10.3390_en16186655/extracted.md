---
title: "10.3390/en16186655"
doi: "10.3390/en16186655"
source: "mdpi_pdf"
has_fulltext: true
content_kind: "fulltext"
has_abstract: false
token_estimate: 22187
---

# 10.3390/en16186655

**_energies_**

_Article_

## **LESS Spark Ignition Engine: An Innovative Alternative to the Crankshaft Mechanism**

**Vasileios Georgitzikis**<sup>**1**</sup> **, Dionisis Pettas**<sup>**2**</sup> **, Konstantinos Loukas**<sup>**2**</sup> **and Georgios Mavropoulos**<sup>**3,**</sup> *****

- 1 G-Drill/LESS Engineering, Thessalonikis 30, Agios Ioannis Rentis, GR-18233 Pireaus, Greece; tzikis@gmail.com

- 2 FEAC Engineering P.C., GR-26442 Patras, Greece; dions.pettas@gmail.com (D.P.); konstantinos.loukas@feacomp.com (K.L.)

- 3 Department of Mechanical Engineering Educators, School of Pedagogical and Technological Education (ASPETE), GR-15122 Marousi, Greece

- Correspondence: mavrop@otenet.gr; Tel.: +30-210-2896-956

**Abstract:** In recent years, the internal combustion engine has been the subject of debate mainly concerning its environmental impact. Despite all the discussion it becomes clear day by day that combustion engines will continue to occupy their dominant role over the following decades, especially in the mid- and large-size power spectrum ranges and retain a large share of the market in the smallersize segment of their application. In this context, in the present paper, a novel engine kinematic mechanism is introduced, which converts rotary to reciprocating motion, and aims to become a potential replacement for the traditional crankshaft mechanism of piston engines. Following a description of the fundamental principles of the new design, we detail the main problems with the application of the new design in the first prototype SI engine and the actions and improvements implemented to overcome them. The actual measurement data from basic engine performance parameters are provided and evaluated, leading to conclusions and decisions for further action which should be implemented in the next improvement steps. Overall, the new SI engine, implementing the novel kinematic mechanism, seems to be quite promising especially in hybrid automotive applications, a fact that encourages the implementation of further improvement plans.

**Citation:** Georgitzikis, V.; Pettas, D.; Loukas, K.; Mavropoulos, G. LESS Spark Ignition Engine: An Innovative Alternative to the Crankshaft Mechanism. _Energies_ **2023**, _16_, 6655. https://doi.org/10.3390/en16186655

Academic Editor: Anastassios M. Stamatelos

Received: 26 July 2023 Revised: 2 September 2023 Accepted: 11 September 2023 Published: 16 September 2023

**Copyright:** © 2023 by the authors. Licensee MDPI, Basel, Switzerland. This article is an open access article distributed under the terms and conditions of the Creative Commons Attribution (CC BY) license (https:// creativecommons.org/licenses/by/ 4.0/).

**Keywords:** internal combustion engine; novel kinematic mechanism; camless engine; rotating piston

## **1. Introduction**

The internal combustion engine has recently become the center of controversial discussion concerning its environmental impact [1–7]. The subject is quite extensive and presents different aspects of great interest. Without going into further details, it is quite interesting and it should be noted that the largest part of this discussion, and the information available in the open literature, usually comes from scientists specialized in almost any other field, irrelevant to mechanical engineering. Suddenly, it seems that engineer specialists who have spent their entire lives studying combustion and engine development and improvement are no longer the people to be questioned about an engine’s performance, and the actual current status of its pollutant emissions.

Despite the above issue, today, with the help of several remaining voices [8,9], it is apparent that internal combustion engines will continue to be the prime mover in marine transportation [10] and maintain a large share in energy production. In the automotive sector it is clear that despite all efforts towards electrification, it currently seems highly unlikely that the EU target of 2035 will be reached, and a new, realistic strategy is urgently needed [11–14]. Nonetheless, in this new strategy, hydrogen and e-fuels are expected to gain a central role, if political organizations seek realistic targets [11–14].

Therefore, engine research and improvement activities are still urgently being carried out in a variety of critical areas [15]. Today’s complex and advanced engine designs, after

_Energies_ **2023**, _16_, 6655. https://doi.org/10.3390/en16186655

https://www.mdpi.com/journal/energies

2 of 36

_Energies_ **2023**, _16_, 6655

a century of continuous improvement, still need further and intensive research efforts, mostly related to performance improvement and, as equally, emission reduction [16–18].

However, the previous areas mentioned are only one aspect of engine development. Different engine designs are currently under investigation, aiming to offer solutions to “old” technical problems. In [19], a novel internal combustion engine is introduced, which may use a nano-magneto-rheological mechatronic commutator that may replace the crankshaft and connecting rod (conrod) mechanisms. The new engine design has only one moving part; namely, the piston–rod assembly; and claims to present a much higher power density than its conventional counterpart. An additional advantage is that it can burn a large variety of liquid–fossil, as well as gaseous–nitrogen fuels, and it has a high potential for emission reduction.

In [20], a new kinematic concept design for a VCR is proposed considering the vertical second harmonic order acceleration. Specific six-link kinematic chains, were proposed as candidate VCR engine mechanisms, and their initial dimensions and design specifications were determined. The methodology can be used to determine the dimensions and mass distribution of links, when applied in the automotive industrial applications. The authors of [21] have introduced the novel solution of a mechanism used for an engine with a variable compression ratio VCR, and compared the results with those from an engine with a classical mechanism. The proposed mechanism allowed a 25% increase in piston stroke, compared with a classical VCR design.

The authors in [22] have proposed a novel electromechanical actuation system, which offers an appropriate solution for cam-switching in high-performance internal combustion engines. Simulations performed in realistic engine conditions have demonstrated that the proposed mechanism is able to perform the required movements within a reasonable safety margin under nominal and off-nominal conditions.

In [23], a novel patented mechanism is presented, which uses a rack- and-pinion assembly connected to a crank-rocker four-bar mechanism instead of the connecting rod. It is claimed that the new mechanism eliminates all the negative friction loss effects of the side-thrust load, and the piston-slap problems encountered in existing conventional internal combustion engines. As a result, the authors claim that the new design improves engine performance and eliminates the noise generated by conventional slider-crank mechanisms.

It is apparent that previous design improvements are being implemented in parallel with advancements in a variety of aspects concerning engine performance and emission reduction. An extensive overview of the current status, and future prospects of ICE’s in the transportation sector is provided, among other aspects in [24]. The significant progress in almost all important engine subsystems is apparent: novel combustion systems, hybrid applications, emission reduction subsystems, fuels and injection systems, to name but a few, are accepting a significant boost forward, in an effort to fulfil today’s performance demand, and the strict environmental regulations.

In this context, the current work presents an introduction to a novel kinematic mechanism with the code name “LESS”, which is aiming to replace the traditional crankshaft mechanism in an SI combustion engine. The basic initial design of the new mechanism is initially presented followed by an overview of the parameters that need to be reevaluated and optimized as a result of the simulation work in the initial prototype. In the second part of the work, the basic performance measurements are presented from an actual SI engine manufactured and operated incorporating the new mechanism, after the application of the most important design enhancements. The discussion about the progress made since the first prototype leads to conclusions about the next steps for improvements, in an effort to achieve the application of the new design concept in the field.

## _2.1. Basic Overview of LESS-1 SI Engine Prototype_

The initial prototype LESS Internal Combustion Engine (hereafter referred to as LESS-1) is a 2-cylinder spark ignition (SI) ICE, with a total displacement of 433 cc (216.52 cc

3 of 36

_Energies_ **2023**, _16_, 6655

per cylinder). The cylinder bore is 82 mm, while the piston stroke is 41 mm. Its compression ratio is 9.66, and it occupies 2 valves per cylinder; the intake valve has a diameter of 32 mm, and the exhaust valve has a diameter of 26 mm. The intake and exhaust ports in the cylinder head as well as the intake and exhaust pipes, have a 30 mm diameter.

Fuel is supplied via a common 30 mm diameter carburetor, which is mounted at the beginning of the intake pipes. The engine is designed to run in a horizontal layout and, as a result, the intake and exhaust pipes are also positioned horizontally, their design and placement resulting in different lengths between the two cylinders.

Finally, the ignition system uses a common ignition coil for the 2 cylinders and a distributor for the corresponding spark plug. In Figure 1a,b the external overview of the first prototype LESS-1 engine is displayed.

<!-- Start of picture text -->
(a)<br>(b)<br><!-- End of picture text -->

**Figure 1.** The side (**a**) and front (**b**) view of the prototype LESS-1 SI engine.

It should be mentioned that, due to the special design of the new mechanism, the LESS-1 engine concludes a full cycle during one revolution of the engine shaft, unlike a conventional 4-stroke engine which needs 2 revolutions of its shaft (otherwise 720 deg CA) to conclude a full thermodynamic cycle. In other words, using the new design mechanism, a 4-stroke cycle takes place in 360 degrees, as opposed to the traditional crankshaft mechanism where a full cycle needs 720 degrees to be completed. Accordingly, compared to the traditional crankshaft mechanism, the proposed engine design produces twice the torque of the conventional one.

## 2.2.1. Basic Description of the Mechanism

LESS is a patented innovative mechanism that converts rotary to reciprocating motion and vice versa. It is a replacement for the traditional crankshaft mechanism, which is found in essentially every reciprocating ICE, as well as other devices such as reciprocating pumps and compressors.

In order to understand the operating principle of the LESS mechanism, one should consider a simple cam-roller mechanism, set on a 2D plane, where the cam surface is a sine wave, as shown in Figure 2, where the green roller sits atop a blue sinusoidal cam profile.

4 of 36

_Energies_ **2023**, _16_, 6655

**Figure 2.** A 2D sinusoidal cam profile (blue) with a roller (green) following a sinusoidal trajectory (black) as it moves across the cam profile.

Suppose the roller is somehow forced to be kept in continuous contact with the sinusoidal cam and it is forced to move along the x-axis. Then, the roller will necessarily reciprocate on the y-axis, and its resulting trajectory will follow the sinusoidal equation of the cam, as shown via the black line in Figure 2.

Instead of using a roller, it is possible to have two 2D cams that slide on each other. However, if one were to simply use two sinusoidal cams, then the resulting trajectory would be a rectified sine, as shown in Figure 3.

**Figure 3.** Two 2D sinusoidal cam profiles, and the trajectory that the top (blue) part will follow as it slides across the bottom (red) cam profile.

In order to achieve a true sinusoidal trajectory using 2 sliding cams, the cam profiles require a very specific, mathematically defined geometry, which is a unique patented aspect of the LESS mechanism. More specifically, the cams need to be designed such that the valleys of the cam profile and the peaks of the cam profile have a size ratio of 3:1. With careful selection of the geometry, it is possible to create a sliding cam pair with a harmonic sinusoidal trajectory, as seen in Figure 4.

**Figure 4.** Two 2D LESS cam profiles, and the sinusoidal trajectory that the top (blue) part will follow as it slides across the bottom (red) cam profile.

This design still suffers from a major drawback, which is the aforementioned need to keep the two components in constant contact through some method. This can be achieved with the use of a third component on top of the blue one of the previous design, and the addition of the same LESS cam on the top side of the blue component. The resulting 3-component mechanism comprises two pairs of LESS cams, i.e., the top-middle pair and the middle-bottom pair, as seen in Figure 5.

5 of 36

_Energies_ **2023**, _16_, 6655

**Figure 5.** A complete reciprocating LESS mechanism on a 2D plane, where the middle (blue) part reciprocates and rotates between the two external parts.

In this case, as the middle (blue) part moves on the x-axis, it is forced by the top LESS cam to move downwards, following the same aforementioned sinusoidal trajectory. It cannot be detached from the top part, because the bottom (red) part is also in constant contact with its bottom side. After the middle part reaches the lowest point of the sinusoidal trajectory, the roles are reversed, and the bottom part pushes it upwards, whereas the top part keeps it in place. Therefore, the middle part can only follow the common trajectory, as it is restrained by the two LESS cams on its top and bottom surfaces, and the opposing LESS cam surfaces of the top and bottom parts.

The final step will be to convert these theoretical 2D planar cams into a real mechanism. By taking the aforementioned 2D cam profiles and wrapping them around a cylinder, and extruding them into annular cam geometries, the mechanism of Figure 6 is created.

**Figure 6.** A real-world, annular implementation of the LESS mechanism, where the middle part (white) can rotate and reciprocate between the two external (red) stators.

It is easy to see that, if the middle (white) part of this mechanism is forced to rotate around the common axis, it will also be forced to reciprocate by the two red stators on its opposing sides.

Furthermore, it is possible to constrain the movement of the components, so that the middle (white) ring can only reciprocate but it cannot rotate with the use of keyways and keys. The red rings can also be constrained so that they can only rotate, via connecting them to a common shaft, which is itself axially constrained by thrust bearings. The end result is the mechanism in Figure 7.

6 of 36

_Energies_ **2023**, _16_, 6655

**Figure 7.** A 3-piece LESS mechanism where the reciprocating and rotating components of the complex movement are isolated.

Finally, by connecting a piston (green) to the reciprocating white part, as shown in the half-section view in Figure 8, one arrives at a complete alternative to the crankshaft mechanism, the basis of a reciprocating ICE.

**Figure 8.** A complete mechanism for converting the reciprocating movement of a piston into rotational movement of the shaft.

In this final design, the rotation of the yellow axle results in the rotation of the red LESS top and bottom parts, which, in turn, results in the reciprocation of the middle white LESS part and the green piston, and vice versa; therefore, a complete alternative to the traditional crankshaft mechanism is achieved.

The two stators of the LESS mechanism are constructed from tool steel and the reciprocating component is constructed with hard anodized 7075-T6 aluminum, so as to reduce the inertial forces of the reciprocating mass.

## 2.2.2. Theoretical Pros/Cons

The LESS mechanism shows some promising theoretical pros, which is why its analysis and understanding has scientific value. To complete a full cycle of a four-stroke engine, four piston movements (strokes) are required. At this point, we should note that it is of great interest that the LESS mechanism performs four piston stokes in one revolution of the drive gear/shaft, unlike conventional engines, where the crankshaft needs two revolutions to complete one engine cycle.

One additional advantage compared to the traditional slider-crank mechanism is its sinusoidal trajectory, as it is symmetric, and it does not have secondary order imbalances. This is shown in Figure 9a–c, where the graphs show the position (piston displacement), velocity, and acceleration of two comparable engines, with one using a traditional crankshaft, and one using the LESS mechanism.

7 of 36

_Energies_ **2023**, _16_, 6655

<!-- Start of picture text -->
(a)<br>(b)<br>(c)<br><!-- End of picture text -->

**Figure 9.** Piston displacement (**a**), velocity (**b**), and acceleration (**c**) of the conventional crankshaft and LESS mechanisms.

It is easy to see that the velocity and acceleration in the case of the LESS mechanism are sinusoidal and, therefore symmetrical, with no higher-order harmonic imbalances, such as the ones seen between the top and bottom peaks of the crankshaft acceleration curve (the dotted line of the bottom graph, Figure 9c).

Another advantage of the LESS mechanism is that, due to its counter-balanced points of contact, there are no side forces on the piston and, therefore, there is no friction between the piston and the cylinder wall.

Finally, one important advantage of the LESS mechanism is the lower number of components needed which reduces its complexity in comparison with a conventional combustion engine. In addition the maintenance cost of an engine incorporating LESS is expected to be lower than the respective one for a conventional engine.

However, the mechanism also has significant potential disadvantages. With it being a new and unproven design, there is a significant amount of research and development that needs to be performed, and the work showcased in this paper is just the beginning of a long and arduous effort.

During the operation tests of the LESS prototype, the steel stator rings did not presented any wear or deformation. In contrast, the middle reciprocating aluminum component have presented signs of wear, which, in several cases, were significant. In the next steps

8 of 36

_Energies_ **2023**, _16_, 6655

of LESS engine development, we consider the replacement of aluminum material with steel with an optimum specification, to successfully match the operating engine requirements.

The geometry and design of the LESS mechanism presents a challenge in terms of the manufacturing difficulty and cost. While the design lends itself to a less complex, smaller engine, with fewer moving parts, the LESS cam itself is a part with a complex geometry, and manufacturing it at volume and low cost could be a significant challenge for production engineers.

## _2.3. Main Engine Geometric Characteristics_

The main characteristics of the engine geometry are shown in Figure 10. As mentioned above, the engine under discussion does not occupy a conventional crankshaft, as it is replaced by the LESS main mechanism, as displayed in Figure 10, component (6).

**Figure 10.** Representation of the geometry, showing the most important parts of the engine: overview of the whole engine geometry (**a**) and details of engine cylinder area (**b**).

Unlike a conventional crankshaft mechanism, the rotary movement of the gear, combined with the geometry of the LESS sliding surfaces, imposes a particular movement to the piston, as shown in Figure 10, part (5), as the gear, during its rotation process, does not perform a relatively sinusoidal motion, but there is an upper and lower limit, where its position (and with it, the position of the piston) remains constant for about 12 degrees.

This kinematic behavior in the piston is a significant difference in the LESS configuration in contrast to the classic piston–rod–crankshaft mechanism. This characteristic provides new possibilities for the improvement of engine combustion and, consequently, the engine performance, and it appears both in the top dead center (TDC) and the bottom dead center (BDC) of the piston movement.

Another important feature is that the LESS four-stroke engine concludes a complete four-stroke engine cycle in one rotation of the gear (360<sup>_◦_</sup>), in contrast to the conventional kinetics achieved with the crankshaft mechanism, which needs two full rotations (720<sup>_◦_</sup> CA). This difference is due to the special design of the mechanism used for transferring the movement of the piston to the output engine shaft.

Nevertheless, in order for the results of the present prototype engine to be compatible with the rest of the literature on internal combustion engines, a convention was set that one engine cycle of the LESS engine corresponds to a 720<sup>_◦_</sup> rotation angle, taking into account all the necessary conversions, as the speed of rotation is calculated to be twice the actual, while the torque is calculated to be half the actual, as the work produced during a complete engine cycle corresponds to two shaft revolutions, while it is actually produced in one. Additionally, the clearance volume of the combustion chamber is defined as the volume between the inner wall of the engine head (2) and the upper surface of the piston (5).

In the case of the prototype LESS-1 engine, the clearance volume of the cylinder equals 25.0 cm<sup>3</sup>, and its displacement volume is 216.52 cm<sup>3</sup>, which results in a total cylinder volume of 241.52 cm<sup>3</sup>. The compression ratio of the engine derived from the above figures, is CR = 9.66. A list of the basic engine geometric characteristics is provided in Table 1.

9 of 36

_Energies_ **2023**, _16_, 6655

**Table 1.** The basic geometric characteristics of the LESS-1 prototype engine.

|Axial clearance of combustion chamber|5.24 mm|
|---|---|
|Clearance volume|25 cm<sup>3</sup>|
|Cylinder bore|82 mm|
|Piston stroke|41 mm|
|Cylinder displacement volume|216.52 cm<sup>3</sup>|
|~~Compression ratio~~|~~9.66~~|
|~~Inlet valve diameter~~|~~38 mm~~|
|~~Inlet valve seat angle~~|~~45~~<sup>_~~◦~~_</sup>|
|Inlet valve lift|7.719 mm|
|Exhaust valve diameter|31 mm|
|Exhaust valve seat angle|45<sup>_◦_</sup>|
|Exhaust valve lift|7.719 mm|

## _2.4. Piston Kinematics_

Figure 11a shows the kinematics of the piston as a function of the rotation angle of the LESS mechanism, respectively. The top dead center (TDC) corresponds to the position 0, while the bottom dead center (BDC) corresponds to the position _−_ 41 mm. In addition, Figure 11b presents the LESS mechanism with a geometry corresponding to the specific piston movement.

**Figure 11.** Piston motion (mm) vs. angle (deg) during a full cycle of the LESS-1 engine. The upper and lower dotted lines represent the positions of the TDC and BDC, respectively (**a**), and the LESS mechanism corresponding to the same kinematics (**b**).

Figure 12 displays the path of the inlet and exhaust valves during an engine cycle as a function of the angle of rotation of the LESS mechanism. As for the inlet valve, the kinematics dictates its opening at 692<sup>_◦_</sup> of the previous cycle, which corresponds to _−_ 28<sup>_◦_</sup> of the completed cycle, and its closing at 208<sup>_◦_</sup> of the cycle, respectively.

In total the inlet valve remains open for 236<sup>_◦_</sup> while its maximum lift is 7718 mm at 90<sup>_◦_</sup>. Accordingly, the exhaust valve also remains open for 236<sup>_◦_</sup>, opens at 512<sup>_◦_</sup>, and closes at 28<sup>_◦_</sup> in the next cycle, while its maximum lift is 7719 mm at 630<sup>_◦_</sup>.

Here, it is worth noting that, for both the inlet and exhaust valves, the duration in which both valves are open (valve overlapping) is based on the common standards of the ICE industry, as applied to the cases of valve lift greater than 0.050<sup>_′′_</sup>, i.e., 1.27 mm. In our case, according to the previous definition, the inlet valve is considered open from 714.26<sup>_◦_</sup> in the previous engine cycle, to 186.08<sup>_◦_</sup> in the current cycle. Consequently, for the exhaust valve, these values are from 534.61<sup>_◦_</sup> in the current cycle, to 6.70<sup>_◦_</sup> in the next engine cycle. Both valves, therefore, have an “actual” opening duration of ~192<sup>_◦_</sup>.

10 of 36

_Energies_ **2023**, _16_, 6655

**Figure 12.** The valve motion (mm) during one cycle of the LESS-1 engine. The blue line corresponds to the inlet valve while the red line corresponds to the exhaust valve displacement.

## _2.5. Valve Kinematic System_

In the LESS prototype, the valves are controlled by a disc-type camshaft, which is attached to the engine’s central shaft, as shown below in Figures 13 and 14.

**Figure 13.** The LESS-1 engine and its drive system for the main shaft.

**Figure 14.** A detail of the camshaft and the valve drive and control system of the LESS-1 prototype.

11 of 36

_Energies_ **2023**, _16_, 6655

As shown in the next Figure 15, the disk consists of two rings (in yellow and green color), each with a different diameter. Each ring has a protrusion, which acts as a cam. On top of the disc, 4 levers/cocks are located (1 for each valve), and they stay continuously in contact with it, and control the 4 valves (2 in each cylinder). The 2 rocker arms on the left-hand side of Figure 14 above are in contact with the inner (green) ring, and the 2 on the right-hand side are in contact on the outer (yellow) ring.

**Figure 15.** A detail of the disk-type camshaft of the LESS-1 prototype. The driving profiles for the two valves of each cylinder are distinguished on each disk.

As the main engine shaft rotates, the rings rotate with it, causing the exhaust valve to open and close first, and then, with a 90-degree phase difference (corresponding to one stroke, or 180 deg of the conventional piston-crank mechanism), the intake valve of the same cylinder. Additionally, the two camshaft rings are positioned with a 90-degree phase difference between them, corresponding to a 180-degree phase difference between the two cylinders of the conventional crankshaft 4-stroke combustion engine.

As the intake and exhaust valves of each cylinder are controlled via the same cam, they have the same kinematics. The only thing that changes is their phase difference, which, as has been mentioned is 90 deg (equivalent to 180 deg of the conventional crank–piston mechanism).

## 2.6.1. Engine Performance

In the first stage of the work, the whole engine system was simulated using the Amesim 2022.1 commercial software [25], approaching the system as an arrangement consisting of several individual processes. Specifically, Amesim 2022.1 simulates independently each individual engine process or subsystem (0 or one-dimensional simulation). Each engine subsystem is represented via a mathematical model that characterizes the respective operation. This can be either a system of ordinary differential equations, one-dimensional simulation, analytical expressions, or non-linear algebraic equations. These objects can be connected in series and interact to simulate the overall engine system.

Due to the nature of the simulation, the Amesim package can quickly implement alternative scenarios, and predict how they will affect the rest of the engine systems. It is interesting that Amesim has a registered library for describing internal combustion engines. Through using this, the engine is decomposed into individual smaller parts which are approximated using numerical models, taking into account both the mechanical movement of the engine and its physicochemical behavior. In order to simulate the most important combustion engine processes, the Amesim software has incorporated the CFM-

12 of 36

_Energies_ **2023**, _16_, 6655

1D model [26] for combustion, heat release, and combustion cycle variability (CCV). The most important theoretical aspects will be presented in the next section.

In the second stage of development, a commercial fluid dynamics software was used to achieve a detailed 3D simulation of the physical and chemical complex engine processes. The results of this second stage will be presented in a second stage of the work, due to space limitations. In Figure 16, we present the layout of different processes, as applied in the Amesim 2022.1 simulation software.

**Figure 16.** The layout of different processes as applied in the simulation software.

For a better understanding of the whole engine system, objects from the software library are assigned the same color. Thus, objects of one-dimensional engineering models are indicated in green, objects of the “signals and control” library in red, and the internal combustion engine library objects are marked in blue.

The appearance of the multiple connections shown in the system is used in order to achieve the best possible approximation of the actual geometry of the pipelines, taking into account the changes in their curvature, and similar constraints of the actual engine system. Additionally, the routing of pipes at the inlet and outlet engine systems is interrupted to install pressure and temperature sensors (the presence of the sensors does not affect the numerical results but, rather, shows the point where the respective variables were actually recorded). These values are intended, among others, to be used as boundary conditions in the upcoming 3D simulation model.

Particular attention was paid to the simulation of piston kinematics. In the case of the LESS-1 engine, the movement of the piston does not follow the standard kinematics of the literature but, instead, follows the variation provided in Figure 11. In particular, thanks to the modular approach offered by Amesim software, it was able to decouple the movement of the piston from the geometric characteristics and the resulting kinematics of a crank, and connect the position of the piston vs the time in our own user-defined way. The actual piston movement is approximated through loading the respective data from a file, using a

13 of 36

_Energies_ **2023**, _16_, 6655

2D table, where the second column of the table is the position of the piston relative to the angle (0–720<sup>_◦_</sup>).

## 2.6.2. Basic Principles and Description of CFM-1D Combustion Model

The basic module in the simulation outline of Figure 16 is the CFM-1D combustion model. This model is used to represent combustion in a thermal-pneumatic chamber with variable volume, pressure dynamics, and heat exchange from the boundaries of the combustion chamber. The rest of the components in Figure 16 represent the secondary engine subsystems, piping connections, and measurement and control instruments.

In order to simulate engine combustion, the CFM-1D model distinguishes two zones: the unburnt fuel–air mixture zone, and the burnt gas zone, which are separated by a flame front propagating from the burnt gases towards the fresh mixture. The chemical reactions of fuel oxidation occur in a very thin layer (the flame front) compared to all scales of the turbulent flow and post-flame chemistry taking place in the burnt gases. The model is based on the next main assumptions:

- The gaseous mixture consists of 15 species, and is considered as perfect gas;

- _•_ The mixture composition is considered homogeneous in each zone (fresh and burnt gases);

- Fuel can be found in both liquid and gaseous phases inside the combustion chamber;

- _•_ The cylinder pressure is assumed to be the same in both the burned and unburned zones;

- Each zone is characterized by its mass, volume, composition, and temperature;

- The turbulent kinetic energy field is assumed to be uniform inside the cylinder volume. The calculation of heat release [27,28] is based on the enthalpy balance inside the

- combustion chamber:

where _V_ is the cylinder volume, _h_ is the mass enthalpy, _m_ is the enclosed mass and _p_ is the pressure which is linked to the mean temperature _T_ via the perfect gas law. The last term of Equation (1) refers to enthalpy exchanges at the inlets and outlets (valves, the injector). _Qwall_ corresponds to heat losses at the walls, which are described with the Woschni model or another similar heat-loss model. _Qcomb_ is the heat released through combustion processes.

The above assumptions allow us to determine the heat release resulting from the computations of a mean flame surface, and flame front wrinkling induced by turbulence.

The fuel consumption rate throughout the flame front mainly depends on the fresh gas properties, as well as on the turbulent flame surface St, which is calculated as the product of the mean surface Sm and the flame front wrinkling factor (_Ki_), which may be determined as follows:

- The mean surface Sm changes with the centered hemisphere expansion between the spark plug and the cylinder walls. In order to account for different engine geometries, Sm may be tabulated as a function of the burned gas volume and the piston position;

- The flame wrinkling factor _Ki_ may be estimated either via a physical 0D equation, or via an empirical algebraic correlation, depending on the rest of the parameters chosen. A simple way to compute the flame wrinkling is through the use of a classical Damköh-

- ler’s formulation based on an equilibrium assumption for _Ki_ [26]:

where _u_<sup>_′_</sup> is the instantaneous velocity fluctuation, Γ is the efficiency function of the turbulent flow on the flame strain, _C_ is a modelling constant, _Sc_ is the Schmidt number, _rbg_ is

14 of 36

_Energies_ **2023**, _16_, 6655

the current mean flame radius and _g_ is a function accounting for the laminar-turbulent transition of the flame front.

where _L_ is the distance between the piston and the cylinder head, and _ωeng_ is the engine speed in rad.s<sup>_−_1</sup>. _Ntumble_ is the tumble number at IVC, which corresponds to an initial condition for the compression stroke.

Using this turbulence approach, the model was able to account for the combustion cycle variability (CCV) at the given engine operating conditions. The sources of CCV accounted for are related to the stochastic properties of turbulence, as well as to the thermochemical properties of the mixture.

The losses through the cylinder wall are computed via correlations established and tested for internal combustion engines, such as those of Woschni, Eicheilberg, or Annand.

Based on the heat release rate, the CFM model can predict the occurrence of engine knock, as well as the knock intensity. Ignition delay is calculated via a simplified Arrhenius correlation, or it may be read in an ignition delay table generated via detailed chemistry computations.

The CFM model accounts for the mixing of three gases inside the combustion chamber:

- Gas 1: air

- Gas 2: fuel

- Gas 3: combustion gas

The combustion chamber considered includes 11 ports which may communicate with various Simcenter Amesim submodels. These ports are the following:

Port 1: Gas losses due to blow-by (mass, enthalpy transfer); Port 2: Mechanical transmission towards crank (piston force, speed. displacement); Port 3: Heat transfer over piston top; Port 4 Heat transfer through cylinder walls; Port 5: Heat transfer through cylinder head; Port 6: Gas exchange through the exhaust valve (mass, enthalpy transfer); Port 7: Direct fuel injection (mass, enthalpy transfer); Port 8: Gas exchange through the inlet valve (mass, enthalpy transfer); Port 9: Engine spark (spark advance); Port 10: Port for co-simulation purposes (variables used in engine control); Port 11: Communication of the current crank angle and engine speed.

This combustion chamber is defined for spark ignition engines. It could be used either for a port fuel injection or a direct injection engine.

2.6.3. Engine Dynamics, Friction, and Lubrication

A detailed model of the friction losses that develop between the contact surfaces of the novel LESS mechanism was developed during the R&D phase of the prototype mechanism. Due to the extent and significance of this subject, a detailed reference guide to the model and its results will be presented in a future paper. A brief reference to the main findings and the challenges that lie ahead, in an effort to improve the prototype mechanism, is given hereafter.

The detailed model was developed by the project team involved in the prototype engine development, in order to provide a preliminary estimation of the friction losses of the new mechanism, and its lubrication characteristics. In order to reduce friction loss, an

15 of 36

_Energies_ **2023**, _16_, 6655

effective lubrication system that ensures that hydrodynamic lubrication is developed at all, or at least at the majority of the contact points of the mechanism is required.

The developed numerical model is capable of determining the contact points of the meshing surfaces for any given profile of the LESS components. Based on this calculation, a second model processes the load distribution between the contact points at every stage of the combustion cycle. Via determination of the loads at each contact point, the contact pressures can be calculated; these are essential to any study regarding lubrication. Given the contact pressures, the geometrical parameters of the meshing surfaces, and the sliding velocities, which are also calculated via the numerical model, an initial investigation can be carried out regarding the friction losses, based on the Stribeck curves published in the literature.

The model requires two main inputs: the pressure distribution on engine piston (cylinder pressure diagram) and the geometry of the LESS mechanism and, specifically, the profile of the meshing surfaces. The calculation process comprises three distinct parts:

- Calculation of the contact points of the meshing LESS profiles at each point of the profile during engine operation;

- Calculation of the load distribution between the contact points;

- Calculation of the pressure profiles and the friction forces between the LESS profiles.

An example result for the model output is presented in Figure 17a–c. It displays the distribution of forces and torque between the components of the LESS mechanism for a <u>specific case study.</u>

<!-- Start of picture text -->
(a)<br>(b)<br>(c)<br><!-- End of picture text -->

**Figure 17.** The distribution of forces acting at different directions on the LESS profile. The vertical force in the direction of the cylinder axis (**a**), the horizontal force (**b**), and the total torque (**c**) due to the horizontal force acting on the LESS profiles.

16 of 36

_Energies_ **2023**, _16_, 6655

Based on the normal forces developed at the contact points of the LESS profiles, the contact pressures can be calculated per contact point, according to Hertz theory. The magnitude of the contact pressures has great significance for the LESS mechanism, as they dictate the strength requirements of the components and they directly affect the amount of wear, and the friction losses.

This is precisely the problem that was identified as the main issue for the engine, and as the point of focus for the near-future R&D. It seems as if, under the given operating conditions, the load on the LESS profiles (as a result of the force acting on the piston that is then propagated to the LESS mechanism, and distributed to the contact area) becomes too high, and results in a loss of hydrodynamic lubrication and, therefore, increased friction and wear.

In particular, the sliding LESS profiles operate under a hydrodynamic regime during most of the engine cycle, but there is an area +/ _−_ 50 degrees around the TDC where the contact pressure becomes high enough, and the velocity low enough, that the lubricant film is reduced to lower than the height of the asperities, and we have mixed lubrication, high friction, and wear.

In order to obtain an accurate model of the lubrication phenomena of the novel LESS mechanism, it was deemed necessary to develop a 2-D lubrication model in polar coordinates. The governing equations are the Navier-Stokes equations. Through the use of certain assumptions, the Navier-Stokes equations are reduced to:

The developed model was generalized for any given topology of the two surfaces as a function _g_ (_θ_) and _f_ (_θ_) for the fixed and moving part of the LESS, respectively. For the calculation of the required film thickness at each contact point, a convergence process was applied. After the calculation of the radial and tangential velocity, and the integration of the continuity equation, a modified Reynolds equation can be derived:

where _h_. is the squeeze velocity of the film thickness at each contact point, and

Equation (7) is a partial differential equation that can be solved with the implementation of the finite element method. Further details of the developed model and its results will be presented in a separate publication by the LESS development project team.

The following Figure 18 presents the initial results from this tribological R&D work to solve the lubrication issues in the design. It is confirmed that, in the area +/ _−_ 50 degrees around the TDC, the lubricant film is reduced to lower than the height of the asperities, and we have mixed lubrication, a high friction coefficient, and wear.

A further analysis of modifications to the LESS profiles is needed in the upcoming steps of development, to ensure that the contacting surfaces operate under hydrodynamic lubrication regime across the whole angle of rotation, and solve the issue.

17 of 36

_Energies_ **2023**, _16_, 6655

**Figure 18.** The distribution friction coefficient for two different surface geometries of LESS profiles.

## _2.7. Experimental Measurement Layout_

To meet the needs of the present engine development, an extensive experimental measurement series was performed, in a layout developed specifically for this purpose. Using this layout, we recorded measurements from the initial stage of engine development, namely the LESS-1 prototype, as well as from the improved prototype engine version, mentioned hereafter as LESS-2. It should be mentioned, at this point, that, after examining the results of the simulation of the LESS-1 engine, we applied important changes to the initial engine layout; namely, a vertical layout and an improved intake piping system; in such a way that the performance of the LESS-2 engine was improved significantly, in comparison with its predecessor.

The experimental measurement of the engine operating data was performed using the Plex Combustion Analysis software from the Plex tuning company. The software was used for the measurement and recording of all the operational parameters of the engine, the combustion analysis, the calculation of additional values, and the drawing of conclusions, after special parameterization and analysis. In particular, special adjustments were made to the software, so that it could calculate the most important combustion parameters, taking into account the special and unique kinematics of the LESS mechanism.

In addition, a series of screens with special layouts and graphs were created, to monitor the acquired quantities, while some mathematical models were also created to calculate additional quantities from the basic engine measurement data. The adjustment and control of the basic parameters of the engine control unit (ECU) during tests and measurements, and the additional recording of all secondary engine parameters, were performed using PCLink G4X software. It should be noted that all the measured engine data are were sent to the Plex PCA-2000 recorder via CAN bus, and were additionally recorded there, as well.

Figures 19 and 20 present two key screens, which, among others, were used in the Plex Combustion Analysis.

18 of 36

_Energies_ **2023**, _16_, 6655

**Figure 19.** PC Link G4X configuration screen.

**Figure 20.** PC Link G4X configuration screen.

## 3.1.1. Effect of Engine Speed and Ignition Timing

Initially, a comparison was made concerning the effect of the ignition timing on the cylinder pressure variation for different engine speeds—namely, at 1000, 3600, and 7200 rpm. The simulation results are shown in Figure 21. It is observed that, when the ignition timing is advanced, the maximum cylinder pressure is increased significantly for all cases of engine speed. This result is expected, and it is in agreement with similar

19 of 36

_Energies_ **2023**, _16_, 6655

findings in conventional SI engines. As the ignition timing is advanced away from the TDC, there is time available for the oxidation to take place, resulting in an increase in the maximum pressure inside the cylinder.

**Figure 21.** The effect of the ignition timing on the cylinder pressure for an engine speed of 1000 rpm (**a**), 3600 rpm (**b**), and 7200 rpm (**c**).

On the other hand, the ignition timing for a specific engine speed should be controlled and regulated at an optimal value, in order for the engine to reach maximum power and efficiency. Therefore, the optimal ignition timing for each operating condition of an engine is the one where the maximum brake torque (MBT) is achieved.

From the results of Figure 21, it can also be concluded that the variation in the ignition timing for a specific engine speed does not alter the angle of the appearance of maximum pressure. This angle depends, on the other hand, on the engine speed, and it is retarded as the engine speed increases, in order to reach the engine MBT, as is also confirmed via the values in Figure 21a–c.

20 of 36

_Energies_ **2023**, _16_, 6655

## 3.1.2. Gas Exchange Process

Figure 22 presents the variation in the cylinder pressure and the temperature at the engine inlet pipe (a, d), cylinder (b, e), and exhaust pipe (c, f) during an engine cycle for an ignition advance 45<sup>_◦_</sup>, and an engine speed of 3600 rpm.

**Figure 22.** The variation in pressure and temperature at the engine inlet pipe (**a**, **d**), cylinder (**b**, **e**), and exhaust pipe (**c**, **f**) during an engine cycle for an ignition advance of 45<sup>_◦_</sup>, and an engine speed of 3600 rpm.

It can be observed that the pressure in the engine inlet and exhaust pipe is varied by 1.017 bar and 1.04 bar, respectively, which is reasonable, given that the engine is a naturally aspirated one. In Figure 22a,d, the largest pressure fluctuations in the inlet pipe are observed in the interval (0<sup>_◦_</sup> < θ < 180<sup>_◦_</sup>), where the air-fuel mixture is introduced into the cylinder, while, for θ > 180<sup>_◦_</sup>, small pressure oscillations are created that decay exponentially in time, due to pressure dynamic effects.

Likewise, in the case of the exhaust pipe, in Figure 22c,f, the largest fluctuations are observed after the moment of the EVO (exhaust valve opening), where the gases are blown and displaced towards the engine exhaust. However, due to the low rotation speed, the pressure oscillations in the exhaust gas are damped, and the pressure stabilizes quickly at 1.015 bar. Corresponding phenomena are also observed in the respective temperature diagrams.

In the case of in-cylinder pressure variation, its peak value appears a few degrees after the TDC (~190<sup>_◦_</sup>), while the calculated peak pressure reaches almost 50 bar. At this period of engine operation, the combustion products combined with the small available cylinder volume, result in a rapid increase in cylinder pressure.

21 of 36

_Energies_ **2023**, _16_, 6655

3.1.3. Variation in Ignition Timing, Imep, Torque, and Power with Engine Speed

In Figure 23, we can observe the variation in ignition timing in order to reach the MBT as a function of the engine speed. As expected, the ignition timing needed to achieve the maximum brake torque increases significantly as the engine speed increases, and we ~~even notice that, at high-speed values, the optimal ignition advance reaches values close t~~ o <u>90 deg before the TDC.</u>

<!-- Start of picture text -->
100<br>90<br>80<br>70<br>60<br>50<br>40<br>0 2,000 4,000 6,000 8,000 10,0 00<br>Rotational Speed (rpm)<br>Ignition Point (deg)<br><!-- End of picture text -->

**Figure 23.** The variation in ignition timing in order to reach the MBT as a function of the engine speed.

This, of course, results in a large piston work penalty during the compression stroke, which creates a negative effect on the final engine performance and efficiency.

It is worth mentioning that it is questionable whether these ignition timing values can be achieved in the existing LESS-1 prototype. Therefore, the LESS-1 ignition system could indeed be responsible for its poor performance in its first stage of development, as its ignition timing deviates significantly from the MBT timing.

Figure 24 presents the variation in the IMEP with the engine speed, which provides a significant indication of the engine performance. The IMEP/RPM curve indicates that the engine performance is maximized when the shaft speed is at 3000 rpm, where the IMEP is calculated at 9.72 bar, but it is generally quite high, up to 4000 rpm, where the IMEP presents a value of 8.96 bar.

<!-- Start of picture text -->
14<br>12<br>10<br>8<br>6<br>4<br>2<br>0<br>0 2,000 4,000 6,000 8,000 10,000<br>Rotational Speed (rpm)<br>IMEP (bar)<br><!-- End of picture text -->

**Figure 24.** The variation in the IMEP as a function of the crankshaft rotation speed. The scintillation timings are optimal, as calculated from the 1D simulations.

22 of 36

_Energies_ **2023**, _16_, 6655

It is worth mentioning that a modern engine, e.g., a naturally aspirated motorcycle or automobile engine, is expected to develop an optimum IMEP of 13–14.5 bar [1–3].

Therefore, we already see that our engine, which produces an optimal IMEP of 9.72 bar, ~~lags behind, but not signif~~ i ~~cantly, if we take into account that, for today’s data, the com~~ - pression ratio CR = 9.66 is considered relatively low, compared to high-performance car engines [1–3].

We must also take into account that the present engine is at its initial stages of development, where a limited level of resources and research activities is feasible. Finally, Figure 25 presents the engine torque and power as a function of the speed.

<!-- Start of picture text -->
30 20.0<br>Torque<br>17.5<br>25 Power<br>15.0<br>20<br>12.5<br>15 10.0<br>7.5<br>10<br>5.0<br>5<br>2.5<br>0 0.0<br>0 2,000 4,000 6,000 8,000 10,000<br>Rotational Speed (rpm)<br>Torque (Nm) Power (kW)<br><!-- End of picture text -->

**Figure 25.** The variation in the engine torque and power as a function of the speed.

From the above Figure 25, it can be observed that the torque follows a pattern similar to the one of the IMEP, as expected, as the point of maximum torque occurs at 3000 rpm.

On the other hand, the power of the engine increases monotonically in proportion to the rotation speed, up to 8000 rpm, where the maximum power is observed.

After 7200 rpm, the increase in speed and, consequently, the number of combustion cycles per unit of time, causes combustion deterioration and, as a result, the engine efficiency is decreased. In addition, the friction losses are increased exponentially with the increase in speed. Both previous effects result in a maximum operating limit of the engine speed at 7200 rpm.

It is important to mention that our analysis so far shows an engine that performs quite well, especially in the 1000–6000 rpm speed range. The power output is more than enough to provide excess at idle, and preserve engine revving.

## 3.1.4. Effect of Throttling

An important parameter of the engine system which has a direct influence on combustion is the angle of the throttle valve, which regulates the mass of fuel and air mixture that ends up inside the engine cylinder. Throughout the one-dimensional simulations it was assumed that the throttle valve was 100% open.

Particular emphasis was placed on the analyses for this variable, as the response to the throttle valve changes was one of the most important problems of the LESS-1 engine, specifically at 500 rpm speed or, otherwise, at 1000 rpm of a conventional combustion engine speed, where the respective Amesim analyses were performed.

Figure 26 presents the variation in the cylinder pressure versus the crankshaft angle for a complete cycle. The different curves refer to the different values of the throttle angle of the control valve at a percentage relative to its maximum.

23 of 36

_Energies_ **2023**, _16_, 6655

**Figure 26.** The variation in cylinder pressure during an engine cycle, as a function of the throttle valve relative opening for 1000 rpm speed.

It should be emphasized that, when the valve is closed (i.e., the valve is almost perpendicular to the flow), a very small percentage of the air escapes, and is drawn into the cylinder. As the active cross-section of the valve increases, the supply of the gas mixture mass, the maximum cylinder pressure, and the work produced per cycle also increase.

As can be seen from Figure 26, the opening of the throttle valve significantly affects the efficiency of the system, as it controls the mass of fuel that participates in the combustion of the system, and that ultimately affects the IMEP, as a result of burning less or more mass per engine cycle.

Specifically, we observe that the maximum pressure for the 10% position was observed to be 10.68 bar. This pattern changes rapidly as the effective cross-section of the valve increases, as, for the cases of 20% and 30%, the peak pressure was calculated to be 26.10 bar and 35.25 bar, suggesting that the combustion of the gas mixture produces more useful work on the engine piston.

However, as the position of the throttle valve takes on larger values, the rate of increase deteriorates, and the maximum pressure was calculated at 43.08 bar and 46.91 bar for 50% and 100%, respectively. This is because the valve opening in the range of 70–100% affects the mixture flow in the active cross-section much less, compared with its opening in the range of 0–20%. That is explained via the fact that the variation in the mixture mass vs. the opening angle of the valve is not linear.

In addition, as the effective cross-section of the throttle valve increases above 50%, pressure losses at the inlet pipe are significantly decreased and, as less vacuum is created at the intake, and the piston finds less resistance to its movement. As a result of the above, the IMEP increases significantly.

Table 2 presents how the relative valve opening affects the engine performance. The corresponding cases of simulation are reported for an engine speed of 1000 rpm. We can observe that, with the increase in the opening percentage of the throttle valve, all the quantities are gradually increased, until the point when the percentage of the valve reaches 100%.

24 of 36

_Energies_ **2023**, _16_, 6655

**Table 2.** The results for the performance simulation of the LESS-1 prototype engine for different throttling angles at 1000 rpm.

|**Simulation**|**Speed**<br>**(rpm)**|**Relative**<br>**Throttle Angle**|**Air Flow**<br>**(%)**|**IMEP**<br>**(bar)**|**Torque**<br>**(Nm)**|**Power**<br>**(kW)**|
|---|---|---|---|---|---|---|
|THR10|1000|10%|55%|0.51|0.88|0.09|
|THR20|1000|20%|73%|1.02|1.76|0.18|
|THR30|1000|30%|88%|5.24|9.03|0.95|
|THR50|1000|50%|96%|6.12|10.54|1.10|
|THR100|1000|100%|99%|6.17|10.63|1.11|

As an example, we mention that, as expected, the minimum engine power is obtained when the throttle valve is opened by 10%, where we have a mass flow at 55% of the maximum, the engine IMEP is at 0.50 bar, and the produced power is approximately 0.1 kW.

From the results of Table 2, we can conclude that the LESS-1 engine seems to have a good response to changes to the throttle valve opening levels.

In particular, at 1000 rpm, the engine should behave extremely well, based on the theoretical results, and should produce more power as the relative throttling angle is increased.

This reveals that, based on the results of the theoretical simulation, and with the assumptions we have made so far (a perfect mixture, specific spark timing, specific cylinder head design) holding, there is no significant engine design problem.

## _3.2. Results from the Experimental Measurements_

In the present section, we will refer to some of the most characteristic performance measurements performed initially on the first LESS-1 engine prototype and, next, to similar performance measurements on the final LESS-2 engine prototype.

Among the main purposes of performance measurements was the recording of the engine torque and the fuel consumption, as well as the pollutant emissions for different engine operating speeds. In addition, the break power and brake engine efficiency were calculated under the same operating conditions. One additional purpose was the initial estimation of the engine reliability under a variety of operating conditions.

## 3.2.1. Less-1 Prototype Measurements

The measurements of the LESS-1 engine prototype were performed under the following operating parameters and operating conditions:

- a. Carburetor nozzle of 0.8 mm and WOT engine operation;

- b. Carburetor nozzle of 1.1 mm and idle engine operation;

- c. Carburetor nozzle of 1.1 mm and WOT engine operation;

- d. Carburetor nozzle of 1.25 mm and idle engine operation.

The results of the most important measured and calculated engine variables for each of the previous cases are summarized below.

- a. Carburetor nozzle of 0.8 mm and WOT engine operation

The results from the most important performance variables of the LESS-1 prototype engine for a carburetor nozzle of 0.8 mm-and WOT engine operation are presented in Table 3.

25 of 36

_Energies_ **2023**, _16_, 6655

**Table 3.** The results for the performance variables of the LESS-1 prototype engine for a carburetor nozzle of 0.8 mm-and WOT engine operation.

|**Engine Variable**|**Value**|**Unit**|
|---|---|---|
|Speed|1300|rpm|
|Indicated torque|28.3|Nm|
|Brake torque (crank<br>equivalent)|4.96|Nm|
|~~Indicated power~~|~~5.65~~|~~kW~~|
|~~Brake power~~|~~0.99~~|~~kW~~|
|~~Mechanical eff~~i~~ciency~~|~~17.52~~|~~%~~|

The indicated torque corresponding to the combustion of the two chambers is 28.3 Nm, while the corresponding indicated power produced through the combustion is 5.65 kW. It is noted that, although an indicated torque of 28.3 Nm is produced, the brake torque is only 4.96 Nm, and the corresponding brake power is only 0.99 kW (from the indicated power of 5.65 kW). These figures lead to a value of mechanical efficiency of 17.5%, which is quite low compared with the mechanical efficiency of a modern high-performance engine, which stands in the range of 80–90%.

It should be mentioned that the torque measured at the output of the engine is reduced to the corresponding value of a crank engine, due to the aforementioned difference that the LESS mechanism has in relation to a conventional crank mechanism, so that we can compare similar values.

Therefore, the low performance of the engine mechanical efficiency reveals that the engine’s tribological losses, and the resulting component wear, are significantly increased, and strongly contribute to the engine’s poor performance. As a result, in the subsequent stages, special care should definitely be taken to solve this problem, and a thorough analysis of the various subsystems and, especially, of the LESS mechanism, is necessary to perform. Based on the results of this analysis, engine design optimization is necessary, in order to reduce the problem, and improve the mechanical efficiency.

Figure 27 presents the variation in the cylinder pressure during an engine cycle for a carburetor nozzle of 0.8 mm, and WOT engine operation.

**Figure 27.** The variation in the cylinder pressure during an engine cycle for a carburetor nozzle of 0.8 mm, and WOT engine operation.

In Figure 27, we present the pressure of the combustion inside cylinder A (yellow line) and cylinder B (blue line), the corresponding pressure variation that would exist without combustion (motoring, the green and orange lines, respectively for A and B) and, finally, the indication of possible auto-ignition or pre-ignition (knock pressure lines).

26 of 36

_Energies_ **2023**, _16_, 6655

In the present and also in the succeeding figures of cylinder pressure variation a series of grey lines is also presented. These lines display the variation of combustion pressure during a number of succeeding engine cycles. They provide a clear indication of combustion instability inside each of the two engine cylinders under the specific operating condition.

It is noted that there is a significant difference between the pressure curves of cylinders A and B. This result is a confirmation that the engine in its present stage of development is undergoing problematic combustion, which is due to problems in the ignition control and ignition timing system, as well as in the fuel delivery and injection system.

- b. Carburetor nozzle of 1.1 mm and idle engine operation

In a second series of measurements, the initial carburetor nozzle was replaced with one of 1.1 mm, with the aim of providing more fuel to the mixture, as cylinder B, in particular, was running lean and, due to the variation, there were cycles where its combustion was significantly unstable, or even where there was no combustion at all.

After the nozzle replacement, we observed a clear reduction in the variation in the operating speed, with the average speed being 1300 rpm and, generally, ranging from 1260to 1340 rpm, while the stable operation and measurement of the engine at idle was possible under the present configuration.

In the following Table 4, we present the results from the most important performance variables of the LESS-1 prototype engine for the case of a carburetor nozzle of 1.1 mm, and idle engine operation.

**Table 4.** The results for the performance variables of the LESS-1 prototype engine for a carburetor nozzle of 1.1 mm and idle engine operation.

|**Engine Variable**|**Value**|**Unit**|
|---|---|---|
|Speed|1300|rpm|
|Indicated torque|19.1|Nm|
|Brake torque (crank<br>equivalent)|4.8|Nm|
|Indicated power|2.60|kW|
|Brake power|0.66|kW|
|Mechanical efficiency|25.13|%|

It is observed that, with the new configuration, the results are improved; however, the mechanical efficiency, despite its improvement, still remains very low, as should be expected. It should be noted that, in this case, the engine operation is in idle; therefore, its performance is expected to deteriorate in comparison with its WOT operation.

The respective cylinder pressure variation for the present case is presented in Figure 28. A relatively low maximum pressure is observed in both engine cylinders, which is actually reached relatively late. The pressure differences between the two cylinders remain significant, and this is due to the large difference in the air–fuel ratio between the two cylinders.

- c. Carburetor nozzle of 1.1 mm and WOT engine operation

In the final stage, the performance measurements were accomplished using the same carburetor nozzle of 1.1 mm, at a WOT operating condition. The engine speed, in this case, was raised, at 2000 rpm.

Table 5, below presents the results from the most important performance variables for the present case of a carburetor nozzle of 1.1 mm, while engine was operated under a WOT condition.

27 of 36

_Energies_ **2023**, _16_, 6655

**Figure 28.** The variation in the cylinder pressure during an engine cycle for a carburetor nozzle of 1.1 mm, and idle engine operation.

**Table 5.** The results for the performance variables of the LESS-1 prototype engine for a carburetor nozzle of 1.1 mm at a WOT operation.

|**~~Engine Variable~~**|**~~Value~~**|**~~Unit~~**|
|---|---|---|
|~~Speed~~|~~2000~~|~~rpm~~|
|~~Indicated torque~~|~~29.9~~|~~Nm~~|
|Brake torque (crank equivalent)|4.9|Nm|
|Indicated power|6.28|kW|
|Brakepower|1.03|kW|
|Mechanical efficiency|16.39%|%|

We observe that the indicated torque increases at 29.9 Nm compared with the case with the 0.8 mm nozzle, where a value of 28.3 Nm was accomplished. However, as in the two previous cases, the friction losses remain high, as was expected, due to the limitations of the proposed new kinematic system. As a result, the engine’s mechanical efficiency continues to hover at a low value of 16.39%.

The cylinder pressure variation inside both cylinders for the present operating condition is presented in Figure 29.

**Figure 29.** The variation in the cylinder pressure during an engine cycle for a carburetor nozzle of 1.1 mm and WOT engine operation.

It is observed that the combustion in cylinder A is noticeably better, as a result of the extra fuel supply. The combustion in cylinder B remains relatively poor, as no significant pressure is developed and, as a result the indicated work in this cylinder is reduced.

28 of 36

_Energies_ **2023**, _16_, 6655

## d. Carburetor nozzle of 1.25 mm and idle engine operation

In the final stage of measurements for the LESS-1 prototype, the carburetor nozzle diameter was increased to 1.25 mm as, in several cases in the previous measurements, it appeared that the air-fuel ratio was still above 1 and, therefore, combustion was not progressing satisfactorily.

Additionally, in the present case, multiple changes were made to the nozzle control and its needle adjustment, as well as at the air bypass and idle air-fuel ratio adjustment, in an effort to achieve an optimum engine performance.

In Table 6, we present the results from the most important performance variables of the LESS-1 prototype engine for the case of a carburetor nozzle of 1.25 mm, and idle <u>engine operation.</u>

**Table 6.** The results for the performance variables of the LESS-1 prototype engine for a carburetor nozzle of 1.25 mm and idle engine operation.

|**~~Engine Variable~~**|**~~Value~~**|**~~Unit~~**|
|---|---|---|
|~~Speed~~|~~1200~~|~~rpm~~|
|Indicated torque|21.2|Nm|
|Brake torque (crank equivalent)|4.2|Nm|
|Indicatedpower|2.67|kW|
|Brake power|0.53|kW|
|Mechanical efficiency|19.81|%|

Again, it is observed that, with the new configuration, the results are improved; however, the mechanical efficiency, despite its improvement, still remains very low, as should be expected.

The cylinder pressure variation inside both cylinders for the present operating condition is presented in Figure 30. Again, a reduced and delayed combustion is observed in cylinder B, which is present more intensively in the present case.

**Figure 30.** The variation in the cylinder pressure during an engine cycle for a carburetor nozzle of 1.25 mm, and idle engine operation.

In this case, cylinder B works—in general—even in areas where its air-fuel ratio exceeds 1; therefore, the combustion takes place with a lean mixture. This is also a reasonable explanation as to why the work is less in this cylinder, compared with cylinder A.

3.2.2. Most Important Findings from the LESS-1 Prototype Measurements

From the measurement campaign performed with the LESS-1 prototype, the following main results were concluded:

29 of 36

_Energies_ **2023**, _16_, 6655

- The spark plug timing was far from the common values used in conventional SI engines. In addition, the distributor system used in the experiments prohibited the adjustment of spark timing to the desired values, and did not provide the possibility to alter the timing value according to the engine speed;

- As a result, the replacement of the current ignition system with an electronic one in the next stage is expected to be an important step towards engine performance improvement;

- In addition to the analysis of the experimental results, we observed a significant difference in the spark timing advance between the two engine cylinders, which explains the difference in performance between them;

- From the different configurations used in the first round of the experimental campaign, the carburetor nozzle 1.1 mm produced the best result concerning engine performance. In addition, this configuration of the SI engine operation presented the best operating stability.

## 3.2.3. LESS-2 Prototype Measurements

Based on the results of theoretical calculations and the experimental measurement campaign with the LESS-1 prototype, the LESS-2 engine prototype was developed and manufactured. Important changes and improvements were applied to the LESS-2. These included fuel injectors, new intake pipes, connecting circuits, etc.

The updated engine configuration presents its idle at 700 rpm (the actual output shaft speed, or “LESS” speed), which is completely compatible with the idle speed of a traditional combustion engine, which usually lies between 800 and 1000 rpm. As mentioned previously, the LESS mechanism operates at half the speed of a crankshaft mechanism and, due to this, the resulting measurements have been reduced to the corresponding crankshaft revolutions, so, for the purposes of analysis and comparison, the engine revolutions are considered at 1400 rpm.

Accordingly, with a full fuel mixture supply, i.e., with a fully open intake throttle, and corresponding fuel supply, the engine crank equivalent varied between 1300 and 2300 rpm, depending on its load. At engine speeds lower than 1500 rpm, we observed dynamic phenomena, mainly engine speed fluctuation. Due to this observation, the lower operating speed for a full engine load was considered at 1500 rpm. A similar speed instability was observed for speed values above 2100 rpm, resulting in an uneven operation. This was considered to be affected by the high percentage of mechanical losses, as the engine speed was increased to higher values. Therefore, the upper speed limit during the second measurement campaign was considered to be 2000 rpm.

The measurements with the LESS-2 engine prototype were performed under the following operating parameters and operating conditions:

- a. 1400 rpm–idle engine operation;

- b. 1500 rpm–WOT engine operation;

- c. 2000 rpm–WOT engine operation.

The results of the most important measured and calculated engine variables for each of the previous cases are summarized below. In the case of the LESS-2 prototype, we will additionally present, in the following subsections, the results from the experimental measurements for the most important engine emissions.

- a. 1400 rpm–idle engine operation

In Table 7, we present the results from the most important performance variables of the LESS-2 engine for the case of 1400 rpm speed, and idle engine operation.

30 of 36

_Energies_ **2023**, _16_, 6655

**Table 7.** The results for the performance variables of the LESS-2 prototype engine at 1400 rpm speed and idle operation.

|**Engine Variable**|**Value**|**Unit**|
|---|---|---|
|Speed|1400|rpm|
|Ignition timing|12|deg|
|Indicated torque|20.18|Nm|
|Brake torque (crank equivalent)|4.35|Nm|
|Indicated power|2.967|kW|
|Brake power|0.639|kW|
|Mechanical efficiency|21.54|%|
|Engine coolant temperature|91.2|_◦_C|

It is observed that the mechanical efficiency remains quite low, as in the case of the LESS-1 prototype, and this is expected, as it is mainly due to frictional losses in the new kinematic system. An improved design is necessary in the next stage of engine development <u>in order to overcome this deficiency, and increase engine performance.</u>

The cylinder pressure variation inside both cylinders for the present operating condition is presented in Figure 31. We observe the relatively low maximum pressure in the cylinder is actually reached relatively late, as a result of the incomplete filling of the engine cylinder with the air-fuel mixture, even after the improvements applied in the present engine version.

**Figure 31.** The variation in the cylinder pressure during an engine cycle for 1400 rpm speed, and idle engine operation.

On the other hand, it should be mentioned that, with the improved version of the LESS-2, the differences between cylinders A and B are significantly reduced in the present operating condition, and we have the possibility of achieving the stoichiometric ratio in both cylinders. Table 8 presents the results from the experimental measurements for the most important engine-out emissions.

It is observed that the figures for the LESS-2 engine emissions are comparable with those of an SI engine with the current technology and, in the case of HC, the value is even below that emitted from a modern SI combustion engine. The last observation allows the flexibility to achieve a better fuel consumption and increase the engine efficiency, <u>through optimizing the values of the engine parameters, and mainly those of the fuel</u> ~~injection system.~~

31 of 36

_Energies_ **2023**, _16_, 6655

**Table 8.** The results from the emissions of the LESS-2 prototype engine at 1400 rpm speed, and idle operation.

|**Engine-Out Emissions**|**Value**|**Unit**|
|---|---|---|
|HC|406.47|ppm|
|CO|0.245|%|
|CO2|7.16|%|
|NO|1526.35|ppm|
|O2|9.89|%|
|NOx|1609.89|ppm|

- b. 1500 rpm–WOT engine operation

Initially, it was observed that, under the present engine operating condition, speed variation almost vanished during the experimental measurements.

Table 9 presents the results for the most important performance variables of the LESS-2 engine for the present case of 1500 rpm speed and WOT engine operation.

**Table 9.** The results for the performance variables of the LESS-2 prototype engine at 1500 rpm speed and WOT operation.

|**Engine Variable**|**Value**|**Unit**|
|---|---|---|
|Speed|1500|rpm|
|Ignition timing|19|deg|
|Indicated torque|25.9|Nm|
|Brake torque (crank<br>equivalent)|4.01|Nm|
|Indicated power|4.09|kW|
|Brake power|0.65|kW|
|Mechanical efficiency|15.8|%|
|Engine coolant temperature|97.8|_◦_C|

The cylinder pressure variation inside both cylinders for the present operating condition is presented in Figure 32. The maximum combustion pressure is increased in comparison with the results for the LESS-1 under WOT operation. However, there is a significant difference in the pressure variation between cylinders A and B. this difference could be explained via a corresponding difference in the cylinder mass flow and volumetric efficiency, which, despite the improvements still exists under WOT operation in the LESS-2 prototype.

Table 10 presents the results from the experimental measurements for the most important engine-out emissions.

It is, again, observed that the figures for the LESS-2 engine emissions and, especially, that of HC are comparable with, or even below, those of an SI combustion engine with the current technology. An exception in the present case is the value of CO, which stands above that expected from a conventional modern SI engine. This result can be controlled via modifying and optimizing the parameters of the fuel injection system to obtain an acceptable CO value.

32 of 36

_Energies_ **2023**, _16_, 6655

**Figure 32.** The variation in cylinder pressure during an engine cycle for 1500 rpm speed and WOT engine operation.

**Table 10.** The results from the emissions of the LESS-2 prototype engine at 1500 rpm speed and-WOT engine operation.

|**Engine-Out Emissions**|**Value**|**Unit**|
|---|---|---|
|HC|302.939|ppm|
|CO|1.162|%|
|~~CO2~~|~~7.386~~|~~%~~|
|~~NO~~|~~1073.62~~|~~ppm~~|
|~~O~~2|~~9.696~~|~~%~~|
|NOx|1129.25|ppm|

## c. 2000 rpm–WOT engine operation

Table 11 presents the results from the most important performance variables of the LESS-2 engine for the present case of 2000 rpm speed, and WOT engine operation.

**Table 11.** The results for the performance variables of the LESS-2 prototype engine at 2000 rpm speed, and WOT operation.

|**Engine Variable**|**Value**|**Unit**|
|---|---|---|
|Speed|2000|rpm|
|Ignition timing|20|deg|
|Indicated torque|28.7|Nm|
|Brake torque (crank<br>equivalent)|3.9|Nm|
|Indicated power|6.0|kW|
|Brake power|0.83|kW|
|Mechanical efficiency|13.7|%|
|Engine coolant temperature|94.7|_◦_C|

The cylinder pressure variation inside both cylinders for the present operating condition is presented in Figure 33. It is observed that, in the present operating condition, the pressure variation presents only a slight difference between the two cylinders. Both the maximum combustion pressure, and the phasing of pressure variation between the two cylinders, are largely improved. It is evident that, in the current operating condition,

33 of 36

_Energies_ **2023**, _16_, 6655

the mass flow and volumetric efficiency are almost identical between the two cylinders. As a result, the air—fuel ratio is almost stoichiometric at 1.0, and the speed variation is almost at zero level.

**Figure 33.** The variation in the cylinder pressure during an engine cycle for 2000 rpm speed and WOT engine operation.

The improvement in cylinder charge filling under 2000 rpm and WOT operation, in comparison to the result under 1500 rpm, is explained through consideration of the dynamic flow phenomena existing during the gas-exchange process in combustion engines. It is obvious that the inlet and exhaust engine manifold have to be redesigned in a future stage in the improvement of the engine, in order to secure a uniform cylinder filling and emptying process in the whole engine speed operating range.

<u>Table 12 presents the results from the experimental measurements for the most impor-</u> ~~tant engine-out emissions.~~

**Table 12.** The results from the emissions of the LESS-2 prototype engine at 2000 rpm speed and WOT engine operation.

|**Engine-Out Emissions**|**Value**|**Unit**|
|---|---|---|
|HC|280|ppm|
|CO|0.9|%|
|CO2|8.1|%|
|NO|1250|ppm|
|O2|9.2|%|
|NOx|1300|ppm|

It is, again, observed that the figures of the LESS-2 engine emissions and, especially, that of HC are comparable with, or well below, those of an SI combustion engine with the current technology. This result is confirmed via the findings of the theoretical simulation, which revealed that the engine combustion with the specific parameter settings is optimum under higher values of engine speed and, as a result, lower values of emitted HC are expected.

- 3.2.4. Most Important Findings from LESS-2 Prototype Measurements

From the measurement campaign performed for the LESS-2 prototype, the following main results were concluded:

- The most important performance variables are improved in comparison with the initial LESS-1 engine prototype. Among them, the engine speed variation is minimized, the air fuel ratio is almost stoichiometric, and the imep, bmep and engine thermal efficiency are improved;

34 of 36

_Energies_ **2023**, _16_, 6655

- The engine friction losses need additional improvement through an improved new version of the kinematic mechanism;

- The gas-exchange process also needs to be improved, to become effective in the whole engine field of operation. This involves the redesign of the inlet and exhaust manifold, in order to obtain the maximum filling and emptying effectiveness of both engine cylinders;

- The overall engine efficiency is mainly influenced by its mechanical efficiency, which is currently in the 20–25% range, compared to 90%+ of a state-of-the-art SI engine. The problem lies in the high friction coefficient around the TDC. This results in up to 70% friction losses on the conversion of rotating to reciprocating movement alone, and in a corresponding total mechanical loss percentage of the whole engine in the range of 75–80%;

- Therefore, an urgent task in the next steps of engine development is to improve the lubrication regiment of the LESS profiles;

- The general engine operation in the case of LESS-2, is significantly improved in comparison with its predecessor.

## **4. Conclusions**

An original engine kinematic mechanism was applied to an SI combustion engine and, as a result, a prototype engine with the code name “LESS” has been developed, and tested under a variety of operating conditions. The engine development followed several stages, from the original LESS-1 to the final LESS-2 prototype. The most important conclusions during this development process are summarized below:

- The current LESS-2 engine prototype performance is significantly improved in comparison with the previous engine versions. However additional improvement steps are necessary, in order for the new engine to be competitive in the market, and ready for actual application in the field. Such modifications include, but are not limited to, the following:

   - The redesign of the LESS component profiles, to secure hydrodynamic lubrication during the whole engine cycle;

   - The redesign of the piston and combustion chamber geometry;

   - The improved design of the inlet and exhaust manifold, to increase the volumetric efficiency;

   - An improved path for the valve opening/closure (valve kinematics);

   - The specification of the optimum number of inlet valves per cylinder;

   - Modified optimum valve timing, in combination with the number of valves and the valve path;

   - The specification of the optimum position of spark plug;

   - The redesign of the disk type camshaft, or a change to an alternative camshaft design.

- After a detailed theoretical and experimental campaign, all the problematic areas of engine operation, and the respective actions for improvement, have been defined, and are expected to be implemented in the next upcoming stage of engine development.

- As soon as the new engine overcomes these remaining deficiencies, it is expected to become largely competitive in the market, as it presents a high degree of simplicity and, consequently, cost reduction, in comparison with a traditional reciprocating combustion engine.

- The new engine configuration seems to be especially interesting for several markets, such as hybrid propulsion, and energy supply in a variety of small-sized energy consumers and portable applications.

## **5. Patents**

The basic LESS mechanism as well as the LESS engine are covered by patents in Greece, the US and abroad—more specifically, by:

35 of 36

_Energies_ **2023**, _16_, 6655

Greek Patent #1009568 US Patent # 11,220,907,B2 US Patent # 11,414,992 B2.

**Author Contributions:** Conceptualization, V.G.; Data curation, V.G.; Formal analysis, G.M.; Funding acquisition, V.G.; Investigation, D.P. and K.L.; Methodology, V.G.; Project administration, V.G.; Resources, V.G.; Software, V.G., D.P. and K.L.; Supervision, V.G.; Validation, V.G., D.P. and K.L.; Visualization, D.P. and K.L.; Writing—original draft, V.G. and G.M.; Writing—review and editing, G.M. All authors have read and agreed to the published version of the manuscript.

**Funding:** This research is co-financed by the European Regional Development Fund of the European Union and Greek national funds through the Operational Program Competitiveness, Entrepreneurship and Innovation, under the call RESEARCH–CREATE–INNOVATE (project code: T2EDK-02566).

**Data Availability Statement:** Data available on request due to privacy and patents.

## **References**

1. Heywood, J.B. _Internal Combustion Engine Fundamentals_; Mcgraw-Hill Education: New York, NY, USA, 2018.

2. Ferguson, C.R.; Kirkpatrick, A. _Internal Combustion Engines: Applied Thermosciences_; John Wiley & Sons, Inc.: Chichester, UK, 2016.

3. Stone, R. _Introduction to Internal Combustion Engines_; Basingstoke Palgrave Macmillan: London, UK, 2012.

4. Obert, E.F. _Internal Combustion Engines and Air Pollution_; Addison Wesley Publishing Company: Boston, MA, USA, 1973.

5. Taylor, C.F. _The Internal-Combustion Engine in Theory and Practice. Vol. 1, Thermodynamics, Fluid Flow, Performance_; M.I.T. Press: Boston, MA, USA, 1985.

6. Kaiser, E.W.; Siegl, W.O.; Brehob, D.D.; Haghgooie, M. Engine-out Emissions from a Direct-Injection Spark-Ignition (DISI) Engine. _J. Fuels Lubr._ **1999**, _108_, 1155–1165. [CrossRef]

7. Singh, P.K.; Ramadhas, A.S.; Mathai, R.; Sehgal, A.K. Investigation on Combustion, Performance and Emissions of Automotive Engine Fueled with Ethanol Blended Gasoline. _SAE Int. J. Fuels Lubr._ **2016**, _9_, 215–223. [CrossRef]

8. Reitz, R.D.; Ogawa, H.; Payri, R.; Fansler, T.; Kokjohn, S.; Moriyoshi, Y.; Agarwal, A.; Arcoumanis, D.; Assanis, D.; Bae, C.; et al. IJER Editorial: The Future of the Internal Combustion Engine. _Int. J. Engine Res._ **2019**, _21_, 3–10. [CrossRef]

9. Andersson, Ö.; Börjesson, P. The Greenhouse Gas Emissions of an Electrified Vehicle Combined with Renewable Fuels: Life Cycle Assessment and Policy Implications. _Appl. Energy_ **2021**, _289_, 116621. [CrossRef]

10. Ovrum, E.; Longva, T.; Hammer, L.S.; Rivedal, N.H.; Endresen, Ø.; Eide, M. DNV. Maritime Forecast to 2050. 2022. Available online: www.dnv.com/maritime-forecast (accessed on 31 August 2023).

11. IASTEC. Position Paper. Available online: https://iastec.org/position-paper (accessed on 23 July 2023).

12. Kalghatgi, G.T. Developments in Internal Combustion Engines and Implications for Combustion Science and Future Transport Fuels. _Proc. Combust. Inst._ **2015**, _35_, 101–115. [CrossRef]

13. Germany Reaches Deal with EU on future Use of Combustion Engines. Available online: https://www.reuters.com/business/ energy/germany-reaches-deal-with-eu-future-use-combustion-engines-2023-03-25/ (accessed on 31 August 2023).

14. European Court of Auditors. _The EU’s Industrial Policy on Batteries. New strategic Impetus Needed_; Special report SR 2023-15; Publications Office of the European Union: Hague, The Netherlands, 2023; Available online: https://www.eca.europa.eu/en/ publications/SR-2023-15 (accessed on 31 August 2023).

15. Singh, A.P.; Agarwal, A.K. (Eds.) _Novel Internal Combustion Engine Technologies for Performance Improvement and Emission Reduction_; Springer: Singapore, 2021. [CrossRef]

16. Sugeng, D.A.; Ithnin, A.M.; Yahya, W.J.; Abd Kadir, H. Emulsifier-Free Water-in-Biodiesel Emulsion Fuel via Steam Emulsification: Its Physical Properties, Combustion Performance, and Exhaust Emission. _Energies_ **2020**, _13_, 5406. [CrossRef]

17. Depcik, C.; Mattson, J.; Alam, S.S. Open-Source Energy, Entropy, and Exergy 0D Heat Release Model for Internal Combustion Engines. _Energies_ **2023**, _16_, 2514. [CrossRef]

18. Ortenzi, F.; Bossaglia, A. A One-Dimensional Numerical Model for High-Performance Two-Stroke Engines. _Energies_ **2023**, _16_, 4947. [CrossRef]

19. Fijalkowski, B.T. A Novel Internal Combustion Engine Without Crankshaft And Connecting Rod Mechanisms. _J. KONES Powertrain Transp._ **2011**, _18_, 91–104.

20. Kwak, S.W.; Shim, J.K.; Mo, Y.K. Kinematic Conceptual Design of In-Line Four-Cylinder Variable Compression Ratio Engine Mechanisms Considering Vertical Second Harmonic Acceleration. _Appl. Sci._ **2020**, _10_, 3765. [CrossRef]

21. Itu, C.; Scutaru, M.-L.; Pruncu, C.I.; Muntean, R. Kinematic and Dynamic Response of a Novel Engine Mechanism Design Driven by an Oscillation Arm. _Appl. Sci._ **2020**, _10_, 2733. [CrossRef]

22. De Martin, A.; Jacazio, G.; Sorli, M. A Novel Electromechanical Solution for Cam-Switching in High Performance Internal Combustion Engines. _J. Dyn. Sys. Meas. Control_ **2020**, _142_, 071007. [CrossRef]

36 of 36

_Energies_ **2023**, _16_, 6655

23. Dado, M.H.; Alrbai, M.; Tanbour, E.; Al Asfar, J. Performance assessment of a novel mechanism design of spark-ignition internal combustion engine. _Energy Sources Part A Recovery Util. Environ. Eff._ **2021**. [CrossRef]

24. Imeche. Internal Combustion Engines and Powertrain Systems for Future Transport 2019. In Proceedings of the International Conference on Internal Combustion Engines and Powertrain Systems for Future Transport, (ICEPSFT 2019), Birmingham, UK, 11–12 December 2019.

25. Simcenter Amesim 2022.1. _Siemens Digital Industries Software_. Available online: https://plm.sw.siemens.com/en-US/simcenter/ systems-simulation/amesim/ (accessed on 31 August 2023).

26. Richard, S.; Bougrine, S.; Font, G.; Lafossas, F.-A.; Le Berr, F. On the Reduction of a 3D CFD Combustion Model to Build a Physical 0D Model for Simulating Heat Release, Knock and Pollutants in SI Engines. _Oil Gas Sci. Technol.-Rev. IFP._ **2009**, _64_, 223–242. [CrossRef]

27. Rakopoulos, C.D.; Mavropoulos, G.C. Experimental evaluation of local instantaneous heat transfer characteristics in the combustion chamber of air-cooled direct injection diesel engine. _Energy_ **2008**, _33_, 1084–1099. [CrossRef]

28. Hountalas, D.T.; Mavropoulos, G.C.; Zannis, T.C.; Schwarz, V. _Possibilities to Achieve Future Emission Limits for HD Di Diesel Engines Using Internal Measures_; 2005-01-0377; SAE 2005 World Congress & Exhibition; SAE International: Detroit, MI, USA, 2005. [CrossRef]

**Disclaimer/Publisher’s Note:** The statements, opinions and data contained in all publications are solely those of the individual author(s) and contributor(s) and not of MDPI and/or the editor(s). MDPI and/or the editor(s) disclaim responsibility for any injury to people or property resulting from any ideas, methods, instructions or products referred to in the content.
