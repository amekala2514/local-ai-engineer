# Eval run — 2026-05-24 05:31:12 UTC

**Collection:** `phase-a`  
**Top-K:** 5  
**Reranker:** `rerank=off`  
**Duration:** 6.6s  

## Summary

- Total questions: **18**
- Hits: **15** (83%)
- Near-misses: **1** (6%)
- Misses: **2** (11%)

## By category

| Category | Hit | Near | Miss |
|---|---|---|---|
| boundary | 1 | 1 | 0 |
| conceptual | 3 | 0 | 2 |
| factual | 11 | 0 | 0 |

## Per-question results

### ✅ q01 — hit

**Question:** What is the definition of an operator according to the CNCF whitepaper?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (operator, definition, Kubernetes, controller)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.851` (page 3)
  2. `cncf-operator-whitepaper.pdf` — score `0.835` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `0.833` (page 5)
  4. `cncf-operator-whitepaper.pdf` — score `0.826` (page 9)
  5. `cncf-operator-whitepaper.pdf` — score `0.822` (page 4)

### ✅ q02 — hit

**Question:** What are the capability levels defined for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (capability, levels)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.661` (page 25)
  2. `cncf-operator-whitepaper.pdf` — score `0.657` (page 31)
  3. `pod-security-admission.md` — score `0.649` (Pod Security levels)
  4. `pod-security-admission.md` — score `0.649` (Pod Security levels)
  5. `pod-security-admission.md` — score `0.649` (Pod Security levels)

### ✅ q03 — hit

**Question:** What's the difference between a Kubernetes controller and an operator?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (controller, operator, difference)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.694` (page 7)
  2. `cncf-operator-whitepaper.pdf` — score `0.687` (page 24)
  3. `cncf-operator-whitepaper.pdf` — score `0.679` (page 8)
  4. `cncf-operator-whitepaper.pdf` — score `0.678` (page 5)
  5. `cncf-operator-whitepaper.pdf` — score `0.678` (page 31)

### ✅ q04 — hit

**Question:** What security risks does the whitepaper identify for operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (security, risks, RBAC)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.770` (page 14)
  2. `cncf-operator-whitepaper.pdf` — score `0.763` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `0.762` (page 13)
  4. `cncf-operator-whitepaper.pdf` — score `0.740` (page 31)
  5. `cncf-operator-whitepaper.pdf` — score `0.730` (page 13)

### ✅ q05 — hit

**Question:** What operator frameworks does the whitepaper mention?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 1/2 (framework)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.781` (page 31)
  2. `cncf-operator-whitepaper.pdf` — score `0.773` (page 31)
  3. `cncf-operator-whitepaper.pdf` — score `0.768` (page 3)
  4. `cncf-operator-whitepaper.pdf` — score `0.764` (page 5)
  5. `cncf-operator-whitepaper.pdf` — score `0.757` (page 4)

### ✅ q06 — hit

