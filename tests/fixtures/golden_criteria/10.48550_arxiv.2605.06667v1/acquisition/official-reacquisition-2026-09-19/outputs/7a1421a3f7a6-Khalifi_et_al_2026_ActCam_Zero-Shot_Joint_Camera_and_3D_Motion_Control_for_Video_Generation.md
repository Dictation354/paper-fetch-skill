---
title: "ActCam: Zero-Shot Joint Camera and 3D Motion Control for Video Generation"
authors: "Omar El Khalifi, Thomas Rossi, Oscar Fossey, Thibault Fouque, Ulysse Mizrahi, Philip Torr, Ivan Laptev, Fabio Pizzati, Baptiste Bellot-Gurlet"
journal: "arXiv"
doi: "10.48550/arxiv.2605.06667v1"
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
token_estimate: 9817
---

# ActCam: Zero-Shot Joint Camera and 3D Motion Control for Video Generation

## Abstract.

For artistic applications, video generation requires fine-grained control over both performance and cinematography—i.e., the actor’s motion and the camera trajectory. We present ActCam, a zero-shot method for video generation that jointly (i) transfers character motion from a driving video into a new scene and (ii) enables per-frame control of intrinsic and extrinsic camera parameters. ActCam builds on any pretrained image-to-video diffusion model that accepts conditioning in terms of scene depth and character pose. Given a source video with a moving character and a target camera motion, ActCam generates pose and depth conditions that remain geometrically consistent across frames. We then run a single sampling process with a two-phase conditioning schedule: early denoising steps condition on both pose and sparse depth to enforce scene structure, after which depth is dropped and pose-only guidance refines high-frequency details without over-constraining the generation. We evaluate ActCam on multiple benchmarks spanning diverse character motions and challenging viewpoint changes. We find that, compared to pose-only control and other pose+camera methods, ActCam improves camera adherence and motion fidelity, and is preferred in human evaluations—especially under large viewpoint changes. Our results highlight that careful camera-consistent conditioning and staged guidance can enable strong joint camera and motion control without training. Project page: https://elkhomar.github.io/actcam/.

