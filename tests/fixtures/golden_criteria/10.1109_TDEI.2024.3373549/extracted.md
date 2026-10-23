---
title: "Nonlinear Traits of Leakage Current and Dynamic Actions of Surface Discharges on Ice-Covered Insulators Under DC Voltages"
authors: "Yong Liu, Chao Li, Fanghui Yin, B. X. Du, Masoud Farzaneh"
journal: "IEEE Transactions on Dielectrics and Electrical Insulation"
doi: "10.1109/tdei.2024.3373549"
published: "June 2024"
source: "ieee_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 10780
---

# Nonlinear Traits of Leakage Current and Dynamic Actions of Surface Discharges on Ice-Covered Insulators Under DC Voltages

**Abstract.** In order to improve the technology for predicting flashover risks of ice-covered insulators, this article delves into the nonlinear characteristics of leakage current (LC) and the phase changes of arcing discharges. The dynamic relationship between them is analyzed quantitatively. The dc ice flashover experiment is conducted in the CIGELE artificial climate room. The dynamic characteristics of arcs during the dc ice flashover process were studied. The chaos of the LC time series is examined by estimating the maximum Lyapunov exponent (${L}_{\text {max}}$) using embedded space theory and the phase space reconstruction method. An analysis of the dynamic behavior of LC is conducted using recurrent plot (RP) technology, leading to the development of an index to quantify the regularity of the LC. A quantitative analysis of the cooperative relationship between the LC and arc length, as extracted through image processing, is performed, confirming the regular patterns of LC variation. The findings indicate that variations in the LC and arc length are effective in distinguishing between the three stages of ice flashover. ${L}_{\text {max}}$ exceeds zero at all stages, indicating the chaotic nature of the LC, which is most pronounced during the early phase of the second stage. RP technology provides a clear, dynamic visualization of icing insulator discharge behavior through graphic texture transformation. The nonlinear indexes, RR and DET, of LC, demonstrate an increase alongside the development of arc discharge, indicating a growth of the regular and deterministic components of the discharge. Additionally, there is a synchronous increase in the LC and arc length, with a clear correlation exhibited during the four arc extension periods (T1–T4). As the flashover approaches, the degree of fitting between them increases significantly.

## Introduction

The reliability of high-voltage insulators in outdoor conditions is paramount to the safe and stable operation of the power transmission system. In cold regions, the icing of insulators can pose serious threats. It may lead to arc discharges and even ice flashovers in the worst conditions<sup>1</sup>. Extensive research has been carried out to study the features and processes concerning the flashover performance of ice-covered insulators. Consequently, well-established experimental and mathematical models have been developed with the aim of predicting the flashover voltage of ice-covered insulators<sup>2</sup>. Currently, much literature is devoted to the development of state detection methods aimed at preventing ice flashovers. The primary objectives of these efforts are as follows: 1) Measure and analyze the surface leakage current (LC) during the icing and melting process; 2) Establish diagnostic criteria for detecting the degree of icing severity; and 3) Analyze the development characteristics and mechanism of surface discharge arc, as well as establish ice flashover model to predict the probability of flashover occurrence<sup>3</sup>.

Previous research suggested that the LC can reflect the comprehensive effects of icing severity, operating voltage, and environmental parameters. It could also systematically provide insight into the level of surface icing on the insulator<sup>4</sup>; furthermore, extracting the LC characteristics in the time-frequency domain could uncover the correlation between icing speed, melting speed, threshold variation patterns of arc discharge, flashover, and environmental factors like ice thickness and icing type<sup>5</sup>. The time-frequency characteristics of the LC were closely linked to arc characteristics. The intensity of the discharge arc varied periodically with the flow of the LC across the insulator surface<sup>6</sup>. The ice flashover process can be divided into four stages. Amplitude fluctuation and waveform change of LC corresponded to irregular discharge behavior on insulator surfaces, directly linked to surface characteristics of ice-covered insulators. Because of the randomness of surface discharge of ice-covered insulators, the development and evolution characteristics of discharge arc still need further study<sup>7</sup>. At present, the research on surface arc dynamics of ice-covered insulators mainly focuses on two aspects: First, the arc development and evolution process. The flashover of ice-covered insulators starts from the local arc in the gap, and the arc develops along the ice surface with the increase of voltage and the conductivity of melted ice water<sup>8</sup>. Second, the flashover path is influenced by factors such as melting icicles, falling ice and different shed structures, which will change the flashover path of insulators and further affect the flashover voltage<sup>9</sup>.

The investigation based on the characteristics of the LC and dynamic actions of discharge of ice-covered insulators is of great value to the prediction of ice flashover risk; however, during ice flashover, surface discharge behavior occurs randomly, and the LC as a nonlinear time series is complex and irregular, making it difficult to accurately match the surface discharge activity of the insulator. The actual insulator shape and structure are complex, and the uncertainty and complexity of the development of insulator ice surface and air gap arc are different from that of regular icicle ice surface arc<sup>10</sup>. Additionally, the relationship between LC and surface discharge behavior is still in the qualitative description stage. Analyzing the motion characteristics of icing arc of insulators in operation and the LC nonlinear traits and establishing a quantitative relationship between surface discharge behavior and LC are, therefore, critical necessities in strengthening the detection technology of ice-covered insulators.

Based on the indoor ice flashover experiment under dc voltage, this article studies the dynamic characteristics of LC and arc characteristics obtained through image processing at various stages. The chaos and nonlinear properties of the LC are examined by applying the embedded space theory with the phase space reconstruction method and recurrent plot (RP) technology, respectively. LC’s regularity changes are confirmed through the collaborative quantitative analysis of both LC and arc characteristics.

## Experimental Setup and Test Procedure

### A. Experimental Setup and Sample Specification