**Question:** When should you use the operator pattern vs. plain Kubernetes resources?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 3/4 (pattern, state, automation)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.700` (page 4)
  2. `cncf-operator-whitepaper.pdf` — score `0.653` (page 23)
  3. `cncf-operator-whitepaper.pdf` — score `0.653` (page 5)
  4. `cncf-operator-whitepaper.pdf` — score `0.647` (page 18)
  5. `cncf-operator-whitepaper.pdf` — score `0.637` (page 25)

### ❌ q07 — miss

**Question:** What are the best practices for observability in operators?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** not in top-5  
**Keywords matched:** 2/3 (observability, metrics)

Top results:
  1. `pod-security-admission.md` — score `0.672` (VERSION must be a valid Kubernetes minor version, or `latest`. > Metrics)
  2. `pod-security-admission.md` — score `0.672` (VERSION must be a valid Kubernetes minor version, or `latest`. > Metrics)
  3. `pod-security-admission.md` — score `0.672` (VERSION must be a valid Kubernetes minor version, or `latest`. > Metrics)
  4. `user-namespaces.md` — score `0.649` ((110 is the default limit for number of pods on the node) > Metrics and observability)
  5. `cloud-native-security.md` — score `0.645` (_Runtime_ lifecycle phase {#lifecycle-phase-runtime} > Observability and runtime security)

### ❌ q08 — miss

**Question:** How should operators handle backup and recovery?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** not in top-5  
**Keywords matched:** 0/3 (none)

Top results:
  1. `secrets-good-practices.md` — score `0.656` (Cluster administrators > Configure least-privilege access to Secrets {#least-privilege-secrets})
  2. `secrets-good-practices.md` — score `0.656` (Developers)
  3. `secrets-good-practices.md` — score `0.652` (Cluster administrators > Improve etcd management policies)
  4. `secrets-good-practices.md` — score `0.649` (Cluster administrators)
  5. `secrets-good-practices.md` — score `0.646`

### ⚠️ q09 — near-miss

**Question:** What does the whitepaper say about using operators outside of Kubernetes?

**Expected source:** `Operator-WhitePaper`  
**Found at rank:** 1  
**Keywords matched:** 1/4 (outside)

Top results:
  1. `cncf-operator-whitepaper.pdf` — score `0.709` (page 15)
  2. `cncf-operator-whitepaper.pdf` — score `0.701` (page 14)
  3. `cncf-operator-whitepaper.pdf` — score `0.691` (page 15)
  4. `cncf-operator-whitepaper.pdf` — score `0.677` (page 13)
  5. `cncf-operator-whitepaper.pdf` — score `0.671` (page 17)

### ✅ q10 — hit

**Question:** What is the difference between an init container and a sidecar container?

**Expected source:** `init-containers.md`  
**Found at rank:** 2  
**Keywords matched:** 4/4 (init, sidecar, completion, lifecycle)

Top results:
  1. `sidecar-containers.md` — score `0.835` (Differences from init containers)
  2. `init-containers.md` — score `0.827` (Understanding init containers > Differences from sidecar containers)
  3. `init-containers.md` — score `0.823`
  4. `sidecar-containers.md` — score `0.809` (Sidecar containers in Kubernetes {#pod-sidecar-containers})
  5. `sidecar-containers.md` — score `0.799` (Resource sharing within containers)

### ✅ q11 — hit

**Question:** What QoS classes does Kubernetes assign to pods, and how is each one determined?

**Expected source:** `pod-qos.md`  
**Found at rank:** 1  
**Keywords matched:** 3/3 (Guaranteed, Burstable, BestEffort)

Top results:
  1. `pod-qos.md` — score `0.832` (Quality of Service classes > BestEffort > Criteria)
  2. `pod-qos.md` — score `0.830` (Quality of Service classes > Burstable > Criteria)
  3. `pod-qos.md` — score `0.826` (Quality of Service classes > BestEffort)
  4. `pod-qos.md` — score `0.825` (Quality of Service classes)
  5. `pod-qos.md` — score `0.823` (Quality of Service classes > Burstable)

### ✅ q12 — hit

**Question:** What probe types are supported on init containers?

**Expected source:** `init-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (probe, readinessProbe, livenessProbe, startupProbe)

Top results:
  1. `init-containers.md` — score `0.753` (Understanding init containers > Differences from regular containers)
  2. `_index.md` — score `0.741` (Container probes)
  3. `init-containers.md` — score `0.723` (Understanding init containers > Differences from sidecar containers)
  4. `init-containers.md` — score `0.720` (Using init containers > Examples)
  5. `sidecar-containers.md` — score `0.720` (Differences from init containers)

### ✅ q13 — hit

**Question:** What's the default restartPolicy for a pod's containers?

**Expected source:** `pod-lifecycle.md`  
**Found at rank:** 1  
**Keywords matched:** 2/2 (restartPolicy, Always)

