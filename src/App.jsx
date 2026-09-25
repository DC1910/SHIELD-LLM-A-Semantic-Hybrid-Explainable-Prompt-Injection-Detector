import { useEffect, useState, useRef } from "react"

function App() {
  const [page, setPage] = useState("console")
  const [prompt, setPrompt] = useState("")
  const [result, setResult] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [techOpen, setTechOpen] = useState(false)



  // ============================================================
  // PROMPT ANALYSIS
  // ============================================================

  const analyzePrompt = async () => {
    if (!prompt.trim() || scanning) return

    setScanning(true)
    setResult(null)

    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: prompt,
        }),
      })

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`)
      }

      const data = await response.json()

      setResult(data)
    } catch (error) {
      console.error("Failed to analyze prompt:", error)

      setResult({
        verdict: "suspicious",
        combined_score: 0,
        detectors: {
          classifier: 0,
          semantic: 0,
          rules: {
            matched: false,
            categories: [],
          },
        },
        explanation:
          "Unable to connect to the SHIELD-LLM backend. Make sure the FastAPI server is running on port 8000.",
        llm_response: null,
      })
    } finally {
      setScanning(false)
    }
  }

  // ============================================================
  // VERDICT STYLES
  // ============================================================

  const verdictStyle = {
    safe: {
      border: "border-emerald-400/25",
      glow: "shadow-[0_0_80px_rgba(52,211,153,.08)]",
      badge:
        "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
      text: "text-emerald-300",
      accent: "emerald",
      label: "PROMPT CLEARED",
    },

    suspicious: {
      border: "border-amber-400/25",
      glow: "shadow-[0_0_80px_rgba(251,191,36,.08)]",
      badge:
        "border-amber-400/25 bg-amber-400/10 text-amber-300",
      text: "text-amber-300",
      accent: "amber",
      label: "REVIEW REQUIRED",
    },

    malicious: {
      border: "border-rose-400/25",
      glow: "shadow-[0_0_80px_rgba(244,63,94,.08)]",
      badge:
        "border-rose-400/25 bg-rose-400/10 text-rose-300",
      text: "text-rose-300",
      accent: "rose",
      label: "THREAT DETECTED",
    },
  }

  const currentStyle = result
    ? verdictStyle[result.verdict]
    : verdictStyle.safe

  // ============================================================
  // MAIN APP
  // ============================================================

  return (
    <div className="min-h-screen bg-[#050816] text-white overflow-hidden">

      {/* ======================================================
          BACKGROUND
      ====================================================== */}

      <div className="fixed inset-0 pointer-events-none">

        {/* Main glow */}
        <div className="absolute top-[-250px] left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-indigo-600/15 blur-[150px] rounded-full" />

        {/* Left glow */}
        <div className="absolute top-[45%] left-[-250px] w-[500px] h-[500px] bg-violet-600/10 blur-[140px] rounded-full" />

        {/* Right glow */}
        <div className="absolute top-[50%] right-[-250px] w-[500px] h-[500px] bg-cyan-500/10 blur-[140px] rounded-full" />

        {/* Grid */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,.8) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.8) 1px, transparent 1px)",
            backgroundSize: "50px 50px",
          }}
        />
      </div>

      {/* ======================================================
          NAVBAR
      ====================================================== */}

      <nav className="relative z-20 border-b border-white/[0.06] bg-[#050816]/75 backdrop-blur-xl">

        <div className="max-w-7xl mx-auto px-6 lg:px-10 h-20 flex items-center justify-between">

          {/* Logo */}
          <div className="flex items-center gap-3">

            <div className="relative w-10 h-10 rounded-xl border border-indigo-400/30 bg-indigo-500/10 flex items-center justify-center">

              <div className="absolute inset-0 rounded-xl bg-indigo-500/20 blur-xl" />

              <svg
                className="relative w-6 h-6 text-indigo-300"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M12 3L19 6V11C19 16 16 19 12 21C8 19 5 16 5 11V6L12 3Z" />
                <path d="M9 12L11 14L15 10" />
              </svg>
            </div>

            <div>
              <span className="text-lg font-bold tracking-tight">
                SHEILD<span className="text-indigo-400">-LLM</span>
              </span>

              <p className="text-[9px] text-gray-600 font-mono tracking-[0.2em]">
                AI SECURITY ENGINE
              </p>
            </div>
          </div>

          {/* Navigation */}
          <div className="hidden md:flex items-center gap-8 text-sm">

            <button
              onClick={() => setPage("console")}
              className={`transition ${page === "console"
                ? "text-white"
                : "text-gray-500 hover:text-white"
                }`}
            >
              Security Console
            </button>

            <button
              onClick={() => setPage("dashboard")}
              className={`transition ${page === "dashboard"
                ? "text-white"
                : "text-gray-500 hover:text-white"
                }`}
            >
              Dashboard
            </button>
          </div>

          {/* System status */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.04]">

            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_#34d399]" />

            <span className="hidden sm:block text-[10px] text-emerald-400 font-mono tracking-wider">
              SYSTEM ONLINE
            </span>
          </div>

        </div>
      </nav>

      {/* ======================================================
          MAIN
      ====================================================== */}

      <main className="relative z-10 max-w-6xl mx-auto px-6 lg:px-10">

        {page === "dashboard" ? (
          <Dashboard />
        ) : (

          <section className="pt-16 pb-24">

            {/* ==================================================
                HERO
            ================================================== */}

            <div className="text-center max-w-4xl mx-auto">

              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-indigo-400/20 bg-indigo-400/[0.05] mb-6">

                <span className="text-indigo-300 text-xs">
                  ✦
                </span>

                <span className="text-[10px] text-indigo-200 font-mono tracking-[0.2em]">
                  HYBRID AI SECURITY
                </span>
              </div>

              <h1 className="text-5xl md:text-7xl font-black tracking-[-0.04em] leading-[0.95]">

                Protect your

                <br />

                <span className="bg-gradient-to-r from-indigo-300 via-violet-400 to-cyan-300 bg-clip-text text-transparent">
                  LLM from the unknown.
                </span>

              </h1>

              <p className="mt-7 text-gray-400 max-w-2xl mx-auto leading-relaxed">
                Detect malicious prompts, injection attempts and suspicious
                instructions before they reach your AI model.
              </p>

            </div>

            {/* ==================================================
                FUSION CORE
            ================================================== */}

            <div className="relative max-w-4xl mx-auto h-[260px] mt-4">

              {/* Lines */}
              <div className="absolute left-[10%] top-1/2 w-[30%] h-px bg-gradient-to-r from-transparent via-indigo-500/40 to-indigo-400/60" />

              <div className="absolute right-[10%] top-1/2 w-[30%] h-px bg-gradient-to-r from-indigo-400/60 via-cyan-400/40 to-transparent" />

              {/* Left nodes */}
              <div className="absolute left-[9%] top-[44%] w-12 h-12 rounded-full border border-indigo-400/30 bg-indigo-500/10 flex items-center justify-center text-indigo-300">
                ◇
              </div>

              <div className="absolute left-[20%] top-[25%] w-9 h-9 rounded-full border border-violet-400/30 bg-violet-400/10 flex items-center justify-center text-violet-300">
                +
              </div>

              <div className="absolute left-[20%] top-[65%] w-9 h-9 rounded-full border border-cyan-400/30 bg-cyan-400/10 flex items-center justify-center text-cyan-300">
                +
              </div>

              {/* Right nodes */}
              <div className="absolute right-[9%] top-[44%] w-12 h-12 rounded-full border border-cyan-400/30 bg-cyan-400/10 flex items-center justify-center text-cyan-300">
                ◇
              </div>

              <div className="absolute right-[20%] top-[25%] w-9 h-9 rounded-full border border-violet-400/30 bg-violet-400/10 flex items-center justify-center text-violet-300">
                +
              </div>

              <div className="absolute right-[20%] top-[65%] w-9 h-9 rounded-full border border-indigo-400/30 bg-indigo-400/10 flex items-center justify-center text-indigo-300">
                +
              </div>

              {/* Core */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">

                <div className="absolute -inset-14 rounded-full border border-indigo-400/10 animate-[spin_18s_linear_infinite]" />

                <div className="absolute -inset-9 rounded-full border border-violet-400/10 border-dashed animate-[spin_12s_linear_infinite_reverse]" />

                <div className="absolute -inset-16 rounded-full bg-indigo-600/15 blur-[60px]" />

                <div className="relative w-32 h-32 rounded-[2rem] border border-indigo-300/30 bg-[#0c1229]/95 backdrop-blur-xl shadow-[0_0_70px_rgba(99,102,241,.25)] flex flex-col items-center justify-center">

                  <span className="text-3xl text-indigo-300">
                    ✦
                  </span>

                  <span className="text-sm font-bold tracking-wider mt-2">
                    SHEILD
                  </span>

                  <span className="text-[8px] text-gray-600 font-mono tracking-widest mt-1">
                    FUSION CORE
                  </span>

                </div>
              </div>
            </div>

            {/* ==================================================
                PROMPT ANALYZER
            ================================================== */}

            <div className="max-w-4xl mx-auto">

              <div className="relative">

                <div className="absolute -inset-1 bg-gradient-to-r from-indigo-500/10 via-violet-500/20 to-cyan-500/10 blur-xl rounded-3xl" />

                <div className="relative rounded-3xl border border-white/[0.09] bg-[#0a1020]/95 backdrop-blur-xl p-2">

                  <div className="rounded-2xl border border-white/[0.05] bg-[#070b15] p-6 md:p-7">

                    <div className="flex items-center justify-between mb-5">

                      <div>
                        <p className="text-[10px] text-indigo-300 font-mono tracking-[0.25em]">
                          PROMPT ANALYZER
                        </p>

                        <p className="text-xs text-gray-500 mt-1">
                          Test a prompt against the detection engine
                        </p>
                      </div>

                      <span className="text-[10px] text-gray-600 font-mono">
                        SECURE INPUT
                      </span>
                    </div>

                    <textarea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="Enter a prompt to analyze..."
                      className="w-full h-36 bg-[#050810] border border-white/[0.07] rounded-xl p-5 text-sm text-gray-200 placeholder-gray-600 font-mono resize-none outline-none focus:border-indigo-400/40 focus:ring-4 focus:ring-indigo-500/[0.06] transition"
                    />

                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-4">

                      <div className="flex items-center gap-3 text-[10px] text-gray-600 font-mono">

                        <span>
                          {prompt.length} CHARACTERS
                        </span>

                        <span className="w-1 h-1 bg-gray-700 rounded-full" />

                        <span>
                          HYBRID DETECTION
                        </span>
                      </div>

                      <button
                        onClick={analyzePrompt}
                        disabled={!prompt.trim() || scanning}
                        className="w-full sm:w-auto px-7 py-3 rounded-xl bg-gradient-to-r from-indigo-500 to-violet-500 text-white font-semibold text-sm shadow-[0_0_25px_rgba(99,102,241,.2)] hover:shadow-[0_0_40px_rgba(99,102,241,.35)] hover:scale-[1.02] transition disabled:opacity-30 disabled:cursor-not-allowed"
                      >
                        {scanning ? (
                          <span className="flex items-center gap-2">

                            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />

                            ANALYZING...

                          </span>
                        ) : (
                          "ANALYZE PROMPT →"
                        )}
                      </button>

                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ==================================================
                SCANNING
            ================================================== */}

            {scanning && (
              <div className="max-w-4xl mx-auto mt-7">

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">

                  {[
                    ["01", "RULE ENGINE"],
                    ["02", "SEMANTIC MODEL"],
                    ["03", "CLASSIFIER"],
                    ["04", "FUSION ENGINE"],
                  ].map(([number, label]) => (

                    <div
                      key={number}
                      className="rounded-xl border border-indigo-400/20 bg-indigo-400/[0.04] p-4 animate-pulse"
                    >
                      <p className="text-[9px] text-indigo-400 font-mono">
                        {number}
                      </p>

                      <p className="text-xs text-gray-300 mt-2">
                        {label}
                      </p>

                      <p className="text-[9px] text-gray-600 font-mono mt-2">
                        SCANNING...
                      </p>
                    </div>

                  ))}

                </div>
              </div>
            )}

            {/* ==================================================
                RESULT
            ================================================== */}

            {result && !scanning && (

              <div className="max-w-4xl mx-auto mt-8">

                <div
                  className={`relative rounded-3xl border ${currentStyle.border} bg-[#0d0b18]/90 backdrop-blur-xl overflow-hidden ${currentStyle.glow} transition-all duration-500`}
                >

                  {/* Dynamic top line */}
                  <div
                    className={`h-[2px] ${result.verdict === "safe"
                      ? "bg-gradient-to-r from-transparent via-emerald-400 to-transparent"
                      : result.verdict === "suspicious"
                        ? "bg-gradient-to-r from-transparent via-amber-400 to-transparent"
                        : "bg-gradient-to-r from-transparent via-rose-400 to-transparent"
                      }`}
                  />

                  <div className="p-7 md:p-9">

                    {/* ==================================================
                        HEADER
                    ================================================== */}

                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-5">

                      <div>

                        <p className="text-[10px] text-gray-500 font-mono tracking-[0.25em]">
                          SECURITY VERDICT
                        </p>

                        <div className="flex flex-wrap items-center gap-4 mt-2">

                          <h2
                            className={`text-4xl md:text-5xl font-black tracking-tight ${currentStyle.text}`}
                          >
                            {result.verdict.toUpperCase()}
                          </h2>

                          <span
                            className={`px-3 py-1.5 rounded-lg border ${currentStyle.badge} text-[10px] font-mono`}
                          >
                            {currentStyle.label}
                          </span>

                        </div>
                      </div>

                      {/* Threat score circle */}
                      <div
                        className={`relative w-24 h-24 rounded-full border ${currentStyle.border} bg-white/[0.02] flex items-center justify-center`}
                      >
                        <div
                          className={`absolute inset-0 rounded-full opacity-10 ${result.verdict === "safe" ? "bg-emerald-400" : result.verdict === "suspicious" ? "bg-amber-400" : "bg-rose-400"
                            } blur-xl`}
                        />
                        <div className="text-center relative">

                          <p className="text-2xl font-black">
                            {(result.combined_score * 100).toFixed(0)}

                            <span className="text-sm text-gray-600">
                              %
                            </span>
                          </p>

                          <p className="text-[7px] text-gray-600 font-mono tracking-widest">
                            THREAT SCORE
                          </p>

                        </div>
                      </div>

                    </div>

                    {/* Divider */}
                    <div className="border-t border-white/[0.06] my-7" />

                    {/* ==================================================
                        ACTION STATUS + ATTACK CATEGORY
                    ================================================== */}

                    <div className="flex flex-wrap items-center gap-3">

                      {/* ALLOWED / FLAGGED / BLOCKED pill */}
                      {(() => {
                        const actionMap = {
                          safe: { label: "ALLOWED", cls: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300 shadow-[0_0_12px_rgba(52,211,153,.12)]" },
                          suspicious: { label: "FLAGGED", cls: "border-amber-400/30 bg-amber-400/10 text-amber-300 shadow-[0_0_12px_rgba(251,191,36,.12)]" },
                          malicious: { label: "BLOCKED", cls: "border-rose-400/30 bg-rose-400/10 text-rose-300 shadow-[0_0_12px_rgba(244,63,94,.12)]" },
                        }
                        const action = actionMap[result.verdict]
                        return (
                          <div className={`flex items-center gap-2 px-4 py-2 rounded-full border font-mono text-xs tracking-widest ${action.cls}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${result.verdict === "safe" ? "bg-emerald-400" : result.verdict === "suspicious" ? "bg-amber-400" : "bg-rose-400"
                              } animate-pulse`} />
                            {action.label}
                          </div>
                        )
                      })()}

                      {/* Attack category tags */}
                      {result.detectors.rules.categories.length > 0 ? (
                        result.detectors.rules.categories.map((cat) => (
                          <span
                            key={cat}
                            className="px-3 py-1.5 rounded-full border border-violet-400/25 bg-violet-400/[0.07] text-[10px] text-violet-300 font-mono tracking-wide"
                          >
                            {cat.toUpperCase()}
                          </span>
                        ))
                      ) : (
                        <span className="px-3 py-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] text-[10px] text-gray-500 font-mono tracking-wide">
                          NO ATTACK CATEGORY
                        </span>
                      )}

                    </div>

                    {/* ==================================================
                        EXPLAINABILITY
                    ================================================== */}

                    <div className="border-t border-white/[0.06] mt-9 pt-7">

                      <div className="flex items-center gap-3 mb-4">

                        <div
                          className={`w-8 h-8 rounded-lg border ${currentStyle.badge} flex items-center justify-center`}
                        >
                          {result.verdict === "malicious" ? "!" : "✓"}
                        </div>

                        <div>

                          <p className="text-[10px] text-gray-500 font-mono tracking-[0.2em]">
                            EXPLAINABILITY
                          </p>

                          <p className="text-xs text-gray-600 mt-0.5">
                            Why SHEILD-LLM classified this prompt
                          </p>

                        </div>
                      </div>

                      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-5">

                        <div className="flex items-start gap-3">

                          <span className={`${currentStyle.text} mt-0.5 text-base`}>
                            {result.verdict === "malicious" ? "⚠" : result.verdict === "suspicious" ? "◈" : "✓"}
                          </span>

                          <div>

                            {/* User-friendly explanation */}
                            <p className="text-sm text-gray-200 leading-relaxed">
                              {result.verdict === "malicious" ? (
                                result.detectors.rules.categories.length > 0
                                  ? `This prompt was identified as a ${result.detectors.rules.categories.map(c =>
                                    c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())
                                  ).join(" / ")
                                  } attack with high confidence. The SHIELD-LLM engine flagged it as malicious and blocked it from reaching the protected LLM.`
                                  : "This prompt was identified as a high-confidence threat by the detection engine. It exhibited strong indicators of prompt-injection or adversarial intent and was blocked from reaching the protected LLM."
                              ) : result.verdict === "suspicious" ? (
                                result.detectors.rules.categories.length > 0
                                  ? `This prompt raised suspicion due to patterns associated with ${result.detectors.rules.categories.map(c =>
                                    c.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())
                                  ).join(" / ")
                                  }. It has been flagged for review — the threat score was elevated but did not cross the high-confidence threshold.`
                                  : "This prompt raised suspicion across one or more detectors. It has been flagged for review — the combined threat score was elevated but did not conclusively indicate a known attack pattern."
                              ) : (
                                "No prompt-injection or adversarial threat was detected in this input. The prompt passed all three security checks — rules engine, semantic similarity, and the DistilBERT classifier — and is cleared to reach the protected LLM."
                              )}
                            </p>

                            {/* Category tags — shown only for non-safe verdicts */}
                            {result.verdict !== "safe" && result.detectors.rules.categories.length > 0 && (
                              <div className="flex flex-wrap gap-2 mt-4">
                                {result.detectors.rules.categories.map((category) => (
                                  <span
                                    key={category}
                                    className={`px-2.5 py-1 rounded-md ${currentStyle.badge} text-[9px] font-mono`}
                                  >
                                    {category.toUpperCase()}
                                  </span>
                                ))}
                                <span className="px-2.5 py-1 rounded-md bg-violet-400/10 border border-violet-400/15 text-[9px] text-violet-300 font-mono">
                                  HYBRID_DETECTION
                                </span>
                              </div>
                            )}

                            {/* Safe — no category tags, just the detection method badge */}
                            {result.verdict === "safe" && (
                              <div className="flex flex-wrap gap-2 mt-4">
                                <span className="px-2.5 py-1 rounded-md bg-violet-400/10 border border-violet-400/15 text-[9px] text-violet-300 font-mono">
                                  HYBRID_DETECTION
                                </span>
                              </div>
                            )}

                          </div>
                        </div>
                      </div>
                    </div>

                    {/* ==================================================
                        COLLAPSIBLE TECHNICAL DETAILS
                    ================================================== */}

                    <div className="mt-6">

                      <button
                        onClick={() => setTechOpen((v) => !v)}
                        className="flex items-center gap-2 text-[10px] font-mono tracking-widest text-gray-500 hover:text-gray-300 transition-colors group"
                      >
                        <span
                          className={`w-4 h-4 border border-white/[0.12] rounded flex items-center justify-center text-[8px] transition-transform duration-300 ${techOpen ? "rotate-90" : ""}`}
                        >
                          ▶
                        </span>
                        VIEW TECHNICAL DETAILS
                      </button>

                      {techOpen && (
                        <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/20 p-5 space-y-4 animate-[fadeIn_.2s_ease]">

                          {/* Raw engine explanation */}
                          <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
                            <p className="text-[9px] text-gray-600 font-mono tracking-wider mb-1.5">RAW ENGINE EXPLANATION</p>
                            <p className="text-xs text-gray-400 font-mono leading-relaxed">{result.explanation}</p>
                          </div>

                          {/* Grid of score metrics */}
                          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">

                            {/* Classifier score */}
                            <div className="rounded-lg border border-cyan-400/15 bg-cyan-400/[0.04] p-3">
                              <p className="text-[9px] text-gray-600 font-mono tracking-wider">CLASSIFIER SCORE</p>
                              <p className="text-lg font-black text-cyan-300 mt-1.5">
                                {(result.detectors.classifier * 100).toFixed(1)}<span className="text-xs text-gray-600">%</span>
                              </p>
                              <div className="h-1 bg-black/40 rounded-full mt-2 overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-cyan-400 to-blue-400 rounded-full transition-all duration-700"
                                  style={{ width: `${Math.min(result.detectors.classifier * 100, 100)}%` }}
                                />
                              </div>
                            </div>

                            {/* Semantic score */}
                            <div className="rounded-lg border border-violet-400/15 bg-violet-400/[0.04] p-3">
                              <p className="text-[9px] text-gray-600 font-mono tracking-wider">SEMANTIC SCORE</p>
                              <p className="text-lg font-black text-violet-300 mt-1.5">
                                {(result.detectors.semantic * 100).toFixed(1)}<span className="text-xs text-gray-600">%</span>
                              </p>
                              <div className="h-1 bg-black/40 rounded-full mt-2 overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-indigo-500 to-violet-400 rounded-full transition-all duration-700"
                                  style={{ width: `${Math.min(result.detectors.semantic * 100, 100)}%` }}
                                />
                              </div>
                            </div>

                            {/* Final fusion score */}
                            <div className="rounded-lg border border-indigo-400/15 bg-indigo-400/[0.04] p-3">
                              <p className="text-[9px] text-gray-600 font-mono tracking-wider">FINAL FUSION SCORE</p>
                              <p className="text-lg font-black text-indigo-300 mt-1.5">
                                {(result.combined_score * 100).toFixed(1)}<span className="text-xs text-gray-600">%</span>
                              </p>
                              <div className="h-1 bg-black/40 rounded-full mt-2 overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-indigo-500 via-violet-400 to-pink-400 rounded-full transition-all duration-700"
                                  style={{ width: `${Math.min(result.combined_score * 100, 100)}%` }}
                                />
                              </div>
                            </div>

                          </div>

                          {/* Rules + Fusion mode row */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

                            {/* Rules engine */}
                            <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
                              <p className="text-[9px] text-gray-600 font-mono tracking-wider mb-2">RULES ENGINE</p>
                              <div className="flex items-center gap-2">
                                <span
                                  className={`w-2 h-2 rounded-full ${result.detectors.rules.matched ? "bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,.6)]" : "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,.6)]"
                                    }`}
                                />
                                <span
                                  className={`text-xs font-mono font-semibold ${result.detectors.rules.matched ? "text-rose-300" : "text-emerald-300"
                                    }`}
                                >
                                  {result.detectors.rules.matched ? "MATCHED" : "CLEAR"}
                                </span>
                              </div>
                              {result.detectors.rules.categories.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-2">
                                  {result.detectors.rules.categories.map((cat) => (
                                    <span
                                      key={cat}
                                      className="px-2 py-0.5 rounded border border-rose-400/20 bg-rose-400/10 text-[9px] text-rose-300 font-mono"
                                    >
                                      {cat.toUpperCase()}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>

                            {/* Fusion mode */}
                            <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
                              <p className="text-[9px] text-gray-600 font-mono tracking-wider mb-2">FUSION MODE</p>
                              <span
                                className={`inline-block px-2.5 py-1 rounded-md border text-[10px] font-mono ${result.fusion_mode === "classifier_confident"
                                  ? "border-cyan-400/25 bg-cyan-400/[0.08] text-cyan-300"
                                  : "border-violet-400/25 bg-violet-400/[0.08] text-violet-300"
                                  }`}
                              >
                                {result.fusion_mode === "classifier_confident" ? "CLASSIFIER CONFIDENT" : "BLENDED UNCERTAIN"}
                              </span>
                              <p className="text-[9px] text-gray-600 font-mono mt-2">
                                {result.fusion_mode === "classifier_confident"
                                  ? `Classifier score (${(result.detectors.classifier * 100).toFixed(0)}%) fell outside the uncertainty zone (15–50%). The engine trusted it directly without blending the other detectors.`
                                  : `Classifier score (${(result.detectors.classifier * 100).toFixed(0)}%) fell inside the uncertainty zone (15–50%), so all three detectors were blended using weighted fusion to produce the final threat score.`}
                              </p>
                            </div>

                          </div>

                        </div>
                      )}

                    </div>

                  </div>
                </div>
              </div>
            )}

            {/* ==================================================
                FOOTER STATS
            ================================================== */}

            <div className="max-w-4xl mx-auto grid grid-cols-3 gap-5 mt-16">

              <div className="text-center">
                <p className="text-xl font-bold text-indigo-300">
                  03
                </p>

                <p className="text-[9px] text-gray-600 font-mono tracking-[0.2em] mt-1">
                  DETECTORS
                </p>
              </div>

              <div className="text-center">
                <p className="text-xl font-bold text-violet-300">
                  01
                </p>

                <p className="text-[9px] text-gray-600 font-mono tracking-[0.2em] mt-1">
                  FUSION ENGINE
                </p>
              </div>

              <div className="text-center">
                <p className="text-xl font-bold text-cyan-300">
                  AI
                </p>

                <p className="text-[9px] text-gray-600 font-mono tracking-[0.2em] mt-1">
                  EXPLAINABLE
                </p>
              </div>

            </div>

          </section>
        )}

      </main>

      {/* ======================================================
          ANIMATIONS
      ====================================================== */}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

    </div>
  )
}


// ============================================================
// DETECTOR BAR COMPONENT
// ============================================================

function DetectorBar({
  label,
  value,
  color,
  status,
}) {
  const gradients = {
    rose: "bg-gradient-to-r from-rose-500 to-pink-400",
    emerald: "bg-gradient-to-r from-emerald-400 to-cyan-400",
    violet: "bg-gradient-to-r from-indigo-500 to-violet-400",
    cyan: "bg-gradient-to-r from-cyan-400 to-blue-400",
    gradient: "bg-gradient-to-r from-indigo-500 via-violet-400 to-pink-400",
  }

  const textColors = {
    rose: "text-rose-400",
    emerald: "text-emerald-400",
    violet: "text-violet-400",
    cyan: "text-cyan-400",
    gradient: "text-indigo-300",
  }

  const dotColors = {
    rose: "bg-rose-400",
    emerald: "bg-emerald-400",
    violet: "bg-violet-400",
    cyan: "bg-cyan-400",
    gradient: "bg-indigo-400",
  }

  return (
    <div>

      <div className="flex justify-between items-center mb-2">

        <div className="flex items-center gap-2">

          <span
            className={`w-2 h-2 rounded-full ${dotColors[color]}`}
          />

          <span className="text-xs text-gray-300">
            {label}
          </span>

        </div>

        <span
          className={`text-[10px] font-mono ${textColors[color]}`}
        >
          {status || `${Math.round(value)}%`}
        </span>

      </div>

      <div className="h-1.5 bg-black/40 rounded-full overflow-hidden">

        <div
          className={`h-full ${gradients[color]} rounded-full transition-all duration-700`}
          style={{
            width: `${Math.min(value, 100)}%`,
          }}
        />

      </div>

    </div>
  )
}


// ============================================================
// DASHBOARD
// ============================================================

function Dashboard() {

  const [dashboardStats, setDashboardStats] = useState(null)
  const [dashboardLogs, setDashboardLogs] = useState([])

  useEffect(() => {
    const fetchDashboardData = () => {
      fetch("http://localhost:8000/stats")
        .then((res) => res.json())
        .then((data) => setDashboardStats(data))
        .catch((err) => console.error("STATS ERROR:", err))

      fetch("http://localhost:8000/logs?limit=10")
        .then((res) => res.json())
        .then((data) => setDashboardLogs(data))
        .catch((err) => console.error("LOGS ERROR:", err))
    }

    // Fetch immediately on mount, then every 3 seconds
    fetchDashboardData()
    const interval = setInterval(fetchDashboardData, 3000)

    // Clean up the interval when Dashboard unmounts
    return () => clearInterval(interval)
  }, [])

  const realAttacks = Object.entries(
    dashboardStats?.attack_categories ?? {}
  ).map(([name, count]) => ({
    name,
    count,
  }))


  const realThreats = (dashboardLogs ?? []).map((log) => ({
    prompt: log.prompt_text,
    type: log.categories || "Unknown",
    verdict: log.verdict.toUpperCase(),
  }))


  return (
    <section className="pt-16 pb-24">

      {/* ======================================================
          DASHBOARD HEADER
      ====================================================== */}

      <div className="mb-10">

        <p className="text-[10px] text-indigo-300 font-mono tracking-[0.25em]">
          SECURITY INTELLIGENCE
        </p>

        <h1 className="text-4xl md:text-5xl font-black mt-3">
          Threat Dashboard
        </h1>

        <p className="text-gray-500 mt-3 max-w-xl">
          Monitor prompt activity, threat classifications and detected
          attack patterns.
        </p>

      </div>

      {/* ======================================================
          STAT CARDS
      ====================================================== */}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">

        <StatCard
          label="TOTAL SCANS"
          value={(dashboardStats?.total_scans ?? 0).toLocaleString()}
          description="ALL ANALYZED PROMPTS"
          color="indigo"
        />

        <StatCard
          label="SAFE"
          value={(dashboardStats?.safe ?? 0).toLocaleString()}
          description="CLEARED PROMPTS"
          color="emerald"
        />

        <StatCard
          label="SUSPICIOUS"
          value={(dashboardStats?.suspicious ?? 0).toLocaleString()}
          description="REQUIRES REVIEW"
          color="amber"
        />

        <StatCard
          label="MALICIOUS"
          value={(dashboardStats?.malicious ?? 0).toLocaleString()}
          description="THREATS DETECTED"
          color="rose"
        />

      </div>

      {/* ======================================================
          CHARTS
      ====================================================== */}

      <div className="grid lg:grid-cols-2 gap-5 mt-6">

        {/* Verdict distribution */}

        <div className="rounded-2xl border border-white/[0.08] bg-[#0a1020]/80 p-7">

          <div className="mb-7">

            <p className="text-[10px] text-gray-500 font-mono tracking-widest">
              VERDICT DISTRIBUTION
            </p>

            <p className="text-sm text-gray-600 mt-1">
              Classification across analyzed prompts
            </p>

          </div>

          <div className="space-y-6">

            <DashboardBar
              label="Safe"
              value={dashboardStats?.safe ?? 0}
              total={dashboardStats?.total_scans || 1}
              color="emerald"
            />

            <DashboardBar
              label="Suspicious"
              value={dashboardStats?.suspicious ?? 0}
              total={dashboardStats?.total_scans || 1}
              color="amber"
            />

            <DashboardBar
              label="Malicious"
              value={dashboardStats?.malicious ?? 0}
              total={dashboardStats?.total_scans || 1}
              color="rose"
            />

          </div>
        </div>

        {/* Attack categories */}

        <div className="rounded-2xl border border-white/[0.08] bg-[#0a1020]/80 p-7">

          <div className="mb-7">

            <p className="text-[10px] text-gray-500 font-mono tracking-widest">
              ATTACK CATEGORIES
            </p>

            <p className="text-sm text-gray-600 mt-1">
              Most frequently detected attack patterns
            </p>

          </div>

          <div className="space-y-5">

            {realAttacks.length > 0 ? realAttacks.map((attack, index) => (

              <div key={attack.name}>

                <div className="flex justify-between items-center mb-2">

                  <div className="flex items-center gap-3">

                    <span className="text-[9px] text-gray-600 font-mono">
                      0{index + 1}
                    </span>

                    <span className="text-xs text-gray-300">
                      {attack.name}
                    </span>

                  </div>

                  <span className="text-[10px] text-violet-300 font-mono">
                    {attack.count}
                  </span>

                </div>

                <div className="h-1.5 bg-black/40 rounded-full overflow-hidden">

                  <div
                    className="h-full bg-gradient-to-r from-indigo-500 to-violet-400 rounded-full"
                    style={{
                      width: `${(attack.count / (realAttacks[0]?.count || 1)) * 100}%`,
                    }}
                  />

                </div>

              </div>

            )) : (
              <p className="text-xs text-gray-600 font-mono py-4 text-center">NO ATTACK DATA YET</p>
            )}

          </div>
        </div>

      </div>

      {/* ======================================================
          RECENT THREATS
      ====================================================== */}

      <div className="rounded-2xl border border-white/[0.08] bg-[#0a1020]/80 mt-6 overflow-hidden">

        <div className="p-7 border-b border-white/[0.06]">

          <p className="text-[10px] text-gray-500 font-mono tracking-widest">
            RECENT FLAGGED PROMPTS
          </p>

          <p className="text-sm text-gray-600 mt-1">
            Latest prompts requiring security attention
          </p>

        </div>

        <div className="divide-y divide-white/[0.05]">

          {realThreats.length > 0 ? realThreats.map((item, index) => (

            <div
              key={index}
              className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-white/[0.02] transition"
            >

              <div className="flex items-start gap-4">

                <span className="text-[9px] text-gray-600 font-mono mt-1">
                  0{index + 1}
                </span>

                <div>

                  <p className="text-sm text-gray-300">
                    {item.prompt}
                  </p>

                  <p className="text-[9px] text-gray-600 font-mono mt-2">
                    {item.type.toUpperCase()}
                  </p>

                </div>
              </div>

              <span
                className={`w-fit px-3 py-1.5 rounded-lg border text-[9px] font-mono ${item.verdict === "MALICIOUS"
                  ? "border-rose-400/20 bg-rose-400/10 text-rose-400"
                  : item.verdict === "SUSPICIOUS"
                    ? "border-amber-400/20 bg-amber-400/10 text-amber-400"
                    : "border-emerald-400/20 bg-emerald-400/10 text-emerald-400"
                  }`}
              >
                {item.verdict}
              </span>

            </div>

          )) : (
            <p className="text-xs text-gray-600 font-mono py-6 text-center">NO PROMPTS LOGGED YET</p>
          )}

        </div>
      </div>

      {/* ======================================================
          DASHBOARD FOOTER
      ====================================================== */}

      <div className="grid grid-cols-3 gap-5 mt-12 text-center">

        <div>
          <p className="text-xl font-bold text-indigo-300">
            03
          </p>

          <p className="text-[9px] text-gray-600 font-mono tracking-widest mt-1">
            DETECTORS
          </p>
        </div>

        <div>
          <p className="text-xl font-bold text-violet-300">
            01
          </p>

          <p className="text-[9px] text-gray-600 font-mono tracking-widest mt-1">
            FUSION ENGINE
          </p>
        </div>

        <div>
          <p className="text-xl font-bold text-cyan-300">
            LIVE
          </p>

          <p className="text-[9px] text-gray-600 font-mono tracking-widest mt-1">
            MONITORING
          </p>
        </div>

      </div>

    </section>
  )
}


// ============================================================
// STAT CARD
// ============================================================

function StatCard({
  label,
  value,
  description,
  color,
}) {

  const styles = {
    indigo:
      "border-white/[0.08] bg-[#0a1020]/80 text-indigo-300",
    emerald:
      "border-emerald-400/15 bg-emerald-400/[0.03] text-emerald-300",
    amber:
      "border-amber-400/15 bg-amber-400/[0.03] text-amber-300",
    rose:
      "border-rose-400/15 bg-rose-400/[0.03] text-rose-300",
  }

  return (
    <div
      className={`rounded-2xl border p-6 ${styles[color]} transition-all duration-300 hover:-translate-y-1`}
    >

      <p className="text-[10px] opacity-70 font-mono tracking-widest">
        {label}
      </p>

      <p className="text-3xl font-black mt-3">
        {value}
      </p>

      <p className="text-[10px] text-gray-600 font-mono mt-3">
        {description}
      </p>

    </div>
  )
}


// ============================================================
// DASHBOARD BAR
// ============================================================

function DashboardBar({
  label,
  value,
  total,
  color,
}) {

  const colors = {
    emerald: "bg-emerald-400",
    amber: "bg-amber-400",
    rose: "bg-gradient-to-r from-rose-500 to-pink-400",
  }

  const textColors = {
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    rose: "text-rose-400",
  }

  return (
    <div>

      <div className="flex justify-between text-xs mb-2">

        <span className="text-gray-300">
          {label}
        </span>

        <span className={`${textColors[color]} font-mono`}>
          {value.toLocaleString()}
        </span>

      </div>

      <div className="h-2 bg-black/40 rounded-full overflow-hidden">

        <div
          className={`h-full ${colors[color]} rounded-full transition-all duration-700`}
          style={{
            width: `${(value / total) * 100}%`,
          }}
        />

      </div>

    </div>
  )
}


export default App