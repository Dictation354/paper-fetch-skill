---
title: "EMO: Pretraining Mixture of Experts for Emergent Modularity"
authors: "Ryan Wang, Akshita Bhagia, Sewon Min"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06663v1"
published: "2026-05-07"
source: "arxiv_html"
acquisition:
  provider: "arxiv"
  route: "official_html"
  representation: "html"
  transport: "http"
  fallback_used: false
has_fulltext: true
content_kind: "fulltext"
has_abstract: true
token_estimate: 14662
---

# EMO: Pretraining Mixture of Experts for Emergent Modularity

## Abstract

Large language models are typically deployed as monolithic systems, requiring the full model even when applications need only a narrow subset of capabilities, e.g., code, math, or domain-specific knowledge. Mixture-of-Experts (MoEs) seemingly offer a potential alternative by activating only a subset of experts per input, but in practice, restricting inference to a subset of experts for a given domain leads to severe performance degradation. This limits their practicality in memory-constrained settings, especially as models grow larger and sparser. We introduce Emo, an MoE designed for modularity—the independent use and composition of expert subsets—without requiring human-defined priors. Our key idea is to encourage tokens from similar domains to rely on similar experts. Since tokens within a document often share a domain, Emo restricts them to select experts from a shared pool, while allowing different documents to use different pools. This simple constraint enables coherent expert groupings to emerge during pretraining using document boundaries alone. We pretrain a 1B-active, 14B-total Emo on 1T tokens. As a full model, it matches standard MoE performance. Crucially, it enables selective expert use: retaining only 25% (12.5%) of experts incurs just a 1% (3%) absolute drop, whereas standard MoEs break under the same setting. We further find that expert subsets in Emo specialize at semantic levels (e.g., domains such as math or code), in contrast to the low-level syntactic specialization observed in standard MoEs. Altogether, our results demonstrate a path toward modular, memory-efficient deployment of large, sparse models and open new opportunities for composable architectures.

|                                                                   |               |                                      |
| ----------------------------------------------------------------- | ------------- | ------------------------------------ |
|                                                                   | Model         | hf.co/allenai/EMO                    |
|                                                                   | Code          | github.com/allenai/EMO               |
|

