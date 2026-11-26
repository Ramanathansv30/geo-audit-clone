/** Small rounded label. tone selects a colour variant defined in styles.css. */
export default function Pill({ children, tone = "neutral" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}
