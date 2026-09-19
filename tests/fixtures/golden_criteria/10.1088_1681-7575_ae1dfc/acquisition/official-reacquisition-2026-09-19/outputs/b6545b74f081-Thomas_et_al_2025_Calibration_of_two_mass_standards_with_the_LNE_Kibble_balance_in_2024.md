---
title: "Calibration of two mass standards with the LNE Kibble balance in 2024"
authors: "M Thomas, D Ziane, P Espel, K Dougdag, F Beaudoux, S Merlet, N Addi, F Couëdo, M Taupin"
journal: "Metrologia"
doi: "10.1088/1681-7575/ae1dfc"
published: "2025-12-1"
source: "iop_html"
acquisition:
  provider: "iop"
  route: "browser_html"
  representation: "html"
  transport: "browser"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 12749
---

# Calibration of two mass standards with the LNE Kibble balance in 2024

## Abstract

Kibble balances are complex electromechanical instruments that enable the determination of mass within the SI by linking it to the Planck constant *h*, the defining constant of the mass unit. The LNE has been developing its own Kibble balance since 2002, with the most recent improvements focusing on the implementation of a contactless linear motor for the dynamic phase and the fine adjustment of the beam’s orientation with respect to the horizontal plane for the static phase. In 2024, two mass calibration campaigns were carried out using the LNE Kibble balance: first with an iridium standard (DB1), and then with a platinum-iridium standard (W1). Both artefacts have a nominal mass of 500 g, and their masses were determined with relative standard uncertainties of $3.1\cdot{10^{ - 8}}$ and $3.5\cdot{10^{ - 8}}$ respectively (${\text{k }} = {\text{ }}1$).

## 1. Introduction

Measurements of the Planck constant *h* were performed in air using the LNE (Laboratoire national de métrologie et d’essais, the French National metrology institute) Kibble balance in 2014 [1], 2016 [2] and 2017 [3] with a continuous improvement in combined uncertainty: the relative standard uncertainty achieved in 2017 was $5.7 \cdot {10^{ - 8}}$ ($k = 1$, as for all uncertainties given in this document). These determinations were carried out in air, with the uncertainty in the air refractive index being the dominant contribution to the uncertainty budget. Vacuum operation was not an option at this time due to unwanted movement of the apparatus when transitioning from air to vacuum. In subsequent years, efforts focused on resolving this issue and improving the entire experiment.

Since 2017, the apparatus has been completely disassembled. The three electrically isolated legs, which support the whole apparatus, and where at the origin of the vacuum movement, have been modified. These modifications also provided an opportunity to improve the type A measurement uncertainty in both static and dynamic phases. Numerous other improvements and characterizations were also carried out, addressing both Type B and Type A uncertainties.

The experiment now operates under vacuum conditions and runs continuously for weeks at a time, interrupted only by liquid helium top-ups for the Josephson standards and some alignment checks.

In the following sections, we provide a brief description of the LNE Kibble balance (LNE-KB), present the results obtained in vacuum conditions for two different standard masses, and discuss the experimental improvements that have led to reduce the uncertainty achieved.

## 2. Principle of the Kibble balance

### 2.1. A power equality

The principle of Bryan Kibble’s experimental setup [4] consists of a virtual comparison of electrical and mechanical powers measured in two phases: a static phase and a dynamic phase (figure 1).

![Figure 1](10.1088_1681-7575_ae1dfc_assets/metae1dfcf1_hr.jpg)

**Figure 1.** Principle and apparatus of the LNE Kibble balance in static and dynamic phases. *Principle:* In the static phase, where the coil is immersed in a magnetic field *B*, the weight of a standard mass *m* is counterbalanced by an electromagnetic force; in the dynamic phase, the coil is moved vertically in the same magnetic field. *Apparatus:* coil velocities are acquired by TIA measuring a heterodyne frequency (*f*<sub>0</sub>) of interferometers, together with the shifted frequency (*f*<sub>0</sub>+ *f*<sub>Doppler</sub>). Positions are measured by monitoring the output of a phase-frequency comparator by means of a field-programmable gate array (FPGA). Voltages are measured by means of three digital voltmeters (DVM, only one shown here), by comparison with the output of a JAVS. In the static phase, the current flowing through the coil is permanently adjusted by a PID servo loop in a RTC. All devices are controlled by a PC on a local network, using LabVIEW routines. Synchronization (mainly voltage and velocity) is ensured by a triggering system.

In the static phase, or weighing phase, the weight $m\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {g}$ of a standard mass *m* subject to the acceleration of gravity $g$ is balanced by the Laplace force $\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {F}$ exerted on a conductor of length $\ell$ crossed by a current $I$ when it is immersed in a radial field of magnetic induction ${\text{ }}\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {B}$. For a perfect alignment of the system, where $\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {F} = {F_z} \cdot {\vec e_z}$, with ${\vec e_z}$ the local vertical, this equilibrium is described by the relation:

**Equation 1.**

$$
\begin{align}m \cdot g = {\text{ }}B\ell \cdot I,\end{align} \tag{ 1 }
$$

where $I$ can be measured by the potential drop $V$ that it produces across a resistor *R*.

In the dynamic phase, or moving phase, the same coil is moved at a vertical velocity $\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {v} = {v_z} \cdot {\vec e_z}$, in the same magnetic flux density $\overset{\lower0.2em\hbox{$\smash{\scriptscriptstyle\rightharpoonup}$}} {B}$. Again, if the system is perfectly aligned, Lenz-Faraday’s law leads to a voltage induced drop across the coil given by the relation:

**Equation 2.**

$$
\begin{equation}U = B\ell \cdot {v_z}.\end{equation} \tag{ 2 }
$$

If the length of the conductor, the relative positions of the conductor and the magnetic flux in the two phases remain unchanged, and if the coil passes through its weighing position during the velocity mode with the same orientation, the combination of the two relations can be re-expressed as the equality of virtual electrical and mechanical powers (and thus in particular without losses by Joule effect):

**Equation 3.**

$$
\begin{align}m \cdot g \cdot {v_z} = U \cdot I = \frac{{U \cdot V}}{R}.\end{align} \tag{ 3 }
$$

### 2.2. Link to defining constant

The voltages of the measurements are carried out in comparison with the Josephson effect, therefore:

**Equation 4.**

$$
\begin{align}U = {n_U} \cdot \frac{{{f_U}}}{{{K_{\text{J}}}}}\end{align} \tag{ 4 }
$$

**Equation 5.**

$$
\begin{align}V = {n_V} \cdot \frac{{{f_V}}}{{{K_J}}}\end{align} \tag{ 5 }
$$

with ${n_U}$ and ${n_V}$ the number of the Shapiro steps used and secondly ${f_U}$ and ${f_V}$ the irradiation frequencies of the Josephson junctions. The reference constant being the Josephson constant:

**Equation 6.**

