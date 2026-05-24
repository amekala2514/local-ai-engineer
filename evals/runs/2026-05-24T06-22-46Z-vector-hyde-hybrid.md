# Eval run — 2026-05-24 06:22:46 UTC

**Collection:** `phase-a`  
**Top-K:** 5  
**Reranker:** `rerank=off`  
**Duration:** 25.8s  

## Summary

- Total questions: **22**
- Hits: **21** (95%)
- Near-misses: **1** (5%)
- Misses: **0** (0%)

## By category

| Category | Hit | Near | Miss |
|---|---|---|---|
| boundary | 1 | 1 | 0 |
| conceptual | 5 | 0 | 0 |
| factual | 11 | 0 | 0 |
| hard-niche-doc | 1 | 0 | 0 |
| hard-vocab-mismatch | 3 | 0 | 0 |

## Per-question results

### ✅ q01 — hit

**Question:** What is the definition of an operator according to the CNCF whitepaper?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (operator, definition, Kubernetes, controller)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.354` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `1.124` (page 22)
  3. `cncf-operator-whitepaper.pdf` — score `0.970` (page 14)
  4. `cncf-operator-whitepaper.pdf` — score `0.939` (page 3)
  5. `cncf-operator-whitepaper.pdf` — score `0.780` (page 13)

### ✅ q02 — hit

**Question:** What are the capability levels defined for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (capability, levels)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.846` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `1.835` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `1.145` (page 9)
  4. `pod-security-admission.md` — score `1.043` (Pod Security levels)
  5. `pod-security-admission.md` — score `1.043` (Pod Security levels)

### ✅ q03 — hit

**Question:** What's the difference between a Kubernetes controller and an operator?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (controller, operator, difference)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.876` (page 8)
  2. `cncf-operator-whitepaper.pdf` — score `1.338` (page 7)
  3. `cncf-operator-whitepaper.pdf` — score `0.980` (page 24)
  4. `cncf-operator-whitepaper.pdf` — score `0.887` (page 21)
  5. `cncf-operator-whitepaper.pdf` — score `0.857` (page 25)

### ✅ q04 — hit

**Question:** What security risks does the whitepaper identify for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (security, risks, RBAC)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.607` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `1.497` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `1.160` (page 13)
  4. `cncf-operator-whitepaper.pdf` — score `1.129` (page 14)
  5. `cncf-operator-whitepaper.pdf` — score `0.851` (page 3)

### ✅ q05 — hit

**Question:** What operator frameworks does the whitepaper mention?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (framework, SDK)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.431` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `1.381` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `1.249` (page 31)
  4. `cncf-operator-whitepaper.pdf` — score `1.065` (page 13)
  5. `cncf-operator-whitepaper.pdf` — score `0.906` (page 16)

### ✅ q06 — hit

**Question:** When should you use the operator pattern vs. plain Kubernetes resources?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (pattern, primitives, state, automation)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.894` (page 4)
  2. `cncf-operator-whitepaper.pdf` — score `1.489` (page 5)
  3. `cncf-operator-whitepaper.pdf` — score `1.394` (page 4)
  4. `cncf-operator-whitepaper.pdf` — score `1.242` (page 30)
  5. `cncf-operator-whitepaper.pdf` — score `1.177` (page 25)

### ✅ q07 — hit

**Question:** What are the best practices for observability in operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 1/3 (observability)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.826` (page 26)
  2. `cncf-operator-whitepaper.pdf` — score `1.440` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `1.228` (page 31)
  4. `cncf-operator-whitepaper.pdf` — score `1.156` (page 22)
  5. `cncf-operator-whitepaper.pdf` — score `0.934` (page 13)

### ✅ q08 — hit

**Question:** How should operators handle backup and recovery?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (backup, recovery, restore)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `2.008` (page 10)
  2. `cncf-operator-whitepaper.pdf` — score `1.280` (page 3)
  3. `cncf-operator-whitepaper.pdf` — score `1.201` (page 26)
  4. `cncf-operator-whitepaper.pdf` — score `1.165` (page 26)
  5. `cncf-operator-whitepaper.pdf` — score `0.982` (page 4)

### ⚠️ q09 — near-miss

