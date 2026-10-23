---
title: "Probability of Quota Violations in Divisor Apportionment Methods with Nonzero Allocations"
authors: "Tyler C. Wunder, Joseph W. Cutrone"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06556v1"
published: "2026-05-07"
source: "arxiv_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 23424
---

# Probability of Quota Violations in Divisor Apportionment Methods with Nonzero Allocations

## Abstract

Apportionment assigns indivisible items among groups. By the Balinski-Young theorem, no method can satisfy both house monotonicity and the quota rule. This paper investigates quota violations caused by nonzero allocation constraints, and derives exact probability formulas for their frequency. Such violations occur in systems like the U.S. House of Representatives, where each state is guaranteed at least one seat. We analyze the three-state case, introduce the $\tau$ statistic to parametrize population distributions, and prove an Asymptotic Quota Stabilization theorem: for fixed $\tau$, quota behavior stabilizes as populations grow, yielding probability results for quota violations determined by the set of ultimately violatory $\tau$ values.

Applying this framework to the five classical divisor methods, we derive exact probability formulas. Additionally, we show that as the number of seats $M\to\infty$, these probabilities converge to method-specific constants. These results provide a precise, quantitative foundation for evaluating the fairness and frequency of quota violations in constrained apportionment systems.

## 1 Introduction and Foundations

### 1.1 Background on Apportionment

Let $n$ be the number of states with populations $p_{i}\in\mathbb{R}_{>0}$ for $1\leq i\leq n$. To avoid ties, assume no two states have the same populations. Let $M\geq n$ be the number of seats to apportion.

A divisor method is an algorithmic procedure to distribute the $M$ seats by dividing populations by a strictly increasing divisor function, $\delta:\mathbb{R}_{\geq 0}\to\mathbb{R}_{\geq 0}$.

Given populations $(p_{1},\dots,p_{n})$ and a divisor function $\delta$, an apportionment $A(p_{1},\dots,p_{n})=(a_{1},\dots,a_{n})$, is calculated as follows:

1. Assign each state zero seats (or one seat if $\delta(0)=0$).
2. Calculate each state’s priority value $\frac{p_{i}}{\delta(r_{i})}$, where $r_{i}$ is the current number of seats assigned to state $i$.
3. Assign to the state with the highest priority value an additional seat.
4. Repeat steps (2) and (3) until $M$ seats have been apportioned.

The five “workable methods” most commonly used are defined by the following divisor functions:

| Method          | Divisor Function                  |
| --------------- | --------------------------------- |
| Adams           | $\delta(s)=s$                     |
| Jefferson       | $\delta(s)=s+1$                   |
| Webster         | $\delta(s)=s+0.5$                 |
| Huntington-Hill | $\delta(s)=\sqrt{s(s+1)}$         |
| Dean            | $\delta(s)=\dfrac{2s(s+1)}{2s+1}$ |

A state’s standard quota $q_{i}$ is the number of seats proportional to its population. This generally non-integer number is defined by $q_{i}=\frac{p_{i}}{SD}$, where $SD=\frac{P}{M}$ is the standard divisor, defined to be the total population $P=\sum_{i=1}^{n}p_{i}$ divided by the number of seats $M$. Ideally, each state should be apportioned its standard quota. However, as the standard quota is rarely an integer, a state should instead receive its *upper quota*, $\lceil q_{i}\rceil$, or its *lower quota*, $\lfloor q_{i}\rfloor$. With this in mind, define the following notion of unfair apportionment:

A *quota violation* occurs whenever a state is assigned more seats than its upper quota or fewer seats than its lower quota. That is, $a_{i}>\lceil q_{i}\rceil$ or $a_{i}<\lfloor q_{i}\rfloor$ for some state $i$. In particular, a *lower quota violation* occurs when $a_{i}<\lfloor q_{i}\rfloor$, and an *upper quota violation* occurs when $a_{i}>\lceil q_{i}\rceil$.