The experimental sample consists of five XP-70 suspension porcelain insulators. Fig. 1 depicts the Layout of the experimental setup. The artificial refrigeration chamber is equipped with cooling, spray, and airflow modulation systems. The adopted high-voltage dc power system possesses a designated voltage of 120 kV and a rated power of 240 kVA. The National Instrument PCI-6251 DAQ device and LabVIEW software are used to simultaneously record the *LC* and applied voltage. The experimental setup and parameter settings adhere to the IEEE 1783/2009 standard. Table I shows the vital parameters pertaining to the experiment involving the icing of insulators. The surface of the samples was thoroughly cleansed using deionized water and subsequently dried under ambient conditions (20 °C). Subsequently, the insulators were placed within a cold chamber set at −12 °C for a duration exceeding 16 h. Before the icing process, the insulator strings were subjected to a 75 kV dc voltage. After that, a mixture of deionized water and sodium chloride was uniformly dispersed onto the surface of the insulators at a wind speed of 3.2 m/s by means of an atomizing nozzle. The conductivity of the solution was $30~\mu \text{S}$/cm at 20 °C, and the spraying duration lasted for an hour. Afterward, the voltage gradually increased at a rate of 3.0 kV/s. After reaching the estimated flashover voltage, the current-voltage level was maintained for 15 min. The experiments were conducted with a sampling frequency of 10 kHz. A high-speed camera capturing 256 gray levels recorded the insulator surface discharge phenomenon at a rate of 6000 frames per second (fps). Because of the influence of the working environment and the equipment itself, the collected LC contains a lot of noise and needs to be smoothed. Wavelet transform is suitable for processing this kind of nonsmooth signal. According to the characteristic that the LC is an asymmetric signal, the db4 wavelet basis function is chosen and decomposed according to the optimal decomposition layer criterion. It can effectively decompose the main components of the LC into approximate components and the noise into detailed components.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu.t1-3373549-large.gif)

**TABLE I** Parameters of Insulator ICING Experiment

![Figure 1](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu1-3373549-large.gif)

**Figure 1.** Layout of experimental device.

### B. Image Manipulation and Extraction of Arc Features

Conventional image processing and morphological processing are synergistically employed to augment the clarity of the image, as depicted in Fig. 2. Initially, a $3\times3$ median filtering method is employed for image denoising, resulting in the outcome illustrated in Fig. 2(b). Because of the blurring effect caused by the denoising process, a power transformer is applied to conduct a nonlinear grayscale transformation. This enhances the image’s contrast and sharpness while maintaining distinct grayscale variations between pixels. The enhanced image is illustrated in Fig. 2(c). During the edge segmentation stage, conventional image processing methods employing different edge detection operators may exhibit varying degrees of difficulty in accurately extracting noisy regions. Consequently, a marker-controlled watershed algorithm based on morphology is employed. As depicted in Fig. 2(d), a closed and precise arc contour is obtained. Finally, the fill algorithm is used to fill the arc edge image, thereby obtaining the arc region. Subsequently, the arc’s length is extracted from the region, as demonstrated in Fig. 2(e). The perimeter of the arc is the contour perimeter of Fig. 2(d). The length of the arc curve can be obtained by dividing the circumference of the extracted arc profile curve by two.

![Figure 2](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu2abcde-3373549-large.gif)

**Figure 2.** Schematic of the experimental setup. (a) Original image. (b) Image denoising. (c) Image enhancement. (d) Edge segmentation. (e) Image fill.

## Surface Discharge of Ice-Covered Insulators

### A. Flashover Process of Ice-Covered Insulators

Fig. 3 shows the time waveform of the arc and the detected voltage and current changes from the period of stable discharge on the surface of the iced insulator to flashover. It has experienced three stages: arc formation, arc development, and right before flashover.

![Figure 3](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu3abc-3373549-large.gif)

**Figure 3.** Recorded LC, the measured voltage, and the length of arc at different stages. (a) Measuring LC and voltage at −DC. (b) Measuring LC and voltage at +DC. (c) Length of arc.

In stage I, the dominant discharge mode is corona discharge, and the occurrence of filamentary partial discharge leads to a sawtooth feature in voltage and current waveforms, as illustrated in Fig. 3(a) and (b). Although the transition from corona discharge to arc discharge initiates during this phase, the duration of arc discharge remains very short, resulting in a stable LC amplitude of around 14 mA under-dc voltage. Additionally, the weak arc obtained through image processing maintains a stable length at this stage, with average values of 41.89 and 30.24 mm for positive and negative dc voltages, respectively, as shown in Fig. 3(c).

During stage II, which spans from 3.15 to 3.29 s in Fig. 3(b), the LC rises from 6.97 to 21.15 mA while the measured voltage drops from 100.78 to 84.95 kV. The Joule heat of LC raises the conductivity of the water film by melting the icicles. Upon reaching a certain threshold, the measured voltage drops dramatically, denoting a transition from a corona discharge to an arc discharge. Afterward, the LC and measured voltage returns to normal levels, as indicated in Fig. 3(b). This occurs because the arc attains a critical size when the energy provided by the power supply to the arc plasma is lower than the heat loss of the arc column. Once this happens, the arc can no longer continue to develop, and the corona discharge mechanism is reinstated. The comparison of Fig. 3(a) and (b) reveals that negative dc voltage results in substantially increased discharge activity during stage II. As a matter of fact, the arc appearance and development frequency is greater during negative dc voltage compared to that observed under positive dc voltage.

At stage III, the electric field intensity at the arc head significantly increased. As a result, a significant amount of charge is transferred to the ice surface, causing the LC to spike and lead to flashover. In Fig. 3(b), the LC increases from 8.29 to 720.3 mA between 5.31 and 5.41 s. In Fig. 3(a), the LC rises from −23.89 to −522.1 mA during 6.20 and 6.25 s. In ten flashover experiments, the spark discharge occurs spontaneously when the leakage distance increases to 41%–52% and 46%–59% of the total distance under both positive and negative dc voltages, respectively. A concentrated discharge channel emerged, resulting in a transient larger current. The inherent instability of the spark discharge leads to obvious pulse characteristics. Based on Fig. 3(a) and (b), the repetitive discharge frequencies at positive and negative dc voltages are 333 and 833 Hz, respectively, while the corresponding maximum peak values are measured to be 720.3 and 522.1 mA, correspondingly, during the flashover period.

