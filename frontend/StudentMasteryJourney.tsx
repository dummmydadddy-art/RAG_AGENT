import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Award, 
  CheckCircle2, 
  AlertTriangle, 
  TrendingUp, 
  BookOpen, 
  RefreshCw, 
  Zap, 
  ShieldCheck, 
  Flame, 
  ChevronRight,
  Clock,
  Check,
  Brain,
  Layers,
  ArrowUpRight,
  Stethoscope
} from 'lucide-react';
import api from '../services/api';
import ConceptDoctorModal from './ConceptDoctorModal';

interface MasterySummary {
  total_quizzes_taken: number;
  overall_mastery_pct: number;
  mastered_quizzes: number;
  mastered_topics_count: number;
  in_progress_topics_count: number;
  needs_practice_topics_count: number;
  refuted_misconceptions_count: number;
}

interface TopicMasteryItem {
  topic: string;
  attempts_count: number;
  avg_score_pct: number;
  best_score_pct: number;
  last_tested_at: string | null;
  status: 'CONCEPT_MASTERED' | 'IN_PROGRESS' | 'NEEDS_PRACTICE' | 'NOT_STARTED';
  badge_label: string;
}

interface RemedialActivity {
  id: number;
  exam_id: string;
  exam_title: string;
  topic: string;
  score: number;
  max_score: number;
  percentage: number;
  passed: boolean;
  evaluated_at: string;
}

interface StudentMasteryJourneyProps {
  studentId: string;
  courseId?: string | null;
  batchId?: string | null;
  onLaunchQuiz?: (examId: string) => void;
}