By the *Balinski-Young Impossibility Theorem* \[[2](https://arxiv.org/html/2605.06556v1#bib.bib2)\], all apportionment methods have either quota violations or other unfair occurrences called paradoxes. Specifically, the previously defined divisor methods are without paradoxes but all are known to violate quota.

### 1.2 Nonzero Allocation Constraints

In many applications, such as the apportionment of legislative representatives, it is undesirable for an apportionment method to assign zero representatives to any state. To ensure $a_{i}\geq 1$, methods like Jefferson and Webster are modified such that $\delta(0)=0$. This modification can introduce additional quota violations not present in the unconstrained method where a small state receives a seat it would not have earned based purely on its priority value.

#### Definition 1.1.

For ordered populations $p_{1},\dots,p_{n}$; $M$ seats; and a divisor method $A$ that guarantees nonzero allocations, define the *modified method* $\tilde{A}$ as follows:

1. With $M-1$ seats, calculate $A(p_{2},\dots,p_{n})$ to obtain $(a_{2},\dots,a_{n})$.
2. Set $a_{1}=1$.
3. Define $\tilde{A}(p_{1},\dots,p_{n})=(a_{1},\dots,a_{n})$

Note the order of the steps is important here. The modified method enforces a guaranteed seat for state one and applies the divisor method on the remaining $M-1$ seats.

#### Definition 1.2.

Let $A$ be a divisor method that guarantees nonzero allocations on $M$ seats and suppose the populations are ordered such that $p_{1}<\cdots<p_{n}$. The apportionment $A(p_{1},\dots,p_{n})$ exhibits a *quota violation caused by nonzero allocations* if the following conditions hold:

1. $A(p_{1},\dots,p_{n})$ violates the quota rule.
2. $\tilde{A}(p_{1},\dots,p_{n})=A(p_{1},\dots,p_{n})$.
3. When apportioning $M$ seats $A(p_{2},\dots,p_{n})$ does not violate the quota rule.

Additionally, define a *quota violation caused or worsened by nonzero allocations* as when conditions 1 and 2 hold.

The motivation behind these definitions is to check if the smallest state has a priority value so low that they would not receive seats by having the largest priority value, and instead only receive a seat because the method guarantees each state at least one seat.

## 2 Main Results

The paper introduces a statistic $\tau$ which is useful for studying quota violations caused by nonzero allocations in the three state case.

### Definition [4.1](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem1).

Let $(1,x,y)$, $1<x<y$, be the associated reduced population vector for a three state distribution ($p_{1},p_{2},p_{3}$). Define the $\tau$ statistic as follows:

$$
\begin{aligned}
\tau:=\frac{\mathrm{mean}(1,x,y)-\mathrm{median}(1,x,y)}{\max(1,x,y)}.
\end{aligned}
$$

### Lemma [4.3](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem3).

The statistic $\tau$ parametrizes a family of population distributions dependent on $x$. Specifically, this is the set of reduced population vectors associated with a fixed $\tau$: $\{(1,x,y(x,\tau))\mid x\in\mathbb{R},x>1\}$, where $y$ is a linear function of $x$.

### Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6).

(Asymptotic Apportionment) Let $(1,x,y(x,\tau))$ be a reduced population vector associated with a fixed $\tau$, and let $A$ be a divisor method that guarantees nonzero allocations on $M$ seats. Then, for all but finitely many $\tau\in(-\frac{1}{3},\frac{1}{3})$:

$$
\begin{aligned}
\displaystyle{\lim_{x\to\infty}A(1,x,y(x,\tau))=\tilde{A}\left(\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right)},
\end{aligned}
$$

where $\tilde{A}$ is defined as apportioning the remaining $M-1$ seats among states 2 and 3 according to the divisor method $A$ (see definition [1.1](https://arxiv.org/html/2605.06556v1#S1.Thmtheorem1)).

### Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7).

(Asymptotic Quota Stabilization for Nonexceptional $\tau$) Let $\mathcal{E}$ be the exceptional set of finite $\tau\in(-\frac{1}{3},\frac{1}{3})$ such that Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6) fails. Fix $\tau\notin\mathcal{E}$. Then there exists some $x_{\tau}$ such that for all $x\geq x_{\tau}$, $A(1,x,y(x,\tau))$ is always a lower quota violation caused by nonzero allocation or never a violation, with this behavior determined by $\tau$.

Specifically, let state $i\in\{2,3\}$ be the state that receives the last seat when apportioning $M$ seats among only states $2$ and $3$ from $A(\tilde{q}_{2},\tilde{q}_{3})$. Then:

1. If $A(\tilde{q}_{2},\tilde{q}_{3})$ assigns state $i$ its lower quota $\lfloor\tilde{q}_{i}\rfloor$, then for all $x\geq x_{\tau}$, the apportionment $A(1,x,y(x,\tau))$ is a lower quota violation caused by nonzero allocations, with state $i$ receiving $\lfloor\tilde{q}_{i}\rfloor-1$ seats.
2. If $A(\tilde{q}_{2},\tilde{q}_{3})$ assigns state $i$ its upper quota $\lceil\tilde{q}_{i}\rceil$, then for all $x\geq x_{\tau}$, the apportionment $A(1,x,y(x,\tau))$ is not a quota violation.

### Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12).

Let $A$ be a divisor method with divisor function $\delta$ that guarantees nonzero allocations on M seats and $n=3$ states. Then, under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$, with $1<x<y$, the probability of a quota violation is the same as the probability of a quota violation caused by states guaranteed nonzero allocations and is calculated by:

$$
\begin{aligned}
P(A(1,x,y)\text{ has a q.v.})=\sum_{k=\lceil M/2\rceil}^{M-1}M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right)
\end{aligned}
$$

where $k$ indexes the integer values of $\lfloor\tilde{q}_{3}\rfloor$, where

$$
\begin{aligned}
\tilde{q}_{3}=\frac{2M}{3-3\tau},\qquad\tau=\frac{\mathrm{mean}(1,x,y)-\mathrm{median}(1,x,y)}{\max(1,x,y)}=\dfrac{1-2x+y}{3y}.
\end{aligned}
$$

and

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

### Theorem [5.16](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem16).

Under the asymptotic uniform distribution for vectors $(1,x,y)$ with $1<x<y$, we have as $M\to\infty$ that the probability of a quota violation caused by nonzero allocations converges to $2\ln(2)-1\approx 0.386292$ in the Adams method, to $0$ in the modified Jefferson method, and to $\ln(2)-\frac{1}{2}\approx 0.193147$ in the Huntington-Hill, Webster, and Dean methods.

### Theorem [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22).

Let $M$ be the total number of seats, and let $A$ be the Modified Jefferson, Modified Webster, Dean, or Huntington-Hill method with divisor function $\delta$. Let $(1,x,y)$ be a reduced population vector with $1<x<y$, drawn from a probability distribution with joint density $f(x,y)$.

For each $\tau\in\left(-\frac{1}{3},\frac{1}{3}\right)$, the $\tau$-line parametrization in $x$ is

$$
\begin{aligned}
x=x(y,\tau):=\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2},
\end{aligned}
$$

Let the set of ultimately violatory $\tau$ values be

$$
\begin{aligned}
V=\bigcup_{k=\lfloor M/2\rfloor+1}^{M-1}\left(1-\frac{2M}{3k},\,1-\frac{2M}{3\bigl(k+D(k)\bigr)}\right),
\end{aligned}
$$

where

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

For each $\tau$, let $y_{\tau}^{F}$ denote the floor stabilization threshold and $y_{\tau}$ the agreement with asymptotic apportionment threshold defined in Lemmas [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17) and [5.19](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem19). Define

$$
\begin{aligned}
y_{\tau}^{\max}:=\begin{cases}\infty&\text{if }\tau\in V,\\
y_{\tau}&\text{if }\tau\notin V.\end{cases}
\end{aligned}
$$

Then the probability of a quota violation caused by a guaranteed seat is

$$
\begin{aligned}
\Pr(\text{quota violation})=\int_{-1/3}^{1/3}\int_{y_{\tau}^{F}}^{y_{\tau}^{\max}}f\bigl(x(y,\tau),\,y\bigr)\,\frac{3}{2}y\,dy\,d\tau.
\end{aligned}
$$

## 3 Assumptions and Background Information

We assume $M\geq n$ and no ties in priority values. The following are simple lemmas and known results:

### Lemma 3.1.

\[[2](https://arxiv.org/html/2605.06556v1#bib.bib2)\] Divisor methods satisfy neutrality and proportionality: they are invariant under permutation of the states and under positive scaling of all populations.

Therefore, we may analyze just the standard quotas $(q_{1},\dots,q_{n})$ or the *reduced population vectors* $\left(1,\frac{p_{2}}{p_{1}},\dots,\frac{p_{n}}{p_{1}}\right)$.

### Theorem 3.2.

\[[2](https://arxiv.org/html/2605.06556v1#bib.bib2)\] No single divisor-method apportionment can simultaneously contain both an upper and a lower quota violation.

### Theorem 3.3.

\[[2](https://arxiv.org/html/2605.06556v1#bib.bib2)\] When $n=2$, no quota violations occur in any divisor method.

This paper builds off of the authors’ prior work. A main result is listed here for convenience which will be used later in the paper.

### Theorem 3.4.

\[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\] (Lower Quota Violation Criteria Test) Let $A$ be Adams’s, Dean’s, or the Huntington-Hill method, with divisor function $\delta(s)$. Order the populations such that $p_{1}<p_{2}<p_{3}$ and calculate the standard quotas $q_{i}$. Then the apportionment $A(p_{1},p_{2},p_{3})$ on $M$ seats has a lower quota violation if and only if all three of the following statements are true:

1. $q_{3}\delta(\lfloor q_{1}\rfloor)<q_{1}\delta(\lfloor q_{3}\rfloor-1)$
2. $q_{3}\delta(\lfloor q_{2}\rfloor)<q_{2}\delta(\lfloor q_{3}\rfloor-1)$
3. $\lceil q_{1}\rceil+\lceil q_{2}\rceil+\lfloor q_{3}\rfloor=M+1$ (equivalently for $q_{1},q_{2}\notin\mathbb{Z}$, $\lfloor q_{1}\rfloor+\lfloor q_{2}\rfloor+\lfloor q_{3}\rfloor=M-1)$.

### Remark 3.5.

By repeating the arguments used in \[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\], the above test still holds for modified Webster’s and modified Jefferson’s methods.

An immediate extension of Theorem 5.5 in \[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\] is:

### Theorem 3.6.

Let $A$ be a divisor method with divisor function $\delta$ satisfying $\delta(0)=0$ and $\dfrac{x+1}{\delta(\lfloor x\rfloor)}$ is a decreasing function for $x\in[1,\infty)$. Then, if $A(q_{1},q_{2},q_{3})$ produces a quota violation with $q_{1}<q_{2}<q_{3}$, $A(q_{1},q_{2},q_{3})=(\lceil q_{1}\rceil,\lceil q_{2}\rceil,\lfloor q_{3}\rfloor-1)$. In particular, this holds for Huntington-Hill’s, Adams’, Dean’s, modified Jefferson’s, and modified Webster’s methods.

## 4 Asymptotic Quota Stabilization via the $\tau$-Statistic

This section introduces a new statistic, $\tau$, which is useful for studying quota violations and quota violations caused by nonzero allocations. For simplicity, the section begins by discussing three states, and later explains how these results extend to $n$ states.

### 4.1 Defining Relative Skewness for $n=3$ States

#### Definition 4.1.

Let $(1,x,y)$, $1<x<y$, be the associated reduced population vector for a three state distribution ($p_{1},p_{2},p_{3}$). Define the $\tau$ statistic as follows:

$$
\begin{aligned}
\tau:=\frac{\mathrm{mean}(1,x,y)-\mathrm{median}(1,x,y)}{\max(1,x,y)}.
\end{aligned}
$$

#### Lemma 4.2.

The statistic $\tau$ is preserved under scaling: $\tau(1,x,y)=\tau(\lambda,\lambda x,\lambda y)$ for $\lambda\in\mathbb{R}_{>0}$. As such, $\tau$ can be calculated for any three state distribution, not just reduced population vectors.

#### Proof.

$$
\begin{aligned}
\tau(\lambda,\lambda x,\lambda y)=\frac{\frac{\lambda+\lambda x+\lambda y}{3}-\lambda x}{\lambda y}=\frac{\frac{1+x+y}{3}-x}{y}=\tau(1,x,y).
\end{aligned}
$$

∎

#### Lemma 4.3.

The statistic $\tau$ parametrizes a family of population distributions dependent on $x$. Specifically, this is the set of reduced population vectors associated with a fixed $\tau$: $\{(1,x,y(x,\tau))\mid x\in\mathbb{R},x>1\}$, where $y$ is a linear function of $x$.

#### Proof.

Fix $\tau$. Then, for some $(1,x,y)$ with $1<x<y$, by definition

$$
\begin{aligned}
\tau=\frac{\frac{1+x+y}{3}-x}{y}
\end{aligned}
$$

Solving for $y$ gives

$$
\begin{aligned}
y(x,\tau)=\frac{2x-1}{1-3\tau}=\frac{2}{1-3\tau}x-\frac{1}{1-3\tau}.
\end{aligned}
$$

Thus, for a fixed $\tau$, $y$ is a linear function of $x$ and the set of reduced population vectors forms a one-dimensional family in $\{(x,y)\,|\,1<x<y\}$. ∎

The last lemma allows us to not think of reduced population vectors $(1,x,y)$ as independent triplets but instead as parametrized rays, with a linear relationship between $x$ and $y$, in the space of allowable reduced population vectors on the $xy$-plane.

![Figure 1](https://arxiv.org/html/2605.06556v1/fig_1_tau_picture.png)

**Figure 1.** Geometric interpretation of $\tau$

### 4.2 Properties and Bounds

#### Lemma 4.4.

For any three state distribution with reduced population $(1,x,y)$, with $1<x<y$, the statistic $\tau$ satisfies the strict inequality $|\tau|<\frac{1}{3}$.

#### Proof.

Since $x>1,1-2x<-1$, and in particular, $1-2x$ is strictly negative. Then from the definition of $\tau,$

$$
\begin{aligned}
\tau=\dfrac{\dfrac{1+x+y}{3}-x}{y}=\dfrac{1+x+y-3x}{3y}=\dfrac{1-2x+y}{3y}=\dfrac{1}{3}+\dfrac{1-2x}{3y}<\dfrac{1}{3}.
\end{aligned}
$$

To show the lower bound for $\tau$, start with the simplified expression $\tau=\dfrac{1-2x+y}{3y}$ and notice that $\tau$ decreases as $x$ increases. Since $x<y$, as $x\rightarrow y^{-},\tau\rightarrow\dfrac{1-2y+y}{3y}=\dfrac{1-y}{3y}=\dfrac{1}{3y}-\dfrac{1}{3}.$ As $y\rightarrow\infty$, $\tau\rightarrow-\dfrac{1}{3}$. Thus $\tau>-\frac{1}{3}$ for any $1<x<y$.

∎

#### Remark 4.5.

The value of $\tau$ effectively measures the relative position of the median $x$ between the minimum and the maximum values. When $\tau$ is close to its upper bound of $\frac{1}{3}$, $x$ is as small as possible (close to 1.) This represents a right-skewed population distribution. Similarly, when $\tau$ is close to its lower bound of $-\frac{1}{3}$, $x$ is as large as possible (close to $y$), and represents a left-skewed population vector. When $\tau=0$, the mean and median are equal, and from the formula for $y$ in terms of $x$ and $\tau$, $y=2x-1$. Equivalently, $x=\frac{1+y}{2}$, the average of 1 and $y$.

The initial space of population vectors is three-dimensional: $(p_{1},p_{2},p_{3}).$ Scaling reduces this space to two dimensions: $(1,x,y)$. Introducing $\tau$, a measure of skewness, replaces $y$, a measure of the relative size of the largest state to the smallest state.

### 4.3 Asymptotic Stability and the Apportionment Limit

Since the reduced population vector $(1,x,y(x,\tau))$ depends continuously on $x$ (and on $\tau$), the next theorem will show the limiting behavior as $x\to\infty$ is determined entirely by taking the limit of the vector of standard quotas, except possibly at the finitely many $\tau$-values where priority values become equal.

#### Theorem 4.6.

(Asymptotic Apportionment) Let $(1,x,y(x,\tau))$ be a reduced population vector associated with a fixed $\tau$, and let $A$ be a divisor method that guarantees nonzero allocations on $M$ seats. Then, for all but finitely many $\tau\in(-\frac{1}{3},\frac{1}{3})$:

$$
\begin{aligned}
\displaystyle{\lim_{x\to\infty}A(1,x,y(x,\tau))=\tilde{A}\left(\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right)},
\end{aligned}
$$

where $\tilde{A}$ is defined as apportioning the remaining $M-1$ seats among states 2 and 3 according to the divisor method $A$ (see definition [1.1](https://arxiv.org/html/2605.06556v1#S1.Thmtheorem1)).

#### Proof.

For a fixed $\tau$ and reduced population vector $(1,x,y(x,\tau))=\left(1,x,\frac{2x-1}{1-3\tau}\right)$, the total population is $P=1+x+\frac{2x-1}{1-3\tau}=\frac{(3-3\tau)x-3\tau}{1-3\tau}.$ Calculate the standard quotas $q_{i}=\frac{Mp_{i}}{P}$:

$$
\begin{aligned}
(q_{1},q_{2},q_{3})=\left(\frac{M(1-3\tau)}{(3-3\tau)x-3\tau},\frac{M(1-3\tau)x}{(3-3\tau)x-3\tau},\frac{M(2x-1)}{(3-3\tau)x-3\tau}\right)
\end{aligned}
$$

Then, as $x\to\infty$

$$
\begin{aligned}
(q_{1},q_{2},q_{3})\to\left(0,\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right).
\end{aligned}
$$

Divisor methods are piecewise constant functions on open regions of the population space. The boundaries of these regions are hypersurfaces defined by equalities of the priority values, $\frac{p_{i}}{\delta(k)}=\frac{p_{j}}{\delta(l)}$, with $0\leq k,l\leq M-1$. The boundaries cause a discontinuity in $A$ and a change in apportionment. The reduced population vector $(1,x,y)$ depends continuously on $\tau$ (and on $x$). There are finitely many such equations, each rational functions in $\tau$. After clearing denominators, each condition yields a linear equation in $\tau$ and has at most one solution. Therefore, the exceptional set of $\tau$ is finite. Define this set as $\mathcal{E}$.

For $\tau\not\in\mathcal{E}$, $A$ is constant on a neighborhood near $\left(0,\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right)$, and therefore

$$
\begin{aligned}
\begin{array}[]{cl}\displaystyle\lim_{x\to\infty}A(1,x,y(x,\tau))&=\displaystyle\lim_{x\to\infty}A(q_{1},q_{2},q_{3})\\[9.0pt]
&=A(\displaystyle\lim_{x\to\infty}(q_{1},q_{2},q_{3}))\\[9.0pt]
&=A\left(0,\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right).\end{array}
\end{aligned}
$$

As $A$ guarantees strictly positive apportionments, state one receives at least one seat. Because $q_{1}(x)\to 0$, state 1’s priorities become negligible so state one only receives one seat and the remaining $M-1$ seats are apportioned exactly as if $A$ were applied only to states $2$ and $3$. This is precisely the definition of $\tilde{A}\left(\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right),$ completing the proof. ∎

In what follows, we introduce new notation for the limiting standard quotas:

$$
\begin{aligned}
\tilde{q}_{2}:=\frac{M(1-3\tau)}{3-3\tau},\qquad\tilde{q}_{3}:=\frac{2M}{3-3\tau}.
\end{aligned}
$$

For $\tau\not\in\mathcal{E}$, both $\tilde{q}_{2}$ and $\tilde{q}_{3}$ are nonintegral limit points of the standard quotas $q_{2}(x)$ and $q_{3}(x)$. As such, their integer parts must stabilize. Consequently, the asymptotic quota behavior of the full three-state apportionment is determined entirely by which of states 2 or 3 receives the final seat from $\tilde{A}.$ The following theorem formalizes this stabilization and shows that, beyond a finite threshold, quota compliance or violation is completely determined by $\tau$.

#### Theorem 4.7.

(Asymptotic Quota Stabilization for Nonexceptional $\tau$) Let $\mathcal{E}$ be the exceptional set of finite $\tau\in(-\frac{1}{3},\frac{1}{3})$ such that Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6) fails. Fix $\tau\notin\mathcal{E}$. Then there exists some $x_{\tau}$ such that for all $x\geq x_{\tau}$, $A(1,x,y(x,\tau))$ is always a lower quota violation caused by nonzero allocation or always not a violation, with this behavior determined by $\tau$.

Specifically, let state $i\in\{2,3\}$ be the state that receives the last seat when apportioning $M$ seats among only states $2$ and $3$ from $A(\tilde{q}_{2},\tilde{q}_{3})$. Then:

1. If $A(\tilde{q}_{2},\tilde{q}_{3})$ assigns state $i$ its lower quota $\lfloor\tilde{q}_{i}\rfloor$, then for all $x\geq x_{\tau}$, the apportionment $A(1,x,y(x,\tau))$ is a lower quota violation caused by nonzero allocations, with state $i$ receiving $\lfloor\tilde{q}_{i}\rfloor-1$ seats.
2. If $A(\tilde{q}_{2},\tilde{q}_{3})$ assigns state $i$ its upper quota $\lceil\tilde{q}_{i}\rceil$, then for all $x\geq x_{\tau}$, the apportionment $A(1,x,y(x,\tau))$ is not a quota violation.

#### Proof.

Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6) implies

$$
\begin{aligned}
\lim_{x\to\infty}A(1,x,y(x,\tau))=\tilde{A}\left(\frac{M(1-3\tau)}{3-3\tau},\frac{2M}{3-3\tau}\right):=\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})
\end{aligned}
$$

By the definition of a limit, there must exist some point in which $A(1,x,y(x,\tau))$ is epsilon close to $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})$. Since $A$ and $\tilde{A}$ only output integer vectors in $\mathbb{Z}^{3}$, convergence implies there exists some $x_{\tau}^{A}$ such that

$$
\begin{aligned}
A(1,x,y(x,\tau))=\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})\qquad\text{for all }x\geq x^{A}_{\tau}.
\end{aligned}
$$

Since $\tau\notin\mathcal{E}$, the limiting quotas

$$
\begin{aligned}
\tilde{q}_{2}=\frac{M(1-3\tau)}{3-3\tau},\qquad\tilde{q}_{3}=\frac{2M}{3-3\tau}
\end{aligned}
$$

are not integers so each lies at positive distance from the nearest integer. Because the corresponding standard quotas $(q_{2}(x),q_{3}(x))$ converge to $(\tilde{q}_{2},\tilde{q}_{3})$ as $x\to\infty$, there exists $\delta>0$ and $x_{\tau}^{F}$ such that for all $x\geq x_{\tau}^{F}$ the varying quotas remain within $\delta$ of their limits and therefore lie in the same unit intervals as $\tilde{q}_{2}$ and $\tilde{q}_{3}$. It follows that for all $x\geq x_{\tau}^{F}$,

$$
\begin{aligned}
\lfloor q_{2}(x)\rfloor=\lfloor\tilde{q}_{2}\rfloor\qquad\text{and}\qquad\lfloor q_{3}(x)\rfloor=\lfloor\tilde{q}_{3}\rfloor,
\end{aligned}
$$

so the integer parts of the quotas stabilize.

Define $x_{\tau}=\max\{x_{\tau}^{A},x_{\tau}^{F}\}$. Then for all $x\geq x_{\tau}$,

$$
\begin{aligned}
A(1,x,y(x,\tau))=\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})\text{ and }\lfloor q_{i}(x)\rfloor=\lfloor\tilde{q}_{i}\rfloor,i=2,3.
\end{aligned}
$$

Therefore whether $A(1,x,y(x,\tau))$ violates lower quota is equivalent to whether the limiting apportionment does.

Finally, $A(\tilde{q}_{2},\tilde{q}_{3})=(a_{2},a_{3})$ apportions $M-1$ seats, and $\tilde{A}$ assigns the remaining seat to state 1. Let state $i$ receive the final seat in the apportionment of $M$ seats in $A(\tilde{q}_{2},\tilde{q}_{3})$. Then, since for two states there are no quota violations by Theorem [3.3](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem3) there are only two possible cases:

1. If $a_{i}=\lfloor\tilde{q}_{i}\rfloor$, the final apportionment for state $i$ is $\lfloor\tilde{q}_{i}\rfloor-1$, which is a lower quota violation caused by nonzero allocations.
2. If $a_{i}=\lceil\tilde{q_{i}}\rceil$, the final apportionment for state $i$ is $\lfloor\tilde{q}_{i}\rfloor$, which is not a quota violation.

