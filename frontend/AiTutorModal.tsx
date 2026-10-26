import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, Sparkles, X, BookOpen, AlertCircle, RefreshCw, GraduationCap, Mic, MicOff, MessageSquareText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import api from '../services/api';
import { supabase } from '../supabaseClient';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface SourceCitation {
  title: string;
  chunk_index: number;
  similarity: number;
}

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  sources?: SourceCitation[];
  timestamp: string;
  mode?: 'direct' | 'socratic';
}

interface AiTutorModalProps {
  isOpen: boolean;
  onClose: () => void;
  courseId?: string;
  batchId?: string;
  courseName?: string;
  initialPrompt?: string;
}

export const AiTutorModal: React.FC<AiTutorModalProps> = ({
  isOpen,
  onClose,
  courseId,
  batchId,
  courseName = 'Full Stack Web Development',
  initialPrompt
}) => {
  const [mode, setMode] = useState<'direct' | 'socratic'>('direct');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: `Hello! I'm your EduConnect AI Course Tutor for **${courseName}**. I answer questions grounded strictly in your official syllabus and study materials.\n\nChoose **Direct** for instant factual explanations or **Socratic Tutor** for guided hints and practice questions. What would you like to explore today?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      mode: 'direct'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastInitialPromptRef = useRef<string | null>(null);
  const recognitionRef = useRef<any>(null);

  const sampleQuestions = [
    'How does Flexbox justify-content differ from align-items?',
    'Explain useEffect cleanup function with an example',
    'What are 1NF, 2NF, and 3NF in database normalization?',
    'What is the difference between let, const, and var?'
  ];

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isOpen]);

  useEffect(() => {
    if (isOpen && initialPrompt && lastInitialPromptRef.current !== initialPrompt) {
      lastInitialPromptRef.current = initialPrompt;
      handleSend(initialPrompt);
    }
  }, [isOpen, initialPrompt]);

  // Web Speech API Voice Recognition setup
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setInput(transcript);
        }
      };

      recognition.onerror = () => {
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  const toggleVoice = () => {
    if (!recognitionRef.current) {
      alert('Voice speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        setIsListening(false);
      }
    }
  };

  if (!isOpen) return null;

  const handleSend = async (questionText?: string) => {
    const q = (questionText || input).trim();
    if (!q || loading) return;

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    const assistantMsgId = String(Date.now() + 1);
    const initialAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      sender: 'assistant',
      text: '',
      sources: [],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      mode: mode
    };

    setMessages((prev) => [...prev, userMsg, initialAssistantMsg]);
    if (!questionText) setInput('');
    setLoading(true);

    try {
      const historyPayload = messages.map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      }));

      // Retrieve session token if available
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      // Stream request to /api/rag/stream
      const response = await fetch(`${API_URL}/api/rag/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          question: q,
          course_id: courseId,
          batch_id: batchId,
          history: historyPayload,
          mode: mode,
          stream: true
        })
      });

      if (!response.ok || !response.body) {
        throw new Error('Streaming failed, falling back to standard endpoint');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulatedText = '';
      let detectedSources: SourceCitation[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.replace('event:', '').trim();
          } else if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.replace('data:', '').trim();
            if (!dataStr) continue;
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent === 'metadata') {
                if (data.sources) {
                  detectedSources = data.sources;
                }
              } else if (currentEvent === 'token') {
                if (data.token) {
                  accumulatedText += data.token;
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMsgId
                        ? { ...m, text: accumulatedText, sources: detectedSources, mode: mode }
                        : m
                    )
                  );
                }
              } else if (currentEvent === 'done') {
                if (data.sources && detectedSources.length === 0) {
                  detectedSources = data.sources;
                }
                if (data.answer && !accumulatedText) {
                  accumulatedText = data.answer;
                }
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, text: accumulatedText, sources: detectedSources, mode: mode }
                      : m
                  )
                );
              }
            } catch (jsonErr) {
              // Ignore partial JSON
            }
          }
        }
      }

      // If finished streaming and accumulatedText is empty, provide fallback
      if (!accumulatedText) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, text: 'I could not generate an answer at this time.' }
              : m
          )
        );
      }
    } catch (err: any) {
      // Fallback to synchronous ask if streaming encounters connection error
      try {
        const historyPayload = messages.map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text
        }));

        const res = await api.post('/api/rag/ask', {
          question: q,
          course_id: courseId,
          batch_id: batchId,
          history: historyPayload,
          mode: mode
        });

        const reply = res.data?.answer || 'I could not generate an answer at this time.';
        const sources = res.data?.sources || [];

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, text: reply, sources: sources, mode: mode }
              : m
          )
        );
      } catch (fallbackErr) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  text: 'Sorry, I encountered an issue connecting to the AI Tutor service. Please ensure the backend server and Ollama are running.'
                }
              : m
          )
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="flex flex-col w-full max-w-2xl h-[660px] bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-700 text-white shadow-sm">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-white/20 rounded-xl backdrop-blur-md">
              <Sparkles className="w-5 h-5 text-yellow-300" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold">EduConnect AI Course Tutor</h2>
                <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-white/20 text-white border border-white/30">
                  {mode === 'socratic' ? '🧠 Socratic' : '⚡ Direct'}
                </span>
              </div>
              <p className="text-xs text-blue-100 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span>
                Grounded in Approved Syllabus (SSE Streaming Active)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-white/80 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Switcher Pill Banner */}
        <div className="px-6 py-2 bg-slate-100/90 border-b border-slate-200/80 flex items-center justify-between text-xs">
          <span className="text-slate-600 font-medium flex items-center gap-1.5">
            Pedagogical Mode:
          </span>
          <div className="inline-flex rounded-lg bg-white p-0.5 border border-slate-300 shadow-xs">
            <button
              onClick={() => setMode('direct')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium text-xs transition-all ${
                mode === 'direct'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Direct Answer
            </button>
            <button
              onClick={() => setMode('socratic')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium text-xs transition-all ${
                mode === 'socratic'
                  ? 'bg-indigo-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <GraduationCap className="w-3.5 h-3.5" />
              Socratic Guide
            </button>
          </div>
        </div>

        {/* Messages Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                  m.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-none'
                    : 'bg-white text-slate-800 border border-slate-200/80 rounded-tl-none'
                }`}
              >
                {/* Socratic indicator tag */}
                {m.sender === 'assistant' && m.mode === 'socratic' && m.id !== 'welcome' && (
                  <div className="inline-flex items-center gap-1 mb-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                    <GraduationCap className="w-3 h-3 text-indigo-600" /> Socratic Guided Learning
                  </div>
                )}

                {m.sender === 'user' ? (
                  <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
                ) : (
                  <div className="prose prose-sm prose-slate max-w-none leading-relaxed
                    prose-p:my-1.5 prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1
                    prose-headings:text-slate-800 prose-headings:font-semibold prose-headings:mt-3 prose-headings:mb-1
                    prose-code:text-indigo-700 prose-code:bg-indigo-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:font-mono prose-code:before:content-none prose-code:after:content-none
                    prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-pre:rounded-lg prose-pre:p-3 prose-pre:text-xs prose-pre:overflow-x-auto prose-pre:my-2
                    prose-a:text-blue-600 prose-strong:text-slate-900">
                    {m.text ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                    ) : (
                      <span className="flex items-center gap-2 text-slate-400 italic">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-600" />
                        Synthesizing verified answer...
                      </span>
                    )}
                  </div>
                )}

                {/* Sources Section */}
                {m.sources && m.sources.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-100 space-y-1">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                      <BookOpen className="w-3 h-3 text-indigo-500" /> Verified Course Sources:
                    </p>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {m.sources.map((s, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 text-[11px] font-medium bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full border border-indigo-100"
                        >
                          {s.title} (Sec {s.chunk_index + 1}) • {Math.round(s.similarity * 100)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <span
                  className={`block text-[10px] mt-1 text-right ${
                    m.sender === 'user' ? 'text-blue-200' : 'text-slate-400'
                  }`}
                >
                  {m.timestamp}
                </span>
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggested Queries */}
        <div className="px-4 py-2 bg-white border-t border-slate-100 overflow-x-auto flex gap-2 no-scrollbar">
          {sampleQuestions.map((sq, i) => (
            <button
              key={i}
              onClick={() => handleSend(sq)}
              disabled={loading}
              className="text-xs whitespace-nowrap bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 font-medium px-3 py-1.5 rounded-full transition-colors border border-slate-200/60"
            >
              {sq}
            </button>
          ))}
        </div>

        {/* Input Bar with Voice & Send */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center gap-2">
          <button
            type="button"
            onClick={toggleVoice}
            disabled={loading}
            title={isListening ? 'Stop voice recording' : 'Speak your question'}
            className={`p-2.5 rounded-xl border transition flex items-center justify-center ${
              isListening
                ? 'bg-red-500 text-white animate-pulse border-red-600 shadow-md'
                : 'bg-slate-100 hover:bg-slate-200 text-slate-600 border-slate-200'
            }`}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder={
              isListening
                ? 'Listening... speak clearly into your microphone'
                : mode === 'socratic'
                ? 'Ask for guidance on a concept, code problem, or error...'
                : 'Ask anything about your syllabus or study notes...'
            }
            disabled={loading}
            className={`flex-1 px-4 py-2.5 bg-slate-50 border rounded-xl text-sm focus:outline-none focus:ring-2 transition ${
              isListening
                ? 'border-red-400 focus:ring-red-400 bg-red-50/30'
                : mode === 'socratic'
                ? 'border-indigo-200 focus:ring-indigo-500 focus:bg-white'
                : 'border-slate-300 focus:ring-blue-500 focus:bg-white'
            }`}
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className={`p-2.5 disabled:bg-slate-300 text-white rounded-xl shadow-sm transition flex items-center justify-center ${
              mode === 'socratic'
                ? 'bg-indigo-600 hover:bg-indigo-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AiTutorModal;