$$
\begin{align}{K_J} = \frac{{2{\text{ }}e}}{h}\end{align} \tag{ 6 }
$$

with $e$ the elementary charge, and $h$ the Planck constant.

The resistances are measured by comparison with a quantum Hall resistance standard (QHRS), so we have

**Equation 7.**

$$
\begin{align}R = \frac{{{R_{\text{K}}}}}{i}\end{align} \tag{ 7 }
$$

where $i$ the index of the step used and the reference constant being the Von Klitzing constant

**Equation 8.**

$$
\begin{align}{R_{\text{K}}} = \frac{h}{{{e^2}}}.\end{align} \tag{ 8 }
$$

We can then express the mass *m* as a function of experimentally determined numbers and quantities, and $h$ the Planck constant:

**Equation 9.**

$$
\begin{align}m = {\text{ }}\left({\frac{{{n_U} \cdot {n_V} \cdot {f_U} \cdot {f_V} \cdot i}}{{4{\text{ }} \cdot g{\text{ }} \cdot {v_z}}}} \right) \cdot h.\end{align} \tag{ 9 }
$$

Finally, as frequencies (and time) are measured in terms of $\Delta \nu \left({{\text{Cs}}} \right)$ (hyperfine splitting frequency of caesium, the defining constant of the second), ${v_z}$ and $g$ in terms of $c$ (speed of light, the defining constant of the meter) and $\Delta \nu \left({{\text{Cs}}} \right)$, the previous equation can be written down as:

**Equation 10.**

$$
\begin{align}m{\text{ = }}{k_{\text{m}}} \cdot \frac{{\Delta v\left(Cs\right) \cdot h}}{{{c^2}}}\end{align} \tag{ 10 }
$$

where ${k_{\text{m}}}$ is a constant given by the product of integers, experimentally determined. The unit of mass can be realized with a Kibble balance from a set of three defining constants: $h$, $c$ and $\Delta \nu \left({{\text{Cs}}} \right)$.

### 2.3. Practical mass measurement

In section 2.1, $B\ell$ is considered as an unknown quantity in equation (1) (static phase) evaluated through equation (2) (dynamic phase). However, both in static phase and in dynamic phase, the $B\ell$ value, also known as the geometrical factor, is the same physical parameter which links the force generated to the current, and the voltage to the velocity. Each describes one aspect of electromagnetic interaction: one mechanical, derived from the Lorentz force (Laplace force in the static phase), and the other electrical, derived from the Maxwell–Faraday equation (Lenz-Faraday voltage in the dynamic phase).

Then, in order to symmetrize the two phases of measurement, and to build on the common principle of the two phases, one can assign a conventional value ${m_0}$ to the mass of the artefact (for example, ${m_0} = 0.5{\text{ kg}}$ for a mass of nominal value 0.5 kg). In this case, a conventional value of $B\ell$ can actually be evaluated in the static phase:

**Equation 11.**

$$
\begin{align}B{\ell _{\text{stat}}} = \frac{{{m_0}}}{m}{\text{ }}B\ell = {\text{ }}\frac{{{m_0} \cdot g}}{I}{\text{ }}.\end{align} \tag{ 11 }
$$

The geometric factor ${\text{ }}B\ell$ is evaluated in dynamic phase (equation (3)), and noted now as ${\text{ }}B{\ell _{{\text{dyn}}}}$:

**Equation 12.**

$$
\begin{align}B{\ell _{{\text{dyn}}}} = \frac{U}{{{v_z}}}.\end{align} \tag{ 12 }
$$

The two former quantities $B{\ell _{{\text{stat}}}}$ and $B{\ell _{{\text{dyn}}}}$ can be determined experimentally, and allow one to determine the value of the unknown mass $m$ (actually the relative deviation to the conventional value ${m_0}$):

**Equation 13.**

$$
\begin{align}\frac{m}{{{m_0}}} - 1 = \frac{{B{\ell _{{\text{dyn}}}}}}{{B{\ell _{{\text{stat}}}}}} - 1.\end{align} \tag{ 13 }
$$

An actual measurement sequence consists of alternating geometric factor determinations in static and dynamic phases: mass determination needs the values of geometric factor in both static and dynamic phases. Furthermore, using this formalism, one can compare the results in the static and dynamic phases, in terms of noise or drift, for example, directly in a common plot.

The typical relative uncertainties aimed for mature Kibble balances are some parts in 10<sup>8</sup> at 1 kg. All quantities measured must then be known with an even better uncertainty: extreme care should be employed in every aspect of the design of a Kibble balance and in its adjustments. Generally speaking, all the instruments, standards or technologies used in a Kibble balance are close to the state-of-the-art.

## 3. LNE Kibble balance description

A comprehensive description of the LNE-KB elements is given in [3]. Therefore, just a very brief description of the apparatus is given here, followed by a focus on parts that have undergone significant changes from 2017 to 2024.

### 3.1. Vacuum operation: structure and concrete slab

In 2017, the LNE Kibble balance was not yet able to operate under vacuum due to problems with the feet of the apparatus. Measurements were done in air and this introduced two significant uncertainties: the buoyancy contribution to the mass determination and the air refractive index contribution to the velocity determination. This index was calculated from temperature, pressure, relative humidity and mole fraction of carbon dioxide: the standard uncertainty associated was estimated to be $4.5 \times {10^{ - 8}}$, mainly due to the temperature measurement uncertainty (30 mK).

To work under vacuum and eliminate buoyancy and air refractive index contributions, the original ‘V-shaped’ feet of the apparatus were replaced by ‘column feet’ with much better mechanical stability. These new feet were also chosen because of their lower transmission factor of mechanical vibrations from the floor to the apparatus. This major change required a complete disassembly of the experiment followed by reassembly, alignment and commissioning of all the instrumentation.

On the other hand, the entire Kibble balance experiment rests on a massive concrete block measuring 6 m × 5.5 m × 2 m, ‘isolated’ laterally from the surrounding soil by a layer of Fontainebleau sand about 3 cm thick. For years, a strong mechanical coupling was observed when mechanical shocks occurred around the block. We suspected that the sand was the cause of this coupling and removed it around the perimeter of the slab and to a depth of 2 m by vacuum earthmoving.

In addition to eliminating two contributions to the uncertainty budget (refractive index and buoyancy), these changes drastically improved the overall stability of the apparatus as well as its mechanical immunity to environmental noise [5].

### 3.2. New beam adjustment stage

A new beam position adjustment system has been designed. This system adjusts the horizontal position of the beam by planar sliding and, consequently, that of the coil relative to the magnetic circuit. The achievable displacement is on the order of a millimeter, with micrometric resolution. Through a kinematic linkage attached to the previously described movable plane, it is also possible to adjust the parallelism of the beam’s central axis (targeting horizontal alignment) with a resolution on the order of tens of microradians (figure 2).

![Figure 2](10.1088_1681-7575_ae1dfc_assets/metae1dfcf2_hr.jpg)