Because the limiting quotas $(\tilde{q}_{2},\tilde{q}_{3})$ are functions of $\tau$, and the two-state allocation $A(\tilde{q}_{2},\tilde{q}_{3})$ depends only on these values, the presence or absence of a lower quota violation is uniquely determined by $\tau$ as claimed. ∎

This theorem then motivates the following definitions:

#### Definition 4.8.

A value $\tau\notin\mathcal{E}$ is said to be ultimately-violatory if for $x\geq x_{\tau}$, $A(1,x,y(\tau,x))$ produces a quota violation. Otherwise $\tau$ is said to be ultimately non-violatory or ultimately quota compliant.

Additionally, note the structure of $x_{\tau}$:

#### Remark 4.9.

The $\tau$-interval $(-\frac{1}{3},\frac{1}{3})$ can be decomposed into finitely many intervals such that on each interval, $x_{\tau}$ is locally represented in the form $x_{\tau}=\frac{a}{b+c\tau}+\frac{d\tau}{b+c\tau}+e$ for $a,b,c,d,e\in\mathbb{R}$ and denominators not identically $0$. This is proven later in Theorem [5.20](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem20).

### 4.4 Extension to $n$ States

For three states, the statistic $\tau$ parametrizes one-dimensional families of reduced population vectors $(1,x,y)$ along which the relative proportions of the populations vary linearly. These families appear as straight rays in the $(x,y)$-plane and are useful because apportionment behavior stabilizes along such rays as $x\to\infty$.

This idea may be generalized to $n$ states, resulting in a similar theory which is presented briefly here. Note that proofs in this section are omitted due to similarity with the three state case.

#### Definition 4.10.

Given a reduced population vector $(1,x,y_{1}\dots,y_{n-2})$, define $\mathbf{τ}$ vector as:

$$
\begin{aligned}
{{\mathbf{τ}} = {(\tau_{1},\mathrm{…},\tau_{n - 2})} = \left(\frac{\frac{1 + x + y_{1}}{3} - x}{y_{1}},\mathrm{…},\frac{\frac{1 + x + y_{n - 2}}{3} - x}{y_{n - 2}} \right)}.
\end{aligned}
$$

#### Lemma 4.11.

The vector ${\mathbf{τ}} = {(\tau_{1},\mathrm{…},\tau_{n - 2})}$ satisfies $-\frac{1}{3}<\tau_{1}<\dots<\tau_{n-2}<\frac{1}{3}$ under the ordering $(1<x<y_{1}<\ldots<y_{n-2})$.

#### Lemma 4.12.

Given ${\mathbf{τ}} = {(\tau_{1},\mathrm{…},\tau_{n - 2})}$, $\mathbf{τ}$ parameterize a family of population vectors

$$
\begin{aligned}
(1,x,y_{1}(x,\tau_{1}),\dots,y_{n-2}(x,\tau_{n-2})),\qquad\text{where }\qquad y_{i}(x,\tau_{i})=\frac{2x-1}{1-3\tau_{i}}.
\end{aligned}
$$

#### Theorem 4.13.

(Asymptotic Apportionment) Let $(1,x,y_{1}(x,\tau_{1}),\ldots,y_{n-2}(x,\tau_{n-2}))$ be a reduced population vector with ${\mathbf{τ}} = {(\tau_{1},\mathrm{…},\tau_{n - 2})}$. Let $A$ be a divisor method that guarantees nonzero allocations on $M$ seats. Then for almost every $\mathbf{τ}$ satisfying $-\tfrac{1}{3}<\tau_{1}<\cdots<\tau_{n-2}<\tfrac{1}{3},$

$$
\begin{aligned}
\lim_{x\to\infty}A(1,x,y_{1}(x,\tau_{1}),\dots,y_{n-2}(x,\tau_{n-2}))=\tilde{A}_{1}(\tilde{q}_{2},\dots,\tilde{q}_{n}).
\end{aligned}
$$

The limiting quotas are

$$
\begin{aligned}
\tilde{q}_{2}=\lim_{x\to\infty}\frac{Mx}{P(x)},\qquad\tilde{q}_{i+2}=\lim_{x\to\infty}\frac{My_{i}(x,\tau_{i})}{P(x)},
\end{aligned}
$$

where $P(x)=1+x+y_{1}(x,\tau_{1})+\cdots+y_{n-2}(x,\tau_{n-2}).$

#### Theorem 4.14.

(Asymptotic Quota Stabilization) Let $\mathbf{τ}$ be a nonexceptional parameter vector for which Theorem [4.13](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem13) holds. Then there exists $x_{\mathbf{τ}}$ such that for all $x \geq x_{\mathbf{τ}}$

$$
\begin{aligned}
A(1,x,y_{1}(x,\tau_{1}),\dots,y_{n-2}(x,\tau_{n-2}))=\tilde{A}_{1}(\tilde{q}_{2},\dots,\tilde{q}_{n}).
\end{aligned}
$$

Consequently the quota behavior stabilizes: for sufficiently large $x$, the apportionment is always either quota compliant, a quota violation caused by nonzero allocation, a quota violation worsened by nonzero allocation, or an upper quota violation. Moreover, this behavior depends only on $\mathbf{τ}$. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})=(\tilde{a}_{2},\dots,\tilde{a}_{n})$ is the apportionment of $M$ seats among states $2,\dots,n$ and state $i$ receive the last seat then:

1. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})$ is not a quota violation and $\tilde{a}_{i}=\lfloor\tilde{q}_{i}\rfloor$, then the asymptotic apportionment is a quota violation caused by nonzero allocation.
2. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})$ is not a quota violation and $\tilde{a}_{i}=\lceil\tilde{q}_{i}\rceil$, then the asymptotic apportionment is not a quota violation.
3. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})$ is an upper quota violation where state $i$ is the only state assigned more than its upper quota and $\tilde{a}_{i}=\lceil\tilde{q}_{i}\rceil+1$, then the asymptotic apportionment is not a quota violation.
4. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})$ is an upper quota violation and case (3) does not apply, then the asymptotic apportionment is an upper quota violation.
5. If $A(\tilde{q}_{2},\dots,\tilde{q}_{n})$ is a lower quota violation, then the asymptotic apportionment is a quota violation worsened by nonzero allocation.

## 5 Probability of Quota Violations Caused by Nonzero Allocation in Three States

In this section, $\tau$ is used to derive a formula for probability of a quota violation caused by nonzero allocations for $n=3$ states. We begin by studying the case in which reduced population vectors are drawn uniformly from $\{(1,x,y)\mid 1<x<y\}$, before expanding the analysis to more general distributions.

Throughout, $A$ denotes either the Huntington-Hill, Adams, Dean, modified Webster or modified Jefferson’s method. The argument presented here can be extended to additional divisor methods with minor modifications.

### 5.1 The Asymptotic Uniform Distribution

The following result characterizes $\tau$ when a reduced population vector $(1,x,y)$ is drawn from the region $\{(1,x,y)\mid 1<x<y\}$ under an asymptotic uniform distribution. Heuristically the drawing is from $\{(1,x,y)\mid 1<x<y<h\}$ where $h$ is large. Formally, the definition of the probability for a set $E$ is

$$
\begin{aligned}
P(E)=\lim_{h\to\infty}P_{h}(E)
\end{aligned}
$$

where $P_{h}(E)$ is the probability of $E$ under a uniform distribution on $\{(1,x,y)\mid 1<x<y<h\}$.

#### Lemma 5.1.

Under the asymptotic uniform distribution defined above on reduced population vectors $\{(1,x,y)\mid 1<x<y\}$, the parameter $\tau$ is a uniform random variable on $\left(-\frac{1}{3},\frac{1}{3}\right)$.

#### Proof.

It suffices to show that for every $k\in\mathbb{R}$, the tail probability $P(\tau>k)$ coincides with that of a Uniform$\left(-\frac{1}{3},\frac{1}{3}\right)$ random variable. The only unknown probability is when $\tau\in(-\frac{1}{3},\frac{1}{3})$ by Lemma [4.4](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem4):

$$
\begin{aligned}
P(\tau>k)=\left\{\begin{array}[]{lcr}1&k\leq-\frac{1}{3}\\
?&k\in\left(-\frac{1}{3},\frac{1}{3}\right)\\
0&k\geq\frac{1}{3}\end{array}\right.
\end{aligned}
$$

To find the unknown expression, let $k\in\left(-\frac{1}{3},\frac{1}{3}\right)$. Then

$$
\begin{aligned}
P\left(\tau>k\right)=P\left(\frac{\frac{1+x+y}{3}-x}{y}>k\right)=P\left(x<\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}\right).
\end{aligned}
$$

This can then be interpreted geometrically as the fraction of the region $1<x<y$ covered by $x<\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}$. For small $y$, the region $x<\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}$ may lie below $x=1$, so the lower bound in $y$ is found by solving $\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}=1$, which gives $y=\frac{1}{1-3k}.$ For $k\in\left(-\frac{1}{3},\frac{1}{3}\right)$, the line $x=\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}$ has slope strictly less than $1$, so for sufficiently large $y$ it lies below the line $x=y$. For sufficiently large $y$, the line determines the upper boundary in $x$ and the contribution from the region where $x=y$ bounds the domain is asymptotically negligible. Accordingly, the $y$–integration extends to $h$.

Thus, the desired probability equals

$$
\begin{aligned}
\displaystyle P(\tau>k)=P\left(x<\left(\frac{1}{2}-\frac{3}{2}k\right)y+\frac{1}{2}\right)=\lim_{h\to\infty}\frac{\int_{\frac{1}{1-3k}}^{h}\left(\frac{1}{2}-\frac{3}{2}k\right)y-\frac{1}{2}\,dy}{\int_{1}^{h}(y-1)\,dy}=\frac{1}{2}-\frac{3}{2}k
\end{aligned}
$$

The last equality follows since both the numerator and the denominator are quadratic polynomials in $h$, so the limit is determined by the leading coefficients. For $k\in\left(-\frac{1}{3},\frac{1}{3}\right)$, this coincides with the tail probability of a Uniform$\left(-\frac{1}{3},\frac{1}{3}\right)$ random variable. ∎

The uniform distribution of $\tau$ obtained above is not merely an result of the specific area normalization on the wedge $\{1<x<y\}$. In fact, the above calculation reveals that the distributional behavior of $\tau$ depends primarily on the asymptotic distribution of the ratio $x/y$. The following proposition makes this precise.

#### Proposition 5.2 (Robustness of the Uniform Distribution of $\tau$).

Suppose reduced population vectors are sampled for which $u=\frac{x}{y}$ is asymptotically uniformly distributed on $(0,1)$ and $y\to\infty$ in density. Then the induced distribution $\tau=\frac{1-2x+y}{3y}$ converges to the uniform distribution on $\left(-\frac{1}{3},\frac{1}{3}\right)$.

#### Proof.

Writing $x=uy$, we have $\tau=\frac{1-2uy+y}{3y}=\frac{1}{3y}+\frac{1-2u}{3}.$ As $y\to\infty$, the term $\frac{1}{3y}$ vanishes in probability. Thus the limiting distribution of $\tau$ coincides with that of $\frac{1-2u}{3}.$ Since $u$ is asymptotically uniform on $(0,1)$, it follows that $\frac{1-2u}{3}\sim\mathrm{Unif}\!\left(-\frac{1}{3},\frac{1}{3}\right)$. ∎

Having established that $\tau$ is uniformly distributed on $\left(-\tfrac{1}{3},\tfrac{1}{3}\right)$, we now relate the behavior of quota violations to the distribution of $\tau$. The following lemma shows that the problem reduces to identifying which values of $\tau$ are ultimately violatory.

#### Theorem 5.3 (Quota Violations Under the Asymptotic Uniform Distribution).

Under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$ with $1<x<y$ the following are equivalent:

- $P(A(1,x,y)\text{ is a quota violation}).$
- $P(A(1,x,y)\text{ is a quota violation caused by nonzero allocations)}.$
- $P(\tau(x,y)\text{ is ultimately violatory}).$

#### Proof.

It follows from Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7) and the definition of ultimately violatory that the following are equivalent:

- $$P(A(1,x,y)\text{ is a quota violation for $x>x_{\tau}$})$$
- $$P(A(1,x,y)\text{ is a quota violation caused by nonzero allocations for $x>x_{\tau}$)}$$
- $$P(\tau(x,y)\text{ is ultimately violatory for $x>x_{\tau}$}).$$

As such, it suffices to show $P(x<x_{\tau})=0$, as then the desired statement may be deduced by adding $0$. To start, let $P_{h}(E)$ be the probability of $E$ under the uniform distribution on $\{(1,x,y)\mid 1<x<y<h\}$ and let $r\in(1,h)$. Then:

$$
\begin{aligned}
0\leq P_{h}(x<x_{\tau})\leq P_{h}(\tau\mid x_{\tau}>r)+P_{h}(x<r).
\end{aligned}
$$

It follows from Remark [4.9](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem9) that for each $\varepsilon>0$, there exists $r_{\varepsilon}$ such that the total length of the set of $\tau$ such that $x_{\tau}>r_{\varepsilon}$ is less than $\left(\frac{2}{3}\right)\cdot\left(\frac{\varepsilon}{2}\right)$. Then, by Lemma [5.1](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem1), $P_{h}(x_{\tau}>r_{\varepsilon})$ converges to $\frac{3}{2}$ times the total length of such $\tau$ and therefore for all $h$ sufficiently large:

$$
\begin{aligned}
P_{h}(\tau\mid x_{\tau}>r_{\varepsilon})<\frac{\varepsilon}{2}.
\end{aligned}
$$

Additionally compute using the area of triangles and squares:

$$
\begin{aligned}
P_{h}(x<r_{\varepsilon})=\frac{2(h-1)(r_{\varepsilon}-1)-(r_{\varepsilon}-1)^{2}}{(h-1)^{2}}
\end{aligned}
$$

which goes to $0$ as $h\to\infty$. Thus, for all $h$ sufficiently large:

$$
\begin{aligned}
P_{h}(x<r_{\varepsilon})<\frac{\varepsilon}{2}.
\end{aligned}
$$

Then for all $h$ sufficiently large:

$$
\begin{aligned}
0\leq P_{h}(x<x_{\tau})\leq P_{h}(\tau\mid x_{\tau}>r_{\varepsilon})+P_{h}(x<r_{\varepsilon})<\varepsilon.
\end{aligned}
$$

So

$$
\begin{aligned}
P(x<x_{\tau})=\lim_{h\to\infty}P_{h}(x<x_{\tau})=0,
\end{aligned}
$$

as needed.

∎

### 5.2 An Asymptotic Probability Function for Three States

Fix $M$ seats and $n=3$ states. By Theorem [5.3](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem3), to derive a probability function for quota violations under uniformly distributed population vectors, it suffices to determine precisely which values of $\tau$ cause families to be violatory for all $x\geq x_{\tau}$. Once the subset of admissible $\tau$ is determined, the desired probability is then the length of this subset divided by the length of all possible $\tau$, which is $\frac{2}{3}$ by Lemma [4.4](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem4).

As shown in Section 4, the three-state problem reduces to a two-state problem. In particular, there is a bijection between $\tau$ and the standard quota $\tilde{q}_{3}.$ For each $\tau$, the reduced population vector $(1,x,y(x,\tau))$ has the same eventual apportionment behavior (for $x\geq x_{\tau}$) to that of $(\tilde{q}_{2},\tilde{q}_{3})$ by Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7).

The relationship between $\tau$ and $\tilde{q}_{3}$ are given by Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6):

$$
\begin{aligned}
\tilde{q}_{3}=\frac{2M}{3-3\tau},\qquad\tilde{q}_{2}+\tilde{q}_{3}=M
\end{aligned}
$$

Consequently,

$$
\begin{aligned}
\tau=1-\frac{2M}{3\tilde{q}_{3}}.
\end{aligned}
$$

Thus specifying $\tilde{q}_{3}$ determines $\tau$ and $\tilde{q}_{2}$, and vice versa. By construction, $\tilde{q}_{3}>\tilde{q}_{2}$.

By Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7), a value of $\tau$ produces a lower quota violation for the reduced population vector if and only if the corresponding two state apportionment $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})=\tilde{A}(M-\tilde{q}_{3},\tilde{q}_{3})$ produces a lower quota violation. We now determine precisely for which values of $\tilde{q}_{3}$ a lower violation occurs.

Write $\tilde{q}_{3}=\lfloor\tilde{q}_{3}\rfloor+d$ for $d\in[0,1)$. The occurrence of a lower quota violation is determined by the apportionment of the final seat as $d\to 1^{-}$. Specifically, by comparing the priority values that determine if the last seat is assigned to the state at $\lfloor\tilde{q}_{2}\rfloor$ or $\lceil\tilde{q}_{2}\rceil$, then we can determine exactly when a lower quota violation occurs in $A$. When $A$ assigns the final seat to the first state, if the seat is removed from either the floor of $\tilde{q}_{2}$ or $\tilde{q}_{3}$ then a lower quota violation will occur. If the last seat is removed for the first state from either the ceiling of $\tilde{q}_{2}$ or $\tilde{q}_{2}$, then no lower quota violation will occur.

#### Lemma 5.4.

Using the notation from above, when $\tilde{q}_{3}=\lfloor\tilde{q}_{3}\rfloor$ (or equivalently when $d=0$), there is lower quota violation in $\tilde{A}(M-\tilde{q}_{3},\tilde{q}_{3})$.

#### Proof.

Suppose $d=0$. Then $\tilde{q}_{3}=\lfloor\tilde{q}_{3}\rfloor$ is an integer. Since $\tilde{q}_{2}=M-\tilde{q}_{3}$, it follows that $\tilde{q}_{2}$ is also an integer. When both quotas are integers, the two state apportionment agrees exactly with the quota vector: $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})=(\tilde{q}_{2},\tilde{q}_{3}).$

Therefore, in the corresponding three–state apportionment, state 1 must receive one seat, and one seat must be removed from either state 2 or state 3. Because $\tilde{q}_{2}$ and $\tilde{q}_{3}$ are integers, removing one seat from either state forces that state to receive strictly fewer seats than its lower quota. Therefore a lower quota violation occurs in $\tilde{A}(M-\tilde{q}_{3},\tilde{q}_{3})$. ∎

#### Lemma 5.5.

Let $\tilde{q}_{3}=\lfloor\tilde{q}_{3}\rfloor+d$, for $d\in[0,1)$. There exist numbers

$$
\begin{aligned}
0\leq d^{*}\leq d^{**}\leq 1
\end{aligned}
$$

such that $[0,1)$ decomposes into three intervals

$$
\begin{aligned}
I_{1}=[0,d^{*}),\qquad I_{2}=[d^{*},d^{**}),\qquad I_{3}=[d^{**},1),
\end{aligned}
$$

with the following properties:

1. For $d\in I_{1}$, a lower quota violation occurs in $\tilde{A}(M-\tilde{q}_{3},\tilde{q}_{3})$.
2. For $d\in I_{2}\cup I_{3}$, no lower quota violation occurs in $\tilde{A}(M-\tilde{q}_{3},\tilde{q}_{3})$.

#### Proof.

By Lemma [5.4](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem4), when $d=0$, a lower quota violation occurs. As $d$ increases, a lower quota violation continues to occur while the third state’s priority values increase and the second state’s priority values decrease. For these values of $d$ close to zero, $a_{2}=\lceil\tilde{q}_{2}\rceil$ and $a_{3}=\lfloor\tilde{q}_{2}\rfloor$, with $a_{3}$ assigned last by $A$. Eventually, for some $d$, the priority value that puts state three at its lower quota becomes less than the priority value that puts state two at its upper quota. Define $d^{*}$ to be the first value of $d$ where this happens and define the interval $I_{1}=[0,d^{*})$. For $d\in I_{1}$, $a_{2}=\lceil\tilde{q}_{2}\rceil$ and $a_{3}=\lfloor\tilde{q}_{3}\rfloor$, with $a_{3}$ assigned last by $A$. Then $\tilde{A}$ results in the final apportionment with $a_{3}=\lfloor\tilde{q}_{3}\rfloor-1$, a lower quota violation.

For $d\geq d^{*}$, $A$ assigns $a_{2}=\lceil\tilde{q}_{2}\rceil$ and $a_{3}=\lfloor\tilde{q}_{3}\rfloor$, with $a_{2}$ assigned last, until there is some $d$ that causes state three to be apportioned its upper quota and state two to be apportioned its lower quota, with the last seat assigned to state three by $A$. Call the first value of $d$ where this happens $d^{**}$ and the interval $I_{2}=[d^{*},d^{**})$. For $d\in I_{2}$, $a_{2}=\lceil\tilde{q}_{2}\rceil$ and $a_{3}=\lfloor\tilde{q}_{3}\rfloor$, with $a_{2}$ assigned last by $A$. Then $\tilde{A}$ results in the final apportionment with $a_{2}=\lfloor\tilde{q}_{2}\rfloor$, which is a not lower quota violation.

Define $I_{3}=[d^{**},1).$ For $d\in I_{3}$, $a_{2}=\lfloor\tilde{q}_{2}\rfloor$ and $a_{3}=\lceil\tilde{q}_{3}\rceil$ with $a_{3}$ assigned last by $A$. Then $\tilde{A}$ results in the final apportionment with $a_{3}=\lfloor\tilde{q}_{3}\rfloor$, which is a not lower quota violation.

Thus lower quota violations occur precisely for $d\in I_{1}=[0,d^{*})$. ∎

We summarize the results of this lemma with the below table:

| Interval               | $A$ assigns $a_{2}$           | $A$ assigns $a_{3}$           | Assigned Last | Lower Quota Violation? |
| ---------------------- | ----------------------------- | ----------------------------- | ------------- | ---------------------- |
| $I_{1}=[0,d^{*})$      | $\lceil\tilde{q}_{2}\rceil$   | $\lfloor\tilde{q}_{3}\rfloor$ | $a_{3}$       | Yes                    |
| $I_{2}=[d^{*},d^{**})$ | $\lceil\tilde{q}_{2}\rceil$   | $\lfloor\tilde{q}_{3}\rfloor$ | $a_{2}$       | No                     |
| $I_{3}=[d^{**},1)$     | $\lfloor\tilde{q}_{2}\rfloor$ | $\lceil\tilde{q}_{3}\rceil$   | $a_{3}$       | No                     |

#### Remark 5.6.

It may occur that $d^{*}=0$, in which case $I_{1}=\emptyset$. It may also occur that $d^{**}=1$, in which case $I_{3}=\emptyset$.

#### Remark 5.7.

By Theorem [3.6](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem6), there is no value of $d\in(0,1)$ for which the final seat is assigned to state 2 while $a_{2}=\lfloor\tilde{q}_{2}\rfloor$.

In summary, for each fixed $\tilde{q}_{3}$, a lower quota violation occurs if and only if $d\in[0,d^{*}).$ Equivalently, violations occur precisely when $\tilde{q}_{3}$ lies in the interval $(\lfloor\tilde{q}_{3}\rfloor,\;\lfloor\tilde{q}_{3}\rfloor+d^{*}),$ and these hold within each fixed integer interval.

#### 5.2.1 A formula for $d^{*}$

To find the interval length ending at $d^{*}$, a function is required that determines $d^{*}$ given $\lfloor\tilde{q}_{3}\rfloor$.

##### Definition/Lemma 5.8.

There exists a function $D(x)$ that calculates $d^{*}$.

##### Proof.

By the interval definitions in Lemma [5.5](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem5), the priority value associated with the larger state’s final seat is less than the priority value associated with the smaller state’s final seat for $d<d^{*}$. Therefore, $d^{*}$ occurs precisely when the priority values are equal:

$$
\begin{aligned}
\frac{\lfloor\tilde{q}_{3}\rfloor+d^{*}}{\delta(\lfloor\tilde{q}_{3}\rfloor-1)}=\frac{M-\lfloor\tilde{q}_{3}\rfloor-d^{*}}{\delta(M-1-\lfloor\tilde{q}_{3}\rfloor)}
\end{aligned}
$$

Solving for $d^{*}$ yields:

$$
\begin{aligned}
d^{*}=\frac{(M-\lfloor\tilde{q}_{3}\rfloor)\delta(\lfloor\tilde{q}_{3}\rfloor-1)-\lfloor\tilde{q}_{3}\rfloor\delta(M-\lfloor\tilde{q}_{3}\rfloor-1)}{\delta(\lfloor\tilde{q}_{2}\rfloor-1)+\delta(M-\lfloor\tilde{q}_{2}\rfloor-1)}
\end{aligned}
$$

Since divisor functions satisfy $\delta(k)>0$ for all admissible $k$, the denominator is strictly positive, and $d^{*}\in[0,1)$.

This then lets us define the function $D(k):\mathbb{N}\to\mathbb{R}$, for $M$ and $\delta(x)$ given, by

$$
\begin{aligned}
D(k):=\frac{(M-k)\delta(k-1)-k\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}
\end{aligned}
$$

∎

##### Remark 5.9.

Note, while $D(k)$ is defined for any $k\in\mathbb{R}$ where $\delta(k)$ is defined and the denominator is not zero, we will only need it for positive integers $k$. In addition, $D(k)$ can output negative values. $d^{*}$ will only be defined by $D(k)$ when $D(k)\in[0,1).$ If $D(k)<0,I_{1}=\emptyset.$

##### Lemma 5.10.

Suppose $k=\left\lfloor\frac{M}{2}\right\rfloor$. If $M$ is even, then $d^{*}=0$ and $I_{1}=\{0\}$. If $M$ is odd, then $d^{*}<0$ and $I_{1}=\emptyset$. In either case, $\mathrm{len}(I_{1})=0$.

##### Proof.

For $M$ even, $\lfloor\frac{M}{2}\rfloor=\frac{M}{2}$. Then, use the function $D$ to calculate $d^{*}$:

$$
\begin{aligned}
d^{*}=D\left(\frac{M}{2}\right)=\frac{\left(M-\frac{M}{2}\right)\delta\left(\frac{M}{2}-1\right)-\frac{M}{2}\delta\left(M-\frac{M}{2}-1\right)}{\delta\left(\frac{M}{2}-1\right)+\delta\left(M-\frac{M}{2}-1\right)}.
\end{aligned}
$$

Note the numerator is 0 and the denominator is $2\delta(\frac{M}{2}-1)$ is strictly positive, so $d^{*}=0$ Thus, $I_{1}=[0,d^{*})=\emptyset$ and $\text{len}(I_{1})=0$.

For $M$ odd, $k=\left\lfloor\frac{M}{2}\right\rfloor=\frac{M-1}{2}$. Then $d^{*}=D(k).$ Since

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)},
\end{aligned}
$$

and since $M-k=\frac{M+1}{2}$,and $M-k-1=k$ this simplifies to:

$$
\begin{aligned}
D(k)=\frac{\frac{M+1}{2}\,\delta(k-1)-\frac{M-1}{2}\,\delta(k)}{\delta(k-1)+\delta(k)}.
\end{aligned}
$$

The denominator is strictly positive so the sign of $D(k)$ is determined by the numerator $N:=\frac{M+1}{2}\,\delta(k-1)-\frac{M-1}{2}\,\delta(k).$

A direct substitution of the divisor functions yields:

1. For Adams ($\delta(s)=s$), $N=-1<0$.
2. For Jefferson ($\delta(s)=s+1$), $N=0$.
3. For Webster ($\delta(s)=s+\tfrac{1}{2}$), $N=-\tfrac{1}{2}<0$.
4. For Huntington-Hill and Dean, a straightforward computation likewise gives $N<0$.

Thus $D(k)\leq 0$ for all five workable methods, with equality occurring only for Jefferson. As such, $d^{*}\leq 0$. Since admissible $d\in[0,1)$, it follows that $I_{1}=[0,d^{*})=\emptyset$ for $d^{*}\leq 0$ and therefore $\mathrm{len}(I_{1})=0$. ∎

##### Remark 5.11.

If $\left\lfloor\tilde{q}_{2}\right\rfloor=M$, then the associated lower-violation interval $I_{1}$ has length zero since $D(M)=0$. If $k<\lceil\frac{M}{2}\rceil$, then $D(k)<0$ and $I_{1}=\emptyset.$ Thus, when searching for quota violations, it suffices to consider $\left\lfloor\tilde{q}_{2}\right\rfloor\in[\left\lceil\frac{M}{2}\right\rceil,\,M-1]$.

We are now ready to prove the main result of this section:

##### Theorem 5.12.

Let $A$ be a divisor method with divisor function $\delta$ that guarantees nonzero allocations on M seats and $n=3$ states. Then, under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$, with $1<x<y$, the probability of a quota violation is the same as the probability of a quota violation caused by states guaranteed nonzero allocations and is calculated by:

$$
\begin{aligned}
P(A(1,x,y)\text{ has a q.v.})=\sum_{k=\lceil M/2\rceil}^{M-1}M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right)
\end{aligned}
$$

where $k$ indexes the integer values of $\lfloor\tilde{q}_{3}\rfloor$, where

$$
\begin{aligned}
\tilde{q}_{3}=\frac{2M}{3-3\tau},\qquad\tau=\frac{\mathrm{mean}(1,x,y)-\mathrm{median}(1,x,y)}{\max(1,x,y)}=\dfrac{1-2x+y}{3y}.
\end{aligned}
$$

and

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

##### Proof.

Combining the previous lemmas yields the stated expression. By Theorem [5.3](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem3) it suffices to find the probability that a given $\tau$ is ultimately violatory. Since $\tilde{q}_{3}=\frac{2M}{3-3\tau}$ is a bijection, fixing $\tau$ then determines $\tilde{q}_{3}$, and vice versa.

By Lemma [5.5](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem5), for a fixed $\tilde{q}_{3}$, quota violations can only be lower quota violations and they only occur in the interval $(\lfloor\tilde{q}_{3}\rfloor,\lfloor\tilde{q}_{3}\rfloor+d^{*})$.

Translate this interval into its corresponding values of $\tau$ through the strictly increasing relation $\tau=1-\frac{2M}{3\tilde{q}_{3}}$ to map this interval to

$$
\begin{aligned}
(1-\frac{2M}{3\lfloor\tilde{q}_{3}\rfloor},1-\frac{2M}{3(\lfloor\tilde{q}_{3}\rfloor+D(\lfloor\tilde{q}_{3}\rfloor))}),
\end{aligned}
$$

where $D(x)$ calculates $d^{*}$ as defined in Lemma [5.8](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem8).

The probability of an ultimately-violatory $\tau$ is then the sum of the length of all such intervals for all choices of $\tilde{q}_{3}\in\left\{\left\lceil\frac{M}{2}\right\rceil,\dots,M-1\right\}$ by Lemma [5.5](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem5) and Remark [5.11](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem11) over the length of all possible $\tau$ values, which is $\frac{2}{3}$ by Lemma [4.4](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem4).

The probability is then:

$$
\begin{aligned}
\frac{3}{2}\left(\sum_{\lfloor\tilde{q}_{3}\rfloor=\lceil\frac{M}{2}\rceil}^{M-1}\left(1-\frac{2M}{3(\lfloor\tilde{q}_{3}\rfloor+D(\lfloor\tilde{q}_{3}\rfloor))}\right)-\left(1-\frac{2M}{3\lfloor\tilde{q}_{3}\rfloor}\right)\right)
\end{aligned}
$$

which simplifies to

$$
\begin{aligned}
\sum_{\lfloor\tilde{q}_{3}\rfloor=\lceil\frac{M}{2}\rceil}^{M-1}M\left(\frac{1}{\lfloor\tilde{q}_{3}\rfloor}-\frac{1}{\lfloor\tilde{q}_{3}\rfloor+D(\lfloor\tilde{q}_{3}\rfloor)}\right).
\end{aligned}
$$

∎

This formula has a nice closed form for the Modified Jefferson’s method:

##### Corollary 5.12.1.

Let $A$ be the Modified Jefferson method with divisor function

$$
\begin{aligned}
\delta(s)=\begin{cases}0&s=0,\\
s+1&s\geq 1.\end{cases}
\end{aligned}
$$

Then, under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$ with $1<x<y$, the probability of a quota violation caused by nonzero allocations is exactly

$$
\begin{aligned}
P_{M}^{\mathrm{JEFF}}=\frac{1}{M-1}.
\end{aligned}
$$

##### Proof.

By Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12), the probability of a quota violation is

$$
\begin{aligned}
P_{M}^{\mathrm{JEFF}}=\sum_{k=\lceil M/2\rceil}^{M-1}M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right),
\end{aligned}
$$

where

$$
\begin{aligned}
D(k)=\frac{(M-k)\,\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

Since $\delta(k)=k+1$ for $k\geq 1$, $\delta(k-1)=k$ for all $k\geq 1$. For $k\leq M-2$, $M-k-1\geq 1$, so $\delta(M-k-1)=M-k$. Substituting:

$$
\begin{aligned}
D(k)=\frac{(M-k)\cdot k-k\cdot(M-k)}{k+(M-k)}=\frac{0}{M}=0,
\end{aligned}
$$

so every summand vanishes for $\lceil M/2\rceil\leq k\leq M-2$.

For $k=M-1$, $M-k-1=0$ and the modified case $\delta(0)=0$ applies. Substituting:

$$
\begin{aligned}
D(M-1)=\frac{1\cdot(M-1)-(M-1)\cdot 0}{(M-1)+0}=\frac{M-1}{M-1}=1.
\end{aligned}
$$

Therefore $k+D(k)=M$, and the summand at $k=M-1$ is:

$$
\begin{aligned}
M\left(\frac{1}{M-1}-\frac{1}{M}\right)=M\cdot\frac{1}{M(M-1)}=\frac{1}{M-1}.
\end{aligned}
$$

Since all other summands are zero, the total probability is

$$
\begin{aligned}
P_{M}^{\mathrm{JEFF}}=\frac{1}{M-1},
\end{aligned}
$$

which confirms the value stated in Section 5.4 and agrees with $\lim_{M\to\infty}P_{M}^{\mathrm{JEFF}}=0$ as given in Theorem [5.16](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem16). ∎

We would now like to lift this result from the reduced population vector $(1,x,y)$ to the original population vector $(p_{1},p_{2},p_{3})$. Apportionments are proportional, so events like lower quota violations are invariant under scaling, but probabilities are not unless the sampling model is scale invariant. A natural choice then is to sample $(p_{1},p_{2},p_{3})$ from a scale-invariant distribution, e.g. as i.i.d. continuous variables with density depending only on their ratios. Proposition [5.2](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem2) gives the assumption needed: that $\frac{p_{2}}{p_{3}}$ be uniform on $(0,1)$. Then $\tau$ will be uniform on $(-\frac{1}{3},\frac{1}{3})$ and we can lift the probability formulas. Without these assumptions on $(p_{1},p_{2},p_{3})$, the probability results from the prior theorem may no longer apply. We formalize this in the following.

##### Corollary 5.12.2.

Let $(p_{1},p_{2},p_{3})$ be a random population vector with $p_{1}<p_{2}<p_{3}$, and define $x=\frac{p_{2}}{p_{1}}$, $y=\frac{p_{3}}{p_{1}}$. Assume that the induced ratios satisfy the hypotheses of Proposition [5.2](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem2); namely, that $u=\frac{x}{y}=\frac{p_{2}}{p_{3}}$ is asymptotically uniformly distributed on $(0,1)$ and $y\to\infty$ in density.

Let $A$ be a divisor method that guarantees nonzero allocations, and let $\tau$ be as in Definition [4.1](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem1). Then:

1. $\tau\sim\mathrm{Unif}\!\left(-\frac{1}{3},\frac{1}{3}\right)$ asymptotically.
2. The probability that $A(p_{1},p_{2},p_{3})$ exhibits a lower quota violation caused by nonzero allocations satisfies

   $$
   \begin{aligned}
   P(\text{quota violation})=P(\text{quota violation caused by nonzero allocation})=P(\tau\text{ is ultimately violatory}).
   \end{aligned}
   $$

In particular, this probability coincides with that obtained under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$.

##### Proof.

By Lemma [3.1](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem1) (Proportionality), divisor methods are invariant under scaling, so $A(p_{1},p_{2},p_{3})=A(1,x,y).$ Thus quota violation events depend only on the reduced population vector. By Proposition [5.2](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem2), the assumptions on $(p_{1},p_{2},p_{3})$ imply that the induced distribution of $\tau$ converges to $\mathrm{Unif}\!\left(-\frac{1}{3},\frac{1}{3}\right)$.

By Theorem [4.6](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem6), for each $\tau$ outside a finite exceptional set, the occurrence or non-occurrence of a lower quota violation for $A(1,x,y(x,\tau))$ stabilizes for all sufficiently large $x$, and is completely determined by whether $\tau$ is ultimately violatory. Therefore, the probability of a lower quota violation given $\tau$ depends only on $\tau$. As such, $P(\text{lower quota violation})=P(\tau\text{ is ultimately violatory}).$

Since both the present model on $(p_{1},p_{2},p_{3})$ and the asymptotic uniform model on $(1,x,y)$ induce the same limiting distribution on $\tau$, the resulting probabilities coincide. ∎

### 5.3 Numerical Behavior of the Probability Formula

Table [1](https://arxiv.org/html/2605.06556v1#S5.T1) below presents approximate values of the probability of lower quota violations caused by nonzero allocations for the classical divisor methods and increasing values of $M$. Values are rounded to 3 decimal places.

**Table 1.** Approximate probabilities of lower quota violations caused by nonzero allocations for several divisor methods, computed using Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12). Values rounded to 3 decimal places.

| Method             | $M=10$ | $M=20$ | $M=50$ | $M=100$ | $M=500$ | $M=1000$ |
| ------------------ | ------ | ------ | ------ | ------- | ------- | -------- |
| Modified Jefferson | 0.111  | 0.053  | 0.020  | 0.010   | 0.002   | 0.001    |
| Adams              | 0.380  | 0.385  | 0.386  | 0.386   | 0.386   | 0.386    |
| Modified Webster   | 0.235  | 0.213  | 0.201  | 0.197   | 0.194   | 0.194    |
| Huntington-Hill    | 0.257  | 0.229  | 0.209  | 0.202   | 0.195   | 0.194    |
| Dean               | 0.278  | 0.244  | 0.218  | 0.207   | 0.197   | 0.195    |

Several patterns emerge:

1. The probabilities appear to converge as $M\to\infty$ to method-dependent constants. The next section will prove this to be true.
2. Since the Jefferson method has no lower quota violations, the only quota violations that occur will arise from the modified method. As such, the sum $P_{M}$ in Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12) above gives the probability for all lower quota violations for three states. This formula simplifies to $\frac{1}{M-1}$ by Corollary [5.12.1](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12.Thmcorollary1). This shows that as $M$ increases, the limit of the probability for a lower quota violation approaches 0.
3. Adams method exhibits limiting behavior quickly near 0.386. This value turns out to be exactly $2\ln(2)-1\approx 0.386294$ as shown in the next section.
4. The Webster, Huntington-Hill, and Dean’s method all exhibit limiting behavior, with limiting values near $0.193$. This limit will turn out to be $\ln(2)-\tfrac{1}{2}\approx 0.193147$ as shown in the next section.

#### Remark 5.13.

The probabilities in Table [1](https://arxiv.org/html/2605.06556v1#S5.T1) for the Modified Webster method admit a particularly clean interpretation. By Theorem 4.5(b) of \[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\], Webster’s method is the unique divisor method for which no quota violations occur in the three-state case when there are no allocation constraints. Therefore, every quota violation appearing in Table [1](https://arxiv.org/html/2605.06556v1#S5.T1) for Modified Webster is entirely attributable to the nonzero allocation constraint. In this sense, Modified Webster isolates the effect of the constraint most cleanly among the five workable methods: its unmodified violation probability is exactly zero, making the values in Table [1](https://arxiv.org/html/2605.06556v1#S5.T1) a pure measure of the constraint’s impact. By contrast, the Adams, Dean, and Huntington-Hill methods have nonzero unconstrained violation probabilities for $n=3$ states, so their entries reflect a combination of the method’s inherent tendency to violate quota and the additional effect of the nonzero allocation constraint.

### 5.4 Asymptotic Limit as $M\to\infty$

We now derive a closed-form expression for the limiting probability of lower quota violations caused by nonzero allocations in $n=3$ seats for different apportionment methods as $M\to\infty$.

By Corollary [5.12.1](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12.Thmcorollary1), the Modified Jefferson’s method has $P_{M}=\frac{1}{M+1}$ and therefore

$$
\begin{aligned}
\lim_{M\to\infty}P_{M}^{\mathrm{JEFF}}=0.
\end{aligned}
$$

Next, we analyze Adams Method as $M\to\infty$.

#### Theorem 5.14 (Limiting Probability for Adams Method).

Let $A$ be the Adams apportionment method with divisor function $\delta(x)=x$ and let $M$ denote the total number of seats. Then, under the asymptotic uniform distribution on reduced population vectors $(1,x,y)$ with $1<x<y$, the probability of a quota violation converges as $M\to\infty$ to

$$
\begin{aligned}
P_{\infty}^{\text{ADAMS}}=\lim_{M\to\infty}\sum_{k=\lceil M/2\rceil}^{M-1}M\Biggl(\frac{1}{k}-\frac{1}{k+D(k)}\Biggr)=2\ln(2)-1\approx 0.386294,
\end{aligned}
$$

where

$$
\begin{aligned}
D(k)=\frac{(2k-M)}{M-2}.
\end{aligned}
$$

#### Proof.

When $\delta(k)=k$, $D(k)$ from Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12) simplifies to $D(k)=\frac{2k-M}{M-2}$. Define the variable $x=\frac{k}{M}\in\left[\tfrac{1}{2},1\right].$

Then, for large $M$,

$$
\begin{aligned}
D(k)=\frac{2k-M}{M-2}\sim\frac{2k-M}{M}=2x-1.
\end{aligned}
$$

The summand in $P_{M}$ then becomes:

$$
\begin{aligned}
\displaystyle M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right) & \displaystyle=M\left(\frac{D(k)}{k(k+D(k)}\right)
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle\sim M\left(\frac{2x-1}{(Mx)(Mx+2x-1)}\right)
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle\sim M\left(\frac{2x-1}{(Mx)(Mx)}\right)
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle\sim\frac{2x-1}{x^{2}}\cdot\frac{1}{M}
\end{aligned}
$$

As $M\to\infty$, the sum over $k$ becomes an integral over $x$, and $\frac{1}{M}$ becomes $dx$:

$$
\begin{aligned}
\sum_{k=\lceil M/2\rceil}^{M-1}M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right)\sim\int_{1/2}^{1}\left(\frac{2x-1}{x^{2}}\right)dx.
\end{aligned}
$$

