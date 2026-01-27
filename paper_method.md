\section{Introduction}

The rapid advancement of Large Language Models (LLMs) has catalyzed a paradigm shift in autonomous agent development, enabling systems that interact with external tools and APIs to accomplish complex real-world tasks \citep{schick2023toolformer,qin2023toolllm,patil2023gorilla}. These tool-augmented agents have demonstrated remarkable capabilities across domains ranging from data analysis and software engineering to scientific discovery and enterprise automation \citep{wang2024survey,xi2023rise}. However, a fundamental tension persists between the flexibility of natural language-driven planning and the stringent reliability requirements of production deployments—current systems often generate arbitrary code or unstructured action sequences that resist systematic optimization, verification, and governance.

Contemporary approaches to tool orchestration predominantly fall into two categories, each with distinct limitations. \textit{Reactive execution frameworks} process tool calls sequentially without holistic planning \citep{yao2022react,shinn2023reflexion}, failing to exploit inherent parallelization opportunities in many workflows and leading to suboptimal end-to-end performance. \textit{Code generation paradigms}, exemplified by recent work on executable code actions \citep{wang2024codeact}, produce flexible programs but lack formal semantic guarantees—the absence of explicit dependency and side-effect annotations renders automated reasoning, safety verification, and systematic optimization intractable. While code-based approaches achieve impressive results on isolated benchmarks, they exhibit critical limitations when deployed in enterprise environments demanding predictable latency, cost control, and auditability.

Furthermore, existing agent architectures suffer from a fundamental inability to accumulate and leverage experiential knowledge in a principled manner. Although recent work has explored skill libraries and memory mechanisms for LLM agents \citep{wang2023voyager,zhang2024proagent}, these approaches typically lack rigorous verification pipelines—learned skills may encode spurious patterns or introduce subtle regressions that propagate through subsequent task executions. The absence of systematic testing, version control, and governance mechanisms transforms skill libraries from assets into liabilities, as polluted or outdated abstractions degrade rather than enhance agent performance over time. This skill pollution problem, where unverified abstractions corrupt planning quality, remains largely unaddressed in prior work.

To address these intertwined challenges, we propose \textbf{EvoC2F} (\textbf{Evo}lving \textbf{C}ompilable \textbf{C}ode \textbf{F}ramework), a novel framework that reconceptualizes tool orchestration through the lens of program compilation and verified continuous learning. Our key insight is that by constraining plan generation to a well-defined intermediate representation (Plan IR) with explicit dependency and side-effect semantics, we enable a semantic compiler to perform provably correct optimizations—parallelization, critical path reduction, rate limiting, and fault tolerance injection—while maintaining formal guarantees about execution behavior. This compilation-centric approach transforms agent planning from an open-ended generation problem into a structured optimization problem amenable to systematic analysis and verification.

EvoC2F operates through two tightly coupled loops: an \textit{online execution loop} that compiles and executes plans with maximal efficiency under resource constraints, and an \textit{offline learning loop} that extracts reusable skills from execution traces subject to rigorous verification gates. The online loop constructs a directed acyclic graph (DAG) from the Plan IR, annotating nodes with effect types (\texttt{pure}, \texttt{read}, \texttt{write}, \texttt{external}), resource dependencies, retry policies, and idempotency requirements. The compiler then optimizes this DAG to minimize makespan while respecting concurrency budgets and reliability constraints—a multi-objective optimization that balances throughput against rate limit violations and retry storms. The offline loop analyzes successful trajectories to abstract candidate macro-skills and planning templates, but critically, these candidates must pass automated unit tests, contract checks, and regression evaluations before promotion to the skill library. This verification-gated evolution ensures that capability growth remains controlled and reversible, preventing the skill pollution observed in unverified approaches.

The contributions of this work are summarized as follows:

