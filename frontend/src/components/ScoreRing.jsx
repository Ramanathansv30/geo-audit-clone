import { labelTone } from "../labels.js";

/** Circular 0-100 score gauge, coloured by its label. */
export default function ScoreRing({ score, label, size = 140 }) {
  const stroke = size / 12;
  const radius = (size - stroke) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className={`score-ring ${labelTone(label)}`} style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Score ${score} out of 100, ${label}`}>
        <circle className="score-ring-track" cx={center} cy={center} r={radius} strokeWidth={stroke} />
        <circle
          className="score-ring-value"
          cx={center}
          cy={center}
          r={radius}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
          transform={`rotate(-90 ${center} ${center})`}
        />
      </svg>
      <span className="score-ring-number" style={{ fontSize: size * 0.3 }}>
        {score}
      </span>
    </div>
  );
}
