# EvoC2F: Evolving Compilable Code Framework for Tool-Orchestrated LLM Agents

Tool-augmented language model agents have shown great potential in solving complex real-world tasks, but a key challenge remains balancing planning flexibility with the reliability required for production deployment. Existing approaches either execute tools sequentially without parallelism or generate unconstrained code, hindering optimization and verification. Additionally, agents that learn from experience often suffer from skill library pollution, where unverified abstractions degrade performance over time. We propose EvoC2F, a framework that redefines tool orchestration through program compilation and verified continuous learning. By constraining plan generation to a well-defined intermediate representation with explicit semantic annotations, EvoC2F enables provably correct optimizations, parallelism, and fault tolerance, while ensuring soundness guarantees. Our verification-gated code-to-function evolution process ensures that learned skills undergo rigorous testing before library admission. Experiments across diverse benchmarks demonstrate that EvoC2F outperforms existing methods, reducing latency and establishing a robust foundation for building reliable, evolving autonomous agents. Our code and datasets are available at https://anonymous.4open.science/r/EvoC2F-1DEF/.

## Contributions

- We demonstrate that tool orchestration can be formulated as a constrained compilation problem, where explicit semantic annotations on plans enable provably correct optimizations while preventing the verification and governance challenges inherent in arbitrary code generation.

- We introduce (1) a compilable Plan IR with explicit side-effect and resource semantics enabling static analysis and optimization, (2) a semantic compiler achieving 63--71% latency reduction through effect-aware parallelization with formal correctness guarantees, and (3) a verification-gated skill evolution mechanism maintaining regression rates below 1% through automated testing, contract validation, and staged deployment.

- We present comprehensive experiments across several benchmarks demonstrating state-of-the-art success rates with substantial efficiency gains. Ablation studies validate each architectural component's necessity, and sequential evaluation over 500 tasks confirms sustained capability growth through verified skill accumulation.

## EvoC2F

EvoC2F operates through two tightly coupled loops. The online execution loop compiles and executes plans with maximal efficiency under resource constraints, constructing a directed acyclic graph (DAG) from Plan IR and annotating nodes with effect types, resource dependencies, retry policies, and idempotency requirements. The compiler optimizes this DAG to minimize makespan while respecting concurrency budgets and reliability constraints. The offline learning loop analyzes successful trajectories to abstract candidate macro-skills, where candidates must pass automated unit tests, contract checks, and regression evaluations before promotion to the skill library, ensuring controlled capability growth.

## Methodology

We present EvoC2F, a framework that formulates tool orchestration as a constrained compilation problem with verified continuous learning. Our approach comprises three core components: (1) a formal Plan Intermediate Representation with explicit semantic annotations, (2) a semantic compiler that optimizes execution under resource and reliability constraints, and (3) a verification-gated skill evolution mechanism.

### Problem Formulation

We consider an environment $\mathcal{E} = (\mathcal{T}, \mathcal{R})$ where $\mathcal{T} = \{t_1, \ldots, t_n\}$ denotes atomic tools and $\mathcal{R}$ represents shared resources (databases, APIs, file systems). Each tool $t \in \mathcal{T}$ is characterized by a tuple $t = \langle \sigma_t, \epsilon_t, \rho_t, \hat{\tau}_t, \hat{c}_t \rangle$ containing input-output signature $\sigma_t: \mathcal{X}_t \rightarrow \mathcal{Y}_t$, effect type $\epsilon_t \in \{\texttt{pure}, \texttt{read}, \texttt{write}\} \times \{\texttt{local}, \texttt{external}\}$, resource footprint $\rho_t = \{(r, a) \mid r \in \mathcal{R}, a \in \{\texttt{R}, \texttt{W}\}\}$ (pairs of resources and access modes derived from tool schema declarations), and expected latency and cost $\hat{\tau}_t, \hat{c}_t \in \mathbb{R}^+$.

Given a natural language task $q$ and budget constraint $\mathcal{B} = (C_{\max}, K_{\max}, T_{\max})$ specifying limits on cost, concurrency, and deadline, we seek a plan $\pi$ and schedule $S$ that solve the following optimization problem:

$$
\begin{split}
\min_{\pi, S} \quad & \mathbb{E}_{\xi}[T_{\text{ms}}(S, \xi)] + \lambda_1 \Phi_{\text{rate}}(S) + \lambda_2 \Phi_{\text{retry}}(S) \\
\textrm{s.t.} \quad & \textstyle\sum_{v \in \pi} \hat{c}_v \leq C_{\max}, \quad \text{conc}(S) \leq K_{\max}
\end{split}
$$