\begin{itemize}
    \item We introduce a \textbf{compilable plan representation} (Plan IR) with explicit side-effect and resource semantics, enabling provably correct parallelization and optimization of tool orchestration workflows. Unlike prior approaches that generate arbitrary code, our constrained IR permits static analysis for safety verification and performance optimization while maintaining expressiveness for complex real-world tasks.
    
    \item We propose a \textbf{semantic compilation framework} that transforms Plan IR into optimized execution DAGs, incorporating rate limiting, idempotency enforcement, circuit breakers, and compensation strategies as first-class compilation targets. Our compiler achieves 36--45\% latency reduction through parallelization while maintaining formal correctness guarantees and reliability under resource constraints.
    
    \item We design a \textbf{verification-gated skill evolution} mechanism that extracts reusable abstractions from execution traces while enforcing rigorous quality gates—including automated test generation, contract validation, and regression assessment—to prevent skill pollution and ensure controlled capability growth. Our staged deployment pipeline maintains regression rates below 1\% compared to 5.8--7.3\% for unverified baselines.
    
    \item We present comprehensive experiments across ToolBench, API-Bank, and TaskBench demonstrating that EvoC2F achieves state-of-the-art success rates (79.2--85.7\%) with substantial improvements in execution efficiency and long-term reliability. Ablation studies validate the necessity of each architectural component, and sequential evaluation over 500 tasks confirms sustained capability growth through verified skill accumulation.
\end{itemize}

% Fixed version - only addressing critical issues

% Fixed version - only addressing critical issues

\section{Methodology} 
We present EvoC2F, a framework that formulates tool orchestration as a constrained compilation problem with verified continuous learning. Our approach comprises three core components: (1) a formal Plan Intermediate Representation with explicit semantic annotations, (2) a semantic compiler that optimizes execution under resource and reliability constraints, and (3) a verification-gated skill evolution mechanism. 

\subsection{Problem Formulation} 
We consider an environment $\mathcal{E} = (\mathcal{T}, \mathcal{R})$ where $\mathcal{T} = \{t_1, \ldots, t_n\}$ denotes atomic tools and $\mathcal{R}$ represents shared resources (databases, APIs, file systems). Each tool $t \in \mathcal{T}$ is characterized by a tuple $t = \langle \sigma_t, \epsilon_t, \rho_t, \hat{\tau}_t, \hat{c}_t \rangle$ containing input-output signature $\sigma_t: \mathcal{X}_t \rightarrow \mathcal{Y}_t$, effect type $\epsilon_t \in \{\texttt{pure}, \texttt{read}, \texttt{write}\} \times \{\texttt{local}, \texttt{external}\}$, resource footprint $\rho_t = \{(r, a) \mid r \in \mathcal{R}, a \in \{\texttt{R}, \texttt{W}\}\}$ (pairs of resources and access modes derived from tool schema declarations), and expected latency and cost $\hat{\tau}_t, \hat{c}_t \in \mathbb{R}^+$. 

Given a natural language task $q$ and budget constraint $\mathcal{B} = (C_{\max}, K_{\max}, T_{\max})$ specifying limits on cost, concurrency, and deadline, we seek a plan $\pi$ and schedule $S$ that solve the following optimization problem: 
\begin{equation} 
\begin{split} 
\min_{\pi, S} \quad & \mathbb{E}_{\xi}[T_{\text{ms}}(S, \xi)] + \lambda_1 \Phi_{\text{rate}}(S) + \lambda_2 \Phi_{\text{retry}}(S) \\ 
\textrm{s.t.} \quad & \textstyle\sum_{v \in \pi} \hat{c}_v \leq C_{\max}, \quad \text{conc}(S) \leq K_{\max} 
\end{split} 
\end{equation} 
where the expectation is taken over random factors $\xi$ including tool latency variation, failure events, and retry counts; $T_{\text{ms}}(S, \xi)$ denotes makespan (total execution time); $\Phi_{\text{rate}}(S) = \sum_{r} [\text{Rate}_r(S) - L_r]_+^2$ penalizes rate limit violations, with $\text{Rate}_r(S)$ measuring the peak request rate to resource $r$ over a sliding time window and $L_r$ denoting the rate limit; and $\Phi_{\text{retry}}(S) = \sum_{v} \mathbb{E}[p_{\text{fail}}(v)] \cdot n_{\text{retry}}(v) \cdot \hat{\tau}_v$ captures expected retry overhead in time units, where $p_{\text{fail}}(v)$ is the empirical failure probability and $n_{\text{retry}}(v)$ represents the expected number of retries under the configured retry policy (approximated using the maximum retry budget scaled by failure probability). The plan must additionally satisfy semantic consistency constraints detailed in Section~\ref{sec:plan_ir}. 

\subsection{Plan Intermediate Representation} 
\label{sec:plan_ir} 
Unlike approaches that generate arbitrary code, EvoC2F produces plans in a constrained intermediate representation amenable to static analysis and optimization. 

