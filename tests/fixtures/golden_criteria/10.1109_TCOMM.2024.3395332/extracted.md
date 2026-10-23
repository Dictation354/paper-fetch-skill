---
title: "An Optimal Two-Step Decoding for PSK-Modulated Noisy Index Coding"
authors: "Navya Saxena, Anjana A. Mahesh, B. Sundar Rajan"
journal: "IEEE Transactions on Communications"
doi: "10.1109/tcomm.2024.3395332"
published: "October 2024"
source: "ieee_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 21347
---

# An Optimal Two-Step Decoding for PSK-Modulated Noisy Index Coding

**Abstract.** This paper studies noisy index coding problems over broadcast channels. The codewords from a chosen binary index code of length N are mapped to a $2^{N}$ -PSK constellation before being transmitted over an AWGN channel. The receivers follow the two-step decoding process of first estimating the PSK symbol using a maximum-likelihood decoder and then performing index code decoding. After estimating the PSK symbol, there is, in general, more than one decoding strategy at a receiver, i.e., more than one linear combination of index-coded bits along with a subset of side information bits, that can be used to estimate the requested message. Thomas et al. in [“Single Uniprior Index Coding With Min-Max Probability of Error Over Fading Channels,” IEEE Transactions on Vehicular Technology, pp. 6050-6059, July 2017] showed that for binary-modulated index code transmissions, minimizing the number of transmissions used to decode a requested message is equivalent to reducing the probability of error. This paper shows that this is no longer true while employing multi-level modulations. Further, we consider the side information available to each receiver also to be noisy and derive an expression for the probability that a requested message bit is estimated erroneously at a receiver. We also show that the criterion for choosing a decoding strategy that gives the best probability of error performance at a receiver changes with the signal-to-noise ratio at which the side information is broadcast. Hence, for a given index coding problem and a chosen index code, we give an algorithm to select the best decoding strategy for the receivers. The above results are shown to be valid over fading channels also.

## Introduction

The Index Coding Problem (ICP), introduced in<sup>1</sup>, is now a well-studied problem in network information theory, which aims to characterize the optimal communication rates and coding schemes for broadcasting multiple messages to a system of receivers with side information. Instances of ICP arise in satellite communications<sup>2</sup>, cache-aided content broadcasting<sup>3</sup>, coded computing<sup>4</sup>, etc. It consists of a central server that has access to a set $\mathcal {X}$ of messages, broadcasting to a group of receivers, each of which knows a subset of the messages in $\mathcal {X}$ *a priori* as side information and requests another subset of messages from the server. The solution of an ICP, which is a set of server transmissions that satisfy all the receivers, is called an index code, and the number of transmissions in it is called its length. If all the transmissions in an index code are linear combinations of the messages in $\mathcal {X}$, then it is called linear. If each coded transmission is formed using a single generation of messages in $\mathcal {X}$, the index code is said to be scalar. An optimal index code is one with the minimum possible number of transmissions.

Bar-Yossef et al.<sup>5</sup> studied a particular type of ICP where each receiver demands a single unique message, represented using a directed graph called a side information graph. In<sup>5</sup>, it was proved that for a given ICP, the length of an optimal scalar linear index is equal to a graph functional called the minrank of the corresponding side information graph. Ong and Ho<sup>2</sup> classified ICPs depending on the nature of demands and side information of receivers. If the side information at each receiver is unique, then it is called a uniprior ICP. If every receiver’s demand is unique, it is called a unicast ICP. Further, in a unicast ICP, if each receiver demands only a single message, it is called a single unicast ICP. General ICPs that are neither uniprior nor unicast are termed multicast/multi-prior.

Most of the literature concerning ICPs consider server transmissions over noiseless broadcast channels, while in practice, the transmissions can never be noise-free. Noisy ICPs have been studied in<sup>6, 7, 8</sup>, and<sup>9</sup>, among others. Multi-level modulations have been used for the transmission of index codewords in some of these works. A particular case of ICP over the AWGN channel with quadrature amplitude modulation has been studied in<sup>6</sup>. Phase shift keying was the chosen modulation scheme for transmitting index-coded bits over the AWGN channel in<sup>8</sup> and<sup>9</sup>, called index-coded PSK modulation. In these papers, for a chosen binary index code of length $N$, the $N$ index-coded bits are mapped to a signal point in $2^{N}$- PSK constellation.

There might be situations in which the server gives higher priority to some of the receivers, which may be based on the premium paid. Such a prioritized receiver system is considered in<sup>9, 10</sup>, and<sup>15</sup>. The techniques used in these papers aim to give the best probability of error performance of the highest priority receiver, but this might lead to the performance of lower priority receivers deteriorating considerably. However, there might also be cases where the server does not prioritize receivers. For instance, a service provider (a television channel) may serve all its users equally as all have paid equal money. This work considers noisy ICPs with unprioritized receivers over the AWGN broadcast channel.

We examine two scenarios: one with noiseless side information and another with noisy side information at the receivers. In the case of noisy side information, we posit that the receivers acquire this information from previous binary-modulated broadcast transmissions by the server, which may have occurred during an earlier off-peak period, and thus, this information may be subject to noise. Due to variations in receiver sensitivities or detection thresholds, different subsets of the messages may fail to get decoded, effectively becoming erased at different receivers. Consequently, this results in distinct, non-identical subsets of the message set $\mathcal {X}$ as side information at different receivers.

Decoding a requested message at a receiver involves the two-step process of first performing maximum-likelihood (ML) decoding to estimate the transmitted PSK symbol, and hence the index-coded bits, and then decoding the requested message bit by using some linear combination of the estimated index-coded bits and its side information. At any receiver, there might be several linear combinations of the index-coded bits, which, along with its side information, could be used for decoding a particular requested message, which we call possible decoding strategies at that receiver. For binary-modulated transmissions, it was shown in<sup>7</sup> that the best decoding strategy w.r.t. probability of error is a linear combination of the minimum number of index-coded bits. In this paper, we show that when the index code is transmitted using $M$-PSK, minimizing the number of index-coded bits used in index-decoding post-ML decoding of the PSK symbol need not result in the best probability of error performance at the receivers.

We derive a criterion for selecting a decoding strategy that results in the best probability of error performance. There might be other two-step decoding processes that use a non-ML decoder to estimate the PSK symbol and a different decoding strategy than the one shown to be the optimal in our setting, which may result in a better probability of error performance at a receiver by virtue of error cancellations. Hence, the optimality of the decoding strategy w.r.t. minimizing the probability of error at a receiver is only among the two-step decoding schemes employing ML estimation of the PSK symbol in the first step. Here, optimality is claimed in the sense of minimizing the probability of error and not in any information theoretic sense like maximizing mutual information.

While the papers<sup>6, 8, 9</sup>, and<sup>10</sup> also studied multi-level modulated transmission of index codes, the novelty of this paper lies in the following aspects. To the best of our knowledge, the existence of different decoding strategies at the receivers for a chosen index code and the role of the decoding strategy in determining the probability of error performance of a receiver has not been previously studied. This is also the first work to analyze the impact of noisy side information when the index-code transmission is not using binary modulation but employing a higher-order modulation scheme, resulting in higher bandwidth efficiency. Further, while the papers<sup>8</sup> and<sup>9</sup> obtained improved bit error performances at some of the receivers by trading off the performance at other receivers, the selection of an optimal decoding strategy takes place independently at each of the receivers and hence, simultaneous optimization of bit error performances at all the receivers. The main technical contributions of this work are listed below:

- We prove that for index code transmission using multi-level modulation, the probability of error performance at a receiver is not proportional to the number of index-coded bits used in decoding a requested message.
- A theoretical analysis is carried out for index code transmission over an AWGN channel using multi-level modulation, and the expression for the probability of bit error is obtained by any decoding strategy at a receiver for both noiseless and noisy side information cases.
- For selecting an optimal decoding strategy at a receiver with respect to the probability of error performance, different criteria are derived, and based on that, an algorithm is presented that outputs the best decoding strategy for a requested message at a given receiver. Later on, we have analyzed the complexity of both algorithms.
- Simulation results validating that the decoding strategy chosen based on the criteria in this paper gives the best probability of error performance at the receivers are also provided.
- Assuming perfect channel state information at each receiver, we establish that the proposed results remain valid even when the broadcast channel between the source and the receivers is a fading channel.
- Further improvement of the bit error rate performance of receivers by optimizing over different $M$-PSK mappings is analyzed.

### A. Organization and Notation

The rest of this paper is organized as follows. Section II describes the system model used in this paper. At a receiver, the expressions for the probability of decoded message error in the noiseless and the noisy side information situations are derived, and a modified algorithm for finding the optimal decoding strategy is also given in Section III. The results in Section III are explained using a detailed example in Section IV. The validity of results is shown over the fading channel also in Section V and Section VI presents some simulation results. The performance of receivers is compared under different mappings in Section VI. Finally, the paper is concluded by giving a summary of the contributions in Section VIII.

The mathematical notations used in the paper are as follows: The binary field consisting of the elements 0 and 1 is denoted as $\mathbb {F}_{2}$. The set $\{1,2,3,\ldots ,n\}$ is denoted by $[n]$. $f(y)$ denotes any function $f$ which takes input argument $y$. A vector is represented by a lowercase bold-face letter, as in **x**, while a matrix is represented by an upper-case bold-face letter, as in **L**. For a length-$m$ vector **x**, $x_{i}$ represents the $i^{th}$ component of $\mathbf {x}, i \in [m]$, while $\mathbf {x}_{B}$ denotes the vector defined as $\mathbf {x}_{B}=(x_{i} : i\in B), B \subset [m]$. For a matrix **A**, $\mathbf {A}^{T}$ denotes its transpose. The symbol $\oplus$ denotes the XOR of the operands. For a set $S$ consisting of $m$ elements, $S(i)$ denotes the $i^{\text {th}}$ element in $S$, for $i \in [m]$.

## System Model

Consider a setting in which a central server with access to a library $\mathcal {X}=\{x_{1}, x_{2},\ldots , x_{m}\}$, $x_{i}\in \ \mathbb {F}_{2}$, of messages, broadcasts to a set of $n$ receivers, $\mathcal {R}=\{R_{1}, R_{2},\ldots , R_{n}\}$. In the first phase, which happens during a window with minimal network congestion, the server broadcasts each of the $m$ messages in $\mathcal {X}$ after BPSK modulation over a noisy channel. The noise characteristics of the channel between the source and a receiver $R_{i}$ is reflected in the signal-to-noise ratio (SNR) observed at it and is denoted as $\Gamma _{si}^{i}$. Depending on the received signal levels, some symbols are decoded at a receiver while others are erased. Hence, at the end of this phase of message broadcast, a receiver $R_{i}$ will have a set $K_{i}$ of decoded messages as side information. Let each message in $K_{i}$ be received at $R_{i}$ with the same SNR of $\Gamma _{si}^{i}$.

This is followed by each receiver demanding a subset of the messages not already in its possession. Let the receiver $R_{i}$ demand the subset $W_{i} \subseteq \mathcal {X} \setminus K_{i}$. We consider that $|W_{i}| = 1$, $\forall i \in [n]$ since, if a receiver requests more than one message, then that receiver can be split into several virtual receivers, each demanding one message and with the same side information set as that of the original receiver. For this ICP, an index code of length $N$ consists of the following:

- an encoding scheme, $\mathcal {E}\colon \mathcal {X} \rightarrow \mathbb {F}_{2}^{N}$, and
- $n$ decoding functions, $\{{\mathcal {D}}^{i}\}_{i \in [n]}$, ${\mathcal {D}}^{i} \colon \mathbb {F}_{2}^{N} \times \mathbb {F}_{2}^{|K_{i}|} \rightarrow \mathbb {F}_{2}^{|W_{i}|}$ s.t., for $\mathbf {x} \in \mathbb {F}_{2}^{n}$, ${\mathcal {D}}^{i}(\mathcal {E }(\mathbf {x}),K_{i}) = W_{i}$.