![Figure](https://arxiv.org/html/2605.06663v1/figures/blog.png)

| Blog          | allenai.org/blog/emo                 |
|

![Figure](https://arxiv.org/html/2605.06663v1/figures/search.png)

| Visualization | https://emovisualization.netlify.app |

## 1 Introduction

Large language models (LLMs) are typically trained and deployed as monolithic systems: a single model is pretrained, finetuned, and served as one unified entity Olmo et al. (2026); DeepSeek-AI et al. (2025); Yang et al. (2025a). While effective, this paradigm becomes increasingly restrictive as models scale. In many deployment settings, applications require only a narrow subset of capabilities—such as code generation, mathematical reasoning, or domain-specific knowledge—but must still serve the full model, incurring unnecessary computational cost and memory use. Moreover, the monolithic design prevents isolating, updating, or improving specific capabilities without retraining and redeploying the entire system.

Mixture-of-Experts (MoE) models appear to offer a natural path toward relaxing this constraint, as they consist of many small FFNs (experts), of which only a small subset is activated for each input token DeepSeek-AI et al. (2025); DeepSeek-AI et al. (2024). However, existing MoEs still require the full model for any task: tokens within the same input activate different experts, causing most or all experts to be used over the course of a task. As we show, this behavior—partially driven by experts specializing in low-level lexical patterns (e.g., prepositions, punctuation)—prevents subsets of the model from being usable independently, limiting the deployability of MoEs in memory-constrained settings, an issue that becomes increasingly important as models grow larger and sparser Dai et al. (2024); DeepSeek-AI et al. (2025); Yang et al. (2025a).

![Figure 1](2605.06663v1_assets/eval_pipeline_with_pareto.svg)

**Figure 1.** (Left) Emo is an MoE trained with modularity as a first-class objective. For a given domain (e.g., math, code, biomedical), users can select a small subset of experts of any size and retain near full-model performance. This turns a single model into a composable architecture, enabling flexible deployment with improved memory-accuracy tradeoffs for large, sparse MoEs. (Right) Averaged performance over 16 MMLU categories across different memory budgets. Emo (purple) and Reg. MoE (green) are single models evaluated with expert subsets of different sizes. Emo expert subsets push the Pareto frontier in memory-accuracy trade-off, outperforming standard MoEs and even fixed-budget models trained from scratch.

We instead seek to train MoE models in which experts organize into coherent groups that can be selectively used and composed. Concretely, we train an MoE model to be modular, i.e., to support (1) the independent use of expert subsets and (2) their composition into a strong general-purpose model. Achieving this in practice, however, is challenging. Prior work has explored partitioning training data into predefined domains (e.g., math, coding) and training separate experts Sukhbaatar et al. (2024); Shi et al. (2025), but this is too restricted for model’s learning and limits the model’s overall performance.

In this work, we propose to train MoE models in which modular structure emerges directly from the data, without relying on human-defined prior, and introduce Emo, an MoE that follows this approach. Our key intuition is that tokens from the similar domains should activate similar subsets of experts. Assuming that tokens within a document tend to share a domain, we enforce this structure by restricting all tokens in a document to select their active experts from a shared pool. For example, in an MoE with 128 total and 8 active experts, all tokens from a document select their active subset from a shared pool of 32 experts. Different documents may use different expert pools, allowing the model to learn recurring expert subsets across the training corpus. Importantly, Emo does not require predefined task or domain labels: expert subsets emerge in a self-supervised way, using document boundaries as the only grouping signal.

We train a 1B-active, 14B-total parameter Emo model on 1 trillion tokens. As a full model, Emo matches the overall performance of a standard MoE. More importantly, however, it enables effective composition of expert subsets, which standard MoEs fail to support. Across domain-specific subsets of MMLU and MMLU-Pro (e.g., math, physics, biology, social sciences), identifying and deploying only the most relevant experts largely preserve performance, e.g., 1% absolute performance drop when retaining 25% of experts, and 3% when retaining 12.5%. This is in contrast to standard MoEs that see severe degradation under the same constraint, e.g., 10% and 15% drops, respectively. These results show that Emo makes MoEs significantly more practical and accessible: instead of loading the full model, one can serve only a small subset of experts relevant to a given task or domain (Figure 1), which has important implications for deployment in memory-constrained settings Song et al. (2025); Shen and Henderson (2026); Tairin et al. (2025).

We further analyze routing patterns and find that expert subsets specialize at higher-level semantic granularity, such as domains and topics (e.g., math, code), which is in contrast to experts in standard MoEs that specialize in lower-level syntactic patterns (e.g., prepositions, punctuation). This difference suggests that expert specialization in Emo is qualitatively distinct and underlies its modularity.

Together, these results demonstrate that modularity can be built into large language models, opening a path for broader functionalities, such as targeted extension training or more interpretable and debuggable components to better regulate model behavior. We release both Emo and a matched baseline trained on the same data to support reproducibility and further study.

## 2 Related Work

### Mixture-of-Experts as Scalable Architectures.

Mixture-of-Experts (MoE) architectures introduce sparsity into Transformers by activating only a subset of experts per input, enabling efficient scaling to very large models Shazeer et al. (2017); Lepikhin et al. (2021); Fedus et al. (2022). Recent systems push this paradigm further by increasing both the number of experts and the degree of sparsity—for example, DeepSeek-V3 DeepSeek-AI et al. (2025) employs hundreds of experts per layer while activating only a small subset per token—allowing models to reach scales of hundreds of billions of parameters.

As MoEs grow larger and sparser, memory bottlenecks become a central challenge: even inactive experts need to reside in VRAM at inference time. This has motivated a line of work such as memory-constrained scaling laws Li et al. (2026), memory-efficient serving Song et al. (2025); Shen and Henderson (2026); Tairin et al. (2025), and expert pruning for a general purpose model that removes redundant experts Lu et al. (2024).

This work introduces an MoE that enables selective use of expert subsets for a given downstream task. Among its benefits, this provides a new way to alleviate memory bottlenecks in large, sparse MoEs, complementary to prior approaches.

### Specialization and Modularity of Existing MoEs.

A growing body of work studies the extent to which specialization emerges in MoE models. Prior work finds that specialization is often driven by surface-level patterns (e.g., token ID that is context-independent) or low-level lexical cues (e.g., prepositions, punctuations) Jiang et al. (2024); Muennighoff et al. (2025), while other works find that specialization is confined to only a tiny subset of experts Chaudhari et al. (2026). Other work suggests that apparent expert specialization may largely reflect geometric properties of the representation space that is difficult to interpret Wang et al. (2026). In parallel, several works attempt to exploit these patterns for efficiency, for example by pruning experts for a given task jie hu et al. (2025); Dong et al. (2025); Lu et al. (2024); Chen et al. (2022); Huang et al. (2026).

In this work, we show that standard MoEs trained with conventional objectives do not support meaningful use of small expert subsets for downstream domains, and instead advocate for training an MoE with modularity as a first-class objective. When training accordingly, MoEs naturally support selective use of expert subsets, and this behavior is robust across different subset selection methods.

### Training MoEs with Structured or Specialized Experts.

Prior work has explored training MoEs with more structured or specialized experts. One line of work promotes interpretability or diversity across experts, primarily to reduce redundancy Yang et al. (2025b); Park et al. (2025); Hu et al. (2026); Guo et al. (2025), but such approaches do not ensure that expert subsets are usable in isolation. Another line of work explicitly partitions training data into predefined domains (e.g., math, biomedical), train separate experts, and merge them into a single MoE Shi et al. (2025); Sukhbaatar et al. (2024); Li et al. (2022). While this enables standalone use of expert subsets, it relies on fixed, human-defined priors, which restricts flexibility and limits overall model performance. In contrast, we train an MoE end-to-end with modularity as a first-class objective, allowing expert structure to emerge without requiring predefined domains or human priors.

The closest line of work is ModuleFormer Shen et al. (2023), which shares our goal of training a modular MoE that supports standalone use of expert subsets. It introduces an objective that maximizes mutual information between tokens and experts. However, they evaluate only against dense models, without standard MoEs. We attempted to reproduce ModuleFormer and found that they do not perform better than standard MoEs, and degrades significantly when less than 40% of experts are retained, which is consistent with their reported results. Emo largely shares the motivation with ModuleFormer but proposed a more effective training objective that significantly outperforms standard MoEs and other parameter-matched and memory-matched baselines, showing minimal degradation even with an expert subset size of just 12.5%.

## 3 Modular Mixture of Experts (Emo)

![Figure 2](2605.06663v1_assets/modmoe_method.svg)

**Figure 2.** Comparison of training of a standard MoE and Emo ($k=2,n=10$, shared experts omitted for simplicity). (Left) In a standard MoE, each token independently selects its top-$k$ experts. (Right) In Emo, the router first selects a subset of experts for each document, and all tokens are constrained to route within this subset. This enforces consistent expert usage across the document, encouraging groups of experts to form domain specialization.

The goal of Emo is to pre-train an MoE with modularity as the first-class objective, i.e., (1) expert subsets should be usable in isolation for a particular downstream domain, and (2) their composition—the full model—remains a strong general-purpose model.

### Naive Approach.

A straightforward approach to develop modularity is to enforce expert specialization in MoEs by routing tokens to experts based on predefined semantic domains (e.g., math, biology, code). Methods such as FlexOlmo Shi et al. (2025) and BTX Sukhbaatar et al. (2024) instantiate this idea. However, this formulation requires domain labels across pretraining data, which can be ambigious, difficult to obtain, and injects human biases. Having fixed domains also restricts flexibility, making it difficult for the model to be applied to new domains during inference.

### Emo’s Approach.

Instead, we induce modular structure without explicit domain labels (Figure 2). Our key observation is that tokens within the same document usually come from the same domain. We therefore treat document boundaries as a weak supervisory signal: for each document, the router selects a shared expert pool, and all tokens in that document choose their active experts only from this pool. Different documents can use different pools, allowing modular expert subsets to emerge directly from the training data.

In the rest of the section, we first describe the standard MoE architecture and objective (§ 3.1), then describe Emo’s training objective (§ 3.2).

### 3.1 Preliminary: Mixture of Experts Architecture

Mixture-of-Experts (MoE) models are decoder-only Transformer language models (Vaswani et al., 2017) in which the feedforward sublayer is replaced by a sparse mixture of expert networks. Let the model contain $n$ total experts, consisting of $n_{r}$ routed experts and $n_{s}$ shared experts ($n=n_{r}+n_{s}$). Routed experts are selected dynamically on a per-token basis, while shared experts are always active.

Given the hidden state $x_{t}$ at token position $t$, a router produces logits over the routed experts,

$$ r(x_{t})\in\mathbb{R}^{n_{r}},\qquad p_{t}=\operatorname{softmax}(r(x_{t})). $$

Let $\mathcal{K}_{t}=\operatorname{Top}\text{-}K(p_{t},k)\subseteq\{1,\dots,n_{r}\}$ denote the indices of the top-$k$ routed experts selected for token $t$. The MoE feedforward output is then

$$ \operatorname{FFN}_{\mathrm{out}}(x_{t})=\sum\limits_{i\in\mathcal{K}_{t}}(p_{t})_{i}\,E_{i}(x_{t})\;+\;\sum\limits_{j=1}^{n_{s}}E^{(s)}_{j}(x_{t}), $$

where $E_{i}$ denotes the $i$-th routed expert and $E^{(s)}_{j}$ denotes the $j$-th shared expert.

The resulting $\operatorname{FFN}_{\mathrm{out}}(x_{t})$ is used throughout the forward pass of the model to compute token probabilities. We train the model using the standard autoregressive language modeling objective:

$$ \mathcal{L}_{\mathrm{CE}}=-\sum\limits_{t=1}^{T}\log P(x_{t}\mid x_{<t}), $$

where the conditional probabilities $P(x_{t}\mid x_{<t})$ are computed using the MoE layer defined above.

In addition to the cross entropy, MoE training includes auxiliary losses such as the load balancing loss $\mathcal{L}_{\mathrm{LB}}$ to encourage uniform expert utilization:

$$ \mathcal{L}_{\mathrm{LB}}=n_{r}\sum\limits_{i=1}^{n_{r}}\bar{f}_{i}\cdot\bar{P}_{i}, $$

where $\bar{f}_{i}$ is the fraction of tokens routed to expert $i$ and $\bar{P}_{i}$ is the average routing probability of expert $i$ across all tokens. The full objective is

$$ \mathcal{L}=\mathcal{L}_{\mathrm{CE}}+\alpha\mathcal{L}_{\mathrm{LB}}+\beta\mathcal{L}_{\mathrm{RZ}}, $$

where $\mathcal{L}_{\mathrm{RZ}}$ regularizes router logits, and $\alpha$ and $\beta$ control auxiliary loss weights.

### 3.2 Emo: An Objective to Induce Modularity

The goal of Emo is to induce modularity by leveraging document boundaries as a weak supervisory signal. Emo achieves this by selecting a document expert pool for each document and constrains all tokens in the document to route within this pool during training (Figure 2).

#### Formulation.

Recall that $p_{t}=\operatorname{softmax}(r(x_{t}))\in\mathbb{R}^{n_{r}}$ denotes the routing distribution for token $t$. We define the document expert pool $\mathcal{D}$ based on the average routing distribution across tokens:

$$ \mathcal{D}=\operatorname{Top}\text{-}K\!\left(\frac{1}{T}\sum\limits_{t=1}^{T}p_{t},\,d\right)\subseteq\{1,\dots,n_{r}\}. $$

Routing is then restricted to $\mathcal{D}$ via a masked and renormalized distribution

$$ \hat{p}_{t}(i)=\begin{cases}\dfrac{p_{t}(i)}{\sum\limits_{j\in\mathcal{D}}p_{t}(j)}&\text{if }i\in\mathcal{D},\\[8.0pt] 0&\text{otherwise}.\end{cases} $$

The routed experts are then

$$ \mathcal{R}_{t}=\operatorname{Top}\text{-}K(\hat{p}_{t},k). $$

The resulting feedforward output is

$$ \operatorname{FFN}_{\mathrm{out}}(x_{t})=\sum\limits_{i\in\mathcal{R}_{t}}(\hat{p}_{t})_{i}\,E_{i}(x_{t})\;+\;\sum\limits_{j=1}^{n_{s}}E^{(s)}_{j}(x_{t}), $$

where $E_{i}$ denotes routed experts and $E^{(s)}_{j}$ denotes shared experts.

The hyperparameter $d$ controls subset granularity: smaller $d$ enforces highly specialized expert subsets with limited expressivity (e.g., $d=k$ forces all tokens in a document to use the same experts), while larger $d$ increases flexibility at the cost of weaker modular structure (e.g., $d=n_{r}$ recovers the standard MoE).

### 3.3 Key Technical Considerations

Several technical choices were important for effective training of Emo (see § A for details).

#### Consideration 1. Load Balancing.

A central challenge is that load balancing and document-level routing appear to impose opposing pressures. This conflict arises under standard micro-batch load balancing, where the load-balancing loss is computed over only a few documents. While this local implementation reduces cross-device communication and simplifies distributed training, it also encourages tokens from the same document to spread across many experts, directly opposing the shared-pool constraint and causing unstable training.

We address this by adopting global load balancing Qiu et al. (2025), aggregating routing statistics across data-parallel groups. Applied over a larger and more diverse set of documents, load balancing encourages uniform utilization of experts across documents, while our routing constraint enforces expert consistency within each document, making the two objectives largely complementary. Empirically, this is important for stable training: see Figure 7 in § A.

#### Consideration 2. Choosing Expert Pool Size.

Fixing a single expert pool size $d$ works well during training but limits inference-time flexibility. The model "overfits" only to expert sets of size $d$ and performs poorly when deployed as expert subsets that isn’t of size $d$.

To enable the model to support expert subsets of all sizes, we treat $d$ as a random variable and sample it independently for each document during pretraining:

$$ d\sim\mathcal{U}\{k,\dots,n_{r}\}. $$

where $k$ is the number of active experts per token and $n_{r}$ is the total number of routable experts. This exposes the model to a range of expert pool sizes during training, enabling it to support expert subsets of varying capacities for selective expert use.

## 4 Experimental Setup

### 4.1 Architecture & Training Details

We consider an MoE with 1B active and 14B total parameters, consisting of $n=128$ experts ($n_{r}=127$ routed, $n_{s}=1$ shared), with $k=8$ experts activated per token. The baseline MoE and Emo share the same architecture; they differ only in their training objectives, as described in § 3.2.

We train both the baseline MoE and Emo from scratch on 1 trillion tokens from the OLMoE pretraining corpus (Muennighoff et al., 2025), followed by an additional 50B-token linear annealing phase. For ablations, we additionally train models on 130B tokens and include comparison to dense baselines and smaller MoEs.

Our architecture largely follows that of OLMoE (Muennighoff et al., 2025), with several key improvements: (1) adding a shared expert, (2) using pre-norm instead of post-norm, and (3) removing QK-norm; see § A for details on the improvements introduced by these changes. These modifications make our baseline MoEs significantly more competitive: as shown in § 5.1, our baseline MoE trained on 1T tokens consistently outperforms OLMoE trained on 5T tokens despite being trained on the same data.

### 4.2 Evaluation

We evaluate our models under two settings: (1) full-model evaluation, reflecting the standard use case in which a pretrained model is deployed for a broad set of tasks, and (2) selective expert use, where only a task-specific subset of experts is activated for a particular task or domain. Additional details on evaluation tasks and settings are provided in § C.

#### Full-model Evaluation.

We first evaluate the full model under zero-shot settings. We report results on five evaluation suites: (1) MC9, an average over nine multiple-choice benchmarks including ARC-Easy (Clark et al., 2018), ARC-Challenge (Clark et al., 2018), BoolQ (Clark et al., 2019), CSQA (Talmor et al., 2019), HellaSwag (Zellers et al., 2019), OpenBookQA (Mihaylov et al., 2018), PIQA (Bisk et al., 2020), SocialIQa (Sap et al., 2019), and WinoGrande (Sakaguchi et al., 2020); (2) Gen5, an average over five generative tasks including CoQA (Reddy et al., 2019), SQuAD (Rajpurkar et al., 2016), Natural Questions (Kwiatkowski et al., 2019), TriviaQA (Joshi et al., 2017), and DROP (Dua et al., 2019); (3) MMLU (Hendrycks et al., 2021)<sup>1</sup> Aggregated results exclude the “other” category; see § C and B.3 for details.; (4) MMLU-Pro (Wang et al., 2024) 1; and (5) GSM8K (Cobbe et al., 2021).

#### Selective Expert Use.

We next evaluate whether models can be deployed using only a subset of experts for each downstream domain (Figure 1). We consider coarse-grained domain grouping of MMLU and MMLU-Pro, e.g., math, physics, health, philosophy, history, which contain 16 1 and 13 1 domains, respectively, as well as GSM8K.

For each domain, we assume access to a small validation set to identify relevant experts. In § B.2, we show that this validation set can be extremely small: even a single few-shot example is sufficient to select an effective expert subset. We consider two selection methods: (1) a simple approach that aggregates routing probabilities across tokens and ranks experts by their average routing probability, and (2) Easy-EP Dong et al. (2025), a more computationally expensive, state-of-the-art expert selection method. We then retain the top-$d$ experts in each layer and discard the rest, producing a domain-specific subset of experts that can be used as a standalone model. We vary $d$ to measure how performance changes as fewer experts are retained. We report both zero-shot performance and performance after finetuning. More evaluation details can be found in § C.

## 5 Results and Analysis

### 5.1 Full-Model Evaluation

**Table 1.** Full-model Evaluation (§ 5.1). All models are trained on the same data mixture, and activate the same number of parameters (1B). Emo matches the performance of a standard MoE. $\dagger$: Use the outdated architecture (no pre-norm, use QK-norm, no shared expert, micro-batch load balancing) and has 64 total experts instead of 128.

|                   | # train tokens | MC9  | Gen5 | MMLU | MMLU Pro | GSM8K |
| ----------------- | -------------- | ---- | ---- | ---- | -------- | ----- |
| OLMoE<sup>†</sup> | 5T | 63.5 | 57.6 | 42.8 | 18.7 | 13.7 |
| Reg. MoE          | 1T             | 63.9 | 59.7 | 42.4 | 19.3     | 13.9  |
| Emo (Ours)        | 1T             | 63.1 | 57.9 | 42.8 | 18.5     | 12.0  |
| Dense             | 130B           | 54.1 | 41.5 | 33.0 | 12.2     | 2.7   |
| Reg. MoE          | 130B           | 60.1 | 51.0 | 37.5 | 15.8     | 5.2   |
| Emo (Ours)        | 130B           | 59.1 | 49.2 | 38.1 | 15.5     | 4.2   |

Table 1 reports full-model performance for models trained on the same data with the same number of active parameters (1B). First, our baseline MoE is competitive, outperforming OLMoE Muennighoff et al. (2025) trained on 5T tokens despite using only 1T tokens. Nonetheless, Emo matches the performance of this standard MoE.

The trend holds in the 130B-token setting: both our baseline MoE and Emo significantly outperform a dense model with matched active parameters, demonstrating the benefits of sparsity. Emo remains comparable to the standard MoE.

### 5.2 Selective Expert Use

![Figure 3](2605.06663v1_assets/modular_use_1t.svg)

**Figure 3.** Selective Expert Use of MoEs trained on 1T tokens (§ 5.2). Results are shown both without fine-tuning (top) and with fine-tuning (bottom). For MMLU and MMLU-Pro, each domain selects a corresponding expert subset as described in § 4.2, and we report macro-averaged results across domains (16 for MMLU and 13 for MMLU-Pro). The baseline MoE degrades sharply under subset restriction, whereas Emo remains robust, with $\approx 1$% drop at 25% parameters and $\approx 3$% drop at 12.5%, in both without and with fine-tuning.

We evaluate whether expert subsets in Emo can retain full-model performance for a given domain (Figure 3 for 1T tokens, Figure 11 for 130B tokens).

#### Standard MoEs (Green) Degrade Sharply.

Restricting to expert subsets leads to large performance drops—for instance, over 10% when retaining 25% of experts (128$\rightarrow$ 32), and below a dense model with matched active parameters (Figure 11). This trend is consistent with and without fine-tuning. These results show that standard MoEs do not support modular use: even when only a narrow set of capabilities is required, restricting to expert subsets causes performance to break down.

#### Emo (Purple) Enables Modular Use.

In contrast, Emo retains performance under subset deployment. Performance drops are minimal, e.g., about 1% at 25% expert retention and 3% at 12.5%, and the model continues to outperform dense baselines, even in an extreme case where only 6.2% of experts are retained. This trend persists after fine-tuning, e.g., notably, on GSM8K, subsets with up to 12.5% of experts perfectly recover full-model performance. These results indicate that Emo supports modular use by identifying domain-relevant expert subsets, enabling significant memory savings by avoiding the need to load the full model.

Notably, we show in § B.2 that selecting relevant expert subsets is sample efficient, needing as few as five examples. We also provide examples of GSM8K generations in § B.5, demonstrating qualitative differences in generation quality between expert subsets of Emo and those for standard MoEs.

#### Expert Subsets of Emo Outperform Memory-matched Models Trained from Scratch.

Figure 1 (right) compares Emo expert subsets against memory-matched models trained from scratch, including a standard MoE with 32 experts and a dense model. A full set of results can be found in Figure 11 in § B.1. Despite using only a subset of the experts from a larger pretrained model, the 32-expert and 8-expert subsets of Emo match or outperform these memory-matched baselines. These results suggest that expert subsets from a single Emo model offer a stronger memory-accuracy trade-off than models trained from scratch under fixed memory budgets, forming a new Pareto frontier across memory regimes.

#### Emo is Robust to Expert Selection Schemes.

![Figure 4](2605.06663v1_assets/expert_selection_method.svg)

**Figure 4.** Expert Selection Methods in selective expert use of MoEs trained on 1T tokens (§ 5.2). Results are without fine-tuning. For MMLU and MMLU-Pro, each domain selects a corresponding expert subset as described in § 4.2. Emo expert subsets maintain high performance compared to regular MoEs across both router-based and Easy-EP expert-selection strategies. Random expert selection converges quickly to random performance as expert subsets shrink.

In addition to router-based selection, we evaluate Easy-EP Dong et al. (2025), the state-of-the-art expert pruning method as an alternative selection strategy (Figure 4). As a sanity check, we also compare with random selection.

For a standard MoE, Easy-EP consistently outperforms router-based selection when larger subsets are retained, although performance still degrades sharply as the subset size decreases, consistent with observations from the original paper Dong et al. (2025). This suggests that even state-of-the-art selection methods cannot overcome the lack of localized domain-specific capabilities.

In contrast, Emo achieves strong performance under both router-based and Easy-EP selection methods. Performance is largely insensitive to the choice of selection scheme, and remains robust even with small expert subsets. This highlights that modularity must be learned during training, rather than recovered through post hoc expert selection.

In § B.4, we also test whether modularity can emerge after pre-training by annealing a standard MoE with the document-level expert pool objective (§ 3.2); while training Emo from scratch performs best, the annealed model shows signs of modularity, which we leave for future work to investigate.

### 5.3 Semantic Specialization Emerge in Emo

![Figure 5](2605.06663v1_assets/token_cluster_comparison.svg)

**Figure 5.** Token Clusters of pretraining data on MoEs trained on 1T tokens, clustered according to the process described in § 5.3. Claude Code was used to assign a representative short description for each cluster. Emo clusters correspond to semantically meaningful domains, with tokens from the same document largely grouped together. Standard MoE training produces clusters of surface-level or syntactic features, with document tokens dispersed across multiple clusters.

![Figure 6](2605.06663v1_assets/domain_similarities.png)

![Figure 6](2605.06663v1_assets/domain_similarities.png)

**Figure 6.** Domain Similarity of WebOrganizer documents on MoEs trained on 1T tokens (§ 5.3). Expert utilization is highly similar (similarity $>0.6$ for most domain pairs) in regular MoEs, while they are much more distinguishable (similarity $<0.4$) in Emo, especially in later layers.

We analyze how functional modularity emerges in Emo by examining expert specialization. We find a qualitative shift in behavior: while standard MoEs specialize at the lexical level, Emo induces specialization at the level of domains and topics.

To study this, we cluster pretraining tokens based on their routing behavior. Specifically, we sample the first 100 tokens from 12K documents and extract routing probabilities across experts. We project these representations using PCA (retaining 95% variance), apply L2 normalization, and cluster them using spherical k-means with 32 clusters.

#### Emo Clusters Align with Semantic Themes.

An interactive visualization is available at emovisualization.netlify.app;

Figure 5 shows representative cluster descriptions, assigned by Claude Code. First, in a standard MoE, clusters correspond to low-level lexical categories, such as “prepositions”, “proper names”, “copula verbs”, or “definite articles”, consistent with observations from prior work Jiang et al. (2024); Muennighoff et al. (2025). As a result, tokens within a single document are dispersed across many clusters.

In contrast, Emo produces clusters aligned with high-level semantics and domains, such as “film, music, TV & book reviews”, “health, medical & wellness”, “news reporting”, and “US. politics & elections”. As a result, tokens within the same document are typically assigned to the same cluster, indicating consistent expert use.

This reveals two key insights. First, domain-level specialization emerges in Emo, even with no explicit supervision. Second, this specialization directly enables modularity: tokens from the same domain share routing patterns, allowing computation to be localized to a small, coherent subset of experts. As a result, expert subsets can be used effectively for downstream domains.

#### Emo Expert Activation Patterns across Domains are Distinct and Matches Human Intuition.

We next ask whether domain-level expert activation patterns reflect human-interpretable domain similarity. We find that Emo groups conceptually related domains while separating unrelated ones, a structure much less pronounced in standard MoEs.

To measure this, we use a random sample of 20 million documents from WebOrganizer Wettig et al. (2025), which assigns each document to one of 24 human-labeled domains. For each domain, we construct a domain-level expert activation vector by first averaging router activations across tokens within each document, and then averaging these document-level vectors across all documents assigned to that domain. We measure similarity between domains using cosine similarity over the resulting domain-level expert activation vectors.

As shown in Figure 6, Emo produces domain-level similarity patterns that better match semantic relationships between human-labeled domains. Related domains exhibit higher expert-activation similarity, while unrelated domains are more clearly separated. In contrast, the standard MoE shows more diffuse similarities across domains, suggesting that its expert activations are less aligned with human-interpretable domain structure.

Across both models, early layers show limited domain structure, while later layers exhibit clearer alignment with human-labeled domains. This suggests that domain-level expert specialization emerges progressively in deeper layers, potentially motivating future work on inducing modularity in a layer-wise manner.

## 6 Future Directions

Emo is among the first MoE models with emergent modularity. While this work primarily focuses on modularity for efficient deployment, it also points to several broader opportunities.

### Accessible Deployment of Large Sparse MoEs.

As MoE models scale to trillions of parameters DeepSeek-AI (2026); Team et al. (2026), deploying or adapting them becomes increasingly resource-intensive. Prior work addresses this through memory-constrained scaling and optimized serving Li et al. (2026); Song et al. (2025); Shen and Henderson (2026); Tairin et al. (2025). Modularity offers an orthogonal path: selectively using small subsets of experts for a given domain, enabling more accessible deployment and adaptation, particularly well-suited for large, highly sparse models.

### Fine-grained Control.

Modularity can enable finer-grained control at inference time. Since Emo organizes experts along semantic domains, subsets could be selectively enabled or disabled depending on the application. For example, clusters associated with spam, gambling, or adult content (Figure 5) can be excluded in child-facing applications. Similarly, specialized domains, e.g., biomedical knowledge, may be valuable for benign use but risky in misuse scenarios, and could be conditionally exposed.

This suggests a potential alternative to dataset-level filtering: isolating and managing capabilities at inference time depending on scenarios.

### Modular Development and Maintenance.

Modularity can also open up a new paradigm for model updates. Current language models are usually trained and maintained as one large system, requiring the full model, data, and compute to be available at once. A modular model could instead support modular pretraining: training task or domain-specific subset of experts and then reintegrating those experts into the full model.

As a preliminary test, we finetune a 32-expert subset from Emo, then inserted it back into the original 128-expert model by replacing the corresponding experts. The resulting model improves over the original full model, though it does not yet match the performance of the standalone subset. This provides early evidence that expert subsets can be trained independently and later integrated, which we leave to future work.

### Higher Degrees of Monitorability.

Finally, modularity can also make models easier to monitor and audit. Expert activations provide a structured signal of which parts of the model are being used for a given input. For example, if a model answers a math question while strongly activating an expert subset associated with creative writing or low-quality web content, that mismatch may warrant closer inspection. This gives model developers a more structured interface for understanding and debugging model behavior.

## 7 Conclusion

We introduced Emo, a mixture-of-experts model designed to make modularity emerge during pretraining. By constraining tokens within the same document to route through a shared expert pool, Emo induces expert subsets that specialize to high-level tasks and capabilities without relying on human-defined domains or task labels. Our results show that this structure does not come at the cost of general performance: as a full model, Emo matches standard MoEs, while its extracted expert subset remain effective even when only a small fraction of experts are retained. Beyond efficient deployment, our analyses show that Emo learns expert subsets aligned with semantic domains rather than surface-level token patterns, suggesting a qualitatively different form of specialization. Together, these results demonstrate that large language models need not remain monolithic systems. Modularity can be built into pretraining itself, opening a path toward models that are easier to deploy, adapt, inspect, and compose.

## Acknowledgement

We thank Prasann Singhal, Gustavo Lucas Carvalho, Weijia Shi, Jagdeep Bhatia, Colin Raffel, Berkeley AI Research members, the Sky computing lab members, and Ai2 members for valuable discussion and feedback.

This research was supported in part by ONR (N00014-26-1-2233), the NVIDIA Academic Grant Program, and gifts from Ai2 and Apple. Ryan Wang was supported by the National Science Foundation Graduate Research Fellowship Program.

## Appendix A Architectural & Training Details and Ablations

![Figure 7](2605.06663v1_assets/global_vs_local_lb.svg)

**Figure 7.** Global vs Local Load Balancing and its effects on training stability (Appendix A.1). Using global load balancing leads to more stable pre-training runs with less gradient norm spikes.

### A.1 Load Balancing

We begin by making explicit how the simplified formulation of load balancing as described in Section 3.1 is implemented in practice.

Under standard implementations, the statistics $\bar{f}_{i}$ and $\bar{P}_{i}$ are computed independently within each data parallel group. Let there be $n_{p}$ data parallel groups<sup>2</sup> In this work, we pre-train with data parallelism only.. For each group $j$, let $f_{i}^{j}$ denote the fraction of tokens in its micro-batch routed to expert $i$, and let $P_{i}^{j}$ denote the average routing probability assigned to expert $i$ across tokens in that micro-batch. The load balancing loss is then defined as

$$ \mathcal{L}_{\mathrm{LB}}=\frac{1}{n_{p}}\sum\limits_{j=1}^{n_{p}}\left[n_{r}\sum\limits_{i=1}^{n_{r}}f_{i}^{j}\cdot P_{i}^{j}\right], $$

which corresponds to computing the simplified objective separately within each group and averaging the results.

In this paper, we instead modify the load balancing objective to operate over aggregated routing statistics across data parallel groups. Specifically, we perform an all-reduce over data parallel groups to obtain the aggregated routing frequency

$$ \bar{f}_{i}=\sum\limits_{j=1}^{n_{p}}f_{i}^{j}, $$

while retaining the per-group routing probabilities $P_{i}^{j}$. The load balancing loss is then computed as

$$ \mathcal{L}_{\mathrm{LB}}=\frac{1}{n_{p}}\sum\limits_{j=1}^{n_{p}}\left[n_{r}\sum\limits_{i=1}^{n_{r}}\bar{f}_{i}\cdot P_{i}^{j}\right]. $$

This formulation, proposed and used in Qwen 3 [<sup>3, 31</sup>], replaces local (micro-batch-level) estimates of $\bar{f}_{i}$ with aggregated statistics across data parallel groups, yielding a closer approximation to global routing behavior. In our setting, where training uses data parallelism only, this corresponds to computing load balancing over a larger set of sequences (i.e., the global batch up to gradient accumulation).

We find that global load balancing is critical for stable training in Emo. As shown in Figure 7, models trained with standard micro-batch-level load balancing exhibit unstable behavior, while global load balancing leads to consistent and reliable training dynamics. This difference arises because micro-batch-level load balancing conflicts with our document-level routing constraint by enforcing uniform expert usage within each micro-batch. In contrast, global load balancing aggregates routing statistics across data-parallel groups, allowing expert utilization to diversify across documents while preserving consistent routing within each document.

**Table 2.** Ablating Shared Experts and Document Pool Size. Evaluation on MMLU across different architectural configurations, comparing the effects of shared experts and dynamic expert subset sizes. We compare models without a shared expert ($n_{s}=0$), with a shared expert and fixed expert subset size ($d=32$), and with a shared expert and dynamic expert subset size ($U(8,128)$). Using a shared expert improves performance, while dynamic expert-subset-size training enables more flexible expert selection across different budgets.

| Configuration / $n_{r}$ | Configuration / $n_{s}$ | Configuration / $d$ | Inference / 8 | Inference / 16 | Inference / 32 | Inference / 64 | Inference / 128 | Fine-tuning / 8 | Fine-tuning / 16 | Fine-tuning / 32 | Fine-tuning / 64 | Fine-tuning / 128 |
| ----------------------- | ----------------------- | ------------------- | ------------- | -------------- | -------------- | -------------- | --------------- | --------------- | ---------------- | ---------------- | ---------------- | ----------------- |
| 128                     | 0                       | 32                  | 30.2          | 35.3           | 37.2           | 36.0           | 31.9            | 31.7            | 36.2             | 37.8             | 38.4             | 37.3              |
| 127                     | 1                       | 32                  | 29.6          | 34.4           | 36.6           | 35.6           | 33.6            | 31.7            | 36.0             | 38.3             | 38.5             | 37.4              |
| 127                     | 1                       | $U(8,128)$          | 33.7          | 36.4           | 37.0           | 37.7           | 38.1            | 34.5            | 37.5             | 38.5             | 39.7             | 39.8              |

### A.2 How to Choose $d$

We find that varying the size $d$ during training is important for enabling flexible selective expert use usage at inference time. As shown in Table 2, models trained with a fixed $d$ perform well at that specific expert subset size but degrade when evaluated at other subset sizes. In contrast, training with a distribution over $d$ yields robust performance across a wide range of expert subset sizes.

### A.3 Shared Experts

In Table 2, we find that incorporating shared experts improves performance in Emo. This is consistent with prior observations in DeepSeek-MoE [<sup>5</sup>].

### A.4 Tuning LR and LB

![Figure 8](2605.06663v1_assets/moe_hyperparameter_ablations.svg)

**Figure 8.** Standard MoE LR and LB Ablations. We ablate standard MoEs across learning rates and load balancing (Appendix A.4). We identify the best configuration as lr = $4e-3$ and lb = $1e-1$. For load balancing coefficient, we do not observe significant differences between $1e-1$ and $1e-2$, and choose the former because it had slightly higher training stability.

Due to limited compute budget, we perform ablations first on learning rate, then on load balancing in a sequential manner. Furthermore, we ablate the coefficients of each in increments of 10x.

#### Standard MoE Hyperparameter Ablations.

In Figure 8, we initialize with the default lr = $4e-4$, lb = $1e-2$ configurations following OLMoE [<sup>17</sup>]. We first ablate the learning rate by increasing it to $4e-3$ and $4e-2$ while keeping the load balancing coefficient fixed. In our results, using a learning rate of $4e-3$ led to the best results. We then ablated the load balancing coefficient from $1e-2$ to $1e-1$, which helped training stablility. We ended up selecting the hyperparameter configurations of lr = $4e-3$ and lb = $1e-1$.

![Figure 9](2605.06663v1_assets/twolevel_hyperparameter_ablations.svg)

**Figure 9.** Emo ablations over LR. Ablations of Emo across learning rates. Due to limited compute resources, we fix lb = $1e-1$ and only ablate the learning rate, finding that lr = $4e-3$ offered the best training loss. Minor training loss spikes in lr = $4e-3$ were resolved by implementing load balancing over global batches.

#### Emo Hyperparameter Ablations.

In Figure 9, we train Emo immediately using lb = $1e-1$ and ablated learning rate across lr = $4e-4$ (OLMoE default), $4e-3$, and $4e-2$. We noticed that lr = $4e-3$ led to the strongest performance by 3000 training steps and decided to move forwards with the final configuration of lr = $4e-3$ and lb = $1e-1$. We noticed small spikes in the loss during training for lr = $4e-3$, which were reduced when we used a global version of load balancing, see A.1.

### A.5 Prenorm vs ReorderedNorm

![Figure 10](2605.06663v1_assets/prenorm_noqknorm_ablations.svg)

**Figure 10.** Prenorm w. No QK Norm Ablations. Ablations on ReorderedNorm from [<sup>17</sup>] versus Prenorm with removed QK-norm (Appendix A.5). On both standard MoEs and Emo, using Prenorm with removed QK-norm achieves lower loss than ReorderedNorm. These experiments were conducted without applying global load balancing, shared experts, and dynamic $d$.

Both Emo and the standard MoE in this work implemented Prenorm with removed QK-norm instead of the default ReorderedNorm implementation in OLMoE [<sup>17</sup>]. We ran ablations that consistently showed that our new implementation achieves a lower training loss, see Figure 10.

## Appendix B Selective expert use Details

### B.1 130B Token Experiments

![Figure 11](2605.06663v1_assets/modular_use_130b.svg)

**Figure 11.** Selective Expert Use of MoEs trained on 130B tokens (§ 5.2). We report performance before fine-tuning (top) and after fine-tuning (bottom). For MMLU and MMLU-Pro, each domain selects a corresponding expert subset as described in § 4.2, and we report macro-averaged results across domains (17 for MMLU and 14 for MMLU-Pro). “Trained baseline @$k$” denotes a model trained from scratch with a parameter count matched to a $k$-expert subset. Across all tasks, the Emo 32-expert subset and 8-expert subset match or outperform the corresponding Reg. MoE @ 32 and Dense @ 8 trained models, with the 8-expert subset of Emo nearly doubling the performance of the Dense @ 8 on GSM8k, both before and after fine-tuning.

Following § 5.2, we show the results for selective expert useacross MMLU, MMLU Pro, and GSM8K for models trained on 130B tokens. Additionally, we compare against memory-matched models traine from scratch, including a standard MoE with 32 experts and a dense model. A subset of these results are presented in Figure 1 (right). Emo match or outperform all baselines in selective expert use, pushing the pareto-frontier in memory-accuracy trade-off.

### B.2 Ablations on expert subset initialization

![Figure 12](2605.06663v1_assets/calibration_sample_ablation.svg)

**Figure 12.** Effects of validation data quantity ($n$) and the presence of few-shot demonstrations (on both the data used to select experts and the actual test-set queries) on Emo expert subset performance, without any subsequent fine-tuning. By default MMLU/MMLU Pro have 5-shot demonstrations and GSM8K has 8-shot demonstrations. For GSM8K, we run with three random seeds for n=1, 5, and 10. Emo is sample-efficient in expert selection, and using few-shot demonstrations during both expert selection and evaluation brings large performance gains.

We now investigate how validation data affects expert selection. To study this, we vary three factors in Figure 12: (1) the number of validation examples used for expert selection, (2) validation set data format (few-shot vs. zero-shot prompts), and (3) the test-set data format (few-shot vs. zero-shot prompts).

#### Emo is Sample-efficient in Expert-selection.

We first consider the default setting used in this work, when both validation and test set use few-shot prompts. In this setting, Emo shows little degradation as validation set size decreases—even down to a single example (red in Figure 12. We hypothesize this robustness arises because of the presence of few-shot demonstrations in each validation datapoint, which may provide sufficient token-level signals.

We then investigate using zero-shot prompts for validation and evaluation (gray), performance degrades slightly as the validation set size decreases, but the drop remains modest even with only 5 validation examples. Overall, this demonstrations that Emo remains effective even in highly data-constrained settings.

#### Emo Depends on Validation Data.

While Emo is sample-efficient, the relationship between validation data and expert subset performance is nuanced and task-dependent. On GSM8K, for example, performance improves as the validation set size decreases. One possible explanation is that smaller validation sets produce more focused estimates of expert relevance, whereas aggregating across multiple examples can smooth these signals and yield less specialized expert subsets.

We also find that validation format sometimes matters independently of evaluation format: selecting experts using few-shot prompts can outperform zero-shot prompts, even when test examples are evaluated using zero-shot formats. This suggests that both the content and structure of validation data play a key role in shaping expert selection, an interaction we leave to future work.

### B.3 Selective Expert Use on "Other" Category in MMLU and MMLU Pro

![Figure 13](2605.06663v1_assets/modular_use_mmlu_other_130b.svg)

**Figure 13.** Selective expert use on Other category on Emo and standard MoEs trained on 130B tokens (Appendix B.3). Results are without fine-tuning. “Trained baseline @$k$” denotes a model trained from scratch with a parameter count matched to a $k$-expert subset. On tasks that are general, Emo expert subsets of sizes 32 and 8 performs worse compared to “Reg MoE @$32$” and “Dense @$8$” that are trained from scratch.

When the deployment task is general (e.g MMLU other and MMLU Pro categories, which serve as a "catch-all" for MMLU subjects), Emo expert subsets of size 32 and 8 experts struggle to match the Reg MoE @ 32 and Dense @8 baseline models trained from scratch (Figure 13). We view this phenomenon as a property of modular models, and believe it provides concrete evidence that Emo works in selective expert use because it has groups of experts that have localize capabilities. When reporting aggregate metrics of MMLU and MMLU Pro, we intentionally exclude including the "other" category, as it is not an example of selective expert use on a specific task.

### B.4 Annealing Standard MoEs to be Modular.

**Table 3.** Inducing Modularity during Annealing Only. We compare Emo, trained from scratch on 1T tokens and annealed on 50B tokens with document-level expert pool constraint (§ 3.2), against Emo-anneal, a model trained on 1T tokens as a standard MoE, but annealed on 50B tokens with the document-level expert pool constraint. Across most tasks and expert subset sizes, Emo improves over Emo-anneal, indicating that pre-training from scratch is important in realizing gains during selective expert use.

|            | # Experts     | Inference / MMLU | Inference / MMLU-Pro | Inference / GSM8K | Fine-tuning / MMLU | Fine-tuning / MMLU-Pro | Fine-tuning / GSM8K |
| ---------- | ------------- | ---------------- | -------------------- | ----------------- | ------------------ | ---------------------- | ------------------- |
| Emo-anneal | 8             | 32.1             | 13.1                 | 7.3               | 33.5               | 14.2                   | 22.6                |
| Emo-anneal | 16            | 35.4             | 14.8                 | 9.9               | 37.3               | 16.3                   | 25.3                |
| Emo-anneal | 32            | 38.8             | 16.5                 | 11.3              | 39.9               | 18.3                   | 26.8                |
| Emo-anneal | 64            | 41.3             | 17.4                 | 12.8              | 42.7               | 19.5                   | 27.7                |
| Emo-anneal | 128 (trained) | 42.3             | 18.2                 | 13.0              | 43.7               | 20.1                   | 27.2                |
| Emo        | 8             | 36.1             | 14.7                 | 6.9               | 37.3               | 15.6                   | 23.3                |
| Emo        | 16            | 39.9             | 16.6                 | 12.2              | 40.1               | 17.5                   | 28.3                |
| Emo        | 32            | 41.4             | 17.6                 | 11.7              | 41.7               | 19.5                   | 27.5                |
| Emo        | 64            | 42.5             | 18.2                 | 11.0              | 43.3               | 20.0                   | 27.1                |
| Emo        | 128 (trained) | 42.8             | 18.5                 | 12.0              | 43.6               | 20.4                   | 27.8                |

We investigate whether modularity requires applying the document-level expert pool objective (§ 3.2) throughout pre-training, or whether a standard MoE can be made modular after pre-training. To test this, we take a standard MoE pretrained on 1T tokens and anneal it using the document-level expert pool objective instead of the standard MoE training objective. Denoted as Emo-anneal in Table 3, this model underperforms Emo on most benchmarks across most expert subset sizes. However, Emo-anneal still trains successfully and exhibits signs of modularity, suggesting that post-training applications of the document-level expert pool objective may be a promising direction for future work.

### B.5 Generations from Selective Expert Use on GSM8K

We now demonstrate how small expert subsets of Emo is qualitatively better than that of regular MoEs. We give examples of GSM8K generations of Emo and Regular MoE trained on 1T tokens under selective expert use across different expert subset sizes. No finetuning was performed (expert subsets are evaluated zero-shot). We note that 8-expert subsets of Emo consistently produces coherent outputs while regular MoEs subsets deteriorate.

## Appendix C Evaluation Details

**Table 4.** Evaluation tasks grouped by MMLU-Pro (14 categories), MMLU (17 categories), MC9 (9 multiple-choice), Gen5 (5 generation), and GSM8K. Train+Val reports the size of the dataset used during expert selection and finetuning.

| Task                | Shots | Train+Val | Test   | Primary metric |
| ------------------- | ----- | --------- | ------ | -------------- |
| MMLU-Pro (14 tasks) |       |           |        |                |
| Math                | 5     | 601       | 750    | acc/raw        |
| Health              | 5     | 388       | 430    | acc/raw        |
| Physics             | 5     | 580       | 719    | acc/raw        |
| Business            | 5     | 376       | 413    | acc/raw        |
| Biology             | 5     | 347       | 370    | acc/raw        |
| Chemistry           | 5     | 513       | 619    | acc/raw        |
| Computer Science    | 5     | 224       | 186    | acc/raw        |
| Economics           | 5     | 398       | 446    | acc/raw        |
| Engineering         | 5     | 448       | 521    | acc/raw        |
| Philosophy          | 5     | 260       | 239    | acc/raw        |
| Other               | 5     | 430       | 494    | acc/raw        |
| History             | 5     | 213       | 168    | acc/raw        |
| Psychology          | 5     | 380       | 418    | acc/raw        |
| Law                 | 5     | 501       | 600    | acc/raw        |
| MMLU (17 tasks)     |       |           |        |                |
| Biology             | 5     | 320       | 182    | acc/raw        |
| Business            | 5     | 308       | 176    | acc/raw        |
| Chemistry           | 5     | 211       | 122    | acc/raw        |
| Computer Science    | 5     | 289       | 165    | acc/raw        |
| Culture             | 5     | 232       | 134    | acc/raw        |
| Economics           | 5     | 525       | 298    | acc/raw        |
| Engineering         | 5     | 103       | 58     | acc/raw        |
| Geography           | 5     | 140       | 80     | acc/raw        |
| Health              | 5     | 1 162     | 659    | acc/raw        |
| History             | 5     | 658       | 373    | acc/raw        |
| Law                 | 5     | 1 250     | 707    | acc/raw        |
| Math                | 5     | 752       | 427    | acc/raw        |
| Other               | 5     | 825       | 467    | acc/raw        |
| Philosophy          | 5     | 1 427     | 808    | acc/raw        |
| Physics             | 5     | 453       | 257    | acc/raw        |
| Politics            | 5     | 459       | 260    | acc/raw        |
| Psychology          | 5     | 823       | 463    | acc/raw        |
| MC9 (9 tasks)       |       |           |        |                |
| ARC-Easy            | 5     | 2 821     | 2 376  | acc/raw        |
| ARC-Challenge       | 5     | 1 418     | 1 172  | acc/raw        |
| BoolQ               | 5     | 9 427     | 3 270  | acc/raw        |
| HellaSwag           | 5     | 39 905    | 10 042 | acc/raw        |
| CSQA                | 5     | 9 741     | 1 221  | acc/raw        |
| OpenBookQA          | 5     | 5 457     | 500    | acc/raw        |
| PIQA                | 5     | 16 113    | 1 838  | acc/raw        |
| SocialIQA           | 5     | 33 410    | 1 954  | acc/raw        |
| WinoGrande          | 5     | 40 398    | 1 267  | acc/raw        |
| Gen5 (5 tasks)      |       |           |        |                |
| SQuAD               | 5     | 87 599    | 10 570 | F1             |
| CoQA                | 0     | 108 647   | 7 983  | F1             |
| NaturalQS           | 5     | 87 925    | 3 610  | F1             |
| TriviaQA            | 5     | 61 888    | 7 993  | F1             |
| DROP                | 5     | 77 409    | 9 536  | F1             |
| GSM8K (1 task)      |       |           |        |                |
| GSM8K               | 8     | 7 473     | 1 319  | EM             |

### MMLU and MMLU-Pro Setup.

For MMLU and MMLU-Pro, we randomly sample 40% of examples for the validation/training set and use the remaining 60% for evaluation. For MMLU, we group the original 57 subjects into 17 broader categories following [<sup>45</sup>] to ensure sufficient examples per category to train and evaluate with. Expert selection is performed at the category level: all subjects within the same category are processed by a single group of experts. When reporting aggregate MMLU and MMLU-Pro results, we exclude the “other” category, which is discussed in Appendix B.3.

### Evaluation and Finetuning Protocol.

We provide the full list of evaluation categories and subjects in Table 4. For multiple-choice benchmarks, we score each answer choice by its log-likelihood and select the highest-scoring option, reporting raw accuracy (“acc-raw”). For generation benchmarks, we report recall on Gen5 and exact match on GSM8K.

During selective expert use, we use the same set of examples as both the validation data for expert selection and training data for finetuning. For tasks other than MMLU and MMLU-Pro, we merge the original train and validation splits and use the combined set for both expert selection and finetuning. When finetuning is performed, we mask the input portion of the prompt and optimize only over output tokens. Unless otherwise specified, finetuning follows standard Hugging Face settings with one epoch, batch size 32, and learning rate $5\times 10^{-5}$.

## Appendix D Token Clustering Details

### Emo forms a Distinct Cluster for the First Token of Each Document.

We observe a dedicated expert cluster consistently activated for the first token in each document. This behavior is intuitive, as the model processes the first token without any context. Interestingly, this cluster does not extend to the second token: in most cases after observing just one token, the model transitions into a specific expert activation pattern that often remains stable throughout the rest of the document. This suggests that Emo rapidly commits to a document-level routing pattern after minimal context, with the first token serving as a distinct initialization phase before more specialized processing begins.

## References (50 total, showing 50)

[1] T. Olmo,:, A. Ettinger, A. Bertsch, B. Kuehl, D. Graham, D. Heineman, D. Groeneveld, F. Brahman, F. Timbers, H. Ivison, J. Morrison, J. Poznanski, K. Lo, L. Soldaini, M. Jordan, M. Chen, M. Noukhovitch, N. Lambert, P. Walsh, P. Dasigi, R. Berry, S. Malik, S. Shah, S. Geng, S. Arora, S. Gupta, T. Anderson, T. Xiao, T. Murray, T. Romero, V. Graf, A. Asai, A. Bhagia, A. Wettig, A. Liu, A. Rangapur, C. Anastasiades, C. Huang, D. Schwenk, H. Trivedi, I. Magnusson, J. Lochner, J. Liu, L. J. V. Miranda, M. Sap, M. Morgan, M. Schmitz, M. Guerquin, M. Wilson, R. Huff, R. L. Bras, R. Xin, R. Shao, S. Skjonsberg, S. Z. Shen, S. S. Li, T. Wilde, V. Pyatkin, W. Merrill, Y. Chang, Y. Gu, Z. Zeng, A. Sabharwal, L. Zettlemoyer, P. W. Koh, A. Farhadi, N. A. Smith, and H. Hajishirzi (2026) Olmo 3.
[2] DeepSeek-AI, A. Liu, B. Feng, B. Xue, B. Wang, B. Wu, C. Lu, C. Zhao, C. Deng, C. Zhang, C. Ruan, D. Dai, D. Guo, D. Yang, D. Chen, D. Ji, E. Li, F. Lin, F. Dai, F. Luo, G. Hao, G. Chen, G. Li, H. Zhang, H. Bao, H. Xu, H. Wang, H. Zhang, H. Ding, H. Xin, H. Gao, H. Li, H. Qu, J. L. Cai, J. Liang, J. Guo, J. Ni, J. Li, J. Wang, J. Chen, J. Chen, J. Yuan, J. Qiu, J. Li, J. Song, K. Dong, K. Hu, K. Gao, K. Guan, K. Huang, K. Yu, L. Wang, L. Zhang, L. Xu, L. Xia, L. Zhao, L. Wang, L. Zhang, M. Li, M. Wang, M. Zhang, M. Zhang, M. Tang, M. Li, N. Tian, P. Huang, P. Wang, P. Zhang, Q. Wang, Q. Zhu, Q. Chen, Q. Du, R. J. Chen, R. L. Jin, R. Ge, R. Zhang, R. Pan, R. Wang, R. Xu, R. Zhang, R. Chen, S. S. Li, S. Lu, S. Zhou, S. Chen, S. Wu, S. Ye, S. Ye, S. Ma, S. Wang, S. Zhou, S. Yu, S. Zhou, S. Pan, T. Wang, T. Yun, T. Pei, T. Sun, W. L. Xiao, W. Zeng, W. Zhao, W. An, W. Liu, W. Liang, W. Gao, W. Yu, W. Zhang, X. Q. Li, X. Jin, X. Wang, X. Bi, X. Liu, X. Wang, X. Shen, X. Chen, X. Zhang, X. Chen, X. Nie, X. Sun, X. Wang, X. Cheng, X. Liu, X. Xie, X. Liu, X. Yu, X. Song, X. Shan, X. Zhou, X. Yang, X. Li, X. Su, X. Lin, Y. K. Li, Y. Q. Wang, Y. X. Wei, Y. X. Zhu, Y. Zhang, Y. Xu, Y. Xu, Y. Huang, Y. Li, Y. Zhao, Y. Sun, Y. Li, Y. Wang, Y. Yu, Y. Zheng, Y. Zhang, Y. Shi, Y. Xiong, Y. He, Y. Tang, Y. Piao, Y. Wang, Y. Tan, Y. Ma, Y. Liu, Y. Guo, Y. Wu, Y. Ou, Y. Zhu, Y. Wang, Y. Gong, Y. Zou, Y. He, Y. Zha, Y. Xiong, Y. Ma, Y. Yan, Y. Luo, Y. You, Y. Liu, Y. Zhou, Z. F. Wu, Z. Z. Ren, Z. Ren, Z. Sha, Z. Fu, Z. Xu, Z. Huang, Z. Zhang, Z. Xie, Z. Zhang, Z. Hao, Z. Gou, Z. Ma, Z. Yan, Z. Shao, Z. Xu, Z. Wu, Z. Zhang, Z. Li, Z. Gu, Z. Zhu, Z. Liu, Z. Li, Z. Xie, Z. Song, Z. Gao, and Z. Pan (2025) DeepSeek-v3 technical report.
[3] A. Yang, A. Li, B. Yang, B. Zhang, B. Hui, B. Zheng, B. Yu, C. Gao, C. Huang, C. Lv, C. Zheng, D. Liu, F. Zhou, F. Huang, F. Hu, H. Ge, H. Wei, H. Lin, J. Tang, J. Yang, J. Tu, J. Zhang, J. Yang, J. Yang, J. Zhou, J. Zhou, J. Lin, K. Dang, K. Bao, K. Yang, L. Yu, L. Deng, M. Li, M. Xue, M. Li, P. Zhang, P. Wang, Q. Zhu, R. Men, R. Gao, S. Liu, S. Luo, T. Li, T. Tang, W. Yin, X. Ren, X. Wang, X. Zhang, X. Ren, Y. Fan, Y. Su, Y. Zhang, Y. Zhang, Y. Wan, Y. Liu, Z. Wang, Z. Cui, Z. Zhang, Z. Zhou, and Z. Qiu (2025) Qwen3 technical report.
[4] DeepSeek-AI, A. Liu, B. Feng, B. Wang, B. Wang, B. Liu, C. Zhao, C. Dengr, C. Ruan, D. Dai, D. Guo, D. Yang, D. Chen, D. Ji, E. Li, F. Lin, F. Luo, G. Hao, G. Chen, G. Li, H. Zhang, H. Xu, H. Yang, H. Zhang, H. Ding, H. Xin, H. Gao, H. Li, H. Qu, J. L. Cai, J. Liang, J. Guo, J. Ni, J. Li, J. Chen, J. Yuan, J. Qiu, J. Song, K. Dong, K. Gao, K. Guan, L. Wang, L. Zhang, L. Xu, L. Xia, L. Zhao, L. Zhang, M. Li, M. Wang, M. Zhang, M. Zhang, M. Tang, M. Li, N. Tian, P. Huang, P. Wang, P. Zhang, Q. Zhu, Q. Chen, Q. Du, R. J. Chen, R. L. Jin, R. Ge, R. Pan, R. Xu, R. Chen, S. S. Li, S. Lu, S. Zhou, S. Chen, S. Wu, S. Ye, S. Ma, S. Wang, S. Zhou, S. Yu, S. Zhou, S. Zheng, T. Wang, T. Pei, T. Yuan, T. Sun, W. L. Xiao, W. Zeng, W. An, W. Liu, W. Liang, W. Gao, W. Zhang, X. Q. Li, X. Jin, X. Wang, X. Bi, X. Liu, X. Wang, X. Shen, X. Chen, X. Chen, X. Nie, X. Sun, X. Wang, X. Liu, X. Xie, X. Yu, X. Song, X. Zhou, X. Yang, X. Lu, X. Su, Y. Wu, Y. K. Li, Y. X. Wei, Y. X. Zhu, Y. Xu, Y. Huang, Y. Li, Y. Zhao, Y. Sun, Y. Li, Y. Wang, Y. Zheng, Y. Zhang, Y. Xiong, Y. Zhao, Y. He, Y. Tang, Y. Piao, Y. Dong, Y. Tan, Y. Liu, Y. Wang, Y. Guo, Y. Zhu, Y. Wang, Y. Zou, Y. Zha, Y. Ma, Y. Yan, Y. You, Y. Liu, Z. Z. Ren, Z. Ren, Z. Sha, Z. Fu, Z. Huang, Z. Zhang, Z. Xie, Z. Hao, Z. Shao, Z. Wen, Z. Xu, Z. Zhang, Z. Li, Z. Wang, Z. Gu, Z. Li, and Z. Xie (2024) DeepSeek-v2: a strong, economical, and efficient mixture-of-experts language model.
[5] D. Dai, C. Deng, C. Zhao, R.x. Xu, H. Gao, D. Chen, J. Li, W. Zeng, X. Yu, Y. Wu, Z. Xie, Y.k. Li, P. Huang, F. Luo, C. Ruan, Z. Sui, and W. Liang (2024) DeepSeekMoE: towards ultimate expert specialization in mixture-of-experts language models. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), L. Ku, A. Martins, and V. Srikumar (Eds.), Bangkok, Thailand, pp. 1280–1297.
[6] S. Sukhbaatar, O. Golovneva, V. Sharma, H. Xu, X. V. Lin, B. Rozière, J. Kahn, D. Li, W. Yih, J. Weston, and X. Li (2024) Branch-train-MiX: mixing expert LLMs into a mixture-of-experts LLM. In Conference on Language Modeling,
[7] W. Shi, A. Bhagia, K. Farhat, N. Muennighoff, P. Walsh, J. Morrison, D. Schwenk, S. Longpre, J. Poznanski, A. Ettinger, D. Liu, M. Li, D. Groeneveld, M. Lewis, W. Yih, L. Soldaini, K. Lo, N. A. Smith, L. Zettlemoyer, P. W. Koh, H. Hajishirzi, A. Farhadi, and S. Min (2025) FlexOlmo: open language models for flexible data use. In Proceedings of Advances in Neural Information Processing Systems,
[8] C. Song, W. Zhao, X. Han, C. Xiao, Y. Chen, Y. Li, Z. Liu, and M. Sun (2025) BlockFFN: towards end-side acceleration-friendly mixture-of-experts with chunk-level activation sparsity.
[9] Z. Shen and P. Henderson (2026) Temporally extended mixture-of-experts models. arXiv preprint arXiv:2604.20156.
[10] S. Tairin, S. Mahmud, H. Shen, and A. Iyer (2025) EMoE: task-aware memory efficient mixture-of-experts-based (moe) model inference. arXiv preprint arXiv:2503.06823.
[11] N. Shazeer, A. Mirhoseini, K. Maziarz, A. Davis, Q. Le, G. Hinton, and J. Dean (2017) Outrageously large neural networks: the sparsely-gated mixture-of-experts layer. In Proceedings of the International Conference on Learning Representations,
[12] D. Lepikhin, H. Lee, Y. Xu, D. Chen, O. Firat, Y. Huang, M. Krikun, N. Shazeer, and Z. Chen (2021) GShard: scaling giant models with conditional computation and automatic sharding. In Proceedings of the International Conference on Learning Representations,
[13] W. Fedus, B. Zoph, and N. Shazeer (2022) Switch transformers: scaling to trillion parameter models with simple and efficient sparsity. Journal of Machine Learning Research 23 (120), pp. 1–39.
[14] H. Li, K. M. Lo, Z. Wang, Z. Wang, W. Zheng, S. Zhou, X. Zhang, and D. Jiang (2026) Can mixture-of-experts surpass dense llms under strictly equal resources?. In ICLR,
[15] X. Lu, Q. Liu, Y. Xu, A. Zhou, S. Huang, B. Zhang, J. Yan, and H. Li (2024) Not all experts are equal: efficient expert pruning and skipping for mixture-of-experts large language models. In Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), L. Ku, A. Martins, and V. Srikumar (Eds.), Bangkok, Thailand, pp. 6159–6172.
[16] A. Q. Jiang, A. Sablayrolles, A. Roux, A. Mensch, B. Savary, C. Bamford, D. S. Chaplot, D. d. l. Casas, E. B. Hanna, F. Bressand, et al. (2024) Mixtral of experts. arXiv preprint arXiv:2401.04088.
[17] N. Muennighoff, L. Soldaini, D. Groeneveld, K. Lo, J. Morrison, S. Min, W. Shi, P. Walsh, O. Tafjord, N. Lambert, et al. (2025) Olmoe: open mixture-of-experts language models. Proceedings of the International Conference on Learning Representations.
[18] M. Chaudhari, I. Gulati, N. Hundia, P. Karra, and S. Raval (2026) MoE lens – an expert is all you need.
[19] X. Wang, S. Hayou, and E. Nalisnick (2026) The myth of expert specialization in moes: why routing reflects geometry, not necessarily domain expertise. arXiv preprint arXiv:2604.09780.
[20] jie hu, J. Hou, and X. Li (2025) Quantifying expert specialization for effective pruning in mixture-of-experts models.
[21] Z. Dong, H. Peng, P. Liu, W. X. Zhao, D. Wu, F. Xiao, and Z. Wang (2025) Domain-specific pruning of large mixture-of-experts models with few-shot demonstrations. In Proceedings of Advances in Neural Information Processing Systems,
[22] T. Chen, S. Huang, Y. Xie, B. Jiao, D. Jiang, H. Zhou, J. Li, and F. Wei (2022) Task-specific expert pruning for sparse mixture-of-experts.
[23] W. Huang, Y. Zhang, X. Zheng, F. Chao, R. Ji, and L. Cao (2026) Discovering important experts for mixture-of-experts models pruning through a theoretical perspective. In The Thirty-ninth Annual Conference on Neural Information Processing Systems,
[24] X. Yang, C. Venhoff, A. Khakzar, C. S. de Witt, P. K. Dokania, A. Bibi, and P. Torr (2025) Mixture of experts made intrinsically interpretable. In Proceedings of the International Conference of Machine Learning, Note: Poster
[25] J. Park, Y. J. Ahn, K. Kim, and J. Kang (2025) Monet: mixture of monosemantic experts for transformers. Proceedings of the International Conference on Learning Representations.
[26] R. Hu, Y. Cao, B. Kong, M. Sun, and K. Yuan (2026) Improving moe performance and efficiency with plug-and-play intra-layer specialization and cross-layer coupling losses.
[27] H. Guo, H. Lu, G. Nan, B. Chu, J. Zhuang, Y. Yang, W. Che, X. Cao, S. Leng, Q. Cui, and X. Jiang (2025) Advancing expert specialization for better MoE. In Advances in Neural Information Processing Systems,
[28] M. Li, S. Gururangan, T. Dettmers, M. Lewis, T. Althoff, N. A. Smith, and L. Zettlemoyer (2022) Branch-train-merge: embarrassingly parallel training of expert language models.
[29] Y. Shen, Z. Zhang, T. Cao, S. Tan, Z. Chen, and C. Gan (2023) ModuleFormer: modularity emerges from mixture-of-experts.
[30] A. Vaswani, N. Shazeer, N. Parmar, J. Uszkoreit, L. Jones, A. N. Gomez, Ł. Kaiser, and I. Polosukhin (2017) Attention is all you need. Advances in neural information processing systems 30.
[31] Z. Qiu, Z. Huang, B. Zheng, K. Wen, Z. Wang, R. Men, I. Titov, D. Liu, J. Zhou, and J. Lin (2025) Demons in the detail: on implementing load balancing loss for training specialized mixture-of-expert models. In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), pp. 5005–5018.
[32] P. Clark, I. Cowhey, O. Etzioni, T. Khot, A. Sabharwal, C. Schoenick, and O. Tafjord (2018) Think you have solved question answering? try arc, the ai2 reasoning challenge. arXiv:1803.05457v1.
[33] C. Clark, K. Lee, M. Chang, T. Kwiatkowski, M. Collins, and K. Toutanova (2019) BoolQ: exploring the surprising difficulty of natural yes/no questions. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers), J. Burstein, C. Doran, and T. Solorio (Eds.), Minneapolis, Minnesota, pp. 2924–2936.
[34] A. Talmor, J. Herzig, N. Lourie, and J. Berant (2019) CommonsenseQA: a question answering challenge targeting commonsense knowledge. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers), J. Burstein, C. Doran, and T. Solorio (Eds.), Minneapolis, Minnesota, pp. 4149–4158.
[35] R. Zellers, A. Holtzman, Y. Bisk, A. Farhadi, and Y. Choi (2019) HellaSwag: can a machine really finish your sentence?. In Proceedings of the 57th Annual Meeting of the Association for Computational Linguistics, A. Korhonen, D. Traum, and L. Màrquez (Eds.), Florence, Italy, pp. 4791–4800.
[36] T. Mihaylov, P. Clark, T. Khot, and A. Sabharwal (2018) Can a suit of armor conduct electricity? a new dataset for open book question answering. In EMNLP,
[37] Y. Bisk, R. Zellers, R. Le Bras, J. Gao, and Y. Choi (2020) PIQA: reasoning about physical commonsense in natural language. In Association for the Advancement of Artificial Intelligence,
[38] M. Sap, H. Rashkin, D. Chen, R. Le Bras, and Y. Choi (2019) SocialIQA: commonsense reasoning about social interactions. In Proceedings of Empirical Methods in Natural Language Processing,
[39] K. Sakaguchi, R. Le Bras, C. Bhagavatula, and Y. Choi (2020) WinoGrande: an adversarial winograd schema challenge at scale. In Association for the Advancement of Artificial Intelligence,
[40] S. Reddy, D. Chen, and C. D. Manning (2019) CoQA: a conversational question answering challenge. Transactions of the Association for Computational Linguistics 7, pp. 249–266.
[41] P. Rajpurkar, J. Zhang, K. Lopyrev, and P. Liang (2016) SQuAD: 100,000+ questions for machine comprehension of text. In Proceedings of the 2016 Conference on Empirical Methods in Natural Language Processing, J. Su, K. Duh, and X. Carreras (Eds.), Austin, Texas, pp. 2383–2392.
[42] T. Kwiatkowski, J. Palomaki, O. Redfield, M. Collins, A. Parikh, C. Alberti, D. Epstein, I. Polosukhin, J. Devlin, K. Lee, K. Toutanova, L. Jones, M. Kelcey, M. Chang, A. M. Dai, J. Uszkoreit, Q. Le, and S. Petrov (2019) Natural questions: a benchmark for question answering research. Transactions of the Association for Computational Linguistics 7, pp. 452–466.
[43] M. Joshi, E. Choi, D. Weld, and L. Zettlemoyer (2017) TriviaQA: a large scale distantly supervised challenge dataset for reading comprehension. In Proceedings of the 55th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), R. Barzilay and M. Kan (Eds.), Vancouver, Canada, pp. 1601–1611.
[44] D. Dua, Y. Wang, P. Dasigi, G. Stanovsky, S. Singh, and M. Gardner (2019) DROP: a reading comprehension benchmark requiring discrete reasoning over paragraphs. In Proceedings of the 2019 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (Long and Short Papers), J. Burstein, C. Doran, and T. Solorio (Eds.), Minneapolis, Minnesota, pp. 2368–2378.
[45] D. Hendrycks, C. Burns, S. Basart, A. Zou, M. Mazeika, D. Song, and J. Steinhardt (2021) Measuring massive multitask language understanding. Proceedings of the International Conference on Learning Representations (ICLR).
[46] Y. Wang, X. Ma, G. Zhang, Y. Ni, A. Chandra, S. Guo, W. Ren, A. Arulraj, X. He, Z. Jiang, et al. (2024) Mmlu-pro: a more robust and challenging multi-task language understanding benchmark. Advances in Neural Information Processing Systems 37, pp. 95266–95290.
[47] K. Cobbe, V. Kosaraju, M. Bavarian, M. Chen, H. Jun, L. Kaiser, M. Plappert, J. Tworek, J. Hilton, R. Nakano, C. Hesse, and J. Schulman (2021) Training verifiers to solve math word problems.
[48] A. Wettig, K. Lo, S. Min, H. Hajishirzi, D. Chen, and L. Soldaini (2025) Organize the web: constructing domains enhances pre-training data curation. In Proceedings of the International Conference of Machine Learning,
[49] DeepSeek-AI (2026) DeepSeek-v4: towards highly efficient million-token context intelligence. Note: Technical reportAvailable at Hugging Face
[50] K. Team, Y. Bai, Y. Bao, Y. Charles, C. Chen, G. Chen, H. Chen, H. Chen, J. Chen, N. Chen, R. Chen, Y. Chen, Y. Chen, Y. Chen, Z. Chen, J. Cui, H. Ding, M. Dong, A. Du, C. Du, D. Du, Y. Du, Y. Fan, Y. Feng, K. Fu, B. Gao, C. Gao, H. Gao, P. Gao, T. Gao, Y. Ge, S. Geng, Q. Gu, X. Gu, L. Guan, H. Guo, J. Guo, X. Hao, T. He, W. He, W. He, Y. He, C. Hong, H. Hu, Y. Hu, Z. Hu, W. Huang, Z. Huang, Z. Huang, T. Jiang, Z. Jiang, X. Jin, Y. Kang, G. Lai, C. Li, F. Li, H. Li, M. Li, W. Li, Y. Li, Y. Li, Y. Li, Z. Li, Z. Li, H. Lin, X. Lin, Z. Lin, C. Liu, C. Liu, H. Liu, J. Liu, J. Liu, L. Liu, S. Liu, T. Y. Liu, T. Liu, W. Liu, Y. Liu, Y. Liu, Y. Liu, Y. Liu, Z. Liu, E. Lu, H. Lu, L. Lu, Y. Luo, S. Ma, X. Ma, Y. Ma, S. Mao, J. Mei, X. Men, Y. Miao, S. Pan, Y. Peng, R. Qin, Z. Qin, B. Qu, Z. Shang, L. Shi, S. Shi, F. Song, J. Su, Z. Su, L. Sui, X. Sun, F. Sung, Y. Tai, H. Tang, J. Tao, Q. Teng, C. Tian, C. Wang, D. Wang, F. Wang, H. Wang, H. Wang, J. Wang, J. Wang, J. Wang, S. Wang, S. Wang, S. Wang, X. Wang, Y. Wang, Y. Wang, Y. Wang, Y. Wang, Y. Wang, Z. Wang, Z. Wang, Z. Wang, Z. Wang, C. Wei, Q. Wei, H. Wu, W. Wu, X. Wu, Y. Wu, C. Xiao, J. Xie, X. Xie, W. Xiong, B. Xu, J. Xu, L. H. Xu, L. Xu, S. Xu, W. Xu, X. Xu, Y. Xu, Z. Xu, J. Xu, J. Xu, J. Yan, Y. Yan, H. Yang, X. Yang, Y. Yang, Y. Yang, Z. Yang, Z. Yang, Z. Yang, H. Yao, X. Yao, W. Ye, Z. Ye, B. Yin, L. Yu, E. Yuan, H. Yuan, M. Yuan, S. Yuan, H. Zhan, D. Zhang, H. Zhang, W. Zhang, X. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Y. Zhang, Z. Zhang, H. Zhao, Y. Zhao, Z. Zhao, H. Zheng, S. Zheng, L. Zhong, J. Zhou, X. Zhou, Z. Zhou, J. Zhu, Z. Zhu, W. Zhuang, and X. Zu (2026) Kimi k2: open agentic intelligence.
