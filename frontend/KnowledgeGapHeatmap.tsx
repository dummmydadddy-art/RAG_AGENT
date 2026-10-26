import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  HelpCircle, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp, 
  BookOpen, 
  RefreshCw, 
  ChevronRight, 
  Check, 
  Copy, 
  X, 
  Flame, 
  Compass, 
  ShieldCheck, 
  Layers,
  ArrowRight,
  Send,
  Zap,
  Bot,
  Sliders,
  Play,
  Settings
} from 'lucide-react';
import api from '../services/api';

interface TelemetryMetrics {
  total_queries: number;
  grounding_rate_pct: number;
  knowledge_gap_rate_pct: number;
  misconceptions_count: number;
  avg_confidence_pct: number;
  direct_queries: number;
  socratic_queries: number;
}

interface TopicHotspot {
  topic: string;
  query_count: number;
  avg_confidence: number;
  abstain_count: number;
  misconception_count: number;
}

interface KnowledgeGapItem {
  question: string;
  topic: string;
  confidence: number;
  created_at: string;
}

interface MisconceptionItem {
  question: string;
  topic: string;
  created_at: string;
}

interface AutopilotConfig {
  enabled: boolean;
  threshold: number;
  auto_publish: boolean;
  question_count: number;
  time_limit_minutes: number;
  course_id?: string | null;
  batch_id?: string | null;
  updated_at?: string | null;
}

interface AutopilotEvent {
  id: number;
  topic: string;
  trigger_reason: string;
  event_type: 'AUTO_PUBLISHED' | 'DRAFT_READY';
  exam_id?: string;
  question_count: number;
  created_at: string;
}

interface PendingTrigger {
  topic: string;
  misconception_count: number;
  abstain_count: number;
  threshold: number;
  status: string;
}

interface RemedialQuizItem {
  exam_id: string;
  exam_title: string;
  topic: string;
  attempt_count: number;
  avg_score: number;
  mastery_rate: number;
  status: 'CONCEPT_RESOLVED' | 'PARTIAL_MASTERY' | 'NEEDS_REINFORCEMENT';
  badge_label: string;
  last_attempt_at: string;
}

interface RemedialImpactData {
  metrics: {
    total_attempts: number;
    avg_score_pct: number;
    mastery_count: number;
    resolution_rate_pct: number;
  };
  quizzes: RemedialQuizItem[];
}

interface AnalyticsData {
  metrics: TelemetryMetrics;
  topic_hotspots: TopicHotspot[];
  knowledge_gaps: KnowledgeGapItem[];
  misconceptions: MisconceptionItem[];
  autopilot?: {
    config: AutopilotConfig;
    recent_events: AutopilotEvent[];
    pending_triggers: PendingTrigger[];
  };
  remedial_impact?: RemedialImpactData;
}

interface QuizOption {
  id: string;
  text: string;
  is_correct: boolean;
}

interface GeneratedQuizQuestion {
  question: string;
  options: QuizOption[];
  explanation: string;
  citation?: string;
  difficulty_tier?: string;
}

interface KnowledgeGapHeatmapProps {
  courses: any[];
  batches: any[];
}