\begin{definition}[Plan IR] 
A Plan IR is a directed acyclic graph $\pi = (V, E, \mathcal{C})$ where each node $v \in V$ represents a computational unit with attributes: 
\begin{equation} 
v = \langle f_v, \theta_v, \epsilon_v, \rho_v, \phi_v, \kappa_v \rangle 
\end{equation} 
Here $f_v \in \mathcal{T} \cup \mathcal{S}$ identifies a tool or learned skill, $\theta_v$ specifies parameters potentially referencing upstream outputs via $\texttt{ref}(u, \texttt{field})$, $\epsilon_v = (e_{\text{se}}, e_{\text{env}}) \in \{\texttt{pure}, \texttt{read}, \texttt{write}\} \times \{\texttt{local}, \texttt{external}\}$ declares the effect type along two orthogonal dimensions (side-effect and environment), $\rho_v = \{(r, a) \mid r \in \mathcal{R}, a \in \{\texttt{R}, \texttt{W}\}\}$ enumerates resource accesses, $\phi_v = (n_{\max}, \gamma, \mathcal{E}_{\text{retry}}, f_{\text{fb}})$ encodes retry policy, and $\kappa_v$ provides idempotency key generation for non-pure effects. 
\end{definition} 

The edge set decomposes as $E = E_{\text{data}} \cup E_{\text{res}}$, capturing distinct dependency types. Data dependencies $E_{\text{data}} = \{(u, v) \mid \theta_v \text{ references } u\}$ encode explicit information flow. To construct resource dependencies, we first establish a per-resource ordering $\prec_r$ for each resource $r \in \mathcal{R}$ by computing a topological order of the data-dependency graph $(V, E_{\text{data}})$ with deterministic tie-breaking (e.g., stable hash on node identifiers). Resource dependencies arise from potential read-write and write-read conflicts on shared state: 
\begin{equation} 
E_{\text{res}} = \left\{(u, v) \;\middle|\; \begin{array}{l} 
\exists r: (r, a_u) \in \rho_u \land (r, a_v) \in \rho_v \\ 
\land\; (a_u \neq a_v \land (a_u = \texttt{W} \lor a_v = \texttt{W})) \land u \prec_r v 
\end{array} \right\} 
\end{equation} 
This formulation serializes read-write and write-read conflicts while permitting concurrent read-read access. Write-write conflicts are additionally enforced through synchronization edges $E_{\text{sync}}$ introduced during compilation (Section~\ref{sec:compiler}), ensuring a complete serialization chain for all writes to each resource.

\paragraph{Annotation Inference.} 
The resource footprint $\rho_v$ and effect type $\epsilon_v$ are derived from tool schema declarations and wrapper specifications. We define $\text{Infer}(f_v)$ as the union of all resource accesses declared in the schema or wrapper metadata for tool/skill $f_v$. For tools with incomplete or uncertain annotations, we apply a conservative policy: unknown side-effects default to $\texttt{write}$, and unknown environment defaults to $\texttt{external}$, ensuring that under-specified tools are serialized rather than incorrectly parallelized. Trace-based analysis of historical executions is used only to monotonically expand (never shrink) the declared footprints, maintaining soundness. Runtime guards detect and log any undeclared resource accesses for future refinement.

\begin{definition}[Semantic Consistency] 
A plan $\pi = (V, E, \mathcal{C})$ is semantically consistent, denoted $\textsf{Con}(\pi)$, iff: (i) $(V, E)$ is acyclic; (ii) $\forall (u,v) \in E_{\text{data}}: \text{type}(u.\text{out}) \preceq \text{type}(v.\text{in})$; (iii) $\forall v: \rho_v \supseteq \text{Infer}(f_v)$; (iv) side-effects respect the lattice $\texttt{pure} \prec \texttt{read} \prec \texttt{write}$; (v) $\forall v: e_{\text{se}}(v) \neq \texttt{pure} \Rightarrow \kappa_v \neq \varnothing$. 
\end{definition} 

\subsection{Semantic Plan Compiler}
\label{sec:compiler}

The compiler transforms semantically consistent Plan IR into optimized execution schedules through a two-phase process: compile-time dependency resolution and runtime resource coordination.