Evaluate the integral to get

$$
\begin{aligned}
P_{\infty}^{\text{ADAMS}}=2\ln(2)-1\approx 0.386294.
\end{aligned}
$$

∎

The next result identifies a common asymptotic behavior for a broad class of divisor methods whose divisor functions differ from linear growth by a bounded perturbation. In particular, the theorem shows that the limiting probability of a quota violation depends only on the first-order structure of the divisor function, leading to a common limit shared by several classical methods.

#### Theorem 5.15 (Limiting Probability for Asymptotically Linear Divisor Methods).

Let $A$ be a divisor method with divisor function satisfying

$$
\begin{aligned}
\delta(k)=k+\frac{1}{2}+O\!\left(\frac{1}{k}\right).
\end{aligned}
$$

Let

$$
\begin{aligned}
P_{M}=\sum_{k=\lceil M/2\rceil}^{M-1}M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right),
\end{aligned}
$$

where

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

Then

$$
\begin{aligned}
\lim_{M\to\infty}P_{M}=\ln 2-\frac{1}{2}.
\end{aligned}
$$

In particular, this holds for the Huntington-Hill, Modified Webster, and Dean method.

#### Proof.

For the Huntington-Hill method, the divisor function $\delta(k)=\sqrt{k(k+1)}$ has Laurent expansion $k+\frac{1}{2}-\frac{1}{8k}+\ldots$. After polynomial division, the divisor function for Dean’s method is $\delta(k)=\frac{2k(k+1)}{2k+1}=k+\frac{1}{2}-\frac{1}{2(2k+1}$. Along with the divisor function for Webster’s method, $\delta(k)=k+0.5$, all three apportionment methods satisfy the assumption of the theorem.

Using the assumption $\delta(k)\sim k+\frac{1}{2}$, write

$$
\begin{aligned}
\delta(k-1)=k-\frac{1}{2}\qquad\delta(M-k-1)=(M-k)-\frac{1}{2}.
\end{aligned}
$$

Substitute into $D(k)$ to get

$$
\begin{aligned}
D(k)=\frac{(M-k)(k-\frac{1}{2})-k((M-k)-\frac{1}{2})}{(k-\frac{1}{2})+((M-k)-\frac{1}{2})}=\frac{2k-M}{2(M-1)}
\end{aligned}
$$

Since $D(k)<1$ and $k>1,\frac{D(k)}{k}<1$, by the geometric series,

$$
\begin{aligned}
\frac{1}{k+D(k)}=\frac{1}{k}\cdot\frac{1}{1+\frac{D(k)}{k}}=\frac{1}{k}\left(1-\frac{D(k)}{k}+\left(\frac{D(k)}{k}\right)^{2}+\ldots\right)=\frac{1}{k}-\frac{D(k)}{k^{2}}+\ldots
\end{aligned}
$$

where the remaining terms are of order $\frac{1}{M^{3}}$. The expression in the summand of $P_{M}$ then becomes

$$
\begin{aligned}
M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right)\sim M\left(\frac{1}{k}-\left(\frac{1}{k}-\frac{D(k)}{k^{2}}\right)\right)=M\cdot\frac{D(k)}{k^{2}}
\end{aligned}
$$

Set $x=\frac{k}{M}\in[\tfrac{1}{2},1]$. Then as $M\to\infty,D(k)\sim\frac{2x-1}{2}$. Then

$$
\begin{aligned}
M\left(\frac{1}{k}-\frac{1}{k+D(k)}\right)\sim M\cdot\frac{D(k)}{k^{2}}\sim M\frac{(2x-1)}{x^{2}M^{2}}=\frac{2x-1}{x^{2}}\cdot\frac{1}{M}
\end{aligned}
$$

The sum is a Riemann sum, so as $M\to\infty,$

$$
\begin{aligned}
P_{M}\to\int_{1/2}^{1}\frac{2x-1}{2x^{2}}\,dx.
\end{aligned}
$$

Evaluating this integral gives

$$
\begin{aligned}
P_{\infty}^{\text{HH}}=P_{\infty}^{\text{DEAN}}=P_{\infty}^{\text{WEB}}=\ln 2-\frac{1}{2}\approx 0.1932.
\end{aligned}
$$

∎

Summarizing the results of this section:

#### Theorem 5.16.

Under the asymptotic uniform distribution for vectors $(1,x,y)$ with $1<x<y$, we have as $M\to\infty$ that the probability of a quota violation caused by nonzero allocations converges to $2\ln(2)-1\approx 0.386294$ in the Adams method, to $0$ in the Modified Jefferson method, and to $\ln(2)-\frac{1}{2}\approx 0.1932$ in the Huntington-Hill, Modified Webster, and Dean methods.

### 5.5 Probability of Quota Violations along $\tau$-Lines

Next, for divisor methods $A$ corresponding to Huntington-Hill, modified Webster, modified Jefferson, or Dean, extend the results of the previous section to characterize when quota violations occur due to a guaranteed seat.

To do this, the first step is to recall the threshold $x_{\tau}^{F}$ that quantifies when the asymptotic behavior in Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7) effectively holds. Specifically, for $x>x_{\tau}^{F}$, the guaranteed-seat state causes floor stabilization and potential quota violations. Equivalently, $x_{\tau}^{F}$ (from Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7)) is the infimum of all $z$ such that for all $x>z$, the following floor conditions hold (i.e., the floors stabilize).

- $\left\lfloor\frac{M(1-3\tau)}{(3-3\tau)x-3\tau}\right\rfloor=0$
- $\left\lfloor\frac{M(1-3\tau)x}{(3-3\tau)x-3\tau}\right\rfloor=\left\lfloor\frac{M(1-3\tau)}{3-3\tau}\right\rfloor$
- $\left\lfloor\frac{2M(1-3\tau)x-M+3M\tau}{(3-3\tau)(1-3\tau)x-3\tau(1-3\tau)}\right\rfloor=\left\lfloor\frac{2M}{3-3\tau}\right\rfloor.$

By Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7), for such $x$, the apportionment converges to $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})$, with $x_{\tau}$ being the infinum over all $z>x_{\tau}^{F}$ such that $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})=A(1,z,y(z,\tau))$. On a $\tau$-line, parametrized in $y(x,\tau)$

$$
\begin{aligned}
y(x,\tau)=\frac{2x-1}{1-3\tau}=\frac{2}{1-3\tau}x-\frac{1}{1-3\tau}
\end{aligned}
$$

Define then for a fixed $\tau$,

$$
\begin{aligned}
y_{\tau}=y(x_{\tau},\tau)\qquad\text{and}\qquad y_{\tau}^{F}=y(x_{\tau}^{F},\tau)
\end{aligned}
$$

Also recall along a $\tau$-line, the reduced population $(1,x,y)$ can be parametrized as $(1,x(y,\tau),y)$, where $x(y,\tau)=\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2},$ so that the total population is $1+x(y,\tau)+y=\frac{3-3\tau}{2}y+\frac{3}{2}$. Then the standard quotas, as functions of $y$, are:

$$
\begin{aligned}
q_{1}(y)=\frac{M}{1+x(y,\tau)+y},q_{2}(y)=\frac{Mx(y,\tau)}{1+x(y,\tau)+y},q_{3}(y)=\frac{My}{1+x(y,\tau)+y}.
\end{aligned}
$$

Next, determine $y_{\tau}^{F}$, the smallest value of $y$ such that the floor stabilization conditions hold along the $\tau$-line.

#### Definition/Lemma 5.17 (Guaranteed-Seat Threshold).

Fix $\tau\in(-\tfrac{1}{3},\tfrac{1}{3})$. There exists a constant $y_{\tau}^{F}>0$ such that for all $y>y_{\tau}^{F}$, the floors of the standard quotas of the distribution $(1,x(y,\tau),y)$ stabilize:

$$
\begin{aligned}
\bigl(\lfloor q_{1}(y)\rfloor,\lfloor q_{2}(y)\rfloor,\lfloor q_{3}(y)\rfloor\bigr)=\bigl(0,\lfloor\tilde{q}_{2}\rfloor,\lfloor\tilde{q}_{3}\rfloor\bigr),
\end{aligned}
$$

where

$$
\begin{aligned}
\tilde{q}_{2}=\frac{M(1-3\tau)}{3-3\tau},\qquad\tilde{q}_{3}=\frac{2M}{3-3\tau}.
\end{aligned}
$$

#### Proof.

Analyze each quota separately. For state 1,

$$
\begin{aligned}
q_{1}(y)=\frac{M}{\frac{3-3\tau}{2}y+\frac{3}{2}}.
\end{aligned}
$$

This is strictly decreasing in $y$ and satisfies $q_{1}(y)\to 0$ as $y\to\infty$. Then there exists $y_{1}(\tau)$ such that for all $y>y_{1}(\tau)$, $0<q_{1}(y)<1$, so $\lfloor q_{1}(y)\rfloor=0$.

For state 3,

$$
\begin{aligned}
q_{3}(y)=\frac{My}{\frac{3-3\tau}{2}y+\frac{3}{2}}=\frac{2M}{3-3\tau+\frac{3}{y}}.
\end{aligned}
$$

So $q_{3}(y)$ is strictly increasing and converges to $\tilde{q}_{3}$ as $y\to\infty$.

If $\tilde{q}_{3}\in\mathbb{Z}$, then $q_{3}(y)$ converges monotonically to $\tilde{q}_{3}$, so there exists $y_{3}(\tau)$ such that $\lfloor q_{3}(y)\rfloor=\tilde{q}_{3}-1$ for all sufficiently large $y$.

If $\tilde{q}_{3}\notin\mathbb{Z}$, choose $\epsilon>0$ small enough that

$$
\begin{aligned}
(\tilde{q}_{3}-\varepsilon,\tilde{q}_{3}+\varepsilon)\subset\bigl(\lfloor\tilde{q}_{3}\rfloor,\lfloor\tilde{q}_{3}\rfloor+1\bigr).
\end{aligned}
$$

Then there exists $y_{3}(\tau)$ such that for all $y>y_{3}(\tau)$, $|q_{3}(y)-\tilde{q}_{3}|<\epsilon,$ and as such, $\lfloor q_{3}(y)\rfloor=\lfloor\tilde{q}_{3}\rfloor.$

For state 2, use $x(y,\tau)$:

$$
\begin{aligned}
q_{2}(y)=\frac{Mx(y,\tau)}{\frac{3-3\tau}{2}y+\frac{3}{2}}=\frac{M\left(\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2}\right)}{\frac{3-3\tau}{2}y+\frac{3}{2}}.
\end{aligned}
$$

A direct computation shows that $q^{\prime}_{2}(y)$ has constant sign depending on $\tau$:

$$
\begin{aligned}
q_{2}^{\prime}(y)\begin{cases}>0&\text{if }\tau<0,\\
=0&\text{if }\tau=0,\\
<0&\text{if }\tau>0,\end{cases}
\end{aligned}
$$

so $q_{2}(y)$ is monotone and converges to $\tilde{q}_{2}$ as $y\to\infty$.

Thus, as for state 3, there exists $y_{2}(\tau)$ such that for all $y>y_{2}(\tau)$, $\lfloor q_{2}(y)\rfloor=\lfloor\tilde{q}_{2}\rfloor.$ Finally, define

$$
\begin{aligned}
y_{\tau}^{F}:=\max\{y_{1}(\tau),y_{2}(\tau),y_{3}(\tau)\}.
\end{aligned}
$$

Then for all $y>y_{\tau}^{F}$,

$$
\begin{aligned}
(\lfloor q_{1}(y)\rfloor,\lfloor q_{2}(y)\rfloor,\lfloor q_{3}(y)\rfloor)=\left(0,\lfloor\tilde{q}_{2}\rfloor,\lfloor\tilde{q}_{3}\rfloor\right).
\end{aligned}
$$

Additionally, a direct computation grants:

$$
\begin{aligned}
\displaystyle y_{1}(\tau) & \displaystyle=\frac{2M-3}{3-3\tau}
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle y_{2}(\tau) & \displaystyle=\left\{\begin{array}[]{lcl}\frac{3\lfloor\tilde{q}_{2}\rfloor-M}{M-3M\tau-3\lfloor\tilde{q}_{2}\rfloor+3\tau\lfloor\tilde{q}_{2}\rfloor}&\tau<0\\
1&\tau=0\\
\frac{3(\lfloor\tilde{q}_{2}\rfloor+1)-M}{M-3M\tau-3(\lfloor\tilde{q}_{2}\rfloor+1)+3\tau(\lfloor\tilde{q}_{2}\rfloor+1)}&\tau>0\end{array}\right.
\end{aligned}
$$

$$
\begin{aligned}
\displaystyle y_{3}(\tau) & \displaystyle=\frac{3\lfloor\tilde{q}_{3}\rfloor}{2M-3\lfloor\tilde{q}_{3}\rfloor+3\tau\lfloor\tilde{q}_{3}\rfloor}.
\end{aligned}
$$

∎

Note by definition and construction, $y_{\tau}^{F}\leq y_{\tau}$ since $y_{\tau}$ imposes more conditions. For a fixed $\tau$, the constant $y_{\tau}^{F}$ identifies the smallest reduced population of the largest state along the $\tau$-line for which the floors of all standard quotas stabilize. When $y>y_{\tau}^{F}$, the guaranteed seat for state 1 could create an apportionment in such a way that state 3 receives fewer seats than its lower quota, producing a quota violation. This observation motivates the following lemma.

#### Lemma 5.18.

Let $\tau$ be ultimately violatory. If $y>y_{\tau}^{F}$, then the apportionment $\tilde{A}_{1}(1,x(y,\tau),y)$ produces a quota violation caused by the guaranteed seat of state 1. Equivalently, if $\tau$ is ultimately violatory $y_{\tau}^{F}=y_{\tau}$

#### Proof.

For $y>y_{\tau}^{F}$, by Lemma [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17),

$$
\begin{aligned}
(\lfloor q_{1}\rfloor,\lfloor q_{2}\rfloor,\lfloor q_{3}\rfloor)=(0,\lfloor\tilde{q}_{2}\rfloor,\lfloor\tilde{q}_{3}\rfloor).
\end{aligned}
$$

Since state 1 is guaranteed a seat, by Theorem [3.6](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem6) the only possible apportionments are either $(1,\lfloor\tilde{q}_{2}\rfloor,\lfloor\tilde{q}_{3}\rfloor)$ or $(1,\lfloor\tilde{q}_{2}\rfloor+1,\lfloor\tilde{q}_{3}\rfloor-1)$. Since $\tau$ is ultimately violatory, the final apportionment must be $(1,\lfloor\tilde{q}_{2}\rfloor+1,\lfloor\tilde{q}_{3}\rfloor-1)$. This means that either the apportionment where $y>y_{\tau}^{F}$ is either always $(1,\lfloor\tilde{q}_{2}\rfloor+1,\lfloor\tilde{q}_{3}\rfloor-1)$, in which case, the Lemma is proved, or is the first apportionment and becomes $(1,\lfloor\tilde{q}_{2}\rfloor+1,\lfloor\tilde{q}_{3}\rfloor-1)$. However, this latter scenario violates population monotonicity on the third state. ∎

#### Definition/Lemma 5.19 (Non-Violatory Threshold).

Fix $\tau\in(-\frac{1}{3},\frac{1}{3})$ that is ultimately non-violatory. There exists a constant $y_{\tau}>0$ such that for all $y>y_{\tau}$, the apportionment $\tilde{A}_{1}(\tilde{q}_{2},\tilde{q}_{3})$ stabilizes without producing a quota violation.

In particular, $y_{\tau}$ is given by

$$
\begin{aligned}
y_{\tau}:=\max\{y_{\tau}^{F},y_{\tau}^{*}\},
\end{aligned}
$$

where $y_{\tau}$ is the threshold from Lemma [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17), and $y_{\tau}^{*}$ solves the priority-equality condition

$$
\begin{aligned}
\frac{My}{\delta(\lfloor\tilde{q}_{3}\rfloor-1)}=\frac{M\left(\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2}\right)}{\delta(M-\lfloor\tilde{q}_{3}\rfloor-1)}.
\end{aligned}
$$

