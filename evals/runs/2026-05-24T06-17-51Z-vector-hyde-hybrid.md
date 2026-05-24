# Eval run — 2026-05-24 06:17:51 UTC

**Collection:** `phase-a`  
**Top-K:** 5  
**Reranker:** `rerank=off`  
**Duration:** 25.8s  

## Summary

- Total questions: **22**
- Hits: **21** (95%)
- Near-misses: **0** (0%)
- Misses: **1** (5%)

## By category

| Category | Hit | Near | Miss |
|---|---|---|---|
| boundary | 2 | 0 | 0 |
| conceptual | 5 | 0 | 0 |
| factual | 11 | 0 | 0 |
| hard-niche-doc | 1 | 0 | 0 |
| hard-vocab-mismatch | 2 | 0 | 1 |

## Per-question results

### ✅ q01 — hit

**Question:** What is the definition of an operator according to the CNCF whitepaper?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (operator, definition, Kubernetes, controller)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.553` (page 14)
  2. `cncf-operator-whitepaper.pdf` — score `0.548` (page 3)
  3. `cloud-native-security.md` — score `0.333` (Cloud native information security)
  4. `cncf-operator-whitepaper.pdf` — score `0.333` (page 25)
  5. `cncf-operator-whitepaper.pdf` — score `0.333` (page 31)

### ✅ q02 — hit

**Question:** What are the capability levels defined for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (capability, levels)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.833` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `0.833` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `0.341` (page 9)
  4. `pod-security-admission.md` — score `0.333` (Pod Security levels)
  5. `pod-security-admission.md` — score `0.268` (Pod Security levels)

### ✅ q03 — hit

**Question:** What's the difference between a Kubernetes controller and an operator?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (controller, operator, difference)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.833` (page 8)
  2. `cncf-operator-whitepaper.pdf` — score `0.611` (page 7)
  3. `cncf-operator-whitepaper.pdf` — score `0.333` (page 16)
  4. `controlling-access.md` — score `0.250` (Admission control)
  5. `pod-lifecycle.md` — score `0.250` (delays between container restarts will always be 2s > Container probes > Types of probe > When should you use a readiness probe?)

### ✅ q04 — hit

**Question:** What security risks does the whitepaper identify for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (security, risks, RBAC)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.643` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `0.583` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `0.562` (page 13)
  4. `cncf-operator-whitepaper.pdf` — score `0.383` (page 14)
  5. `cloud-native-security.md` — score `0.250` (_Develop_ lifecycle phase {#lifecycle-phase-develop})

### ✅ q05 — hit

**Question:** What operator frameworks does the whitepaper mention?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (framework, SDK)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.667` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `0.533` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `0.500` (page 16)
  4. `cncf-operator-whitepaper.pdf` — score `0.375` (page 31)
  5. `cncf-operator-whitepaper.pdf` — score `0.333` (page 2)

### ✅ q06 — hit

**Question:** When should you use the operator pattern vs. plain Kubernetes resources?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (pattern, primitives, state, automation)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.000` (page 4)
  2. `cncf-operator-whitepaper.pdf` — score `0.667` (page 5)
  3. `cncf-operator-whitepaper.pdf` — score `0.417` (page 4)
  4. `cncf-operator-whitepaper.pdf` — score `0.393` (page 25)
  5. `cncf-operator-whitepaper.pdf` — score `0.310` (page 30)

### ✅ q07 — hit

**Question:** What are the best practices for observability in operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 1/3 (observability)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.000` (page 26)
  2. `cncf-operator-whitepaper.pdf` — score `0.583` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `0.386` (page 22)
  4. `cncf-operator-whitepaper.pdf` — score `0.325` (page 31)
  5. `cncf-operator-whitepaper.pdf` — score `0.250` (page 29)

### ✅ q08 — hit

**Question:** How should operators handle backup and recovery?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (backup, recovery, restore)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.000` (page 10)
  2. `cncf-operator-whitepaper.pdf` — score `0.500` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `0.450` (page 26)
  4. `cncf-operator-whitepaper.pdf` — score `0.361` (page 26)
  5. `cncf-operator-whitepaper.pdf` — score `0.333` (page 11)

### ✅ q09 — hit

**Question:** What does the whitepaper say about using operators outside of Kubernetes?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (outside, beyond, wider context)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.700` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `0.583` (page 26)
  3. `cncf-operator-whitepaper.pdf` — score `0.424` (page 31)
  4. `cncf-operator-whitepaper.pdf` — score `0.333` (page 3)
  5. `cncf-operator-whitepaper.pdf` — score `0.258` (page 13)