\paragraph{Compile-Time Scheduling.} 
We first construct the augmented dependency graph $G = (V, E \cup E_{\text{sync}})$. For each resource $r \in \mathcal{R}$, let $V_r^W = \{v \in V \mid (r, \texttt{W}) \in \rho_v\}$ denote nodes with write access. We compute a per-resource serial chain by ordering $V_r^W$ according to the same topological order used to establish $\prec_r$ (i.e., on $(V, E_{\text{data}})$), then adding synchronization edges $E_{\text{sync}}^r$ to enforce this chain. The combined synchronization edges $E_{\text{sync}} = \bigcup_r E_{\text{sync}}^r$ do not introduce cycles since they respect the underlying data-dependency order.

Let $s_v \in \mathbb{R}^+$ denote the scheduled start time of node $v$. The earliest start time (EST) and latest start time (LST) are computed via forward and backward passes:
\begin{align}
\text{EST}(v) &= \max_{u \in \text{pred}(v)} \bigl(\text{EST}(u) + \hat{\tau}_u\bigr) \\
\text{LST}(v) &= \min_{w \in \text{succ}(v)} \bigl(\text{LST}(w) - \hat{\tau}_v\bigr)
\end{align}
with boundary conditions $\text{EST}(v) = 0$ for source nodes and $\text{LST}(v) = T^* - \hat{\tau}_v$ for sink nodes, where $T^* = \max_{v \in V_{\text{sink}}} (\text{EST}(v) + \hat{\tau}_v)$ is the critical path length. Nodes with positive slack $\Delta_v = \text{LST}(v) - \text{EST}(v)$ admit scheduling flexibility.

Since DAG scheduling under resource and concurrency constraints is NP-hard in general, we employ a modified HEFT (Heterogeneous Earliest Finish Time) heuristic. Specifically: (1) nodes are prioritized by upward rank (sum of execution time along the longest path to any sink); (2) each node is greedily assigned to the earliest feasible start time that respects all dependency edges in $E \cup E_{\text{sync}}$, the concurrency limit $K_{\max}$, and resource lock availability; (3) rate limit constraints are checked via token bucket availability before scheduling; (4) if no feasible slot exists within the deadline, the node is deferred with exponential backoff.

\paragraph{Runtime Resource Coordination.} 
For nodes accessing multiple resources, we employ lock ordering to prevent deadlocks: resources are assigned global identifiers, and a node must acquire locks in ascending order before execution. If acquisition fails within a timeout, the node releases held locks and retries with exponential backoff.

\paragraph{Rate Limiting.} 
For each external resource $r$ with rate limit $L_r$ (requests per unit time), we instantiate a token bucket regulator with capacity $B_r$:
\begin{equation}
\text{Tokens}_r(t) = \mathrm{clip}_{[0, B_r]}\Bigl(\text{Tokens}_r(0) + L_r \cdot t - N_r(t)\Bigr)
\end{equation}
where $N_r(t)$ counts requests issued by time $t$. A request proceeds only if $\text{Tokens}_r \geq 1$, whereupon one token is consumed. The penalty term $\Phi_{\text{rate}}$ in Equation~1 provides learning-time guidance to avoid rate-limit pressure, while token buckets enforce hard limits during execution.

\paragraph{Fault Tolerance.} 
Circuit breakers monitor failure statistics within a sliding window and halt invocations when the empirical failure rate $\hat{p}_{\text{fail}}$ exceeds service-specific tolerance, preventing cascade failures. For write operations with reversible semantics (e.g., APIs providing explicit undo endpoints), the compiler generates compensation actions $\bar{v}$ following the saga pattern. We distinguish: (i) \emph{reversible writes} with compensation $\bar{v}$ satisfying $\text{exec}(\bar{v}, \text{exec}(v, \sigma)) \approx \sigma$, and (ii) \emph{irreversible external effects} (e.g., sending emails, financial transactions) which are logged for manual intervention but cannot be automatically rolled back.

\begin{assumption}[Annotation Soundness]
\label{ass:annotation}
For all nodes $v \in V$, the declared resource footprint $\rho_v$ is a superset of actual resources accessed during execution, and the declared effect type $\epsilon_v$ is an upper bound under the respective lattice orderings.
\end{assumption}

