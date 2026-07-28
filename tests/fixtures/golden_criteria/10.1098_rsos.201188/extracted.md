---
title: "Learning agents in Black–Scholes financial markets"
authors: "Vaidya, Tushar, Murguia, Carlos, Piliouras, Georgios"
journal: "Royal Society Open Science"
doi: "10.1098/rsos.201188"
published: "2020/10/01"
source: "royalsocietypublishing_html"
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 12269
---

# Learning agents in Black–Scholes financial markets

## Abstract

Black–Scholes (BS) is a remarkable quotation model for European option pricing in financial markets. Option prices are calculated using an analytical formula whose main inputs are strike (at which price to exercise) and volatility. The BS framework assumes that volatility remains constant across all strikes; however, in practice, it varies. How do traders come to learn these parameters? We introduce natural agent-based models, in which traders update their beliefs about the true implied volatility based on the opinions of other agents. We prove exponentially fast convergence of these opinion dynamics, using techniques from control theory and leader-follower models, thus providing a resolution between theory and market practices. We allow for two different models, one with feedback and one with an unknown leader.

## 1 Introduction

Econophysics divides into two paradigms. Statistical Econophysics relies on data, fitting certain power laws to existing asset prices at various time scales [1,2]. In statistical Econophysics, zero-intelligence agents have random interactions. Agents are homogeneous and have no learning ability. The central object of study is historical price data. The viewpoint is that interacting zero-intelligence traders’ actions are already incorporated into price fluctuations. The focus is on the macroscopic aggregation of interactions in the form of available data.

While this is an important area of research, agent-based Econophysics offers the opportunity to study the microscopic interactions in more detail, where agents are heterogeneous.

Our objective is to offer a cogent and clear motivation for agent-based Econophysics in the context of option volatilities, whereby learning and interaction are made explicit. To an outsider, it may seem that financial assets are observed at one price, decided by the market. In reality, prices fluctuate throughout the day and there is no equilibrium price: it is always in flux. Interaction between strategic traders and other players is embedded in all transactions and informational channels. Interaction is vital to understanding markets. The motivation for this paper was inspired by the works of Kirman [3] and Follmer et al. [4]. Rather than develop a thorough game theoretic or mean-field model, we advocate something in between. We aim to take a more nuanced view of agent-based Econophysics as espoused by Chakraborti et al. [5].

### 1.1 Our contribution

