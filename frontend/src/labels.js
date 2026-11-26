/** CSS class that sets the --tone colour for a score label, e.g. "Needs work" -> "tone-needs-work". */
export function labelTone(label) {
  return `tone-${label.toLowerCase().replace(/\s+/g, "-")}`;
}
