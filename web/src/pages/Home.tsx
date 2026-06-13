import { Link } from "react-router";

export function Home() {
  return (
    <section className="mx-auto flex max-w-3xl flex-1 flex-col items-start justify-center gap-6 px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight text-balance">
        Your next role, one proven skill at a time.
      </h1>
      <p className="max-w-xl text-lg text-ink-muted">
        PathForward helps workers step into adjacent technical roles — and only
        certifies a skill when it can prove it. No guesswork, no inflated
        claims: if the evidence isn&apos;t there, it says &ldquo;not yet.&rdquo;
      </p>
      <Link
        to="/tour"
        className="rounded-full bg-brand-500 px-5 py-2.5 font-medium text-white transition-colors hover:bg-brand-600"
      >
        Watch how it thinks →
      </Link>
    </section>
  );
}