### B. Generation and Development of Ice-Covered Insulator Arc Under Positive DC Voltage

Based on several flashover experiments, it is found that the discharge process of ice-covered insulators under positive dc voltage is, as shown in Fig. 4. First, the discharge mode is corona discharge, then the partial discharge arc appears between the steel foot strong field and the icicle of No.5 insulator, and develops to the grounding end \[Fig. 4(a)\], and then the arc appears between the icicle of the No.1 shed and the ice layer of the No.2 shed and spreads to the shed No.3 insulator. The joule thermal effect of current and arc heating causes the ice layer to melt, the air gap voltage to rise, and arc discharge to occur at the grounding end \[Fig. 4(b) and 4(c)\]. Then, the main discharge channel is formed from the ice layer of shed No.4 insulator to the surface of shed No.5 insulator icicle. There are many discharge channels in the development of the arc foot on the ice surface, and there are many branches near the contact point of the ice surface. At the same time, influenced by factors such as thermal buoyancy, electrostatic force, and collision ionization, the arc appears to have elongation, attenuation, bending, and floating, as shown in Fig. 4(g). When the arc column of the arc deviates greatly, the energy provided by the power supply for the arc plasma will be lower than the heat loss of the arc column, which will lead to a decrease in the temperature of the arc plasma and the conductivity of the arc column, and the equilibrium state of arc discharge cannot be maintained. At this time, the arc channel will be extinguished \[Fig. 4(g)–(i)\], or a new discharge path will be formed, which will lead to the arc attenuation. Through experiments, two ways of arc attenuation were found.

- When the arc develops to the grounding end of the ice-covered insulator, the arc column gradually approaches the ice surface of the shed, and when it is about to touch the ice surface, a new bright white filamentary arc is generated and extends to the ice surface. The arc discharge channel between the original contact point and the new contact point quickly darkens until it disappears, and the radius of the arc column of the new discharge channel between the new contact point and the arc root is almost unchanged, and the brightness is improved \[Fig. 4(e)–(f)\]. Because the new discharge path connects the ice surface with the arc column, it is called “contact attenuation.”
- With the development of the arc, the local arc between the sheds in the middle of the series insulator and the grounding terminal will be seriously deviated due to the influence of thermal buoyancy in the area with low plasma density. Several flashover experiments show that the new discharge path always forms at the arc column near the arc root and develops toward the arc column near the arc foot \[Fig. 4(j) and (k)\], the arc column is bridged, the original arc is transferred to the new path, the channel is enlarged, and the brightness becomes brighter \[Fig. 4(l)\]. The new path shortens the original arc column, and at this time, the arc development matches the power supply energy. During the attenuation process, the position of the arc root and arc foot basically remains unchanged, and the arc does not touch the ice surface, so it is called “noncontact attenuation.”

![Figure 4](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu4abcdefghijkl-3373549-large.gif)

**Figure 4.** Generation and Development of Local Arc under positive dc Voltage. (a) 0 ms, (b) 233 ms, (c) 236.5 ms, (d) 917.5 ms, (e) 919 ms, (f) 922.5 ms, (g) 3034 ms, (h) 3035.5 ms, (i) 3037 ms, (j) 4061 ms, (k) 4062 ms, and (l) 4063.5 ms.

### C. Generation and Development of Ice-Covered Insulator Arc Under Negative DC Voltage

The discharge process of ice-covered insulators under negative dc voltage is shown in Fig. 5. The blue-purple corona discharge on the lower surface of the high-voltage terminal and the lower surface of the grounding shed turns into yellow-white arc. Because of more discharge activities and accumulated charges on the surface under negative dc voltage, many unstable arc discharge channels and corona discharge areas appear on the high-voltage terminal and the grounding terminal \[Fig. 5(a)\]. The arc discharge path shows obvious randomness between the outside and the inside along the ice layer \[Fig. 5(b) and (c)\]. Because of the severe discharge under negative dc voltage, there is obvious melting and shedding of the ice layer in the process of arc development, which intensifies the reduction of icicles. Compared with the formation of a positive dc arc, it takes a shorter time for a negative dc corona to transform into an arc, and the initial local arc brightness and arc column radius are larger. During ice melting, with the increase of water film conductivity, the radius of the arc column increases, and the arc extinguishes and reignites more frequently when the arc develops toward the grounding end \[Fig. 5(g)–(i)\]. At the same time, the discharge activity is more intense under negative dc voltage and contact attenuation \[Fig. 5(d)–(f)\] and noncontact attenuation \[Fig. 5(j)–(l)\]. For contact attenuation, the new discharge path from arc to ice surface generally develops under positive dc voltage, while from ice surface to arc column, the path develops under negative dc voltage. For noncontact attenuation, the new discharge path is generally the same as the arc foot extension direction under positive dc voltage, while it is opposite to the arc foot development direction under negative dc voltage.

![Figure 5](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu5abcdefghijkl-3373549-large.gif)

**Figure 5.** Generation and Development of Local Arc under negative dc Voltage. (a) 0 ms, (b) 155 ms, (c) 406 ms, (d) 1684.5 ms, (e) 1686.5 ms, (f) 1689 ms, (g) 4125.5 ms, (h) 4126 ms, (i) 4127 ms, (j) 5687.5 ms, (k) 5688 ms, and (l) 5689 ms.

## Nonlinear for Characteristic Analysis of LC