**Figure 2.** CAD view of the beam and of its adjustement stage.

### 3.3. New suspension stop

A new stop system has been installed in the coil suspension. It consists of a highly rigid aluminum structure, fixed to beam adjustment stage, and equipped with two micrometric screws. These screws, aligned with the suspension axis, have glass spheres with a diameter of 1 mm at their ends, which come into contact with tungsten pads on the suspension. The high hardness of these materials ensures a repeatable limitation of the total excursion of the beam during weighing. Furthermore, by applying a constant force to the suspension, the different beam joints experience the same forces throughout all weighing phases, reducing hysteretic effects.

### 3.4. New mass lifter

The mass positioning system used during the 2017 campaign had several limitations, the most significant being its poor reliability, which made long-duration measurement campaigns impossible. A new mass positioning system was designed in 2022, based on vacuum-compatible stepper motors equipped with their own ball-bearing guide plates. This high-reliability two-axis exchanger allows position adjustments in the horizontal plane and fine-tuning of the deposition axis relative to the vertical, ensuring the most repeatable mass placement and removal possible.

### 3.5. A commercial interferometer to measure the vertical position of the beam

The slit detector previously used for the vertical position of the beam, with sub-nanometer resolution [6], was replaced by a commercial fiber interferometer with 10 pm resolution (Attocube IDS3010), offering higher bandwidth and improved signal-to-noise ratio.

In addition to these upgrades, the implementation of a customized PID controller enables stringent criteria for the servo-controlled position required to consider the beam stabilized. We typically consider the beam to be ‘locked’ on position when the $z$ -position of the beam is at a distance of less than 50 nm from the target for at least 7 s and with a current stability lower than 2 nA. As a result, the $z$ -positions of the beam for mass-up and mass-down have a standard deviation of 12 nm, see figure 7(given the beam stiffness of about 0.5 N m<sup>−1</sup>, this corresponds to a mass comparison standard deviation of the equivalent of 0.8 µg).

Indeed, the relative overlapping Allan standard deviation for $B{\ell _{{\text{stat}}}}$ has value of $1.5 \times {10^{ - 8}}$ for $\tau = 1{\text{ day}}$ with a typical $- \raise.5ex\hbox{$\scriptstyle 1$}\kern-.1em/ \kern-.15em\lower.25ex\hbox{$\scriptstyle 2$}$ slope of a white noise measurement. This performance represents a 16-fold improvement over the 2017 results [5].

### 3.6. New electronic triggering system and new motor for the dynamic phase

The performance of the dynamic phase and the reduction of its noise were improved by two significant modifications.

1. First, attention has been paid to simultaneously measuring *U* and v during the dynamic phase in order to achieve maximum noise rejection. To do this, a commercial multi-trigger digital delay generator (Berkeley model 725) is used to coordinate and synchronize the output triggering signals emitted from the voltmeters with the velocity and position measurements in both phases. The delay between both signals is less than 30 ns.

2. Secondly, the motor that drives the linear guiding stage which in turn moves up and down the coil immersed in the magnetic flux has been changed. Until the end of 2022, a commercial screw motor (Aerotech ATS150-100-M-20P) with its controller (Aerotech NL Drive A3200) was used on the LNE Kibble balance. However, as a screw motor, it is prone to solid friction, with a rather high value of induced speed noise. The tuning of the controller was done by the manufacturer (it includes 10 main gain parameters and several other factors) and has never been changed for years because of complexity and risks. In fact, any modification of the gains could lead to damage to the delicate parts that support it: the guiding stage, the beam and the double gimbal of the suspension, which are monolithic parts with a bending strip of 40 µm thickness. However, by this time it was clear that the screw motor was the weak point of the experiment. Changes were made and a commercial linear motor (Aerotech BLMC-192-MTC-250P) with its controller (Aerotech Soloist ML) was implemented in the LNE-KB in early 2023, taking advantage of the time between the last CCM (Comité consultative des masses) key comparison in 2021 and the next one in 2024. The motor was fixed in place in the LNE-KB and the controller was connected to the computer controlling the experiment. Since the guide table is counterbalanced, the vertical motor only needs to generate a maximum force of 5 N, which is equivalent to 0.2 A. In this way, the Joule heating has a maximum value of 200 mW.

Finally, these modifications were very beneficial: the spatial profile of ${\text{ }}B{\ell _{{\text{dyn}}}}\left(z \right)$ shows a relative noise 20 times better than in 2017 and the relative overlapping Allan standard deviation for $B{\ell _{{\text{dyn}}}}$ has value of $6 \times {10^{ - 8}}$ for $\tau = 1{\text{ day}}$, a 4-fold improvement [5].

## 4. Measurement scheme

One of the characteristics of the balance of the LNE-KB (figures 3 and 4) lies in its dynamic phase where the force comparator (beam of the balance and its suspension) used for the static phase is displaced as a whole in order to avoid the use of the beam as motion generator.

![Figure 3](10.1088_1681-7575_ae1dfc_assets/metae1dfcf3_hr.jpg)

**Figure 3.** Picture of the LNE Kibble balance. The light trails (made visible by the long exposure time of the photograph) are caused by the Nd:YAG laser (green), used for the metrological measurement of the coil’s vertical velocity, and the laser diode (red) used to measure the coil’s horizontal position.

![Figure 4](10.1088_1681-7575_ae1dfc_assets/metae1dfcf4_hr.jpg)

**Figure 4.** Schematic of the LNE Kibble watt balance. Only the main visible parts are shown. The 1 m platinum iridium bar and the 1 kilogram platinum iridium cylinder are for scale.

During the dynamic phase, the coil is moved vertically, by means of a flexible strip guiding stage [7] controlled at a speed of 2 mm s<sup>−1</sup> over a distance of 40 mm. Typically, sixty upward and downward motions are performed in 1 h. The displacement of the coil in the magnetic field generates a voltage of about 1 V measured against a Josephson standard: the speed of the coil is measured synchronously (by means of three heterodyne interferometers aiming to three corner cubes located at 120° on the perimeter of the coil, illuminated by a iodine frequency stabilized laser) with the integration times of the voltmeters.

During the static phase, the comparison of forces is ensured by a beam with monolithic bi-circular flexure strip (thickness at the neck of 40 μm) [8]. The beam actually compares moments, and in order to get rid of the need to know the length ratio between the two arms, we compare the Laplace’s force and the weight by means of the same arm. Typically, the succession of 5 double weighings (with and without standard mass) takes 1 h: the currents necessary to ensure the balance of the beam are of the order of 5 mA (i.e. 1 V measured across a 200 Ω resistor against a Josephson standard [9]) in the 1 T induction of the magnetic circuit used [10] (radial and horizontal field). Acceleration of gravity needs to be known in real time at the center of mass of the standard mass: a cold atom gravimeter is used and the self-gravity of the apparatus is calculated [11, 12].

