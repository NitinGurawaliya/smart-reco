import { useState, useRef, useCallback, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Search, Star, Users } from "lucide-react";
import { mockCourses, courseCategories } from "@/data/mockCourses";
import { eventTracker } from "@/lib/eventTracker";
import { BrowseRecommendationPanel } from "@/components/BrowseRecommendationPanel";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { MockCourse } from "@/types/api";

function CourseCard({
  course,
  query,
  activeCategory,
}: {
  course: MockCourse;
  query: string;
  activeCategory: string | null;
}) {
  return (
    <Link
      id={`course-card-${course.id}`}
      to={`/browse/${course.id}`}
      state={{ query, activeCategory }}
      className="group block bg-white border border-[#D1CAB8] rounded-lg p-5 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-[#0B1F33] text-base leading-snug line-clamp-2 group-hover:text-[#0F8B8D] transition-colors">
            {course.title}
          </h3>
          <p className="text-xs text-[#6B7280] mt-0.5">{course.instructor}</p>
        </div>
        <span className="shrink-0 font-semibold text-[#0B1F33] text-sm">
          {course.price === 0 ? "Free" : `$${course.price}`}
        </span>
      </div>

      <p className="text-sm text-[#6B7280] line-clamp-2 mb-4">{course.shortDescription}</p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-[#6B7280]">
          <span className="flex items-center gap-1">
            <Star className="h-3 w-3 fill-amber-400 text-amber-400" /> {course.rating}
          </span>
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" /> {(course.students / 1000).toFixed(0)}k
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className="text-[10px] px-2 py-0">{course.level}</Badge>
          <Badge className="text-[10px] px-2 py-0 bg-[#e6f4f4] text-[#0a6e70]">{course.category}</Badge>
        </div>
      </div>
    </Link>
  );
}

export default function Browse() {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const location = useLocation();

  // Restore category/query from URL (carried forward by CourseDetail's back link)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    setQuery(params.get("query") || "");
    setActiveCategory(params.get("category") || null);
  }, [location.search]);

  // Restore scroll to the exact card the user came from
  useEffect(() => {
    const restoreCourseId = (location.state as { restoreCourseId?: string } | null)?.restoreCourseId;
    if (!restoreCourseId) return;

    // Wait a tick for the filtered list to render before scrolling
    const raf = requestAnimationFrame(() => {
      const el = document.getElementById(`course-card-${restoreCourseId}`);
      el?.scrollIntoView({ block: "center" });
    });
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state, query, activeCategory]);

  const handleSearch = useCallback((val: string) => {
    setQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (val.trim()) eventTracker.track("search", { query: val.trim() });
    }, 400);
  }, []);

  const filtered = mockCourses.filter((c) => {
    const matchQ =
      query === "" ||
      c.title.toLowerCase().includes(query.toLowerCase()) ||
      c.shortDescription.toLowerCase().includes(query.toLowerCase());
    const matchCat = activeCategory === null || c.category === activeCategory;
    return matchQ && matchCat;
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-semibold text-[#0B1F33] mb-1">Explore courses</h1>
        <p className="text-sm text-[#6B7280] max-w-xl">
          Browse freely — your free learning path stays visible above as SmartReco learns from what
          you open (not these paid listings).
        </p>
      </div>



      <div className="relative mb-5 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#9CA3AF]" />
        <Input
          type="search"
          placeholder="Search courses…"
          className="pl-9"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setActiveCategory(null)}
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
            activeCategory === null
              ? "bg-[#0B1F33] text-white border-[#0B1F33]"
              : "border-[#D1CAB8] text-[#6B7280] hover:border-[#0B1F33] hover:text-[#0B1F33] bg-white"
          }`}
        >
          All
        </button>
        {courseCategories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              activeCategory === cat
                ? "bg-[#0B1F33] text-white border-[#0B1F33]"
                : "border-[#D1CAB8] text-[#6B7280] hover:border-[#0B1F33] hover:text-[#0B1F33] bg-white"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-[#6B7280]">
          <p className="text-lg font-medium mb-1">No courses found</p>
          <p className="text-sm">Try a different search or category.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((course) => (
            <CourseCard
              key={course.id}
              course={course}
              query={query}
              activeCategory={activeCategory}
            />
          ))}
        </div>
      )}


            <div className="m-8">
        <BrowseRecommendationPanel />
      </div>
    </div>
  );
} 