Currently, the monitoring and diagnostic techniques for LC are mainly based on the analysis of its time-domain and frequency-domain characteristics<sup>8</sup>. Methods such as pulse counting, effective value method, accumulated charge method<sup>9</sup>, harmonic components, and power spectral analysis can be used to analyze the features of LC from multiple perspectives<sup>10, 11</sup>. During the flashover process, the discharges on the surface of the insulator, however, occur randomly, and due to the nonlinear time series nature of LC, it possesses complex and irregular characteristics. The characteristic quantities obtained through time-frequency analysis of LC do not accurately correspond to the discharge activity on the insulator’s surface. In contrast, the nonlinear characteristics based on LC can assist in understanding the fundamental mechanism of flashover processes. This article, therefore, employs the recursive graph technique to transform the 1-D nonlinear time series of LC into 2-D matrix data, effectively extracting its nonlinear features for the performance detection of outdoor insulators.

### A. Lyapunov Exponent of LC

Chaotic systems refer to deterministic nonlinear systems exhibiting various characteristic properties. The primary characteristic is their sensitivity to initial conditions, causing trajectories generated by closely spaced initial values in phase space to exponentially diverge over time<sup>12</sup>. The mechanism of a chaotic system responding to the change of initial conditions is the folding and elongation of characteristic points, and folding is used to describe the overall stability of the system, which shows that the distance between chaotic characteristic points is limited; however, the extensibility indicates that there is local instability in the system, specifically the distance between chaotic feature points increases. Folding and elongation lead to the scale diversity of chaotic systems, and the unstable structure and stable periodicity in the system are alternately repeated, which makes it have significant autocorrelation and hierarchy. Lyapunov exponents can reflect this characteristic and provide quantitative descriptions of the state evolution of chaotic systems, enabling multidimensional evaluation of time series. Its definition is as follows.

Take the long-term evolution of an infinitesimal n-dimensional sphere in an n-dimensional phase space as an example. Because of the local instability of the system, the n-dimensional sphere will transform into an ellipsoidal surface. The <em>i</em>th Lyapunov exponent is defined by the length of the principal axis of the ellipsoid, denoted as $p_{i}(t)$
$$
\begin{equation*} L_{i} =\lim _{t\to \infty } \frac {1}{t}\ln \frac {p_{i} (t)}{p_{i} (0)}. \tag{1}\end{equation*}
$$

The magnitude of the Lyapunov exponent indicates the exponential rate of convergence or divergence of nearby trajectories in phase space. In the direction of $L_{i} < 0$, the phase volume contracts, and the motion is stable. In the direction of $L_{i} >$ 0, the long-term behavior is sensitive to initial conditions, and the motion exhibits a chaotic state. $L_{i}$ = 0 corresponds to a stable boundary, which is a critical situation; therefore, if the maximum $L_{i}$ value of a time series is greater than 0, it can be determined as a chaotic sequence.

This article employs a small data quantity method to calculate the maximum Lyapunov exponent ($L_{\mathrm {max}}$) of chaotic time series<sup>13</sup>. Compared to the traditional Wolf method<sup>14</sup>, it does not require the calculation of the entire Lyapunov exponent spectrum of the time series. It only needs to determine the chaotic nature based on whether $L_{\mathrm {max}}$ is greater than 0. The small data quantity method, therefore, has higher computational efficiency and accuracy. The calculation steps are as follows.