The measurement of these voltages and currents compared to quantum electrical standards ensures the link between the mass and the Planck constant, and can be used to implement the new SI definition of the mass unit [13].

The product ${\text{ }}B{\ell _{{\text{dyn}}}}\left(z \right)$ is given by the ratio of the induced voltage *U* at the terminals of the coil to the velocity $v$ of the coil at different heights $z{\text{ }}$ of the trajectory. Measurements are made when the coil is translated vertically (up and down) through the gap of the magnetic circuit over a 40 mm travel range. During a movement, the velocity is first increased linearly with time, kept at a constant value of 2 mm s<sup>−1</sup> and then decreased to zero. This movement induces a voltage *U* around 1 V at the terminals of the coil. Trajectories are averaged to give one $B{\ell _{{\text{dyn}}}}\left(z \right)$ evaluation at different vertical position, see figure 10. The profile is then fitted in order to obtain the value of the geometric factor at the height of the static phase: $B{\ell _{{\text{dyn}}}}$.

However, if the coil rotates about the horizontal as it moves, an error in the vertical distance measurement and thus the vertical velocity measure, known as Abbe error, appears. This error is linked to the horizontal distance between the coil gimbal and the point where the velocity is measured (‘optical center’). An algorithm is used to determine the weight associated to each of the three velocity determinations in order to align the optical center to the gimbal center suspension.

The product ${\text{ }}B{\ell _{{\text{stat}}}}$ is given by the ratio of the acceleration of gravity multiplied by a conventional value of mass ${m_0}$ to the total current injected in the coil (equation (11)). The measurement is made in two steps with either a direct or a reversed current flowing through the coil for the configurations ‘mass on’ and ‘mass off’. In both cases, a voltage drop $V$ is measured at the terminals of a $200{{ \Omega }}$ resistor $R$. The current $I$ flowing through the coil is continuously adjusted by a programmable current source (controlled by a real-time computer) to oppose any change in the forces acting on the beam. It takes around $100{\text{ s}}$ for the beam position to reach the steady state from one mass configuration to the other. The knowledge of the acceleration of gravity and the measurements of the current $I$ allow one to evaluate the product ${\text{ }}B{\ell _{{\text{stat}}}}$.

Typically, one value of the geometrical factor ($B{\ell _{{\text{stat}}}}$ or ${\text{ }}B{\ell _{{\text{dyn}}}}$) is obtained every hour. The set ${\text{ }}B{\ell _{{\text{stat}}}}$ is interpolated to match the dates of the ${\text{ }}B{\ell _{{\text{dyn}}}}$ measurements, and the set ${\text{ }}B{\ell _{{\text{dyn}}}}$ is interpolated to match dates of the ${\text{ }}B{\ell _{{\text{stat}}}}$ measurements. In this way, one can compare values of the geometrical factors at the same time, to get rid of any mutual variation in value (mainly due to the temperature of the magnetic circuit). Then one mass measurement can be calculated at each ${\text{ }}B{\ell _{{\text{stat}}}}$ or ${\text{ }}B{\ell _{{\text{dyn}}}}$ evaluation. Thus, one typical day of measurement leads to 20 values of mass. Correlation between these successive mass values is discussed later in section 6.1

## 5. Results

In summer and autumn 2024, two different artefacts were weighed in the LNE Kibble balance.

The first one, ‘DB1’ is a pure iridium artefact. The second one, ‘W1’ is a platinum iridium artefact. Both have a nominal value of $500{\text{ g}}$. Each calibration lasted several tens of days of continuous measurement.

The upper graph of figure 5 shows a typical run of one day with alternating $B{\ell _{{\text{stat}}}}$ and ${\text{ }}B{\ell _{{\text{dyn}}}}$ determinations. The lower graph of figure 5 shows the relative standard deviations of ${\text{ }}B{\ell _{{\text{stat}}}}$ and ${\text{ }}B{\ell _{{\text{dyn}}}}$. The maximal relative successive differences (ABA, BAB scheme) are respectively below $75 \cdot {10^{ - 9}}{\text{ }}$ and $150 \cdot {10^{ - 9}}$, which is significantly better than the values obtained in 2017.

![Figure 5](10.1088_1681-7575_ae1dfc_assets/metae1dfcf5_hr.jpg)

**Figure 5.** Upper graph: A one-day typical run with alternating $B{\ell _{{\text{stat}}}}$ and of ${\text{ }}B{\ell _{{\text{dyn}}}}$ determinations. Lower graph: relative standard deviations of $B{\ell _{{\text{stat}}}}{\text{ }}$ and of ${\text{ }}B{\ell _{{\text{dyn}}}}.$

One liquid helium top-up lasts typically 13 d (this corresponds to the autonomy of a liquid helium Dewar required to cool down the Josephson array voltage standard): one measurement campaign requires several liquid helium top-ups in order to obtain a competitive value of Type A uncertainty together with a robust estimation of this Type A. The final estimation of the mass is the average value of all the data sets.

The DB1 measurement campaign started on 12 June 2024 and ended on 5 September 2024. It lasted 86 d and required 6 helium cylinders producing 2741 individual determinations of mass (days without values were devoted to alignment verifications).

Results for DB1 calibration are presented on figure 6. The relative Type A standard uncertainty (which is the relative Allan deviation calculated from these data) is $1.6 \times {10^{ - 8}}$. The combined relative uncertainty is $3.1 \times {10^{ - 8}}$. All the contributions are summarized in table 1, and the uncertainty budget being detailed in the next section.

![Figure 6](10.1088_1681-7575_ae1dfc_assets/metae1dfcf6_hr.jpg)

**Figure 6.** Results of mass campaign determinations. The DB1 measurement campaign (blue) lasted 86 d from 12 June 2024 to 5 September 2024. The W1 measurement campaign (orange) started on 17 September 2024 and ended on 11 November 2024. It lasted 58 d and required 4 helium cylinders producing 1479 individual determinations of mass.

**Table 1.** Main uncertainty contributions to the measurements of DB1 masse (*k* = 1).

**Table**

| Contributions                 | Relative uncertainty    |
| ----------------------------- | ----------------------- |
| Current correction            | $5 \cdot {10^{ - 9}}$   |
| Beam: parasitic forces        | $1.5 \cdot {10^{ - 9}}$ |
| Beam: ${\text{z}}$ error      | $8 \cdot {10^{ - 9}}$   |
| Parasitic watt ratio error    | $8 \cdot {10^{ - 9}}$   |
| Resistance value              | $5 \cdot {10^{ - 9}}$   |
| Velocity                      | $1 \cdot {10^{ - 8}}$   |
| Absolute gravity value        | $5 \cdot {10^{ - 9}}$   |
| Voltage                       | $1 \cdot {10^{ - 8}}$   |
| Field gradient                | $1 \cdot {10^{ - 9}}$   |
| Fit                           | $1.5 \cdot {10^{ - 8}}$ |
| Others                        | $1 \cdot {10^{ - 8}}$   |
| Statistical                   | $1.6 \cdot {10^{ - 8}}$ |
|                               |                         |
| Combined uncertainty (u(DB1)) | $3.1 \cdot {10^{ - 8}}$ |