where the expectation is taken over random factors $\xi$ including tool latency variation, failure events, and retry counts; $T_{\text{ms}}(S, \xi)$ denotes makespan (total execution time); $\Phi_{\text{rate}}(S) = \sum_{r} [\text{Rate}_r(S) - L_r]_+^2$ penalizes rate limit violations, with $\text{Rate}_r(S)$ measuring the peak request rate to resource $r$ over a sliding time window and $L_r$ denoting the rate limit; and $\Phi_{\text{retry}}(S) = \sum_{v} \mathbb{E}[p_{\text{fail}}(v)] \cdot n_{\text{retry}}(v) \cdot \hat{\tau}_v$ captures expected retry overhead in time units, where $p_{\text{fail}}(v)$ is the empirical failure probability and $n_{\text{retry}}(v)$ represents the expected number of retries under the configured retry policy (approximated using the maximum retry budget scaled by failure probability). The plan must additionally satisfy semantic consistency constraints detailed below.

### Plan Intermediate Representation (Plan IR)

Unlike approaches that generate arbitrary code, EvoC2F produces plans in a constrained intermediate representation amenable to static analysis and optimization.

**Plan IR.** A Plan IR is a directed acyclic graph $\pi = (V, E, \mathcal{C})$ where each node $v \in V$ represents a computational unit with attributes:

$$
v = \langle f_v, \theta_v, \epsilon_v, \rho_v, \phi_v, \kappa_v \rangle
$$

Here $f_v \in \mathcal{T} \cup \mathcal{S}$ identifies a tool or learned skill, $\theta_v$ specifies parameters potentially referencing upstream outputs via $\texttt{ref}(u, \texttt{field})$, $\epsilon_v = (e_{\text{se}}, e_{\text{env}}) \in \{\texttt{pure}, \texttt{read}, \texttt{write}\} \times \{\texttt{local}, \texttt{external}\}$ declares the effect type along two orthogonal dimensions (side-effect and environment), $\rho_v = \{(r, a) \mid r \in \mathcal{R}, a \in \{\texttt{R}, \texttt{W}\}\}$ enumerates resource accesses, $\phi_v = (n_{\max}, \gamma, \mathcal{E}_{\text{retry}}, f_{\text{fb}})$ encodes retry policy, and $\kappa_v$ provides idempotency key generation for non-pure effects.

The edge set decomposes as $E = E_{\text{data}} \cup E_{\text{res}}$, capturing distinct dependency types. Data dependencies $E_{\text{data}} = \{(u, v) \mid \theta_v \text{ references } u\}$ encode explicit information flow. To construct resource dependencies, we first establish a per-resource ordering $\prec_r$ for each resource $r \in \mathcal{R}$ by computing a topological order of the data-dependency graph $(V, E_{\text{data}})$ with deterministic tie-breaking (e.g., stable hash on node identifiers). Resource dependencies arise from potential read-write and write-read conflicts on shared state:

$$
E_{\text{res}} = \{(u, v) \mid \exists r: (r, a_u) \in \rho_u \land (r, a_v) \in \rho_v \land (a_u \neq a_v \land (a_u = \texttt{W} \lor a_v = \texttt{W})) \land u \prec_r v\}
$$

This formulation serializes read-write and write-read conflicts while permitting concurrent read-read access. Write-write conflicts are additionally enforced through synchronization edges $E_{\text{sync}}$ introduced during compilation, ensuring a complete serialization chain for all writes to each resource.

**Annotation Inference.** The resource footprint $\rho_v$ and effect type $\epsilon_v$ are derived from tool schema declarations and wrapper specifications. We define $\text{Infer}(f_v)$ as the union of all resource accesses declared in the schema or wrapper metadata for tool/skill $f_v$. For tools with incomplete or uncertain annotations, we apply a conservative policy: unknown side-effects default to $\texttt{write}$, and unknown environment defaults to $\texttt{external}$, ensuring that under-specified tools are serialized rather than incorrectly parallelized. Trace-based analysis of historical executions is used only to monotonically expand (never shrink) the declared footprints, maintaining soundness. Runtime guards detect and log any undeclared resource accesses for future refinement.

**Semantic Consistency.** A plan $\pi = (V, E, \mathcal{C})$ is semantically consistent, denoted $\textsf{Con}(\pi)$, iff: (i) $(V, E)$ is acyclic; (ii) $\forall (u,v) \in E_{\text{data}}: \text{type}(u.\text{out}) \preceq \text{type}(v.\text{in})$; (iii) $\forall v: \rho_v \supseteq \text{Infer}(f_v)$; (iv) side-effects respect the lattice $\texttt{pure} \prec \texttt{read} \prec \texttt{write}$; (v) $\forall v: e_{\text{se}}(v) \neq \texttt{pure} \Rightarrow \kappa_v \neq \varnothing$.