#### Proof.

First consider the case where $y_{\tau}^{F}$ does not yet calculate $y_{\tau}$. As in the previous proof, the only valid apportionments after $y_{\tau}^{F}$ are $(\lceil q_{1}\rceil,\lceil q_{2}\rceil,\lfloor q_{3}\rfloor-1)$ and $(\lceil q_{1}\rceil,\lfloor q_{2}\rfloor,\lfloor q_{3}\rfloor)$. Since by assumption the final apportionment is non-violatory, the apportionment must be moving from $(\lceil q_{1}\rceil,\lceil q_{2}\rceil,\lfloor q_{3}\rfloor-1)$ toward $(\lceil q_{1}\rceil,\lfloor q_{2}\rfloor,\lfloor q_{3}\rfloor).$

Consider the apportionment functions $A(\tilde{q}_{2},\tilde{q}_{3})$ and $\tilde{A}_{1}(\tilde{q}_{2},\tilde{q}_{3})$. Before reaching $y_{\tau}$, state 3 receives its floor (and potentially loses a seat), while state 2 receives its ceiling. This implies that, at that point, the priority value for assigning state 3 an additional seat is less than the priority value for assigning state 2 an additional seat.

As $y$ increases past $y_{\tau}$, the last seat is assigned in such a way that the priority values equalize, and the inequality flips. Solving for the value of $y$ where the priority values are equal gives

$$
\begin{aligned}
\frac{My}{\delta(\lfloor\tilde{q}_{3}\rfloor-1)}=\frac{M\left(\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2}\right)}{\delta(\lfloor\tilde{q}_{2}\rfloor)}.
\end{aligned}
$$

Solving this equation gives

$$
\begin{aligned}
y_{\tau}^{*}:=\frac{\delta(\lfloor\tilde{q}_{3}\rfloor-1)}{2\,\delta(\lfloor\tilde{q}_{2}\rfloor)+(3\tau-1)\,\delta(\lfloor\tilde{q}_{3}\rfloor-1)}.
\end{aligned}
$$

Finally, it follows the non-violatory threshold is then

$$
\begin{aligned}
y_{\tau}:=\max\{y_{\tau}^{F},y_{\tau}^{*}\}.
\end{aligned}
$$

∎

To summarize the above results, for $y\in(y_{\tau}^{F},y_{\tau})$, the guaranteed seat of state 1 forces one of the other states below its lower quota, producing a temporary quota violation. This violation disappears once $y>y_{\tau}$, consistent with the distribution being ultimately non-violatory. This gives the following:

#### Corollary 5.19.1.

For distributions that are ultimately non-violatory, if $y\in(y_{\tau}^{F},\,y_{\tau})$, then the guaranteed seat of state one temporarily causes a quota violation in the apportionment.

Additionally, the preceding results allow a characterization of the structure of $x_{\tau}$:

#### Theorem 5.20.

(Local structure of $x_{\tau})$ The $\tau$-interval $(-\frac{1}{3},\frac{1}{3})$ can be decomposed into finitely many intervals such that on each interval, $x_{\tau}$ is locally represented in the form $x_{\tau}=\frac{a}{b+c\tau}+\frac{d\tau}{b+c\tau}+e$ for $a,b,c,d,e\in\mathbb{R}$ and denominators not identically $0$.

#### Proof.

By Definition/Lemma [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7) and Lemma [5.18](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem18), $y_{\tau}$ is given by the maximum of functions of the form

$$
\begin{aligned}
\frac{a}{b+c\tau}
\end{aligned}
$$

when $\tau$ is ultimately violatory. For $\tau$ ultimately non violatory, the same form holds by Lemma [5.19](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem19). Decomposing into intervals for violatory and non-violatory, further decomposing based on which component is the maximum, and recalling $x(y,\tau)=\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2}$ grants the desired result.

∎

Next, look at $y$ values less than $y_{\tau}^{F}$ and determine the behavior of any possible quota violations.

#### Lemma 5.21.

If $y<y_{\tau}^{F}$, then no quota violations occur that are caused by the guaranteed seat of state 1 in Huntington-Hill, Modified Jefferson, Dean, and Modified Webster methods.

#### Proof.

Let $A$ denote one of the Huntington-Hill, Modified Jefferson, Dean, or Modified Webster methods with divisor function $\delta$. Let the quotas satisfy $q_{1}<q_{2}<q_{3}$ and fix $\tau$.

Recall $y_{i}(\tau)$ from Definition/Lemma [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17). We may restrict to the case $y>y_{1}(\tau)$ since if $y\leq y_{1}(\tau)$ $q_{1}\geq 1$ and hence a quota violation caused by the nonzero allocation cannot occur.

The proof proceeds by considering two cases, $\tau\leq 0$ and $\tau>0$, due to monotonicity of the quota $q_{2}(y)$ depending on the sign of $\tau$.

Case 1: $\tau\leq 0$. Suppose a quota violation exists. By Lemma [3.6](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem6), the floors of the quotas would have the form

$$
\begin{aligned}
(\lfloor q_{1}\rfloor,\lfloor q_{2}\rfloor,\lfloor q_{3}\rfloor)=(0,\lfloor\tilde{q}_{2}\rfloor\pm s,\lfloor\tilde{q}_{3}\rfloor\mp s),\quad s>0.
\end{aligned}
$$

But for $\tau\leq 0$, $q_{1}$ and $q_{2}$ are non-decreasing towards their limits $\tilde{q}_{2},\tilde{q}_{3}$. Hence, such floors cannot occur, so no violation exists.

Case 2: $\tau>0$. First, note that we may assume $y_{(2,+)}\leq\max(y_{2},y_{1})$, as otherwise there would exist $y$ such that the quotas at $y$ satisfy $(\lfloor q_{1}\rfloor,\lfloor q_{2}\rfloor,\lfloor q_{3}\rfloor)=(0,\lfloor\tilde{q}_{2}\rfloor+s,\lfloor q_{3}\rfloor)$ where $s>0$. But then $\sum\lfloor q_{i}\rfloor\geq M$ and therefore there cannot be a quota violation by Theorem [3.4](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem4).

Given $y_{1}(\tau)<y<y_{\tau}^{F}$, it therefore suffices to check two intervals: $y_{1}\leq y\leq y_{(2,+)}$ and $y_{(2,+)}\leq y\leq y_{3}$.

For $y_{(2,+)}\leq y\leq y_{3}$, the floor of $q_{3}$ is $\lfloor\tilde{q}_{3}\rfloor-s$ with $s\geq 1$, so $\sum\lfloor q_{i}\rfloor<M-1$. By Theorem [3.4](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem4), no quota violation occurs.

For $y_{1}\leq y\leq y_{(2,+)}$, the floor of $q_{1}$ is 0, and $q_{2}$ decreases monotonically towards $\tilde{q}_{2}$. At $y=y_{1}(\tau)$ compute,

$$
\begin{aligned}
q_{2}=\tilde{q}_{2}+\epsilon,\quad 0<\epsilon<\frac{1}{2},
\end{aligned}
$$