The mass of the artefact DB1, as calibrated by the LNE-KB is therefore:

**Equation 14.**

$$
\begin{align}m_{{\text{DB}}1}^{{\text{LNE}} - {\text{KB}}} - 500{\text{ g}} = {\text{ }}42μ{\text{g }} \pm 16μ{\text{g }}\left({k = 1} \right).\end{align} \tag{ 14 }
$$

The same artefact was compared to mass standard references of the LNE Mass Department:

**Equation 15.**

$$
\begin{align}m_{{\text{DB}}1}^{{\text{LNE}} - {\text{mDep}}} - 500{\text{ g}} = {\text{ }}53μ{\text{g }} \pm 13μ{\text{g }}\left({k = 1} \right).\end{align} \tag{ 15 }
$$

The difference between these two values is 11 µg, which corresponds to a normalized interval of $0.44.$

The W1 measurement campaign started on 17 September 2024 and ended on 11 November 2024. It lasted 58 d and required 4 helium cylinders producing 1479 individual determinations of mass.

Results for W1 calibration are presented on figure 6. The relative Type A standard uncertainty is $2.2 \times {10^{ - 8}}$. The combined relative uncertainty is $3.5 \times {10^{ - 8}}$. All the contributions are summarized in table 2, and the uncertainty budget being detailed in the next section.

**Table 2.** Main uncertainty contributions to the measurements of W1 masse (*k* = 1).

**Table**

| Contributions                | Relative uncertainty    |
| ---------------------------- | ----------------------- |
| Current correction           | $5 \cdot {10^{ - 9}}$   |
| Beam: parasitic forces       | $1.5 \cdot {10^{ - 9}}$ |
| Beam: ${\text{z}}$ error     | $8 \cdot {10^{ - 9}}$   |
| Parasitic watt ratio error   | $8 \cdot {10^{ - 9}}$   |
| Resistance value             | $5 \cdot {10^{ - 9}}$   |
| Velocity                     | $1 \cdot {10^{ - 8}}$   |
| Absolute gravity value       | $5 \cdot {10^{ - 9}}$   |
| Voltage                      | $1 \cdot {10^{ - 8}}$   |
| Field gradient               | $1 \cdot {10^{ - 9}}$   |
| Fit                          | $1.5 \cdot {10^{ - 8}}$ |
| Others                       | $1 \cdot {10^{ - 8}}$   |
| *Statistical*                | $2.2 \cdot {10^{ - 8}}$ |
|                              |                         |
| Combined uncertainty (u(W1)) | $3.5 \cdot {10^{ - 8}}$ |

The mass of the artefact W1, as calibrated by the LNE-KB is therefore:

**Equation 16.**

$$
\begin{align}m_{{\text{W}}1}^{{\text{LNE}} - {\text{KB}}} - 500{\text{ g}} = {\text{ }}178 μ{\text{g }} \pm 18 μ{\text{g }}\left({k = 1} \right).\end{align} \tag{ 16 }
$$

This value can also be compared to mass standard references of the LNE Mass Department:

**Equation 17.**

$$
\begin{align}m_{{\text{W}}1}^{{\text{LNE}} - {\text{mDep}}} - 500{\text{ g}} = {\text{ }}180μ{\text{g }} \pm 13 μ{\text{g }}\left({k = 1} \right).\end{align} \tag{ 17 }
$$

The difference between these two values is 2 µg, which corresponds to a normalized interval of $0.09.$ Ultimately, the LNE-KB together with other KBs and x-ray crystal density experiment, are the source of traceability for the kilogram [14]: the difference between a mass calibrated by the LNE-KB and the mass standard references of the LNE Mass Department is therefore the difference between the LNE-KB realization of the mass unit and the previous kilogram consensus value.

The contribution from both phases in terms of type B uncertainties are similar because the various elements of the experiment have been checked regularly after prior adjustment.

## 6. Uncertainty budget

The uncertainty contributions are summarized in tables 1 and 2. Most of them have been explained in detailed elsewhere [1, 3, 5, 15]; therefore only a brief description is given here.

‘Statistical’, uncertainties evaluated by a statistical method, i.e. Type A uncertainties, see section 6.1. Relative standard uncertainty associated, $1 \cdot {10^{ - 8}}$ and $1.6 \cdot {10^{ - 8}}$ resp. for DB1 campaign and W1 campaign

‘Current correction’: correction applied to take into account the influence of the current flowing into the coil (during the static phase only) on the determination of the geometric factor, see section 6.2. Relative standard uncertainty associated, $5 \cdot {10^{ - 9}}.$

‘Beam: parasitic forces’: the horizontal forces exerted on the coil generate a bias in the comparison between the weight of the test mass and the electromagnetic force, see section 6.3.2. The relative standard uncertainty associated is ${\text{ }}1.5 \cdot {10^{ - 9}}$.

‘Beam: $z$ error’: The end of the beam does not occupy the same vertical position during successive weighings which causes a bias due to the non-zero stiffness of its pivots. The relative standard uncertainty associated is $8 \cdot {10^{ - 9}}$.

‘Parasitic watt ratio error’: perfect alignment of the coil with respect to the magnetic circuit is impossible. Therefore, in addition to the vertical force ${F_z}$, parasitic horizontal forces and parasitic torques are exerted on the coil (typically lower than 50 µN and 50 µNm). Also, a perfect vertical trajectory of the coil is impossible. Therefore, the movement of the coil during dynamic is describe not only by ${v_z}$, but also by parasitic horizontal velocities and parasitic angular velocities (typically lower than 0.5 µm s<sup>−1</sup> and 0.5 µrad s<sup>−1</sup>). The watt ratio error is an estimation of the contribution of each misalignment and its associated motion to the measured voltage in the moving part of the experiment. The relative standard uncertainty associated $8 \cdot {10^{ - 9}}$.

‘Resistance value’: during the static phase, a 200 Ω resistor is connected in series with the coil and the current injected in the circuit is measured through the voltage drop across the resistor. This resistor placed in a thermostatically controlled enclosure (within ±50 mK) was calibrated against the QHRS before, during and after the two measurement campaigns. ‘Resistance value’ gives the total relative standard uncertainty associated with the resistance determination, comprised of calibration, stability and interpolation. The relative standard uncertainty associated is $5 \cdot {10^{ - 9}}$.

‘Velocity’: this term refers to the uncertainty in measuring the vertical velocity of the coil, mainly due to the alignment on verticality of the interferometric beams, see section 6.3.1. The relative standard uncertainty associated is $1 \cdot {10^{ - 8}}.$