**Question:** What does the whitepaper say about using operators outside of Kubernetes?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 1/4 (outside)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `1.623` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `1.382` (page 26)
  3. `cncf-operator-whitepaper.pdf` — score `1.352` (page 31)
  4. `cncf-operator-whitepaper.pdf` — score `1.085` (page 13)
  5. `cncf-operator-whitepaper.pdf` — score `0.806` (page 15)

### ✅ q10 — hit

**Question:** What is the difference between an init container and a sidecar container?

**Expected source:** `init-containers.md`  
**Found at rank:** 2  
**Keywords matched:** 4/4 (init, sidecar, completion, lifecycle)

Top results:
  1. `sidecar-containers.md` — score `1.537` (Differences from init containers)
  2. `init-containers.md` — score `1.421` (Understanding init containers > Differences from sidecar containers)
  3. `init-containers.md` — score `1.377`
  4. `init-containers.md` — score `1.337` (Understanding init containers > Differences from regular containers)
  5. `sidecar-containers.md` — score `1.219` (Sidecar containers in Kubernetes {#pod-sidecar-containers})

### ✅ q11 — hit

**Question:** What QoS classes does Kubernetes assign to pods, and how is each one determined?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (Guaranteed, Burstable, BestEffort)

Top results:
  1. `pod-qos.md` — score `1.522` (Quality of Service classes)
  2. `pod-qos.md` — score `1.499`
  3. `pod-qos.md` — score `1.391` (Some behavior is independent of QoS class {#class-independent-behavior})
  4. `pod-qos.md` — score `1.378` (Quality of Service classes > BestEffort)
  5. `pod-qos.md` — score `1.128` (Quality of Service classes > Burstable > Criteria)

### ✅ q12 — hit

**Question:** What probe types are supported on init containers?

**Expected source:** `init-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (probe, readinessProbe, livenessProbe, startupProbe)

Top results:
  1. `init-containers.md` — score `1.476` (Understanding init containers > Differences from sidecar containers)
  2. `init-containers.md` — score `1.321` (Detailed behavior > Pod restart reasons)
  3. `sidecar-containers.md` — score `1.265` (Differences from init containers)
  4. `pod-lifecycle.md` — score `0.998` (delays between container restarts will always be 2s > Container probes > Check mechanisms {#probe-check-methods})
  5. `pod-lifecycle.md` — score `0.966` (delays between container restarts will always be 2s > Container probes > Types of probe > When should you use a readiness probe?)

### ✅ q13 — hit

**Question:** What's the default restartPolicy for a pod's containers?

**Expected source:** `pod-lifecycle.md`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (restartPolicy, Always)

Top results:
  1. `pod-lifecycle.md` — score `1.478` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy)
  2. `pod-lifecycle.md` — score `1.468` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Individual container restart policy and rules {#container-restart-rules})
  3. `pod-lifecycle.md` — score `1.408` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Sidecar containers and restart policies)
  4. `pod-lifecycle.md` — score `1.214` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Restart behavior comparison)
  5. `pod-lifecycle.md` — score `1.095` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Example scenarios)

### ✅ q14 — hit

**Question:** Under memory pressure, in what order does Kubernetes evict pods?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 4/5 (evict, BestEffort, Burstable, Guaranteed)

Top results:
  1. `pod-qos.md` — score `1.559` (Memory QoS with cgroup v2 > Configuring memory reservation)
  2. `pod-qos.md` — score `1.346` (Quality of Service classes > BestEffort)
  3. `pod-qos.md` — score `1.272` (Quality of Service classes)
  4. `pod-qos.md` — score `1.070` (Some behavior is independent of QoS class {#class-independent-behavior})
  5. `pod-qos.md` — score `0.890` (Quality of Service classes > Burstable)

### ✅ q15 — hit

**Question:** How do init containers and sidecar containers differ in terms of their lifecycle and restart behavior?

**Expected source:** `init-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (restart, lifecycle, completion, run to completion)

Top results:
  1. `init-containers.md` — score `1.614` (Understanding init containers > Differences from sidecar containers)
  2. `sidecar-containers.md` — score `1.610` (Differences from init containers)
  3. `pod-lifecycle.md` — score `1.237` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Pod-level container restart policy > Sidecar containers and restart policies)
  4. `sidecar-containers.md` — score `1.194` (Sidecar containers and Pod lifecycle)
  5. `sidecar-containers.md` — score `1.178` (Sidecar containers in Kubernetes {#pod-sidecar-containers})

### ✅ q16 — hit

**Question:** What happens to a Guaranteed pod when the node it's running on faces resource pressure?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (Guaranteed, eviction, limits)

Top results:
  1. `pod-qos.md` — score `1.614` (Some behavior is independent of QoS class {#class-independent-behavior})
  2. `pod-qos.md` — score `1.611` (Quality of Service classes)
  3. `pod-qos.md` — score `1.386` (Quality of Service classes > BestEffort)
  4. `pod-qos.md` — score `1.338` (Quality of Service classes > Burstable)
  5. `pod-condition.md` — score `1.148` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})

### ✅ q17 — hit

**Question:** What are the three Pod Security Standards profiles and what does each restrict?

**Expected source:** `pod-security-standards.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (Privileged, Baseline, Restricted, profile)

Top results:
  1. `pod-security-standards.md` — score `1.392` (FAQ > Why isn't there a profile between Privileged and Baseline?)
  2. `pod-security-admission.md` — score `1.231`
  3. `pod-security-admission.md` — score `1.231`
  4. `pod-security-admission.md` — score `1.231`
  5. `pod-security-admission.md` — score `1.191` (Pod Security levels)

### ✅ q18 — hit

**Question:** Can a single pod use both init containers and ephemeral containers?

**Expected source:** `ephemeral-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (init, ephemeral, container, pod)

Top results:
  1. `ephemeral-containers.md` — score `1.637` (Understanding ephemeral containers > What is an ephemeral container?)
  2. `ephemeral-containers.md` — score `1.371` (Uses for ephemeral containers)
  3. `_index.md` — score `1.307` (Pods with multiple containers {#how-pods-manage-multiple-containers})
  4. `ephemeral-containers.md` — score `1.237`
  5. `init-containers.md` — score `1.071` (Understanding init containers > Differences from sidecar containers)

### ✅ q19 — hit

**Question:** If my app writes temporary files and the pod is killed and rescheduled elsewhere, what happens to that data?

**Expected source:** `pod-lifecycle.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (storage, container, restart)

Top results:
  1. `pod-lifecycle.md` — score `1.131` (Pod lifetime > Pods and fault recovery {#pod-fault-recovery})
  2. `pod-condition.md` — score `0.840` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  3. `disruptions.md` — score `0.824` (Pod disruption budgets)
  4. `init-containers.md` — score `0.769` (Detailed behavior)
  5. `init-containers.md` — score `0.759` (Detailed behavior)

### ✅ q20 — hit

**Question:** What identity does a pod use when it calls the Kubernetes API, and how is it assigned?

**Expected source:** `service-accounts.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (service account, token, pod)

Top results:
  1. `service-accounts.md` — score `1.182` (Alternatives)
  2. `service-accounts.md` — score `1.062` (What are service accounts? {#what-are-service-accounts})
  3. `service-accounts.md` — score `0.880` (How to use service accounts {#how-to-use} > Assign a ServiceAccount to a Pod {#assign-to-pod})
  4. `multi-tenancy.md` — score `0.863` (Additional Considerations > API Priority and Fairness)
  5. `multi-tenancy.md` — score `0.863` (Additional Considerations > API Priority and Fairness)

### ✅ q21 — hit

**Question:** How do I get a debugging shell inside a running pod whose image has no shell or debug tools?

**Expected source:** `ephemeral-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (ephemeral, container, debug, running)

Top results:
  1. `ephemeral-containers.md` — score `2.160` (Uses for ephemeral containers)
  2. `_index.md` — score `1.248` (Using Pods)
  3. `init-containers.md` — score `1.163` (Using init containers > Examples > Init containers in use)
  4. `init-containers.md` — score `1.050` (Using init containers > Examples > Init containers in use)
  5. `user-namespaces.md` — score `1.029` (Understanding user namespaces for pods {#pods-and-userns})

### ✅ q22 — hit

**Question:** How can a workload ask for a GPU or other specialized hardware device?

**Expected source:** `dynamic-resource-allocation.md`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (resource, device, allocation)

Top results:
  1. `dynamic-resource-allocation.md` — score `1.141`
  2. `_index.md` — score `0.955` (Working with Pods > Pods and controllers)
  3. `_index.md` — score `0.928` (Resource requests and limits)
  4. `dynamic-resource-allocation.md` — score `0.823`
  5. `dynamic-resource-allocation.md` — score `0.823`
