import React, { useState, useEffect, useRef } from 'react';
import { 
  Stethoscope, 
  X, 
  Send, 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle, 
  RefreshCw, 
  BookOpen, 
  Lightbulb, 
  MessageSquare,
  Award
} from 'lucide-react';
import api from '../services/api';

interface ConceptDoctorModalProps {
  isOpen: boolean;
  onClose: () => void;
  topic: string;
  question: string;
  studentChoice: string;
  correctChoice: string;
  citation?: string;
  courseId?: string | null;
  batchId?: string | null;
  studentId: string;
  onBreakthroughResolved?: () => void;
}

interface ChatMessage {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  time: string;
}

export const ConceptDoctorModal: React.FC<ConceptDoctorModalProps> = ({
  isOpen,
  onClose,
  topic,
  question,
  studentChoice,
  correctChoice,
  citation,
  courseId,
  batchId,
  studentId,
  onBreakthroughResolved
}) => {
  const [loadingInitial, setLoadingInitial] = useState<boolean>(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<Array<{ title: string; section: string }>>([]);
  const [inputText, setInputText] = useState<string>('');
  const [sending, setSending] = useState<boolean>(false);
  const [breakthrough, setBreakthrough] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>('');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      initiateSession();
    } else {
      setMessages([]);
      setSources([]);
      setInputText('');
      setBreakthrough(false);
      setErrorMsg('');
    }
  }, [isOpen, topic, question]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  const initiateSession = async () => {
    setLoadingInitial(true);
    setErrorMsg('');
    try {
      const res = await api.post('/api/rag/concept-doctor/initiate', {
        student_id: studentId,
        topic,
        question,
        student_choice: studentChoice,
        correct_choice: correctChoice,
        course_id: courseId || null,
        batch_id: batchId || null
      });

      if (res.data?.success) {
        setMessages([
          {
            id: 'msg_0',
            role: 'assistant',
            content: res.data.initial_message || 'Welcome to your 1-on-1 Socratic diagnostic consultation.',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          }
        ]);
        setSources(res.data.sources || []);
      } else {
        setErrorMsg(res.data?.error || 'Failed to initiate diagnostic consultation.');
      }
    } catch (err: any) {
      console.error('Error starting Concept Doctor session:', err);
      setErrorMsg('Could not connect to AI Concept Doctor. Please try again.');
    } finally {
      setLoadingInitial(false);
    }
  };

  const handleSendMessage = async (customText?: string) => {
    const textToSend = customText || inputText;
    if (!textToSend.trim() || sending) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: textToSend.trim(),
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setSending(true);

    try {
      const historyPayload = messages.map(m => ({
        role: m.role,
        content: m.content
      }));

      const res = await api.post('/api/rag/concept-doctor/message', {
        student_id: studentId,
        topic,
        question,
        correct_choice: correctChoice,
        message: textToSend.trim(),
        history: historyPayload,
        course_id: courseId || null,
        batch_id: batchId || null
      });

      if (res.data?.success) {
        const assistantMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          role: 'assistant',
          content: res.data.message || 'Understood. Let us think about the next step.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, assistantMsg]);

        if (res.data.breakthrough) {
          setBreakthrough(true);
          if (onBreakthroughResolved) {
            onBreakthroughResolved();
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to send turn to Concept Doctor:', err);
    } finally {
      setSending(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-slate-800 flex justify-between items-center bg-slate-950/60">
          <div className="flex items-center gap-3">
            <span className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Stethoscope className="h-5 w-5" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-100">AI Concept Doctor</h3>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-300 border border-teal-500/30 flex items-center gap-1">
                  <Sparkles className="h-2.5 w-2.5" /> Socratic Remediation
                </span>
              </div>
              <p className="text-xs text-slate-400 truncate max-w-sm sm:max-w-md">
                Topic Focus: <span className="text-teal-300 font-semibold">{topic}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Diagnostic Context Bar */}
        <div className="p-3.5 bg-slate-950/90 border-b border-slate-800/80 text-xs space-y-2">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5 flex-1">
              <p className="font-medium text-slate-300 line-clamp-2">
                <span className="text-slate-400">Target Question:</span> {question}
              </p>
              <div className="flex flex-wrap items-center gap-3 text-[11px]">
                {studentChoice && (
                  <span className="text-rose-400">
                    Your choice: <span className="font-semibold">{studentChoice}</span>
                  </span>
                )}
                {citation && (
                  <span className="text-slate-400 flex items-center gap-1">
                    <BookOpen className="h-3 w-3 text-primary-400" /> Ref: {citation}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Breakthrough Banner */}
        {breakthrough && (
          <div className="p-3 bg-gradient-to-r from-emerald-950/40 via-teal-950/30 to-emerald-950/40 border-b border-emerald-500/30 flex items-center gap-2.5 text-xs text-emerald-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
            <div className="flex-1">
              <span className="font-bold text-slate-100">Concept Breakthrough Achieved! </span>
              <span>You resolved the misconception. Your mastery records have been automatically updated.</span>
            </div>
          </div>
        )}

        {/* Chat Stream Body */}
        <div className="p-4 sm:p-5 overflow-y-auto space-y-4 flex-1 bg-slate-950/30">
          {loadingInitial ? (
            <div className="py-16 text-center space-y-3">
              <RefreshCw className="h-7 w-7 animate-spin text-teal-400 mx-auto" />
              <p className="text-xs font-bold text-slate-300">
                Examining curriculum notes and preparing Socratic consultation...
              </p>
              <p className="text-[11px] text-slate-500">
                Isolating root distractor with local llama3.2 inference.
              </p>
            </div>
          ) : errorMsg ? (
            <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-xs text-rose-300 text-center space-y-2">
              <p>{errorMsg}</p>
              <button 
                onClick={initiateSession}
                className="btn-secondary py-1 px-3 text-xs inline-flex items-center gap-1"
              >
                <RefreshCw className="h-3 w-3" /> Retry Consultation
              </button>
            </div>
          ) : (
            <>
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-3 text-xs ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {m.role === 'assistant' && (
                    <div className="h-7 w-7 rounded-lg bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400 shrink-0 mt-0.5">
                      <Stethoscope className="h-3.5 w-3.5" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl p-3.5 space-y-1.5 ${
                      m.role === 'user'
                        ? 'bg-primary-600 text-white rounded-tr-none'
                        : 'bg-slate-900/90 border border-slate-800 text-slate-200 rounded-tl-none shadow-md'
                    }`}
                  >
                    <p className="leading-relaxed whitespace-pre-wrap">{m.content}</p>
                    <div
                      className={`text-[10px] text-right ${
                        m.role === 'user' ? 'text-primary-200' : 'text-slate-400'
                      }`}
                    >
                      {m.time}
                    </div>
                  </div>
                </div>
              ))}

              {sending && (
                <div className="flex gap-3 text-xs justify-start">
                  <div className="h-7 w-7 rounded-lg bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400 shrink-0 mt-0.5">
                    <Stethoscope className="h-3.5 w-3.5" />
                  </div>
                  <div className="bg-slate-900 border border-slate-800 text-slate-400 rounded-2xl rounded-tl-none p-3 flex items-center gap-2">
                    <RefreshCw className="h-3 w-3 animate-spin text-teal-400" />
                    <span>Concept Doctor is formulating guiding feedback...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Suggestion Chips */}
        {!loadingInitial && !sending && (
          <div className="px-4 py-2 bg-slate-950/70 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto text-[11px]">
            <span className="text-slate-400 flex items-center gap-1 shrink-0">
              <Lightbulb className="h-3 w-3 text-amber-400" /> Quick Replies:
            </span>
            <button
              onClick={() => handleSendMessage("Could you explain with a simple real-world analogy?")}
              className="px-2.5 py-1 rounded-full bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 shrink-0 transition"
            >
              Ask for an analogy
            </button>
            <button
              onClick={() => handleSendMessage("What happens during the unmounting lifecycle phase?")}
              className="px-2.5 py-1 rounded-full bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 shrink-0 transition"
            >
              Ask about lifecycle
            </button>
            <button
              onClick={() => handleSendMessage("I think the cleanup function prevents active subscriptions from persisting!")}
              className="px-2.5 py-1 rounded-full bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 border border-teal-500/30 shrink-0 transition"
            >
              Propose solution
            </button>
          </div>
        )}

        {/* Message Input Footer */}
        <div className="p-3 sm:p-4 border-t border-slate-800 bg-slate-950/90">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={breakthrough ? "Breakthrough confirmed! Ask any follow-up..." : "Type your reasoning or ask a clarifying question..."}
              disabled={loadingInitial || sending}
              className="glass-input flex-1 text-xs py-2"
            />
            <button
              type="submit"
              disabled={loadingInitial || sending || !inputText.trim()}
              className="btn-primary py-2 px-3.5 text-xs flex items-center gap-1.5 shrink-0 bg-teal-600 hover:bg-teal-500 text-white font-semibold"
            >
              <Send className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Respond</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ConceptDoctorModal;