![Figure 1](https://arxiv.org/html/2605.06667v1/teaser6.png)

![Figure 1](2605.06667v1_assets/pipeline.png)

**Figure 1.** Overview. ActCam enables zero-shot joint control of acting motion and camera motion for single-image video generation from a reference image, assuming only widespread conditioning capability of the backbone model on depth and keypoints. Given a reference image, an acting video representing the desired motion, and a target per-frame camera trajectory, ActCam generates a video that preserves identity while following both motion and cinematography.

## 1. Introduction

Driven by the intrinsic ambiguities of natural language, video generation has rapidly progressed from text-guided synthesis to strong conditioned generation pipelines (Zhang et al., 2023; Jiang et al., 2025), capable of accepting additional signals in the generation process to improve fidelity to the user’s instructions. This has already opened up possibilities for use in content production. For example, in experimental filmmaking (Juhi Marzia, 2025; Tangermann, 2025), visually appealing, consistent shots of synthetic humans can be seamlessly combined to form a short movie. However, results are still far from perfect, mostly due to the limited control over the stylistic characteristics of the output videos. Among other factors, in cinematography, a compelling shot of an actor is defined not only by what the subject does but also by how the camera moves (trajectory, parallax, viewpoint changes). Yet, the capability of controlling both the subject acting performance and the camera movements remains largely unexplored in the current literature.

To mitigate this problem, a class of motion-control approaches conditions video generation on 2D signals, typically depending on keypoints of human bodies (Wang et al., 2025a; Huang et al., 2025). While effective under mild viewpoint changes, such controls can become ambiguous under moving cameras: the same 2D signal can correspond to multiple 3D motions, and the control signal may no longer remain consistent once the camera rotates or translates. The closest approach enabling acting videos of humans with a moving camera is Uni3C (Cao et al., 2025), in which 3D representations of humans in motion are combined with camera information thanks to a custom architecture and ad-hoc finetuning. However, we argue that the necessity of using a specific model for generating videos with acting and camera control is a fundamental limitation: First, because the finetuning procedure can be expensive and limitedly transferable to newer models using different architectures. Second, because using a specialized model for this task, potentially combined with other models for shots in which acting is not necessary, may introduce stylistic inconsistencies in the resulting movie, ultimately harming the quality of the end result. Unlike Uni3C, requiring task-specific training, ActCam operates entirely at inference time and can be applied to any compatible video backbone without modification.

Hence, we introduce ActCam, a zero-shot framework exploiting only existing dense 2D conditioning mechanisms, such as depth and human keypoints (Zhang et al., 2023), to generate videos of acting humans with 3D camera control. We show some compelling results of ActCam in Figure 1. Assuming as input an acting video and the first frame of the target scenario, ActCam is able to generate multiple scenarios of the same acting, in the target scene, with arbitrary camera movements, using a pre-trained model with no finetuning. Our main intuition is that the main limiting factor for this task is the current lack of a camera-aligned conditioning representation for joint motion and camera control. ActCam addresses this by constructing a multi-modal, camera-aligned conditioning signal, including per-frame pose maps that encode acting motion under the desired camera, and per-frame depth maps that provide a coarse scene geometry proxy under the same camera. For controlling human motion, we benefit from 3D reconstruction of the acting video, avoiding inconsistencies related to the 2D keypoints. For camera control, instead, we benefit from depth reprojection, similarly to related approaches (Cao et al., 2025; Ren et al., 2025). However, one core characteristic of ActCam is how these conditioning signals interact. To avoid interference between static (depth) and dynamic (human motion) elements in the scene, we remove the reference character from the scene geometry and insert the animated character with a novel geometry-aware placement and depth alignment strategy. Finally, we introduce a two-phase conditioning schedule that exploits depth information only in early high-noise steps, while we use only pose information in later steps. This still provides the necessary guidance, removing artifacts due to the over-constraining of the diffusion model with a coarse depth. With both static cameras and dynamic cameras, ActCam outperforms the state-of-the-art under multiple metrics on visual quality and control fidelity. Our contributions are:

- Zero-shot joint control. We introduce ActCam, a training-free method for joint acting-motion and camera-trajectory control in image-conditioned video generation.
- Condition construction for joint control. We design a novel geometry-grounded conditioning pipeline that aligns motion (pose) and scene geometry (depth) to the target camera while preventing static/dynamic interference via reference-character removal, geometry-aware placement, and depth alignment.
- Two-phase conditioning pipeline. We propose a two-phase inference pipeline that adapts the conditioning information depending on the denoising step, leading to a flexible conditioning that preserves dynamic aspects of the scene.

## 2. Related Work

### Control signals for video generation.

A growing body of work improves controllability of diffusion-based image and video generation by injecting external conditions through adapters or control branches, and by conditioning on dense spatial signals such as edges, depth, or semantic layouts (Zhang et al., 2023; Guo et al., 2023; Guo et al., 2024; Lin et al., 2024). These approaches show that dense conditioning can strongly steer generative models. Some focus on motion control, either with reference videos (Pondaven et al., 2025; Ling et al., 2024; Xiao et al., 2024; Yatim et al., 2024) or with additional control signals such as trajectories (Zhang et al., 2025b; Yin et al., 2023; Wu et al., 2024; Zhou et al., 2025a; Mou et al., 2024) or sparse optical flow (Geng et al., 2025). Some impose motion control in a zero-shot manner, although they do not support precise camera control (Burgert et al., 2025). Pardo et al. (2025) manipulate noise at inference time to generate videos with similar motion. However, none of those methods solve the joint requirement of controlling an articulated performance while enforcing a non-trivial camera trajectory.

### Human-oriented video generation

Recent reference-based animation methods condition video diffusion on human-centric signals (e.g., keypoints, pose, dense pose) to reproduce an intended performance while preserving identity (Hu et al., 2024; Wang et al., 2024; Zhang et al., 2024; Tan et al., 2024; Xu et al., 2025b; Wang et al., 2025c; Jiang et al., 2025; Cheng et al., 2025; Zhang et al., 2025a). Wang et al. (2025a) uses keypoints as intermediate condition to render more realistic videos starting from text. Xu et al. (2024) exploits dense human part masks for guiding generation. All these approaches may suffer from occlusions and perspective-induced errors. Recent efforts (Gan et al., 2025) have also focused on increasing the length of synthesized human videos. Differently, some use reconstructed 3D humans to condition video generation (Zhu et al., 2024; Liang et al., 2025), although they offer no camera control. Similarly, Kulal et al. (2023) insert humans into scenes by inferring affordance-aware poses, but without motion or camera control. Our proposal, instead, offers unified camera control and human motion conditioning by exploiting 3D humans.

### Camera control and joint camera–motion control.

There is an interest in controlling camera trajectories in generated videos. A first line of work exploits Plucker embeddings and additional trained branches to enforce camera control (Kuang et al., 2024; He et al., 2025; Xu et al., 2025a; Bahmani et al., 2025b; Bahmani et al., 2025a). Alternatively, camera trajectories can be enforced by geometry-aware conditions that convey viewpoint changes more directly (Ren et al., 2025; Hou and Chen, 2024; Meng et al., 2025). These systems do not allow for joint human and camera conditioning simultaneously. Concurrently, Pulp Motion (Courant et al., 2026) generates camera trajectories and human motions, but focuses on trajectory generation rather than video synthesis. The closest work to ours is Uni3C (Cao et al., 2025), that allows joint camera and human motion control. However, it relies on additional training/finetuning to unify camera and motion control. In contrast, ActCam outperforms Uni3C exploiting joint control by constructing camera-aligned pose and depth conditions from a reference image, an acting video, and a camera preset.

## 3. Method

![Figure 1](2605.06667v1_assets/pipeline.png)

![Figure 2](2605.06667v1_assets/ablation_nd.png)

**Figure 2.** ActCam pipeline. Given a reference image, an acting video, and a target camera trajectory, we (1) estimate background depth from an inpainted reference, (2) recover motion and align it to the background scene via fitting, and (3) rasterize pose and depth+pose control signals under the target viewpoint. A two-phase denoising schedule conditions early steps on depth+pose for stronger camera control, then refines with pose-only to encourage motion adherence.

### 3.1. Problem setup

#### Inputs and goals.

We study image-conditioned video generation with joint control over the character’s motion and the camera trajectory, using a pretrained conditioned video diffusion backbone. We assume a sequence length $T$ and three inputs: a reference image $I_{\mathrm{ref}}\in\mathbb{R}^{H\times W\times 3}$ defining the target character identity and the environment appearance, an acting video $V_{\mathrm{act}}=\{I^{\mathrm{act}}_{\tau}\}_{\tau=1}^{T}$ providing the target performance, and a target per-frame camera trajectory $\mathcal{C}=\{(K_{\tau},R_{\tau},\mathbf{t}_{\tau})\}_{\tau=1}^{T}$, with intrinsics $K_{\tau}\in\mathbb{R}^{3\times 3}$ and extrinsics $(R_{\tau},\mathbf{t}_{\tau})\in SO(3)\times\mathbb{R}^{3}$. Let $V=\{I_{\tau}\}_{\tau=1}^{T}$ be the generated video. Our goal is to generate $V$ such that the identity and appearance match $I_{\mathrm{ref}}$, the motion in the output video matches the performance in $V_{\mathrm{act}}$, and finally, such that each frame’s viewpoint is in accordance with the desired camera parameters $\mathcal{C}$.

#### Formalisation of the setup.

We formalize the pretrained VACE (Jiang et al., 2025) model as a mapping $f:\mathfrak{C}\rightarrow\mathcal{V}$ that transforms a set of dense video-aligned signals $C$ into a video sequence $V$. VACE is trained on a video dataset combining various video-aligned conditions such as: depth, optical flow, character poses, and activation masks. We restrict the conditioning input to the tuple $C=(I_{\mathrm{ref}},c_{\mathrm{pose+depth}},c_{\mathrm{pose}})$. Our objective is to synthesize novel, geometrically consistent dense conditions $c_{\mathrm{pose}}$ and $c_{\mathrm{depth}}$ derived jointly from the acting video $V_{\mathrm{act}}$ and the target camera $\mathcal{C}$, such that the generated video $V=f(C)$ satisfies the desired motion and trajectory constraints. ActCam is a pure inference-time method: we keep the backbone fixed and design conditioning signals that jointly encode motion and camera.

#### Continuous flow formulation.

Let $z_{t}$ denote the latent video state at continuous time $t\in[0,1]$ and let $C$ denote the conditioning input. We model the generative dynamics as a flow governed by an ordinary differential equation (ODE). The backbone network $v_{\theta}$ approximates the instantaneous velocity field, defining the temporal evolution of the latent state as

(1)
$$ \frac{\mathrm{d}z_{t}}{\mathrm{d}t}=v_{\theta}(z_{t},t,C). $$

The target latent $z_{1}$ is obtained by integrating this flow over time from $z_{0}\sim\mathcal{N}(0,1)$ and is subsequently decoded into the video $V$.

#### Conditioning Requirements for Camera-Aligned Motion Control.

To jointly ensure camera control and pose reproduction, the conditioning must provide spatially grounded, per-frame cues in the target camera view: it must both enforce the intended motion and stabilize the scene layout under viewpoint changes. To enforce camera control, we preferred a dense per frame aligned depth signal making sure the model understands the 3D geometry and camera motion rather than numerical camera control using Plücker rays since dense superiority has been proven in (Ren et al., 2025). In practice, simply combining off-the-shelf controls is brittle: view-locked motion cues (e.g., 2D keypoints) become ambiguous under camera motion, and conditioning on depth estimated from $I_{\mathrm{ref}}$ entangles the static reference character with the dynamic character we want to animate, which can cause duplicated characters, freezing, or violations of motion/camera constraints. ActCam addresses this by constructing camera-aligned pose/depth conditions and by using a two-phase conditioning schedule (Sections 3.2–3.3).

### 3.2. Camera-aligned condition construction

#### Intuition.

Our goal is to provide the diffusion model with a target-view-aligned condition that jointly encodes character motion and camera motion. To this end, we leverage depth as a geometric prior: once rasterized under the target camera trajectory, the depth signal implicitly conveys viewpoint changes as apparent background motion. However, naively using the reference image depth introduces a static character that conflicts with the dynamic pose signal (see Figure 2). We address this by inpainting the character out of the reference image and estimating a background-only depth map $\mathcal{D}_{\text{bg}}$. ActCam then constructs a unified 3D scene from $\mathcal{D}_{\text{bg}}$ and the recovered poses, from which we rasterize two control signals under the target camera: a depth+pose condition and a pose-only condition obtained by omitting the depth.

#### Camera motion and 3D anchor

In order to provide a 3D anchor to VACE, we construct a 3D background environment which we argue, once rasterized, will provide enough information to the model to effectively encode the camera motion as an equivalent background motion, and disentangle the character motion from camera motion, reducing conflicts between the two signals. We estimate a depth map $D_{\mathrm{ref}}$ from $I_{\mathrm{ref}}$ using a monocular depth estimator (MoGe (Wang et al., 2025b)). This leads to the creation of a 3D mesh that can be rendered from different viewpoints. Mesh-based rendering provides stronger geometric consistency than point clouds, which tend to exhibit sparsity and visual artifacts under camera motion.

Nonetheless, solely relying on the reference image depth proves insufficient. Indeed, the presence of a static character in the 3D mesh provides a conflicting signal when rendered with a dynamic pose control signal, as in Figure 2. To tackle this, we propose to inpaint the character out of the reference image $I_{\mathrm{ref}}$ to extract a background-only depth map $\mathcal{D}_{\text{bg}}$, yielding a background 3D mesh, suppressing depth-static character related issues, such as character duplication in the output video.

Also, since VACE relies on dense conditioning, enforcing strict pixel correspondence between the control signals and the generated video is crucial. A key challenge is the alignment of the dynamic actor pose with the background 3D scene geometry. In practice, the reference depth map $\mathcal{D}_{\mathrm{ref}}$ and the background depth map $\mathcal{D}_{\mathrm{bg}}$ are estimated in two independent passes, leading to inconsistencies in 3D space. To resolve this discrepancy, we estimate a geometric alignment allowing the character to be correctly registered within the background 3D mesh. We refer to this stage as the scene transfer, described in the next paragraph, and visible in Figure 2.

#### Scene transfer

Let $\mathcal{M}\subset\llbracket 1,H\rrbracket\times\llbracket 1,W\rrbracket$ denote the binary character segmentation mask in $\mathcal{I}_{\mathrm{ref}}$, obtained using (Liu et al., 2024). Our goal is to find the new position of the reference character when transferred into the 3D background mesh, while preserving pixel reprojection with $\mathcal{I}_{\mathrm{ref}}$; therefore, only the depth of the character points is adjusted, since its scale and image plane coordinates will be imposed. We exploit the set of non-inpainted pixels $(u,v)\notin\mathcal{M}$, for which reliable correspondences exist between the two depth maps. Let $\mathbf{x}^{\mathrm{ref}}_{u,v}\in\mathbb{R}^{3}$ and $\mathbf{x}^{\mathrm{bg}}_{u,v}\in\mathbb{R}^{3}$ denote the 3D points reconstructed from $\mathcal{D}_{\mathrm{ref}}$ and $\mathcal{D}_{\mathrm{bg}}$, respectively. To emphasize constraints near the character boundary, we assign each an importance weight: not all environment points contribute equally to the scene transfer, as points closer to the character are more informative for rendering correct scene interactions. We assign higher weight to closer points:

(2)
$$ w(u,v)=\exp\Big(-\mathrm{dist}(\mathbf{x}^{\mathrm{ref}}_{u,v},\mathcal{M})\Big), $$

where $\mathrm{dist}(\cdot,\mathcal{M})$ denotes the Euclidean distance in the image plane to the closest pixel in the mask $\mathcal{M}$. We then compute the weighted centroids of the character relative to each set of points in $\mathcal{D}_{\mathrm{ref}}$ and $\mathcal{D}_{\mathrm{bg}}$ respectively:

(3)
$$ \mathbf{p}_{\mathrm{ref}}=\frac{\sum\limits_{(u,v)\notin\mathcal{M}}w(u,v)\,\mathbf{x}^{\mathrm{ref}}_{u,v}}{\sum\limits_{(u,v)\notin\mathcal{M}}w(u,v)},\qquad\mathbf{p}_{\mathrm{bg}}=\frac{\sum\limits_{(u,v)\notin\mathcal{M}}w(u,v)\,\mathbf{x}^{\mathrm{bg}}_{u,v}}{\sum\limits_{(u,v)\notin\mathcal{M}}w(u,v)}. $$

Assuming that the relative position of the character with respect to these centroids is preserved up to a global depth scaling, we align the character by applying an affine transformation along the depth axis. For any character point with reference depth $z^{\mathrm{char}}_{\mathrm{ref}}$, the aligned depth in the background coordinate system is given by

(4)
$$ z^{\mathrm{char}}_{\mathrm{bg}}=\big(z^{\mathrm{char}}_{\mathrm{ref}}-p^{z}_{\mathrm{ref}}\big)\frac{p^{z}_{\mathrm{bg}}}{p^{z}_{\mathrm{ref}}}+p^{z}_{\mathrm{bg}}, $$

where $p^{z}_{\mathrm{ref}}$ and $p^{z}_{\mathrm{bg}}$ denote the $z$-coordinates of $\mathbf{p}_{\mathrm{ref}}$ and $\mathbf{p}_{\mathrm{bg}}$, respectively. This transformation jointly accounts for scale and translation mismatches, enabling consistent addition of the character points to the background 3D scene, while effectively taking character-environment proximities (e.g. contacts) into account via the importance weighting.

#### 4D motion recovery (acting).

We recover a motion sequence of 3D humans from $V_{\mathrm{act}}$ using a monocular 3D human motion estimator (GVHMR (Chu and others, 2024)). We denote the recovered articulated state at frame $\tau$ as $\mathcal{S}_{\tau}$ (e.g., SMPL parameters and root pose). Unlike 2D keypoints, $\{\mathcal{S}_{\tau}\}$ reduces depth ambiguity and provides a stable motion signal under viewpoint changes.

#### Character 3D fitting

As in (Cao et al., 2025), we align the dynamic poses $\mathcal{S}$ with the actual replaced character in the assembled background 3D scene (see Figure 2). To that extent, we adopt the same approach as in (Cao et al., 2025) using a least squares estimation based on rigid transformation at time $\tau=0$ between the $\mathcal{S}_{0}$ and the extracted keypoints from $I_{\mathrm{ref}}$. This method (Umeyama, 1991) provides a rotation matrix $R\in SO(3)$, a translation $\hat{t}\in\mathbb{R}^{3}$ and a scale $s$ that we will apply to the pose sequence as follows:

$$ \hat{\mathcal{S}}_{\tau}=s.R\mathcal{S}_{\tau}+\hat{t} $$

This new sequence $\hat{\mathcal{S}}_{\tau}$ is the one being rendered.

#### Rendering control signals

VACE control signal is a dense, image-like representation that can be directly processed by standard video encoders. We thus directly rasterize both the pose and the depth+pose control signals as videos. We denote $\mathcal{R}^{\mathcal{C}}$ the rasterization operator under the camera $\mathcal{C}$. For the pose, we rasterize the animated skeleton $\hat{\mathcal{S}}_{\tau}$ following the standard openpose representation in other works (see (Jiang et al., 2025; Zhang et al., 2025a)) encoding 2D joint locations and limb connectivity. This yields a pose control video $c_{\mathrm{pose}}=\mathcal{R}^{\mathcal{C}}(\hat{\mathcal{S}}_{\tau})\in\mathbb{R}^{T\times H\times W\times 3}$, rendered on a black background, following the target camera viewpoint (see Figure 2). For the depth+pose control signal, we simply render the background 3D mesh built from $\mathcal{D}_{\mathrm{bg}}$ using min-max depth normalized grayscale color values, following the format that VACE uses at train time. To obtain actual depth+pose joint signal, we finally superimpose the previously rendered pose signal with the background depth rasterization to obtain $c_{\mathrm{pose+depth}}=\mathcal{R}^{\mathcal{C}}(\hat{\mathcal{S}}_{\tau},\mathcal{D}_{\mathrm{bg}})\in\mathbb{R}^{T\times H\times W\times 3}$.

### 3.3. Two-phase conditioning

Monocular depth estimates are often coarse and locally inaccurate. Conditioning solely on actor poses fails to capture camera motion, as the model interprets such motion as part of the body rather than the camera. On the other hand, conditioning on both depth and poses throughout all denoising steps can over-constrain the generation, leading to static backgrounds and the propagation of depth artifacts into high-frequency details (see Ablation, 5). To address this, we adopt a two-phase conditioning schedule that gradually relaxes depth conditioning.

Let $t$ denote the diffusion timestep. We define the conditioning signal $c(t)_{\tau}$ using a cutoff threshold $t_{\text{stop}}$:

(5)
$$ c(t)_{\tau}=\begin{cases}\mathcal{R}^{\mathcal{C}_{\tau}}(\hat{\mathcal{S}}_{\tau},\mathcal{D}_{\mathrm{bg}}),&\text{if }t\leq t_{\text{stop}},\\ \mathcal{R}^{\mathcal{C}_{\tau}}(\hat{\mathcal{S}}_{\tau}),&\text{if }t>t_{\text{stop}}.\end{cases} $$

The pose signal is derived from 3D motion recovery and target-camera alignment, and provides a stable motion constraint. We therefore keep pose conditioning throughout the full denoising process.

## 4. Experiments

### 4.1. Setup

We evaluate ActCam having an image $I_{\mathrm{ref}}$, an acting video $V_{\mathrm{act}}$, and optionally a target per-frame camera trajectory as inputs. We adopt VACE (Jiang et al., 2025) as backbone. We set the same resolution ($H{\times}W$), number of steps ($N$), and scheduler across methods.

#### Datasets.

For moving camera, we design an evaluation inspired by Uni3C (Cao et al., 2025). We select 4 camera presets with common cinematic motions and evaluate on 100 reference clips from RealisDance-Val (Zhou et al., 2025b) per preset (total 4$\times$ 100 tests). For each clip, we sample a reference $I_{\mathrm{ref}}$, extract an acting-motion signal from the original clip, and generate a new video under one of the 4 camera presets. For baselines, we input the same setup, meaning same $I_{\mathrm{ref}}$, extracted motion, camera preset. For static cameras, we use RealisDance-Val (Zhou et al., 2025b) under fixed viewpoint.

#### Baselines.

For moving camera, we compare with Uni3C (Cao et al., 2025), the most similar method in literature. Both ActCam and Uni3C are based on the same Wan 2.1 14B backbone, ensuring a fair comparison. We also test ActCam in a static camera setup by comparing against strong motion control methods without explicit camera control: Moore-AnimateAnyone (Hu et al., 2024), HumanVid (Wang et al., 2024), MimicMotion (Zhang et al., 2024), Animate-X (Tan et al., 2024), Hyper-Motion (Xu et al., 2025b), UniAnimate-DiT (Wang et al., 2025c), VACE (Jiang et al., 2025), Wan-Animate (Cheng et al., 2025), and SteadyDancer (Zhang et al., 2025a). We intentionally do not compare to camera-control-only methods, as our goal is joint control with motion.

#### Metrics.

We follow Uni3C (Cao et al., 2025) for the evaluation protocol. First, we use VBench (Huang et al., 2024a) for evaluating the visual quality of the generated videos. We evaluate Subject Consistency (SC), Background Consistency (BC), Appearance Fidelity (AF), Imaging Quality (IQ), Temporal Consistency (TC) and Motion Smoothness (MS), all higher is better. This quantifies quality-oriented generation capabilities. We also calculate the Mean Per Joint Error (MPJPE) between the estimated 3D humans in the acting video and in the generated one, to assess the quality of the joint camera and motion control. We evaluate the Sampson Error (SE) (Sampson, 1982) for geometric consistency in presence of moving camera. We also report the 3D Consistency (3D-C) and Object Control (OC) scores from WorldScore (Chen et al., 2025): 3D-C measures multi-view coherence of the generated scene, while OC quantifies the fidelity of object appearance across frames. In the comparison against methods with no camera control, we evaluate only motion quality with VBench metrics.

**Table 1.** Joint camera and character control. We evaluate against Uni3C both on VBench, focusing on generation quality, and assessing control quality (MPJPE) and geometric consistency (SE). We also use WorldScore (Chen et al., 2025) to evaluate the 3D consistency (3D-C) and object control (OC) of the generations. We outperform in all cases Uni3C, the closest baseline in our setup.

| Model                    | VBench Average$\uparrow$ | SC$\uparrow$ | BC$\uparrow$ | AF$\uparrow$ | IQ$\uparrow$ | TC$\uparrow$ | MS$\uparrow$ | MPJPE$\downarrow$ | SE$\downarrow$ | 3D-C$\uparrow$ | OC$\uparrow$ |
| ------------------------ | ------------------------ | ------------ | ------------ | ------------ | ------------ | ------------ | ------------ | ----------------- | -------------- | -------------- | ------------ |
| Uni3C (Cao et al., 2025) | 0.8370                   | 0.9084       | 0.9380       | 0.5688       | 0.6640       | 0.9607       | 0.9821       | 0.2121            | 0.5665         | 0.539          | 0.9878       |
| ActCam (Ours)            | 0.8497                   | 0.9212       | 0.9350       | 0.5767       | 0.7212       | 0.9571       | 0.9872       | 0.2087            | 0.4546         | 0.6304         | 0.9953       |

**Table 2.** Static camera comparison. We evaluate on RealisDance-Val (Zhou et al., 2025b) with a static camera using VBench (Huang et al., 2024a; Huang et al., 2024b). The improved performance of ActCam compared to alternatives using 2D keypoints as conditions advocates for the superiority of our 3D-based pipeline.

| Model                                 | Average$\uparrow$ | SC$\uparrow$ | BC$\uparrow$ | AF$\uparrow$ | IQ$\uparrow$ | TC$\uparrow$ | MS$\uparrow$ |
| ------------------------------------- | ----------------- | ------------ | ------------ | ------------ | ------------ | ------------ | ------------ |
| Moore-AnimateAnyone (Hu et al., 2024) | 83.78             | 94.65        | 94.90        | 51.56        | 66.34        | 97.16        | 98.07        |
| HumanVid (Wang et al., 2024)          | 84.68             | 93.69        | 94.94        | 55.58        | 67.45        | 97.87        | 98.52        |
| MimicMotion (Zhang et al., 2024)      | 82.27             | 92.21        | 93.60        | 52.09        | 59.67        | 97.46        | 98.61        |
| Animate-X (Tan et al., 2024)          | 82.93             | 93.39        | 95.11        | 51.72        | 60.91        | 97.79        | 98.68        |
| Hyper-Motion (Xu et al., 2025b)       | 84.04             | 93.58        | 94.97        | 52.97        | 65.52        | 98.19        | 99.01        |
| UniAnimate-DiT (Wang et al., 2025c)   | 84.29             | 94.56        | 95.44        | 52.18        | 65.52        | 98.78        | 99.24        |
| VACE (Jiang et al., 2025)             | 85.33             | 93.56        | 95.03        | 57.81        | 70.61        | 96.74        | 98.25        |
| Wan-Animate (Cheng et al., 2025)      | 84.38             | 93.06        | 94.52        | 54.47        | 66.87        | 98.42        | 98.96        |
| SteadyDancer (Zhang et al., 2025a)    | 85.15             | 93.48        | 95.18        | 56.80        | 68.45        | 97.99        | 99.02        |
| ActCam (Ours)                         | 86.47             | 95.28        | 95.83        | 58.66        | 70.83        | 98.88        | 99.34        |

### 4.2. Quantitative evaluation

![Figure 3](2605.06667v1_assets/user_study_2afc.svg)

**Figure 3.** User study. We compare with Uni3C on camera adherence (Camera) and motion faithfulness (Motion) with respect to the conditioning input, alongside overall visual quality (Visual). We considerably outperform Uni3C, the closest method to ours.

#### 4.2.1. Joint camera and motion control

We now present our main results. From Table 1, ActCam achieves higher quality/consistency scores than Uni3C and reduces motion/geometry errors under controlled camera trajectories. ActCam outperforms Uni3C in MPJPE (0.2087 vs 0.2121) and SE (0.4546 vs 0.5665), showcasing the superior potential of our conditioning mechanism for the moving camera and character. Interestingly, we also outperform Uni3C in the majority of VBench metrics, reporting significant improvements, especially in Subject Consistency (0.9212) and Imaging Quality (0.7212). In our zero-shot setup, we avoid loss of performance due to finetuning on restricted ad-hoc data for motion control. We propose also a qualitative comparison with Uni3C in Figure 10.

##### User evaluation.

As a further comparison on joint motion and camera control, we use a two-alternative forced choice (2AFC) study on 17 users with anonymized video pairs comparing ActCam against Uni3C. We use videos generating the same 4 camera presets as in Table 1, and a small subset of RealisDance-Val clips. Each trial shows two generated videos conditioned on the same inputs, alongside the reference acting video and a textual description of the camera motion. Participants then reply to questions evaluating: (1) Camera adherence: “Which video better follows the specified camera motion (viewpoint changes and stable background/parallax)?”, (2) Motion faithfulness: “Which video better matches the motion in the reference acting video (pose accuracy and smoothness)?”, and (3) Visual quality: “Which video looks more visually realistic and pleasing overall (fewer artifacts and less flicker)?”. We report the results in Figure 3. As visible, we considerably outperform Uni3C in all questions, strongly suggesting that the user preference for generated videos are aligned with the performance boost reported in Table 1.

#### 4.2.2. Motion control with static camera

We now compare against previous methods for motion control, isolating the quality of our 3D human-based motion conditioning. In Table 2, we show VBench metrics on RealisDance-Val. For fairness with others, we assume a static camera, and render only videos of characters in motion following the reference acting video. ActCam is consistently better than strong baselines in this setting, improving subject/background consistency and temporal/motion metrics while maintaining high imaging quality. For example, ActCam improves TC from 98.78 (UniAnimate-DiT, second best) to 98.88 and AF from 57.81 (VACE, second best) to 58.66, while also improving IQ from 70.61 (VACE, second best) to 70.83. We attribute this result to the structural characteristics of our 3D-based conditioning: while methods based on 2D keypoints are subject to bone deformation and occlusion issues, exploiting a 3D signal regularizes subject proportions across the video.

### 4.3. Qualitative evaluation

We now report qualitative results. Besides the reported frames, we strongly suggest to visualize the supplementary video. We include multiple results showcasing the different degrees of control of ActCam. In Figure 10, we illustrate how we can render different cameras for the same scene. Those scenarios prove the flexibility of our method across scenes, characters, and reference motion. In Figure 13, we show how the same motion with the same camera can be rendered on different scenes. In Figure 13, we include a camera variation, showing that even complex motion is preserved across scenarios. Moreover, our method is adaptable to multi-character scenarios if the backbone supports it, as shown in Figure 13.

### 4.4. Ablation studies

#### Balance of depth conditioning.

We vary the number of initial diffusion steps conditioned on both pose and depth ($N_{D}$) and observe a trade-off. This is reflected in VBench metrics reported in Figure 4. We select a canonical $N_{D}$ that balances these effects; unless stated otherwise, we use $N_{D}=0.2N$ (e.g., $N_{D}{=}2$ when $N{=}10$). From our evaluation, introducing $N_{D}$ denoising iterations with depth conditioning improves environment/camera stability, improving VBench-based evaluations. However, setting $N_{D}$ too high can over-constrain late-stage refinement, as we show in Figure 5. In there we set $N_{D}=1$, resulting in guidance on depth for all diffusion steps. As visible, in presence of dynamic elements or interacting objects, the rigid depth conditioning prevents motion, limiting the realism of the output scene. On the contrary, not benefiting from depth conditioning ($N_{D}=0$) results in ambiguities between character and camera motion, as we demonstrate in Figure 6. There, providing only pose information results in a moving character on a fixed background, failing to capture adequately the camera motion.

![Figure 4](2605.06667v1_assets/ablation_nd.svg)

**Figure 4.** Effect of $N_{D}$ on VBench score. The figure shows the average VBench scores as a function of $N_{D}$, where the conditioning switches from pose+depth to pose-only. Early switching under-constrains the generation, while late switching (low $t$) can propagate depth artifacts into high-frequency details, harming results. We set an optimal $N_{D}=0.2$.

![Figure 5](2605.06667v1_assets/go_muscu.png)

![Figure 5](2605.06667v1_assets/go_muscu.png)

**Figure 5.** Importance of conditioning schedule. Excessive depth guidance (setting $N_{D}=1$) can overly constrain the scene, producing static backgrounds under camera motion (center, red circle). Instead, $N_{D}<1$ allows to flexibly move the barbell to follow the human motion (right).

![Figure 6](2605.06667v1_assets/spiderman.png)

![Figure 6](2605.06667v1_assets/spiderman.png)

**Figure 6.** Importance of depth. Providing only pose information ($N_{D}=0$, top) for conditioning creates ambiguities between camera and character motion. Conversely, using depth yields the correct character and camera motions ($N_{D}=0.2$, bottom).

![Figure 7](2605.06667v1_assets/condition_full.png)

![Figure 7](2605.06667v1_assets/generation_full.png)

![Figure 7](2605.06667v1_assets/condition_normal.png)

![Figure 7](2605.06667v1_assets/generation_normal.png)

![Figure 7](2605.06667v1_assets/condition_full.png)

![Figure 7](2605.06667v1_assets/generation_full.png)

![Figure 7](2605.06667v1_assets/condition_normal.png)

![Figure 7](2605.06667v1_assets/generation_normal.png)

**Figure 7.** Character removal. Without removal, the reference character is captured in the depth map, yielding duplicate subjects.

![Figure 8](2605.06667v1_assets/fig8_weight_ablation.png)

![Figure 8](2605.06667v1_assets/fig8_weight_ablation.png)

**Figure 8.** Importance of scene transfer. Without scene transfer (No alignment), the condition does not respect 3D coherence. Uniform weighting improves placement but importance weighting (ours) is required to achieve best results. The red arrows (right column) show depth/positions offsets.

#### Reference character removal.

As described in Sec. 3.2, we remove the static reference character from the reconstructed scene depth before inserting the animated character. Without this step, the static geometry of the reference character interferes with the dynamic motion conditioning in the depth map, often leading to duplicated characters. Figure 7 shows a representative example: the static character imprint in the depth signal interferes with the animated actor, yielding duplication and inconsistent compositing. This proves the importance of our design decision based on character inpainting.

#### Scene transfer.

In Section 3.2, we describe how we align the composed character depth with the rendered environment depth to stabilize occlusions and prevent depth-inconsistent decomposition under difficult motions or camera changes. Without alignment, reusing the first-frame depth map can produce implausible occlusions and unstable layout when the scene contains strong depth variation or large viewpoint change. Figure 8 illustrates that depth alignment improves occlusion ordering and reduces layout/tearing artifacts around the actor during strong viewpoint changes. Our importance weighting produces depth-faithful placements, as shown in Figure 8.

## 5. Conclusion

We presented ActCam, a zero-shot method for joint camera and motion control in image-conditioned video generation. ActCam constructs camera-aligned conditioning cues from a reference image, an acting video, and a target camera preset by combining target-view pose control with target-view depth-based scene guidance, while preventing static/dynamic interference through reference character removal, geometry-aware placement, and depth alignment. To mitigate depth-induced artifacts, we introduced a two-phase conditioning schedule that uses depth only in early denoising steps to lock global structure and viewpoint changes, then relies on pose-only control for high-frequency refinement. Experiments on both static cameras and moving camera benchmarks assess the capabilities of ActCam to render high-quality videos of humans in motion. We also provided ablations and failure cases to clarify the contribution of each design choice and the remaining limitations.

![Figure 9](2605.06667v1_assets/fig9_comparison_with_conditions.png)

![Figure 9](2605.06667v1_assets/fig9_comparison_with_conditions.png)

**Figure 9.** Comparison with Uni3C. Uni3C yields suboptimal camera control (top, middle) and unrealistic character motion (bottom). In the insets, a visualization of the control signal for both Uni3C and ActCam.

![Figure 10](2605.06667v1_assets/diff_cams3.png)

![Figure 10](2605.06667v1_assets/diff_cams3.png)

**Figure 10.** Different cameras. We first show the conditioning signal and ActCam results (top two rows). In the next three rows, we variate camera movements. As visible, the character appearance and motion remain consistent.

![Figure 11](2605.06667v1_assets/diff_scenes_1.jpg)

![Figure 11](2605.06667v1_assets/diff_scenes_1.jpg)

**Figure 11.** Different scenes. We display two outputs of ActCam showing the same motion rendered on two characters in different scenes, using the same camera controls.

![Figure 12](2605.06667v1_assets/diff_scenes_2.jpg)

![Figure 12](2605.06667v1_assets/diff_scenes_2.jpg)

**Figure 12.** Different scenes and different cameras. To show the flexibility of our approach, we apply the same motion to two characters in different scenes, by also varying the camera control. ActCam still renders the correct motion.

![Figure 13](2605.06667v1_assets/fig_multichar.png)

![Figure 13](2605.06667v1_assets/fig_multichar.png)

**Figure 13.** Multi-character results. ActCam handles multiple characters by applying the scene transfer and motion fitting independently per character.

## References (53 total, showing 53)

- Bahmani et al. (2025a) S. Bahmani, I. Skorokhodov, G. Qian, A. Siarohin, W. Menapace, A. Tagliasacchi, D. B. Lindell, and S. Tulyakov Ac3d: analyzing and improving 3d camera control in video diffusion transformers. In CVPR,
- Bahmani et al. (2025b) S. Bahmani, I. Skorokhodov, A. Siarohin, W. Menapace, G. Qian, M. Vasilkovsky, H. Lee, C. Wang, J. Zou, A. Tagliasacchi, et al. Vd3d: taming large video diffusion transformers for 3d camera control. In ICLR,
- Burgert et al. (2025) R. Burgert, Y. Xu, W. Xian, O. Pilarski, P. Clausen, M. He, L. Ma, Y. Deng, L. Li, M. Mousavi, et al. Go-with-the-flow: motion-controllable video diffusion models using real-time warped noise. In CVPR,
- Cao et al. (2025) C. Cao, J. Zhou, S. Li, J. Liang, C. Yu, F. Wang, Y. Fu, and X. Xue Uni3C: unifying precisely 3d-enhanced camera and human motion controls for video generation. arXiv.
- Chen et al. (2025) H. Chen, H. Zhang, T. Pang, C. Du, and M. Lin WorldScore: a unified evaluation benchmark for world generation. In IEEE/CVF International Conference on Computer Vision (ICCV),
- Cheng et al. (2025) G. Cheng, X. Gao, L. Hu, S. Hu, M. Huang, C. Ji, J. Li, D. Meng, J. Qi, P. Qiao, Z. Shen, Y. Song, K. Sun, L. Tian, F. Wang, G. Wang, Q. Wang, Z. Wang, J. Xiao, S. Xu, B. Zhang, P. Zhang, et al. Wan-animate: unified character animation and replacement with holistic replication. arXiv.
- Chu et al. (2024) H. Chu et al. GVHMR: human motion recovery via gravity-view coordinates. In SIGGRAPH Asia,
- Courant et al. (2026) R. Courant, D. Loiseaux, X. Wang, M. Christie, and V. Kalogeiton Pulp motion: framing-aware multimodal camera and human motion generation. In International Conference on Learning Representations (ICLR),
- Gan et al. (2025) Q. Gan, Y. Ren, C. Zhang, Z. Ye, P. Xie, X. Yin, Z. Yuan, B. Peng, and J. Zhu Humandit: pose-guided diffusion transformer for long-form human motion video generation. arXiv.
- Geng et al. (2025) D. Geng, C. Herrmann, J. Hur, F. Cole, S. Zhang, T. Pfaff, T. Lopez-Guevara, Y. Aytar, M. Rubinstein, C. Sun, et al. Motion prompting: controlling video generation with motion trajectories. In CVPR,
- Guo et al. (2024) X. Guo, M. Zheng, L. Hou, Y. Gao, Y. Deng, P. Wan, D. Zhang, Y. Liu, W. Hu, Z. Zha, et al. I2v-adapter: a general image-to-video adapter for diffusion models. In SIGGRAPH,
- Guo et al. (2023) Y. Guo, C. Yang, A. Rao, Z. Liang, Y. Wang, Y. Qiao, M. Agrawala, D. Lin, and B. Dai AnimateDiff: animate your personalized text-to-image diffusion models without specific tuning. In ICLR,
- He et al. (2025) H. He, Y. Xu, Y. Guo, G. Wetzstein, B. Dai, H. Li, and C. Yang Cameractrl: enabling camera control for text-to-video generation. In ICLR,
- Hou and Chen (2024) C. Hou and Z. Chen Training-free camera control for video generation. arXiv.
- Hu et al. (2024) L. Hu, X. Gao, P. Zhang, K. Sun, B. Zhang, L. Bo, et al. Animate anyone: consistent and controllable image-to-video synthesis for character animation. In CVPR,
- Huang et al. (2025) H. Huang, Y. Zhou, J. Wang, D. Liu, F. Liu, M. Yang, and Z. Xu Move-in-2d: 2d-conditioned human motion generation. In CVPR,
- Huang et al. (2024a) Z. Huang, Y. He, J. Yu, F. Zhang, C. Si, Y. Jiang, Y. Zhang, T. Wu, Q. Jin, N. Chanpaisit, Y. Wang, X. Chen, L. Wang, D. Lin, Y. Qiao, and Z. Liu VBench: comprehensive benchmark suite for video generative models. In CVPR,
- Huang et al. (2024b) Z. Huang, F. Zhang, X. Xu, Y. He, J. Yu, Z. Dong, Q. Ma, N. Chanpaisit, C. Si, Y. Jiang, Y. Wang, X. Chen, Y. Chen, L. Wang, D. Lin, Y. Qiao, and Z. Liu VBench++: comprehensive and versatile benchmark suite for video generative models. arXiv.
- Jiang et al. (2025) Z. Jiang, Z. Han, C. Mao, J. Zhang, Y. Pan, Y. Liu, et al. VACE: all-in-one video creation and editing. arXiv.
- Juhi Marzia (2025) Juhi Marzia “Only gets better here”: Elon Musk reacts to ai-generated short film Harry Potter set in vietnam war going viral (Website) Sportskeeda. Note: Accessed: 2026-01-22
- Kuang et al. (2024) Z. Kuang, S. Cai, H. He, Y. Xu, H. Li, L. J. Guibas, and G. Wetzstein Collaborative video diffusion: consistent multi-video generation with camera control. NeurIPS.
- Kulal et al. (2023) S. Kulal, T. Brooks, A. Aiken, J. Wu, J. Yang, J. Lu, A. A. Efros, and K. K. Singh Putting people in their place: affordance-aware human insertion into scenes. In IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR),
- Liang et al. (2025) J. Liang, J. Zhou, S. Li, C. Cao, L. Sun, Y. Qian, W. Chen, and F. Wang Realismotion: decomposed human motion control and video generation in the world space. arXiv.
- Lin et al. (2024) H. Lin, J. Cho, A. Zala, and M. Bansal Ctrl-adapter: an efficient and versatile framework for adapting diverse controls to any diffusion model. arXiv.
- Ling et al. (2024) P. Ling, J. Bu, P. Zhang, X. Dong, Y. Zang, T. Wu, H. Chen, J. Wang, and Y. Jin Motionclone: training-free motion cloning for controllable video generation. arXiv.
- Liu et al. (2024) S. Liu, Z. Zeng, T. Ren, F. Li, H. Zhang, J. Yang, Q. Jiang, C. Li, J. Yang, H. Su, et al. Grounding dino: marrying dino with grounded pre-training for open-set object detection. In ECCV,
- Meng et al. (2025) Y. Meng, Z. Zhu, L. Hui, and J. Hou NVS-solver: video diffusion model as zero-shot novel view synthesizer. In ICLR,
- Mou et al. (2024) C. Mou, M. Cao, X. Wang, Z. Zhang, Y. Shan, and J. Zhang Revideo: remake a video with motion and content control. NeurIPS.
- Pardo et al. (2025) A. Pardo, F. Pizzati, T. Zhang, A. Pondaven, P. Torr, J. C. Perez, and B. Ghanem MatchDiffusion: training-free generation of match-cuts. In ICCV,
- Pondaven et al. (2025) A. Pondaven, A. Siarohin, S. Tulyakov, P. Torr, and F. Pizzati Video motion transfer with diffusion transformers. In CVPR,
- Ren et al. (2025) X. Ren, T. Shen, J. Huang, H. Ling, Y. Lu, M. Nimier-David, T. Müller, A. Keller, S. Fidler, and J. Gao GEN3C: 3d-informed world-consistent video generation with precise camera control. In CVPR,
- Sampson (1982) P. D. Sampson Fitting conic sections to “very scattered” data: an iterative refinement of the bookstein algorithm. Computer graphics and image processing.
- Tan et al. (2024) S. Tan, B. Gong, X. Wang, S. Zhang, D. Zheng, R. Zheng, K. Zheng, J. Chen, M. Yang, et al. Animate-x: universal character image animation with enhanced motion representation. In ICLR,
- Tangermann (2025) V. Tangermann OpenAI says it’s making a full hollywood movie using ai (Website) Note: Accessed: 2026-01-22
- Umeyama (1991) S. Umeyama Least-squares estimation of transformation parameters between two point patterns. IEEE T-PAMI.
- Wang et al. (2025a) B. Wang, X. Wang, C. Ni, G. Zhao, Z. Yang, Z. Zhu, M. Zhang, Y. Zhou, X. Chen, G. Huang, et al. HumanDreamer: generating controllable human-motion videos via decoupled generation. In CVPR,
- Wang et al. (2025b) R. Wang, S. Xu, C. Dai, J. Xiang, Y. Deng, X. Tong, J. Yang, et al. MoGe: unlocking accurate monocular geometry estimation for open-domain images with optimal training supervision. In CVPR,
- Wang et al. (2025c) X. Wang, S. Zhang, L. Tang, Y. Zhang, C. Gao, Y. Wang, N. Sang, et al. UniAnimate-dit: human image animation with large-scale video diffusion transformer. arXiv.
- Wang et al. (2024) Z. Wang, Y. Li, Y. Zeng, Y. Fang, Y. Guo, W. Liu, J. Tan, K. Chen, T. Xue, B. Dai, D. Lin, et al. HumanVid: demystifying training data for camera-controllable human image animation. In NeurIPS,
- Wu et al. (2024) W. Wu, Z. Li, Y. Gu, R. Zhao, Y. He, D. J. Zhang, M. Z. Shou, Y. Li, T. Gao, and D. Zhang Draganything: motion control for anything using entity representation. In ECCV,
- Xiao et al. (2024) Z. Xiao, Y. Zhou, S. Yang, and X. Pan Video diffusion models are training-free motion interpreter and controller. NeurIPS.
- Xu et al. (2025a) D. Xu, W. Nie, C. Liu, S. Liu, J. Kautz, Z. Wang, and A. Vahdat Camco: camera-controllable 3d-consistent image-to-video generation. In ICLR,
- Xu et al. (2025b) S. Xu, S. Zheng, Z. Wang, H. C. Yu, J. Chen, H. Zhang, B. Li, P. Jiang, et al. HyperMotion: dit-based pose-guided human image animation of complex motions. arXiv.
- Xu et al. (2024) Z. Xu, J. Zhang, J. H. Liew, H. Yan, J. Liu, C. Zhang, J. Feng, and M. Z. Shou Magicanimate: temporally consistent human image animation using diffusion model. In CVPR,
- Yatim et al. (2024) D. Yatim, R. Fridman, O. Bar-Tal, Y. Kasten, and T. Dekel Space-time diffusion features for zero-shot text-driven motion transfer. In CVPR,
- Yin et al. (2023) S. Yin, C. Wu, J. Liang, J. Shi, H. Li, G. Ming, and N. Duan Dragnuwa: fine-grained control in video generation by integrating text, image, and trajectory. arXiv.
- Zhang et al. (2025a) J. Zhang, S. Cao, R. Li, X. Zhao, Y. Cui, X. Hou, G. Wu, H. Chen, Y. Xu, L. Wang, K. Ma, et al. SteadyDancer: harmonized and coherent human image animation with first-frame preservation. arXiv.
- Zhang et al. (2023) L. Zhang, A. Rao, and M. Agrawala Adding conditional control to text-to-image diffusion models. In ICCV,
- Zhang et al. (2024) Y. Zhang, J. Gu, L. Wang, H. Wang, J. Cheng, Y. Zhu, F. Zou, et al. MimicMotion: high-quality human motion video generation with confidence-aware pose guidance. In ICML,
- Zhang et al. (2025b) Z. Zhang, J. Liao, M. Li, Z. Dai, B. Qiu, S. Zhu, L. Qin, and W. Wang Tora: trajectory-oriented diffusion transformer for video generation. In CVPR,
- Zhou et al. (2025a) H. Zhou, C. Wang, R. Nie, J. Liu, D. Yu, Q. Yu, and C. Wang Trackgo: a flexible and efficient method for controllable video generation. In AAAI,
- Zhou et al. (2025b) J. Zhou, Y. Wu, S. Li, M. Wei, C. Fan, W. Chen, W. Jiang, F. Wang, et al. RealisDance-dit: simple yet strong baseline towards controllable character animation in the wild. arXiv.
- Zhu et al. (2024) S. Zhu, J. L. Chen, Z. Dai, Z. Dong, Y. Xu, X. Cao, Y. Yao, H. Zhu, and S. Zhu Champ: controllable and consistent human image animation with 3d parametric guidance. In ECCV,