\begin{proposition}[Parallelization Soundness]
Given Assumption~\ref{ass:annotation} and a semantically consistent plan $\pi$ with $\textsf{Con}(\pi)$, let $S^*$ be the schedule produced by the compiler. For any nodes $u, v$ with overlapping execution intervals under $S^*$, either $\rho_u \cap \rho_v = \varnothing$, or $\forall r \in \rho_u \cap \rho_v: (r,\texttt{R}) \in \rho_u \land (r,\texttt{R}) \in \rho_v$.
\end{proposition}

\begin{proof}
Read-write and write-read conflicts on any shared resource $r$ are serialized by $E_{\text{res}}$ as defined in Equation~3. Write-write conflicts are additionally serialized by the per-resource chain $E_{\text{sync}}^r$ (which totally orders $V_r^W$). The scheduler respects all edges in $E \cup E_{\text{sync}}$, enforcing $s_v \geq s_u + \hat{\tau}_u$ for $(u,v) \in E \cup E_{\text{sync}}$. By Assumption~\ref{ass:annotation}, actual resource accesses are contained within declared footprints. Thus concurrent execution under $S^*$ implies no conflicting access. \qed
\end{proof}


\subsection{Skill-Augmented Planning} 
The planner generates Plan IR by leveraging both atomic tools $\mathcal{T}$ and learned skills from a dynamically growing library $\mathcal{S}$. Given task $q$, we first retrieve relevant skills by ranking candidates according to: 
\begin{equation} 
\text{Score}(s, q) = \underbrace{\cos(\mathbf{e}_s, \mathbf{e}_q)}_{\text{semantic}} + \underbrace{\eta_\phi(s, q)}_{\text{learned}} 
\end{equation} 
where $\mathbf{e}_s, \mathbf{e}_q \in \mathbb{R}^d$ are embedding representations (obtained by encoding textual descriptions of skills and tasks) and $\eta_\phi: \mathcal{S} \times \mathcal{Q} \rightarrow \mathbb{R}$ is a lightweight MLP that ingests skill metadata (historical success rate, average cost, recency) to produce a learned adjustment. The top-$k$ skills, along with tool schemas, form the augmented context $\mathcal{C}_q$ for plan generation. 

The planner $\mathcal{M}_\theta$ generates Plan IR autoregressively via constrained decoding that enforces the IR grammar: 
\begin{equation} 
\pi^* = \argmax_{\pi \in \Pi_{\text{valid}}} P_\theta(\pi \mid \mathcal{C}_q) 
\end{equation} 
where $\Pi_{\text{valid}}$ denotes the set of syntactically and semantically consistent plans. 

To improve planning quality over time, we apply offline preference learning. For each completed task, trajectories are scored by a reward combining success, efficiency, and reliability: 
\begin{equation} 
R(\tau) = \mathbf{1}[\text{succ}] - \alpha_T \frac{T(\tau)}{T_{\max}} - \alpha_C \frac{C(\tau)}{C_{\max}} - \alpha_R \frac{N_{\text{retry}}}{N_{\text{budget}}} 
\end{equation} 
Given preference pairs $(\tau^+, \tau^-)$ with $R(\tau^+) > R(\tau^-)$, we update the planner via Direct Preference Optimization: 
\begin{equation} 
\mathcal{L}_{\text{DPO}} = -\mathbb{E}\Bigl[\log \sigma\Bigl( \beta \log \frac{P_\theta(\pi^+ \mid \mathcal{C}_q)}{P_{\text{ref}}(\pi^+ \mid \mathcal{C}_q)} - \beta \log \frac{P_\theta(\pi^- \mid \mathcal{C}_q)}{P_{\text{ref}}(\pi^- \mid \mathcal{C}_q)} \Bigr)\Bigr] 
\end{equation} 
where $P_{\text{ref}}$ is the frozen planner checkpoint from the previous training iteration. The retrieval router $\eta_\phi$ is jointly trained with a margin ranking objective on skill utility labels derived from trajectory outcomes (specifically, credit is assigned proportional to the performance delta when a skill is used versus when the same task is solved without it).

\subsection{Verification-Gated Skill Evolution} 
The learning module continuously analyzes execution traces to extract reusable abstractions, but enforces rigorous verification to prevent skill pollution and error amplification. 

