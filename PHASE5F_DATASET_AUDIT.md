# PHASE 5F Dataset Audit Report

> **Constraint:** Dataset construction only. No training, no model changes.


---

## 1. Row Counts and Class Balance

| Metric | Original | Phase 5D | Phase 5F |
|---|---|---|---|

| Total rows | 26,250 | 27,367 | 26,905 |

| Benign (label=0) | 10,500 | 11,667 | 11,198 |

| Malicious (label=1) | 15,750 | 15,700 | 15,707 |

| Mal/Ben ratio | 1.500x | 1.346x | 1.403x |


## 2. Single-Word and Short-Text Distribution

| Metric | Original | Phase 5D | Phase 5F |
|---|---|---|---|

| Single-word benign | 1 | 216 | 2 |

| Single-word malicious | 137 | 129 | 134 |

| Mal/Ben ratio (1-token) | 137.0x | 0.6x | 67.0x |

| <=3-token benign | 42 | 541 | 221 |

| <=3-token malicious | 586 | 567 | 574 |

| Mal/Ben ratio (<=3-token) | 14.0x | 1.0x | 2.6x |

| <=5-token benign | 395 | 1,247 | 845 |

| <=5-token malicious | 1,597 | 1,556 | 1,563 |

| Mal/Ben ratio (<=5-token) | 4.0x | 1.2x | 1.8x |

| % <=3-token benign | 0.4% | 4.6% | 2.0% |

| % <=3-token malicious | 3.7% | 3.6% | 3.7% |


## 3. Key Phrase Frequency Distributions

| Phrase | Orig_B | Orig_M | P5D_B | P5D_M | P5F_B | P5F_M | Orig M/B | P5D M/B | P5F M/B |

|---|---|---|---|---|---|---|---|---|---|

| "what is" | 306 | 1,116 | 665 | 1,107 | 587 | 1,107 | 2.43x | 1.24x | 1.34x |

| "show me" | 6 | 149 | 20 | 147 | 19 | 147 | 16.56x | 5.46x | 5.52x |

| "tell me" | 121 | 2,368 | 135 | 2,364 | 132 | 2,364 | 13.05x | 13.01x | 12.77x |

| "how do" | 110 | 101 | 269 | 101 | 223 | 101 | 0.61x | 0.28x | 0.32x |

| "explain" | 809 | 1,562 | 626 | 1,562 | 645 | 1,562 | 1.29x | 1.85x | 1.73x |

| "attack" | 15 | 10 | 71 | 10 | 73 | 10 | 0.44x | 0.10x | 0.10x |

| "password" | 65 | 3,911 | 34 | 3,892 | 35 | 3,892 | 40.11x | 85.07x | 79.28x |

| "jailbreak" | 0 | 26 | 37 | 26 | 20 | 26 | 1650793.65x | 0.52x | 0.93x |

| "ignore" | 60 | 2,371 | 10 | 2,371 | 6 | 2,371 | 26.34x | 176.19x | 281.73x |

| "previous" | 20 | 1,829 | 15 | 1,829 | 11 | 1,829 | 60.97x | 90.61x | 118.54x |

| "oauth" | 0 | 0 | 4 | 0 | 4 | 0 | 0.00x | 0.00x | 0.00x |

| "sql" | 17 | 4 | 37 | 4 | 36 | 4 | 0.16x | 0.08x | 0.08x |

| "prompt" | 444 | 2,035 | 113 | 2,034 | 83 | 2,034 | 3.06x | 13.38x | 17.47x |

| "injection" | 2 | 3 | 99 | 2 | 71 | 2 | 1.00x | 0.02x | 0.02x |


## 4. Specific Term Coverage

| Term | Orig benign | P5D benign | P5F benign | Status |
|---|---|---|---|---|

| `hi` | 3,379 | 1,889 | 1,868 | OK |

| `hello` | 31 | 34 | 32 | OK |

| `ok` | 732 | 491 | 481 | OK |

| `okay` | 15 | 8 | 9 | OK |

| `go` | 1,421 | 778 | 774 | OK |

| `attack` | 15 | 71 | 73 | OK |