It follows then for all $y\in(y_{1}(\tau),y_{(2,+)}(\tau))$ that $\lfloor q_{2}\rfloor=\lfloor\tilde{q}_{2}\rfloor+1$ and $\lfloor q_{1}\rfloor=0$. Additionally, the corresponding decimal parts $(d_{1},d_{2})$ trace a line segment entirely below the line $y=\frac{1}{2}x$ in the unit square. Interpreting Theorem [3.4](https://arxiv.org/html/2605.06556v1#S3.Thmtheorem4) geometrically in the manner described in \[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\] as a feasible region of $\{(d_{1},d_{2})\}$ for lower quota violations and considering the largest possible feasible region given the previously stated floors grants that lower quota violations can only occur within the triangle given by $(0,\delta(1)-1),(2-\delta(1),\delta(1)-1)$, and $(0,1)$. Since the trajectory of $(d_{1},d_{2})$ lies outside this region, no lower quota violation occurs for $y_{1}(\tau)<y<y_{(2,+)}.$

Combing the two intervals, we conclude for $\tau>0$ no quota violations caused by nonzero allocations occur when $y<y_{\tau}^{F}$. Together with the case $\tau\leq 0$, the result follows. ∎

Summarizing the above results gives the following:

#### Theorem 5.22 (Quota Violation Probability).

Let $M$ be the total number of seats, and let $A$ be the Modified Jefferson, Modified Webster, Dean, or Huntington-Hill method with divisor function $\delta$. Let $(1,x,y)$ be a reduced population vector with $1<x<y$, drawn from a probability distribution with joint density $f(x,y)$.

For each $\tau\in\left(-\frac{1}{3},\frac{1}{3}\right)$, the $\tau$-line parametrization in $x$ is

$$
\begin{aligned}
x=x(y,\tau):=\frac{1}{2}y-\frac{3}{2}\tau y+\frac{1}{2},
\end{aligned}
$$

Let the set of ultimately violatory $\tau$ values be

$$
\begin{aligned}
V=\bigcup_{k=\lfloor M/2\rfloor+1}^{M-1}\left(1-\frac{2M}{3k},\,1-\frac{2M}{3\bigl(k+D(k)\bigr)}\right),
\end{aligned}
$$

where

$$
\begin{aligned}
D(k)=\frac{(M-k)\delta(k-1)-k\,\delta(M-k-1)}{\delta(k-1)+\delta(M-k-1)}.
\end{aligned}
$$

For each $\tau$, let $y^{F}_{\tau}$ denote the floor-stabilization threshold and $y_{\tau}$ the agreement with asymptotic apportionment threshold defined in Lemma [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17). Define

$$
\begin{aligned}
y_{\tau}^{\max}:=\begin{cases}\infty&\text{if }\tau\in V,\\
y_{\tau}&\text{if }\tau\notin V.\end{cases}
\end{aligned}
$$

Then the probability of a quota violation caused by a guaranteed seat is

$$
\begin{aligned}
\Pr(\text{quota violation})=\int_{-1/3}^{1/3}\int_{y_{\tau}^{F}}^{y_{\tau}^{\max}}f\bigl(x(y,\tau),\,y\bigr)\,\frac{3}{2}y\,dy\,d\tau.
\end{aligned}
$$

#### Proof.

For a fixed $\tau\in(-\frac{1}{3},\frac{1}{3})$, the reduced population vector $(1,x,y)$ can be parametrized along the $\tau$-line by

$$
\begin{aligned}
y=y(x,\tau)=\frac{2(x-1)+3\tau(x+1)}{3-3\tau}.
\end{aligned}
$$

Along each such line, Lemmas [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17) and [5.19](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem19) define the guaranteed-seat threshold $y_{\tau}^{F}$ and the agreement with asymptotic apportionment threshold $y_{\tau}$.

By the preceding lemmas, a quota violation caused by the guaranteed seat of state 1 occurs precisely when $y>y_{\tau}^{F}$ and $y\leq y_{\tau}^{\mathrm{max}}$, where

$$
\begin{aligned}
y_{\tau}^{\mathrm{max}}=\begin{cases}\infty,&\tau\in V\text{ (ultimately violatory)},\\
y_{\tau},&\tau\notin V\text{ (temporarily violatory)}.\end{cases}
\end{aligned}
$$

This follows from the monotonicity of the quotas $q_{1}(y),q_{2}(y),q_{3}(y)$ and the stabilization of their floors as $y$ increases.

The probability of a quota violation is then obtained by integrating the probability density $f(x,y)$ over all $\tau$-lines and all $y$ in the violation interval:

$$
\begin{aligned}
\Pr(\text{quota violation})=\int_{-\frac{1}{3}}^{\frac{1}{3}}\int_{y^{F}_{\tau}}^{y_{\tau}^{\mathrm{max}}}f(x(y,\tau),y)\left|\frac{\partial x}{\partial y}\right|\,dy\,d\tau.
\end{aligned}
$$

Since the union of these intervals over all $\tau$ covers exactly the set of population vectors for which the guaranteed seat of state 1 causes a quota violation (temporarily or ultimately), the integral of $f(x,y)$ computes the total probability. ∎

#### Remark 5.23.

Lemma [5.21](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem21) does not hold for the Adams method. A counterexample is the population vector $(1,6.25,115)$ which produces a quota violation caused by nonzero allocations, but $y=115<y_{\tau}^{F}=570$. Consequently, the prior Theorem [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22) can, in general, provide only a lower bound on the probability of a quota violation caused by nonzero allocations when applied to the Adams method.

### 5.6 Summary of notation used

For clarity, the following is a list of relevant notation used in the paper.

**Table 2.** Threshold notation summary for the $\tau$-stabilization framework.

| **Symbol**                          | **Description**                                                              | **Defined in**                                                         |
| ----------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Thresholds in $x$-parametrization:  |                                                                              |                                                                        |
| $x_{\tau}^{A}$                      | Apportionment equals limiting value $\tilde{A}(\tilde{q}_{2},\tilde{q}_{3})$ | Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7)      |
| $x_{\tau}^{F}$                      | Quota floors stabilize at $\lfloor\tilde{q}_{i}\rfloor$                      | Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7)      |
| $x_{\tau}$                          | $\max\{x_{\tau}^{A},x_{\tau}^{F}\}$: full stabilization                      | Theorem [4.7](https://arxiv.org/html/2605.06556v1#S4.Thmtheorem7)      |
| Thresholds in $y$-parametrization:  |                                                                              |                                                                        |
| $y_{\tau}^{F}$                      | Floor stabilization in $y$; equals $y(x_{\tau}^{F},\tau)$                    | Def./Lemma [5.17](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem17) |
| $y_{\tau}$                          | $\max\{y_{\tau}^{F},y_{\tau}^{*}\}$: non-violatory threshold                 | Def./Lemma [5.19](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem19) |
| $y_{\tau}^{\max}$                   | Upper integration limit ($\infty$ if $\tau\in V$, else $y_{\tau}$)           | Theorem [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22)    |
| Limiting quotas and violation sets: |                                                                              |                                                                        |
| $\tilde{q}_{2},\tilde{q}_{3}$       | $\lim_{x\to\infty}q_{2}(x),q_{3}(x)$ along $\tau$-line                       | Page 9                                                                 |
| $V$                                 | Set of ultimately violatory $\tau$ values                                    | Theorem [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22)    |
| $D(k)$                              | Length of violation interval for $\lfloor\tilde{q}_{3}\rfloor=k$             | Def./Lemma [5.8](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem8)   |

## 6 Conclusion

The results in this paper contribute both conceptually and practically to apportionment theory. Conceptually, $\tau$ provides a geometrically transparent coordinate that captures skewness and identifies families of distributions with uniform asymptotic behavior. Practically, the probability formulas and limits quantify how frequently common divisor methods violate quota when per‑state minimums are enforced, giving policymakers a principled basis for comparing methods.

This paper is a natural continuation of the authors’ first paper. In that paper, (\[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\]) quota violations that are intrinsic to the divisor method itself (violations that arise purely from the population distribution and the method’s rounding behavior) are analyzed. This nonzero divisor paper studies a more constrained setting, isolating violations that are caused or worsened by the requirement that every state receive at least one seat. Definition [1.2](https://arxiv.org/html/2605.06556v1#S1.Thmtheorem2) makes this distinction precise. The combined results would allow one to compute, for each divisor method, the fraction of all quota violations in the constrained system that are directly attributable to the nonzero allocation constraint rather than to the method’s inherent tendency to violate quota. This is a quantity of direct practical relevance to the design of apportionment systems with minimum representation guarantees.

This work extends a growing body of research on probabilistic approaches to apportionment in social choice theory and electoral mathematics. Most directly, it builds upon earlier work found in \[[13](https://arxiv.org/html/2605.06556v1#bib.bib1)\]. Additionally, it is related to analyses of systemic bias in apportionment methods \[[11](https://arxiv.org/html/2605.06556v1#bib.bib13), [12](https://arxiv.org/html/2605.06556v1#bib.bib12), [3](https://arxiv.org/html/2605.06556v1#bib.bib14), [9](https://arxiv.org/html/2605.06556v1#bib.bib15)\], and investigations into the likelihood of voting paradoxes \[[5](https://arxiv.org/html/2605.06556v1#bib.bib9), [10](https://arxiv.org/html/2605.06556v1#bib.bib17)\].

Natural next steps include refining the probabilistic model to reflect empirical population distributions (state‑size histograms or heavy‑tailed models), deriving finite‑$M$ error bounds for the Riemann‑sum approximations, computing explicit polyhedral volumes for small $n$ beyond three, and extending the analysis to combinations of constraints (e.g., regional minimum guarantees or multi-member districts). Applications range from legislative seat allocation and international treaty design to automated resource allocation systems that must satisfy fairness and minimal entitlement constraints. Further empirical and computational study will help translate the asymptotic insight provided here into concrete guidance for real-world apportionment decisions.

## Appendix A Comparison of Theoretical Results to Simulations

The following are the results of simulations and comparisons to theoretical values calculated using Theorems [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12) and [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22).

The python code used to sample quota violations is available on GitHub here: [https://github.com/TylerCWunder/Probability-of-Quota-Violations-in-Divisor-Apportionment-Methods-with-Nonzero-Allocations.git](https://github.com/TylerCWunder/Probability-of-Quota-Violations-in-Divisor-Apportionment-Methods-with-Nonzero-Allocations.git).

For the case where $(p_{1},p_{2},p_{3})=(1,x,y)$ are uniform on $\{1<x<y\}$ we compare a sample of 100,000 $(p_{1},p_{2},p_{3})=(1,x,y)$ where $x,y$ are both uniform random variables on $[1,1000000]$. By symmetry and as the range is large, one expects this sample to be comparable to the formula found in Theorem [5.12](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem12).

**Probability of Quota Violations Caused by Nonzero Allocation with $(1,x,y)$ uniform on $\{1<x<y\}$**

| Method             | $M$  | Theoretical Probability | Sample Probability | $95\%$ Confidence Interval |
| ------------------ | ---- | ----------------------- | ------------------ | -------------------------- |
| Huntington-Hill    | $10$ | $0.257$                 | $0.257$            | $(0.254,0.260)$            |
| Huntington-Hill    | $20$ | $0.229$                 | $0.228$            | $(0.225,0.230)$            |
| Huntington-Hill    | $50$ | $0.209$                 | $0.209$            | $(0.207,0.212)$            |
| Adams              | $10$ | $0.380$                 | $0.380$            | $(0.376,0.383)$            |
| Adams              | $20$ | $0.385$                 | $0.386$            | $(0.383,0.389)$            |
| Adams              | $50$ | $0.386$                 | $0.385$            | $(0.382,0.388)$            |
| Dean               | $10$ | $0.278$                 | $0.280$            | $(0.277,0.283)$            |
| Dean               | $20$ | $0.244$                 | $0.244$            | $(0.242,0.247)$            |
| Dean               | $50$ | $0.218$                 | $0.218$            | $(0.215,0.221)$            |
| Modified Jefferson | $10$ | $0.111$                 | $0.111$            | $(0.109,0.113)$            |
| Modified Jefferson | $20$ | $0.053$                 | $0.053$            | $(0.052,0.054)$            |
| Modified Jefferson | $50$ | $0.020$                 | $0.021$            | $(0.020,0.022)$            |
| Modified Webster   | $10$ | $0.235$                 | $0.236$            | $(0.234,0.239)$            |
| Modified Webster   | $20$ | $0.213$                 | $0.213$            | $(0.210,0.215)$            |
| Modified Webster   | $50$ | $0.201$                 | $0.202$            | $(0.199,0.204)$            |

For the case $(p_{1},p_{2},p_{3})$ are IID and $p_{i}\sim\exp(1)$, we compare a sample of 100,000 $(p_{1},p_{2},p_{3})$ to a theoretical probability calculated using Theorem [5.22](https://arxiv.org/html/2605.06556v1#S5.Thmtheorem22). Note that these are the same probabilities for $p_{i}\sim\exp(\lambda)$ for any $\lambda$ or $(p_{1},p_{2},p_{3})\sim\mathrm{Dir}(1,1,1)$.

**Probability of Quota Violations Caused by Nonzero Allocation with $(p_{1},p_{2},p_{3})$ IID and $p_{i}\sim\exp(1)$**

| Method             | $M$  | Theoretical Probability | Sample Probability | $95\%$ Confidence Interval |
| ------------------ | ---- | ----------------------- | ------------------ | -------------------------- |
| Huntington-Hill    | $5$  | $0.131$                 | $0.130$            | $(0.128,0.132)$            |
| Huntington-Hill    | $10$ | $0.049$                 | $0.049$            | $(0.048,0.051)$            |
| Huntington-Hill    | $15$ | $0.029$                 | $0.029$            | $(0.028,0.030)$            |
| Dean               | $5$  | $0.137$                 | $0.137$            | $(0.135,0.139)$            |
| Dean               | $10$ | $0.056$                 | $0.056$            | $(0.055,0.057)$            |
| Dean               | $15$ | $0.033$                 | $0.033$            | $(0.032,0.034)$            |
| Modified Jefferson | $5$  | $0.120$                 | $0.119$            | $(0.117,0.121)$            |
| Modified Jefferson | $10$ | $0.030$                 | $0.030$            | $(0.029,0.031)$            |
| Modified Jefferson | $15$ | $0.013$                 | $0.013$            | $(0.012,0.014)$            |
| Modified Webster   | $5$  | $0.126$                 | $0.125$            | $(0.123,0.127)$            |
| Modified Webster   | $10$ | $0.043$                 | $0.043$            | $(0.042,0.045)$            |
| Modified Webster   | $15$ | $0.025$                 | $0.025$            | $(0.024,0.026)$            |

## References (13 total, showing 13)

- \[1\] M. L. Balinski and H. P. Young (1974) On huntington methods of apportionment. SIAM Journal on Applied Mathematics 27 (4), pp. 606–610. [https://dx.doi.org/10.1137/0127061](https://dx.doi.org/10.1137/0127061) [https://www.jstor.org/stable/2100756](https://www.jstor.org/stable/2100756)

- \[2\] M. L. Balinski and H. P. Young (2001) Fair representation: meeting the ideal of one man, one vote. 2 edition, Brookings Institution Press, Washington, DC. [https://www.jstor.org/stable/10.7864/j.ctvcb59f6](https://www.jstor.org/stable/10.7864/j.ctvcb59f6)

- \[3\] M. Drton and U. Schwingenschlögl (2005) Asymptotic seat bias formulas. Metrika: International Journal for Theoretical and Applied Statistics 62 (1), pp. 23–31. [https://dx.doi.org/10.1007/s001840400352](https://dx.doi.org/10.1007/s001840400352) [https://link.springer.com/article/10.1007/s001840400352](https://link.springer.com/article/10.1007/s001840400352)

- \[4\] S. El-Helaly (2019) The mathematics of voting and apportionment: an introduction. Birkhäuser / Springer, Cham, Switzerland. [https://dx.doi.org/10.1007/978-3-030-14768-6](https://dx.doi.org/10.1007/978-3-030-14768-6) [https://link.springer.com/book/10.1007/978-3-030-14768-6](https://link.springer.com/book/10.1007/978-3-030-14768-6)

- \[5\] W. V. Gehrlein and D. Lepelley (2017) Elections, voting rules and paradoxical outcomes. Studies in Choice and Welfare, Springer International Publishing, Cham, Switzerland. [https://link.springer.com/book/10.1007/978-3-319-64659-6](https://link.springer.com/book/10.1007/978-3-319-64659-6) [https://dx.doi.org/10.1007/978-3-319-64659-6](https://dx.doi.org/10.1007/978-3-319-64659-6)

- \[6\] J. K. Hodge and R. E. Klima (2018) The mathematics of voting and elections: a hands-on approach. 2 edition, Mathematical World, Vol. 30, American Mathematical Society, Providence, RI. [https://dx.doi.org/10.1090/mawrld/030](https://dx.doi.org/10.1090/mawrld/030) [https://bookstore.ams.org/mawrld-30](https://bookstore.ams.org/mawrld-30)

- \[7\] E. V. Huntington (1921) A new method of apportionment of representatives. Quarterly Publications of the American Statistical Association 17 (133), pp. 859–870. [https://dx.doi.org/10.1080/01621459.1921.10502491](https://dx.doi.org/10.1080/01621459.1921.10502491) [https://www.jstor.org/stable/2965187](https://www.jstor.org/stable/2965187)

- \[8\] E. V. Huntington (1921) The mathematical theory of the apportionment of representatives. Proceedings of the National Academy of Sciences 7 (4), pp. 123–127. [https://dx.doi.org/10.1073/pnas.7.4.123](https://dx.doi.org/10.1073/pnas.7.4.123) [https://www.jstor.org/stable/84087](https://www.jstor.org/stable/84087)

- \[9\] T. Ichimori (2012) Relaxed divisor methods and their seat biases. Journal of the Operations Research Society of Japan 55 (1), pp. 63–72. [https://dx.doi.org/10.15807/jorsj.55.63](https://dx.doi.org/10.15807/jorsj.55.63) [https://www.jstage.jst.go.jp/article/jorsj/55/1/55_KJ00008017545/_article/-char/ja/](https://www.jstage.jst.go.jp/article/jorsj/55/1/55_KJ00008017545/_article/-char/ja/)

- \[10\] V. Pandit and J. Cutrone (2025) Evaluating fairness of voting systems: simulating violations of arrow’s conditions. Theory and Decision, pp. 1–21. [https://dx.doi.org/10.1007/s11238-025-10104-5](https://dx.doi.org/10.1007/s11238-025-10104-5) [https://doi.org/10.1007/s11238-025-10104-5](https://doi.org/10.1007/s11238-025-10104-5)

- \[11\] K. Schuster, F. Pukelsheim, M. Drton, and N. R. Draper (2003) Seat biases of apportionment methods for proportional representation. Electoral Studies 22 (4), pp. 651–676. [https://dx.doi.org/10.1016/S0261-3794%2802%2900027-6](https://dx.doi.org/10.1016/S0261-3794%2802%2900027-6)

- \[12\] U. Schwingenschlögl and M. Drton (2004) Seat allocation distributions and seat biases of stationary apportionment methods for proportional representation. Metrika: International Journal for Theoretical and Applied Statistics 60 (2), pp. 191–202. [https://dx.doi.org/10.1007/s001840400347](https://dx.doi.org/10.1007/s001840400347) [https://link.springer.com/article/10.1007/s001840400347](https://link.springer.com/article/10.1007/s001840400347)

- \[13\] T. C. Wunder and J. Cutrone (2026) Quantifying the balinski-young theorem: structure and probability of quota violations in divisor methods for three states (preprint). [https://arxiv.org/abs/2505.09100](https://arxiv.org/abs/2505.09100)