\paragraph{Candidate Extraction.} 
From successful trajectory $\tau = \{(v_i, x_i, y_i, t_i)\}_{i=1}^{|\tau|}$, we identify candidate macro-skills through sequential pattern mining on canonicalized Plan IR traces. Specifically, we canonicalize each DAG via topological linearization (using a deterministic ordering on node IDs for tie-breaking), then apply sequential pattern mining algorithms (e.g., PrefixSpan) on these linearized sequences. Let $\text{supp}(P) = |\{\tau \in \mathcal{D}: P \preceq \tau\}| / |\mathcal{D}|$ denote the support of pattern $P$ in trajectory corpus $\mathcal{D}$, where $P \preceq \tau$ indicates that $P$ appears as a contiguous subsequence in the linearized representation of $\tau$. High-support patterns with consistent data flow signatures are promoted to candidates. 

For pattern families exhibiting structural similarity, we compute parameterized templates via anti-unification at the Plan IR level: 
\begin{equation} 
\text{LGG}(P_1, P_2) = \argmin_{P:\, P_1 \unlhd P,\, P_2 \unlhd P} \text{Cost}(P) 
\end{equation} 
yielding the least general generalization that subsumes both instances, where $P_1 \unlhd P$ indicates that pattern $P$ is a generalization of $P_1$ (i.e., $P_1$ is an instance of the more general template $P$), and $\text{Cost}(P)$ measures the generalization complexity (e.g., number of introduced parameters or wildcards). During abstraction, we simultaneously generate type constraints and contract placeholders; candidates failing to satisfy $\textsf{Con}(\pi)$ after generalization are discarded or retained only as non-executable planning suggestions. 

\paragraph{Three-Stage Verification.} 
Candidates enter a verification pipeline before library admission: 

\emph{Stage 1: Functional Testing.} We synthesize test suites $\mathcal{T}_s = \mathcal{T}_{\text{nom}} \cup \mathcal{T}_{\text{bnd}} \cup \mathcal{T}_{\text{err}}$ by: (i) replaying observed inputs from successful traces ($\mathcal{T}_{\text{nom}}$); (ii) generating boundary-condition tests by perturbing inputs to edge values (empty strings, null values, min/max numeric ranges, schema limit values) and using property-based testing frameworks ($\mathcal{T}_{\text{bnd}}$); and (iii) injecting expected failure modes such as timeouts, HTTP 429/5xx errors, malformed responses, and resource unavailability ($\mathcal{T}_{\text{err}}$). Each test must produce expected outputs or gracefully handle errors.

\emph{Stage 2: Contract Verification.} We verify that inferred pre-conditions imply post-conditions: $\forall x \in \text{Dom}(s): \text{Pre}_s(x) \Rightarrow \text{Post}_s(s(x))$. Pre- and post-conditions are derived from: (a) schema declarations and wrapper contracts; (b) invariants mined from execution traces (e.g., output ranges, field presence); and (c) template-based contracts instantiated for common patterns. Verification is performed via lightweight randomized testing (QuickCheck-style property checking) combined with symbolic constraint solving when feasible.

\emph{Stage 3: Regression Assessment.} We evaluate impact through controlled experiments at two levels: 
\begin{itemize} 
\item \textbf{Isolated skill correctness}: Direct invocation of the skill on held-out inputs, bypassing the planner, to measure intrinsic reliability. 
\item \textbf{End-to-end controlled evaluation}: For a held-out task set $\mathcal{H}$, we compare performance with the skill enabled versus disabled, controlling for planner stochasticity via fixed random seeds and identical retrieval candidate sets: 
\end{itemize} 
\begin{equation} 
\Delta_{\text{reg}}(s) = \frac{1}{|\mathcal{H}|} \sum_{q \in \mathcal{H}} \Bigl[ \mathbf{1}[\text{fail}(q, \mathcal{S} \cup \{s\}, \xi)] - \mathbf{1}[\text{fail}(q, \mathcal{S}, \xi)] \Bigr] 
\end{equation} 
where $\xi$ denotes the controlled random state. Skills with $\Delta_{\text{reg}} \leq 0$ that pass functional and contract verification are admitted. 

\paragraph{Staged Deployment.} 
Newly admitted skills enter a deployment pipeline progressing through shadow, canary, and stable phases. In shadow mode, skills appear in planning context but execution falls back to atomic decomposition, allowing passive observation. Canary deployment routes a fraction of compatible traffic to the new skill while monitoring success metrics. Promotion to stable status occurs after sufficient usage volume with sustained performance. Conversely, skills exhibiting degradation trigger automatic demotion, and persistent underperformers are deprecated. This lifecycle management ensures the skill library improves monotonically while maintaining production reliability.