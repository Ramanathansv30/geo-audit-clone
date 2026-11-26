import { useCallback, useEffect, useState } from "react";
import { auditUrl, getBenchmarks } from "./api.js";
import BotAccess from "./components/BotAccess.jsx";
import ComparisonStrip from "./components/ComparisonStrip.jsx";
import DimensionCard from "./components/DimensionCard.jsx";
import Faq from "./components/Faq.jsx";
import Footer from "./components/Footer.jsx";
import Header from "./components/Header.jsx";
import Hero from "./components/Hero.jsx";
import HowItWorks from "./components/HowItWorks.jsx";
import LoadingCard from "./components/LoadingCard.jsx";
import PlatformStrip from "./components/PlatformStrip.jsx";
import ResultHeader from "./components/ResultHeader.jsx";
import TopFixes from "./components/TopFixes.jsx";

export default function App() {
  const [view, setView] = useState("landing");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);
  const [benchmarks, setBenchmarks] = useState({ status: "loading", data: null });

  // Fetched once on page load; the server may need a few seconds to compute them the first time.
  useEffect(() => {
    getBenchmarks()
      .then((data) => setBenchmarks({ status: "ready", data }))
      .catch(() => setBenchmarks({ status: "error", data: null }));
  }, []);

  async function analyze() {
    if (view === "loading") return;
    setError("");
    setReport(null);
    setView("loading");
    try {
      setReport(await auditUrl(url.trim()));
    } catch (err) {
      setError(err.message);
      setView("landing");
    }
  }

  function reset() {
    setView("landing");
    setReport(null);
    setUrl("");
  }

  const showResults = useCallback(() => setView("results"), []);

  return (
    <>
      <Header />
      <main className="container">
        {view === "results" ? (
          <div className="results">
            <ResultHeader report={report} onReset={reset} />
            <ComparisonStrip score={report.overall_score} benchmarks={benchmarks} />
            <TopFixes issues={report.top_fixes} />
            <BotAccess bots={report.bot_access} />
            <div className="dimension-grid">
              {report.dimensions.map((dimension) => (
                <DimensionCard key={dimension.key} dimension={dimension} />
              ))}
            </div>
          </div>
        ) : (
          <>
            <Hero url={url} onUrlChange={setUrl} onSubmit={analyze} loading={view === "loading"} error={error} />
            <PlatformStrip />
            {view === "loading" ? (
              <LoadingCard url={url} done={report !== null} onFinished={showResults} />
            ) : (
              <>
                <HowItWorks />
                <Faq />
              </>
            )}
          </>
        )}
      </main>
      <Footer />
    </>
  );
}