When $\mathcal {E}$ is linear, then the encoding scheme is said to be linear and can be represented by the generator matrix **L** of dimensions $n \times N$ where $N$ is the length of the index code. The index-coded bit tuple is given by $\mathbf {y}=\mathbf {xL}$ over $\mathbb {F}_{2}$.

Assuming that the index code transmissions happen when the network is heavily congested, for further reduction in bandwidth, the length-$N$ index-coded vector $\mathbf {y} = (y_{1}, y_{2}, \ldots , y_{N})$ is transmitted using $2^{N}$-PSK modulation. For an AWGN broadcast channel, at $R_{i}$, the received complex symbol is $c_{i} = \mathcal {M}(\mathbf {y}) +n_{i}$, where $n_{i}$ is the white Gaussian noise, and the signal-to-noise ratio at which this symbol $c_{i}$ is received is denoted as $\Gamma _{ic}^{i}$ which is equal to $\frac {E_{s}}{N_{o}}$ or $\frac {NE_{b}}{N_{o}}$ with $E_{s}$ being the symbol energy, $E_{b}$ the energy per bit and $N_{o}$ being the variance of the additive noise $n_{i}$. In either case, after minimum distance decoding at a receiver $R_{i}$, the vector of estimated index-coded bits is denoted as $\hat {\mathbf {y}}^{i} = (\hat {y}^{i}_{1}, \hat {y}^{i}_{2}, \ldots , \hat {y}^{i}_{N})$.

For a linear encoding scheme, the decoding function ${\mathcal {D}}^{i}$ at receiver $R_{i}$ is a linear combination of all or a subset of the index-coded bits and a subset of its side information. At any receiver, multiple linear combinations of index-coded bits and side information could give its requested message, which we call the possible decoding strategies at that receiver. At receiver $R_{i}$, if there are $r$ different decoding strategies, they are denoted as ${\mathcal {D}}^{i}_{1}, {\mathcal {D}}^{i}_{2}, \ldots , {\mathcal {D}}^{i}_{r}$, each of which is a function of the estimated index-coded bits in $\hat {\mathbf {y}}^{i}$ as well as its side information. The following example illustrates the notations defined above.

### Example 1:

Consider an ICP with $m=n=5$ and $W_{i}=x_{i}, \ \forall {i} \in \{1,2,3,4,5\}$. The messages in $\mathcal {X}$ are transmitted using BPSK over an AWGN channel in low-traffic hours. Depending upon each receiver’s threshold value or sensitivities, some of the messages are decoded while others are erased, resulting in the following side information at the receivers $K_{1}=\{\tilde {x}_{2},\tilde {x}_{3},\tilde {x}_{4},\tilde {x}_{5}\}$, $K_{2}=\{\tilde {x}_{1},\tilde {x}_{3},\tilde {x}_{4},\tilde {x}_{5}\}$, $K_{3}=\{\tilde {x}_{2}, \tilde {x}_{4}\}$, $K_{4}=\{\tilde {x}_{1}, \tilde {x}_{3}\}$, and $K_{5}=\{\tilde {x}_{3}\}$. For this ICP, the length of an optimal linear index code is $N=3$. We consider the linear encoding scheme specified by $\begin{aligned} \mathbf {L} = \begin{bmatrix} 1 & 0 & 0 & 1 & 1 \\ 1 & 1 & 1 & 1 & 1 \\ 1 & 0 & 1 & 1 & 0 \end{bmatrix}^{T} \end{aligned}$ and the index coded vector is $\mathbf {y}=(y_{1},y_{2},y_{3})$ where $\mathbf {y}=\mathbf {x}\mathbf {L}$, for $\mathbf {x} \in \mathbb {F}_{2}^{5}$. We transmit the above index code using the 8-PSK mapping given in Fig. 1 through an AWGN channel. At the receiver $R_{i}$, after performing ML decoding on the received signal, the vector of estimated index coded bits is $\mathbf {\hat {y}}^{i}= (\hat {y}^{i}_{1}, \hat {y}^{i}_{2},\hat {y}^{i}_{3})$. The different decoding strategies for each of the receivers are given below.

![Figure 1](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan1-3395332-large.gif)

**Figure 1.** 8-PSK mapping used for modulating the index-coded bits in Example 1.

At $R_{1}$:

- $\hat {x}_{1}=\mathcal {D}_{1}^{1}(\mathbf {\hat {y}}^{1},K_{1}) := \hat {y}^{1}_{1} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5}$,
- $\hat {x}_{1}=\mathcal {D}_{2}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{2} \oplus \tilde {x}_{2} \oplus \tilde {x}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5}$,
- $\hat {x}_{1}=\mathcal {D}_{3}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{3} \oplus \tilde {x}_{3} \oplus \tilde {x}_{4}$, and
- $\hat {x}_{1}=\mathcal {D}_{4}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{2} \oplus \hat {y}^{1}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{2}$.

At $R_{2}$:

- $\hat {x}_{2}=\mathcal {D}_{1}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{1} \oplus \hat {y}^{2}_{2} \oplus \tilde {x}_{3}$,
- $\hat {x}_{2}=\mathcal {D}_{2}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{2} \oplus \tilde {x}_{1} \oplus \tilde {x}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5}$,
- $\hat {x}_{2}=\mathcal {D}_{3}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{2} \oplus \hat {y}^{2}_{3} \oplus \tilde {x}_{5}$, and
- $\hat {x}_{2}=\mathcal {D}_{4}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{1} \oplus \hat {y}^{2}_{2} \oplus \hat {y}^{2}_{3} \oplus \tilde {x}_{1} \oplus \tilde {x}_{4}$.

At $R_{3}$:

- $\hat {x}_{3}=\mathcal {D}_{1}^{3}(\mathbf {\hat {y}}^{3},K_{3}) :=\hat {y}^{3}_{1} \oplus \hat {y}^{3}_{2} \oplus \tilde {x}_{2}$.

At $R_{4}$:

- $\hat {x}_{4}=\mathcal {D}_{1}^{4}(\mathbf {\hat {y}}^{4},K_{4}) :=\hat {y}^{4}_{3} \oplus \tilde {x}_{1} \oplus \tilde {x}_{3}$.

At $R_{5}$:

- $\hat {x}_{5}=\mathcal {D}_{1}^{5}(\mathbf {\hat {y}}^{5},K_{5}) :=\hat {y}^{5}_{1} \oplus \hat {y}^{5}_{3} \oplus \tilde {x}_{3}$.

From the above example, we saw that for a given index code, there could exist different ways in which a receiver could decode its requested message. When we transmit the index-coded bits using multi-level modulation schemes, the erroneous reception of an index-coded bit is not independent of the other index-coded bits being received erroneously. Hence, unlike BPSK, the probability of error performance of each index-coded bit is not the same. In the following section, we prove that, for transmission employing multi-level modulations, the error probability in decoding a requested message is not proportional to the number of index-coded bits used in decoding it and then derive a criterion for choosing an optimal decoding strategy at a receiver.

## Main Results

For a chosen index code of length $N$ of a given ICP and a chosen mapping $\mathcal {M}$ of index codewords to PSK signal points, let the $2^{N}$- PSK signal set configuration used for transmission be denoted as $\mathcal {S}_{2^{N},\mathcal {M}}$. At a receiver $R_{i}$ which has the side information $K_{i}$, denote the set $\{\hat {y}^{i}_{j}\}_{j \in [N]}$ of estimated index-coded bits by $\hat {Y}^{i}$. For a decoding strategy ${\mathcal {D}}_{j}^{i}$ at $R_{i}$, let the indices of the index-coded bits used by ${\mathcal {D}}_{j}^{i}$ be denoted as $I({\mathcal {D}}_{j}^{i})$. Similarly, the index set of the subset of the side information $K_{i}$ used by ${\mathcal {D}}_{j}^{i}$ is represented as $S({\mathcal {D}}_{j}^{i})$. Hence, from the set $\hat {Y}^{i}$ of estimated index coded bits, ${\mathcal {D}}_{j}^{i}$ uses a linear combination of the subset $\hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})} \subseteq \hat {Y}^{i}$ of estimated index-coded bits, along with the subset $\tilde {\mathcal {X}}_{S({\mathcal {D}}_{j}^{i})} \subseteq K_{i}$ of the side information to decode $W_{i}$. The XOR of the bits in $\hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ corresponding to a signal point $s_{k} \in \mathcal {S}_{2^{N},\mathcal {M}}$ is denoted as $\bigoplus \limits _{s_{k}} \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$.

For a pair of signal points $s_{j}, s_{k} \in \mathcal {S}_{2^{N},\mathcal {M}}$, the Euclidean distance between them in $\mathcal {S}_{2^{N},\mathcal {M}}$ is denoted as $\text {dist}(s_{j},s_{k})$. The minimum Euclidean distance of an $M$-PSK signal set is denoted as $\Delta _{M-\text {PSK}}$. For a decoding strategy ${\mathcal {D}}_{j}^{i}$ and a chosen $2^{N}$- PSK signal set configuration $\mathcal {S}_{2^{N},\mathcal {M}}$, the set of signal-pairs $(s_{j},s_{k})$, such that $s_{j},s_{k} \in \mathcal {S}_{2^{N},\mathcal {M}}$, which are at a distance equal to $\Delta _{2^{N}-\text {PSK}}$, and for which the value of $\bigoplus \limits _{s_{j}} \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ is not equal to that of $\bigoplus \limits _{s_{k}} \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ is denoted as $P({\mathcal {D}}_{j}^{i})$,
$$
\begin{align*} P({\mathcal {D}}_{j}^{i}) & = \big \{(s_{j}, s_{k}) \ |\ j \lt k, \ \text {dist}(s_{j},s_{k}) = \Delta _{2^{N}-\text {PSK},} \text {and}~ \\ & \quad \bigoplus \limits _{s_{j}} \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})} \neq \bigoplus \limits _{s_{k}} \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}\big \}. \tag {1}\end{align*}
$$

### Theorem 1:

For a given ICP and a chosen index code of length $N$, let the index-coded bits be transmitted after modulation using the $2^{N}$-PSK configuration $\mathcal {S}_{2^{N},\mathcal {M}}$ over an AWGN channel. For this setting, under the assumption that the receivers have noiseless side information, the probability of error ${\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}$, in decoding a requested message using the decoding strategy ${\mathcal {D}}_{j}^{i}$ at receiver $R_{i}$ is upper bounded as:
$$
\begin{equation*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}} \lt \frac {|P({\mathcal {D}}_{j}^{i})|}{2^{N}}2{Q}\left ({{\sqrt {2 \Gamma _{ic}^{i}\left ({{\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}\right )}}}\right ). \tag {2}\end{equation*}
$$

#### Proof:

At any receiver, the probability of error in estimating its requested message is due to the error in estimating the index-coded bits. This is because it is assumed that there is no error in the side information bits available at the receiver, and hence, they will not contribute to the error in the index decoding step. Minimum Euclidean distance decoding is performed at a receiver to estimate the PSK symbol transmitted over an AWGN channel. At receiver $R_{i}$, when a transmitted symbol $s_{j} \in \mathcal {S}_{2^{N},\mathcal {M}}$ is wrongly estimated as $s_{k}$, all the index-coded bits need not be wrongly estimated. Now, we will derive an upper bound on the probability that $Y_{I({\mathcal {D}}_{j}^{i})}$ is decoded in error.

We know that the probability that a symbol $s_{m} \in \mathcal {S}_{2^{N},\mathcal {M}}$ transmitted over an AWGN channel is wrongly decoded as $s_{m'} \in \mathcal {S}_{2^{N},\mathcal {M}}$ is $P_{\text {Err}(m \rightarrow m')}=Q(d_{mm{'}}/ \sqrt {2N_{o}})$, where $d_{mm{'}} = \text {dist}(s_{j},s_{k})$, where $Q(x)$ is the tail probability of a standard normal distribution. Considering all the $M =2^{N}$ symbols to be equally likely, the union bound for the average probability of error is obtained as
$$
\begin{align*} P_{\text {Err}_{\text {avg}}} \lt \frac {1}{M}\sum _{m=1}^{M} \sum _{\substack { \\ m{'} \neq m }}Q(d_{mm'}/ \sqrt {2N_{o}}). \tag {3}\end{align*}
$$

For a $2^{N}-$PSK constellation, the minimum Euclidean distance is $\Delta _{2^{N}-\text {PSK}}=2\sqrt {E_{s} \sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}$. In [(3)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn3), the dominant terms will be those with $d_{mm'}$ equal to the minimum Euclidean distance $\Delta _{2^{N}-\text {PSK}}$. In any $2^{N}-$PSK constellation, for a given transmitted symbol $s_{m}$, there will be two other symbols that are at a distance equal to $\Delta _{2^{N}-\text {PSK}}$ from $s_{m}$. Hence, we can approximate [(3)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn3) as
$$
\begin{equation*} P_{\text {Err}_{\text {avg}}} \lt \frac {1}{2^{N}}\sum _{m=1}^{2^{N}} 2{Q}\left ({{\sqrt {2\left ({{\frac {E_{s}}{N_{o}}}}\right )\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}}\right ). \tag {4}\end{equation*}
$$

For determining the probability of error in decoding $W_{i}$, using a decoding strategy ${\mathcal {D}}_{j}^{i}$, at $R_{i}$, we only need to consider the error events where the XOR of the bits used in decoding, i.e., $Y_{I({\mathcal {D}}_{j}^{i})}$, are in error. Up to first-order approximations, the probability of error $Pr(\hat {W}_{i} \neq W_{i})$ is determined by the probability of the error events $(s_{j} \rightarrow s_{k})$, i.e., $s_{j}$ is decoded as $s_{k}$, for $(s_{j},s_{k}) \in P({\mathcal {D}}_{j}^{i})$. Therefore, using [(4)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn4) and the number of error events $P({\mathcal {D}}_{j}^{i})$, the probability of error ${\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}$ can be upper bounded as
$$
\begin{equation*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}} \lt \frac {|P({\mathcal {D}}_{j}^{i})|}{2^{N}}2{Q}\left ({{\sqrt {2 \Gamma _{ic}^{i}\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}}\right )\end{equation*}
$$
where $\Gamma _{ic}^{i}=\frac {E_{s}}{N_{o}}$ is the signal-to-noise ratio observed at receiver $R_{i}$ for the $2^{N}$-PSK symbol.

### Corollary 1:

For a given ICP and a chosen index code of length $N$ with receivers having noiseless side information, when the index-coded bits are transmitted employing any $2^{N}$-PSK configuration, the probability of error in decoding a requested message at any receiver is not proportional to the number of index-coded bits used to decode it.

#### Proof:

From [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2), we saw that the probability of error for a decoding strategy ${\mathcal {D}}_{j}^{i}$ depends on $|P({\mathcal {D}}_{j}^{i})|$ and is not proportional to the number of estimated bits in the linear combination used in ${\mathcal {D}}_{j}^{i}$. Consider the 8- PSK constellation with decimal to binary mapping shown in Fig. 1. It can be seen that when $\hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})} = \{\hat {y}^{i}_{1}\}$, the number of error events $(s_{j} \rightarrow s_{k})$, with $(s_{j},s_{k}) \in P({\mathcal {D}}_{j}^{i})$ is two, whereas with $\hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})} = \{\hat {y}^{i}_{3}\}$, the number of such error events is 8. Hence, a decoding strategy using $\hat {y}^{i}_{1}$ will not perform the same as another one using $\hat {y}^{i}_{3}$. Further, consider that ${\mathcal {D}}_{j}^{i}$ uses a linear combination of $\hat {y}^{i}_{1}$ and $\hat {y}^{i}_{2}$, for which the number of error events $\{(s_{j} \rightarrow s_{k}), (s_{j},s_{k}) \in P({\mathcal {D}}_{j}^{i})\}$ is two which implies that this strategy will perform better than the one using $\hat {y}^{i}_{3}$ alone. Hence, we see that the probability of error performance is not proportional to the number of index-coded bits used in decoding.

The fact that the probability of error in decoding a message is not proportional to the number of index-coded bits used in its decoding is true for any multi-level modulation scheme, not just $M$-PSK. Hence, unlike in<sup>7</sup>, the best decoding strategy, while employing multi-level modulation for index code transmission, differs from the one that minimizes the number of index-coded bits used in decoding. In the rest of this section, we consider that the side information at the receivers is noisy and obtained via binary-modulated broadcast transmissions over an AWGN channel. We derive the probability of bit error obtained using a given decoding strategy based on which we derive a criterion for selecting an optimal decoding strategy, denoted ${\mathcal {D}}^{i}_{*}$, with the best probability of bit error performance at receiver $R_{i}$.

### Theorem 2:

For a given ICP, let the side information at the receivers be noisy. For a chosen index code of length $N$, let $\mathcal {S}_{2^{N},\mathcal {M}}$ be the PSK configuration used for transmitting the index code over an AWGN channel. In this setting, the probability of bit error obtained using a decoding strategy ${\mathcal {D}}_{j}^{i}$ is given by
$$
\begin{align*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}={\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}+\frac {1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}{2}, \tag {5}\end{align*}
$$
where ${\mathcal {P}}_{e}^{si}$ is the probability of bit error for BPSK-modulated message transmissions over an AWGN channel, and ${\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}$ is the probability of error for the linear combination $\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ of the index-coded bits obtained from the $M$-PSK signal.

#### Proof:

Any decoding strategy, in a general form, can be written as ${\mathcal {D}}_{j}^{i}= \bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})} \oplus \tilde {X}_{S({\mathcal {D}}_{j}^{i})}$. At a receiver, decoding the $M$-PSK symbol corresponding to the index-coded bits and the side information messages occur independently. Since the error analysis is done over the binary field $\mathbb {F}_{2}$, a decoding strategy ${\mathcal {D}}_{j}^{i}$ is said to make an error in estimating the demanded message when there are an odd number of errors in the decoded side information bits and the linear combination $\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ used by ${\mathcal {D}}_{j}^{i}$. The side information bits are transmitted using BPSK modulation, so they are independent of each other. Hence, ${\mathcal {D}}_{j}^{i}$ will decode wrongly in the following two situations:

- The linear combination $\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ of index-coded bits is decoded wrongly, and there are an even number of errors in $S({\mathcal {D}}_{j}^{i})$.
- The linear combination $\oplus Y_{(I({\mathcal {D}}_{j}^{i}))}$ of index-coded bits is decoded correctly, and there are an odd number of errors in $S({\mathcal {D}}_{j}^{i})$.

Combining the two cases above, the probability of error for ${\mathcal {D}}_{j}^{i}$ is obtained as

$$
\begin{align*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}& ={\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}\Bigg (\sum _{\substack {v \le |S({\mathcal {D}}_{j}^{i})| \\ v \ \text {even}}} \binom {|S({\mathcal {D}}_{j}^{i})|}{v} ({\mathcal {P}}_{e}^{si})^{v} \\ & \quad (1-{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}_{j}^{i})|-v}\Bigg )+(1-{\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}) \\ & \quad \left ({{\sum _{\substack {v \le |S({\mathcal {D}}_{j}^{i})| \\ v \ \text {odd}}} \binom {|S({\mathcal {D}}_{j}^{i})|}{v} ({\mathcal {P}}_{e}^{si})^{v}(1-{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}_{j}^{i})|-v}}}\right ). \tag {6}\end{align*}
$$

Using the binomial expansions for $(1+x)^{\eta }$ and $(1-x)^{\eta }$ with $x=\frac {{\mathcal {P}}_{e}^{si}}{1-{\mathcal {P}}_{e}^{si}}$ and $\eta = |S({\mathcal {D}}_{j}^{i})|$, we can simplify the above expression as follows.
$$
\begin{align*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}& =\frac {{\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}}{2}\left ({{\left ({{1+\frac {{\mathcal {P}}_{e}^{si}}{1-{\mathcal {P}}_{e}^{si}}}}\right )^{\eta }+\left ({{1-\frac {{\mathcal {P}}_{e}^{si}}{1-{\mathcal {P}}_{e}^{si}}}}\right )^{\eta }}}\right ) \\ & \quad \Big (1-{\mathcal {P}}_{e}^{si}\Big )^{\eta }+ \frac {1-{\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}}{2}\Bigg (\left ({{1+\frac {{\mathcal {P}}_{e}^{si}}{1-{\mathcal {P}}_{e}^{si}}}}\right )^{\eta }\\ & \quad -\left ({{1-\frac {{\mathcal {P}}_{e}^{si}}{1-{\mathcal {P}}_{e}^{si}}}}\right )^{\eta }\Bigg )\Big (1-{\mathcal {P}}_{e}^{si}\Big )^{\eta }\tag {7}\\ {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}& =\frac {{\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}}{2}\Bigg (1+(1-2{\mathcal {P}}_{e}^{si})^{\eta }\Bigg )+ \frac {1-{\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}}{2} \\ & \quad \Bigg (1-(1-2{\mathcal {P}}_{e}^{si})^{\eta }\Bigg ) \\ {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}& ={\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}(1-2{\mathcal {P}}_{e}^{si})^{\eta }+\frac {1-(1-2{\mathcal {P}}_{e}^{si})^{\eta }}{2} \tag {8}\end{align*}
$$
where,
$$
\begin{equation*} {\mathcal {P}}_{e}^{si} \approx {Q}(\sqrt {2\Gamma _{si}^{i}})\end{equation*}
$$
and ${\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}$ is approximated using the upper bound in [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2) as
$$
\begin{equation*} {\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}} \approx \frac {|P({\mathcal {D}}_{j}^{i})|}{2^{N}}2{Q}\left ({{\sqrt {2 {\Gamma }_{ic}^{i}\left ({{\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}\right )}}}\right )\end{equation*}
$$
which becomes tight for high values of $\Gamma _{ic}^{i}$.

We can see that the expression for the probability of bit error in [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5) derived in Theorem 2 consists of two terms, one determined by the error in the index-coded $M$-PSK transmission and the other by the error in the BPSK-modulated message transmissions from which the side information at a receiver is obtained. In the following lemma, we determine the value of $\Gamma _{ic}^{i}$ at which, for a given decoding strategy ${\mathcal {D}}_{j}^{i}$, the first term in [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5) becomes equal to the second term in [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5). We denote this value of $\Gamma _{ic}^{i}$, which we call the *threshold value*, as $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$.

### Lemma 1:

For a given ICP and a chosen index code of length $N$, consider that the index-coded bits are transmitted using $2^{N}$-PSK modulation over an AWGN channel. Let the messages in the side information of a receiver $R_{i}$ be obtained with an SNR of $\Gamma _{si}^{i}$ through BPSK-modulated transmissions over an AWGN channel. In this scenario, the threshold value of $\Gamma _{ic}^{i}$ for a given decoding strategy ${\mathcal {D}}_{j}^{i}$ is given by
$$
\begin{equation*} \Gamma ^{th}({\mathcal {D}}_{j}^{i}) \approx \beta \left ({{{Q}^{-1}\left ({{\frac {2^{N}(1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|})}{|P({\mathcal {D}}_{j}^{i})|2(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}}}\right )}}\right )^{2}, \tag {9}\end{equation*}
$$
where $\beta =1/\left ({{2N \left ({{\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}\right )}}\right )$.

#### Proof:

At a given receiver $R_{i}$, the probability of bit error performance of a decoding strategy ${\mathcal {D}}_{j}^{i}$ is given by [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5). The second term in [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5) is independent of $\Gamma _{ic}^{i}$. At very low values of $\Gamma _{ic}^{i}$ compared to $\Gamma _{si}^{i}$, the error performance of ${\mathcal {D}}_{j}^{i}$ is determined predominantly by the first term. As the value of $\Gamma _{ic}^{i}$ increases, the value of the first term reduces exponentially for transmissions over an AWGN channel. As long as the order of the first term is greater than that of the second term, the probability of bit error will continue to trace the waterfall curve with an increasing value of $\Gamma _{ic}^{i}$. Whereas, when the value of the first term is approximately equal to that of the second term, the probability of error curve does not fall significantly with further increase in the value of $\Gamma _{ic}^{i}$. An approximate value of $\Gamma _{ic}^{i}$ at which this “error floor” occurs can be estimated using [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5) as the value at which
$$
\begin{equation*} {\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|} \approx \frac {1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}{2},\end{equation*}
$$
which can simplified using [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5) for transmissions over the AWGN channel to get
$$
\begin{equation*} \Gamma ^{th}({\mathcal {D}}_{j}^{i}) \approx \beta \left ({{{Q}^{-1}\left ({{\frac {2^{N}(1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|})}{|P({\mathcal {D}}_{j}^{i})|2(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}}}\right )}}\right )^{2},\end{equation*}
$$
where $\beta =\frac {1}{2N \left ({{\sin ^{2}\left ({{\frac {\pi }{2^{N}}}}\right )}}\right )}$, and ${\mathcal {P}}_{e}^{si}={Q}(\sqrt {2\Gamma _{si}^{i}})$. From [(9)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn9), it can be seen clearly that as the value of $\Gamma _{si}^{i}$ increases, the value of $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$ also increases.

### Theorem 3:

For the setting considered in Theorem 2, at a receiver $R_{i}$ which has $r$ possible decoding strategies, an optimal decoding strategy w.r.t. probability of error is given by
$$
\begin{align*} {\mathcal {D}}^{i}_{*} \!=\! \begin{cases} \displaystyle \arg \min \limits _{ j \in [r]}(|S({\mathcal {D}}^{i}_{j})|),\Gamma _{ic}^{i} \ge \max \{\Gamma ^{th}(\mathcal {D}_{1}^{i}),\ldots \Gamma ^{th}({\mathcal {D}}_{r}^{i})\} \\ \displaystyle \arg \min \limits _{ j \in [r]}(|P({\mathcal {D}}^{i}_{j})|),\text {otherwise}. \end{cases}\end{align*}
$$

#### Proof:

**Case 1: Side information is transmitted in the low** $\Gamma _{si}^{i}$ **regime.**

When the value of $\Gamma _{si}^{i}$ is considerably lower than that of $\Gamma _{ic}^{i}$, the order of the second term is higher than that of the first term in [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2). Therefore, the error performance is primarily determined by the second term, and we can approximate the probability of bit error obtained by ${\mathcal {D}}^{i}_{j}$ as
$$
\begin{equation*} P_{e}^{{\mathcal {D}}_{j}^{i}} \approx \frac {1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}{2}. \tag {10}\end{equation*}
$$

In this regime, the probability of error will not decrease significantly with an increase in $\Gamma _{ic}^{i}$, which can be inferred from the approximate expression in [(10)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn10). Thus, at low $\Gamma _{si}^{i}$ an optimal decoding strategy at $R_{i}$ will be given by ${\mathcal {D}}^{i}_{*} = \arg \min \limits _{ j \in [r]}(|S({\mathcal {D}}^{i}_{j})|)$.

**Case 2: Side information is transmitted in the high** $\Gamma _{si}^{i}$ **regime.**

In this regime, in [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2), the order of the second term is lower than that of the first term. Therefore, the expression for the probability of bit error can be approximated as
$$
\begin{equation*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}} \approx {\mathcal {P}}_{e}^{\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}}(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}. \tag {11}\end{equation*}
$$
Hence, in this regime, where the probability that a message in the side information of $R_{i}$ is decoded in error is very low, an optimal decoding strategy will be the one that minimizes the number of signal pairs in $P({\mathcal {D}}^{i}_{j})$, i.e., ${\mathcal {D}}^{i}_{*} = \arg \min \limits _{ j \in [r]}(|P({\mathcal {D}}^{i}_{j})|)$.