### Semantic Plan Compiler

The compiler transforms semantically consistent Plan IR into optimized execution schedules through a two-phase process: compile-time dependency resolution and runtime resource coordination.

**Compile-Time Scheduling.** We first construct the augmented dependency graph $G = (V, E \cup E_{\text{sync}})$. For each resource $r \in \mathcal{R}$, let $V_r^W = \{v \in V \mid (r, \texttt{W}) \in \rho_v\}$ denote nodes with write access. We compute a per-resource serial chain by ordering $V_r^W$ according to the same topological order used to establish $\prec_r$ (i.e., on $(V, E_{\text{data}})$), then adding synchronization edges $E_{\text{sync}}^r$ to enforce this chain. The combined synchronization edges $E_{\text{sync}} = \bigcup_r E_{\text{sync}}^r$ do not introduce cycles since they respect the underlying data-dependency order.

Let $s_v \in \mathbb{R}^+$ denote the scheduled start time of node $v$. The earliest start time (EST) and latest start time (LST) are computed via forward and backward passes:

$$
\begin{aligned}
\text{EST}(v) &= \max_{u \in \text{pred}(v)} \bigl(\text{EST}(u) + \hat{\tau}_u\bigr) \\
\text{LST}(v) &= \min_{w \in \text{succ}(v)} \bigl(\text{LST}(w) - \hat{\tau}_v\bigr)
\end{aligned}
$$

with boundary conditions $\text{EST}(v) = 0$ for source nodes and $\text{LST}(v) = T^* - \hat{\tau}_v$ for sink nodes, where $T^* = \max_{v \in V_{\text{sink}}} (\text{EST}(v) + \hat{\tau}_v)$ is the critical path length. Nodes with positive slack $\Delta_v = \text{LST}(v) - \text{EST}(v)$ admit scheduling flexibility.

Since DAG scheduling under resource and concurrency constraints is NP-hard in general, we employ a modified HEFT (Heterogeneous Earliest Finish Time) heuristic. Specifically: (1) nodes are prioritized by upward rank (sum of execution time along the longest path to any sink); (2) each node is greedily assigned to the earliest feasible start time that respects all dependency edges in $E \cup E_{\text{sync}}$, the concurrency limit $K_{\max}$, and resource lock availability; (3) rate limit constraints are checked via token bucket availability before scheduling; (4) if no feasible slot exists within the deadline, the node is deferred with exponential backoff.

**Runtime Resource Coordination.** For nodes accessing multiple resources, we employ lock ordering to prevent deadlocks: resources are assigned global identifiers, and a node must acquire locks in ascending order before execution. If acquisition fails within a timeout, the node releases held locks and retries with exponential backoff.

**Rate Limiting.** For each external resource $r$ with rate limit $L_r$ (requests per unit time), we instantiate a token bucket regulator with capacity $B_r$:

$$
\text{Tokens}_r(t) = \mathrm{clip}_{[0, B_r]}\Bigl(\text{Tokens}_r(0) + L_r \cdot t - N_r(t)\Bigr)
$$

where $N_r(t)$ counts requests issued by time $t$. A request proceeds only if $\text{Tokens}_r \geq 1$, whereupon one token is consumed. The penalty term $\Phi_{\text{rate}}$ in Equation 1 provides learning-time guidance to avoid rate-limit pressure, while token buckets enforce hard limits during execution.

**Fault Tolerance.** Circuit breakers monitor failure statistics within a sliding window and halt invocations when the empirical failure rate $\hat{p}_{\text{fail}}$ exceeds service-specific tolerance, preventing cascade failures. For write operations with reversible semantics (e.g., APIs providing explicit undo endpoints), the compiler generates compensation actions $\bar{v}$ following the saga pattern. We distinguish: (i) reversible writes with compensation $\bar{v}$ satisfying $\text{exec}(\bar{v}, \text{exec}(v, \sigma)) \approx \sigma$, and (ii) irreversible external effects (e.g., sending emails, financial transactions) which are logged for manual intervention but cannot be automatically rolled back.

### Skill-Augmented Planning

The planner generates Plan IR by leveraging both atomic tools $\mathcal{T}$ and learned skills from a dynamically growing library $\mathcal{S}$. Given task $q$, we first retrieve relevant skills by ranking candidates according to:

$$
\text{Score}(s, q) = \underbrace{\cos(\mathbf{e}_s, \mathbf{e}_q)}_{\text{semantic}} + \underbrace{\eta_\phi(s, q)}_{\text{learned}}
$$

