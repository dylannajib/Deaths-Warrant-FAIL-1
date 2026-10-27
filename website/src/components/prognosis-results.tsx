import type { PrognosisReport } from "@/lib/prognosis-client";

// Present the fitted mean, its uncertainty and the model's stated limitations together.
export function PrognosisResults({ report }: { report: PrognosisReport }) {
  const interval = report.meanUncertainty;
  return <section aria-labelledby="prognosis-heading">
    <h2 id="prognosis-heading">Research estimate</h2>
    <p>Assessment date: {report.asOf}</p>
    <p>Estimated mean remaining years: <strong>{report.remainingYears.toFixed(1)}</strong></p>
    <p>95% interval for the fitted mean: {interval.lower.toFixed(1)}–{interval.upper.toFixed(1)} years.</p>
    <p>{interval.meaning}</p>
    <ul>{(["1", "3", "5"] as const).map(year =>
      <li key={year}>Survival at {year} {year === "1" ? "year" : "years"}: {(report.survivalByYear[year] * 100).toFixed(1)}%</li>
    )}</ul>
    <ul>{report.warnings.map(message => <li key={message}>{message}</li>)}</ul>
    <small>Model: {report.modelVersion}</small>
  </section>;
}