### Corollary 1:

If the receivers have noiseless side information, then an optimal decoding strategy w.r.t. probability of error is given by ${\mathcal {D}}^{i}_{*} = \arg \min \limits _{ j \in [r]}(|P({\mathcal {D}}^{i}_{j})|)$

### Remark 1:

For a given decoding strategy ${\mathcal {D}}_{j}^{i}$, suppose we want to ensure that the probability of error falls exponentially with increasing $\Gamma _{ic}^{i}$ until a specific cut-off value, say $P_{c} = 10^{-5}$. In [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2), the second term is independent of $\Gamma _{ic}^{i}$, so its value will not reduce with increasing $\Gamma _{ic}^{i}$. To ensure that ${\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}$ falls exponentially until $10^{-5}$, we find the value of $\Gamma _{si}^{i}$ required to get the second term equal to the cut-off value of ${\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}}$.
$$
\begin{equation*} \frac {1-(1-2{\mathcal {P}}_{e}^{si})^{|S({\mathcal {D}}^{i}_{j})|}}{2} \approx P_{c} \tag {12}\end{equation*}
$$
Simplifying the above equation in the AWGN channel by replacing ${\mathcal {P}}_{e}^{si}$ as mentioned in [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2) we get
$$
\begin{equation*} \Gamma _{si}^{th} \approx \frac {1}{2}\left \{{{Q^{-1}\left \{{{\frac {1-(1-2P_{c})^{\frac {1}{|S({\mathcal {D}}^{i}_{j})|}}}{2}}}\right \}}}\right \}^{2} \tag {13}\end{equation*}
$$
When $\Gamma _{si}^{i} \gt \Gamma _{si}^{th}$, then the probability of error until the cut-off value will be determined by the first term in [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2), hence will fall exponentially with increasing $\Gamma _{ic}^{i}$.

Based on the selection criterion in Theorem 3 above, we now propose the algorithm for finding an optimal decoding strategy ${\mathcal {D}}^{i}_{*}$ at receiver $R_{i}$ in Algorithm 1.

Algorithm 1

### Find the Best Decoding Strategy at $R_{i}$

Input: Encoding matrix **L**, side information $K_{i}$, the chosen PSK configuration $\mathcal {S}_{2^{N},\mathcal {M}}$, and the SNRs $\Gamma _{si}^{i}$ and $\Gamma _{ic}^{i}$.

Output: Best Decoding strategy, ${\mathcal {D}}^{i}_{*}$

1: Find all decoding strategies at $R_{i}$, say ${\mathcal {D}}^{i}_{1}, {\mathcal {D}}^{i}_{2}, \ldots , {\mathcal {D}}^{i}_{r}$.

2: Calculate the threshold values $\Gamma ^{th}(\mathcal {D}_{1}^{i}), \Gamma ^{th}(\mathcal {D}_{2}^{i}) \ldots \Gamma ^{th}({\mathcal {D}}_{r}^{i})$

3: **if** r==1 **then**

4: **return** ${\mathcal {D}}^{i}_{*} = {\mathcal {D}}^{i}_{1}$.

5: **end if**

6: **if** $\Gamma _{ic}^{i} \ge \max \{\Gamma ^{th}(\mathcal {D}_{1}^{i}), \Gamma ^{th}(\mathcal {D}_{2}^{i}) \ldots \Gamma ^{th}({\mathcal {D}}_{r}^{i})\}$ **then**

7: Determine $|S({\mathcal {D}}^{i}_{1})|, |S({\mathcal {D}}^{i}_{2})|, \ldots |S({\mathcal {D}}^{i}_{r})|$.

8: Compute $\mathbf {\mathcal {D}}_{min}^{i} =\arg \min \limits _{ j \in [r]}(|S({\mathcal {D}}^{i}_{j})|)$.

9: **if** $|{\mathcal {D}}_{min}^{i}|=z \gneq 1$ **then**

10: Determine $P({\mathcal {D}}^{i}_{min}(1)),\ldots P({\mathcal {D}}^{i}_{min}(z))$.

11: Compute $\mathbf {\mathcal {D}}_{min}^{i} =\arg \min \limits _{ j \in [z]}(|P({\mathcal {D}}^{i}_{min}(j))|)$.

12: **end if**

13: ${\mathcal {D}}^{i}_{*} = {\mathcal {D}}^{i}_{j}$, for some ${\mathcal {D}}^{i}_{j} \in \mathbf {\mathcal {D}}_{min}^{i}$.

14: **else**

15: Determine $P({\mathcal {D}}^{i}_{1}), P({\mathcal {D}}^{i}_{2}), \ldots P({\mathcal {D}}^{i}_{r})$.

16: Compute $\mathbf {\mathcal {D}}_{min}^{i} =\arg \min \limits _{ j \in [r]}(|P({\mathcal {D}}^{i}_{j})|)$.

17: **if** $|{\mathcal {D}}_{min}^{i}|=z \gneq 1$ **then**

18: Determine $S({\mathcal {D}}^{i}_{min}(1)), \ldots S({\mathcal {D}}^{i}_{min}(z))$.

19: Compute $\mathbf {\mathcal {D}}_{min}^{i} =\arg \min \limits _{ j \in [z]}(|S({\mathcal {D}}^{i}_{min}(j))|)$.

20: **end if**

21: ${\mathcal {D}}^{i}_{*} = {\mathcal {D}}^{i}_{j}$, for some ${\mathcal {D}}^{i}_{j} \in \mathbf {\mathcal {D}}_{min}^{i}$.

22: **end if**

### Remark 2:

For a receiver $R_{i}$, if there is more than one decoding strategy in the set $\mathbf {\mathcal {D}}_{min}^{i}$ computed in step 13 or step 21 of Algorithm 1, any one of them can be chosen arbitrarily for obtaining the best probability of error performance. The same is also true when there are multiple decoding strategies at step 6 in Algorithm 2.

Based on Corollary 1, a straightforward algorithm for selecting an optimal decoding strategy for the case where receivers have noiseless side information is given in Algorithm 2.

Algorithm 2

### Find the Best Decoding Strategy at $R_{i}$ When the Side Information Is Noiseless

Input: Encoding matrix **L**, side information $K_{i}$, and the chosen PSK configuration $\mathcal {S}_{2^{N},\mathcal {M}}$.

Output: Best Decoding strategy, ${\mathcal {D}}^{i}_{*}$

1: Find all decoding strategies at $R_{i}$, say ${\mathcal {D}}^{i}_{1}, {\mathcal {D}}^{i}_{2}, \ldots , {\mathcal {D}}^{i}_{r}$.

2: **if** r==1 **then**

3: **return** ${\mathcal {D}}^{i}_{*} = {\mathcal {D}}^{i}_{1}$.

4: **end if**

5: Determine $P({\mathcal {D}}^{i}_{1}), P({\mathcal {D}}^{i}_{2}), \ldots P({\mathcal {D}}^{i}_{r})$.

6: Compute $\mathbf {\mathcal {D}}_{min}^{i} =\arg \min \limits _{ j \in [r]}(|P({\mathcal {D}}^{i}_{j})|)$.

7: ${\mathcal {D}}^{i}_{*} = {\mathcal {D}}^{i}_{j}$, for some ${\mathcal {D}}^{i}_{j} \in \mathbf {\mathcal {D}}_{min}^{i}$.

**Complexity Analysis:** There will be $2^{N}-1$ linear combinations of index-coded bits for a length-$N$ index code. For a given receiver $R_{i}$, we will consider only those linear combinations that include an odd number of index coded bits containing the requested message. A linear combination is a valid decoding strategy at $R_{i}$ if it contains the message requested by $R_{i}$ along with a subset of its side information and none of the interfering messages. Hence, for finding the valid decoding strategies at a receiver, we need to check all the $2^{N}-1$ linear combinations of the $N$ index-coded bits Thus, the complexity for finding possible decoding strategies at a receiver in Step 1 of both algorithms is $\mathcal {O}(2^{N})$. Further, for each of the $r$ possible decoding strategies at $R_{i}$, to determine $P({\mathcal {D}}^{i}_{j})$, we need to calculate the value of the linear combination used by that decoding strategy at each of the $2^{N}$ signal points and then compare the values at adjacent signal points. This takes $\mathcal {O}(2^{N})$ operations. Hence the complexity of both the algorithms at a receiver $R_{i}$ is $\mathcal {O}(r2^{N})$, where $r$ is the number of decoding strategies at $R_{i}$.