### ✅ q10 — hit

**Question:** What is the difference between an init container and a sidecar container?

**Expected source:** `init-containers.md`  
**Found at rank:** 2  
**Keywords matched:** 4/4 (init, sidecar, completion, lifecycle)

Top results:
  1. `sidecar-containers.md` — score `0.750` (Differences from init containers)
  2. `init-containers.md` — score `0.533` (Understanding init containers > Differences from sidecar containers)
  3. `cncf-operator-whitepaper.pdf` — score `0.500` (page 8)
  4. `init-containers.md` — score `0.476` (Understanding init containers > Differences from regular containers)
  5. `init-containers.md` — score `0.417`

### ✅ q11 — hit

**Question:** What QoS classes does Kubernetes assign to pods, and how is each one determined?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (Guaranteed, Burstable, BestEffort)

Top results:
  1. `pod-qos.md` — score `0.750` (Quality of Service classes)
  2. `pod-qos.md` — score `0.700`
  3. `pod-qos.md` — score `0.476` (Quality of Service classes > BestEffort)
  4. `pod-qos.md` — score `0.417` (Some behavior is independent of QoS class {#class-independent-behavior})
  5. `pod-qos.md` — score `0.333` (Quality of Service classes > Guaranteed > Criteria)

### ✅ q12 — hit

**Question:** What probe types are supported on init containers?

**Expected source:** `init-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (probe, readinessProbe, livenessProbe, startupProbe)

Top results:
  1. `init-containers.md` — score `0.500` (Understanding init containers > Differences from regular containers)
  2. `sidecar-containers.md` — score `0.500` (Resource sharing within containers > Sidecar containers and Linux cgroups {#cgroups})
  3. `init-containers.md` — score `0.450` (Understanding init containers > Differences from sidecar containers)
  4. `init-containers.md` — score `0.417` (Detailed behavior > Pod restart reasons)
  5. `init-containers.md` — score `0.333` (Understanding init containers)

### ✅ q13 — hit

**Question:** What's the default restartPolicy for a pod's containers?

**Expected source:** `pod-lifecycle.md`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (restartPolicy, Always)

Top results:
  1. `pod-lifecycle.md` — score `0.667` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Individual container restart policy and rules {#container-restart-rules})
  2. `pod-lifecycle.md` — score `0.643` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy)
  3. `pod-lifecycle.md` — score `0.450` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Sidecar containers and restart policies)
  4. `pod-lifecycle.md` — score `0.417` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Restart behavior comparison)
  5. `pod-lifecycle.md` — score `0.333` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy})

### ✅ q14 — hit

**Question:** Under memory pressure, in what order does Kubernetes evict pods?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 5/5 (evict, BestEffort, Burstable, Guaranteed, order)

Top results:
  1. `pod-qos.md` — score `0.667` (Memory QoS with cgroup v2 > Configuring memory reservation)
  2. `pod-condition.md` — score `0.500` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  3. `pod-qos.md` — score `0.433` (Quality of Service classes > BestEffort)
  4. `pod-qos.md` — score `0.341` (Quality of Service classes)
  5. `disruptions.md` — score `0.333` (Pod disruption conditions {#pod-disruption-conditions})

### ✅ q15 — hit

**Question:** How do init containers and sidecar containers differ in terms of their lifecycle and restart behavior?

**Expected source:** `init-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (restart, lifecycle, completion, run to completion)

Top results:
  1. `init-containers.md` — score `0.750` (Understanding init containers > Differences from sidecar containers)
  2. `sidecar-containers.md` — score `0.667` (Differences from init containers)
  3. `pod-lifecycle.md` — score `0.500` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Restart behavior comparison)
  4. `sidecar-containers.md` — score `0.333` (Sidecar containers in Kubernetes {#pod-sidecar-containers})
  5. `sidecar-containers.md` — score `0.300` (Sidecar containers and Pod lifecycle)

### ✅ q16 — hit

**Question:** What happens to a Guaranteed pod when the node it's running on faces resource pressure?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (Guaranteed, eviction, limits)

Top results:
  1. `pod-qos.md` — score `0.700` (Quality of Service classes)
  2. `pod-qos.md` — score `0.667` (Quality of Service classes > Burstable)
  3. `pod-qos.md` — score `0.583` (Some behavior is independent of QoS class {#class-independent-behavior})
  4. `pod-condition.md` — score `0.392` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  5. `pod-qos.md` — score `0.375` (Quality of Service classes > BestEffort)

### ✅ q17 — hit

**Question:** What are the three Pod Security Standards profiles and what does each restrict?

**Expected source:** `pod-security-standards.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (Privileged, Baseline, Restricted, profile)

Top results:
  1. `pod-security-standards.md` — score `0.625` (FAQ > Why isn't there a profile between Privileged and Baseline?)
  2. `pod-security-admission.md` — score `0.571` (Pod Security levels)
  3. `pod-security-admission.md` — score `0.417` (Pod Security levels)
  4. `pod-security-admission.md` — score `0.350`
  5. `pod-security-standards.md` — score `0.333` (FAQ > What's the difference between a security profile and a security context?)

### ✅ q18 — hit

**Question:** Can a single pod use both init containers and ephemeral containers?

**Expected source:** `ephemeral-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (init, ephemeral, container, pod)

Top results:
  1. `ephemeral-containers.md` — score `1.000` (Understanding ephemeral containers > What is an ephemeral container?)
  2. `ephemeral-containers.md` — score `0.450` (Uses for ephemeral containers)
  3. `_index.md` — score `0.444` (Pods with multiple containers {#how-pods-manage-multiple-containers})
  4. `init-containers.md` — score `0.410` (Understanding init containers > Differences from sidecar containers)
  5. `sidecar-containers.md` — score `0.312` (Differences from init containers)

### ❌ q19 — miss

**Question:** If my app writes temporary files and the pod is killed and rescheduled elsewhere, what happens to that data?

**Expected source:** `pod-lifecycle.md`  
**Found at rank:** not in top-5  
**Keywords matched:** 3/4 (storage, container, restart)

Top results:
  1. `pod-condition.md` — score `0.500` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  2. `init-containers.md` — score `0.500` (Detailed behavior)
  3. `disruptions.md` — score `0.333` (Pod disruption budgets)
  4. `init-containers.md` — score `0.333` (Detailed behavior)
  5. `disruptions.md` — score `0.250` (Pod disruption conditions {#pod-disruption-conditions})

### ✅ q20 — hit

**Question:** What identity does a pod use when it calls the Kubernetes API, and how is it assigned?

**Expected source:** `service-accounts.md`  
**Found at rank:** 2  
**Keywords matched:** 3/4 (service account, token, pod)

Top results:
  1. `multi-tenancy.md` — score `0.500` (Additional Considerations > API Priority and Fairness)
  2. `service-accounts.md` — score `0.500` (How to use service accounts {#how-to-use} > Assign a ServiceAccount to a Pod {#assign-to-pod})
  3. `service-accounts.md` — score `0.333` (How to use service accounts {#how-to-use})
  4. `multi-tenancy.md` — score `0.333` (Additional Considerations > API Priority and Fairness)
  5. `service-accounts.md` — score `0.278` (What are service accounts? {#what-are-service-accounts})

### ✅ q21 — hit

**Question:** How do I get a debugging shell inside a running pod whose image has no shell or debug tools?

**Expected source:** `ephemeral-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (ephemeral, container, debug, running)

Top results:
  1. `ephemeral-containers.md` — score `1.000` (Uses for ephemeral containers)
  2. `_index.md` — score `0.476` (Using Pods)
  3. `init-containers.md` — score `0.444` (Using init containers > Examples > Init containers in use)
  4. `user-namespaces.md` — score `0.312` (Understanding user namespaces for pods {#pods-and-userns})
  5. `init-containers.md` — score `0.298` (Using init containers > Examples)

### ✅ q22 — hit

**Question:** How can a workload ask for a GPU or other specialized hardware device?

**Expected source:** `dynamic-resource-allocation.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (resource, device, allocation)

Top results:
  1. `dynamic-resource-allocation.md` — score `0.548`
  2. `_index.md` — score `0.500` (Working with Pods > Pods and controllers)
  3. `dynamic-resource-allocation.md` — score `0.333`
  4. `_index.md` — score `0.333` (Resource requests and limits)
  5. `security-checklist.md` — score `0.250` (Pod security)