Top results:
  1. `pod-lifecycle.md` — score `0.786` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Restart All Containers {#restart-all-containers} > How in-place Pod restarts work)
  2. `pod-lifecycle.md` — score `0.786` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Individual container restart policy and rules {#container-restart-rules})
  3. `pod-lifecycle.md` — score `0.777` (delays between container restarts will always be 2s > Pod conditions)
  4. `pod-lifecycle.md` — score `0.777` (How Pods handle problems with containers {#container-restarts} > Container restarts {#restart-policy} > Restart All Containers {#restart-all-containers})
  5. `pod-lifecycle.md` — score `0.776`

### ✅ q14 — hit

**Question:** Under memory pressure, in what order does Kubernetes evict pods?

**Expected source:** `pod-qos.md`  
**Found at rank:** 4  
**Keywords matched:** 5/5 (evict, BestEffort, Burstable, Guaranteed, order)

Top results:
  1. `pod-condition.md` — score `0.798` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  2. `disruptions.md` — score `0.780` (Pod disruption conditions {#pod-disruption-conditions})
  3. `disruptions.md` — score `0.777` (Pod disruption budgets)
  4. `pod-qos.md` — score `0.772` (Quality of Service classes)
  5. `advanced-pod-config.md` — score `0.756` (PriorityClasses > Built-in PriorityClasses)

### ✅ q15 — hit

**Question:** How do init containers and sidecar containers differ in terms of their lifecycle and restart behavior?

**Expected source:** `init-containers.md`  
**Found at rank:** 3  
**Keywords matched:** 4/4 (restart, lifecycle, completion, run to completion)

Top results:
  1. `sidecar-containers.md` — score `0.839` (Sidecar containers and Pod lifecycle)
  2. `sidecar-containers.md` — score `0.831` (Sidecar containers and Pod lifecycle > Jobs with sidecar containers)
  3. `init-containers.md` — score `0.828` (Understanding init containers > Differences from sidecar containers)
  4. `sidecar-containers.md` — score `0.806` (Differences from init containers)
  5. `sidecar-containers.md` — score `0.786` (Sidecar containers in Kubernetes {#pod-sidecar-containers})

### ✅ q16 — hit

**Question:** What happens to a Guaranteed pod when the node it's running on faces resource pressure?

**Expected source:** `pod-qos.md`  
**Found at rank:** 2  
**Keywords matched:** 3/4 (Guaranteed, eviction, limits)

Top results:
  1. `disruptions.md` — score `0.749` (Pod disruption budgets)
  2. `pod-qos.md` — score `0.747` (Quality of Service classes > Burstable)
  3. `pod-qos.md` — score `0.745` (Quality of Service classes)
  4. `pod-condition.md` — score `0.734` (Other Pod conditions {#other-pod-conditions} > DisruptionTarget {#disruption-target})
  5. `disruptions.md` — score `0.723` (Pod disruption conditions {#pod-disruption-conditions})

### ✅ q17 — hit

**Question:** What are the three Pod Security Standards profiles and what does each restrict?

**Expected source:** `pod-security-standards.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (Privileged, Baseline, Restricted, profile)

Top results:
  1. `pod-security-standards.md` — score `0.740` (FAQ > Why isn't there a profile between Privileged and Baseline?)
  2. `pod-security-admission.md` — score `0.737` (Pod Security levels)
  3. `pod-security-admission.md` — score `0.737` (Pod Security levels)
  4. `pod-security-admission.md` — score `0.737` (Pod Security levels)
  5. `linux-kernel-security-constraints.md` — score `0.726` (Security features in the Linux kernel {#linux-security-features} > AppArmor and SELinux: policy-based mandatory access control {#policy-based-mac} > AppArmor)

### ✅ q18 — hit

**Question:** Can a single pod use both init containers and ephemeral containers?

**Expected source:** `ephemeral-containers.md`  
**Found at rank:** 1  
**Keywords matched:** 4/4 (init, ephemeral, container, pod)

Top results:
  1. `ephemeral-containers.md` — score `0.736` (Understanding ephemeral containers > What is an ephemeral container?)
  2. `_index.md` — score `0.730` (Pods with multiple containers {#how-pods-manage-multiple-containers})
  3. `ephemeral-containers.md` — score `0.729` (Uses for ephemeral containers)
  4. `sidecar-containers.md` — score `0.708` (Differences from init containers)
  5. `init-containers.md` — score `0.701` (Understanding init containers > Differences from regular containers)