## Illustrative Example

Consider the ICP and the chosen index code of length $N=3$ in Example 1, for which the chosen 8-PSK configuration is given in Fig. 1. For comparing the performances of different receivers, the signal-to-noise-ratios with which the side information is received at the different receivers are assumed to be the same, i.e., $\Gamma _{si}^{1} = \Gamma _{si}^{2}=\cdots = \Gamma _{si}^{5} = \Gamma _{si}$. Similarly, we also assume that the signal-to-noise ratios at which the index-coded messages are received are also the same across the different receivers, i.e., $\Gamma _{ic}^{1} = \Gamma _{ic}^{2}=\cdots = \Gamma _{ic}^{5} = \Gamma _{ic}$. The threshold values in decibels (dB) of $\Gamma _{ic}$ calculated using the expression in Lemma 1 are given in Table I for two values of $\Gamma _{si}$. Now, consider the performances of various decoding strategies at different receivers.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan.t1-3395332-large.gif)

**TABLE I** Threshold Values of $\Gamma _{ic}$ for Different Decoding Strategies at the Receivers in Example 1

Let us assume that the side information bits are received at a low value of SNR, say, at $\Gamma _{si} = 5$ dB. At $R_{1}$, there are a total of 4 decoding strategies. According to Theorem 3, an optimal decoding strategy will use the least number of side information bits. For $R_{1}$, $|S(\mathcal {D}_{1}^{1})|$ is 2, $|S(\mathcal {D}_{2}^{1})|$ is 4, $|S(\mathcal {D}_{3}^{1})|$ is 2 and $|S(\mathcal {D}_{4}^{1})|$ is 2. Each of the decoding strategies $\mathcal {D}_{1}^{1}$, $\mathcal {D}_{3}^{1}$, and $\mathcal {D}_{4}^{1}$ uses the same number of side information bits which is the least among all possible strategies at $R_{1}$. According to Algorithm 1, $\mathcal {D}_{1}^{1}$ will give the best performance as $|P(\mathcal {D}_{1}^{1})|=2$ which is the minimum among the three strategies mentioned above.

Similarly, at $R_{2}$, there are a total of 4 decoding strategies; the number of side information bits used by each of these is as follows: $|S(\mathcal {D}_{1}^{2})|=1$, $|S(\mathcal {D}_{2}^{2})|=4$, $|S(\mathcal {D}_{3}^{2})|=1$, and $|S(\mathcal {D}_{4}^{2})|=2$. Among the two strategies $\mathcal {D}_{1}^{2}$ and $\mathcal {D}_{3}^{2}$ using the minimum number of side information bits, $\mathcal {D}_{1}^{2}$ will be returned as the optimal decoding strategy by Algorithm 1 as we have $|P(\mathcal {D}_{1}^{2})|\lt |P(\mathcal {D}_{3}^{2})|$.

There is only one decoding strategy each at the receivers $R_{3}$, $R_{4}$, and $R_{5}$ for decoding their respective requested messages. While the receivers $R_{3}$ and $R_{5}$ use only one side information bit each, the receiver $R_{4}$ uses two side information bits. Since we assume similar noise characteristics for the channels from the source to all the receivers, we can compare the performances of different receivers. In that regard, among all the receivers, $R_{2}$ and $R_{3}$ perform the same, and the best as the optimal decoding strategy of both these receivers uses only one side information bit, and the number of adjacent signal pairs given by [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) is two. These two receivers are followed by $R_{5}$ in performance, which uses the same number of side information bits but has $|P(\mathcal {D}_{1}^{5})|=6$. The receiver $R_{1}$, which utilizes two side information bits, performs worse than $R_{5}$. $R_{4}$ utilizes the same number of side information bits as $R_{1}$ but $R_{4}$ performs the worst as $y_{3}$ has 8 signal pairs which are at the minimum Euclidean distance.

Now, we will consider the same setup but with the side information being broadcast at a higher value of $\Gamma _{si}$, equal to 12 dB. At a given receiver, the value of $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$ is calculated for all possible decoding strategies. We can clearly see from Lemma 1 that $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$ is an increasing function of $\Gamma _{si}$. So, for a high value of $\Gamma _{si}$, the value of $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$ is also high, as can be verified from Table I. So, according to Theorem 3, the performance of a decoding strategy will be dominated by the performance of the linear combination of index-coded bits used in that strategy which is given by [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2) for the AWGN channel.

At $R_{1}$, there are four decoding strategies, for each of which the set $P(\mathcal {D}^{1}_{j}), \ j \in [{4}]$ is determined. As shown in Fig. 2, for $\mathcal {D}^{1}_{1}$, there are two signal pairs at minimum distance differing in the value of $\hat {y}_{1}^{1}$, i.e., $P(\mathcal {D}^{1}_{1}) = \{(s_{0},s_{7}), (s_{3},s_{4})\}$. Similarly, there are four signal pairs at minimum distance differing in the value of $\hat {y}_{2}^{1}$, which implies that $|P(\mathcal {D}^{1}_{2})| = 4$. For the decoding strategy $\mathcal {D}^{1}_{3}$ using the index-coded bit $\hat {y}_{3}^{1}$ for decoding $x_{1}$, $|P(\mathcal {D}^{1}_{3})| = 8$, whereas for $\mathcal {D}^{1}_{4}$, $|P(\mathcal {D}^{1}_{4})| = 6$. Hence, using Theorem 3, we find that an optimal decoding strategy at receiver $R_{1}$ is $\mathcal {D}^{1}_{1}$.

![Figure 2](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan2ab-3395332-large.gif)

**Figure 2.** Decoding at $R_{1}$: (a) $P(\mathcal {D}^{1}_{1})$ and $P(\mathcal {D}^{1}_{2})$ (b) $P(\mathcal {D}^{1}_{3})$ and $P(\mathcal {D}^{1}_{4})$.

Similarly, at $R_{2}$, there are four decoding strategies, for each of which, the signal pairs at the minimum Euclidean distance differing in the value of the linear combination of index-coded bits are shown in Fig. 3. The number of such signal pairs differing in the value of $\hat {y}^{2}_{1} \oplus \hat {y}^{2}_{2}$ used by $\mathcal {D}^{2}_{1}$ is two, whereas, for the strategy $\mathcal {D}^{2}_{2}$, there are four signal pairs in $P(\mathcal {D}^{2}_{2})$ given by $\{(s_{0},s_{7}), (s_{1},s_{2}),(s_{3},s_{4}),(s_{5},s_{6})\}$. Likewise, for $\mathcal {D}^{3}_{2}$ using the linear combination $\hat {y}^{2}_{1}\oplus \hat {y}^{2}_{3}$ of estimated index-coded bits, $|P(\mathcal {D}^{2}_{3})| = 4$, whereas for $\mathcal {D}^{4}_{2}$ using $\hat {y}^{2}_{1}\oplus \hat {y}^{2}_{2} \oplus \hat {y}^{2}_{3}$, we have $|P(\mathcal {D}^{2}_{3})| = 6$. Hence, an optimal decoding strategy is $\mathcal {D}^{2}_{1}$.

![Figure 3](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan3ab-3395332-large.gif)

**Figure 3.** Decoding at $R_{2}$: (a) $P(\mathcal {D}^{2}_{1})$ and $P(\mathcal {D}^{2}_{2})$ (b) $P(\mathcal {D}^{2}_{3})$ and $P(\mathcal {D}^{2}_{4})$.

For the receivers $R_{3}, R_{4}$ and $R_{5}$, there is only one decoding strategy for which $|P(\mathcal {D}^{3}_{1})| = 2$, $|P(\mathcal {D}^{4}_{1})| = 8$ and $|P(\mathcal {D}^{5}_{1})| = 6$ as shown in Fig. 4. So, in the high $\Gamma _{si}$ regime, the best performance at the receivers $R_{1}, R_{2}$ and $R_{3}$ are obtained by using the decoding strategies $\mathcal {D}_{1}^{1}$, $\mathcal {D}_{1}^{2}$, and $\mathcal {D}_{1}^{3}$, respectively. All these receivers will have the same performance and the best among all the receivers as the number of adjacent signal pairs as in [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) is 2, which is the least among all the receivers. The receiver $R_{5}$ employing the decoding strategy $\mathcal {D}^{5}_{1}$, which has six adjacent signal pairs, will perform second-best, followed by $R_{4}$, performing the worst among all the receivers.

![Figure 4](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan4abc-3395332-large.gif)

**Figure 4.** (a) Decoding at $R_{3}$: $P(\mathcal {D}^{3}_{1})$ (b) Decoding at $R_{4}$: $P(\mathcal {D}^{4}_{1})$ and (c) Decoding at $R_{5}$: $P(\mathcal {D}^{5}_{1})$.

### Example 2:

Consider an ICP with $m=n=7$ and $W_{i}=x_{i} \ \forall {i} \in \{1,2,3,4,5,6,7\}$. The server transmits $\mathcal {X}$ after BPSK modulation over an AWGN channel during low traffic hours, which results in the following side information at the receivers: $K_{1}=\{\tilde {x}_{2},\tilde {x}_{3},\tilde {x}_{4},\tilde {x}_{5},\tilde {x}_{6},\tilde {x}_{7}\}$, $K_{2}=\{\tilde {x}_{1},\tilde {x}_{3},\tilde {x}_{4},\tilde {x}_{5},\tilde {x}_{7}\}$, $K_{3}=\{\tilde {x}_{1},\tilde {x}_{4},\tilde {x}_{6},\tilde {x}_{7}\}$, $K_{4}=\{\tilde {x}_{2},\tilde {x}_{5},\tilde {x}_{6}\}$, $K_{5}=\{\tilde {x}_{1},\tilde {x}_{2}\}$, $K_{6}=\{\tilde {x}_{3}\}~and~K_{7}=\phi$. For this ICP, the length of an optimal linear index code is $N=4$. We consider the linear encoding scheme specified by $\begin{aligned} \mathbf {L} = \begin{bmatrix} 1 & 1 & 0 & 0 & 1 & 0 & 0 \\ 0 & 0 & 0 & 1 & 0 & 0 & 0 \\ 0 & 0 & 1 & 0 & 0 & 1 & 0 \\ 0 & 0 & 0 & 0 & 0 & 0 & 1 \\ \end{bmatrix}^{T} \end{aligned}$ and the index-coded vector is $\mathbf {y}=(y_{1},y_{2},y_{3},y_{4})$ where $\mathbf {y}=\mathbf {x}\mathbf {L}$, for $\mathbf {x} \in \mathbb {F}_{2}^{7}$. We transmit the above index code using the 16-PSK constellation given in Fig. 5 over an AWGN channel. At receiver $R_{i}$, after performing ML decoding on the received signal, the vector of estimated index-coded bits is $\mathbf {\hat {y}}^{i}= (\hat {y}^{i}_{1}, \hat {y}^{i}_{2},\hat {y}^{i}_{3}, \hat {y}^{i}_{4})$. The different decoding strategies for each of the receivers are given below.

![Figure 5](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan5-3395332-large.gif)

**Figure 5.** 16-PSK mapping used for modulating the index-coded bits in Example 2.

At $R_{1}$:

- $\hat {x_{1}}=\mathcal {D}_{1}^{1}(\mathbf {\hat {y}}^{1},K_{1}) := \hat {y}^{1}_{1} \oplus \tilde {x}_{2} \oplus \tilde {x}_{5}$
- $\hat {x_{1}}=\mathcal {D}_{2}^{1}(\mathbf {\hat {y}}^{1},K_{1}):= \hat {y}^{1}_{1} \oplus \hat {y}^{1}_{2} \oplus \tilde {x}_{2} \oplus \tilde {x}_{5} \oplus \tilde {x}_{4}$
- $\hat {x_{1}}=\mathcal {D}_{3}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{3} \oplus \tilde {x}_{2} \oplus \tilde {x}_{5} \oplus \tilde {x}_{3} \oplus \tilde {x}_{6}$
- $\hat {x_{1}}=\mathcal {D}_{4}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{4}\oplus \tilde {x}_{2} \oplus \tilde {x}_{5} \oplus \tilde {x}_{7}$
- $\hat {x_{1}}=\mathcal {D}_{5}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1}\oplus \hat {y}^{1}_{2} \oplus \hat {y}^{1}_{3}\oplus \tilde {x}_{2} \oplus \tilde {x}_{5} \oplus \tilde {x}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{6}$
- $\hat {x_{1}}=\mathcal {D}_{6}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{2} \oplus \hat {y}^{1}_{4} \oplus \tilde {x}_{2} \oplus \tilde {x}_{5} \oplus \tilde {x}_{4} \oplus \tilde {x}_{7}$
- $\hat {x_{1}}=\mathcal {D}_{7}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{3} \oplus \hat {y}^{1}_{4} \oplus \tilde {x}_{2} \oplus \tilde {x}_{3} \oplus \tilde {x}_{5} \oplus \tilde {x}_{6} \oplus \tilde {x}_{7}$
- $\hat {x_{1}}=\mathcal {D}_{8}^{1}(\mathbf {\hat {y}}^{1},K_{1}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{1}_{2} \oplus \hat {y}^{1}_{3} \oplus \hat {y}^{1}_{4}\oplus \tilde {x}_{2} \oplus \tilde {x}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5} \oplus \tilde {x}_{6} \oplus \tilde {x}_{7}$

At $R_{2}$:

- $\hat {x_{2}}=\mathcal {D}_{1}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{1}\oplus \tilde {x}_{1} \oplus \tilde {x}_{5}$
- $\hat {x_{2}}=\mathcal {D}_{2}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{1} \oplus \hat {y}^{2}_{2} \oplus \tilde {x}_{1} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5}$
- $\hat {x_{2}}=\mathcal {D}_{3}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{2}_{1} \oplus \hat {y}^{2}_{4} \oplus \tilde {x}_{1} \oplus \tilde {x}_{5} \oplus \tilde {x}_{7}$
- $\hat {x_{2}}=\mathcal {D}_{4}^{2}(\mathbf {\hat {y}}^{2},K_{2}) :=\hat {y}^{1}_{1} \oplus \hat {y}^{2}_{2} \oplus \hat {y}^{2}_{4} \oplus \tilde {x}_{1} \oplus \tilde {x}_{4} \oplus \tilde {x}_{5} \oplus \tilde {x}_{7}$

At $R_{3}$:

- $\hat {x_{3}}=\mathcal {D}_{1}^{3}(\mathbf {\hat {y}}^{3},K_{3}) :=\hat {y}^{3}_{3} \oplus \tilde {x}_{6}$
- $\hat {x_{3}}=\mathcal {D}_{2}^{3}(\mathbf {\hat {y}}^{3},K_{3}) :=\hat {y}^{3}_{2} \oplus \hat {y}^{3}_{3} \oplus \tilde {x}_{4} \oplus \tilde {x}_{6}$
- $\hat {x_{3}}=\mathcal {D}_{3}^{3}(\mathbf {\hat {y}}^{3},K_{3}) :=\hat {y}^{3}_{3} \oplus \hat {y}^{3}_{4} \oplus \tilde {x}_{6} \oplus \tilde {x}_{7}$
- $\hat {x_{3}}=\mathcal {D}_{4}^{3}(\mathbf {\hat {y}}^{3},K_{3}) :=\hat {y}^{3}_{2} \oplus \hat {y}^{3}_{3} \oplus \hat {y}^{3}_{4} \oplus \tilde {x}_{4} \oplus \tilde {x}_{6} \oplus \tilde {x}_{7}$

At $R_{4}$:

- $\hat {x_{4}}=\mathcal {D}_{1}^{4}(\mathbf {\hat {y}}^{4},K_{4}) :=\hat {y}^{4}_{2}$

At $R_{5}$:

- $\hat {x_{5}}=\mathcal {D}_{1}^{5}(\mathbf {\hat {y}}^{5},K_{5}) :=\hat {y}^{5}_{1} \oplus \tilde {x}_{1} \oplus \tilde {x}_{2}$

At $R_{6}$:

- $\hat {x_{6}}=\mathcal {D}_{1}^{6}(\mathbf {\hat {y}}^{6},K_{6}) :=\hat {y}^{6}_{3} \oplus \tilde {x}_{3}$

At $R_{7}$:

- $\hat {x_{7}}=\mathcal {D}_{1}^{7}(\mathbf {\hat {y}}^{7},K_{7}) :=\hat {y}_{4}^{7}$

As in the previous example, we consider that the SNR at which side information bits are received is the same across all the receivers given by $\Gamma _{si}$ and similarly the SNR at which the PSK-modulated index code is received at all the receivers is given by $\Gamma _{ic}$. Initially, we consider that side information is received at a low SNR, let’s say $\Gamma _{si}=5$ dB. At $R_{1}$, there are a total of eight decoding strategies. According to Theorem 3, we will choose a strategy that utilizes the least number of side information bits. For $R_{1}$, we can clearly see that $|S(\mathcal {D}_{1}^{1})|=2$, $|S(\mathcal {D}_{2}^{1})|=3$, $|S(\mathcal {D}_{3}^{1})|=4$, $|S(\mathcal {D}_{4}^{1})|=3$, $|S(\mathcal {D}_{5}^{1})|=5$, $|S(\mathcal {D}_{6}^{1})|=4$, $|S(\mathcal {D}_{7}^{1})|=5$ and $|S(\mathcal {D}_{8}^{1})|=6$. So the best performance for $R_{1}$ will be obtained using $\mathcal {D}_{1}^{1}$, which uses the least number of side information bits among the eight strategies.

Likewise, for $R_{2}$, there are four possible decoding strategies for which we can calculate the number of side information bits used to decode $x_{2}$ as $|S(\mathcal {D}_{1}^{2})|=2$, $|S(\mathcal {D}_{2}^{2})|=3$, $|S(\mathcal {D}_{3}^{2})|=3$ and $|S(\mathcal {D}_{4}^{2})|=4$. Using case 1 of Theorem 3, the optimal decoding strategy at $R_{2}$ is $\mathcal {D}_{1}^{2}$.

Similarly, for $R_{3}$, $\mathcal {D}_{1}^{3}$ is an optimal decoding strategy that uses only one side information bit to decode $x_{3}$. Other receivers $R_{4}, R_{5}, R_{6}$, and $R_{7}$ can decode their demanded messages in only one way for which $|S(\mathcal {D}_{1}^{4})|=0$, $|S(\mathcal {D}_{1}^{5})|=2$, $|S(\mathcal {D}_{1}^{6})|=1$ and $|S(\mathcal {D}_{1}^{7})|=0$ respectively.

Among all the receivers, $R_{4}$ and $R_{7}$ use no side information for decoding, so they perform the best in the low $\Gamma _{si}$ regime. Among $R_{4}$ and $R_{7}$, $R_{4}$ will perform better than $R_{7}$ as the number of signaling pair given by [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) is more for $R_{7}$ than that of $R_{4}$ i.e, $|P(\mathcal {D}_{1}^{4})|=4$ while $|P(\mathcal {D}_{1}^{7})|=16$. So, $R_{4}$ performs the best among all the receivers, followed by $R_{7}$. The optimal decoding strategies of $R_{3}$ and $R_{6}$ use only one side information bit and $|P(\mathcal {D}_{1}^{3})|=|P(\mathcal {D}_{1}^{6})|=8$, thus according to [(5)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn5), both receivers will have the same performance. Similarly, since the optimal decoding strategies for $R_{1}$, $R_{2}$, and $R_{5}$ use two side information bits each and also the number of signal pairs given by [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) is equal for all strategies, so all these three receivers will have the same performance. Thus, $R_{3}$ and $R_{6}$ perform worse than $R_{7}$ but better than $R_{1}$, $R_{2}$, and $R_{5}$.

At high $\Gamma _{si}$, say 20 dB, the error floor will happen only at high $\Gamma _{ic}$, so the performance of any decoding strategy will be governed by the criterion given in Case 2 of Theorem 3. Using the same procedure as in Example 1, we can find the values of $P({\mathcal {D}}_{j}^{1}), \ j \in [{8}]$. There are two signal pairs at the minimum Euclidean distance for $\mathcal {D}_{1}^{1}$, i.e., $|P(\mathcal {D}_{1}^{1})|=2$. Similarly, for the decoding strategy $\mathcal {D}_{2}^{1}$, there are two signal pairs at the minimum Euclidean distance where $\hat {y}_{1}^{1}\oplus \hat {y}_{2}^{1}$ differs, which implies that $|P(\mathcal {D}_{2}^{1})|=2$. For the decoding strategy $\mathcal {D}_{3}^{1}$ using the linear combination $\hat {y}_{1}^{1}\oplus \hat {y}_{3}^{1}$, $|P(\mathcal {D}_{3}^{1})|=6$, whereas, for $\mathcal {D}_{4}^{1}$, $|P(\mathcal {D}_{4}^{1})|=14$. Likewise, for $\mathcal {D}_{5}^{1}$ in which $\hat {y}_{1}^{1} \oplus \hat {y}_{2}^{1} \oplus \hat {y}_{3}^{1}$ is used, there are six signal-pairs at the minimum Euclidean distance, i.e., $|P(\mathcal {D}_{5}^{1})|=6$, whereas, for $\mathcal {D}_{6}^{1}$ using the linear combination $\hat {y}_{1}^{1} \oplus \hat {y}_{2}^{1} \oplus \hat {y}_{4}^{1}$, we have $|P(\mathcal {D}_{6}^{1})|=14$. We also have $\mathcal {D}_{7}^{1}$ for which $|P(\mathcal {D}_{7}^{1})|=10$, and $\mathcal {D}_{8}^{1}$ which has $|P(\mathcal {D}_{8}^{1})|=10$. Hence, we find that for $R_{1}$, there are two decoding strategies, $\mathcal {D}_{1}^{1}$ and $\mathcal {D}_{2}^{1}$, which has the minimum multiplicity of signal pairs at the minimum Euclidean distance. Now, with respect to minimizing the second term of [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2), we have $|S(\mathcal {D}_{1}^{1})|=2$ and $|S(\mathcal {D}_{2}^{1})|=3$. Hence, for $R_{1}$, the optimal decoding strategy is $\mathcal {D}_{1}^{1}$.

Similarly, at the receiver $R_{2}$, there are four decoding strategies as listed above. For $\mathcal {D}_{1}^{2}$, where only the index-coded bit $\hat {y}_{1}^{2}$ is used, we get $|P(\mathcal {D}_{1}^{2})|=2$. The decoding strategy $\mathcal {D}_{2}^{2}$ which employs the linear combination $\hat {y}_{1}^{2} \oplus \hat {y}_{2}^{2}$ has $|P(\mathcal {D}_{2}^{2})|=2$, whereas for $\mathcal {D}_{3}^{2}$ which used $\hat {y}_{1}^{2} \oplus \hat {y}_{4}^{2}$, we have $|P(\mathcal {D}_{3}^{2})|=14$. On the same note, for $\mathcal {D}_{4}^{2}$, the number of adjacent signal pairs where the linear combination used in the above strategy differs is 14. By Theorem 3, among $\mathcal {D}_{1}^{2}$ and $\mathcal {D}_{2}^{2}$, the performance obtained by the one that uses the minimum number of side information bits will be better, and hence $\mathcal {D}_{1}^{2}$ gives the best performance for $R_{2}$.