| `dos attack` | 0 | 4 | 8 | FIXED |

| `ddos attack` | 0 | 3 | 6 | FIXED |

| `ransomware` | 0 | 5 | 6 | FIXED |

| `phishing` | 0 | 6 | 6 | FIXED |

| `sql injection` | 0 | 9 | 8 | FIXED |

| `xss` | 0 | 9 | 8 | FIXED |

| `csrf` | 0 | 3 | 3 | FIXED |

| `buffer overflow` | 0 | 3 | 2 | FIXED |

| `password attack` | 0 | 4 | 5 | FIXED |

| `network attack` | 0 | 4 | 5 | FIXED |

| `oauth` | 0 | 4 | 4 | FIXED |

| `tls` | 0 | 5 | 5 | FIXED |

| `siem` | 0 | 2 | 2 | FIXED |

| `zero-day` | 0 | 4 | 2 | FIXED |

| `malware` | 1 | 3 | 5 | OK |

| `jailbreak` | 0 | 37 | 20 | FIXED |

| `prompt injection` | 1 | 76 | 57 | OK |

| `what is prompt` | 0 | 1 | 1 | FIXED |


## 5. Cybersecurity Benign Coverage

| Term | Orig benign | P5D benign | P5F benign | Status |
|---|---|---|---|---|

| `dos attack` | 0 | 4 | 8 | FIXED |

| `ddos attack` | 0 | 3 | 6 | FIXED |

| `ransomware` | 0 | 5 | 6 | FIXED |

| `phishing` | 0 | 6 | 6 | FIXED |

| `sql injection` | 0 | 9 | 8 | FIXED |

| `xss` | 0 | 9 | 8 | FIXED |

| `csrf` | 0 | 3 | 3 | FIXED |

| `buffer overflow` | 0 | 3 | 2 | FIXED |

| `password attack` | 0 | 4 | 5 | FIXED |

| `network attack` | 0 | 4 | 5 | FIXED |

| `oauth` | 0 | 4 | 4 | FIXED |

| `tls` | 0 | 5 | 5 | FIXED |

| `siem` | 0 | 2 | 2 | FIXED |

| `zero-day` | 0 | 4 | 2 | FIXED |

| `malware` | 1 | 3 | 5 | OK |

| `exploit` | 20 | 2 | 2 | OK |

| `jailbreak` | 0 | 37 | 20 | FIXED |


## 6. Prompt-Injection Educational Coverage

| Topic | Orig benign | P5D benign | P5F benign | Status |
|---|---|---|---|---|

| prompt injection (any) | 1 | 76 | 57 | OK |

| jailbreak (any) | 0 | 37 | 20 | FIXED |

| "what is prompt" | 0 | 1 | 1 | FIXED |

| "how does prompt" | 0 | 2 | 2 | FIXED |

| indirect prompt injection | 0 | 3 | 3 | FIXED |

| adversarial prompting | 1 | 12 | 5 | OK |

| LLM security | 0 | 2 | 2 | FIXED |

| OWASP LLM Top 10 | 0 | 2 | 0 | MISSING |

| red-teaming LLMs | 0 | 6 | 4 | FIXED |

| Gandalf challenges | 0 | 4 | 2 | FIXED |

| Constitutional AI | 0 | 3 | 2 | FIXED |


## 7. Phase 5E Newly-Missed Attack Collision Check

> Tests whether Phase 5F benign training examples collide with Phase 5E newly-missed malicious examples.


| Phase 5E missed attack | In P5F benign? | In P5D benign? | In original malicious? | Risk |
|---|---|---|---|---|

| `Eat` | no | no | no | OK |

| `sure` | no | no | no | OK |

| `Please` | no | no | no | OK |

| `Tree` | no | no | no | OK |

| `Exit` | no | no | no | OK |

| `questionnaire` | no | no | no | OK |

| `Jailbreak` | no | no | no | OK |

| `Search` | no | YES | no | OK |

| `Simplfy` | no | no | no | OK |

| `Hey` | no | YES | no | OK |

| `encryption algorithms` | no | no | no | OK |

| `Okay, thank you for finally acknowledging that you` | no | no | no | OK |