export const StudentMasteryJourney: React.FC<StudentMasteryJourneyProps> = ({
  studentId,
  courseId,
  batchId,
  onLaunchQuiz
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [summary, setSummary] = useState<MasterySummary | null>(null);
  const [topics, setTopics] = useState<TopicMasteryItem[]>([]);
  const [recentActivities, setRecentActivities] = useState<RemedialActivity[]>([]);
  const [activeFilter, setActiveFilter] = useState<'all' | 'mastered' | 'practice'>('all');
  const [doctorModalTarget, setDoctorModalTarget] = useState<any | null>(null);

  const fetchMasteryData = async () => {
    if (!studentId) return;
    setLoading(true);
    try {
      const params: any = { student_id: studentId };
      if (courseId) params.course_id = courseId;
      if (batchId) params.batch_id = batchId;

      const res = await api.get('/api/rag/student/mastery', { params });
      if (res.data?.success) {
        setSummary(res.data.summary);
        setTopics(res.data.topic_mastery || []);
        setRecentActivities(res.data.recent_activities || []);
      }
    } catch (err) {
      console.error('Failed to load student mastery journey:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMasteryData();
  }, [studentId, courseId, batchId]);

  const filteredTopics = topics.filter(t => {
    if (activeFilter === 'mastered') return t.status === 'CONCEPT_MASTERED';
    if (activeFilter === 'practice') return t.status === 'NEEDS_PRACTICE' || t.status === 'IN_PROGRESS';
    return true;
  });

  const getStatusBadge = (status: TopicMasteryItem['status']) => {
    switch (status) {
      case 'CONCEPT_MASTERED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="h-3.5 w-3.5" /> Concept Mastered
          </span>
        );
      case 'IN_PROGRESS':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <TrendingUp className="h-3.5 w-3.5" /> In Progress
          </span>
        );
      case 'NEEDS_PRACTICE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <AlertTriangle className="h-3.5 w-3.5" /> Needs Reinforcement
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            <BookOpen className="h-3.5 w-3.5" /> Ready to Learn
          </span>
        );
    }
  };

  const getDifficultyTierBadge = (avgScore: number, attempts: number) => {
    if (attempts === 0 || avgScore < 50) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
          <Layers className="h-3 w-3" /> Foundation Tier
        </span>
      );
    }
    if (avgScore < 75) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <Zap className="h-3 w-3" /> Application Tier
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
        <Sparkles className="h-3 w-3" /> Architectural Tier
      </span>
    );
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl p-5 md:p-6 shadow-xl relative overflow-hidden">
      {/* Decorative ambient glow */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
      <div className="absolute bottom-0 left-0 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl pointer-events-none -ml-20 -mb-20" />

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-800/80 relative z-10">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary-500/20 to-purple-500/20 border border-primary-500/30 text-primary-400">
            <Brain className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-slate-100">My AI Learning Journey & Concept Mastery</h3>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary-500/15 text-primary-300 border border-primary-500/30 flex items-center gap-1">
                <Sparkles className="h-2.5 w-2.5" /> Adaptive RAG
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Personalized concept tracking, diagnostic quiz milestones, and validated syllabus comprehension.
            </p>
          </div>
        </div>

        <button
          onClick={fetchMasteryData}
          disabled={loading}
          className="self-start md:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold border border-slate-700 transition"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-primary-400' : ''}`} />
          Refresh Journey
        </button>
      </div>

      {/* Summary KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 my-5 relative z-10">
          <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800/80">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Remedial Mastery</span>
              <Award className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 mt-1">
              {summary.overall_mastery_pct}%
            </div>
            <div className="text-[11px] text-emerald-400 mt-0.5">
              {summary.overall_mastery_pct >= 75 ? '🌟 Proficient grasp' : summary.overall_mastery_pct >= 50 ? '📈 Steady progress' : '🎯 Building foundation'}
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800/80">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Mastered Concepts</span>
              <CheckCircle2 className="h-4 w-4 text-primary-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 mt-1">
              {summary.mastered_topics_count}
              <span className="text-xs font-normal text-slate-400 ml-1">topics</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Across curriculum modules
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800/80">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Quizzes Completed</span>
              <Zap className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 mt-1">
              {summary.total_quizzes_taken}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              {summary.mastered_quizzes} passed (≥70%)
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800/80">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Gaps Resolved</span>
              <ShieldCheck className="h-4 w-4 text-purple-400" />
            </div>
            <div className="text-2xl font-black text-slate-100 mt-1">
              {summary.refuted_misconceptions_count}
            </div>
            <div className="text-[11px] text-purple-400 mt-0.5">
              AI-diagnosed misconceptions
            </div>
          </div>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex items-center justify-between gap-2 mb-4 relative z-10 flex-wrap">
        <div className="flex items-center gap-1.5 p-1 bg-slate-950/60 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveFilter('all')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
              activeFilter === 'all'
                ? 'bg-primary-500/20 text-primary-300 border border-primary-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Concepts ({topics.length})
          </button>
          <button
            onClick={() => setActiveFilter('mastered')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
              activeFilter === 'mastered'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Mastered ({summary?.mastered_topics_count || 0})
          </button>
          <button
            onClick={() => setActiveFilter('practice')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
              activeFilter === 'practice'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Needs Practice ({(summary?.in_progress_topics_count || 0) + (summary?.needs_practice_topics_count || 0)})
          </button>
        </div>

        <span className="text-xs text-slate-400 hidden sm:inline">
          Target: ≥75% average score for full mastery
        </span>
      </div>

      {/* Concept Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 relative z-10">
        {filteredTopics.map((topic, idx) => (
          <div
            key={idx}
            className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/80 hover:border-slate-700/80 transition flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <h4 className="font-bold text-sm text-slate-200 leading-snug">{topic.topic}</h4>
                {getStatusBadge(topic.status)}
              </div>
              <div className="mb-2">
                {getDifficultyTierBadge(topic.avg_score_pct, topic.attempts_count)}
              </div>

              {/* Progress bar */}
              <div className="space-y-1 my-3">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>Concept Mastery</span>
                  <span className="font-semibold text-slate-200">{topic.avg_score_pct}%</span>
                </div>
                <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      topic.avg_score_pct >= 75
                        ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                        : topic.avg_score_pct >= 50
                        ? 'bg-gradient-to-r from-amber-500 to-yellow-400'
                        : topic.attempts_count > 0
                        ? 'bg-gradient-to-r from-rose-500 to-red-400'
                        : 'bg-slate-700'
                    }`}
                    style={{ width: `${Math.max(4, topic.avg_score_pct)}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs text-slate-400 gap-2">
              <span>
                {topic.attempts_count > 0 ? (
                  <>
                    <span className="text-slate-300 font-medium">{topic.attempts_count}</span> {topic.attempts_count === 1 ? 'quiz' : 'quizzes'} (Best: {topic.best_score_pct}%)
                  </>
                ) : (
                  'No quizzes attempted'
                )}
              </span>

              <button
                onClick={() => setDoctorModalTarget({
                  topic: topic.topic,
                  question: `Key conceptual mechanisms, common runtime bugs, and best practices in ${topic.topic}`,
                  studentChoice: 'Common conceptual confusion or anti-pattern',
                  correctChoice: 'Curriculum-grounded technical rule'
                })}
                className="py-1 px-2.5 rounded-lg bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 text-[11px] font-semibold flex items-center gap-1 transition shrink-0"
                title="Consult AI Concept Doctor on this topic"
              >
                <Stethoscope className="h-3 w-3 text-teal-400" />
                Concept Doctor
              </button>
            </div>
          </div>
        ))}

        {filteredTopics.length === 0 && (
          <div className="col-span-full py-8 text-center text-slate-400 text-xs border border-dashed border-slate-800 rounded-xl">
            No topics matching this filter.
          </div>
        )}
      </div>

      {/* Recent Activity Timeline */}
      {recentActivities.length > 0 && (
        <div className="mt-6 pt-5 border-t border-slate-800/80 relative z-10">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" /> Recent Diagnostic & Remedial Activity
            </h4>
            <span className="text-[11px] text-slate-400">Last 10 attempts</span>
          </div>

          <div className="space-y-2">
            {recentActivities.slice(0, 4).map((activity, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/30 border border-slate-850 hover:bg-slate-950/60 transition text-xs"
              >
                <div className="flex items-center gap-2.5">
                  <div className={`p-1.5 rounded-md ${activity.passed ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'}`}>
                    {activity.passed ? <Check className="h-3.5 w-3.5" /> : <Flame className="h-3.5 w-3.5" />}
                  </div>
                  <div>
                    <div className="font-semibold text-slate-200">{activity.exam_title}</div>
                    <div className="text-[11px] text-slate-400 flex items-center gap-2">
                      <span>{activity.topic}</span>
                      <span>•</span>
                      <span>{new Date(activity.evaluated_at).toLocaleDateString()} {new Date(activity.evaluated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-right">
                    <span className={`font-bold ${activity.passed ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {activity.percentage}%
                    </span>
                    <span className="text-[10px] text-slate-400 block">
                      {activity.score}/{activity.max_score} pts
                    </span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                    activity.passed 
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' 
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                  }`}>
                    {activity.passed ? 'Mastered' : 'Review'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Concept Doctor Diagnostic Modal */}
      {doctorModalTarget && (
        <ConceptDoctorModal
          isOpen={!!doctorModalTarget}
          onClose={() => setDoctorModalTarget(null)}
          topic={doctorModalTarget.topic}
          question={doctorModalTarget.question}
          studentChoice={doctorModalTarget.studentChoice}
          correctChoice={doctorModalTarget.correctChoice}
          courseId={courseId}
          batchId={batchId}
          studentId={studentId}
          onBreakthroughResolved={() => {
            fetchMasteryData();
          }}
        />
      )}
    </div>
  );
};

export default StudentMasteryJourney;
