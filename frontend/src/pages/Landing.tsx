import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#F7F4EF] flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 flex items-center justify-between">
        <span className="font-display text-xl font-semibold text-[#0B1F33] tracking-tight">SmartReco</span>
        <nav className="flex items-center gap-1">
          <Link
            to="/login"
            className="px-4 py-2 text-sm text-[#6B7280] hover:text-[#0B1F33] transition-colors"
          >
            Log in
          </Link>
          <Link
            to="/signup"
            className="px-4 py-2 text-sm font-medium bg-[#0B1F33] text-white rounded-lg hover:bg-[#163550] transition-colors"
          >
            Get started
          </Link>
        </nav>
      </header>

      {/* Hero — editorial split */}
      <main className="flex-1 px-8 pt-12 pb-20 max-w-6xl mx-auto w-full">
        {/* Eyebrow */}
        <p className="text-xs font-medium text-[#0F8B8D] uppercase tracking-[0.15em] mb-8">
          Free-alternative recommender
        </p>

        {/* Headline */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-end mb-20">
          <h1 className="font-display text-[clamp(2.8rem,6vw,5rem)] font-semibold text-[#0B1F33] leading-[1.05]">
            Find the free<br />
            version of what<br />
            <span className="italic text-[#0F8B8D]">you're learning.</span>
          </h1>

          <div>
            <p className="text-[#6B7280] text-lg leading-relaxed mb-8 max-w-sm">
              SmartReco watches how you browse paid courses and quietly surfaces free YouTube resources and docs that match exactly what you're after.
            </p>
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 bg-[#0F8B8D] text-white px-6 py-3 rounded-lg font-medium hover:bg-[#0a6e70] transition-colors group"
            >
              Start exploring
              <ArrowUpRight className="h-4 w-4 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </Link>
          </div>
        </div>

        {/* Three-column feature strip */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-[#D1CAB8] border border-[#D1CAB8] rounded-xl overflow-hidden">
          {[
            {
              label: "01",
              title: "You browse",
              body: "Explore a marketplace of paid courses. Your clicks and time-on-page are the signal.",
            },
            {
              label: "02",
              title: "We watch",
              body: "SmartReco reads your behavioral patterns — topics, categories, time spent — without storing anything personal.",
            },
            {
              label: "03",
              title: "You get free",
              body: "Curated YouTube videos and docs appear on your dashboard, matched to what you were actually looking for.",
            },
          ].map((item) => (
            <div key={item.label} className="bg-[#F7F4EF] px-6 py-7">
              <span className="text-xs font-mono text-[#0F8B8D] mb-4 block">{item.label}</span>
              <h3 className="font-display text-lg font-semibold text-[#0B1F33] mb-2">{item.title}</h3>
              <p className="text-sm text-[#6B7280] leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>

        {/* Demo hint */}
        <p className="mt-10 text-center text-xs text-[#9CA3AF]">
          Admin demo:{" "}
          <span className="font-mono text-[#6B7280]">admin@smartreco.dev</span>
          {" "}·{" "}
          <span className="font-mono text-[#6B7280]">admin123</span>
        </p>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#D1CAB8] px-8 py-5 flex items-center justify-between text-xs text-[#9CA3AF]">
        <span>SmartReco</span>
        <span>Hackathon demo · No paid upsells, ever</span>
      </footer>
    </div>
  );
}