We introduce two different classes of learning models that converge to a consensus. Our interest is not in equilibrium but what process leads to it [6–8]. The first introduces a feedback mechanism (§[4.1](#s4a), theorem 4.1) where agents who are off the true ‘hidden’ volatility parameter feel a slight (even infinitesimally so) pull towards it along with the all the other ‘random’ chatter of the market. This model captures the setting where traders have access to an alternative trading venue or an information source provided by brokers and private message boards. The second model incorporates a market leader (e.g. Goldman Sachs) that is confident in its own internal metrics or is privy to client flow (private information) and does not give any weight to outside opinions (§[4.3](#s4c), theorem 4.4). Proving the convergence results (as well as establishing the exponentially fast convergence rates) requires tools from discrete dynamical systems. We showcase as well as complement our theoretical results with experiments (e.g. figure 2a–d), which for example show that if we move away from our models, convergence is no longer guaranteed.

![Figure 2](https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/7/10/10.1098_rsos.201188/9/rsos201188f02.png?Expires=1781820291&Signature=HiZ1sO8sCDeLnYS2N-MIJm0aM~T5tBHlFi3Id8ddnfchNjrzdc1HrEZ8SeZx36s3nFKxGpaTvOW4pqMoxSGC5qzVwU4rMiS9PTblW4a3BFoizFcwkIZzPUzoshAW0RWvDEaNtb9UYu9GbsFX567UgClXEywwi0qB~siP2zPIxy2uS1mLID~P~wRLs28wyzxZQy5cB2AoHAP6zuqRalQ1Zm83z85a6kkMITvV2WPRQg4UfWx-GvlT15zRrl8E-o5JaIf9NnA5WMNDAt5tE4tFocM2Zb88TmYL2G13c8FCTwyOua0n~XCchKKM~Qj9viGa-JSe3LUTCUaOsM~kvEWfng__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 2.** Evolution of the agents’ dynamics (4.2): (a) without learning, (b) with learning and εi satisfying the conditions of theorem 4.1, (c) with learning and εi not satisfying the conditions of theorem 4.1, and (d) evolution of the agents’ dynamics with a leader (4.5).

We formalize the multi-dimensional analogues of our two models by using Kronecker products (§[5](#s5), theorems 5.1 and 5.3). Thus, our models show how a volatility curve could function as a global attractor given adaptive agents. We conclude the paper by discussing future work and connections to other fields.

## 2 Derivatives and social learning

Before discussing the main models of this paper, we give an overview of options markets and trading. We then motivate our framework and explain why certain social learning models are appropriate.

### 2.1 Trading

Most trading is done electronically. To be dominant, firms now invest huge sums in technology to get an edge. For futures trading, speed is vital to profits. Trading complex derivatives requires not only speed but huge amounts of investment in quantitative models. This, in turn, feeds the need for mathematicians, computer scientists and engineers. Increasingly, over the last two decades, the way trading is conducted has also seen drastic changes. Electronification of the markets has affected both instruments traded on and off exchange. Algorithmic trading drives not only plain vanilla instruments like stocks and futures but also derivatives [9–11]. Furthermore, the distinction between stock exchanges and over-the-counter (OTC) markets is not as clear as it once was [12]. In OTC markets, trading is between two counterparties and there is no centralized marketplace. Increasingly, over the last decade, there has been a regulatory push to make OTC markets more exchange-like. In OTC markets, participants may see what their competitors are quoting for a particular security, but volume and the actual price transacted remain the privy of the bilateral counterparties. In some quarters, OTC markets are usually referred to as being quote-driven or truly dark markets [13]. Regulation in the USA and European Union has resulted in fragmented exchange-based trading but centralization of opaque OTC markets.

### 2.2 Options markets

Derivative contracts are actively traded across the world’s financial markets with a total estimate value in the trillions of dollars. To get an intuitive understanding of the setting and the issues at hand, let us consider the prototypical example of European options.

A European option is the right to buy or sell an underlying asset at some point in the future at a fixed price, also known as the strike. A call option gives the right to buy an asset and a put option gives the right to sell an asset at the agreed price. On the opposite side of the buyer is the seller who has relinquished his control of exercise. Buyers of puts and calls can exercise the right to buy or sell. Sellers of options have to fulfil obligations when exercised against. The payoff of a buyer of a call option with stock price ST at expiry time T and exercise price K is max{ST − K, 0}, whereas for a put option is max{K − ST, 0}.

To get a price, we input the current stock price S0 (e.g. $101), the exercise price K (e.g. $ 90), the expiry T (e.g. three months from today) and the volatility σ in the Black–Scholes (BS) formula [14–16]:
Equation: $\text{price} = \text{BS}(S_{0},K,T,\sigma).$
Volatility, which captures the beliefs about how turbulent the stock price will be, is left up to the market. This parameter is so important that in practice the market trades European calls and puts by quoting volatilities.1

Options can be struck at different strike prices on the same asset (e.g. K = $90, $ 75, $60). If the underlying asset and the time to exercise T (e.g. three months) are the same, one would expect the volatility to be the same at different strikes. In practice, however, the market after the 1987 crash has evolved to exhibit different volatilities. This rather strange phenomenon is referred to as the smile, or smirk (figure 1). Depending on the market, these smirks can be more or less pronounced. For instance, equity markets display a strong skew or smirk. A symmetric smile is more common in foreign exchange options markets. An excellent introduction to volatility smiles is given in [17].

![Figure 1](https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/7/10/10.1098_rsos.201188/9/rsos201188f01.png?Expires=1781820291&Signature=AMRi4Y5iy~RBoI9zMPnj4Shjw7h8HzaWbeqs4Jxd05Ns3L3MpXUu0Khkvtx9unplAZny1KP2E63Vsw6ENxBbabUWZhGRHR~8ICm~fPN98-3U7O9hSKQI3Yfu62yjPg~7fYp9NwZOP2Gm6fuvME5uOABnLdjokzPDfTZEXruN2wIAmwS5EHTlMouoK5~0Rt1KKfOKwneQoVZp~slW8auUTZJQFy74fpDx7T5cdHQo16rV8B5YU6IezY3elKYIaKT-hfgym-JTwRxbm40C4F-THCn2QOIXGhG7klZA7K9Zlt9sdSNJ0qAGjo7vP2nmMMmA1Js0C~SkWd3nGu-E0LzayQ__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 1.** (a) A typical implied volatility smile for varying strikes K divided by fixed spot price. Moneyness is K/S0. ATM denotes At-The-Money where K equals S0. (b) Consensus occurs as all traders’ opinions of the implied volatility converge, round by round, to a distinct value for varying strikes.

How does the market decide what the quoted volatility should be (e.g. for a stock index three months from now)? This is a critical but not well-understood question. This is exactly what we aim to study by introducing models of learning agents who update their beliefs about the volatility. Agent-based models on volatility–smile interaction and formation have not been thoroughly addressed in finance or Econophysics. They remain a challenge [18]. Previous attempts have been made, but the focus has never been on the mathematical or specific nature of interaction [19,20]. Furthermore, our work takes into account the physicality of how trading occurs. An alternative perspective is offered in [21,22], again though the nature of interaction is missing. Nevertheless, these early attempts offer a good indication that at least the problem has garnered significant interest in different disciplines.

### 2.3 Econophysics

The challenge for physicists is not to force existing physics-based models on human behaviour but rather develop new models [23–25]. To go from local microscopic interactions to global macroscopic behaviour is not an easy task [26,27]. In fact, the choice of models seems infinite. There are a plethora of agent-based models [5,25,28]. Which one is correct? And, moreover, which type of social learning is representative of financial markets trading? LeBaron provides an early guide [29]. Agent-based models were proclaimed as the future for Econophysics [30,31]. While development in this area has been steady, the problem of the emergence of volatility smiles remains unresolved. The volatility smile is an active and vigorous area of research in the mathematical finance community [32–34]. Many models postulate a stochastic process for the underlying stock and volatility combined.

### 2.4 Knightian uncertainty

Risk and uncertainty are two different concepts [35–37]. Risky assets are those on which the probabilities of random events are well defined and known. For instance, suppose we observe historical data of a stock price. Are we confident to claim we know the distribution of the stock’s returns? If we are, then the stock is considered risky. Its risk is quantifiable. However, if we were unsure of even the correct probability measure, then we would be faced with uncertainty. In a sense, this captures the essence of financial markets. Traders and players use different probability measures when trading and quoting options. No single measure dominates. In fact, there are many models that are consistent with the observation of a finite number of strike volatilities in the market [38–41]. In practice, the choice of a correct probability measure such that a derivative contract is priced correctly is a subjective and quantitative exercise. In any case, no perfect model exists [42–46]. As a result, participants in financial markets are free to choose whichever probability model they calibrate to market data [47–49].

The problem with economics-based models and those in mathematical finance literature is that many times the analysis is centred on a representative agent. In the case of risk and uncertainty, the choice of pricing a derivative contract reduces to choosing a correct equivalent martingale measure under which a derivative claim is replicable. For market-makers and dealers, the choice of models is vast. Each player has to make a choice and inevitably no two institutions will use the same models with the same parameters. In this case, it is remarkable that the market will aggregate the diverse beliefs to arrive at a consensus smile. At the microscopic level, though, the dealers are observing one another’s updates. Hence, our model can be seen as a meta-opinion dynamics framework built upon the individual choices of the dealers.

### 2.5 Non-Bayesian financial markets

In financial markets, updating occurs at high frequency across geographical locations [50,51]. Agents move simultaneously: cancellations are the norm [52–54]. In practical terms, sequential Bayesian learning models do not seem appropriate [55,56]. Bayesian observational learning examples include [57–59]. These models are sequential in nature. They study herd behaviour. As time passes, a player in turn observes the actions of previous agents and receives a private signal. Each agent has a one-off decision when she updates her posterior probability and takes an action. In some instances, the nth agent may reach the truth as n → ∞.

In DeGroot learning, myopic updating occurs in each iteration. Agents in our set-up have fixed weights but update their responses until consensus is reached. Recently, there have been some experimental papers on the evidence of DeGroot updating [60,61]. Repeated averaging models are our base precisely because they capture the nature of interaction and learning in financial markets so compactly. Players can observe previous choices but not the payoffs of their competitors. A more in-depth discussion of learning in games would take us further away from our goal of studying the mathematical nature of interaction. The reader can consult [62,63] for a game-theoretic perspective.

## 3 Model description

In mathematical opinion dynamic models, agents take views of other agents into account before arriving at their own updated estimate. Agents can observe other agents’ previous signals.

DeGroot [64] was one of the early developers of such observational learning dynamics. While simple, these models allow us to examine convergence to consensus. In a sense, these types of models are called naive models, as agents can recall perfectly what the other players submitted in the previous round. See the survey papers [65–68].

### 3.1 Volatility basics

Agents have an initial opinion of the implied volatility, which they update after taking into account volatilities of other agents. A feedback mechanism aids the agents in arriving at the true volatility parameter.

At all times, the focus is on a static picture of the volatility smile. Within this static framework agents are updating their opinion of the true implied volatility. This updating occurs in a high-frequency sense. In an exchange setting, one can think of all bids and offers as visible to agents. The agents initially are unsure of the true value of the implied volatility, but by learning—and feedback—reach consensus on the true parameter. Our first attempt is a naive learning model common in social networks. Learning occurs between trading times. Therefore, our implicit assumption is that no transactions occur while traders are adjusting and learning each other’s quotes.

This rather peculiar feature is market practice. Trading happens at longer intervals than quote updating. This is as true for high-frequency trading of stocks as it is for options markets. Quotes and prices—or rather vols—are changing more frequently than actual transactions.

Each dollar value of an option corresponds to an implied volatility parameter σ(K, T) ∈ (0, 1) that depends on strike and expiry. Implied volatility is quoted in percentage terms.

#### Assumption 3.1.

We have three types of players: agents/traders, brokers and leaders. Brokers give feedback to the traders. The ability of agents to determine this feedback is their learning ability. Leaders are unknown and do not give feedback but their quotes are visible.

### 3.2 Naive opinion dynamics

A first approach towards opinion dynamics is to assume each agent takes a weighted average of other agents’ opinions and updates his own estimate of the volatility parameter for the next period. At time t, the opinion $x_{t}^{i} \in \mathbb{R}$ of the i-th agent is given by
Equation 3.1: $x_{t}^{i} = \sum\limits_{\, j = 1}^{n}a_{ij}x_{t - 1}^{j},\quad t \in \mathbb{N},$
where $x_{t - 1}^{j} \in \mathbb{R}$ is the opinion of agent j at time (t − 1) and aij ≥ 0 denotes the opinion weights for the n players with $\sum\limits_{\, j = 1}^{n}a_{ij} = 1$ and aii > 0 for all 1 ≤ i ≤ n. Define $X_{t}:={(x_{t}^{1},\ldots,x_{t}^{n})}^{\top}$, then the opinion dynamics of the n agents can be written in matrix form as follows:
Equation 3.2: $X_{t} = AX_{t - 1},$
where $A:=a_{ij} \in \mathbb{R}^{n \times n}$ is a row-stochastic matrix.

#### Definition 3.2 (consensus).

The n agents (3.2) are said to reach consensus if for any fixed initial condition $X_{1} \in \mathbb{R}^{n}$, $|x_{t}^{i} - x_{t}^{j}|\rightarrow 0$ as t → ∞ for all i, j ∈ {1, … n}.

#### Definition 3.3 (consensus to a point).

The n agents (3.2) are said to reach consensus to a point if for any initial condition $X_{1} \in \mathbb{R}^{n}$, lim t→∞Xt = c1n, where 1n denotes the n × 1 vector composed of only ones and $c \in \mathbb{R}$. The constant c is often referred to as the consensus value.

For the opinion dynamics (3.2), we introduce the following result by [64] (see also [69] for definitions).

#### Proposition 3.4.

Consider the opinion dynamics in equation (3.2). If A is aperiodic and irreducible, then for any initial condition $X_{1} \in \mathbb{R}^{n}$ consensus to a point is reached. The consensus value c depends on both the matrix A and the initial condition X1.

#### Remark 3.5.

Proposition 3.4 implies that if the row stochastic opinion matrix A is aperiodic and irreducible, then all the agents converge to some consensus value c. However, since c depends on the unknown initial opinion X1, the consensus value c is unknown and, in general, different from the true volatility σ(K, T). We wish to alleviate this and thus introduce two novel models.

## 4 Consensus (scalar agent dynamics)

In this section, we assume that the agents are able to learn how far off they are from the true volatility by informational channels in the marketplace. There are many avenues, platforms and private online chat rooms that provide quotes for option prices; some of these are stale and some are fresh. The agents’ learning ability determines the quality of the feedback from all these sources. In reality, options are not traded on one exchange or platform. There are multiple venues and, though there might be a dominant marketplace, the same instruments can be traded across different venues and locations. We aggregate all of this information in the form of feedback with learning ability. If agents are fast learners, they adjust their volatility estimates quickly.

### 4.1 Consensus with feedback

We model this feedback by introducing an extra driving term into the opinion dynamics (3.1). An early model developed by Mizuno et al. [70] shares some similarities to ours. Traders use feedback from past behaviour. Our model is a discrete autoregressive process but the focus is on learning in high-frequency time [71]. Furthermore, our model formalizes this in a more social and dynamical set-up. In particular, we feed back the difference between the agents’ opinion and the true volatility σ(K, T) scaled by a learning coefficient εi ∈ (0, 1). We assume that σ(K, T) is invariant, i.e. for some fixed $\overline{\sigma} \in(0,1)$, $\sigma(K,T) = \overline{\sigma}$ for some fixed strike K and maturity M. Then the new model is written as follows:
Equation 4.1: $x_{t}^{i} = \sum\limits_{\, j = 1}^{n}a_{ij}x_{t - 1}^{j} + \epsilon_{i}(\overline{\sigma} - x_{t - 1}^{i}),$
or in matrix form
Equation 4.2: $X_{t} = AX_{t - 1} + \mathcal{E}(\overline{\sigma}1_{n} - X_{t - 1}),$
where $\mathcal{E}:=\text{diag}(\epsilon_{1},\ldots,\epsilon_{n})$. Then we have the following result.

#### Theorem 4.1.

Consider the agent dynamics in (4.2) and assume that εi ∈ (0, aii), i = {1, …, n}. Then consensus to $\overline{\sigma}$ is reached, i.e. $\lim\limits_{t\rightarrow\infty}X_{t} = \overline{\sigma}1_{n}$.

#### Proof.

It is easy to verify that the solution Xt of the difference equation (4.2) is given by
Equation 4.3: $X_{t + 1} = {(A - \mathcal{E})}^{t}X_{1} + \sum\limits_{\, j = 0}^{t - 1}{(A - \mathcal{E})}^{j}\mathcal{E}\overline{\sigma}1_{n},\, t > 1.$
By the Gershgorin circle theorem, the spectral radius $\rho(A - \mathcal{E}) < 1$ for all i, εi < aii. It follows that $\sum\limits_{\, j = 0}^{\infty}{(A - \mathcal{E})}^{j}\mathcal{E}\overline{\sigma}1_{n} = {(I_{n} - A + \mathcal{E})}^{- 1}\mathcal{E}\overline{\sigma}1_{n}$, where In denotes the identity matrix of dimension n, and $\lim\limits_{t\rightarrow\infty}{(A - \mathcal{E})}^{t} = 0$, see [72]. As the matrix A is row stochastic, (I − A)1n = 0n, where 0n denotes the n × 1 vector composed of only zeros. Hence, we can write $\mathcal{E}1_{n} = (I_{n} - A)1_{n} + \mathcal{E}1_{n}$, and consequently $1_{n} = {(I_{n} - A + \mathcal{E})}^{- 1}\mathcal{E}1_{n}$. It follows that
Equation: $\begin{matrix} {\lim\limits_{t\rightarrow\infty}X_{t + 1}} & {= \lim\limits_{t\rightarrow\infty}{(A - \mathcal{E})}^{t}X_{1} + \sum\limits_{\, j = 0}^{\infty}{(A - \mathcal{E})}^{j}\mathcal{E}\overline{\sigma}1_{n}} \\ \, & {= 0_{n} + {(I_{n} - A + \mathcal{E})}^{- 1}\mathcal{E}1_{n}\overline{\sigma} = 1_{n}\overline{\sigma},} \end{matrix}$
and the assertion follows. ▪

#### Corollary 4.2.

Consensus to $\overline{\sigma}$ is reached exponentially with convergence rate $\parallel A - \mathcal{E} \parallel_{\infty}$, i.e. $\max\limits_{i}\{\parallel x_{t}^{i} - \overline{\sigma} \parallel\} \leq \parallel A - \mathcal{E} \parallel_{\infty}^{t - 1} \parallel X_{1} - \overline{\sigma}1_{n} \parallel_{\infty}$, i ∈ {1, …, n}, where $\parallel \cdot \parallel_{\infty}$ denotes the matrix norm induced by the vector infinity norm.

#### Proof.

Define the error sequence $E_{t - 1}:=(X_{t - 1} - \overline{\sigma}1_{n}) \in \mathbb{R}$ n. Then, from (4.2), the following is satisfied:
Equation: $\begin{matrix} E_{t} & {= X_{t} - \overline{\sigma}1_{n}} \\ \, & {= AX_{t - 1} + \mathcal{E}(\overline{\sigma}1_{n} - X_{t - 1}) - \overline{\sigma}1_{n}} \\ \, & {= A(E_{t - 1} + \overline{\sigma}1_{n}) + \mathcal{E}(\overline{\sigma}1_{n} - (E_{t - 1} + \overline{\sigma}1_{n})) - \overline{\sigma}1_{n}} \\ \, & {= (A - \mathcal{E})E_{t - 1} + \overline{\sigma}(A - I_{n})1_{n}} \\ \, & {= (A - \mathcal{E})E_{t - 1}.} \end{matrix}$
The last equality in the above expression follows from the fact that (A − In)1n = 0, because A is a stochastic matrix. The solution Et of the above difference equation is given by $E_{t} = {(A - \mathcal{E})}^{t - 1}E_{1}$, where $E_{1} = X_{1} - \overline{\sigma}1_{n}$ denotes the initial error. Let $\parallel E_{t} \parallel_{\infty} = \max\limits_{i}(\parallel e_{t}^{i} \parallel)$, i ∈ {1, …, n}, where $E_{t} = {(e_{t}^{1},\ldots,e_{t}^{n})}^{T}$. Note that exponential convergence of $\parallel E_{t} \parallel_{\infty}$ implies exponential convergence of Et itself. With the solution $E_{t} = {(A - \mathcal{E})}^{t - 1}E_{1}$, the following can be written:
Equation: $\begin{matrix} {\parallel E_{t} \parallel_{\infty}} & {= \parallel {(A - \mathcal{E})}^{t - 1}E_{1} \parallel_{\infty}} \\ \, & {\leq \parallel(A - \mathcal{E}) \parallel_{\infty}^{t - 1} \parallel E_{1} \parallel_{\infty},} \end{matrix}$
where $\parallel(A - \mathcal{E}) \parallel_{\infty}$ denotes the matrix norm of $(A - \mathcal{E})$ induced by the vector infinity norm [72]. The inequality $\parallel E_{t} \parallel_{\infty} \leq \parallel(A - \mathcal{E}) \parallel_{\infty}^{t - 1} \parallel E_{1} \parallel_{\infty}$ implies exponential convergence if $\parallel(A - \mathcal{E}) \parallel_{\infty} < 1$. Because A = aij and $\mathcal{E} = \text{diag}(\epsilon_{1},\ldots,\epsilon_{n})$, we can compute $\parallel(A - \mathcal{E}) \parallel_{\infty}$ as $\parallel(A - \mathcal{E}) \parallel_{\infty} = \max\limits_{i}(\sum\limits_{\, j = 1,j \neq i}^{n}\parallel a_{ij} \parallel + \parallel a_{i} - \epsilon_{i} \parallel)$, i ∈ {1, …, n}. The matrix A is stochastic, which implies aij ≥ 0 and $\sum\limits_{i = 1}^{n}\parallel a_{ij} \parallel = 1$. Therefore, under the conditions of theorem 4.1 (i.e. εi ∈ (0, aii)), $\parallel(A - \mathcal{E}) \parallel_{\infty} = \max\limits_{i}(\sum\limits_{\, j = 1,j \neq i}^{n}\parallel a_{ij} \parallel + \parallel a_{i} - \epsilon_{i} \parallel) < 1$ and hence exponential convergence of the consensus error Et can be deduced with rate given by $\parallel(A - \mathcal{E}) \parallel_{\infty} = \max\limits_{i}(\sum\limits_{\, j = 1,j \neq i}^{n}\parallel a_{ij} \parallel + \parallel a_{i} - \epsilon_{i} \parallel)$. ▪

### 4.2 Random case

Under suitable random conditions for the trust matrix A and $\mathcal{E}$, we can still have consensus. In this case, the learning rates and weights are independently and identically distributed from each iteration. However, we need a condition to ensure convergence, namely that on average the learning rates are less than the self-belief condition. Since this is only in expectation, a probabilistic statement, there is some leeway on the learning rates being strictly less than self-belief aii at time t.

#### Theorem 4.3.

Consider the updating rule
Equation 4.4: $X_{t} = A_{t}X_{t - 1} + \mathcal{E}_{t}(\overline{\sigma}1_{n} - X_{t - 1}),$
where $A_t$ and $\mathcal{E}_{t}$ are independent and identically distributed (iid). Furthermore, suppose
Equation: $- \infty < \mathbb{E}\lbrack\log \parallel A_{t} - \mathcal{E}_{t} \parallel_{\infty}\rbrack < 0\,\text{and } \parallel X_{0} - \overline{\sigma} \parallel < \infty,$
then consensus to $\overline{\sigma}$ is reached, i.e. $\lim\limits_{t\rightarrow\infty}X_{t} = \overline{\sigma}1_{n}$.

#### Proof.

We rewrite the above iteration, subtracting $\overline{\sigma}$ from both sides and dropping the one vector notation as the context is clear
Equation: $\begin{matrix} {X_{t} - \overline{\sigma}} & {= A_{t}X_{t - 1} + \mathcal{E}_{t}(\overline{\sigma} - X_{t - 1}) - \overline{\sigma},} \\ {X_{t} - \overline{\sigma}} & {= A_{t}X_{t - 1} - A_{t}\overline{\sigma} + \mathcal{E}_{t}\overline{\sigma} - \mathcal{E}_{t}X_{t - 1},} \\ {X_{t} - \overline{\sigma}} & {= (A_{t} - \mathcal{E}_{t})(X_{t - 1} - \overline{\sigma}),} \\ Y_{t} & {= (A_{t} - \mathcal{E}_{t})Y_{t - 1}} \\ {{and}\qquad\qquad Y_{t}} & {= B_{t}Y_{t - 1},} \end{matrix}$
where $Y_{t} = X_{t} - \overline{\sigma}$ and $B_{t} = A_{t} - \mathcal{E}_{t}$. We want to show Yt → 0. To this end, iterating the above recursion gives us
Equation: $Y_{t} = \underset{{iid}\,{matrices}}{\underbrace{B_{t}B_{t - 1}\cdots B_{1}}}Y_{0}.$
Taking norms on the above equation results in the following inequalities, understanding that we mean the $\parallel \cdot \parallel_{\infty}$ norm:
Equation: $\begin{matrix} {\parallel Y_{t} \parallel} & {= \parallel B_{t}B_{t - 1}\cdots B_{1}Y_{0} \parallel,} \\ {\parallel Y_{t} \parallel} & {\leq \parallel B_{t} \parallel \parallel B_{t - 1} \parallel \cdots \parallel B_{1} \parallel \parallel Y_{0} \parallel,} \\ {\log \parallel Y_{t} \parallel} & {\leq \log(\parallel B_{t} \parallel \parallel B_{t - 1} \parallel \cdots \parallel B_{1} \parallel \parallel Y_{0} \parallel),} \\ {\log \parallel Y_{t} \parallel} & {\leq \log \parallel B_{t} \parallel + \log \parallel B_{t - 1} \parallel + \cdots + \log \parallel B_{1} \parallel + \log \parallel Y_{0} \parallel} \\ {{and}\qquad\qquad \parallel Y_{t} \parallel} & {\leq \exp^{t\,\frac{\sum\limits_{k = 1}^{t}\log \parallel B_{k} \parallel}{t}} \parallel Y_{0} \parallel.} \end{matrix}$
The first inequality follows by sub-multiplicative property of matrix norms. Moreover, by the law of large numbers $\frac{1}{t}\sum\limits_{k = 1}^{t}\log \parallel B_{k} \parallel_{\infty}\longrightarrow\mathbb{E}\lbrack\log \parallel A_{t} - \mathcal{E}_{t} \parallel_{\infty}\rbrack$, which is negative by assumption. So the exponent ensures that, as the initial opinion $\parallel Y_{0} \parallel_{\infty} < \infty$ is finite,
Equation: $\lim\limits_{t\rightarrow\infty} \parallel Y_{t} \parallel_{\infty} = 0.$
Consequently, $Y_{t}\longrightarrow 0$ and every agent reaches consensus. ▪

Note we do not require the stronger condition that $\log \parallel A_{t} - \mathcal{E}_{t} \parallel_{\infty} < 0,$ for all t. Unlike the deterministic case, the random case allows considerable flexibility. Neither self-belief aii > 0 nor positive learning εi is required for all times. However, there must be some interaction and learning for beliefs to converge. As matrix products do not commute, if we were to follow the full expansion of the recursion in any of the dynamics, the result would be long, unwieldy matrix products. Random matrix products and dynamics are an active area of research not only in mathematics but also in physics and control theory [73–78]. While the random case is certainly interesting, in this article our focus is on the first steps of modelling interaction and learning dynamics.

### 4.3 Consensus with an unknown leader

One criticism of model (4.2) is that feedback, even if it is not perfect, has to be learned. In practice, there might not be a helpful mechanism that provides feedback. An alternative is to have an unknown leader embedded in the set of traders. The agents are unsure who the leader is but by taking averages of other traders, they all arrive at the opinion of the leader. In Markov chain theory, such behaviour is called an absorbing state. The leader guides the system to the true value. We assume that the identity of the leader is unknown to all agents.

Without loss of generality, we assume that the first agent (with corresponding opinion $x_{t}^{1}$) is the leader; it follows that $x_{1}^{1} = \overline{\sigma}$, a1i = 0, i ∈ {2, …, n}, and a11 = 1. Then in this configuration, the opinion dynamics is given by
Equation 4.5: $X_{t} = AX_{t - 1},\quad A = \begin{pmatrix} 1 & 0 & \ldots & 0 \\ a_{21} & a_{22} & \ldots & a_{2n} \\ \vdots & \vdots & \ldots & \vdots \\ a_{n1} & a_{n2} & \ldots & a_{nn} \end{pmatrix}\operatorname{=:}\begin{pmatrix} 1 & 0 \\ \ast & \overset{\sim}{A} \end{pmatrix},$
with aij ≥ 0, $\sum\limits_{\, j = 1}^{n}a_{ij} = 1$, aii > 0 for all 1 ≤ i ≤ n, and for at least one i ≥ 2, $\sum\limits_{\, j = 2}^{n}a_{ij} < 1$.

#### Theorem 4.4.

Consider the opinion dynamics in (4.5) and assume that the matrix $\overset{\sim}{A}$ is substochastic and irreducible. It holds that $\lim\limits_{t\rightarrow\infty}X_{t} = \overline{\sigma}1_{n}$, i.e. consensus to $\overline{\sigma}$ is reached.

#### Proof.

Define the invertible matrix $M \in \mathbb{R}^{n \times n}$
Equation: $M:=\begin{pmatrix} 1 & \, & 0 \\ 1_{n - 1} & \, & {- I_{n - 1}} \end{pmatrix}.$
Introduce the set of coordinates ${\overset{\sim}{X}}_{t - 1}:=MX_{t - 1}$. Note that ${\overset{\sim}{x}}_{t - 1}^{1} = x_{t - 1}^{1}$, ${\overset{\sim}{x}}_{t - 1}^{2} = x_{t - 1}^{1} - x_{t - 1}^{2},\ldots,{\overset{\sim}{x}}_{t - 1}^{n} = x_{t - 1}^{1} - x_{t - 1}^{n}$. Hence, if the error vector $e_{t - 1}:={({\overset{\sim}{x}}_{t - 1}^{2},\ldots,{\overset{\sim}{x}}_{t - 1}^{n})}^{\top} = 0_{n - 1}$, then consensus to $x_{t}^{1} = \overline{\sigma}$ is reached. Note that
Equation: $MAM^{- 1} = \begin{pmatrix} 1 & \, & \ast \\ 0 & \, & \overset{\sim}{A} \end{pmatrix},$
where 0 denotes the zero vector of appropriate dimensions and $\overset{\sim}{A}$ as defined in (4.5). By construction, ${\overset{\sim}{X}}_{t - 1}:=MX_{t - 1}\rightarrow{\overset{\sim}{X}}_{t} = MX_{t} = MAX_{t - 1} = MAM^{- 1}{\overset{\sim}{X}}_{t - 1}$; hence, the consensus error et satisfies the following difference equation
Equation 4.6: ${\overset{\sim}{X}}_{t} = MAM^{- 1}{\overset{\sim}{X}}_{t - 1} = \begin{pmatrix} 1 & \, & \ast \\ 0 & \, & \overset{\sim}{A} \end{pmatrix}{\overset{\sim}{X}}_{t - 1}; e_{t} = \overset{\sim}{A}e_{t - 1},$
and the solution of et is then given by $e_{t} = {\overset{\sim}{A}}^{t}e_{1}$.

Because for at least one i, $\sum\limits_{\, j = 2}^{n}a_{ij} < 1$ and $\overset{\sim}{A}$ is substochastic and irreducible, the spectral radius $\rho(\overset{\sim}{A}) < 1$, see lemma 6.28 in [69]; it follows that $\lim\limits_{t\rightarrow\infty}{\overset{\sim}{A}}^{t} = 0$. Therefore, lim t→∞et = 0 and the assertion follows. ▪

#### Corollary 4.5.

Let $\parallel \cdot \parallel_{\ast}$ denote some matrix norm such that $\parallel \overset{\sim}{A} \parallel_{\ast} < 1$ (such a norm always exists because $\rho(\overset{\sim}{A}) < 1$ under the conditions of theorem 4.4). Then consensus to $\overline{\sigma}$ is reached exponentially with the convergence rate given by $\parallel \overset{\sim}{A} \parallel_{\ast}$, i.e. $\max\limits_{i}\{\parallel x_{t}^{i} - \overline{\sigma} \parallel\} \leq C \parallel \overset{\sim}{A} \parallel_{\ast}^{t - 1} \parallel X_{1} - \overline{\sigma}1_{n} \parallel_{\infty}$, for i ∈ {1, …, n} and some positive constant $C \in \mathbb{R}_{> 0}$.

#### Proof.

See lemma 5.6.10 in [72] on how to construct such a $\parallel \cdot \parallel_{\ast}$. Now consider the consensus error et defined in the proof of theorem 4.4, which evolves according to the difference equation (4.6). It follows that $e_{t} = {\overset{\sim}{A}}^{t - 1}e_{1}$, where e1 denotes the initial consensus error. Under the assumptions of theorem 4.4, $\rho(\overset{\sim}{A}) < 1$. By lemma 5.6.10 in [72], $\rho(\overset{\sim}{A}) < 1$ implies that there exists some matrix norm, say $\parallel \cdot \parallel_{\ast}$, such that $\parallel \overset{\sim}{A} \parallel_{\ast} < 1$. We restate the error with norms and obtain $\parallel e_{t} \parallel_{\infty} \leq \parallel \overset{\sim}{A} \parallel_{\infty}^{t - 1} \parallel e_{1} \parallel_{\infty}$. Because all norms are equivalent in finite dimensional vector spaces (see ch. 5 in [72]), $\parallel e_{t} \parallel_{\infty} \leq \parallel \overset{\sim}{A} \parallel_{\infty}^{t - 1} \parallel e_{1} \parallel_{\infty}\Rightarrow$ $\parallel e_{t} \parallel_{\infty} \leq C \parallel \overset{\sim}{A} \parallel_{\ast}^{t - 1} \parallel e_{1} \parallel_{\infty}$ for some positive constant $C \in \mathbb{R}_{> 0}$. As $\parallel \overset{\sim}{A} \parallel_{\ast} < 1$, the norm of the consensus error $\parallel e_{t} \parallel_{\infty}$ converges to zero exponentially with rate $\parallel \overset{\sim}{A} \parallel_{\ast}$. ▪

## 5 Consensus (vectored agent dynamics)

In this section, we suppose that agents have beliefs over a range of strikes. Thus, each agent’s opinion of the volatility curve is a vector with each entry corresponding to a particular strike. Typically, in markets, options are quoted for At-The-Money (ATM) K = S0 and for two further strikes left of and right of the ATM level. Here, we examine the case of k strikes and n agents, i.e. each agent i now has k quotes for k different moneyness levels. In this configuration, the true volatility is $\overline{\sigma}:={\lbrack\sigma_{1},\ldots,\sigma_{k}\rbrack}^{\top} \in \mathbb{R}^{k}$. See figure 1b.

### 5.1 Consensus with feedback

Again, we assume that each agent takes a weighted average of other agents’ opinions and updates his volatility estimate vector for the next period. At time t, the opinion $x_{t}^{i} \in \mathbb{R}^{k}$ of the i-th agent is given by
Equation 5.1: $x_{t}^{i} = \sum\limits_{\, j = 1}^{n}a_{ij}x_{t - 1}^{j} + \epsilon_{i}(\overline{\sigma} - x_{t - 1}^{i}),\, t \in \mathbb{N},$
where εi ∈ (0, 1) denotes the learning coefficient of agent i, $x_{t - 1}^{j} \in \mathbb{R}^{k}$ is the opinion of agent j at time (t − 1), and aij ≥ 0 denotes the opinion weights for the n agents with $\sum\limits_{\, j = 1}^{n}a_{ij} = 1$ and aii > 0 for all 1 ≤ i ≤ n. In this case, the stacked vector of opinions is $X_{t}:={(x_{t}^{1},\ldots,x_{t}^{n})}^{\top}$, $X_{t} \in \mathbb{R}^{kn}$. The opinion dynamics of the n agents can then be written in matrix form as follows:
Equation 5.2: $X_{t} = (A \otimes I_{k})X_{t - 1} + (\mathcal{E} \otimes I_{k})(1_{n} \otimes \overline{\sigma} - X_{t - 1}),$
where $A = a_{ij} \in \mathbb{R}^{n \times n}$ is a row-stochastic matrix, $\mathcal{E} = \text{diag}(\epsilon_{1},\ldots,\epsilon_{n})$, and ⊗ denotes a Kronecker product. We have the following result.

#### Theorem 5.1.

Consider the opinion dynamics in (5.2) and assume that εi ∈ (0, aii), i = {1, …, n}. Then consensus to $1_{n} \otimes \overline{\sigma}$ (with $\overline{\sigma} = {\lbrack\sigma_{1},\ldots,\sigma_{k}\rbrack}^{\top} \in \mathbb{R}^{k}$) is reached, i.e. $\lim\limits_{t\rightarrow\infty}X_{t} = 1_{n} \otimes \overline{\sigma}$.

#### Proof.

Define the error sequence $e_{t - 1}:=X_{t - 1} - (1_{n} \otimes \overline{\sigma})$. Note that et−1 = 0 implies that consensus to $(1_{n} \otimes \overline{\sigma})$ is reached. Given the opinion dynamics in (5.2), the evolution of the error et−1 satisfies the following difference equation:
Equation: $\begin{matrix} e_{t} & {= ((A - \mathcal{E}) \otimes I_{k})X_{t - 1} + ((\mathcal{E} \otimes I_{k}) - I_{kn})(1_{n} \otimes \overline{\sigma})} \\ \, & {= ((A - \mathcal{E}) \otimes I_{k})e_{t - 1} - (1_{n} \otimes \overline{\sigma}) + (A \otimes I_{k})(1_{n} \otimes \overline{\sigma})} \\ \, & {= ((A - \mathcal{E}) \otimes I_{k})e_{t - 1} + ((A - I_{n})1_{n} \otimes \overline{\sigma}).} \end{matrix}$
It is easy to verify that, because A is stochastic, (A − In)1n = 0n. Then the error dynamics simplifies to
Equation 5.3: $e_{t} = ((A - \mathcal{E}) \otimes I_{k})e_{t - 1},$
and consequently, the solution et of (5.3) is given by $e_{t} = {((A - \mathcal{E}) \otimes I_{k})}^{t}e_{1}$. By properties of the Kronecker product and Gershgorin’s circle theorem, the spectral radius $\rho(A - \mathcal{E}) < 1$ for εi ∈ (0, aii). It follows that $\lim\limits_{t\rightarrow\infty}{((A - \mathcal{E}) \otimes I_{k})}^{t} = 0$, see [72]. Therefore, lim t→∞et = 0kn and the assertion follows. ▪

#### Corollary 5.2.

Consensus to $\overline{\sigma}$ is reached exponentially with the convergence rate given by $\parallel(A - \mathcal{E}) \otimes I_{k}) \parallel_{\infty}$, i.e. $\parallel X_{t} - (1_{n} \otimes \overline{\sigma}) \parallel_{\infty} \leq \parallel(A - \mathcal{E}) \otimes I_{k}) \parallel_{\infty}^{t - 1} \parallel X_{1} - (1_{n} \otimes \overline{\sigma}) \parallel_{\infty}$.

The proof of the above result is very similar to previous corollaries and is omitted.

### 5.2 Consensus with an unknown leader

As in the scalar case, there is a leader driving all the other agents through the opinion matrix A. Again, without loss of generality, we assume that the first agent (with corresponding opinion $x_{t}^{1} \in \mathbb{R}^{k}$) is the leader, $x_{1}^{1} = \overline{\sigma} = {\lbrack\sigma_{1},\ldots,\sigma_{k}\rbrack}^{\top} \in \mathbb{R}^{k}$, a1i = 0, i ∈ {2, …, n}, and a11 = 1. Then in this configuration, the opinion dynamics is given by
Equation 5.4: $X_{t} = (A \otimes I_{k})X_{t - 1},\quad A = \begin{pmatrix} 1 & 0 & \ldots & 0 \\ a_{21} & a_{22} & \ldots & a_{2n} \\ \vdots & \vdots & \ldots & \vdots \\ a_{n1} & a_{n2} & \ldots & a_{nn} \end{pmatrix}\operatorname{=:}\begin{pmatrix} 1 & 0 \\ \ast & \overset{\sim}{A} \end{pmatrix},$
with aij ≥ 0, $\sum\limits_{\, j = 1}^{n}a_{ij} = 1$, aii > 0 for all 1 ≤ i ≤ n, and for at least one i ≥ 2, $\sum\limits_{\, j = 2}^{n}a_{ij} < 1$.

#### Theorem 5.3.

Consider the opinion dynamics in (5.4) and assume that the matrix $\overset{\sim}{A}$ is substochastic and irreducible. Then consensus to $1_{n} \otimes \overline{\sigma}$ is reached, i.e. $\lim\limits_{t\rightarrow\infty}X_{t} = 1_{n} \otimes \overline{\sigma}$.

The proof of theorem 5.3 follows the same line of reasoning as the proof of theorem 4.4 and it is omitted here.

#### Corollary 5.4.

Let $\parallel \cdot \parallel_{\ast}$ denote some matrix norm such that $\parallel \overset{\sim}{A} \parallel_{\ast} < 1$. Then consensus to $\overline{\sigma}$ is reached exponentially with convergence rate $\parallel \overset{\sim}{A} \otimes I_{k} \parallel_{\ast}$, i.e. $\parallel X_{t} - (1_{n} \otimes \overline{\sigma}) \parallel_{\infty} \leq C \parallel \overset{\sim}{A} \otimes I_{k} \parallel_{\ast}^{t - 1} \parallel X_{1} - (1_{n} \otimes \overline{\sigma}) \parallel_{\infty}$, for some positive constant $C \in \mathbb{R}_{> 0}$.

## 6 Numerical simulations

Consider the opinion dynamics with feedback (4.2) with 10 agents (n = 10), $\overline{\sigma} = 0.375$ and initial condition
Equation: $X_{1} = {(0.3,0.35,0.37,0.4,0.45,0.5,0.55,0.57,0.6,0.65)}^{\top}.$
In both exchange-based and OTC markets, it is easy to ascertain who the main market-makers are for options on single stock or commodity [79,80]. Option market-makers are usually investment banks and big trading houses. In this sense, the number of players is not large and thus the models developed always have a finite number of agents, N = 10.

Figure 2 depicts the obtained simulation results for different values of the learning parameters εi, i = 1, …, 10. Specifically, figure 2a shows results without learning, i.e, εi = 0 (here there is no consensus to $\overline{\sigma}$), figure 2b depicts the results for εi = 0.9aii. As stated in theorem 4.1, consensus to $\overline{\sigma}$ is reached. Figure 2c shows results for εi = 0.9aii + 0.94 bi with b4 = 1 and bi = 0 otherwise, i = 1, …, 10. Note that, in this case, the value of ε4 violates the condition of theorem 4.1 (i.e. $\epsilon_{4} \notin(0,a_{44})$) and, as expected, consensus is not reached. Next, consider the opinion dynamics with a leader (4.5) with n = 10 and initial condition
Equation: $X_{1} = {(\overline{\sigma},0.35,0.37,0.4,0.45,0.5,0.55,0.57,0.6,0.65)}^{\top}.$
For the leader case, the opinion weights matrix is constructed by replacing the first row of A by (1, 0, …, 0). The corresponding matrix $\overset{\sim}{A}$ (defined in 4.5) is substochastic and irreducible, and $\sum\limits_{i = 2}^{i = 10}a_{ij} < 1$, j = 1, …, 10. Hence, all the conditions of theorem 4.4 are satisfied and consensus to $\overline{\sigma} = 0.375$ is reached. Figure 2d shows the corresponding simulation results. Finally, figure 3 shows the evolution of the vectored opinion dynamics (5.2) with n = 10 and k = 3 (i.e. 10 three-dimensional agents), matrix A as in the case with feedback, (vectored) volatility $\overline{\sigma} = {(0.67,0.22,0.88)}^{\top}$, learning parameters εi = 0.9aii for aii as in A, and initial condition 1k ⊗ X1 with X1 as in the first experiment above.

![Figure 3](https://trs.silverchair-cdn.com/trs/content_public/journal/rsos/7/10/10.1098_rsos.201188/9/m_rsos201188f03.png?Expires=1781820291&Signature=gE2Ohbcz-RW1pKWKzQHwMLAHO-a1wmdJ0eBLtRG1bCKaD6ibhZh-F2mYkXnA7G2hRJrzjW6g3-pSl7jdpLA8KhmtqtE6rcO6XYRr6ostXunXNcBejD-oNI0vSWY0JA~~yIozIisKwRbzm~Z1YeDQSFwrPf9ZeZ9m7RSBArbEUDS~jv5REvveE7IUq3h7yUHMemALGcNgG5gSZllihIxd-QEepFPjF0LXGrrbpM4Za-mV4GoeLql2hDOgSSnAhHdkPvLmmHLgZcTUwyvxjVJBKHUNZsIV4Vu8Um5TIUnLUnSsmkHk1T8w0WnpbLxO5Ap~94RvCKb7RfNaqa43IegFDw__&Key-Pair-Id=APKAIE5G5CRDK6RD3PGA)

**Figure 3.** Evolution of the multi-dimensional agents’ dynamics with learning (5.2).

## 7 Arbitrage bounds

We have taken the true volatility parameter as exogenous to our models. Our only requirement is that there is no static arbitrage, by which we mean that all the quotes in volatility which translate to option prices are such that one cannot trade in the different strikes to create a profit. Checking whether a volatility surface is indeed arbitrage-free is non-trivial, nevertheless some sufficient conditions are well known [81–83]. As long as the volatility surface satisfies them our analysis implies global stability towards an arbitrage-free smile.

We parametrize the volatility function (assuming expiry $T\text{~and~}S_{0}$ are fixed) and denote the option price as
Equation: $\overset{¯}{BS}(K,\sigma(K)) \triangleq {BS}(S_{0},K,T,\sigma(K)).$
Our attention is on varying K, to ensure no static arbitrage. We assume that the σ(K) translates into unique call option dollar prices. This follows from the strictly positive first derivative of the option price formula with respect to σ. We require two conditions:

- Condition 1: (Call Spread) For 0 < K1 ≤ K2, we have $\overset{¯}{BS}(K_{1},\sigma(K_{1})) \geq \overset{¯}{BS}(K_{2},\sigma(K_{2})).$
- Condition 2: (Butterfly Spread) For 0 < K1 < K2 < K3, $\overset{¯}{BS}(K_{1},\sigma(K_{1})) + (({K_{2} - K1})/({K_{3} - K_{2}})) \times \overset{¯}{BS}(K_{3},\sigma(K_{3})) \geq({K_{3} - K1})/({K_{3} - K_{2}}) \times \overset{¯}{BS}(K_{2},\sigma(K_{2})).$

## 8 Discussion

### 8.1 Future work

Social learning is an active area of research in many different fields. By combining aspects of social learning models with dynamical systems, we were able to develop insightful analysis for the volatility smile. This can be extended further. There are several immediate possibilities. Can the number of strikes be infinite? We restricted the models to a finite number of strikes: fixed k. In practical terms, at any given time, there are usually two strikes below and two strikes above the ATM level that are liquid. This means the corresponding quotes are visible or updated for five strikes. One way to circumvent this is to consider arbitrage-free volatility curves. But again, we are faced with the observational nature of our framework. A trader only observes a fixed number of strikes of his competitors. The issue of how to introduce heterogeneity in the volatility curves, which themselves emanate from specific pricing models, remains open.

The number of agents can also be infinite. Perhaps a propagation of chaos type of result could shed some light on how an individual trader interacts with the mean-field limit [89–91]. In this case, we lose the heterogeneity of beliefs and the behaviour we are trying to study would have a different implication. Moreover, considerable technical machinery is required [92,93]. We could study the pure limiting behaviour as t, n → ∞. In our current framework, this would have to be balanced with whether an individual can observe an infinite number of competitors. While the technical subtleties are not insurmountable, the modelling issues are more subjective.

The technical issues in random matrix products, briefly discussed in this paper, assure us that much more work needs to be done on the modelling and mathematical front. For example, the matrices A and $\mathcal{E}$ can be dependent with correlation decreasing in time. Work in this direction has been addressed by Popescu & Vaidya [94].

### 8.2 Connection

Recently, there has been some rather interesting work at the intersection of computer science and option pricing. Demarzo et al. [95] showed how to use efficient online trading algorithms to price the current value of financial instruments, deriving both upper and lower bounds using online trading algorithms. Moreover, Abernethy et al. [96,97] developed a BS price as sequential two-player zero-sum game. While these papers made an excellent start to bridge the gap between two different academic communities—mainly mathematical finance and theoretical computer science—they do not address the reality of volatility smiles and trading. Our contribution can be viewed as making these connections more concrete. The smile itself is a conundrum and there have even been articles questioning whether it can be solved [98]. The traditional way from the ground up is to develop a stochastic process for the volatility and asset price, possibly introducing jumps or more diffusions through uncertainty [99,100]. Such models have been successfully developed, but the time is ripe to incorporate multi-agent models with arbitrage-free curves.

Introducing learning agents in stochastic differential equation models [101], such as the BS model, is an exciting proposition. Moreover, opinion dynamics as a subject on its own has been studied quite extensively. Recent references that present an expansive discussion in computer science are [8,102]. Econophysics is the right community to develop new models. After all, there is no attachment to utilities of players or stochastic volatility models so entrenched in the mathematical finance community. Free from these shackles, researchers can use a range of tools and techniques to build more sophisticated models. Moreover, there is no restriction or debate on continuous or discrete time. While our framework is discrete, continuous time could perhaps show a way forward to incorporate models from mathematical finance and financial economics [103–105]. Jarrow [106] makes the case for continuous time, arguing that today’s financial markets trade and update at high frequency.

In this paper, we introduce models of learning agents in the context of option trading. A key open question in this setting is how the market comes to a consensus about market volatility, which is reflected in derivative pricing through the BS formula. The framework we have established allows us to explore other areas. Thus far, we took the smile as an exogenous object, proving convergence to equilibrium beliefs. A natural step forward would be to look at the beliefs as probability measures, where each measure corresponds to a different option pricing model. Our learning models focus on interaction between agents. Actually, agents can be interpreted as algorithms. Each algorithm corresponds to a particular belief of a pricing model. Until now, the replication paradigm has led to very sophisticated models. The future may belong to deep hedging arguments [107]. Still, whether we consider models or algorithms, interaction will always be a topic of interest.

## Data accessibility

This article has no additional data. Code for simulations is available within the Dryad Digital Repository: https://doi.org/10.5061/dryad.prr4xgxjg [108].

## Authors' contributions

T.V. conceptualized the model. T.V. and C.M. formalized the mathematical framework. G.P. guided the work and aided the discussions and structuring of the manuscript. T.V. and C.M. wrote the manuscript.

## Competing interests

We declare we have no competing interests.

## Funding

T.V. acknowledges a SUTD Presidential fellowship. C.M. acknowledges the National Research Foundation (NRF), Prime Minister’s Office, Singapore, under its National Cybersecurity R&D Programme (Award no. NRF2014NCR-NCR001-40) and administered by the National Cybersecurity R&D Directorate. G.P. acknowledges AcRF Tier 2 grant nos. 2016-T2-1-170, PIE-SGP-AI-2020-01, NRF2019-NRF-ANR095 ALIAS grant and NRF2018 Fellowship NRF-NRFF2018-07.

## Acknowledgements

The authors thank Ioannis Panageas, Ionel Popescu, Niels Nygaard and JM Schumacher for fruitful discussions.

## Footnotes

Using the BS formula with a particular implied volatility, traders obtain a dollar value for the price.

## References (108 total, showing 108)

1. Schinckus C . 2012 Methodological comment on Econophysics review I and II: statistical econophysics and agent-based econophysics . Quant. Finance , 12 , 1189 - 1192 . ( doi:10.1080/14697688.2012.704692 )
2. Chakraborti A , Toke IM , Patriarca M , Abergel F . 2011 Econophysics review: I. Empirical facts . Quant. Finance , 11 , 991 - 1012 . ( doi:10.1080/14697688.2010.539248 )
3. Kirman A . 2002 Reflections on interaction and markets . Quant. Finance , 2 , 322 - 326 . ( doi:10.1088/1469-7688/2/5/602 )
4. Föllmer H , Horst U , Kirman A . 2005 Equilibria in financial markets with heterogeneous agents: a probabilistic perspective . J. Math. Econ. , 41 , 123 - 155 . ( doi:10.1016/j.jmateco.2004.08.001 )
5. Chakraborti A , Toke IM , Patriarca M , Abergel F . 2011 Econophysics review: II. Agent-based models . Quant. Finance , 11 , 1013 - 1041 . ( doi:10.1080/14697688.2010.539249 )
6. Papadimitriou C , Piliouras G . 2018 Game dynamics as the meaning of a game . SIGEcom Exchanges , 16 , 53 - 63 . ( doi:10.1145/3331041.3331048 )
7. Piliouras G , Nieto-Granda C , Christensen HI , Shamma JS . 2014 Persistent patterns: multi-agent learning beyond equilibrium and utility. In Proceedings of the 2014 Int. Conf. on Autonomous Agents and Multi-agent Systems AAMAS ’14, pp. 181–188 .
8. Mai T , Panageas I , Vazirani VV . 2017 Opinion dynamics in networks: convergence, stability and lack of explosion. In 44th Int. Colloquium on Automata, Languages, and Programming (ICALP) .
9. Bacoyannis V , Glukhov V , Jin T , Kochems J , Song DR . 2018 Idiosyncrasies and challenges of data driven learning in electronic trading. In NIPS workshop 2018: Challenges and Opportunities for AI in Financial Services: the Impact of Fairness, Explainability, Accuracy, and Privacy .
10. Ganesh S , Vadori N , Xu M , Zheng H , Reddy P , Veloso M . 2019 Multi-agent simulation for pricing and hedging in a dealer market. In ICML’19 Workshop on AI in Finance .
11. Wei H , Wang Y , Mangu L , Decker K . 2019 Model-based reinforcement learning for predictions and control for limit order books. ( http://arxiv.org/abs/1910.03743 )
12. Malamud S , Rostek M . 2017 Decentralized exchange . Am. Econ. Rev. , 107 , 3320 - 62 . ( doi:10.1257/aer.20140759 )
13. Duffie D . 2011 Dark markets: asset pricing and information transmission in over-the-counter markets . Princeton, NJ : Princeton University Press .
14. Chriss N . 1996 Black Scholes and beyond: option pricing models . New York, NY : McGraw-Hill .
15. Otto M . 2001 Finite arbitrage times and the volatility smile? . Physica A , 299 , 299 - 304 . ( doi:10.1016/S0378-4371(01)00309-0 )
16. Kakushadze Z . 2017 Volatility smile as relativistic effect . Physica A , 475 , 59 - 76 . ( doi:10.1016/j.physa.2017.02.012 )
17. Derman E , Miller MB . 2016 The volatility smile . Hoboken, NJ : John Wiley & Sons .
18. Sornette D . 2014 Physics and financial economics (1776–2014): puzzles, Ising and agent-based models . Rep. Prog. Phys. , 77 , 062001 . ( doi:10.1088/0034-4885/77/6/062001 )
19. Vagnani G . 2009 The Black–Scholes model as a determinant of the implied volatility smile: a simulation study . J. Econ. Behav. Organ. , 72 , 103 - 118 . ( doi:10.1016/j.jebo.2009.05.025 )
20. Liu YF , Zhang W , Xu HC . 2014 Collective behavior and options volatility smile: an agent-based explanation . Econ. Modell. , 39 , 232 - 239 . ( doi:10.1016/j.econmod.2014.03.011 )
21. Li T . 2013 Investors’ heterogeneity and implied volatility smiles . Manage. Sci. , 59 , 2392 - 2412 . ( doi:10.1287/mnsc.2013.1712 )
22. Platen E , Schweizer M . 1998 On feedback effects from hedging derivatives . Math. Finance , 8 , 67 - 84 . ( doi:10.1111/1467-9965.00045 )
23. Challet D . 2016 Regrets, learning and wisdom . Eur. Phys. J. Spec. Top. , 225 , 3137 - 3143 . ( doi:10.1140/epjst/e2016-60122-y )
24. Iori G , Porter J . 2012 Agent-based modelling for financial markets. In Handbook on Computational Economics and Finance . ( doi:10.1093/oxfordhb/9780199844371.013.43 )
25. Sinha S , Chatterjee A , Chakraborti A , Chakrabarti BK . 2010 Econophysics: an introduction . Hoboken, NJ : John Wiley & Sons .
26. Stanley HE , et al . 1996 Anomalous fluctuations in the dynamics of complex systems: from DNA and physiology to econophysics . Physica-Section A , 224 , 302 - 321 . ( doi:10.1016/0378-4371(95)00409-2 )
27. Schinckus C . 2018 Ising model, Econophysics and analogies . Physica A , 508 , 95 - 103 . ( doi:10.1016/j.physa.2018.05.063 )
28. Castellano C , Fortunato S , Loreto V . 2009 Statistical physics of social dynamics . Rev. Mod. Phys. , 81 , 591 . ( doi:10.1103/RevModPhys.81.591 )
29. LeBaron B et al. 2001 A builder’s guide to agent-based financial markets . Quant. Finance , 1 , 254 - 261 . ( doi:10.1088/1469-7688/1/2/307 )
30. Farmer JD , Foley D . 2009 The economy needs agent-based modelling . Nature , 460 , 685 - 686 . ( doi:10.1038/460685a )
31. Samanidou E , Zschischang E , Stauffer D , Lux T . 2007 Agent-based models of financial markets . Rep. Prog. Phys. , 70 , 409 . ( doi:10.1088/0034-4885/70/3/R03 )
32. Lee RW . 2005 Implied volatility: statics, dynamics, and probabilistic interpretation. In Recent advances in applied probability , pp. 241–268. New York, NY: Springer .
33. Jacquier A , Shi F . 2019 The randomized Heston model . SIAM J. Finance Math. , 10 , 89 - 129 . ( doi:10.1137/18M1166420 )
34. Gatheral J , Jaisson T , Rosenbaum M . 2018 Volatility is rough . Quant. Finance , 18 , 933 - 949 . ( doi:10.1080/14697688.2017.1393551 )
35. Ellsberg D . 1961 Risk, ambiguity, and the Savage axioms . Q. J. Econ. , 75 , 643 - 669 . ( doi:10.2307/1884324 )
36. Knight FH . 2012 Risk, uncertainty and profit . Boston, MA : Courier Corporation .
37. Schinckus C . 2009 Economic uncertainty and econophysics . Physica A , 388 , 4415 - 4423 . ( doi:10.1016/j.physa.2009.07.008 )
38. Assa H , Gospodinov N . 2018 Market consistent valuations with financial imperfection . Decis. Econ. Finance , 41 , 65 - 90 . ( doi:10.1007/s10203-018-0207-2 )
39. Cousot L . 2004 Necessary and sufficient conditions for no static arbitrage among European calls . New York University : Courant Institute .
40. Laurent JP , Leisen DP . 2001 Building a consistent pricing model from observed option prices. In Quantitative Analysis In Financial Markets: Collected Papers of the New York University Mathematical Finance Seminar , vol. II, pp. 216–238. World Scientific .
41. Buehler H . 2006 Expensive martingales . Quant. Finance , 6 , 207 - 218 . ( doi:10.1080/14697680600668071 )
42. Duembgen M , Rogers L . 2014 Estimate nothing . Quant. Finance , 14 , 2065 - 2072 . ( doi:10.1080/14697688.2014.951678 )
43. Khrennikova P , Patra S . 2019 Asset trading under non-classical ambiguity and heterogeneous beliefs . Physica A , 521 , 562 - 577 . ( doi:10.1016/j.physa.2019.01.067 )
44. Mykland PA et al. 2003 Financial options and statistical prediction intervals . Ann. Stat. , 31 , 1413 - 1438 . ( doi:10.1214/aos/1065705113 )
45. Cheridito P , Kupper M , Tangpi L . 2017 Duality formulas for robust pricing and hedging in discrete time . SIAM J. Finance Math. , 8 , 738 - 765 . ( doi:10.1137/16M1064088 )
46. Acciaio B , Beiglböck M , Penkner F , Schachermayer W . 2016 A model-free version of the fundamental theorem of asset pricing and the super-replication theorem . Math. Finance , 26 , 233 - 251 . ( doi:10.1111/mafi.12060 )
47. Davis MH . 2016 Model-free methods in valuation and hedging of derivative securities. In The handbook of post crisis financial modeling , pp. 168–189. New York, NY: Springer .
48. Cont R . 2006 Model uncertainty and its impact on the pricing of derivative instruments . Math. Finance , 16 , 519 - 547 . ( doi:10.1111/j.1467-9965.2006.00281.x )
49. Burzoni M , Frittelli M , Maggis M . 2016 Universal arbitrage aggregator in discrete-time markets under uncertainty . Finance Stoch. , 20 , 1 - 50 . ( doi:10.1007/s00780-015-0283-x )
50. Wissner-Gross AD , Freer CE . 2010 Relativistic statistical arbitrage . Phys. Rev. E , 82 , 056104 . ( doi:10.1103/PhysRevE.82.056104 )
51. Buchanan M . 2015 Physics in finance: trading at the speed of light . Nature , 518 , 161 - 163 . ( doi:10.1038/518161a )
52. Gu GF , Xiong X , Ren F , Zhou WX , Zhang W . 2013 The position profiles of order cancellations in an emerging stock market . J. Stat. Mech: Theory Exp. , 2013 , P04027 . ( doi:10.1088/1742-5468/2013/04/P04027 )
53. Yoshimura Y , Okuda H , Chen Y . 2020 A mathematical formulation of order cancellation for the agent-based modelling of financial markets . Physica A , 538 , 122507 . ( doi:10.1016/j.physa.2019.122507 )
54. Eisler Z , Bouchaud JP , Kockelkoren J . 2012 The price impact of order book events: market orders, limit orders and cancellations . Quant. Finance , 12 , 1395 - 1419 . ( doi:10.1080/14697688.2010.528444 )
55. Hkazla J , Jadbabaie A , Mossel E , Rahimian MA . 2019 Reasoning in Bayesian opinion exchange networks is PSPACE-hard. In Conf. on Learning Theory , pp. 1614–1648. http://proceedings.mlr.press/v99/hazla19a.html .
56. Mossel E , Sly A , Tamuz O . 2014 Asymptotic learning on Bayesian social networks . Probab. Theory Relat. Fields , 158 , 127 - 157 . ( doi:10.1007/s00440-013-0479-y )
57. Banerjee AV . 1992 A simple model of herd behavior . Q. J. Econ. , 107 , 797 - 817 . ( doi:10.2307/2118364 )
58. Bikhchandani S , Hirshleifer D , Welch I . 1992 A theory of fads, fashion, custom, and cultural change as informational cascades . J. Pol. Econ. , 100 , 992 - 1026 . ( doi:10.1086/261849 )
59. Smith L , Sørensen P . 2000 Pathological outcomes of observational learning . Econometrica , 68 , 371 - 398 . ( doi:10.1111/1468-0262.00113 )
60. Chandrasekhar AG , Larreguy H , Xandri JP . 2019 Testing models of social learning on networks: evidence from two experiments . Econometrica , 88 , 1 - 32 . ( doi:10.3982/ecta14407 )
61. Becker J , Brackbill D , Centola D . 2017 Network dynamics of social influence in the wisdom of crowds . Proc. Natl Acad. Sci. USA , 114 , E5070 - E5076 . ( doi:10.1073/pnas.1621512114 )
62. Fudenberg D , Levine DK . 1998 The theory of learning in games , vol. 2 . Cambridge, MA : MIT Press .
63. Kalai E , Lehrer E . 1994 Weak and strong merging of opinions . J. Math. Econ. , 23 , 73 - 86 . ( doi:10.1016/0304-4068(94)90037-X )
64. DeGroot MH . 1974 Reaching a consensus . J. Am. Stat. Assoc. , 69 , 118 - 121 . ( doi:10.1080/01621459.1974.10480137 )
65. Masuda N , Porter MA , Lambiotte R . 2017 Random walks and diffusion on networks . Phys. Rep. , 716 , 1 - 58 . ( doi:10.1016/j.physrep.2017.07.007 )
66. Acemoglu D , Ozdaglar A . 2011 Opinion dynamics and learning in social networks . Dyn. Games Appl. , 1 , 3 - 49 . ( doi:10.1007/s13235-010-0004-1 )
67. Golub B , Sadler E . 2016 Learning in social networks. In The Oxford Handbook of the Economics of Networks . Oxford, UK: Oxford University Press .
68. Noorazar H . 2020 Recent advances in opinion propagation dynamics: a 2020 Survey . Eur. Phys. J. Plus , 135 , 521 . ( doi:10.1140/epjp/s13360-020-00541-2 )
69. Salinelli E , Tomarelli F . 2014 In Discrete dynamical systems: one-step scalar equations , pp. 85–124. Cham, Switzerland: Springer International Publishing .
70. Mizuno T , Nakano T , Takayasu M , Takayasu H . 2004 Traders’ strategy with price feedbacks in financial market . Physica A , 344 , 330 - 334 . ( doi:10.1016/j.physa.2004.06.145 )
71. Mizuno T , Kurihara S , Takayasu M , Takayasu H . 2003 Analysis of high-resolution foreign exchange data of USD-JPY for 13 years . Physica A , 324 , 296 - 302 . ( doi:10.1016/S0378-4371(02)01881-2 )
72. Horn RA , Johnson CR . 2012 Matrix analysis , (2nd edn) . New York, NY : Cambridge University Press .
73. Diaconis P , Freedman D . 1999 Iterated random functions . SIAM Rev. , 41 , 45 - 76 . ( doi:10.1137/S0036144598338446 )
74. Crisanti A , Paladin G , Vulpiani A . 2012 Products of random matrices: in statistical physics , vol. 104 . Heidelberg, Germany : Springer Science & Business Media .
75. Bruneau L , Joye A , Merkli M . 2010 Infinite products of random matrices and repeated interaction dynamics. In Annales de l’IHP Probabilités et statistiques , vol. 46, pp. 442–464 .
76. Garnerone S , de Oliveira TR , Zanardi P . 2010 Typicality in random matrix product states . Phys. Rev. A , 81 , 032336 . ( doi:10.1103/PhysRevA.81.032336 )
77. Tahbaz-Salehi A , Jadbabaie A . 2008 A necessary and sufficient condition for consensus over random networks . IEEE Trans. Autom. Control , 53 , 791 - 795 . ( doi:10.1109/TAC.2008.917743 )
78. Askarzadeh Z , Fu R , Halder A , Chen Y , Georgiou TT . 2019 Stability theory of stochastic models in opinion dynamics . IEEE Trans. Autom. Control , 65 , 522 - 533 . ( doi:10.1109/TAC.2019.2912490 )
79. Guéant O . 2016 The financial mathematics of market liquidity: from optimal execution to market making , vol. 33 . Boca Raton, FL : CRC Press .
80. Bouchaud JP , Bonart J , Donier J , Gould M . 2018 Trades, quotes and prices: financial markets under the microscope . Cambridge, UK : Cambridge University Press .
81. Carr P , Madan DB . 2005 A note on sufficient conditions for no arbitrage . Finance Res. Lett. , 2 , 125 - 130 . ( doi:10.1016/j.frl.2005.04.005 )
82. Gatheral J , Jacquier A . 2014 Arbitrage-free SVI volatility surfaces . Quant. Finance , 14 , 59 - 71 . ( doi:10.1080/14697688.2013.819986 )
83. Tehranchi MR . 2016 Uniform bounds for Black–Scholes implied volatility . SIAM J. Finance Math. , 7 , 893 - 916 . ( doi:10.1137/14095248X )
84. Assa H , Pouralizadeh M , Badamchizadeh A . 2019 Sound deposit insurance pricing using a machine learning approach . Risks , 7 , 45 . ( doi:10.3390/risks7020045 )
85. Roper M . 2010 Arbitrage free implied volatility surfaces. preprint . https://talus.maths.usyd.edu.au/u/pubs/publist/preprints/2010/roper-9.pdf .
86. Rogers L , Tehranchi M . 2010 Can the implied volatility surface move by parallel shifts? . Finance Stoch. , 14 , 235 - 248 . ( doi:10.1007/s00780-008-0081-9 )
87. Delbaen F , Schachermayer W . 2006 The mathematics of arbitrage . New York, NY : Springer Science & Business Media .
88. Ellersgaard S , Jönsson M , Poulsen R . 2017 The fundamental theorem of derivative trading-exposition, extensions and experiments . Quant. Finance , 17 , 515 - 529 . ( doi:10.1080/14697688.2016.1222078 )
89. Budhiraja A , Pal Majumder A . 2015 Long time results for a weakly interacting particle system in discrete time . Stoch. Anal. Appl. , 33 , 429 - 463 . ( doi:10.1080/07362994.2014.1003434 )
90. Carmona R , Delarue F . 2018 Probabilistic theory of mean field games with applications. I , vol. 83 . Probability Theory and Stochastic Modelling . Cham, Switzerland : Springer .
91. Boers N , Pickl P . 2016 On mean field limits for dynamical systems . J. Stat. Phys. , 164 , 1 - 16 . ( doi:10.1007/s10955-015-1351-5 )
92. Kolarijani MAS , Proskurnikov AV , Esfahani PM . In press. Macroscopic noisy bounded confidence models with distributed radical opinions . IEEE Trans. Autom. Control . ( doi:10.1109/TAC.2020.2994284 )
93. Jabin PE , Motsch S . 2014 Clustering and asymptotic behavior in opinion formation . J. Differ. Equ. , 257 , 4165 - 4187 . ( doi:10.1016/j.jde.2014.08.005 )
94. Popescu I , Vaidya T . 2019 Averaging plus Learning in financial markets. ( http://arxiv.org/abs/1904.08131 )
95. DeMarzo P , Kremer I , Mansour Y . 2006 Online trading algorithms and robust option pricing. In Proc. of the 38th Annual ACM Symp. on Theory of Computing , pp. 477–486. ACM .
96. Abernethy J , Frongillo RM , Wibisono A . 2012 Minimax option pricing meets Black-Scholes in the limit. In Proc. of the 44th Annual ACM Symp. on Theory of Computing , pp. 1029–1040. ACM .
97. Abernethy J , Bartlett PL , Frongillo R , Wibisono A . 2013 How to hedge an option against an adversary: Black-Scholes pricing is minimax optimal. In Advances in neural information processing systems (eds MI Jordan, Y Lecun, SA Solla), pp. 2346–2354 . Cambridge, MA : MIT Press .
98. Ayache E , Henrotte P , Nassar S , Wang X . 2004 Can anyone solve the smile problem. In The best of Wilmott , p. 229 .
99. Kamal M , Gatheral J . 2010 Implied volatility surface. In Encyclopedia of quantitative finance , vol. 2, pp. 926–930. Hoboken, NJ: Wiley .
100. Kyprianou A , Schoutens W , Wilmott P . 2006 Exotic option pricing and advanced Lévy models . Hoboken, NJ : John Wiley & Sons .
101. Schweizer M , Wissel J . 2008 Arbitrage-free market models for option prices: the multi-strike case . Finance Stoch. , 12 , 469 - 505 . ( doi:10.1007/s00780-008-0068-6 )
102. Mossel E , Tamuz O . 2017 Opinion exchange dynamics . Probab. Surv. , 14 , 155 - 204 . ( doi:10.1214/14-PS230 )
103. Nadtochiy S , Obłój J . 2017 Robust trading of implied skew . Int. J. Theor. Appl. Finance , 20 , 1750008 . ( doi:10.1142/S021902491750008X )
104. Davis MH , Hobson DG . 2007 The range of traded option prices . Math. Finance , 17 , 1 - 14 . ( doi:10.1111/j.1467-9965.2007.00291.x )
105. Shafer G , Vovk V . 2019 Game-theoretic foundations for probability and finance , vol. 455 . Hoboken, NJ : John Wiley & Sons .
106. Jarrow RA . 2018 Continuous-time asset pricing theory . New York, NY : Springer .
107. Buehler H , Gonon L , Teichmann J , Wood B . 2019 Deep hedging . Quant. Finance , 19 , 1271 - 1291 . ( doi:10.1080/14697688.2019.1571683 )
108. Vaidya T , Murguia C , Piliouras G . 2020 Learning agents in Black–Scholes financial markets. Dryad Digital Repository . ( doi:10.5061/dryad.prr4xgxjg )