where $\mathbf{e}_s, \mathbf{e}_q \in \mathbb{R}^d$ are embedding representations (obtained by encoding textual descriptions of skills and tasks) and $\eta_\phi: \mathcal{S} \times \mathcal{Q} \rightarrow \mathbb{R}$ is a lightweight MLP that ingests skill metadata (historical success rate, average cost, recency) to produce a learned adjustment. The top-$k$ skills, along with tool schemas, form the augmented context $\mathcal{C}_q$ for plan generation.

The planner $\mathcal{M}_\theta$ generates Plan IR autoregressively via constrained decoding that enforces the IR grammar:

$$
\pi^* = \arg\max_{\pi \in \Pi_{\text{valid}}} P_\theta(\pi \mid \mathcal{C}_q)
$$

where $\Pi_{\text{valid}}$ denotes the set of syntactically and semantically consistent plans.

To improve planning quality over time, we apply offline preference learning. For each completed task, trajectories are scored by a reward combining success, efficiency, and reliability:

$$
R(\tau) = \mathbf{1}[\text{succ}] - \alpha_T \frac{T(\tau)}{T_{\max}} - \alpha_C \frac{C(\tau)}{C_{\max}} - \alpha_R \frac{N_{\text{retry}}}{N_{\text{budget}}}
$$

Given preference pairs $(\tau^+, \tau^-)$ with $R(\tau^+) > R(\tau^-)$, we update the planner via Direct Preference Optimization:

$$
\begin{split}
\mathcal{L}_{\text{DPO}} = -\mathbb{E}\Bigg[ \log \sigma\Bigg( \beta \log \frac{P_\theta(\pi^+ \mid \mathcal{C}_q)}{P_{\text{ref}}(\pi^+ \mid \mathcal{C}_q)} \\
\quad - \beta \log \frac{P_\theta(\pi^- \mid \mathcal{C}_q)}{P_{\text{ref}}(\pi^- \mid \mathcal{C}_q)} \Bigg)\Bigg]
\end{split}
$$

where $P_{\text{ref}}$ is the frozen planner checkpoint from the previous training iteration. The retrieval router $\eta_\phi$ is jointly trained with a margin ranking objective on skill utility labels derived from trajectory outcomes (specifically, credit is assigned proportional to the performance delta when a skill is used versus when the same task is solved without it).

### Verification-Gated Skill Evolution

The learning module continuously analyzes execution traces to extract reusable abstractions while enforcing rigorous verification to prevent skill pollution.

**Candidate Extraction.** From successful trajectories, we identify candidate macro-skills through sequential pattern mining on canonicalized Plan IR traces. We canonicalize each DAG via topological linearization with deterministic tie-breaking, then apply PrefixSpan on linearized sequences. Let $\text{supp}(P) = |\{\tau \in \mathcal{D}: P \preceq \tau\}| / |\mathcal{D}|$ denote pattern support. High-support patterns with consistent data flow signatures are promoted to candidates. For structurally similar pattern families, we compute parameterized templates via anti-unification:

$$
\text{LGG}(P_1, P_2) = \arg\min_{P:\, P_1 \unlhd P,\, P_2 \unlhd P} \text{Cost}(P)
$$

yielding the least general generalization, where $P_1 \unlhd P$ indicates $P$ generalizes $P_1$, and $\text{Cost}(P)$ measures complexity. Candidates failing $\textsf{Con}(\pi)$ after generalization are discarded.

**Three-Stage Verification.** Candidates enter a verification pipeline: (1) Functional Testing synthesizes test suites $\mathcal{T}_s = \mathcal{T}_{\text{nom}} \cup \mathcal{T}_{\text{bnd}} \cup \mathcal{T}_{\text{err}}$ covering nominal inputs, boundary conditions, and error modes; (2) Contract Verification checks $\forall x \in \text{Dom}(s): \text{Pre}_s(x) \Rightarrow \text{Post}_s(s(x))$ via property-based testing and symbolic constraint solving; (3) Regression Assessment evaluates impact through controlled experiments:

$$
\Delta_{\text{reg}}(s) = \frac{1}{|\mathcal{H}|} \sum_{q \in \mathcal{H}} \Bigl[ \mathbf{1}[\text{fail}(q, \mathcal{S} \cup \{s\}, \xi)] - \mathbf{1}[\text{fail}(q, \mathcal{S}, \xi)] \Bigr]
$$

where $\mathcal{H}$ is a held-out task set and $\xi$ controls randomness. Skills with $\Delta_{\text{reg}} \leq 0$ passing all stages are admitted.

**Staged Deployment.** Admitted skills progress through shadow, canary, and stable phases. Shadow mode enables passive observation with atomic fallback. Canary deployment routes a traffic fraction to new skills while monitoring metrics. Skills exhibiting degradation trigger automatic demotion. This lifecycle management ensures monotonic library improvement while maintaining reliability.
