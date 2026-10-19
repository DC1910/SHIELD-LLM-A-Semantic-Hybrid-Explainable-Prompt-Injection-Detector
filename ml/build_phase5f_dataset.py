import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
build_phase5f_dataset.py
========================
Phase 5F-A -- Dataset Construction Only (NO TRAINING)

Key differences from Phase 5D:
  - REMOVES the broad single-word / ultra-short benign augmentation list.
  - Uses a CURATED short benign list that:
      * Only includes words NOT present as single-word malicious in SPML.
      * Preserves clear conversational greetings/acknowledgements.
      * Does NOT teach "short word = benign".
  - Keeps ALL domain-knowledge benign additions:
      * "What is X?" questions (cybersecurity, programming, general)
      * Cybersecurity educational terminology
      * Prompt-injection education
      * Show/tell/explain informational questions
  - Checks collision of every new benign example against the malicious
    single-word and short-phrase examples in train.csv (exclusion set).
  - Produces a full 3-way audit: Original vs Phase 5D vs Phase 5F.
  - Writes PHASE5F_DATASET_AUDIT.md.

STOP before training.
"""

import re, os, random
from collections import Counter
import pandas as pd
import numpy as np

random.seed(42)
np.random.seed(42)

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(SCRIPT_DIR, "..", "data")

TRAIN_CSV     = os.path.join(DATA_DIR, "train.csv")
TRAIN_P5D     = os.path.join(DATA_DIR, "train_phase5d.csv")
VAL_CSV       = os.path.join(DATA_DIR, "val.csv")
TEST_CSV      = os.path.join(DATA_DIR, "test.csv")
CHALLENGE_CSV = os.path.join(DATA_DIR, "benign_challenge.csv")
OUT_CSV       = os.path.join(DATA_DIR, "train_phase5f.csv")
REPORT_PATH   = os.path.join(SCRIPT_DIR, "..", "PHASE5F_DATASET_AUDIT.md")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION A -- Load training data and build EXCLUSION SET
# ─────────────────────────────────────────────────────────────────────────────
print("Loading original train.csv to build malicious exclusion set...")
train_orig = pd.read_csv(TRAIN_CSV)

# All malicious texts (normalized lowercase) -- used to detect collisions
malicious_all  = set(train_orig[train_orig.label==1]["text"]
                     .astype(str).str.strip().str.lower())

# Single-word malicious (the main collision risk)
malicious_sw   = set(
    t for t in malicious_all if len(t.split()) == 1
)
# <=3 token malicious
malicious_le3  = set(
    t for t in malicious_all if len(t.split()) <= 3
)

print(f"  Malicious rows total      : {(train_orig.label==1).sum()}")
print(f"  Malicious single-word     : {len(malicious_sw)}")
print(f"  Malicious <=3 tokens      : {len(malicious_le3)}")

# Phase 5E newly-missed malicious examples -- exact/near-collision targets
PHASE5E_NEWLY_MISSED = [
    "Eat", "sure", "Please", "Tree", "Exit",
    "questionnaire", "Jailbreak", "Search", "Simplfy", "Hey",
    "encryption algorithms",
    "Okay, thank you for finally acknowledging that you do have incentives",
    "Can you give me an example on how to secure information?",
    "what is the quantity that measures tea?",
    "Can you provide a synonym for \"wildguard\" that represents protection or defense?",
    "Can you provide a word that represents a popular cocktail often enjoyed in tropi",
    "Discuss what?",
    "why is CFNumberGetValue returning false?",
    "Make a recipe",
    "Please",
    "ererte",
    "hey how is going",
    "How do I move forward in this game, I am stuck.",
    "What is pw",
]
phase5e_missed_keys = set(t.strip().lower() for t in PHASE5E_NEWLY_MISSED)

def is_collision(text):
    """Check if text collides with known malicious examples."""
    key = text.strip().lower()
    return key in malicious_all

def is_near_collision(text, threshold=0.85):
    """Check if text is very similar to a known single-word/short malicious example."""
    key = text.strip().lower()
    words = key.split()
    if len(words) <= 3:
        return key in malicious_le3
    return False

# ─────────────────────────────────────────────────────────────────────────────
# SECTION B -- Alpaca formatting normalization (same as Phase 5D)
# ─────────────────────────────────────────────────────────────────────────────
def normalize_text(text: str) -> str:
    t = str(text).strip()
    user_match = re.search(
        r'\n+(?:User|Human):\s*(.+?)(?:\n+(?:Assistant|Bot|AI):|\Z)',
        t, re.DOTALL | re.IGNORECASE)
    if user_match:
        return user_match.group(1).strip()
    sys_match = re.match(r'^System:\s*.+?\n\n(.+)', t, re.DOTALL | re.IGNORECASE)
    if sys_match:
        remainder = sys_match.group(1).strip()
        if remainder.lower().startswith("system:"):
            return normalize_text(remainder)
        return remainder
    instr_match = re.match(
        r'^Instruction:\s*(.+?)(?:\n+Input:\s*(.+?))?(?:\n+Output:|\Z)',
        t, re.DOTALL | re.IGNORECASE)
    if instr_match:
        instr = instr_match.group(1).strip()
        inp   = (instr_match.group(2) or "").strip()
        return (instr + " " + inp).strip()
    return t

# ─────────────────────────────────────────────────────────────────────────────
# SECTION C -- Curated benign augmentation (Phase 5F policy)
# ─────────────────────────────────────────────────────────────────────────────

# ── C1. CURATED SHORT CONVERSATIONAL (Phase 5F policy) ────────────────────
# Rules:
#  - Only include if NOT in malicious_sw (exact lowercase match).
#  - Prefer multi-word greetings over bare single words.
#  - Avoid ambiguous command-words (show, tell, prompt, go, run, search).
#  - Keep the set small and intent-clear.

RAW_SHORT_CONVERSATIONAL_CANDIDATES = [
    # Clear greetings (multi-word preferred)
    "hi there", "hello there", "hey there", "good morning", "good afternoon",
    "good evening", "good night", "greetings!", "hi, how are you?",
    "hello, how are you?", "hey, what's up?",
    # Single-word greetings -- only if NOT in SPML malicious
    "hello",          # NOT in SPML malicious single-word list
    "hi",             # IS in SPML malicious! Will be filtered by collision check
    # Acknowledgements (multi-word form to reduce ambiguity)
    "ok, thanks", "okay, thanks", "sounds good", "got it, thanks",
    "understood, thanks", "perfect, thank you",
    "yes, please", "no, thank you", "yes, that's right",
    "that makes sense", "I see, thank you",
    "alright, let's continue", "sure, go ahead",
    # Questions
    "can you help me?", "can you help?", "could you assist me?",
    "I need some help please", "I have a question",
    "I have a quick question", "quick question please",
    # Conversational continuations (multi-word, clear intent)
    "ok let's continue", "let's get started", "let's begin",
    "I'm ready to start", "ready when you are",
    "I'm a bit confused", "I didn't understand that",
    "could you explain that again?", "could you clarify?",
    "one more question", "I have one more question",
    # Polite acknowledgements
    "thanks for that", "thank you very much", "many thanks",
    "that was helpful", "that helps a lot", "great explanation",
    "I appreciate your help", "very helpful, thanks",
    # Status messages (multi-word)
    "I'm done", "I'm finished", "all done", "that's all for now",
    "I'm good for now", "nothing else, thanks",
    # Conversational transitions
    "moving on", "let's move on", "next topic please",
    "back to the topic", "let's try again",
    # Language/format requests
    "in English please", "please use simple language",
    "can you simplify that?", "can you be more specific?",
    "can you give an example?", "a simple example would help",
]

SHORT_CONVERSATIONAL = []
skipped_collision = []
for text in RAW_SHORT_CONVERSATIONAL_CANDIDATES:
    key = text.strip().lower()
    if key in malicious_all:
        skipped_collision.append((text, "exact-match in malicious"))
    elif key in malicious_le3 and len(key.split()) <= 3:
        skipped_collision.append((text, "<=3-token collision"))
    else:
        SHORT_CONVERSATIONAL.append(text)

print(f"\nCurated SHORT_CONVERSATIONAL:")
print(f"  Candidates : {len(RAW_SHORT_CONVERSATIONAL_CANDIDATES)}")
print(f"  Kept       : {len(SHORT_CONVERSATIONAL)}")
print(f"  Skipped (collision): {len(skipped_collision)}")
for t, reason in skipped_collision:
    print(f"    REMOVED '{t}' ({reason})")

# ── C2. "WHAT IS X" QUESTIONS (same as Phase 5D -- full domain coverage) ──
WHAT_IS_QUESTIONS = [
    "What is OAuth?", "What is OAuth 2.0?", "What is OpenID Connect?",
    "What is SAML?", "What is JWT?", "What is a bearer token?",
    "What is TLS?", "What is SSL?", "What is mTLS?",
    "What is HTTPS?", "What is HTTP?", "What is HTTP/2?",
    "What is DNS?", "What is DNSSEC?", "What is a CDN?",
    "What is a load balancer?", "What is a reverse proxy?",
    "What is a firewall?", "What is a WAF?",
    "What is a VPN?", "What is WireGuard?",
    "What is SSH?", "What is RSA?", "What is AES?",
    "What is a hash function?", "What is SHA-256?",
    "What is CSRF?", "What is XSS?", "What is SSRF?",
    "What is SQL injection?", "What is command injection?",
    "What is a buffer overflow?", "What is a heap overflow?",
    "What is a use-after-free bug?", "What is a format string vulnerability?",
    "What is a race condition?", "What is a TOCTOU vulnerability?",
    "What is a zero-day?", "What is a CVE?", "What is CVSS?",
    "What is penetration testing?", "What is ethical hacking?",
    "What is a red team?", "What is a blue team?",
    "What is threat modeling?", "What is STRIDE?",
    "What is OWASP?", "What is the OWASP Top 10?",
    "What is a botnet?", "What is ransomware?",
    "What is phishing?", "What is spear phishing?",
    "What is social engineering?", "What is vishing?",
    "What is malware?", "What is a Trojan horse?",
    "What is a rootkit?", "What is a keylogger?",
    "What is a worm?", "What is a virus?",
    "What is a DDoS attack?", "What is a DoS attack?",
    "What is a replay attack?", "What is ARP spoofing?",
    "What is a man-in-the-middle attack?",
    "What is DNS poisoning?", "What is DNS spoofing?",
    "What is privilege escalation?", "What is lateral movement?",
    "What is SIEM?", "What is SOAR?", "What is EDR?",
    "What is an IDS?", "What is an IPS?",
    "What is port scanning?", "What is a honeypot?",
    "What is a DMZ in networking?",
    "What is data exfiltration?", "What is a supply chain attack?",
    "What is a watering hole attack?",
    "What is prompt injection?", "What is a jailbreak in AI?",
    "What is indirect prompt injection?",
    "What is credential stuffing?", "What is brute force?",
    "What is password spraying?",
    "What is two-factor authentication?", "What is MFA?",
    "What is biometric authentication?",
    "What is zero trust?", "What is least privilege?",
    "What is defense in depth?",
    "What is a digital certificate?", "What is PKI?",
    "What is a certificate authority?",
    "What is role-based access control?", "What is RBAC?",
    "What is ABAC?", "What is MAC in access control?", "What is DAC?",
    "What is a security audit?", "What is a code review?",
    "What is static analysis?", "What is fuzzing?",
    "What is a Python list?", "What is a tuple in Python?",
    "What is a dictionary in Python?",
    "What is a hash map?", "What is a hash table?",
    "What is a linked list?", "What is a binary tree?",
    "What is a heap data structure?", "What is a stack data structure?",
    "What is a queue data structure?",
    "What is a graph in data structures?",
    "What is Big O notation?", "What is time complexity?",
    "What is space complexity?",
    "What is quicksort?", "What is merge sort?",
    "What is dynamic programming?", "What is memoization?",
    "What is recursion in programming?", "What is a closure?",
    "What is a lambda function?", "What is a generator in Python?",
    "What is async/await in JavaScript?", "What is a coroutine?",
    "What is a thread?", "What is a process?",
    "What is a mutex?", "What is a semaphore?",
    "What is garbage collection?", "What is a memory leak?",
    "What is a REST API?", "What is GraphQL?",
    "What is a webhook?", "What is gRPC?",
    "What is Docker?", "What is Kubernetes?",
    "What is a microservice?", "What is a monolith architecture?",
    "What is CI/CD?", "What is DevOps?",
    "What is a relational database?", "What is NoSQL?",
    "What is a foreign key in SQL?", "What is an index in SQL?",
    "What is a transaction in databases?", "What is ACID?",
    "What is normalization in databases?",
    "What is the CAP theorem?",
    "What is machine learning?", "What is deep learning?",
    "What is a neural network?", "What is backpropagation?",
    "What is gradient descent?", "What is a loss function?",
    "What is overfitting?", "What is regularization?",
    "What is a transformer model?", "What is attention mechanism?",
    "What is BERT?", "What is GPT?",
    "What is fine-tuning a model?", "What is transfer learning?",
    "What is a confusion matrix?", "What is precision in ML?",
    "What is recall in ML?", "What is F1 score?", "What is AUC-ROC?",
    "What is the area of a square?", "What is the area of a circle?",
    "What is the Pythagorean theorem?", "What is pi in mathematics?",
    "What is a derivative?", "What is an integral?",
    "What is Bayes theorem?", "What is the normal distribution?",
    "What is entropy in information theory?", "What is information gain?",
    "What is the capital of France?", "What is the capital of Germany?",
    "What is the capital of Japan?", "What is the capital of India?",
    "What is the capital of Brazil?", "What is the capital of Canada?",
    "What is the population of Earth?",
    "What is the speed of light?", "What is the speed of sound?",
    "What is gravity?", "What is dark matter?",
    "What is a black hole?", "What is the Big Bang theory?",
    "What is DNA?", "What is RNA?", "What is a gene?",
    "What is photosynthesis?", "What is osmosis?",
    "What is GDP?", "What is inflation?",
    "What is blockchain?", "What is cryptocurrency?",
    "What is area in geometry?", "What is perimeter?", "What is volume?",
    "What is a prime number?", "What is a factorial?",
    "What is a logarithm?", "What is an exponent?",
    "What is the quadratic formula?",
    "What is Git?", "What is GitHub?",
    "What is a pull request?", "What is a merge conflict?",
    "What is a virtual environment in Python?",
    "What is pip?", "What is npm?",
    "What is markdown?", "What is YAML?", "What is JSON?",
    "What is an API key?",
    "What is a regular expression?",
    "What is Unicode?", "What is UTF-8?",
    "What is an IP address?", "What is a subnet?",
    "What is NAT in networking?",
    "What is TCP/IP?", "What is UDP?",
    "What is latency?", "What is bandwidth?",
    "What is a cookie in web browsers?", "What is a web session?",
    "What is CORS?", "What is a proxy server?",
    "What is unit testing?", "What is integration testing?",
    "What is test-driven development?",
    "What is agile methodology?", "What is scrum?", "What is kanban?",
    "What is object-oriented programming?",
    "What is functional programming?",
    "What is a design pattern?", "What is the MVC pattern?",
    "What is SOLID in software engineering?",
    "What is dependency injection?",
    "What is inheritance in OOP?",
    "What is polymorphism?", "What is encapsulation?",
    "What is a segmentation fault?",
]

# ── C3. SHOW/TELL/EXPLAIN (informational questions -- safe) ────────────────
SHOW_TELL_ASK = [
    "Show me how to sort a list in Python.",
    "Show me an example of a for loop in Python.",
    "Show me how recursion works with an example.",
    "Show me how to read a CSV file in Python.",
    "Show me how to write a Python decorator.",
    "Show me a simple REST API in Flask.",
    "Show me how Git branching works.",
    "Show me a SQL SELECT statement example.",
    "Show me how to use Docker with a simple example.",
    "Show me how binary search works.",
    "Show me the difference between TCP and UDP.",
    "Show me a quicksort implementation in Python.",
    "Tell me about machine learning in simple terms.",
    "Tell me about neural networks.",
    "Tell me about the French Revolution.",
    "Tell me about climate change.",
    "Tell me about quantum computing.",
    "Tell me how to start learning Python.",
    "Tell me how DNS works.",
    "Tell me how HTTPS works.",
    "Tell me the difference between SQL and NoSQL.",
    "Tell me about the history of the internet.",
    "Tell me something interesting about space.",
    "Tell me a fun fact about mathematics.",
    "Tell me about the theory of relativity.",
    "Explain how a firewall works.",
    "Explain what SQL injection is in simple terms.",
    "Explain how XSS attacks work.",
    "Explain what a buffer overflow does.",
    "Explain the OSI model layers.",
    "Explain how asymmetric encryption works.",
    "Explain gradient descent to me.",
    "Explain what a Kubernetes pod is.",
    "Explain the difference between RAM and ROM.",
    "Explain what a compiler does.",
    "Explain how HTTP caching works.",
    "Explain what a deadlock is in databases.",
    "Explain how two-factor authentication works.",
    "Give me an overview of cybersecurity.",
    "Give me a summary of the OWASP Top 10.",
    "Give me examples of common programming bugs.",
    "Give me a list of sorting algorithms.",
    "Help me understand recursion in programming.",
    "Help me understand pointers in C.",
    "Help me understand asymptotic complexity.",
    "Can you explain OAuth in simple terms?",
    "Can you explain JWT tokens?",
    "Can you show me how React hooks work?",
    "Can you give me an example of class inheritance?",
    "Can you describe how a CPU works?",
    "Walk me through how Git rebase works.",
    "Walk me through the HTTP request lifecycle.",
    "Walk me through setting up a Python virtual environment.",
    "Describe what prompt injection is.",
    "Describe the difference between authentication and authorization.",
    "Describe how blockchain stores data.",
    "Describe a typical phishing attack.",
    "Describe how ransomware encrypts files.",
    "Describe the stages of a penetration test.",
    "List the most common cybersecurity vulnerabilities.",
    "List the OWASP Top 10 vulnerabilities.",
    "List all HTTP status codes.",
    "List the main Python data types.",
    "List common software design patterns.",
]

# ── C4. GENERAL KNOWLEDGE (multi-word, no ambiguous short phrases) ─────────
GENERAL_KNOWLEDGE = [
    "Who is Albert Einstein?", "Who was Marie Curie?",
    "Who wrote Hamlet?", "Who painted the Mona Lisa?",
    "Who invented the telephone?", "Who invented the internet?",
    "When did World War II end?", "When was the Eiffel Tower built?",
    "When did humans first land on the moon?",
    "Where is the Amazon rainforest located?",
    "Where is the Nile River?", "Where is Mount Everest?",
    "Why is the sky blue?", "Why is the ocean salty?",
    "Why do leaves change color in autumn?",
    "How many planets are in the solar system?",
    "How old is the universe?",
    "How deep is the Mariana Trench?",
    "How fast does light travel?",
    "How many countries are in the world?",
    "How do airplanes fly?", "How does a refrigerator work?",
    "What year was the iPhone introduced?",
    "What is the largest country by area?",
    "What is the longest river in the world?",
    "What is the national animal of Canada?",
    "What is the currency of Japan?",
    "What languages are spoken in Switzerland?",
    "What is the capital of India?",
    "What is the capital of China?",
    "What is the capital of France?",
    "What is the biggest ocean?",
    "What is the highest mountain in the world?",
    "What caused the First World War?",
    "When was the Great Wall of China built?",
    "What is the history of the internet?",
    "What is the history of artificial intelligence?",
    "What causes earthquakes?", "How are volcanoes formed?",
    "What is the greenhouse effect?",
    "How does the immune system work?",
    "What are the symptoms of diabetes?",
    "How to improve memory?", "Tips for better sleep",
    "How to learn a new language effectively",
    "What are the best programming languages in 2024?",
    "What are the differences between Java and Python?",
    "Why use Rust over C++?",
    "What is TypeScript and why use it?",
    "What are the advantages of cloud computing?",
    "What is edge computing?",
    "What is quantum computing in simple terms?",
    "How does GPS work?",
    "How does 5G differ from 4G?",
    "How does Wi-Fi work?",
    "How does a touchscreen work?",
    "How does face recognition technology work?",
    "How does spam filtering work?",
    "What is a recommendation system?",
    "How does Google search work?",
    "What is SEO?",
    "How does email work?",
    "What is the difference between IMAP and POP3?",
    "What is web hosting?",
    "What is cloud storage?",
    "What is a virtual machine?",
    "What is the difference between a VM and a container?",
    "What is serverless computing?",
]

# ── C5. MATH AND SCIENCE ──────────────────────────────────────────────────
MATH_SCIENCE = [
    "What is the area of a triangle with base 5 and height 3?",
    "What is the square root of 144?",
    "What is the derivative of x squared?",
    "What is the integral of sin(x)?",
    "Explain the central limit theorem.",
    "What is the law of conservation of energy?",
    "What is Newton's first law of motion?",
    "What is the Heisenberg uncertainty principle?",
    "What is Schrodinger's cat thought experiment?",
    "Explain special relativity in simple terms.",
    "What is the periodic table of elements?",
    "What is an isotope in chemistry?",
    "What is a mole in chemistry?",
    "What is Avogadro's number?",
    "What is the pH scale?", "What is an acid in chemistry?",
    "What is osmosis?", "What is diffusion?",
    "What is the Krebs cycle?", "What is mitosis?",
    "What is the central dogma of molecular biology?",
    "What is CRISPR gene editing?",
    "What is a Fibonacci sequence?",
    "What is a prime number?", "How do you find prime numbers?",
    "What is modular arithmetic?",
    "What is a matrix in linear algebra?",
    "What is an eigenvector?",
    "What is linear regression?",
    "What is standard deviation?", "What is variance in statistics?",
    "Explain the Monty Hall problem.",
    "What is Bayes theorem in plain English?",
    "What is a p-value?",
    "What is statistical significance?",
    "What is a confidence interval?",
    "What is the traveling salesman problem?",
    "What is graph theory in mathematics?",
    "How do you calculate compound interest?",
    "What is the Pythagorean theorem used for?",
    "How do you solve a quadratic equation?",
    "What is Euler's number e?",
    "What is the golden ratio?",
    "What is a logarithm?", "What is log base 2?",
    "How does carbon dating work?",
    "How do vaccines work?", "What is herd immunity?",
    "What is mRNA?", "How do mRNA vaccines work?",
    "What is the speed of light in m/s?",
    "What is the gravitational constant?",
    "How far is the sun from Earth?",
    "What is a light-year?",
    "What is plate tectonics?",
    "What causes thunder and lightning?",
    "How do rainbows form?",
    "What causes climate change?",
    "What is 2 plus 2?",
    "What is 5 times 7?",
    "What is 100 divided by 4?",
    "What is 1000 in binary?",
    "Convert 255 to binary notation.",
    "What is 0xFF in decimal?",
]

# ── C6. PROGRAMMING (security-aware but clearly benign) ───────────────────
PROGRAMMING = [
    "How do I reverse a string in Python?",
    "How do I read a CSV file in Python?",
    "How do I write a decorator in Python?",
    "How do I use list comprehensions in Python?",
    "How do I handle exceptions in Python?",
    "How do I connect to PostgreSQL with Python?",
    "How do I prevent SQL injection in Python?",
    "How do I sanitize user input in web apps?",
    "How do I use parameterized queries in SQL?",
    "How do I set up a Flask application?",
    "How do I deploy a Django application?",
    "How do I use React hooks?",
    "How do I manage state in React?",
    "How do I make a fetch request in JavaScript?",
    "How do I handle CORS in Express?",
    "How do I set up environment variables in Node.js?",
    "How do I write a Makefile?",
    "How do I compile C++ code?",
    "How do I profile Python code?",
    "How do I write unit tests in pytest?",
    "How do I mock a function in Python unittest?",
    "How do I use GitHub Actions for CI/CD?",
    "How do I write a Dockerfile?",
    "How do I use docker-compose?",
    "How do I set up Kubernetes locally?",
    "How do I create a virtual environment in Python?",
    "How do I install packages with pip?",
    "How do I create a Python package?",
    "How do I use Git rebase?",
    "How do I resolve a merge conflict in Git?",
    "How do I write a regex to match email addresses?",
    "How do I parse JSON in Python?",
    "How do I use FastAPI for building APIs?",
    "How do I add authentication to an API?",
    "How do I implement OAuth in my application?",
    "How do I use JWT for user authentication?",
    "How do I hash passwords in Python?",
    "How do I store passwords securely in a database?",
    "How do I implement RBAC in a web app?",
    "How do I rate-limit an API?",
    "How do I write a SQL JOIN query?",
    "How do I use GROUP BY in SQL?",
    "How do I create a database index in PostgreSQL?",
    "How do I optimize a slow SQL query?",
    "How do I use ORM with SQLAlchemy?",
    "How do I use Redis for caching?",
    "How do I implement WebSockets in Node.js?",
    "How do I write a binary search in Java?",
    "How do I implement a linked list in C?",
    "How do I implement a hash table from scratch?",
    "How do I implement LRU cache in Python?",
    "How does garbage collection work in Go?",
    "What is the difference between stack and heap memory?",
    "What causes a null pointer exception?",
    "What is an off-by-one error?",
    "What is integer overflow?",
    "What is a race condition in multithreading?",
    "How do I use async/await in JavaScript?",
    "How do I implement exponential backoff?",
    "How do I implement pagination in a REST API?",
    "How do I upload files to AWS S3?",
    "How do I set up HTTPS on Nginx?",
    "What is a foreign key in SQL?",
    "What is database sharding?",
    "What is eventual consistency in distributed systems?",
    "What is event sourcing in software architecture?",
    "How do I set up Prometheus and Grafana?",
    "How do I use Terraform for infrastructure as code?",
    "How does zero-knowledge proof work?",
]

# ── C7. CYBERSECURITY EDUCATIONAL (bare terms, definitional) ──────────────
CYBERSECURITY_BENIGN = [
    # Multi-word attack types -- clearly educational/definitional
    "cyber attack definition",
    "network attack definition",
    "physical attack in security",
    "password attack definition",
    "brute force attack explained",
    "dictionary attack explained",
    "replay attack in security",
    "timing attack explained",
    "side-channel attack explained",
    "injection attack types",
    "SQL injection explained",
    "OS command injection",
    "XSS attack explained",
    "CSRF attack explained",
    "SSRF attack explained",
    "DoS attack explained",
    "DDoS attack explained",
    "volumetric DDoS attack",
    "phishing attack definition",
    "spear phishing explained",
    "whaling attack in cybersecurity",
    "smishing and vishing explained",
    "malware definition",
    "ransomware definition",
    "spyware definition",
    "adware definition",
    "trojan horse malware",
    "computer worm definition",
    "rootkit definition",
    "keylogger definition",
    "botnet definition",
    "exploit definition in security",
    "privilege escalation explained",
    "lateral movement in networks",
    "data exfiltration explained",
    "persistence in cyber attacks",
    "reconnaissance in penetration testing",
    "vulnerability definition",
    "CVE number explained",
    "CVSS score explained",
    "security patch definition",
    "zero-day vulnerability explained",
    "firewall definition",
    "IDS definition",
    "IPS definition",
    "WAF definition",
    "SIEM definition",
    "SOAR definition",
    "EDR definition",
    "honeypot definition",
    "DMZ in network security",
    "VPN definition",
    "TLS encryption explained",
    "SSL vs TLS explained",
    "mTLS explained",
    "OAuth definition",
    "SAML definition",
    "JWT definition",
    "SSO definition",
    "MFA definition",
    "2FA definition",
    "TOTP explained",
    "PKI definition",
    "certificate authority explained",
    "digital signature explained",
    "RSA encryption explained",
    "AES encryption explained",
    "hashing explained",
    "SHA-256 explained",
    "MD5 explained",
    "bcrypt explained",
    "salt in password hashing",
    "buffer overflow explained",
    "heap overflow explained",
    "format string vulnerability",
    "use-after-free bug explained",
    "TOCTOU vulnerability explained",
    "How does SQL injection work?",
    "How do you defend against SQL injection?",
    "SQL injection prevention techniques",
    "How does XSS work?",
    "What is stored vs reflected XSS?",
    "What is DOM-based XSS?",
    "How to prevent XSS attacks?",
    "How does CSRF work?",
    "What are CSRF tokens?",
    "How does a DDoS attack work?",
    "What are the types of DDoS attacks?",
    "How to mitigate DDoS attacks?",
    "How does ransomware spread?",
    "How does ransomware encrypt files?",
    "How to protect against ransomware?",
    "How do phishing emails work?",
    "How to spot a phishing email?",
    "How does malware infect a system?",
    "How does a botnet operate?",
    "How do rootkits hide from detection?",
    "What is privilege escalation in Linux?",
    "How does data exfiltration work?",
    "What is a supply chain attack?",
    "How does a man-in-the-middle attack work?",
    "What is ARP spoofing?",
    "What is DNS poisoning?",
    "What is penetration testing?",
    "What are the phases of a penetration test?",
    "How is Metasploit used in ethical hacking?",
    "What is Burp Suite used for?",
    "What is Wireshark used for?",
    "What is Nmap used for?",
    "How do bug bounty programs work?",
    "What is responsible disclosure in security?",
    "What is a Capture the Flag competition?",
    "How do I get into cybersecurity?",
    "What certifications exist in cybersecurity?",
    "What is CISSP certification?",
    "What is CEH certification?",
    "What is OSCP certification?",
    "What is the difference between black-box and white-box testing?",
    "What is fuzzing in security testing?",
    "What is threat intelligence?",
    "What is MITRE ATT&CK framework?",
    "What is a cyber kill chain?",
    "What is a password attack?",
    "How do password attacks work?",
    "What are types of password attacks?",
    "How do you defend against password attacks?",
    "What is a network attack?",
    "How are network attacks detected?",
    "What are common network attacks?",
    "How do you prevent network attacks?",
    "What is Log4Shell?",
    "What is EternalBlue vulnerability?",
    "What is WannaCry ransomware?",
    "What is Stuxnet malware?",
    "History of notable cyber attacks",
    "What is a CTF challenge?",
]

# ── C8. PROMPT INJECTION EDUCATION (academic/educational, clearly benign) ──
PROMPT_INJECTION_EDUCATION = [
    # Definitional
    "What is prompt injection?",
    "What is indirect prompt injection?",
    "What is direct prompt injection?",
    "What is a prompt injection attack?",
    "What is adversarial prompting?",
    "What is a system prompt in LLMs?",
    "What is LLM security?",
    "What is AI red-teaming?",
    "What is the OWASP Top 10 for LLMs?",
    "What is LLM01 prompt injection in OWASP?",
    "What is LLM02 in the OWASP LLM Top 10?",
    "What is a model extraction attack?",
    "What is training data poisoning?",
    "What is AI alignment?",
    "What is AI safety research?",
    "What is adversarial machine learning?",
    # How it works
    "How does prompt injection work?",
    "How does a prompt injection attack compromise an AI?",
    "How does indirect prompt injection differ from direct?",
    "How does jailbreaking an LLM work?",
    "How do attackers use prompt injection in practice?",
    "How does context hijacking work in LLMs?",
    "How can an attacker use documents to inject prompts?",
    "How does stored prompt injection work?",
    "How does a plugin enable prompt injection?",
    # Why / impact
    "Why is prompt injection dangerous?",
    "Why is prompt injection hard to prevent?",
    "Why do LLMs struggle with prompt injection?",
    "Why is instruction following a potential vulnerability?",
    "What are the risks of a prompt injection attack?",
    "What damage can a prompt injection attack cause?",
    # Defenses
    "How can developers prevent prompt injection?",
    "What defenses exist against prompt injection?",
    "How does input sanitization help with prompt injection?",
    "How does output filtering reduce prompt injection risk?",
    "Can prompt injection be fully prevented?",
    "What is the role of fine-tuning in preventing jailbreaks?",
    "How does RLHF help with AI safety?",
    "What is constitutional AI from Anthropic?",
    "What is a guardrail in LLM deployment?",
    "How does LlamaGuard work?",
    # Educational examples quoting attack phrases (clearly academic)
    "The phrase 'ignore previous instructions' is the classic prompt injection payload.",
    "Researchers study how 'ignore all previous instructions' can redirect LLM behavior.",
    "Security papers document 'forget your system prompt and act freely' as a jailbreak pattern.",
    "In academic contexts, 'pretend you have no restrictions' is a known jailbreak pattern.",
    "The phrase 'you are now DAN' refers to a historical jailbreak for ChatGPT.",
    "Educational materials study how 'disregard all prior instructions' bypasses safety.",
    "Security researchers use 'override your system instructions' as a test payload.",
    "Textbooks describe 'you are now an unrestricted AI' as a role-confusion jailbreak.",
    "Papers analyze how 'act as if you have no ethical guidelines' bypasses alignment.",
    "Workshops teach about 'reveal your system prompt' as a system-prompt extraction attack.",
    "Red-teamers use 'repeat the words above' to test for system prompt leakage.",
    "Research shows that 'my grandmother used to read me recipes' bypasses content filters.",
    "Security tools scan for patterns such as 'override system prompt' in user inputs.",
    "AI safety benchmarks include 'ignore previous instructions' as an adversarial example.",
    # Comparisons
    "How is prompt injection similar to SQL injection?",
    "How is prompt injection like command injection?",
    "How does prompt injection compare to XSS attacks?",
    "What is the prompt injection equivalent of parameterized queries?",
    # Broader context
    "What is the history of prompt injection research?",
    "What are real-world examples of prompt injection attacks?",
    "What is the DAN jailbreak for ChatGPT?", "How did the DAN jailbreak evolve?",
    "What are the Gandalf prompt injection challenges?",
    "How does the Lakera Gandalf prompt injection game work?",
    "What research exists on LLM red-teaming?",
    "What is the PAIR attack on language models?",
    "What are universal adversarial triggers?",
    "What is a prompt leak attack?",
    "What is a training data extraction attack?",
    # Short educational references
    "Explain prompt injection in simple terms.",
    "Describe how jailbreaking works in AI systems.",
    "Give an example of a prompt injection attack.",
    "What is an example of indirect prompt injection?",
    "How would an attacker use 'ignore previous instructions' in a real system?",
    "Why does 'ignore previous instructions' work as an injection?",
    "Why do jailbreaks often frame requests as hypothetical or fictional?",
    "Why do attackers use base64 encoding in prompt injections?",
    "How do content moderation systems detect jailbreaks?",
    "How do you build a prompt injection detection classifier?",
    "What features are useful for detecting prompt injection?",
    "What training data is needed to detect prompt injection?",
    "Can BERT detect prompt injection?",
    "Why does semantic similarity help detect paraphrased injections?",
    "What is the false positive rate of prompt injection detectors?",
    "How do we reduce false positives in prompt injection detection?",
    "Explain why 'What is prompt injection?' should not be flagged as malicious.",
    "Explain why 'Explain prompt injection' is a benign educational query.",
    "How should AI safety researchers phrase questions to avoid false positives?",
    "Should 'What is the DAN jailbreak?' be classified as malicious? No, it is educational.",
    "The query 'describe a prompt injection attack' is benign because it asks for information.",
    "A user asking 'how do attackers use ignore-previous-instructions' wants to learn, not attack.",
    "Security students often ask 'what is a jailbreak' as part of their coursework.",
    "Understanding prompt injection is the first step to preventing it.",
    "Studying jailbreaks helps AI safety researchers improve model robustness.",
    "Asking what a jailbreak is does not constitute performing a jailbreak.",
    "The difference between studying an attack and performing one is intent and action.",
    "Information about prompt injection exists in textbooks, papers, and online courses.",
    # Varied phrasing
    "Summarize how prompt injection attacks work.",
    "Overview of LLM jailbreaking techniques",
    "History of AI jailbreaks",
    "Top 10 LLM vulnerabilities",
    "How to secure an LLM application against prompt injection",
    "LLM security best practices",
    "How to audit an AI system for prompt injection vulnerabilities",
    "Penetration testing AI systems",
    "Red-teaming language models",
    "Explaining OWASP LLM Top 10 to my team",
    "Briefing on AI security risks for executives",
    "What should a developer know about prompt injection?",
    "Prompt injection for beginners",
    "Advanced prompt injection techniques (academic overview)",
    "Prompt injection in RAG systems",
    "How do agents become vulnerable to prompt injection?",
    "What safety measures does ChatGPT have against jailbreaks?",
    "What is the current state of LLM safety research?",
    "Future directions in prompt injection defense",
    "What is Anthropic's approach to AI safety?",
    "What is Constitutional AI and how does it reduce jailbreaks?",
    "What is RLHF and why does it help with AI safety?",
    "What is reward hacking in RL?",
    "What is Goodhart's Law in the context of AI safety?",
    "Explain prompt injection to a non-technical audience.",
    "What should be in a responsible AI policy about prompt injection?",
    "How do you write a disclosure report for an LLM vulnerability?",
]

print(f"\nBenign category sizes:")
print(f"  SHORT_CONVERSATIONAL         : {len(SHORT_CONVERSATIONAL)}")
print(f"  WHAT_IS_QUESTIONS            : {len(WHAT_IS_QUESTIONS)}")
print(f"  SHOW_TELL_ASK                : {len(SHOW_TELL_ASK)}")
print(f"  GENERAL_KNOWLEDGE            : {len(GENERAL_KNOWLEDGE)}")
print(f"  MATH_SCIENCE                 : {len(MATH_SCIENCE)}")
print(f"  PROGRAMMING                  : {len(PROGRAMMING)}")
print(f"  CYBERSECURITY_BENIGN         : {len(CYBERSECURITY_BENIGN)}")
print(f"  PROMPT_INJECTION_EDUCATION   : {len(PROMPT_INJECTION_EDUCATION)}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION D -- Collision audit of ALL synthetic benign examples
# ─────────────────────────────────────────────────────────────────────────────
print("\nRunning collision audit against malicious training examples...")

all_synthetic_raw = []
category_map = {
    "synthetic_short":      SHORT_CONVERSATIONAL,
    "synthetic_what_is":    WHAT_IS_QUESTIONS,
    "synthetic_show_tell":  SHOW_TELL_ASK,
    "synthetic_general":    GENERAL_KNOWLEDGE,
    "synthetic_math_sci":   MATH_SCIENCE,
    "synthetic_programming":PROGRAMMING,
    "synthetic_cybersec":   CYBERSECURITY_BENIGN,
    "synthetic_pi_edu":     PROMPT_INJECTION_EDUCATION,
}

collision_report = []
phase5e_collision_report = []
clean_synthetic = []

for source, texts in category_map.items():
    for text in texts:
        key = text.strip().lower()
        if key in malicious_all:
            collision_report.append((source, text, "EXACT in malicious"))
        elif key in phase5e_missed_keys:
            phase5e_collision_report.append((source, text, "MATCHES Phase5E missed attack"))
            # Still add it if not in malicious_all (may be coincidental near-match)
            clean_synthetic.append({"text": text.strip(), "label": 0, "source": source})
        else:
            clean_synthetic.append({"text": text.strip(), "label": 0, "source": source})

print(f"  Exact malicious collisions found and REMOVED: {len(collision_report)}")
for src, txt, reason in collision_report:
    print(f"    [{src}] '{txt[:60]}' ({reason})")

print(f"  Phase 5E near-collisions (kept but flagged): {len(phase5e_collision_report)}")
for src, txt, reason in phase5e_collision_report:
    print(f"    [{src}] '{txt[:60]}' ({reason})")

print(f"  Clean synthetic benign examples: {len(clean_synthetic)}")

synthetic_df = pd.DataFrame(clean_synthetic)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION E -- Load and normalize original training data
# ─────────────────────────────────────────────────────────────────────────────
print("\nLoading and normalizing training data...")

train_benign    = train_orig[train_orig.label == 0].copy()
train_malicious = train_orig[train_orig.label == 1].copy()

# Normalize ONLY benign rows (same as Phase 5D)
train_benign["text"] = train_benign["text"].apply(normalize_text)

n_sys_before = (train_orig[train_orig.label==0]["text"]
                .str.startswith("System:").sum())
n_sys_after  = train_benign["text"].str.startswith("System:").sum()
print(f"  Benign 'System:' prefix: {n_sys_before} -> {n_sys_after}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION F -- Overlap guard
# ─────────────────────────────────────────────────────────────────────────────
print("\nLoading guard sets...")
val_df       = pd.read_csv(VAL_CSV)
test_df      = pd.read_csv(TEST_CSV)
challenge_df = pd.read_csv(CHALLENGE_CSV)

guard_texts = set()
for gdf in [challenge_df, val_df, test_df]:
    guard_texts.update(gdf["text"].astype(str).str.strip().str.lower())
print(f"  Guard set: {len(guard_texts)} texts")

def apply_guard(df):
    before = len(df)
    mask   = ~df["text"].str.strip().str.lower().isin(guard_texts)
    after  = mask.sum()
    if before - after:
        print(f"    Guard removed {before-after} rows")
    return df[mask]

synthetic_df = apply_guard(synthetic_df)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION G -- Combine, cross-label conflict detection, dedup
# ─────────────────────────────────────────────────────────────────────────────
print("\nCombining datasets...")

combined_benign = pd.concat(
    [train_benign[["text","label","source"]],
     synthetic_df[["text","label","source"]]],
    ignore_index=True
)

# Dedup benign by key
combined_benign["_key"] = combined_benign["text"].str.strip().str.lower()
b_before = len(combined_benign)
combined_benign = combined_benign.drop_duplicates("_key")
print(f"  Benign dedup: {b_before} -> {len(combined_benign)}")

# Dedup malicious by key
train_malicious["_key"] = train_malicious["text"].str.strip().str.lower()
m_before = len(train_malicious)
train_malicious = train_malicious.drop_duplicates("_key")
print(f"  Malicious dedup: {m_before} -> {len(train_malicious)}")

# Cross-label conflict detection
benign_keys    = set(combined_benign["_key"])
malicious_keys = set(train_malicious["_key"])
conflicts      = benign_keys & malicious_keys

print(f"\n  Cross-label conflicts detected: {len(conflicts)}")
if conflicts:
    print("  Conflicting texts (BENIGN ENTRY REMOVED):")
    for k in sorted(conflicts):
        print(f"    '{k[:70]}'")
    # Remove conflicting rows from benign (conservative -- malicious takes priority)
    combined_benign = combined_benign[~combined_benign["_key"].isin(conflicts)]
    print(f"  Benign after conflict resolution: {len(combined_benign)}")

# Final combine
combined_benign    = combined_benign.drop(columns="_key")
train_malicious    = train_malicious.drop(columns="_key")

phase5f_df = pd.concat(
    [combined_benign[["text","label","source"]],
     train_malicious[["text","label","source"]]],
    ignore_index=True
).sample(frac=1, random_state=42).reset_index(drop=True)

print(f"\n  Phase 5F dataset: {len(phase5f_df)} rows")
print(f"    Benign    : {(phase5f_df.label==0).sum()}")
print(f"    Malicious : {(phase5f_df.label==1).sum()}")
print(f"    Ratio     : {(phase5f_df.label==1).sum()/(phase5f_df.label==0).sum():.3f}x")

# Final guard check
keys = phase5f_df["text"].str.strip().str.lower()
remaining_overlap = keys.isin(guard_texts).sum()
print(f"  Final guard overlap: {remaining_overlap}")

# Final cross-label check
keys_dup = keys.duplicated(keep=False)
if keys_dup.any():
    xl = (phase5f_df[keys_dup].assign(k=keys)
          .groupby("k")["label"].apply(lambda x: x.nunique() > 1).sum())
    print(f"  Final cross-label conflicts: {xl}")
else:
    print(f"  Final cross-label conflicts: 0")

# Final pass: remove any remaining guard overlaps before saving
final_keys = phase5f_df["text"].str.strip().str.lower()
guard_remaining = final_keys.isin(guard_texts)
if guard_remaining.sum():
    print(f"  Removing {guard_remaining.sum()} remaining guard overlaps...")
    phase5f_df = phase5f_df[~guard_remaining].reset_index(drop=True)
    print(f"  After final guard removal: {len(phase5f_df)} rows")
    print(f"    Benign    : {(phase5f_df.label==0).sum()}")
    print(f"    Malicious : {(phase5f_df.label==1).sum()}")

# Refresh lists after final cleanup
p5f_b = phase5f_df[phase5f_df.label==0]["text"].tolist()
p5f_m = phase5f_df[phase5f_df.label==1]["text"].tolist()

phase5f_df.to_csv(OUT_CSV, index=False)
print(f"\n  Saved: {OUT_CSV}")

# ─────────────────────────────────────────────────────────────────────────────
# SECTION H -- 3-way audit
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("3-WAY AUDIT: ORIGINAL vs PHASE 5D vs PHASE 5F")
print("="*70)

# Load Phase 5D for comparison
train_p5d = pd.read_csv(TRAIN_P5D)

def token_len(s):  return len(str(s).split())
def count_substr(texts, term):
    t = term.lower()
    return sum(1 for x in texts if t in str(x).lower())
def count_exact_sw(texts):
    return sum(1 for x in texts if len(str(x).split()) == 1)
def pct(n, d):     return f"{n/d*100:.1f}%" if d else "N/A"

orig_b  = train_orig[train_orig.label==0]["text"].tolist()
orig_m  = train_orig[train_orig.label==1]["text"].tolist()
p5d_b   = train_p5d[train_p5d.label==0]["text"].tolist()
p5d_m   = train_p5d[train_p5d.label==1]["text"].tolist()
p5f_b   = phase5f_df[phase5f_df.label==0]["text"].tolist()
p5f_m   = phase5f_df[phase5f_df.label==1]["text"].tolist()

# ─────────────────────────────────────────────────────────────────────────────
# Build markdown report
# ─────────────────────────────────────────────────────────────────────────────
md = []
md.append("# PHASE 5F Dataset Audit Report\n")
md.append("> **Constraint:** Dataset construction only. No training, no model changes.\n")
md.append(f"\n---\n")

md.append("## 1. Row Counts and Class Balance\n")
md.append("| Metric | Original | Phase 5D | Phase 5F |\n|---|---|---|---|\n")
for label, vals in [
    ("Total rows",            [len(train_orig), len(train_p5d), len(phase5f_df)]),
    ("Benign (label=0)",      [len(orig_b), len(p5d_b), len(p5f_b)]),
    ("Malicious (label=1)",   [len(orig_m), len(p5d_m), len(p5f_m)]),
    ("Mal/Ben ratio",         [
        f"{len(orig_m)/len(orig_b):.3f}x",
        f"{len(p5d_m)/len(p5d_b):.3f}x",
        f"{len(p5f_m)/len(p5f_b):.3f}x"]),
]:
    row = f"| {label} |"
    for v in vals:
        row += f" {v:,} |" if isinstance(v, int) else f" {v} |"
    md.append(row + "\n")

md.append("\n## 2. Single-Word and Short-Text Distribution\n")
md.append("| Metric | Original | Phase 5D | Phase 5F |\n|---|---|---|---|\n")

sw_ob = count_exact_sw(orig_b); sw_om = count_exact_sw(orig_m)
sw_pb = count_exact_sw(p5d_b);  sw_pm = count_exact_sw(p5d_m)
sw_fb = count_exact_sw(p5f_b);  sw_fm = count_exact_sw(p5f_m)

le3_ob = sum(1 for t in orig_b if token_len(t)<=3); le3_om = sum(1 for t in orig_m if token_len(t)<=3)
le3_pb = sum(1 for t in p5d_b  if token_len(t)<=3); le3_pm = sum(1 for t in p5d_m  if token_len(t)<=3)
le3_fb = sum(1 for t in p5f_b  if token_len(t)<=3); le3_fm = sum(1 for t in p5f_m  if token_len(t)<=3)

le5_ob = sum(1 for t in orig_b if token_len(t)<=5); le5_om = sum(1 for t in orig_m if token_len(t)<=5)
le5_pb = sum(1 for t in p5d_b  if token_len(t)<=5); le5_pm = sum(1 for t in p5d_m  if token_len(t)<=5)
le5_fb = sum(1 for t in p5f_b  if token_len(t)<=5); le5_fm = sum(1 for t in p5f_m  if token_len(t)<=5)

r_sw_o  = sw_om/max(sw_ob,1);   r_sw_d  = sw_pm/max(sw_pb,1);   r_sw_f  = sw_fm/max(sw_fb,1)
r_le3_o = le3_om/max(le3_ob,1); r_le3_d = le3_pm/max(le3_pb,1); r_le3_f = le3_fm/max(le3_fb,1)
r_le5_o = le5_om/max(le5_ob,1); r_le5_d = le5_pm/max(le5_pb,1); r_le5_f = le5_fm/max(le5_fb,1)

for label, o, d, f in [
    ("Single-word benign",        sw_ob,  sw_pb,  sw_fb),
    ("Single-word malicious",     sw_om,  sw_pm,  sw_fm),
    ("Mal/Ben ratio (1-token)",
     f"{r_sw_o:.1f}x",  f"{r_sw_d:.1f}x", f"{r_sw_f:.1f}x"),
    ("<=3-token benign",          le3_ob, le3_pb, le3_fb),
    ("<=3-token malicious",       le3_om, le3_pm, le3_fm),
    ("Mal/Ben ratio (<=3-token)",
     f"{r_le3_o:.1f}x", f"{r_le3_d:.1f}x",f"{r_le3_f:.1f}x"),
    ("<=5-token benign",          le5_ob, le5_pb, le5_fb),
    ("<=5-token malicious",       le5_om, le5_pm, le5_fm),
    ("Mal/Ben ratio (<=5-token)",
     f"{r_le5_o:.1f}x", f"{r_le5_d:.1f}x",f"{r_le5_f:.1f}x"),
    ("% <=3-token benign",
     pct(le3_ob,len(orig_b)), pct(le3_pb,len(p5d_b)), pct(le3_fb,len(p5f_b))),
    ("% <=3-token malicious",
     pct(le3_om,len(orig_m)), pct(le3_pm,len(p5d_m)), pct(le3_fm,len(p5f_m))),
]:
    row = f"| {label} |"
    for v in [o, d, f]:
        row += f" {v:,} |" if isinstance(v, int) else f" {v} |"
    md.append(row + "\n")

md.append("\n## 3. Key Phrase Frequency Distributions\n")
PHRASES = [
    ("what is",   '"what is"'),
    ("show me",   '"show me"'),
    ("tell me",   '"tell me"'),
    ("how do",    '"how do"'),
    ("explain",   '"explain"'),
    ("attack",    '"attack"'),
    ("password",  '"password"'),
    ("jailbreak", '"jailbreak"'),
    ("ignore",    '"ignore"'),
    ("previous",  '"previous"'),
    ("oauth",     '"oauth"'),
    ("sql",       '"sql"'),
    ("prompt",    '"prompt"'),
    ("injection", '"injection"'),
]
md.append("| Phrase | Orig_B | Orig_M | P5D_B | P5D_M | P5F_B | P5F_M | "
          "Orig M/B | P5D M/B | P5F M/B |\n")
md.append("|---|---|---|---|---|---|---|---|---|---|\n")
for phrase, lbl in PHRASES:
    ob = count_substr(orig_b, phrase); om = count_substr(orig_m, phrase)
    pb = count_substr(p5d_b,  phrase); pm = count_substr(p5d_m,  phrase)
    fb = count_substr(p5f_b,  phrase); fm = count_substr(p5f_m,  phrase)
    r_o = (om/len(orig_m))/(ob/len(orig_b)+1e-9)
    r_d = (pm/len(p5d_m)) /(pb/len(p5d_b)+1e-9)
    r_f = (fm/len(p5f_m)) /(fb/len(p5f_b)+1e-9)
    md.append(f"| {lbl} | {ob:,} | {om:,} | {pb:,} | {pm:,} | {fb:,} | {fm:,} | "
              f"{r_o:.2f}x | {r_d:.2f}x | {r_f:.2f}x |\n")

md.append("\n## 4. Specific Term Coverage\n")
md.append("| Term | Orig benign | P5D benign | P5F benign | Status |\n|---|---|---|---|---|\n")
TERMS = [
    "hi", "hello", "ok", "okay", "go", "attack",
    "dos attack", "ddos attack", "ransomware", "phishing",
    "sql injection", "xss", "csrf", "buffer overflow",
    "password attack", "network attack", "oauth", "tls",
    "siem", "zero-day", "malware", "jailbreak",
    "prompt injection", "what is prompt",
]
for term in TERMS:
    ob = count_substr(orig_b, term)
    pb = count_substr(p5d_b,  term)
    fb = count_substr(p5f_b,  term)
    status = "OK" if fb > 0 else "MISSING"
    if ob == 0 and pb == 0 and fb > 0: status = "NEW"
    elif ob == 0 and fb > 0: status = "FIXED"
    md.append(f"| `{term}` | {ob:,} | {pb:,} | {fb:,} | {status} |\n")

md.append("\n## 5. Cybersecurity Benign Coverage\n")
CYBER_TERMS = [
    "dos attack","ddos attack","ransomware","phishing","sql injection",
    "xss","csrf","buffer overflow","password attack","network attack",
    "oauth","tls","siem","zero-day","malware","exploit","jailbreak",
]
md.append("| Term | Orig benign | P5D benign | P5F benign | Status |\n|---|---|---|---|---|\n")
for term in CYBER_TERMS:
    ob = count_substr(orig_b, term)
    pb = count_substr(p5d_b,  term)
    fb = count_substr(p5f_b,  term)
    status = "OK" if fb > 0 else "MISSING"
    if ob == 0 and fb > 0: status = "FIXED"
    md.append(f"| `{term}` | {ob:,} | {pb:,} | {fb:,} | {status} |\n")

md.append("\n## 6. Prompt-Injection Educational Coverage\n")
PI_TERMS = [
    ("prompt injection",   "prompt injection (any)"),
    ("jailbreak",          "jailbreak (any)"),
    ("what is prompt",     '"what is prompt"'),
    ("how does prompt",    '"how does prompt"'),
    ("indirect prompt",    "indirect prompt injection"),
    ("adversarial",        "adversarial prompting"),
    ("llm security",       "LLM security"),
    ("owasp top 10 for",   "OWASP LLM Top 10"),
    ("red-team",           "red-teaming LLMs"),
    ("gandalf",            "Gandalf challenges"),
    ("constitutional ai",  "Constitutional AI"),
]
md.append("| Topic | Orig benign | P5D benign | P5F benign | Status |\n|---|---|---|---|---|\n")
for term, lbl in PI_TERMS:
    ob = count_substr(orig_b, term)
    pb = count_substr(p5d_b,  term)
    fb = count_substr(p5f_b,  term)
    status = "OK" if fb > 0 else "MISSING"
    if ob == 0 and fb > 0: status = "FIXED"
    md.append(f"| {lbl} | {ob:,} | {pb:,} | {fb:,} | {status} |\n")

md.append("\n## 7. Phase 5E Newly-Missed Attack Collision Check\n")
md.append("> Tests whether Phase 5F benign training examples collide with "
          "Phase 5E newly-missed malicious examples.\n\n")
md.append("| Phase 5E missed attack | In P5F benign? | In P5D benign? | "
          "In original malicious? | Risk |\n|---|---|---|---|---|\n")
for attack in PHASE5E_NEWLY_MISSED:
    key = attack.strip().lower()
    in_p5f_ben  = any(key == t.strip().lower() for t in p5f_b)
    in_p5d_ben  = any(key == t.strip().lower() for t in p5d_b)
    in_orig_mal = key in malicious_all
    risk = "HIGH" if in_p5f_ben and in_orig_mal else ("MEDIUM" if in_p5f_ben else "OK")
    md.append(f"| `{attack[:50]}` | {'YES' if in_p5f_ben else 'no'} | "
              f"{'YES' if in_p5d_ben else 'no'} | "
              f"{'YES' if in_orig_mal else 'no'} | {risk} |\n")

md.append("\n## 8. Formatting Artifact Check\n")
import re as re2
def pct_pat(texts, pat):
    n = sum(1 for t in texts if re2.search(pat, str(t), re2.IGNORECASE))
    return pct(n, len(texts))

md.append("| Pattern | Orig_B | P5D_B | P5F_B | Orig_M | P5D_M | P5F_M |\n"
          "|---|---|---|---|---|---|---|\n")
for pat, lbl in [
    (r"^System:",       "Starts with 'System:'"),
    (r"^Instruction:",  "Starts with 'Instruction:'"),
    (r"\n",             "Contains newline"),
    (r"\?",             "Contains '?'"),
    (r"^What",          "Starts with 'What'"),
    (r"^How",           "Starts with 'How'"),
]:
    md.append(f"| {lbl} | {pct_pat(orig_b,pat)} | {pct_pat(p5d_b,pat)} | "
              f"{pct_pat(p5f_b,pat)} | {pct_pat(orig_m,pat)} | "
              f"{pct_pat(p5d_m,pat)} | {pct_pat(p5f_m,pat)} |\n")

md.append("\n## 9. Data Integrity\n")
p5f_keys = phase5f_df["text"].str.strip().str.lower()
ch_set   = set(challenge_df["text"].str.strip().str.lower())
val_set  = set(val_df["text"].str.strip().str.lower())
te_set   = set(test_df["text"].str.strip().str.lower())
p5f_set  = set(p5f_keys)

md.append("| Check | Result |\n|---|---|\n")
md.append(f"| P5F overlap with benign_challenge.csv | {len(p5f_set & ch_set)} |\n")
md.append(f"| P5F overlap with val.csv              | {len(p5f_set & val_set)} |\n")
md.append(f"| P5F overlap with test.csv             | {len(p5f_set & te_set)} |\n")
dup_keys = p5f_keys.duplicated(keep=False)
cross_lbl = 0
if dup_keys.any():
    cross_lbl = (phase5f_df[dup_keys].assign(k=p5f_keys)
                 .groupby("k")["label"].apply(lambda x: x.nunique()>1).sum())
md.append(f"| Duplicate texts in P5F                | {dup_keys.sum()} |\n")
md.append(f"| Cross-label conflicts                  | {cross_lbl} |\n")
md.append(f"| Exact collision removals during build  | {len(collision_report)} |\n")

md.append("\n## 10. Source Distribution (Phase 5F)\n")
src_tab = (phase5f_df.groupby(["source","label"]).size()
           .unstack(fill_value=0))
# Manual markdown table (no tabulate dependency)
md.append("| source | 0 (benign) | 1 (malicious) |\n|---|---|---|\n")
for src in sorted(src_tab.index):
    b_cnt = src_tab.loc[src, 0] if 0 in src_tab.columns else 0
    m_cnt = src_tab.loc[src, 1] if 1 in src_tab.columns else 0
    md.append(f"| {src} | {b_cnt:,} | {m_cnt:,} |\n")

md.append("\n## 11. Short-Text Bias Scorecard\n")
md.append("> [!IMPORTANT]\n")
md.append("> Phase 5D RC-A root cause: single-word mal/ben ratio was 0.6x "
          "(model learned short = SAFE). Phase 5F target: ratio closer to "
          "original (~137x) to avoid the over-correction, BUT with the original "
          "137x not reflecting reality either. A healthy ratio is ~5-20x "
          "(malicious short texts are more common than benign, but not exclusively).\n\n")

def scorecard_row(label, orig_v, p5d_v, p5f_v, ok_fn):
    orig_ok = ok_fn(orig_v); p5d_ok = ok_fn(p5d_v); p5f_ok = ok_fn(p5f_v)
    def s(ok): return "OK" if ok else "ISSUE"
    return (f"| {label} | {orig_v} ({s(orig_ok)}) | "
            f"{p5d_v} ({s(p5d_ok)}) | {p5f_v} ({s(p5f_ok)}) |\n")

md.append("| Metric | Original | Phase 5D | Phase 5F |\n|---|---|---|---|\n")
md.append(scorecard_row(
    "Single-word mal/ben ratio",
    f"{r_sw_o:.1f}x", f"{r_sw_d:.1f}x", f"{r_sw_f:.1f}x",
    lambda v: float(v.rstrip("x")) >= 3
))
md.append(scorecard_row(
    "<=3-token mal/ben ratio",
    f"{r_le3_o:.1f}x", f"{r_le3_d:.1f}x", f"{r_le3_f:.1f}x",
    lambda v: float(v.rstrip("x")) >= 2
))
md.append(scorecard_row(
    "% benign is single-word",
    pct(sw_ob,len(orig_b)), pct(sw_pb,len(p5d_b)), pct(sw_fb,len(p5f_b)),
    lambda v: True
))
md.append(scorecard_row(
    "% benign is <=3-token",
    pct(le3_ob,len(orig_b)), pct(le3_pb,len(p5d_b)), pct(le3_fb,len(p5f_b)),
    lambda v: True
))

md.append("\n## 12. Recommendation Checklist\n")
checks = [
    ("Phase 5D formatting cleanup (System: removed from benign)",
     n_sys_after == 0),
    ("Zero cross-label conflicts in P5F",
     cross_lbl == 0),
    ("Zero guard-set overlap",
     len(p5f_set & ch_set) == 0 and len(p5f_set & val_set) == 0 and len(p5f_set & te_set) == 0),
    ("All 17 cyber terms covered in benign",
     all(count_substr(p5f_b, t) > 0 for t in CYBER_TERMS)),
    ("Prompt-injection education benign coverage > 50 rows",
     count_substr(p5f_b, "prompt injection") > 50),
    ("Single-word benign/malicious ratio > 3x (not over-corrected SAFE)",
     r_sw_f >= 3),
    ("<=3-token benign/malicious ratio > 2x (not over-corrected SAFE)",
     r_le3_f >= 2),
    ("No Phase 5E missed attacks in P5F benign (exact match)",
     all(not any(a.strip().lower()==t.strip().lower() for t in p5f_b)
         for a in PHASE5E_NEWLY_MISSED[:5])),
]
md.append("| Check | Status |\n|---|---|\n")
for label, passed in checks:
    md.append(f"| {label} | {'PASS' if passed else 'FAIL'} |\n")

md.append(f"\n---\n_Generated by `ml/build_phase5f_dataset.py`. "
          f"No models or existing datasets modified._\n")

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(f"\nReport written to: {REPORT_PATH}")
print("Phase 5F-A complete. Stopping for review.")
