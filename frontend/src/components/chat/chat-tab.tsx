// filepath: frontend/src/components/chat/chat-tab.tsx
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, MessageSquare, Plus, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { chatApi, type ChatMessage, type ChatSession } from "@/lib/api-client";
import { streamChat, type ChatSourceEvent } from "@/lib/sse-client";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ErrorBanner } from "@/components/ui/error-banner";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/format";

export function ChatTab({ companyId }: { companyId: string }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [sources, setSources] = useState<ChatSourceEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const queryClient = useQueryClient();

  // Load sessions list
  const { data: sessionsData } = useQuery({
    queryKey: ["chat-sessions", companyId],
    queryFn: () => chatApi.listSessions(companyId, { limit: 50 }),
  });
  const sessions = sessionsData?.items ?? [];

  // Load session history when selecting a session
  const loadSession = useCallback(
    async (sid: string) => {
      try {
        const data = await chatApi.getSession(companyId, sid);
        setSessionId(sid);
        setMessages(data.messages);
        setSources([]);
        setError(null);
      } catch {
        setError("Failed to load session");
      }
    },
    [companyId],
  );

  // New chat
  const newChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setSources([]);
    setStreamingContent("");
    setError(null);
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // Send message
  const sendMessage = useCallback(() => {
    const text = input.trim();
    if (!text || streaming) return;

    setInput("");
    setError(null);
    setSources([]);

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setStreaming(true);
    setStreamingContent("");

    const controller = streamChat(
      companyId,
      { message: text, session_id: sessionId ?? undefined },
      {
        onSession: (data) => {
          setSessionId(data.session_id);
          queryClient.invalidateQueries({
            queryKey: ["chat-sessions", companyId],
          });
        },
        onToken: (data) => {
          setStreamingContent((prev) => prev + data.token);
        },
        onSources: (data) => {
          setSources(data.sources);
        },
        onDone: (data) => {
          setStreamingContent((prev) => {
            const assistantMsg: ChatMessage = {
              id: data.message_id,
              role: "assistant",
              content: prev,
              created_at: new Date().toISOString(),
            };
            setMessages((msgs) => [...msgs, assistantMsg]);
            return "";
          });
          setStreaming(false);
        },
        onError: (data) => {
          setError(data.message || data.error);
          setStreaming(false);
        },
        onConnectionError: (err) => {
          setError(`Connection lost: ${err.message}`);
          setStreaming(false);
        },
      },
    );
    abortRef.current = controller;
  }, [input, streaming, companyId, sessionId, queryClient]);

  return (
    <div className="flex h-[calc(100vh-280px)] gap-4">
      {/* Session sidebar */}
      <div className="w-64 flex-shrink-0 space-y-2 overflow-y-auto rounded-xl border border-gray-200 bg-white p-3">
        <Button variant="outline" size="sm" className="w-full" onClick={newChat}>
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </Button>
        <div className="space-y-1">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadSession(s.id)}
              className={cn(
                "w-full rounded-lg px-3 py-2 text-left text-sm transition-colors",
                sessionId === s.id
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:bg-gray-100",
              )}
            >
              <p className="truncate font-medium">{s.title}</p>
              <p className="text-xs text-gray-400">
                {formatRelativeTime(s.updated_at)}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Chat main */}
      <div className="flex flex-1 flex-col rounded-xl border border-gray-200 bg-white">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !streaming && (
            <EmptyState
              icon={<MessageSquare className="h-10 w-10" />}
              title="Start a conversation"
              description="Ask questions about this company's financial filings."
            />
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {streaming && streamingContent && (
            <div className="flex justify-start">
              <div className="max-w-[80%] rounded-2xl bg-gray-100 px-4 py-3 text-sm text-gray-800">
                <ReactMarkdown>{streamingContent}</ReactMarkdown>
                <span className="inline-block h-4 w-1 animate-pulse bg-gray-400 ml-0.5" />
              </div>
            </div>
          )}
          {streaming && !streamingContent && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-gray-100 px-4 py-3">
                <Spinner className="h-4 w-4 text-gray-400" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Sources */}
        {sources.length > 0 && (
          <div className="border-t border-gray-100 px-4 py-2">
            <p className="text-xs font-medium text-gray-500 mb-1">Sources</p>
            <div className="flex flex-wrap gap-1.5">
              {sources.map((s, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  📄 {s.doc_type} FY{s.fiscal_year}
                  {s.section_title ? ` ${s.section_title}` : ""}
                  {s.score ? ` (${(s.score * 100).toFixed(0)}%)` : ""}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className="px-4 pb-2">
            <ErrorBanner message={error} />
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-200 p-3">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask about financial filings…"
              rows={1}
              className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <Button
              size="icon"
              onClick={sendMessage}
              disabled={!input.trim() || streaming}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm",
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-800",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <ReactMarkdown>{message.content}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
