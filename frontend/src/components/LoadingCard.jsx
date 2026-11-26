import { useEffect, useState } from "react";

const STEPS = ["Preparing analysis", "Crawling website", "Processing data", "Analyzing content", "Finalizing report"];
const STEP_PROGRESS = [10, 35, 60, 90];
const HOLD_STEP = STEPS.indexOf("Analyzing content");
const STEP_INTERVAL_MS = 1200;
const FINISH_DELAY_MS = 400;

function stepState(index, current, done) {
  if (done || index < current) return "done";
  return index === current ? "active" : "pending";
}

export default function LoadingCard({ url, done, onFinished }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (done || step >= HOLD_STEP) return undefined;
    const timer = setTimeout(() => setStep((current) => current + 1), STEP_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [step, done]);

  useEffect(() => {
    if (!done) return undefined;
    const timer = setTimeout(onFinished, FINISH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [done, onFinished]);

  const percent = done ? 100 : STEP_PROGRESS[step];

  return (
    <section className="card loading-card" aria-live="polite">
      <div className="loading-head">
        <div>
          <p className="eyebrow">Analyzing</p>
          <p className="loading-url">{url}</p>
        </div>
        <span className="loading-percent">{percent}%</span>
      </div>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <ol className="steps">
        {STEPS.map((label, index) => (
          <li key={label} className={`step step-${stepState(index, step, done)}`}>
            <span className="step-marker" aria-hidden="true" />
            {label}
          </li>
        ))}
      </ol>
    </section>
  );
}