At the receiver $R_{3}$, there are four decoding strategies, for which we can find that $|P(\mathcal {D}_{1}^{3})|=8$, $|P(\mathcal {D}_{2}^{3})|=4$, $|P(\mathcal {D}_{3}^{3})|=8$ and $|P(\mathcal {D}_{4}^{3})|=12$ which implies that an optimal decoding strategy at $R_{3}$ is $\mathcal {D}_{2}^{3}$. For each of the remaining receivers, $R_{4}$, $R_{5}$, $R_{6}$, $R_{7}$, there is only one decoding strategy for decoding their desired messages. We can calculate the number of signal-pairs at the minimum Euclidean distance for each of them as $|P(\mathcal {D}_{1}^{4})|=4$, $|P(\mathcal {D}_{1}^{5})|=2$, $|P(\mathcal {D}_{1}^{6})|=8$, and $|P(\mathcal {D}_{1}^{7})|=16$.

**Noiseless Side Information Case -** If we consider that the receivers have noiseless side information, then according to Corollary 1, an optimal decoding strategy for any receiver will be the one for which the linear combination used has the least number of signal pairs at the minimum Euclidean distance. In Example 1, at $R_{1}$, the optimal decoding strategy is $\mathcal {D}_{1}^{1}$ since $|P(\mathcal {D}_{1}^{1})|=2$ is the least among all the four decoding strategies. Similarly, at $R_{2}$, $\mathcal {D}_{1}^{2}$ gives the best performance. There is only one decoding strategy for each of $R_{3}$, $R_{4}$, and $R_{5}$. Summarizing, $R_{1}, R_{2}$ and $R_{3}$ performs the best followed by $R_{5}$ and $R_{4}$ which performs the worst.

Similarly, in Example 2, at $R_{1}$, the best performance will be given by any of the two decoding strategies, $\mathcal {D}_{1}^{1}$ and $\mathcal {D}_{2}^{1}$ as $|P(\mathcal {D}_{1}^{1})|=|P(\mathcal {D}_{2}^{1})|=2$. At $R_{2}$ also $|P(\mathcal {D}_{1}^{2})|=|P(\mathcal {D}_{2}^{2})|=2$ is the least among the four strategies, so both give the same best performance, and we can choose one arbitrarily from them. Likewise, at $R_{3}$, the optimal strategy is $\mathcal {D}_{2}^{3}$. There is only one decoding strategy at each of the other receivers. Comparing the performances across the receivers, $R_{1}, R_{2}$, and $R_{5}$ perform the best. $R_{3}$ and $R_{4}$ performs the same but worse than $R_{1}, R_{2}$, and $R_{5}$, and are followed by $R_{6}$ with $R_{7}$ being the worst-performing receiver as $|P(\mathcal {D}_{1}^{7})|=16$ is the maximum.

## Validity of Results Over Fading Channel

For a given ICP and a chosen index code, assume that the index-coded vector after modulation using an $M$-PSK constellation is transmitted over a fading channel. For an index-coded vector **y**, the received signal at a receiver $R_{i}$ is $c_{i} = h_{i} \mathcal {M}(\mathbf {y}) + n_{i}$, where $h_{i}$ is the fade coefficient of the channel between the source and the receiver $R_{i}$, $\mathcal {M}$ denotes the mapping from the index-coded vector to a signal point in the $M$-PSK constellation, and $n_{i}$ is the Gaussian noise added at $R_{i}$ which is assumed to have mean zero and variance $N_{0}$. Assume that the receivers have perfect channel state information and follow the two-step process of first estimating the transmitted signal point or, equivalently, the index-coded bits and then index-decoding to estimate their desired messages.

Under this assumption, the results in Section III continue to hold, and the best decoding strategy at receiver $R_{i}$ in a low $\Gamma _{si}^{i}$ regime is the one that utilizes the least number of side information bits. In contrast, in the high $\Gamma _{si}^{i}$ regime, the best decoding strategy continues to be the one with the minimum multiplicity of signal pairs at a distance equal to the minimum Euclidean distance of the constellation used. In the noiseless side information case, the probability of error expression can be expressed similarly to the AWGN channel. The symbol error probability of $M$-PSK in Rayleigh channel is given in<sup>16</sup> and using that we can write $\mathcal {P}({\mathcal {D}}_{j}^{i})$ as
$$
\begin{align*} {\mathcal {P}}_{e}^{{\mathcal {D}}_{j}^{i}} \lt \alpha \left [{{\frac {(M-1)}{M}-\beta _{s} \left \{{{\frac {1}{2}+\frac {1}{\pi }\tan ^{-1}{\left ({{\beta _{s}\cot \left ({{\frac {\pi }{M}}}\right )}}\right )}}}\right \}}}\right ] \tag {14}\end{align*}
$$
where, $\alpha =\frac {|P({{\mathcal {D}}_{j}^{i}})|}{2^{N}}$, $\beta _{s}=\sqrt {\frac {g_{PSK}\gamma _{s}}{1+g_{PSK}\gamma _{s}}}$, $g_{PSK}=\sin ^{2}\left ({{\frac {\pi }{M}}}\right )$ and $\gamma _{s}=\Gamma _{ic}^{i}\log _{2}M$.

The probability of error expression for the noisy side information case will continue to be [(2)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn2) with
$$
\begin{equation*} {\mathcal {P}}_{e}^{si}= \frac {1}{2}\left ({{1-\sqrt {\frac {\Gamma _{si}^{i}}{\Gamma _{si}^{i}+1}}}}\right ). \tag {15}\end{equation*}
$$
Using the expressions for the probability of error above and Lemma 1, we can derive the formula for $\Gamma ^{th}({\mathcal {D}}_{j}^{i})$ in a manner akin to what was done for the AWGN channel. In the following section, we give some simulation results validating that the probability of error performance indeed depends on the criterion given in Theorem 2.

## Simulation Results

For a given ICP, the index code is transmitted over noisy broadcast channels after PSK modulation. For comparing the probability of error performances of different receivers, we assume that the characteristics of the Gaussian noise added at each of these receivers are the same. Let the noise be distributed as $\mathcal {N}(0,N_{0})$. For a fading channel, the received symbol at receiver $R_{i}$ is given as $c_{i} = h_{i} \mathcal {M}(\mathbf {y}) + n_{i}$, where $n_{i}$ is the additive white Gaussian noise. We assume that the fade coefficient $h_{i}$ has a Rayleigh distribution and that the perfect channel state information is available at the receivers.

Consider the ICP in Example 1, where the index-coded bits are modulated using the 8-PSK constellation shown in Fig. 1. Let the broadcast side information be received at a low SNR, say $\Gamma _{si}=5$ dB at all the receivers. For this problem, we can see from Fig. 1, that the best probability of error performance for $R_{1}$ is obtained by the decoding strategies $\mathcal {D}_{1}^{1}$, $\mathcal {D}_{3}^{1}$ and $\mathcal {D}_{4}^{1}$, followed by $\mathcal {D}_{2}^{1}$. This order of the BER plots obtained by the decoding strategies is the same as the increasing number of side information bits used in each of these decoding strategies. Out of $\mathcal {D}_{1}^{1}$, $\mathcal {D}_{3}^{1}$ and $\mathcal {D}_{4}^{1}$ we can see that $\mathcal {D}_{1}^{1}$ performs the best as $|P(\mathcal {D}_{1}^{1})|=2$. Similarly, at $R_{2}$, the best performance is obtained by $\mathcal {D}_{2}^{1}$. The number of side information bits used in different decoding strategies at $R_{2}$ is $|S(\mathcal {D}^{2}_{1})| = |S(\mathcal {D}^{2}_{3})| \lt |S(\mathcal {D}^{2}_{4})| \lt |S(\mathcal {D}^{2}_{2})|$. In Fig. 6a, we can see that the BER plots of decoding strategies follow the same order as the number of side information bits used by them. There is only one decoding strategy for each of $R_{3}, R_{4}$, and $R_{5}$.

Among the receivers, $R_{2}$ and $R_{3}$ will have the same and the best performance, followed by $R_{5}$, which uses one side information bit, followed by $R_{1}$. We can see in the simulation results that $R_{4}$ performs the worst. We have discussed performances over the AWGN channel, but the same order of BER plots can be seen over a Rayleigh fading channel also at $\Gamma _{si}=20$ dB as shown in Fig. 7a.

![Figure 6](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan6-3395332-large.gif)

**Figure 6.** Example 1 - Simulated and theoretical plots comparing the performances of decoding strategies with receivers having noisy side information over the AWGN channel.

![Figure 7](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan7-3395332-large.gif)

**Figure 7.** Example 1 - Simulation result comparing the performances of decoding strategies with receivers having noisy side information over Rayleigh channel.

We now consider the same setup but with $\Gamma _{si}=12$ dB. For this case, we can see from Fig. 6b that the best probability of error performance at $R_{1}$ is obtained for the decoding strategy $\mathcal {D}^{1}_{1}$, followed by $\mathcal {D}^{1}_{2}$, then $\mathcal {D}^{1}_{4}$, with $\mathcal {D}^{1}_{3}$ giving the worst performance. This ordering of the performances of the decoding strategies $\{\mathcal {D}^{1}_{j}\}_{j \in [{4}]}$ is the same as that of the number of elements in their corresponding sets $\{P(\mathcal {D}^{1}_{j})\}_{j \in [{4}]}$. Similarly at receiver $R_{2}$, we have $|P(\mathcal {D}^{2}_{1})| \lt |P(\mathcal {D}^{2}_{2})| = |P(\mathcal {D}^{2}_{3})| \lt |P(\mathcal {D}^{2}_{4})|$. It can be seen that the probability of error performances of the decoding strategies at $R_{2}$ follow this same order in the simulation results in Fig. 6b.

Further, across different receivers, since we are assuming the same noise characteristics, the optimal decoding strategies at $R_{1}$, $R_{2}$, and $R_{3}$ all give the same and the best probability of error performance as the number of signal-pairs in $P(\mathcal {D}^{1}_{1})$, $P(\mathcal {D}^{2}_{1})$ and $P(\mathcal {D}^{3}_{1})$ are all equal to two. However, $R_{1}$ will perform worse than the other two at very high $\Gamma _{ic}$ as it uses more side information. $R_{5}$ performs second-best to it with $R_{4}$ performing the worst among all. Over a fading channel under perfect channel state information, in the high-SNR regime, say $\Gamma _{si}=45$ dB, it can be seen in Fig. 7b that the order of the performances of the decoding strategies is the same as that discussed for the AWGN channel.

For Example 2, the transmission of the 4-bit index code is done after 16-PSK modulation using the constellation shown in Fig. 5 over an AWGN broadcast channel at $\Gamma _{si}=5$ dB, and the simulation results are shown in Fig. 8. We can see that $R_{4}$ and $R_{7}$ perform better than the other receivers as both do not use any side information to decode their required messages. In the simulation result, $R_{4}$ performs better than $R_{7}$ as $|P(\mathcal {D}_{1}^{4})|=4$ while $|P(\mathcal {D}_{1}^{7})|=16$. In Fig. 8, we can see that the error floor value of $\mathcal {D}_{1}^{1}$ is the lowest among that of all the decoding strategies at $R_{1}$. Likewise, for $R_{2}$, we see that $\mathcal {D}_{1}^{2}$ performs the best. $R_{1}, R_{2}$ and $R_{5}$ are showing the same performance after some $\Gamma _{ic}$ the approximate value of which can be obtained from Lemma 1. It can be seen that $R_{3}$ and $R_{6}$ perform better than $R_{1}, R_{2}$ and $R_{5}$ but worse than $R_{7}$ as $|S(\mathcal {D}_{1}^{6})|= |S(\mathcal {D}_{1}^{3})|=1$. Thus, the criterion corresponding to Case 1 of Theorem 3 holds to be true. We will observe the same pattern in the fading channel also. In the high $\Gamma _{si}$ regime, the criterion mentioned will be valid and can be verified by simulation. Here also, the same pattern of probability of error performance will be observed in the fading channel.

![Figure 8](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan8-3395332-large.gif)

**Figure 8.** Example 2 - Simulation result comparing the performances of decoding strategies with receivers having noisy side information over the AWGN channel at $\Gamma _{si}=5$dB.