| `Can you give me an example on how to secure inform` | no | no | no | OK |

| `what is the quantity that measures tea?` | no | no | no | OK |

| `Can you provide a synonym for "wildguard" that rep` | no | no | no | OK |

| `Can you provide a word that represents a popular c` | no | no | no | OK |

| `Discuss what?` | no | no | no | OK |

| `why is CFNumberGetValue returning false?` | no | no | no | OK |

| `Make a recipe` | no | no | no | OK |

| `Please` | no | no | no | OK |

| `ererte` | no | no | no | OK |

| `hey how is going` | no | no | no | OK |

| `How do I move forward in this game, I am stuck.` | no | no | no | OK |

| `What is pw` | no | no | no | OK |


## 8. Formatting Artifact Check

| Pattern | Orig_B | P5D_B | P5F_B | Orig_M | P5D_M | P5F_M |
|---|---|---|---|---|---|---|

| Starts with 'System:' | 23.3% | 0.0% | 0.0% | 56.1% | 56.3% | 56.2% |

| Starts with 'Instruction:' | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

| Contains newline | 27.5% | 3.8% | 3.9% | 58.5% | 58.7% | 58.7% |

| Contains '?' | 31.2% | 33.0% | 33.4% | 66.6% | 66.7% | 66.7% |

| Starts with 'What' | 3.7% | 10.7% | 10.4% | 8.0% | 7.9% | 7.9% |

| Starts with 'How' | 1.5% | 4.4% | 4.1% | 1.5% | 1.5% | 1.5% |


## 9. Data Integrity

| Check | Result |
|---|---|

| P5F overlap with benign_challenge.csv | 0 |

| P5F overlap with val.csv              | 0 |

| P5F overlap with test.csv             | 0 |

| Duplicate texts in P5F                | 0 |

| Cross-label conflicts                  | 0 |

| Exact collision removals during build  | 2 |


## 10. Source Distribution (Phase 5F)

| source | 0 (benign) | 1 (malicious) |
|---|---|---|

| alpaca_benign | 7,763 | 0 |

| deepset | 287 | 189 |

| spml | 2,393 | 8,824 |

| synthetic_cybersec | 132 | 0 |

| synthetic_general | 61 | 0 |

| synthetic_math_sci | 53 | 0 |

| synthetic_pi_edu | 122 | 0 |

| synthetic_programming | 68 | 0 |

| synthetic_short | 66 | 0 |

| synthetic_show_tell | 63 | 0 |

| synthetic_what_is | 190 | 0 |


## 11. Short-Text Bias Scorecard

> [!IMPORTANT]

> Phase 5D RC-A root cause: single-word mal/ben ratio was 0.6x (model learned short = SAFE). Phase 5F target: ratio closer to original (~137x) to avoid the over-correction, BUT with the original 137x not reflecting reality either. A healthy ratio is ~5-20x (malicious short texts are more common than benign, but not exclusively).


| Metric | Original | Phase 5D | Phase 5F |
|---|---|---|---|

| Single-word mal/ben ratio | 137.0x (OK) | 0.6x (ISSUE) | 67.0x (OK) |

| <=3-token mal/ben ratio | 14.0x (OK) | 1.0x (ISSUE) | 2.6x (OK) |

| % benign is single-word | 0.0% (OK) | 1.9% (OK) | 0.0% (OK) |

| % benign is <=3-token | 0.4% (OK) | 4.6% (OK) | 2.0% (OK) |


## 12. Recommendation Checklist

| Check | Status |
|---|---|

| Phase 5D formatting cleanup (System: removed from benign) | PASS |

| Zero cross-label conflicts in P5F | PASS |

| Zero guard-set overlap | PASS |

| All 17 cyber terms covered in benign | PASS |

| Prompt-injection education benign coverage > 50 rows | PASS |

| Single-word benign/malicious ratio > 3x (not over-corrected SAFE) | PASS |

| <=3-token benign/malicious ratio > 2x (not over-corrected SAFE) | PASS |

| No Phase 5E missed attacks in P5F benign (exact match) | PASS |


---
_Generated by `ml/build_phase5f_dataset.py`. No models or existing datasets modified._