- *Calculating Time Delay* $\tau$ *and Embedding Dimension m:* The time delay of the chaotic time series LC is $\tau$, and the embedding dimension is *m*. According to the time-domain characteristics of LC, Takens’ embedding theorem is applied to reconstruct its time series. According to Takens’ phase space reconstruction theory<sup>15</sup>, the reconstructed phase space of the time series LC is represented by the points $X_{i}$
  $$
  \begin{align*}&\hspace {-.5pc} X_{i} =\left ({x_{i},x_{i+\tau },\ldots,x_{i+(m-1)\tau } }\right),\quad X_{i} \in R^{m} \\&\hspace {-2pc} (i=1,2, \ldots,M). \tag{2}\end{align*}
  $$
  Among them, *N* represents the size of the dataset, where $N=M+(m-1)\tau$. The C-C **method** is used to determine the value of $\tau$ and *m*. The steps are as follows.

  - a) First, define the correlation integral of the embedded time series:
    $$
    \begin{align*}&\hspace {-.5pc} C(m,N,r,t)\!=\!\frac {2}{M(M-1)}\!\sum _{I\le i\le j\le M} \theta (r-d_{ij}) \\&\hspace {-4pc} r >0 \tag{3}\end{align*}
    $$
    where, $d_{ij} =\| {X_{i} -X_{j}} \|$, when $x < 0$, $\theta (x)=0$. When $x\ge 0$, $\theta (x)=1$. Vectors in phase space that are less than *r* apart (the distance between $X_{i}$) are referred to as correlation vectors. The proportion of these correlation vectors among all $M(M-1)$ possible pairs is defined as the correlation integral $C(m, N, r, t)$. The study of the C-C algorithm is related to the function *S*
    $$
    \begin{equation*} S(m,N,r,t)=C(m,N,r,t)-C^{m}(1,N,r,t). \,\, \tag{4}\end{equation*}
    $$
  - b) To select the appropriate $\tau$, the time series is divided into *t* subsequences
    $$
    \begin{align*} S(m,N,r,t)=&\frac {1}{t}\sum _{s=1}^{t} \left \{{\vphantom {\left.{-\,C_{s}^{m} (1,N/t,r,t) }\right \}} C_{s} (m,N/t,r,t)}\right. \\&\qquad \quad \left.{-\,C_{s}^{m} (1,N/t,r,t) }\right \}\quad \tag{5}\end{align*}
    $$
    when $N\to \infty$
    $$
    \begin{align*} S(m,r,t)=\frac {1}{t}\sum _{s=1}^{t} {\left \{{{C_{s} (m,r,t)-C_{s}^{m} (1,r,t)} }\right \}}. \tag{6}\end{align*}
    $$
    when processing actual sequences, the zero crossing points of $S(m, r, t)$ or the time corresponding to the smallest difference in ${S(m, r, t)}$ for different radii are selected as local maximum time intervals. The difference between the maximum and minimum values of *r* is defined as
    $$
    \begin{align*}&\hspace {-.5pc} \Delta S(m,t)=\max \left \{{{S(m,r_{j},t,N)} }\right \} \\&\hspace {-4pc} -\min \left \{{ {S(m,r_{j},t,N)} }\right \}. \tag{7}\end{align*}
    $$
  - c) According to the statistical conclusion, let *m* = 2, 3, 4, 5, $r_{j} ={i\sigma }/{2}$, $i= 1, 2, 3, 4$. The formula is as follows:
    $$
    \begin{align*} \overline S (t)&=\frac {1}{16}\sum _{m=2}^{5} {\sum _{j=1}^{4} {S(m,r_{j},t)}} \tag{8}\\ \Delta \overline S (t)&=\frac {1}{4}\sum _{m=2}^{5} {\Delta S(m,t)} \tag{9}\\ S_{\textrm {cor}} (t)&=\Delta \overline S (t)+\left |{ {\overline S (t)} }\right |. \tag{10}\end{align*}
    $$
    Fig. 6 shows three corresponding curves for [(8)–(10)](https://ieeexplore.ieee.org/rest/document/10459335/?logAccess=true#deqn8-deqn10). Taking the LC data of the third stage under positive voltage as an example, the time $\tau$ = 14 s corresponding to the first zero point of $\overline S (t)$ or the first local minimum point of $\Delta \overline S (t)$ is the appropriate delay time. The minimum value point of $S_{cor} (t)$, $\tau _{w}$ = 28 s, is the selected time window value, from $\tau _{w} =(m-1)\tau$, which we can obtain ${m}$ = 3. Similarly, for the first and second stages under +75 kV, the respective values of t are 15 and 10 s, and the values of *m* are 3 and 4.
- *Reconstruct the Phase Space:* Reconstruct the phase space based on $\tau$ and $m\{X_{j},\, j= 1,2\ldots,M\}$.
- *Find the Nearest Neighbor Point:* Find the nearest neighbor point $X_{\hat {j}}$ for each point $X_{j}$ in the phase space and impose a constraint on transient separation, i.e.,
  $$
  \begin{equation*} d_{j} (0)=\min \left \|{ {X_{j} -X_{\hat {j}}} }\right \|,\quad \left |{ {j-\hat {j}} }\right |>T. \tag{11}\end{equation*}
  $$
- *Calculate the Distance Between the Neighboring Points:* For each point $X_{j}$ in the phase space, calculate the distance between the pair of neighboring points after the <em>i</em>th discrete time step as
  $$
  \begin{align*}&\hspace {-.5pc} d(j)=\left |{ {X_{j+i} -X_{\hat {j}+i}} }\right | \\&\hspace {-2pc} i=1,2,\ldots,\min \left ({M-j,M-\hat {j}}\right). \tag{12}\end{align*}
  $$
- <em>Calculate the Value of lnd<sub><em>j</em></sub>(i):</em> For each *i*, calculate the average value of $\ln d_{j}(i)$ for all *j* as $y(i)$
  $$
  \begin{equation*} y(i)=\frac {1}{ph}\sum _{j=1}^{p} {\ln d_{j} (i)}. \tag{13}\end{equation*}
  $$
  In [(13)](https://ieeexplore.ieee.org/rest/document/10459335/?logAccess=true#deqn13), *p* represents the number of nonzero $\ln d_{j}(i)$. A regression line is fit using the least squares method, and the slope of this line represents the $L_{\mathrm {max}}$. Fig. 7 illustrates that in each stage of the icing flashover process, $L_{\mathrm {max}}$ exceeds 0, implying that the LC time series of the icing insulator flashover process exhibits chaotic behavior and can be analyzed using chaos analysis. Fig. 7 demonstrates a decreasing trend of $L_{\mathrm {max}}$ from the first to the second stage, followed by an increasing trend from the second to the third stage. This variation indicates that the second stage exhibits the most pronounced chaotic characteristics of surface discharge on the icing insulator, primarily due to the prevalence of corona discharge; however, as LC increases, a transient and unstable occurrence of local arc discharge emerges, thereby intensifying the nonlinearity of the LC time series.

![Figure 6](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu6-3373549-large.gif)

**Figure 6.** Calculation of ${m}$ and $\tau$ using the C-C method.

![Figure 7](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu7-3373549-large.gif)

**Figure 7.** ${L}_{\text {max}}$ of LC at each stage of the flashover process.

### B. RP Map Analysis of LC

In Section IV-A, it has been demonstrated that the LC in the flashover process exhibits chaotic characteristics. To effectively extract nonlinear features from the LC time series, the RP technique is employed to convert the chaotic time series into a 2-D matrix. Each time point on the axis represents the moments of different states derived from the phase space reconstruction of the LC sequence<sup>16</sup>. The matrix elements (RP points) correspond to the combinations of time points associated with similar states in the dynamical system represented by the original time series. As a result, the RP map visually illustrates the phase space trajectory of the original system at various comparable time instances within the phase space<sup>17</sup>. When surface discharge occurs on ice-covered insulators, RP technology can analyze the discharge characteristics of ice-covered insulators during surface flashover and reveal its relationship with the nonlinear change of LC. The dynamic alterations of the arc discharge channel, moreover, culminate in a flashover that permeates both hardware fittings. This article, therefore, focuses on the recursive characteristics during stages with significant arc discharge occurrences; furthermore, The LC of negative polarity arc and positive polarity arc has a similar relationship with arc characteristic quantity when arc discharge is formed and developed. Only the characteristics of positive polarity are, therefore, selected to analyze the flashover process.

Fig. 8 shows the RP diagrams for various stages under the application of positive dc. The typical waveforms T1 and T4 are extracted from stages I and III, respectively. Because of the longer duration in the second stage, two time intervals were selected, namely T2 and T3, that exhibit significant arc discharge. Each time interval is associated with LC data of 100 ms. Using the computational procedure mentioned in previous studies, The article generated the RP diagrams for each time interval based on the calculated values of m and $\tau$<sup>18, 19</sup>. The analysis reveals that the topology of RP displays significant variations across different time periods. The progressive changes in topology and fine texture of the recursive graph, ranging from initial corona discharge to near-flashover stages, provide valuable research methods into the distinct characteristics and alterations of surface discharge on insulators. The distribution of dense points in the RP diagram correlates with continuous arc burning, which signifies the persistent behavior of surface discharge on iced insulators. Conversely, the blank areas correspond to the cessation of surface discharge, signifying transitions between distinct discharge modes.

![Figure 8](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu8abcd-3373549-large.gif)

**Figure 8.** RP diagram at different stages. (a) T1. (b) T2. (c) T3. (d) T4.

Fig. 8 exhibits a distinctive pattern of alternating large white areas and block regions composed of RP points, indicating the pronounced variations of this dynamic system and reflecting the transitions in discharge patterns on the surface of icing insulators. Specifically, Fig. 8(a) depicts the surface condition of the insulator during the transition from corona discharge to arc discharge in Stage II. The abundance of scattered recursive points, to some extent, signifies the stochastic nature of corona discharge on the surfaces of icing insulators. The presence of numerous vertical and horizontal line segments, furthermore, suggests a slow variation in the state of LC over a specific timeframe, indicating a nonsevere surface discharge on the insulator.

Fig. 8(b) reflects the situation when a thick and bright white arc appears on the surface of the insulator. There is a decrease in the number of scattered points, while the time points exhibit dense distribution along the main diagonal. The frequency of alternation between blank areas and densely concentrated RP points increases. This characterization effectively captures the periodic transitions that occur on the surface of icing insulators and demonstrates the alternating formation and extinction of arc discharge channels. Fig. 8(c) reflects the further development of the arc, where the radius of the arc root and arc head in the arc channel increases, resulting in increased discharge energy. The gathering area of recursive points along the main diagonal expands further. This indicates that the intensity of arc discharge gradually increases and has become the main discharge mode in this stage. The discharge can continue, and the discharge quantity gradually increases. Fig. 8(d) depicts the proximity to the flashover on the surface of the insulator. During this period, the arc can span across 2–3 units of insulators, accompanied by observable floating arcs. The densely concentrated points along the diagonal and the blank area exhibit minimal alternation. This indicates the ambiguous nature of the transition at this stage, with the arc continuing to evolve. The blank area in the recursive graph diminishes further, signifying intensified discharge phenomena. It signifies an impending flashover; however, during a flashover, due to the unstable discharge of electric sparks, the instantaneous large current will be accompanied by obvious pulse characteristics. At this time, as the LC time series does not have regularity, this article does not consider the discharge characteristics analysis during the flashover stage.

### C. LC Quantitative Analysis of Nonlinear Characteristics

Through the calculation of quantitative indicators for the nonlinear characteristics of LC, The article obtain values for the recurrence rate (RR) and determinism (DET)<sup>20</sup>. These values are used to analyze the nonlinear characteristics of the discharge process occurring on the surfaces of icing insulators. The following formulas are used for the calculation of RR and DET.

RR represents the proportion of recursive points in the recursive plane of the phase space, indicating the proportion of adjacent phase spaces in the m-dimensional phase space. The expression is as follows:
$$
\begin{equation*} \text {RR}=\frac {1}{N^{2}}\sum _{i,j=1}^{N} {R_{i,j}}. \tag{14}\end{equation*}
$$

DET refers to the proportion of recursive points that form line segments parallel to the diagonal in the recursive plane, which can distinguish isolated points. The expression is as follows:
$$
\begin{equation*} \text {DET}=\frac {\sum _{l=l_{\min }}^{N-1} {l\cdot p(l)} }{\sum _{i,j=1}^{N} {R_{i,j}}} \tag{15}\end{equation*}
$$
where *N* is the coordinate axis range in the RP diagram, *l* is the length of the line segment, and $p(l)$ is the number of line segments with length *l*. The RR value indicates the level of proximity between different vectors obtained by creating an LC time series in phase space. A larger level of proximity between two vectors corresponds to a higher RR value. The DET value is associated with the connectivity of isolated points along the diagonal of the RP plot. A higher DET value indicates a greater presence of deterministic elements in the investigated LC sequence. To account for the repeatability of discharge phenomena and data, the values in Fig. 9 represent the averages obtained from all flashover and withstand voltage tests. Fig. 9 displays the RR and DET values of LC at various stages during the flashover test. Based on the observations from Fig. 9, it is evident that both RR and DET exhibit an upward trend as the flashover process develops. The fluctuations in RR indicate a gradual increase in the regular components of LC, accompanying the development of surface discharge on icing insulators. Similarly, the variations in DET imply a reduction in the uncertain components of LC. This phenomenon can be attributed to the transition of surface discharge on iced insulators from initial corona discharge to weak arc discharge, eventually reaching a stable state of long arc discharge. Consequently, the regular components experience growth, and the deterministic elements expand. Consistent with the qualitative description in Fig. 8, this phenomenon supports the characterization of the flashover process. It signifies that the recursive analysis of LC effectively uncovers the surface discharge characteristics in the ice flashover process; however, further investigation is warranted to comprehend the regularity features within LC flashover processes.

![Figure 9](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu9-3373549-large.gif)

**Figure 9.** RR and DET variation of the flashover test.

### D. Regularity Analysis of LC Based on Correlation With Arc Characteristic Quantity

Recursion analysis of flashover process of icing insulator can reveal the surface performance of each stage of outdoor iced insulator discharge process using recursion technology. It particularly emphasizes the increased regularity of LC as the arc discharge occurs closer to the flashover. Since LC is directly related to the discharge process on the insulator surface, the regularity of its changes can be characterized by the correlation of LC and arc characteristic quantities.

The arc length and LC were extracted within each period. To ensure a consistent time resolution to compare the arc length and LC data, segmentation processing was applied to the data for both LC and arc length, and the average was taken using a time window of 1 ms. The data for a duration of 100 ms was selected. Arc discharge phenomena were observed in all four selected time periods, as depicted in Fig. 10. During the T1 period, the purple filament-like local partial discharge turned into a white arc, and LC and arc length increased simultaneously. The maximum LC was 16.2 mA, and the maximum arc length was 127.52 mm. In the T2 period, due to the Joule heat generated by LC and corona discharge at the tip of the icicle, the icicles melted, and the water film conductivity increased. The LC reached a maximum value of 23.4 mA, and the arc development speed was significantly faster than in the T1 period. The conductivity of the water film increased further during T3 and T4, leading to a decrease in the electrical resistance of the remaining ice layer. Consequently, the LC continued to rise, increasing the energy provided by the power source. At this stage, the arc further developed and exhibited drifting arc phenomena. The maximum LC was 43.4 mA, and the maximum arc length was 138.63 mm. The average LC and arc development speed were also significantly greater than in the T1 and T2 periods.

![Figure 10](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu10abcd-3373549-large.gif)

**Figure 10.** Mean LC and arc length across diverse intervals. (a) T1. (b) T2. (c) T3. (d) T4.

### E. Correlation Fitting Analysis of LC and Arc Circumference

As shown in Fig. 10, LC and arc length increase simultaneously with a strong correlation in time intervals T1–T4 and were fit with linear and polynomial models. Initially, the simplest linear model was used to fit LC and arc length, and the result is shown in Fig. 11. It was found that the correlation coefficient was lower than 0.7 in time interval T1 when almost LC was less than 15 mA. Although the arcing discharge occurred on the insulator surface at this time, the main discharge mode was still the corona discharge; therefore, the changes in arc and LC were irregularly and randomly distributed, and their correlation was weak. As ice melting progressed and LC increased, the correlation between LC and arc length in time intervals T2–T4 exhibited a continuously increasing trend and was significantly higher than that in T1. The correlation coefficient in T4 even reached 0.9119.

![Figure 11](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/94/10543207/10459335/liu11abcd-3373549-large.gif)

**Figure 11.** Fitting analysis for various periods. (a) Fitting analysis for T1. (b) Fitting analysis for T2. (c) Fitting analysis for T3. (d) Fitting analysis for T3.

Then, the relationship between the two in time intervals T1–T4 was fit with a third-order polynomial. It was found that the trend in correlation change from T1 to T4 also exhibited a continuously increasing trend. The correlation in each stage of polynomial fitting was, moreover, higher than that in linear fitting. By studying the fitting relationship between LC and arc length, it was found that the closer to the flashover, the stronger the correlation between LC and arc length. It is consistent with the phenomenon that the regularity and deterministic components of LC increase with the approach of flashover along with the manuscript.

## Conclusion

Laboratory icing flashover experiments were performed under dc voltage to investigate the surface flashover characteristics of outdoor high-voltage direct current insulators during extreme icing conditions. The dynamic characteristics of LC and arcs during various stages of the dc ice flashover process were studied. According to the experimental phenomena, the dynamic discharge characteristics and differences under different polarity dc voltages are summarized in detail. By using the embedding space theory and phase space reconstruction method, this study confirms the presence of chaos in LC and analyzes its nonlinear characteristics through RP technology. The coordinated analysis of LC and arc feature quantities verifies the change in LC regularity. The main conclusions are as follows.

- Modifications in LC and arc length when exposed to dc voltages prove to be efficacious in discerning the three stages of arc development. Under negative dc voltage in stage II, there are more discharge activities, and the frequency of arc appearance and development is greater than that under positive dc voltage. In addition, the generation and development process of an iced insulator arc under positive and negative dc voltages are quite different, and the new discharge path is generated in the opposite direction under different polarity dc voltages.
- The estimated maximum Lyapunov exponent ($L_{\mathrm {max}}$) under dc voltage is greater than 0, indicating that LC has chaotic characteristics. Since the main discharge mode during the early stage of stage II is corona discharge accompanied by short and unstable arc discharge, $L_{\mathrm {max}}$ is the smallest, showing the most obvious surface discharge chaotic characteristics.
- The nonlinear changes of LC can be intuitively revealed by RP technology in the form of graphs, reflecting the dynamic behavior of icing insulator arc discharge. The nonlinear indicators RR and DET of LC increase continuously with the development of arc discharge, indicating that the regularity and DET of its discharge are increasing.
- Both LC and arc circumference synchronously increase and have a significant correlation during the four arc extension periods of T1–T4. When LC is low, the fitting effect of the two is poor. As the flashover approaches, the fitting degree of the two increases significantly.

## References (22 total, showing 22)

1. Y. Hu, “DC flashover performance of ice-covered insulators under complex ambient conditions,” IET Gener. Trans. Distrib. , vol. 10, no. 10, pp. 2504–2511, Jul. 2016, doi: 10.1049/iet-gtd.2015.146.

2. C. Zong, Y. Hu, X. Jiang, R. Xian, Z. Liu, and J. Sun, “AC flashover characteristics and arc development process of glaze ice-covered insulators in natural environment,” Int. J. Electr. Power Energy Syst. , vol. 135, Feb. 2022, Art. no. 107559, doi: 10.1016/j.ijepes.2021.107559.

3. C. Fan, “Novel DC flashover model for predicting flashover voltage of the iced insulators,” High Voltage , vol. 6, no. 1, pp. 149–159, Feb. 2021, doi: 10.1049/hve.2020.0005.

4. Y. Liu, M. Farzaneh, and B. X. Du, “Using chaotic features of leakage current for monitoring dynamic behavior of surface discharges on an ice-covered insulator,” IEEE Trans. Dielectr. Electr. Insul. , vol. 24, no. 4, pp. 2607–2615, Sep. 2017, doi: 10.1109/TDEI.2017.006062.

5. F. Meghnefi, C. Volat, and M. Farzaneh, “Temporal and frequency analysis of the leakage current of a station post insulator during ice accretion,” IEEE Trans. Dielectr. Electr. Insul. , vol. 14, no. 6, pp. 1381–1389, Dec. 2007, doi: 10.1109/TDEI.2007.4401220.

6. C. Fang, “Mapping relation of leakage currents of polluted insulators and discharge arc area,” Frontiers Energy Res. , vol. 9, Nov. 2021, Art. no. 777230, doi: 10.3389/fenrg.2021.777230.

7. C. Li, “Coordinating analysis of leakage current and arc development for icing flashover prediction of HVDC outdoor insulators,” in Proc. 4th Int. Conf Dielectrics , Palermo, Italy, Jul. 2022, pp. 142–145.

8. M. Farzaneh, “Insulator flashover under icing conditions,” IEEE Trans. Dielectr. Electr. Insul. , vol. 21, no. 5, pp. 1997–2011, Oct. 2014, doi: 10.1109/TDEI.2014.004598.

9. L. Shu, “Three-dimensional electric field simulation and flashover path analysis of ice-covered suspension insulators,” High Voltage , vol. 5, no. 3, pp. 327–333, Jun. 2020, doi: 10.1049/hve.2019.0095.

10. Y. Liu, M. Farzaneh, and B. X. Du, “Nonlinear characteristics of leakage current for flashover monitoring of ice-covered suspension insulators,” IEEE Trans. Dielectr. Electr. Insul. , vol. 23, no. 3, pp. 1242–1250, Jun. 2016, doi: 10.1109/TDEI.2015.005396.

11. Y. Kim, K. K. Min, J. Yu, D. Kwon, and B.-G. Park, “Lamination method for improved polarization-leakage current relation in HfO2-based metal/ferroelectric/insulator/semiconductor structure,” Semicond. Sci. Technol. , vol. 37, no. 4, Feb. 2022, Art. no. 045001, doi: 10.1088/1361-6641/ac4edd.

12. O. E. Gouda, M. M. F. Darwish, K. Mahmoud, M. Lehtonen, and T. M. Elkhodragy, “Pollution severity monitoring of high voltage transmission line insulators using wireless device based on leakage current bursts,” IEEE Access , vol. 10, pp. 53713–53723, 2022, doi: 10.1109/ACCESS.2022.3175515.

13. H. Ren, T. Takada, H. Uehara, S. Iwata, and Q. Li, “Research on charge accumulation characteristics by PEA method and Q(t) method,” IEEE Trans. Instrum. Meas. , vol. 70, pp. 1–9, 2021, doi: 10.1109/TIM.2021.3055288.

14. G. Lu and P. Zhang, “A novel leakage-current-based online insulation monitoring strategy for converter transformers using common-mode and differential-mode harmonics in VSC system,” IEEE Trans. Ind. Electron. , vol. 68, no. 2, pp. 1636–1645, Feb. 2021, doi: 10.1109/TIE.2020.2972447.

15. M. Khodsuz, M. Mirzaie, and S. Seyyedbarzegar, “Metal oxide surge arrester condition monitoring based on analysis of leakage current components,” Int. J. Electr. Power Energy Syst. , vol. 66, pp. 188–193, Mar. 2015, doi: 10.1016/j.ijepes.2014.10.052.

16. A. Wolf, J. B. Swift, H. L. Swinney, and J. A. Vastano, “Determining Lyapunov exponents from a time series,” Phys. D, Nonlinear Phenomena , vol. 16, no. 3, pp. 285–317, Jul. 1985, doi: 10.1016/0167-2789(85)90011-9.

17. M. T. Rosenstein, J. J. Collins, and C. J. De Luca, “A practical method for calculating largest Lyapunov exponents from small data sets,” Phys. D, Nonlinear Phenomena , vol. 65, nos. 1–2, pp. 117–134, May 1993, doi: 10.1016/0167-2789(93)90009-P.

18. T. Floris, “Detecting strange attractors in turbulence,” in Dynamical Systems and Turbulence . Berlin, Germany : Springer, Jan. 2006, pp. 366–381.

19. B. Du and H. Liu, “The application of recurrence plot in DC tracking test of gamma-ray irradiated polycarbonate,” IEEE Trans. Dielectr. Electr. Insul. , vol. 16, no. 1, pp. 17–23, Feb. 2009, doi: 10.1109/TDEI.2009.4784547.

20. C. D. Nguyen, S. J. Wilson, and S. Crozier, “Automated quantification of the synchrogram by recurrence plot analysis,” IEEE Trans. Biomed. Eng. , vol. 59, no. 4, pp. 946–955, Apr. 2012, doi: 10.1109/TBME.2011.2179937.

21. B. Du, Y. Liu, H. Liu, and Y. Yang, “Recurrent plot analysis of leakage current for monitoring outdoor insulator performance,” IEEE Trans. Dielectr. Electr. Insul. , vol. 16, no. 1, pp. 139–146, Feb. 2009, doi: 10.1109/TDEI.2009.4784561.

22. B. X. Du and D. S. Dong, “Recurrence plot analysis of discharge currents in tracking tests of gamma-ray irradiated polymers,” IEEE Trans. Dielectr. Electr. Insul. , vol. 15, no. 4, pp. 974–981, Aug. 2008, doi: 10.1109/TDEI.2008.4591218.