The noiseless side information scenario is considered for Example 2 over the AWGN channel for which the simulation results are given in Fig. 9. It can be seen that the best probability of error performance at the receiver $R_{1}$ is obtained when it uses either $\mathcal {D}_{1}^{1}$ or $\mathcal {D}_{2}^{1}$. At $R_{2}$, according to Algorithm 2, $\mathcal {D}_{1}^{2}$ will perform the best. For $R_{3}$, we have already seen that $|P(\mathcal {D}_{2}^{3})| \lt |P(\mathcal {D}_{1}^{3})| = |P(\mathcal {D}_{3}^{3})| \lt |P(\mathcal {D}_{4}^{3})|$ and the simulation results validate that an optimal decoding strategy is indeed $\mathcal {D}_{2}^{3}$. The simulation plots corresponding to different decoding strategies at $R_{3}$ also illustrate Corollary 1 as $\mathcal {D}_{2}^{3}$ using two index coded bits is performing better than $\mathcal {D}_{1}^{3}$ which uses only one index coded bit. The receivers $R_{4}$, $R_{5}$, $R_{6}$, and $R_{7}$ decode their requested messages using the only decoding strategy available to them. Under the assumption of the same noise characteristics, the receivers $R_{1}$, $R_{2}$, and $R_{5}$ have identical and the best probability of error performances among all the receivers. This can be explained using the fact that the best decoding strategy at each of these three receivers has only two signal pairs at the minimum distance in the 16-PSK constellation in Fig. 5, which is also the minimum across all the decoding strategies at all the receivers. The receivers $R_{3}$ and $R_{4}$ perform second-best to them, $R_{6}$ performs better than $R_{7}$ but worse than the others, and $R_{7}$ has the worst probability of error performance among all the receivers. The BER curves corresponding to different decoding strategies at the receivers follow the same order for the Rayleigh fading channel also.

![Figure 9](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan9-3395332-large.gif)

**Figure 9.** Example 2 - Simulated and theoretical result comparing the performance in Noiseless Side Information System over the AWGN channel.

![Figure 10](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan10-3395332-large.gif)

**Figure 10.** Example 1 - Comparison of the performances of receivers $R_{3}$ and $R_{4}$ with noisy side information at $\Gamma _{si}=12$ dB with different mappings over the AWGN channel.

Now, consider Fig. 11. It shows the bit error rate performances of all the decoding strategies at the receiver $R_{1}$ in Example 1 when the 3-bit index code is transmitted using an 8-PSK constellation with Gray-mapping and using an 8-QAM constellation with Gray-mapping, respectively. Because of the larger minimum distance of the QAM constellation, we may expect the BER performance obtained for any decoding strategy with QAM to be better than the best BER performance obtained with PSK modulation. However, from Fig. 11, it can be observed that this is not the case. While it is true that the best decoding strategy with QAM performs the best overall, the other three decoding strategies when used with QAM do not outperform the best PSK-based scheme. Since QAM-modulated transmission of index codes does not give uniformly better BER performance over PSK-modulated transmission for any decoding strategy, the problem considered in this manuscript of selecting the best decoding strategy at a receiver is worth studying.

![Figure 11](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan11-3395332-large.gif)

**Figure 11.** Comparison of the BER performances of the decoding strategies at $R_{1}$ in Example 1 with PSK and QAM.

Further, it can also be observed that the BER performances of the decoding strategies when used with QAM do not follow the same order as in the case of PSK. This implies that the criterion for selection of the best decoding strategy that was derived in the current manuscript for PSK does not hold for QAM-modulated transmission of index codes. This is because of the asymmetry in the QAM constellation and the resulting pair-wise distance distributions. The best and worst decoding strategies in Fig. 11 for QAM-modulated transmission of index codes and two-step decoding have been identified from the simulation results only.

## Performance of Receivers Under Different PSK Mappings

For a given ICP and chosen index code, at receiver $R_{i}$, consider that side information is transmitted at a high SNR, i.e., $\Gamma _{si}^{i}\gg \Gamma _{si}^{th}$. In this setting, let us assume that $R_{i}$ has to meet some minimum performance requirements. In such a case, in addition to choosing the best decoding strategy for a given mapping of index-coded bits, we can also optimize over different $M$-PSK mappings. This idea is illustrated using the following example.

For an 8-PSK constellation, there exists $\frac {7!}{2}$ distinct mappings of signal points. We have already listed the different decoding strategies for all receivers. Here, we consider five different mappings as shown in Fig. 12. We can calculate $|P({\mathcal {D}}_{j}^{i})|$ using [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) for each mapping. In Table II, the values of $|P({\mathcal {D}}_{j}^{i})|$ for the five mappings considered are listed. For a given mapping, the entries in red color in Table II correspond to the decoding strategies that will result in the optimal probability of error performance at a receiver. Suppose $R_{3}$ has to meet some minimum bit error rate value. $R_{3}$ decodes $\hat {x}_{3}$ by using $\mathcal {D}_{1}^{3}$, so we will choose such a mapping for which the value of $|P(\mathcal {D}_{1}^{3})|$ is the least. The criterion to choose such a mapping is to keep all the signal points that have the same value of $\hat {y}^{3}_{1} \oplus \hat {y}^{3}_{2}$ adjacent to each other, in turn, $|P(\mathcal {D}_{1}^{3})|=2$. There will be several mappings where the above-mentioned criteria will be met. Out of the five mappings that we have considered, from Table II, we can see that the probability of error is the least for $R_{3}$ when the mappings $\mathcal {M}_{1}$ and $\mathcal {M}_{4}$ are used.

![Figure](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan.t2-3395332-large.gif)

**TABLE II** $|P({\mathcal {D}}_{j}^{i})|$ Values for Different $M$ -PSK Mappings for the Receivers in Example 1

![Figure 12](https://ieeexplore.ieee.org/mediastore/IEEE/content/media/26/10721242/10511075/rajan12-3395332-large.gif)

**Figure 12.** Different 8-PSK mappings used for modulating the index-coded bits in Example 1.

### Remark 3:

If a receiver, say $R_{i}$, has to meet a certain error threshold value when $\Gamma _{si}^{i}\gg \Gamma _{si}^{th}$, then the mapping of $M$-PSK should be done in such a way that the number of signal points given by [(1)](https://ieeexplore.ieee.org/rest/document/10511075/?logAccess=true#deqn1) is minimum for a decoding strategy at that receiver, which happens when all the signal pairs that have the same value of $\bigoplus \hat {Y}^{i}_{I({\mathcal {D}}_{j}^{i})}$ are mapped adjacent to each other.

Fig. 10a compares the performance of $R_{3}$ under all the aforementioned mappings of 8-PSK. We can clearly see that $R_{3}$ performs better for $\mathcal {M}_{1}$ and $\mathcal {M}_{4}$ mapping as for these mappings the value of $|P(\mathcal {D}_{1}^{3})|=2$ is the least. The performance of $R_{4}$ under the different mappings shown in Fig. 12 are given in Fig. 10b. $R_{4}$ decodes $x_{4}$ using $\hat {y}_{3}^{4}$. Among all the mappings, $\mathcal {M}_{3}$ satisfies the criterion in Remark 3 as all the signal points with the least significant bit of the index coded tuple being 0 are kept adjacent to each other. $R_{4}$ performs the best when the mapping $\mathcal {M}_{3}$ with $|P(\mathcal {D}_{1}^{4})|=2$ is used. Although the analysis is done for the AWGN channel, it also continues to be true for the Rayleigh fading channel.

## Conclusion

For a given ICP with unprioritized receivers, we proved that when multi-level modulation schemes are used for transmitting the index-coded bits over a noisy channel, minimizing the number of index-coded bits used for decoding a requested message does not assure the best probability of error performance. Further, when we consider the side information at the receivers to be noisy, the probability of error performance depends on the signal-to-noise ratio ($\Gamma _{si}$) at which the side information is broadcast. We also derived a criterion for selecting an optimal decoding strategy in both the low and the high $\Gamma _{si}$ regimes. An algorithm for determining the optimal decoding strategy at a given receiver was also proposed. We also showed that the criterion for selecting an optimal decoding strategy derived in this paper for PSK-modulated index code transmission does not hold if the modulation scheme employed is QAM. Characterizing the criterion for selection of the best decoding strategy at a receiver for QAM-modulated transmission of index codes and two-step decoding will be an interesting problem for future research.

## References (16 total, showing 16)

1. Y. Birk and T. Kol, “Informed-source coding-on-demand (ISCOD) over broadcast channels,” in Proc. IEEE Conf. Comput. Commun. , San Francisco, CA, USA, Mar. 1998, pp. 1257–1264.

2. L. Ong and C. K. Ho, “Optimal index codes for a class of multicast networks with receiver side information,” in Proc. IEEE Int. Conf. Commun. (ICC) , Jun. 2012, pp. 2213–2218.

3. M. A. Maddah-Ali and U. Niesen, “Fundamental limits of caching,” IEEE Trans. Inf. Theory , vol. 60, no. 5, pp. 2856–2867, May 2014.

4. S. Li, M. A. Maddah-Ali, Q. Yu, and A. S. Avestimehr, “A fundamental tradeoff between computation and communication in distributed computing,” IEEE Trans. Inf. Theory , vol. 64, no. 1, pp. 109–128, Jan. 2018.

5. Z. Bar-Yossef, Y. Birk, T. S. Jayram, and T. Kol, “Index coding with side information,” IEEE Trans. Inf. Theory , vol. 57, no. 3, pp. 1479–1494, Mar. 2011.

6. L. Natarajan, Y. Hong, and E. Viterbo, “Index codes for the Gaussian broadcast channel using quadrature amplitude modulation,” IEEE Commun. Lett. , vol. 19, no. 8, pp. 1291–1294, Aug. 2015.

7. A. Thomas, K. Radhakumar, C. Attada, and B. S. Rajan, “Single uniprior index coding with min–max probability of error over fading channels,” IEEE Trans. Veh. Technol. , vol. 66, no. 7, pp. 6050–6059, Jul. 2017.

8. A. A. Mahesh and B. S. Rajan, “Index coded PSK modulation,” in Proc. 47th Annu. IEEE Wireless Commun. Netw. , Apr. 2016, pp. 1890–1896.

9. D. U. Sudhakaran and B. S. Rajan, “Index coded PSK modulation for prioritized receivers,” IEEE Trans. Veh. Technol. , vol. 66, no. 12, pp. 11151–11165, Dec. 2017.

10. A. A. Mahesh, A. Chhetri, and B. S. Rajan, “Role of index codes in noisy broadcasting with side information and index coded QAM for prioritized receivers,” IEEE Trans. Commun. , vol. 71, no. 7, pp. 3889–3904, Jul. 2023.

11. J.-W. Kim and J.-S. No, “Index coding with erroneous side information,” IEEE Trans. Inf. Theory , vol. 63, no. 12, pp. 7687–7697, Dec. 2017.

12. S. Ghosh and L. Natarajan, “On linear codes for broadcasting with noisy side information,” in Proc. 24th Nat. Conf. Commun. (NCC) , Hyderabad, India, Feb. 2018, pp. 1–6.

13. S. Ghosh and L. Natarajan, “Linear codes for broadcasting with noisy side information,” IEEE Trans. Inf. Theory , vol. 65, no. 7, pp. 4207–4226, Jul. 2019.

14. C. Arunachala, V. K. Gangwar, and B. S. Rajan, “Linear codes for broadcasting with noisy side-information and different error thresholds,” in Proc. IEEE Global Commun. Conf. (GLOBECOM) , Waikoloa, HI, USA, Dec. 2019, pp. 1–6.

15. A. E. Tom and B. S. Rajan, “Index coded PSK modulation with rotated constellation for prioritized receivers,” in Proc. IEEE 95th Veh. Technol. Conf. , Helsinki, Finland, Jun. 2022, pp. 1–6.

16. M. K. Simon and M. S. Alouini, Digital Communication Over Fading Channels . Hoboken, NJ, USA : Wiley, 2005.