‘Absolute gravity value’: gravity in the Kibble balance laboratories is continuously monitored with a superconducting gravimeter (iGrav#005 [16]), which is regularly calibrated and drift corrected with an absolute cold atom gravimeter (CAG) [17] and commercial AQG-B01, FG5X#206 and FG5#228 of French park of gravimeters PGrav [18]. This relative gravimeter is located in the gravimetry laboratory next to the LNE Kibble balance laboratory, on the same pillar on which the absolute gravimeters operate. ‘Absolute gravity value’ is the total standard uncertainty due to gravity, comprised notably of gravity measurement, gravity transfer and self gravity of the LNE-KB apparatus. Relative standard uncertainty associated $5 \cdot {10^{ - 9}}.$

‘Voltage’: this term takes into account the uncertainties due to the Josephson reference, the voltmeters (gain and non-linearity) and the switch-box. Relative standard uncertainty associated $1 \cdot {10^{ - 8}}.$

‘Field gradient’: this term expresses the uncertainty associated with the difference in position of the coil between the static and dynamic phases. Relative standard uncertainty associated $1 \cdot {10^{ - 9}}.$

‘Fit’: this term gives the uncertainty associated with the choice of polynomial order and fitting limits. See section 6.4. Relative standard uncertainty associated $1.5 \cdot {10^{ - 8}}.$

Some contributions are described with more details in the following paragraphs.

### 6.1. Statistical

In particular for determinations spanning several weeks, as is the case for the determinations presented here, a stationary process cannot be assumed *a priori*. Thus, the standard deviation of the mean result cannot be determined as standard deviation of the sample divided by the root square number of data points.

A more robust estimator of the standard deviation of the mean (i.e. the evaluation of Type A uncertainty for these determinations) is the Allan deviation as mentioned in [19] section 4.2.3.

Here, we estimate the Type A uncertainty associated with each mass determination as the minimum value of the overlapping Allan deviation. Moreover, since individual mass measurements are obtained using a $Bl_{{\text{stat}}}^{{t_1}} - Bl_{{\text{dyn}}}^{{t_2}} - Bl_{{\text{stat}}}^{{t_3}}$, $Bl_{{\text{dyn}}}^{{t_2}} - Bl_{{\text{stat}}}^{{t_3}} - Bl_{{\text{dyn}}}^{{t_4}}$ scheme, they are not independent. To eliminate these correlations, three independent mass populations are extracted from the individual mass determinations, and the overlapping Allan deviation is calculated for each population. Finally, a root mean square is computed from these three standard deviations values.

Ultimately, the Type A uncertainty of DB1 and W1 mass determination is evaluated at $1 \cdot {10^{ - 8}}$ and $1.6 \cdot {10^{ - 8}}{\text{ }}$, see figure 7. Each of these measurement campaign has lasted several tens of days. Even if it is entirely possible to find within these data 10 d sequences that produce Type A uncertainty estimates on the order of $1 \cdot {10^{ - 8}}$, continuing the measurements over much longer durations allows for the consideration of weekly-scale variations in measured values—regardless of the origin of these variations: external disturbances or the difficulty in maintaining a perfectly stable experimental environment—in order to make the Type A evaluation both robust and meaningful, and to ensure the reliability of the mean value calculated from the dataset.

![Figure 7](10.1088_1681-7575_ae1dfc_assets/metae1dfcf7_hr.jpg)

**Figure 7.** Experimental standard deviation of the mean estimated by Allan deviation of the data for W1 and DB1 mass measurements. The relative Type A standard uncertainties (which are the value of the relative Allan deviation) are respectively $1.6 \times {10^{ - 8}}$ and ${\text{ }}2.2 \times {10^{ - 8}}$.

The difference measured between the two campaigns in terms of relative Type A standard uncertainty can be explained by an increase in the mechanical noise due to the measurement period (the beginning and end of the year are always marked by a significant increase in noise levels in the laboratory) and major construction work carried out outside the building.

### 6.2. Coil current effect

The equality of the geometric factors in the weighing ${\text{ }}B{\ell _{{\text{stat}}}}$ and velocity ${\text{ }}B{\ell _{{\text{dyn}}}}$ modes is not true if we consider the coil flux in the weighing mode [20, 21]. Generally, the change in $B\ell$ due to the coil flux can be expressed as a function of the weighting current:

**Equation 18.**

$$
\begin{equation}{\text{ }}B{\ell _{\text{stat}}} = {\text{ }}B{\ell _{dyn}} \cdot \left({1 + \alpha \cdot I + \beta \cdot {I^2}} \right)\end{equation} \tag{ 18 }
$$

where $\alpha$ and $\beta$ are the linear and non-linear coefficients.

The non-linear term $\beta$ has not yet been studied but it is supposed to be negligible as it is for all the Kibble balance considering their accuracy in the order of $1 \times {10^{ - 8}}$ [20–22]. The linear term $\alpha$ depends on the vertical position of the coil and can be therefore different for measurements realized during the static phase: ${\alpha _{{\text{on}}}}$ for mass-on and ${\alpha _{{\text{off}}}}$ for mass-off.

A special feature of the LNE Kibble balance is that the force comparator (balance beam and its suspension) can be moved as a single element by means of a translation stage. We use this feature to compensate for the difference in coil position between the two weighing states, which arises from elasticity of the coil suspension. Indeed, the suspension elongates by about ten micrometers when the current is reversed. Figure 8 shows the difference in coil vertical position during the fifteen static phases which occur in a typical run of one day. The static phases consisting of 5 weighing sessions are separated by dynamic phases. Results show that both measurements mass-on and mass-off take place at the same position to within 30 nm.

![Figure 8](10.1088_1681-7575_ae1dfc_assets/metae1dfcf8_hr.jpg)

**Figure 8.** Coil vertical position difference from mass on to mass off (${z_{{\text{on}}}} - {z_{{\text{off}}}}){\text{ }}$ during 15 static phases (each phase consists of 5 weighings): average value is 30 nm.

It means that the linear coefficient $\alpha$ can be considered identical in both configurations: ${\alpha _{{\text{on}}}} = {\alpha _{{\text{off}}}}{\text{ }}$. In our experiment, the relative error due to the coil current effect depends only on the product of the linear coefficient by the current asymmetry during mass-on and mass-off. The two suspensions have been equilibrated to have a current asymmetry of better than 2 µA on the two measurement campaign. The linear coefficient has been experimentally estimated to be $8 \cdot {10^{ - 6}}{\text{ m}}{{\text{A}}^{ - 1}}$. A maximum correction of $1.6 \cdot {10^{ - 8}}$ has been applied and the corresponding relative standard uncertainty $5 \cdot {10^{ - 9}}$, considering a rectangular distribution.

### 6.3. Alignments

The main alignment procedures—alignment of the translation stage, alignment of the points of application of the gravitational and Laplace forces, alignment of the coil—have been described extensively elsewhere [15–18, 20–22]. Here, we present the two notable improvements done in terms of alignments since last publications.

#### 6.3.1. Alignments of the laser beams to vertical

The directions of the six laser beams (three for the heterodyne interferometers and three for the position sensors ‘Gaussian beams’) that measure the coil velocities and positions have to be aligned along the vertical direction *z* defined by the direction of the acceleration due to gravity *g*.

To align the laser beam of each position sensor, a partial reflector, a corner-cube reflector and an alcohol pool are added. Part of the measurement beam is reflected directly to a corner-cube reflector and the other part passes through the partial reflector and is intercepted by an alcohol pool. Both reflected laser beams from the corner-cube reflector and from the alcohol pool travel through a refracting telescope associated with a CCD camera. The direction of the laser beam is adjusted to superimpose both beams on the camera.

A similar method, but requiring only the alcohol pool, is adopted to align the laser beam of each heterodyne interferometer.

During the two measurement campaigns in 2024, a special effort was made to check beam alignments ‘continuously’, *i.e*. at every liquid helium Dewar change. Checks are performed in air, while measurements are carried out in vacuum: studies have shown an almost total stability of the mechanical structure from air to vacuum. Regular checks carried out, as well as study of long term comportment have consolidated the measurements. The total uncertainty of the alignment procedure has been evaluated as less than 100 µrad.

Considering a cosine error, this translates to a relative uncertainty associated to the velocity measurement of $0.5 \times {10^{ - 8}}$.

#### 6.3.2. Alignment of the pivots of the balance beam

The pivots of the beam must be aligned and placed horizontally. Horizontality is critical because the comparator is not used as a mass comparator but rather as a force comparator. If there is a vertical distance between the pivots of the beam, a parasitic force perpendicular to the longitudinal beam axis produces a parasitic torque which introduces a bias in the estimation of the product $B{\ell _{{\text{stat}}}}$ during the static phase. This torque is proportional to the product of the vertical distance between the pivots by the horizontal parasitic force [22].

The beam is a 20 mm long single-piece beam from a special aluminum alloy EN AW-7075 T651 designed with three flexures hinges formed by symmetrical 40 µm-thick bi-concave profiles [8]. The central hinge is a double hinge to strongly reduce the torsion effect.

To reduce unwanted force during static phase, the beam must balance as close to its horizontal position in order to not be sensitive to horizontal parasitic forces. Indeed, the aim of the static phase is to measure a vertical force ${F_z}$ without bias. However, if a parasitic force ${F_x}$ (horizontal and parallel to the longitudinal axis of the beam) is exerted at the end of the beam, with the axis from the central hinge to the arm end hinge separated from the horizontal by an angle $\alpha$, a relative biais ${\varepsilon _{{F_z}}}$ on ${F_z}$ appears [1]:

**Equation 19.**

$$
\begin{equation}{\varepsilon _{{F_z}}} = {{\alpha }}\frac{{{F_x}}}{{{F_z}}}.\end{equation} \tag{ 19 }
$$

The challenge remains to be able to match the two centers of rotation of the beam with the horizontal line in order to maintain ${\varepsilon _{{F_z}}}$ on the order of 10 ppb.

In 2024, this error was estimated by a new method which requires:

1. The environmental conditions to be stable: the whole balance must have reached, in vacuum, a thermal equilibrium, in particular the magnetic circuit. Four heating resistors driven by a regulation system can maintain the temperature of magnetic circuit at a fraction of millikelvins for days in a row.

2. The measurement of the vertical position of the coil with respect to the vertical: the directions of the six laser beams monitoring the position of the coil must be aligned with vertical in order to access to its position in frame of reference where the vertical axis $z$ is actually vertical, and the plane $xOy$ is actually horizontal (figure 9).

![Figure 9](10.1088_1681-7575_ae1dfc_assets/metae1dfcf9_hr.jpg)

**Figure 9.** Schematic view of the experimental set up for alignment of the pivots of the balance beam. From top to bottom: balance beam, coil suspension, coil immersed in the magnetic circuit.

Once these conditions are met, the method consists in monitoring and correlating the coil displacement (with respect to the six laser beams) with the beam position (with respect to the interferometer targeting the beam’s end) during a weighing phase when a very low frequency ($\sim5 \cdot {10^{ - 5}}$ Hz) sinusoidal setpoint is applied to the beam position.

If the coil is hanging vertically and its sensor’s Gaussian beams are also vertical, then the coil position in the horizontal plane will reach an extremum when the beam crosses its horizontal position (figure 9). During the process the beam end path travels along an arc of circle whose vertical projection is the coil trajectory. Even if the beam’ *s* axis of rotation is itself tilted with respect to the horizontal, the trajectory of the coil continues to present a turnaround point when the horizontality of the beam is crossed.

The beam can be balanced between two mechanical stops spaced 1 mm apart, the lower one being the position reference (0 µm). A current is injected and adjusted in the coil in order to slowly oscillate the beam with 0.8 mm amplitude at it is end. The vertical motor of the translation stage is commanded to move in an opposite way to always nullify the vertical coil motion with respect to the magnet circuit gap. Simultaneously, the three Gaussian beam signals are acquired with an integration time of 10 s and converted to *x* and *y* positions. Figure 10 shows in its left part, the evolution of the vertical imposed displacement of the beam end versus time; in the right part the blue line represents the corresponding measured horizontal excursion of the coil. As expected, the coil reaches repeatedly (8 times) an extremum. The coil trajectory can be locally and fitted to a parabola (orange line) and finally the horizontal beam position can be extracted (red line), in this case at 455 µm.

![Figure 10](10.1088_1681-7575_ae1dfc_assets/metae1dfcf10_hr.jpg)

**Figure 10.** (left) Low frequency sinusoidal movement of the beam (right) Vertical beam displacement according to horizontal coil displacement during a horizontality beam determination (blue line), fitted with a circle (orange line). The vertical asymptote of the fitted curve indicates the horizontal position of the beam.

Measurement repeatability is of the order of 10 µm: considering the estimated parasitic horizontal forces, the uncertainty associated is 1.5 × 10<sup>−9</sup>. It was 2 × 10<sup>−8</sup> in 2017.

### 6.4. Polynomial fi t

The geometric profile obtained at each dynamic phase (see figure 11) is a table of $Bl$ values indexed by the measurement altitude *z*. To determine the geometric profile value at the weighing point altitude, a polynomial fit is used. Without theoretical model of the geometrical factor, any order can been chose *a priori*. A study of spatial properties of the profile gives a lower limit of the order which is needed for a particular width of the profile. The uncertainty associated to the choice of the couple order/width, from a dozen of such couples, is calculated at 1$.5 \cdot {10^{ - 8}}$.

![Figure 11](10.1088_1681-7575_ae1dfc_assets/metae1dfcf11_hr.jpg)

**Figure 11.** Typical spatial values of the geometric factor $B{l_{{\text{dyn}}}}$ from 60 up and down trajectories averaged.

## 7. Conclusion

Two mass determinations were performed using the LNE Kibble balance in the summer and autumn of 2024, with two standards: a pure iridium standard (DB1) and a platinum-iridium standard (W1).

The uncertainty budget is nearly half that of 2017. It has been consolidated by accounting for a greater number of influencing factors and significantly reduced through vacuum operation, improved alignment and mechanical stability, and a substantial reduction in measurement noise.

The DB1 standard was measured at 500 g + 42 µg ± 16 µg, while the W1 standard was measured at 500 g + 179 µg ± 18 µg. The corresponding relative combined standard uncertainties are 3.1 · 10<sup>−</sup><sup>⁸</sup> and 3.5 · 10<sup>−</sup><sup>⁸</sup>, respectively, and are consistent compared to the mass maintained by the LNE.

The W1 standard was used to calibrate a 1 kg PtIr standard for participation in the CCM.M-K8.2024 comparison.

## Acknowledgment

A multidisciplinary experiment of such ambition requires the skills and contributions of many individuals over many years of effort. Over the years, the LNE Kibble balance team has benefited from the expertise of numerous people—either directly as team members or more indirectly but no less essentially as external experts. We send our sincere thanks to all of them.

## Contributions

F. B. is in charge of the mass department of LNE, and provides the W1 and DB1 standards. N. A. and S.M. are in charge of the gravimetry. M. Th., D. Z. and P. E. are responsible for primary mass metrology at LNE. F. C. and M. Ta. are responsible of the primary resistance laboratory and performed the calibrations of the transfer resistance standard through comparison with the Quantum Hall Resistance Standard used. M.Th, K. D. and P.E. carry out the mechanical adjustment and tuning of the LNE Kibble balance. M.Th. and D. Z. develop software to analyse results. D. Z. develops software to control instrumentation. K.D. carries out mechanical engineering. M.Th., D. Z. and P.E. plan, conduct and analyse the results. M.Th., D. Z. and P.E. finalised this study and wrote the paper. All authors read and approved the final manuscript.

**Figure 5. Upper graph: A one-day typical run with alternating and of determinations. Lower graph: relative standard deviations of and of**

**Figure 7. Experimental standard deviation of the mean estimated by Allan deviation of the data for W1 and DB1 mass measurements. The relative Type A standard uncertainties (which are the value of the relative Allan deviation) are respectively and.**

**Figure 8. Coil vertical position difference from mass on to mass off (during 15 static phases (each phase consists of 5 weighings): average value is 30 nm.**

**Figure 11. Typical spatial values of the geometric factor from 60 up and down trajectories averaged.**

## References (22 total, showing 22)

1. Thomas M, Espel P, Ziane D, Pinot P, Juncar P, Santos F P D, Merlet S, Piquemal F, Genevès G 2015 First determination of the Planck constant using the LNE watt balance Metrologia 52 433 doi:10.1088/0026-1394/52/2/433
2. Stock M, others 2017 Report on CCM pilot study CCM.R-kg-P1: comparison of future realizations of the kilogram
3. Thomas M, Ziane D, Pinot P, Karcher R, Imanaliev A, Santos F P D, Merlet S, Piquemal F, Espel P 2018 A determination of the Planck constant using the LNE Kibble balance in air Metrologia 54 468 doi:10.1088/1681-7575/aa7882
4. Kibble B P 1975 Atomic Masses and Fundamental Constants Springer vol 5 doi:10.1007/978-1-4684-2682-3_80
5. Thomas M, Espel P, Dougdag K, Ziane D Mass measurement noise improvement of the LNE Kibble balance, from 2017 to 2024
6. Haddad D, Juncar P, Pinot P, Genevès G 2007 Absolute position sensor using Gaussian beam propagation properties and their spatial modulation Proc. SPIE 6585 65850U doi:10.1117/12.723033
7. Villar F, David J, Genevès G 2011 75 mm stroke flexure stage for the LNE watt balance experiment Precis. Eng 35 693-703 doi:10.1016/j.precisioneng.2011.06.003
8. Pinot P, Espel P, Liu Y, Thomas M, Ziane D, Palacios-Restrepo M-A, Piquemal F 2016 Static phase improvements in the LNE watt balance Rev. Sci. Instrum 87 105113 doi:10.1063/1.4964293
9. Genevès G, Gournay P, Hauck C, Djordjevic S, Behr R 2006 Characterisation of a SINIS programmable binary Josephson junction array as a reference for the French watt balance experiment
10. Gournay P, Genevès G, Alves F, Besbes M, Villar F, David J 2005 Magnetic circuit design for the BNM Watt balance experiment IEEE Trans. Instrum. Meas 54 742-5 doi:10.1109/TIM.2004.843072
11. Merlet S, Kopaev A, Diament M, Geneves G, Landragin A, Pereira Dos Santos F 2008 Micro-gravity investigations for the LNE watt balance project Metrologia 45 265 doi:10.1088/0026-1394/45/3/002
12. Jiang Z, others 2012 The 8th international comparison of absolute gravimeters 2009: the first key comparison (CCM.G-K1) in the field of absolute gravimetry Metrologia 49 666 doi:10.1088/0026-1394/49/6/666
13. Robinson I A, Schlamminger S 2016 The watt or Kibble balance: a technique for implementing the new SI definition of the unit of mass Metrologia 53 A46 doi:10.1088/0026-1394/53/5/A46
14. CCM 2019 Detailed note on the dissemination process after the redefinition of the kilogram (CCM)
15. Thomas M 2015 PhD Thesis
16. Merlet S, Pereira dos Santos F 2020
17. Merlet S, Gillot P, Cheng B, Karcher R, Imanaliev A, Timmen L, Pereira Dos Santos F 2021 Calibration of a superconducting gravimeter with an absolute atom gravimeter J. Geod. 95 62 doi:10.1007/s00190-021-01516-6
18. Merlet S, others 2024 French gravimetry organization and its instrumental park IEEE Instrum. Meas. Mag. 27 24-31 doi:10.1109/MIM.2024.10654723
19. Joint Committee for Guides in Metrology 2008 Evaluation of measurement data—Guide to the expression of uncertainty in measurement JCGM 100 1-116
20. Li S, Bielsa F, Stock M, Kiss A, Fang H 2018 Coil-current effect in Kibble balances: analysis, measurement and optimization Metrologia 55 75 doi:10.1088/1681-7575/aa9a8e
21. Haddad D, Seifert F, Chao L S, Possolo A, Newell D B, Pratt J R, Williams C J, Schlamminger S 2017 Measurement of the Planck constant at the National Institute of Standards and Technology from 2015 to 2017 Metrologia 54 633 doi:10.1088/1681-7575/aa7bf2
22. Robinson I A, Kibble B 2007 An initial measurement of Planck’s constant using the NPL Mark II watt balance Metrologia 44 427-40 doi:10.1088/0026-1394/44/6/001