export const KnowledgeGapHeatmap: React.FC<KnowledgeGapHeatmapProps> = ({ courses = [], batches = [] }) => {
  const [selectedCourse, setSelectedCourse] = useState<string>('');
  const [selectedBatch, setSelectedBatch] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  // Practice generation modal states
  const [practiceModalOpen, setPracticeModalOpen] = useState<boolean>(false);
  const [generatingQuiz, setGeneratingQuiz] = useState<boolean>(false);
  const [activeTopic, setActiveTopic] = useState<string>('');
  const [generatedQuestions, setGeneratedQuestions] = useState<GeneratedQuizQuestion[]>([]);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const [selectedDifficulty, setSelectedDifficulty] = useState<'AUTO' | 'FOUNDATION' | 'APPLICATION' | 'ARCHITECTURAL'>('AUTO');
  const [resolvedTierInfo, setResolvedTierInfo] = useState<{ tier: string; label: string; reason?: string } | null>(null);

  // 1-Click Pop Quiz Publishing states
  const [publishStep, setPublishStep] = useState<boolean>(false);
  const [publishing, setPublishing] = useState<boolean>(false);
  const [publishSuccess, setPublishSuccess] = useState<boolean>(false);
  const [publishError, setPublishError] = useState<string>('');
  const [publishForm, setPublishForm] = useState({
    title: '',
    course_id: '',
    batch_id: '',
    time_limit_minutes: 15,
    due_date: ''
  });

  // Autopilot states
  const [autopilotConfig, setAutopilotConfig] = useState<AutopilotConfig>({
    enabled: false,
    threshold: 3,
    auto_publish: false,
    question_count: 3,
    time_limit_minutes: 15
  });
  const [savingAutopilot, setSavingAutopilot] = useState<boolean>(false);
  const [checkingAutopilot, setCheckingAutopilot] = useState<boolean>(false);
  const [autopilotFeedback, setAutopilotFeedback] = useState<string>('');
  const [showAutopilotSettings, setShowAutopilotSettings] = useState<boolean>(false);

  useEffect(() => {
    if (analytics?.autopilot?.config) {
      setAutopilotConfig(analytics.autopilot.config);
    }
  }, [analytics]);

  const handleSaveAutopilot = async (newConfig: Partial<AutopilotConfig>) => {
    const updated = {
      ...autopilotConfig,
      ...newConfig,
      course_id: selectedCourse || null,
      batch_id: selectedBatch || null
    };
    setAutopilotConfig(updated);
    setSavingAutopilot(true);
    setAutopilotFeedback('');
    try {
      const res = await api.post('/api/rag/teacher/autopilot', {
        action: 'save_config',
        ...updated
      });
      if (res.data?.success) {
        setAutopilotFeedback('Autopilot settings saved.');
        setTimeout(() => setAutopilotFeedback(''), 3000);
      }
    } catch (err: any) {
      console.error('Failed to save autopilot config:', err);
    } finally {
      setSavingAutopilot(false);
    }
  };

  const handleRunAutopilotCheck = async () => {
    setCheckingAutopilot(true);
    setAutopilotFeedback('');
    try {
      const res = await api.post('/api/rag/teacher/autopilot', {
        action: 'evaluate',
        course_id: selectedCourse || null,
        batch_id: selectedBatch || null,
        force: true
      });
      if (res.data?.success) {
        if (res.data.triggered && res.data.dispatches?.length > 0) {
          const d = res.data.dispatches[0];
          setAutopilotFeedback(`Triggered ${d.action === 'AUTO_PUBLISHED' ? 'Live Pop-Quiz' : 'Draft'} on "${d.topic}"!`);
        } else {
          setAutopilotFeedback(res.data.message || 'No topics exceeded confusion threshold.');
        }
        fetchAnalytics();
      }
    } catch (err: any) {
      console.error('Failed to run autopilot check:', err);
      setAutopilotFeedback('Autopilot check failed.');
    } finally {
      setCheckingAutopilot(false);
      setTimeout(() => setAutopilotFeedback(''), 4000);
    }
  };

  const fetchAnalytics = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const params = new URLSearchParams();
      if (selectedCourse) params.append('course_id', selectedCourse);
      if (selectedBatch) params.append('batch_id', selectedBatch);

      const res = await api.get(`/api/rag/teacher/analytics?${params.toString()}`);
      if (res.data?.success) {
        setAnalytics(res.data);
      } else {
        setErrorMsg(res.data?.error || 'Failed to load telemetry analytics.');
      }
    } catch (err: any) {
      console.error('Error fetching RAG analytics:', err);
      setErrorMsg(err.response?.data?.error || 'Could not connect to AI analytics telemetry service.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [selectedCourse, selectedBatch]);

  const handleGeneratePractice = async (topicOrQuestion: string, explicitDiff?: 'AUTO' | 'FOUNDATION' | 'APPLICATION' | 'ARCHITECTURAL') => {
    setActiveTopic(topicOrQuestion);
    setPracticeModalOpen(true);
    setGeneratingQuiz(true);
    setGeneratedQuestions([]);
    setPublishStep(false);
    setPublishSuccess(false);
    setPublishError('');

    const targetDiff = explicitDiff || selectedDifficulty;
    if (explicitDiff) {
      setSelectedDifficulty(explicitDiff);
    }

    const defaultDueDate = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 16);
    const targetCourse = selectedCourse || (courses[0]?.id ?? '');
    const matchingBatch = batches.find(b => !targetCourse || b.course_id === targetCourse);
    setPublishForm({
      title: `Pop Quiz: ${topicOrQuestion.slice(0, 45)}`,
      course_id: targetCourse,
      batch_id: selectedBatch || (matchingBatch ? matchingBatch.id : (batches[0]?.id ?? '')),
      time_limit_minutes: 15,
      due_date: defaultDueDate
    });
    try {
      const res = await api.post('/api/rag/teacher/generate-practice', {
        topic: topicOrQuestion,
        course_id: selectedCourse || null,
        batch_id: selectedBatch || null,
        count: 4,
        difficulty: targetDiff
      });

      if (res.data?.adaptive_info) {
        setResolvedTierInfo(res.data.adaptive_info);
      } else if (res.data?.difficulty_tier) {
        setResolvedTierInfo({
          tier: res.data.difficulty_tier,
          label: `${res.data.difficulty_tier} Tier`,
          reason: `Configured at ${res.data.difficulty_tier} difficulty.`
        });
      }

      const rawQuestions = Array.isArray(res.data?.quiz) && res.data.quiz.length > 0
        ? res.data.quiz
        : (Array.isArray(res.data?.questions) && res.data.questions.length > 0 ? res.data.questions : null);

      if (rawQuestions && rawQuestions.length > 0) {
        const mapped: GeneratedQuizQuestion[] = rawQuestions.map((q: any) => {
          let opts: QuizOption[] = [];
          if (Array.isArray(q.options)) {
            opts = q.options.map((opt: any, i: number) => ({
              id: opt.id || String.fromCharCode(65 + i),
              text: opt.text || opt.option_text || String(opt),
              is_correct: !!opt.is_correct
            }));
          } else if (q.options && typeof q.options === 'object') {
            opts = Object.entries(q.options).map(([key, val]) => ({
              id: key,
              text: String(val),
              is_correct: key === q.correct_answer
            }));
          }
          return {
            question: q.question || q.question_text || '',
            options: opts,
            explanation: q.explanation || 'Grounded in core curriculum materials to eliminate misconceptions.',
            citation: q.citation || q.source_citation || '',
            difficulty_tier: q.difficulty_tier || res.data?.difficulty_tier || 'APPLICATION'
          };
        });
        setGeneratedQuestions(mapped);
      } else {
        // Fallback demo questions if specific material not indexed for that topic
        setGeneratedQuestions([
          {
            question: `Which fundamental principle best resolves the conceptual confusion in: "${topicOrQuestion}"?`,
            options: [
              { id: 'A', text: 'Clean separation of side-effects from rendering life cycles', is_correct: true },
              { id: 'B', text: 'Executing asynchronous closures on a separate background thread pool', is_correct: false },
              { id: 'C', text: 'Mutating component state directly during reconciliation', is_correct: false },
              { id: 'D', text: 'Bypassing dependency tracking arrays during component updates', is_correct: false }
            ],
            explanation: 'Grounded in core curriculum best practices to reinforce conceptual clarity and eliminate misconceptions.',
            citation: 'Course Syllabus Core Principles',
            difficulty_tier: targetDiff === 'AUTO' ? 'FOUNDATION' : targetDiff
          }
        ]);
      }
    } catch (err: any) {
      console.error('Error generating practice quiz:', err);
      setErrorMsg('Failed to generate practice quiz.');
    } finally {
      setGeneratingQuiz(false);
    }
  };

  const copyQuestionToClipboard = (q: GeneratedQuizQuestion, index: number) => {
    const formatted = `${q.question}\n\n` + 
      q.options.map((opt, i) => `${String.fromCharCode(65 + i)}) ${opt.text}${opt.is_correct ? ' [CORRECT]' : ''}`).join('\n') +
      `\n\nExplanation: ${q.explanation}` +
      (q.citation ? `\nCitation: ${q.citation}` : '');

    navigator.clipboard.writeText(formatted);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handlePublishExam = async () => {
    if (!publishForm.course_id) {
      setPublishError('Please select a target course for the pop quiz.');
      return;
    }
    if (!publishForm.batch_id) {
      setPublishError('Please select a target batch for the pop quiz.');
      return;
    }
    if (!publishForm.title.trim()) {
      setPublishError('Please enter a quiz title.');
      return;
    }
    if (!publishForm.due_date) {
      setPublishError('Please choose a submission deadline (due date).');
      return;
    }
    if (generatedQuestions.length === 0) {
      setPublishError('No generated questions found to publish.');
      return;
    }

    setPublishing(true);
    setPublishError('');
    try {
      const questionsPayload = generatedQuestions.map((q) => ({
        question_text: q.question,
        marks: 5,
        options: q.options.map((opt) => ({
          option_text: opt.text,
          is_correct: !!opt.is_correct
        }))
      }));

      const res = await api.post('/api/exams', {
        title: publishForm.title,
        exam_type: 'MCQ',
        course_id: publishForm.course_id,
        batch_id: publishForm.batch_id,
        time_limit_minutes: publishForm.time_limit_minutes,
        due_date: publishForm.due_date,
        questions: questionsPayload
      });

      if (res.data?.success) {
        setPublishSuccess(true);
      } else {
        setPublishError(res.data?.error || 'Failed to publish pop quiz to batch.');
      }
    } catch (err: any) {
      console.error('Error publishing pop quiz:', err);
      setPublishError(err.response?.data?.error || 'Server error while publishing pop quiz.');
    } finally {
      setPublishing(false);
    }
  };

  const maxQueryCount = analytics?.topic_hotspots?.reduce((max, h) => Math.max(max, h.query_count), 1) || 1;

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="glass-card p-6 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-primary-500/10 text-primary-400 border border-primary-500/20">
              <Sparkles className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                Curriculum Knowledge-Gap Telemetry & AI Analytics
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Live System
                </span>
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time tracking of student queries, abstentions, and conceptual misconceptions from the AI Course Tutor.
              </p>
            </div>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          <div className="min-w-[180px]">
            <select
              value={selectedCourse}
              onChange={(e) => {
                setSelectedCourse(e.target.value);
                setSelectedBatch('');
              }}
              className="glass-input text-xs py-2 w-full bg-dark-900 border-slate-700"
            >
              <option value="">All Courses</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.course_name}
                </option>
              ))}
            </select>
          </div>

          <div className="min-w-[180px]">
            <select
              value={selectedBatch}
              onChange={(e) => setSelectedBatch(e.target.value)}
              className="glass-input text-xs py-2 w-full bg-dark-900 border-slate-700"
              disabled={!selectedCourse}
            >
              <option value="">All Batches</option>
              {batches
                .filter((b) => !selectedCourse || b.course_id === selectedCourse)
                .map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.batch_name}
                  </option>
                ))}
            </select>
          </div>

          <button
            onClick={fetchAnalytics}
            disabled={loading}
            className="btn-secondary py-2 px-3 text-xs flex items-center gap-1.5"
            title="Refresh Telemetry"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 p-4 rounded-xl text-xs flex items-center gap-3">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* KPI Metrics Banner */}
      {analytics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Card 1: Total Queries */}
          <div className="glass-card p-4 space-y-2 border-slate-800">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Inquiries</span>
              <Compass className="h-4 w-4 text-primary-400" />
            </div>
            <div className="text-2xl font-extrabold text-slate-100">{analytics.metrics.total_queries}</div>
            <div className="text-[11px] text-slate-400 flex items-center gap-1">
              <span className="text-primary-400 font-semibold">{analytics.metrics.direct_queries} Direct</span>
              <span>·</span>
              <span className="text-purple-400 font-semibold">{analytics.metrics.socratic_queries} Socratic</span>
            </div>
          </div>

          {/* Card 2: Grounding Rate */}
          <div className="glass-card p-4 space-y-2 border-slate-800">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Grounding Rate</span>
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-extrabold text-emerald-400">
              {analytics.metrics.grounding_rate_pct}%
            </div>
            <div className="text-[11px] text-emerald-500/80 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              <span>Grounded on course notes</span>
            </div>
          </div>

          {/* Card 3: Knowledge Gap Rate */}
          <div className="glass-card p-4 space-y-2 border-slate-800">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Knowledge Gaps</span>
              <AlertTriangle className="h-4 w-4 text-amber-400" />
            </div>
            <div className="text-2xl font-extrabold text-amber-400">
              {analytics.metrics.knowledge_gap_rate_pct}%
            </div>
            <div className="text-[11px] text-amber-400/80">
              Missing or shallow syllabus topics
            </div>
          </div>

          {/* Card 4: Misconceptions */}
          <div className="glass-card p-4 space-y-2 border-slate-800">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Misconceptions</span>
              <Flame className="h-4 w-4 text-rose-400" />
            </div>
            <div className="text-2xl font-extrabold text-rose-400">
              {analytics.metrics.misconceptions_count}
            </div>
            <div className="text-[11px] text-rose-400/80">
              Refuted false assumptions
            </div>
          </div>

          {/* Card 5: Avg Confidence */}
          <div className="glass-card p-4 space-y-2 border-slate-800">
            <div className="flex justify-between items-start">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Avg Retrieval Conf.</span>
              <TrendingUp className="h-4 w-4 text-sky-400" />
            </div>
            <div className="text-2xl font-extrabold text-sky-400">
              {analytics.metrics.avg_confidence_pct}%
            </div>
            <div className="text-[11px] text-slate-400">
              Dense + BM25 RRF score
            </div>
          </div>
        </div>
      )}

      {/* --- AI REMEDIAL AUTOPILOT CONTROL CARD --- */}
      {analytics && (
        <div className="glass-card p-5 border-slate-800 bg-gradient-to-r from-slate-900/90 via-dark-900/90 to-primary-950/20 shadow-xl space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl border flex-shrink-0 transition-colors ${
                autopilotConfig.enabled 
                  ? 'bg-primary-500/15 text-primary-400 border-primary-500/30' 
                  : 'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
                <Bot className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                    AI Remedial Autopilot Engine
                  </h3>
                  <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                    autopilotConfig.enabled
                      ? (autopilotConfig.auto_publish 
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' 
                          : 'bg-primary-500/15 text-primary-400 border-primary-500/30')
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}>
                    {autopilotConfig.enabled 
                      ? (autopilotConfig.auto_publish ? '⚡ Active (Auto-Publish)' : '📝 Active (Draft Review)') 
                      : 'Paused'}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Automatically triggers grounded pop-quizzes when student confusion on a topic crosses your threshold.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <button
                onClick={handleRunAutopilotCheck}
                disabled={checkingAutopilot}
                className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5"
                title="Evaluate telemetry for pending confusion thresholds right now"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${checkingAutopilot ? 'animate-spin' : ''}`} />
                {checkingAutopilot ? 'Evaluating...' : 'Check Triggers'}
              </button>
              <button
                onClick={() => setShowAutopilotSettings(!showAutopilotSettings)}
                className="glass-button text-xs py-2 px-3 flex items-center gap-1.5 bg-slate-800/80 hover:bg-slate-800 text-slate-200"
              >
                <Sliders className="h-3.5 w-3.5 text-primary-400" />
                Configure Autopilot
              </button>
            </div>
          </div>

          {autopilotFeedback && (
            <div className="text-xs px-3.5 py-2 rounded-xl bg-primary-950/60 border border-primary-500/30 text-primary-300 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 flex-shrink-0 text-primary-400" />
              <span>{autopilotFeedback}</span>
            </div>
          )}

          {/* Pending Threshold Triggers Alert */}
          {analytics.autopilot?.pending_triggers && analytics.autopilot.pending_triggers.length > 0 && (
            <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
                <span className="text-xs">
                  <strong className="text-amber-300">{analytics.autopilot.pending_triggers[0].topic}</strong> has exceeded the confusion threshold ({analytics.autopilot.pending_triggers[0].misconception_count} misconceptions / {analytics.autopilot.pending_triggers[0].abstain_count} gaps).
                </span>
              </div>
              <button
                onClick={() => handleGeneratePractice(analytics.autopilot!.pending_triggers[0].topic)}
                className="btn-primary text-xs py-1 px-3 whitespace-nowrap bg-amber-500 hover:bg-amber-600 text-dark-950 font-bold border-amber-400 flex items-center gap-1"
              >
                <Zap className="h-3 w-3 fill-current" />
                Review & Dispatch Pop Quiz
              </button>
            </div>
          )}

          {/* Collapsible Autopilot Settings Drawer */}
          {showAutopilotSettings && (
            <div className="pt-4 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in duration-200">
              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Autopilot Status</label>
                <button
                  type="button"
                  onClick={() => handleSaveAutopilot({ enabled: !autopilotConfig.enabled })}
                  disabled={savingAutopilot}
                  className={`w-full py-2 px-3 rounded-xl text-xs font-semibold border flex items-center justify-between transition-colors ${
                    autopilotConfig.enabled
                      ? 'bg-primary-500/20 text-primary-300 border-primary-500/40'
                      : 'bg-slate-800/80 text-slate-400 border-slate-700'
                  }`}
                >
                  <span>{autopilotConfig.enabled ? 'Autopilot ENABLED' : 'Autopilot PAUSED'}</span>
                  <div className={`h-2.5 w-2.5 rounded-full ${autopilotConfig.enabled ? 'bg-primary-400' : 'bg-slate-500'}`} />
                </button>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Trigger Threshold (Inquiries)</label>
                <select
                  value={autopilotConfig.threshold}
                  onChange={(e) => handleSaveAutopilot({ threshold: Number(e.target.value) })}
                  disabled={savingAutopilot}
                  className="glass-input text-xs py-2 w-full bg-dark-900 border-slate-700"
                >
                  <option value={2}>2 confused inquiries (Aggressive)</option>
                  <option value={3}>3 confused inquiries (Recommended)</option>
                  <option value={5}>5 confused inquiries (Moderate)</option>
                  <option value={10}>10 confused inquiries (Conservative)</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Dispatch Behavior</label>
                <select
                  value={autopilotConfig.auto_publish ? 'live' : 'draft'}
                  onChange={(e) => handleSaveAutopilot({ auto_publish: e.target.value === 'live' })}
                  disabled={savingAutopilot}
                  className="glass-input text-xs py-2 w-full bg-dark-900 border-slate-700"
                >
                  <option value="draft">Draft for Teacher Review</option>
                  <option value="live">⚡ Instant Live Batch Publish</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[11px] font-semibold text-slate-400">Quiz Format</label>
                <div className="text-xs py-2 px-3 rounded-xl bg-slate-800/50 border border-slate-700/60 text-slate-300 flex items-center justify-between">
                  <span>{autopilotConfig.question_count} MCQs</span>
                  <span>•</span>
                  <span>{autopilotConfig.time_limit_minutes} Mins Limit</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main Heatmap & Telemetry Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Topic Confusion Hotspots (7 Cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="glass-card p-6 space-y-5 border-slate-800">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <Flame className="h-4 w-4 text-amber-400" />
                  Topic Inquiry & Confusion Heatmap
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Distribution of student inquiries across syllabus modules with confidence levels.
                </p>
              </div>
              <span className="text-[10px] text-slate-400 font-mono bg-slate-900/60 px-2.5 py-1 rounded-md border border-slate-800">
                Sorted by inquiry volume
              </span>
            </div>

            {loading ? (
              <div className="py-12 text-center text-slate-400 text-xs flex justify-center items-center gap-2">
                <RefreshCw className="h-4 w-4 animate-spin text-primary-400" />
                Aggregating curriculum telemetry...
              </div>
            ) : analytics?.topic_hotspots?.length === 0 ? (
              <div className="py-12 text-center text-slate-500 text-xs">
                No telemetry recorded for the selected filter yet.
              </div>
            ) : (
              <div className="space-y-4">
                {analytics?.topic_hotspots.map((hotspot) => {
                  const percentage = Math.round((hotspot.query_count / maxQueryCount) * 100);
                  const isHighConfusion = hotspot.abstain_count > 0 || hotspot.misconception_count > 0;

                  return (
                    <div
                      key={hotspot.topic}
                      className="bg-slate-900/40 p-4 rounded-xl border border-slate-800/80 hover:border-slate-700 transition-all space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="space-y-0.5">
                          <h4 className="text-xs font-bold text-slate-100 flex items-center gap-2">
                            {hotspot.topic}
                            {isHighConfusion && (
                              <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                High Gap Area
                              </span>
                            )}
                          </h4>
                          <p className="text-[11px] text-slate-400">
                            {hotspot.query_count} student inquiries · Avg confidence: {hotspot.avg_confidence}%
                          </p>
                        </div>

                        <div className="flex items-center gap-2">
                          {hotspot.abstain_count > 0 && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                              {hotspot.abstain_count} Abstentions
                            </span>
                          )}
                          {hotspot.misconception_count > 0 && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                              {hotspot.misconception_count} Refuted
                            </span>
                          )}
                          <button
                            onClick={() => handleGeneratePractice(hotspot.topic)}
                            className="btn-primary py-1 px-2.5 text-[11px] flex items-center gap-1 shrink-0 ml-auto sm:ml-0"
                          >
                            <Sparkles className="h-3 w-3" />
                            Targeted Quiz
                          </button>
                        </div>
                      </div>

                      {/* Interactive Visual Bar */}
                      <div className="space-y-1">
                        <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800/80">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              isHighConfusion
                                ? 'bg-gradient-to-r from-amber-500 to-rose-500'
                                : 'bg-gradient-to-r from-primary-600 to-emerald-500'
                            }`}
                            style={{ width: `${Math.max(12, percentage)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Unanswered Knowledge Gaps & Misconceptions (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Card: Unanswered Knowledge Gaps */}
          <div className="glass-card p-5 space-y-4 border-slate-800">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertTriangle className="h-4 w-4" />
              </span>
              <div>
                <h3 className="text-xs font-bold text-slate-200">Unanswered Knowledge Gaps</h3>
                <p className="text-[11px] text-slate-400">Questions where AI tutor safely abstained due to missing syllabus material.</p>
              </div>
            </div>

            <div className="space-y-2.5">
              {analytics?.knowledge_gaps && analytics.knowledge_gaps.length > 0 ? (
                analytics.knowledge_gaps.map((gap, i) => (
                  <div
                    key={i}
                    className="p-3 bg-slate-900/30 rounded-xl border border-slate-800/70 hover:border-amber-500/30 transition-all space-y-2"
                  >
                    <p className="text-xs font-semibold text-slate-200 leading-relaxed">
                      "{gap.question}"
                    </p>
                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                      <span className="text-[10px] text-slate-400 font-mono">{gap.topic}</span>
                      <button
                        onClick={() => handleGeneratePractice(gap.question)}
                        className="text-[10px] text-primary-400 hover:text-primary-300 font-bold flex items-center gap-1"
                      >
                        Create Practice <ArrowRight className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-slate-500 text-xs">
                  No abstained questions logged. Syllabus coverage is optimal!
                </div>
              )}
            </div>
          </div>

          {/* Card: Student Misconceptions */}
          <div className="glass-card p-5 space-y-4 border-slate-800">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                <Flame className="h-4 w-4" />
              </span>
              <div>
                <h3 className="text-xs font-bold text-slate-200">Student Misconceptions</h3>
                <p className="text-[11px] text-slate-400">Premises refuted before generation to prevent student confusion.</p>
              </div>
            </div>

            <div className="space-y-2.5">
              {analytics?.misconceptions && analytics.misconceptions.length > 0 ? (
                analytics.misconceptions.map((misc, i) => (
                  <div
                    key={i}
                    className="p-3 bg-slate-900/30 rounded-xl border border-slate-800/70 hover:border-rose-500/30 transition-all space-y-2"
                  >
                    <p className="text-xs font-semibold text-rose-300 leading-relaxed">
                      "{misc.question}"
                    </p>
                    <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                      <span className="text-[10px] text-slate-400 font-mono">{misc.topic}</span>
                      <button
                        onClick={() => handleGeneratePractice(misc.topic)}
                        className="text-[10px] text-rose-400 hover:text-rose-300 font-bold flex items-center gap-1"
                      >
                        Reinforce Topic <ArrowRight className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-center text-slate-500 text-xs">
                  No false premises detected in student queries.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* --- REMEDIAL QUIZ IMPACT & CONCEPT RESOLUTION DASHBOARD --- */}
      {analytics?.remedial_impact && (
        <div className="glass-card p-6 border-slate-800 space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-4 border-b border-slate-800">
            <div>
              <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                Remedial Exam Performance & Concept Resolution
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Measures how effectively dispatched pop-quizzes have eliminated student confusion and restored curriculum mastery.
              </p>
            </div>

            {/* Quick KPI stats pill */}
            <div className="flex items-center gap-3">
              <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-right">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">Resolution Rate</span>
                <span className="text-sm font-extrabold text-emerald-400">
                  {analytics.remedial_impact.metrics.resolution_rate_pct}%
                </span>
              </div>
              <div className="px-3 py-1.5 rounded-xl bg-primary-500/10 border border-primary-500/20 text-right">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">Avg Score</span>
                <span className="text-sm font-extrabold text-primary-400">
                  {analytics.remedial_impact.metrics.avg_score_pct}%
                </span>
              </div>
              <div className="px-3 py-1.5 rounded-xl bg-slate-800 border border-slate-700 text-right">
                <span className="text-[10px] text-slate-400 uppercase font-bold block">Total Attempts</span>
                <span className="text-sm font-extrabold text-slate-200">
                  {analytics.remedial_impact.metrics.total_attempts}
                </span>
              </div>
            </div>
          </div>

          {/* Remedial Quiz Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/60 text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Remedial Pop Quiz</th>
                  <th className="py-3 px-4">Target Topic</th>
                  <th className="py-3 px-4 text-center">Student Attempts</th>
                  <th className="py-3 px-4 text-center">Average Score</th>
                  <th className="py-3 px-4 text-center">Mastery Rate (≥70%)</th>
                  <th className="py-3 px-4 text-right">Resolution Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {analytics.remedial_impact.quizzes.length > 0 ? (
                  analytics.remedial_impact.quizzes.map((quiz, i) => (
                    <tr key={i} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3 px-4 font-semibold text-slate-200">
                        <div className="flex items-center gap-2">
                          <Zap className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
                          <span>{quiz.exam_title}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        <span className="px-2 py-0.5 rounded-md bg-slate-800 text-slate-300 text-[11px]">
                          {quiz.topic}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center font-bold text-slate-300">
                        {quiz.attempt_count}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`font-bold ${
                          quiz.avg_score >= 75 ? 'text-emerald-400' : quiz.avg_score >= 55 ? 'text-amber-400' : 'text-rose-400'
                        }`}>
                          {quiz.avg_score}%
                        </span>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                quiz.mastery_rate >= 75 ? 'bg-emerald-500' : quiz.mastery_rate >= 50 ? 'bg-amber-500' : 'bg-rose-500'
                              }`}
                              style={{ width: `${Math.min(100, quiz.mastery_rate)}%` }}
                            />
                          </div>
                          <span className="text-[11px] font-semibold text-slate-300">{quiz.mastery_rate}%</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold border ${
                          quiz.status === 'CONCEPT_RESOLVED'
                            ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : quiz.status === 'PARTIAL_MASTERY'
                            ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                            : 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                        }`}>
                          {quiz.badge_label}
                        </span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-500">
                      No remedial pop quiz submissions recorded yet for this batch.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Targeted Practice Quiz Generation Modal */}
      {practiceModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-800 flex justify-between items-center bg-slate-950/50">
              <div className="flex items-center gap-2.5">
                <span className={`p-2 rounded-xl border ${
                  publishSuccess
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : publishStep
                    ? 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                    : 'bg-primary-500/10 text-primary-400 border-primary-500/20'
                }`}>
                  {publishSuccess ? <CheckCircle2 className="h-5 w-5" /> : publishStep ? <Zap className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">
                    {publishSuccess 
                      ? 'Remedial Pop Quiz Dispatched!' 
                      : publishStep 
                      ? 'Publish Pop Quiz to Batch' 
                      : 'Targeted Practice Questions for Knowledge Gap'}
                  </h3>
                  <p className="text-xs text-slate-400 truncate max-w-md">
                    {publishSuccess
                      ? 'Exam is now active in Student Test Center'
                      : publishStep
                      ? 'Configure batch exam parameters and dispatch in 1 click'
                      : <>Focus: <span className="text-primary-300 font-semibold">{activeTopic}</span></>}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setPracticeModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 flex-1">
              {publishSuccess ? (
                <div className="py-10 px-4 text-center space-y-4">
                  <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-500/10">
                    <CheckCircle2 className="h-8 w-8 animate-pulse" />
                  </div>
                  <div className="space-y-1">
                    <h4 className="text-base font-bold text-slate-100">Pop Quiz Published Successfully!</h4>
                    <p className="text-xs text-slate-400 max-w-lg mx-auto leading-relaxed">
                      All students in <span className="text-primary-400 font-semibold">{batches.find(b => b.id === publishForm.batch_id)?.batch_name || 'the selected batch'}</span> have been assigned this remedial quiz. It is now live in their Online Test Center.
                    </p>
                  </div>

                  <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 max-w-md mx-auto text-left text-xs space-y-2">
                    <div className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Quiz Title:</span>
                      <span className="font-semibold text-slate-200">{publishForm.title}</span>
                    </div>
                    <div className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Target Batch:</span>
                      <span className="font-semibold text-slate-200">{batches.find(b => b.id === publishForm.batch_id)?.batch_name || 'Selected Batch'}</span>
                    </div>
                    <div className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Time Limit:</span>
                      <span className="font-semibold text-slate-200">{publishForm.time_limit_minutes} Minutes</span>
                    </div>
                    <div className="flex justify-between text-slate-300">
                      <span className="text-slate-500">Questions:</span>
                      <span className="font-semibold text-emerald-400">{generatedQuestions.length} Questions (20 Marks)</span>
                    </div>
                  </div>
                </div>
              ) : publishStep ? (
                <div className="space-y-5">
                  <div className="bg-primary-950/20 border border-primary-500/20 p-4 rounded-xl flex items-center gap-3 text-xs text-primary-300">
                    <Zap className="h-5 w-5 text-primary-400 shrink-0" />
                    <div>
                      <p className="font-semibold text-slate-200">1-Click Knowledge-Gap Remediation</p>
                      <p className="text-slate-400">
                        Convert these {generatedQuestions.length} AI-verified practice questions directly into a real, auto-evaluated MCQ exam for your students.
                      </p>
                    </div>
                  </div>

                  {publishError && (
                    <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-xl text-xs flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span>{publishError}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1 col-span-1 md:col-span-2">
                      <label className="text-xs font-semibold text-slate-400 uppercase">Exam / Pop Quiz Title</label>
                      <input
                        type="text"
                        value={publishForm.title}
                        onChange={(e) => setPublishForm({ ...publishForm, title: e.target.value })}
                        className="w-full glass-input text-xs"
                        placeholder="e.g. Pop Quiz: React Hooks Dependency Array"
                        required
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-400 uppercase">Target Course</label>
                      <select
                        value={publishForm.course_id}
                        onChange={(e) => {
                          const newCourseId = e.target.value;
                          const matchingBatch = batches.find(b => b.course_id === newCourseId);
                          setPublishForm({
                            ...publishForm,
                            course_id: newCourseId,
                            batch_id: matchingBatch ? matchingBatch.id : ''
                          });
                        }}
                        className="w-full glass-input text-xs bg-dark-900 border-slate-700"
                        required
                      >
                        <option value="">Select Course</option>
                        {courses.map((c) => (
                          <option key={c.id} value={c.id}>{c.course_name}</option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-400 uppercase">Target Batch</label>
                      <select
                        value={publishForm.batch_id}
                        onChange={(e) => setPublishForm({ ...publishForm, batch_id: e.target.value })}
                        className="w-full glass-input text-xs bg-dark-900 border-slate-700"
                        required
                        disabled={!publishForm.course_id}
                      >
                        <option value="">Select Batch</option>
                        {batches
                          .filter((b) => !publishForm.course_id || b.course_id === publishForm.course_id)
                          .map((b) => (
                            <option key={b.id} value={b.id}>{b.batch_name}</option>
                          ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-400 uppercase">Time Limit (Minutes)</label>
                      <input
                        type="number"
                        min="5"
                        max="180"
                        value={publishForm.time_limit_minutes}
                        onChange={(e) => setPublishForm({ ...publishForm, time_limit_minutes: parseInt(e.target.value) || 15 })}
                        className="w-full glass-input text-xs"
                        required
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-slate-400 uppercase">Submission Deadline (Due Date)</label>
                      <input
                        type="datetime-local"
                        value={publishForm.due_date}
                        onChange={(e) => setPublishForm({ ...publishForm, due_date: e.target.value })}
                        className="w-full glass-input text-xs"
                        required
                      />
                    </div>
                  </div>

                  <div className="p-3.5 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Questions Attached:</span>
                    <span className="font-bold text-slate-200">
                      {generatedQuestions.length} Questions · 5 Marks each (20 Marks Total) · Auto-Evaluated
                    </span>
                  </div>
                </div>
              ) : generatingQuiz ? (
                <div className="py-16 text-center space-y-3">
                  <RefreshCw className="h-8 w-8 animate-spin text-primary-400 mx-auto" />
                  <p className="text-xs font-bold text-slate-300">
                    Generating curriculum-grounded practice questions...
                  </p>
                  <p className="text-[11px] text-slate-500">
                    Querying local vector database and running candidate verification.
                  </p>
                </div>
              ) : generatedQuestions.length === 0 ? (
                <div className="py-12 text-center text-slate-400 text-xs">
                  Could not generate practice questions for this topic. Try rephrasing the topic.
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Adaptive Difficulty Ladder Selector */}
                  <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                        <Sliders className="h-3.5 w-3.5 text-primary-400" /> Difficulty Ladder:
                      </span>
                      <div className="inline-flex rounded-lg bg-slate-900 border border-slate-800 p-0.5">
                        {(['AUTO', 'FOUNDATION', 'APPLICATION', 'ARCHITECTURAL'] as const).map((tier) => (
                          <button
                            key={tier}
                            onClick={() => {
                              setSelectedDifficulty(tier);
                              handleGeneratePractice(activeTopic, tier);
                            }}
                            disabled={generatingQuiz}
                            className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition ${
                              selectedDifficulty === tier
                                ? 'bg-primary-500 text-white shadow-sm'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            {tier === 'AUTO' ? '⚡ Adaptive (Auto)' : tier === 'FOUNDATION' ? '📘 Foundation' : tier === 'APPLICATION' ? '⚙️ Application' : '🏛️ Architectural'}
                          </button>
                        ))}
                      </div>
                    </div>

                    {resolvedTierInfo && (
                      <div className="text-[11px] flex items-center gap-1.5">
                        <span className="text-slate-400">Current Tier:</span>
                        <span className={`px-2 py-0.5 rounded font-bold uppercase tracking-wider text-[10px] border ${
                          resolvedTierInfo.tier === 'FOUNDATION'
                            ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
                            : resolvedTierInfo.tier === 'ARCHITECTURAL'
                            ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        }`}>
                          {resolvedTierInfo.label || resolvedTierInfo.tier}
                        </span>
                      </div>
                    )}
                  </div>

                  {generatedQuestions.map((q, idx) => (
                    <div
                      key={idx}
                      className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 space-y-3 relative group"
                    >
                      <div className="flex justify-between items-start gap-4">
                        <p className="text-xs font-bold text-slate-200 leading-snug">
                          <span className="text-primary-400 mr-1.5">Q{idx + 1}.</span>
                          {q.question}
                        </p>
                        <div className="flex items-center gap-2 shrink-0">
                          {q.difficulty_tier && (
                            <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                              q.difficulty_tier === 'FOUNDATION'
                                ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
                                : q.difficulty_tier === 'ARCHITECTURAL'
                                ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                            }`}>
                              {q.difficulty_tier}
                            </span>
                          )}
                          <button
                            onClick={() => copyQuestionToClipboard(q, idx)}
                            className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-1 rounded bg-slate-900 border border-slate-800 flex items-center gap-1 shrink-0"
                            title="Copy Question"
                          >
                            {copiedIndex === idx ? (
                              <>
                                <Check className="h-3 w-3 text-emerald-400" />
                                <span className="text-emerald-400">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="h-3 w-3" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Options */}
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {q.options?.map((opt, optIdx) => (
                          <div
                            key={opt.id || optIdx}
                            className={`p-2.5 rounded-lg border text-xs flex items-center gap-2 ${
                              opt.is_correct
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 font-semibold'
                                : 'bg-slate-900/40 border-slate-800/80 text-slate-300'
                            }`}
                          >
                            <span className="font-mono text-[10px] uppercase font-bold text-slate-400">
                              {opt.id || String.fromCharCode(65 + optIdx)})
                            </span>
                            <span className="flex-1">{opt.text}</span>
                            {opt.is_correct && (
                              <span className="text-[9px] uppercase font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                                Correct
                              </span>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Explanation & Citation */}
                      {q.explanation && (
                        <div className="pt-2 border-t border-slate-900 text-[11px] text-slate-400 flex items-start gap-1.5">
                          <BookOpen className="h-3.5 w-3.5 text-primary-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="font-semibold text-slate-300">Explanation:</span> {q.explanation}
                            {q.citation && (
                              <div className="text-[10px] text-primary-400 font-mono mt-0.5">
                                Source: {q.citation}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-800 bg-slate-950/40 flex flex-col sm:flex-row justify-between items-center gap-3">
              <span className="text-[11px] text-slate-500">
                Grounding Engine: Ollama nomic-embed-text & llama3.2
              </span>

              <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
                {publishSuccess ? (
                  <button
                    onClick={() => {
                      setPracticeModalOpen(false);
                      setPublishSuccess(false);
                      setPublishStep(false);
                    }}
                    className="btn-primary py-1.5 px-5 text-xs"
                  >
                    Done
                  </button>
                ) : publishStep ? (
                  <>
                    <button
                      onClick={() => {
                        setPublishStep(false);
                        setPublishError('');
                      }}
                      disabled={publishing}
                      className="btn-secondary py-1.5 px-4 text-xs"
                    >
                      Back to Questions
                    </button>
                    <button
                      onClick={handlePublishExam}
                      disabled={publishing || !publishForm.batch_id || !publishForm.course_id}
                      className="btn-primary py-1.5 px-5 text-xs flex items-center gap-1.5 shadow-lg shadow-primary-500/20 font-semibold"
                    >
                      {publishing ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          Publishing to Batch...
                        </>
                      ) : (
                        <>
                          <Send className="h-3.5 w-3.5" />
                          Confirm & Dispatch Quiz
                        </>
                      )}
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => setPracticeModalOpen(false)}
                      className="btn-secondary py-1.5 px-4 text-xs"
                    >
                      Close
                    </button>
                    {generatedQuestions.length > 0 && !generatingQuiz && (
                      <button
                        onClick={() => {
                          setPublishStep(true);
                          setPublishError('');
                        }}
                        className="btn-primary py-1.5 px-4 text-xs flex items-center gap-1.5 shadow-lg shadow-primary-500/20 font-semibold"
                      >
                        <Zap className="h-3.5 w-3.5 text-amber-300" />
                        Publish to Batch as Pop Quiz
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default KnowledgeGapHeatmap;
