import { useEffect, useRef, useMemo } from "react";
import { useParams, Link, useNavigate, useLocation } from "react-router-dom";
import { ArrowLeft, Star, Users, Tag, ExternalLink } from "lucide-react";
import { mockCourses } from "@/data/mockCourses";
import { eventTracker } from "@/lib/eventTracker";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BrowseRecommendationPanel } from "@/components/BrowseRecommendationPanel";


interface BrowseNavState {
  query?: string;
  activeCategory?: string | null;
  scrollY?: number;
}

export default function CourseDetail() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const course = mockCourses.find((c) => c.id === courseId);
  const mountedAt = useRef(Date.now());
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const navState = (location.state as BrowseNavState) || {};

  // Build the "Back to Browse" destination carrying forward the exact
  // category/query the user came from, plus this course id so Browse can
  // scroll the same card back into view.
  const backHref = useMemo(() => {
    const params = new URLSearchParams();
    if (navState.activeCategory) params.set("category", navState.activeCategory);
    if (navState.query) params.set("query", navState.query);
    const qs = params.toString();
    return qs ? `/browse?${qs}` : "/browse";
  }, [navState.activeCategory, navState.query]);

  useEffect(() => {
    if (!course) return;
    eventTracker.trackOnce("view", {
      courseId: course.id,
      title: course.title,
      category: course.category,
      level: course.level,
    });
    mountedAt.current = Date.now();

    intervalRef.current = setInterval(() => {
      const seconds = Math.floor((Date.now() - mountedAt.current) / 1000);
      eventTracker.track("time_spent", { courseId: course.id, title: course.title, seconds });
    }, 30_000);

    return () => {
      clearInterval(intervalRef.current);
      const seconds = Math.floor((Date.now() - mountedAt.current) / 1000);
      if (seconds >= 10) {
        eventTracker.trackOnce(
          "time_spent",
          { courseId: course.id, title: course.title, seconds },
          5000,
        );
      }
    };
  }, [course]);

  if (!course) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <p className="text-lg text-[#6B7280] mb-4">Course not found.</p>
        <Button onClick={() => navigate("/browse")} variant="outline">Back to Browse</Button>
      </div>
    );
  }

  const handleCTA = () => {
    eventTracker.track("click", { courseId: course.id, title: course.title });
  };

  useEffect(() => {
  window.scrollTo(0, 0);
}, [courseId]);

  const backLinkState = { restoreCourseId: course.id };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      <Link
        to={backHref}
        state={backLinkState}
        className="inline-flex items-center gap-1.5 text-sm text-[#6B7280] hover:text-[#0B1F33] mb-6 transition-colors"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Browse
      </Link>

      <div className="grid  md:mb-9 grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <Badge className="text-xs">{course.category}</Badge>
            <Badge variant="outline" className="text-xs">{course.level}</Badge>
          </div>

          <h1 className="font-display text-3xl font-semibold text-[#0B1F33] leading-tight mb-2">{course.title}</h1>
          <p className="text-[#6B7280] mb-4">{course.shortDescription}</p>

          <div className="flex items-center gap-4 text-sm text-[#6B7280] mb-6">
            <span className="flex items-center gap-1.5">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" /> {course.rating}
            </span>
            <span className="flex items-center gap-1.5">
              <Users className="h-4 w-4" /> {course.students.toLocaleString()} students
            </span>
            <span>by <span className="text-[#0B1F33] font-medium">{course.instructor}</span></span>
          </div>

          <div className="bg-[#F7F4EF] rounded-lg p-5 border border-[#D1CAB8]">
            <h2 className="font-display text-base font-semibold text-[#0B1F33] mb-3 flex items-center gap-2">
              <Tag className="h-4 w-4 text-[#0F8B8D]" /> Topics covered
            </h2>
            <div className="flex flex-wrap gap-2">
              {course.topics.map((t) => (
                <span key={t} className="px-2.5 py-1 rounded bg-white border border-[#D1CAB8] text-xs text-[#1A1A1A]">{t}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-1">
          <div className="bg-white border border-[#D1CAB8] rounded-xl p-6 sticky top-20">
            <div className="text-3xl font-bold text-[#0B1F33] mb-1 font-display">
              {course.price === 0 ? "Free" : `$${course.price}`}
            </div>
            <p className="text-xs text-[#6B7280] mb-5">One-time purchase</p>

            <Button className="w-full mb-3" onClick={handleCTA}>
              <ExternalLink className="h-4 w-4" /> View syllabus
            </Button>
            <Button variant="outline" className="w-full mb-3" onClick={handleCTA}>
              I&apos;m interested
            </Button>

            <div className="mt-4 rounded-lg border border-[#0F8B8D]/30 bg-[#e6f4f4] px-4 py-3 text-sm text-[#0a6e70]">
              <p className="font-medium mb-0.5">Want free alternatives?</p>
              <Link
                to={backHref}
                state={backLinkState}
                className="text-xs underline underline-offset-2 hover:text-[#0F8B8D]"
              >
                Back to Browse — your free path panel lives there →
              </Link>
            </div>
          </div>
        </div>
        
      </div>
              <BrowseRecommendationPanel />
      
    </div>
  );
}