'use client';

import { FormEvent, useEffect, useState } from 'react';
import AuthenticatedLayout from '@/app/authenticated-layout';

type Citation = { citation_id: string; source_label: string; page_number: number | null; chunk_index: number };
type Document = { id: string; title: string; source_name: string; status: string; chunk_count: number };
type ChatResult = { conversation_id: string; answer: string; answerable: boolean; citations: Citation[]; retrieval_count: number };

export default function AssistantPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [title, setTitle] = useState('');
  const [sourceName, setSourceName] = useState('notes.txt');
  const [content, setContent] = useState('');
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [result, setResult] = useState<ChatResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { fetch('/api/ai/documents', { credentials: 'include' }).then((response) => response.json()).then(setDocuments).catch(() => setError('Could not load your documents.')); }, []);

  async function addDocument(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'include' });
      const { csrf_token: csrfToken } = await csrfResponse.json();
      const response = await fetch('/api/ai/documents', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, credentials: 'include', body: JSON.stringify({ title, source_name: sourceName, content }) });
      if (!response.ok) throw new Error((await response.json()).detail || 'Document indexing failed');
      const document = await response.json(); setDocuments((items) => [document, ...items]); setTitle(''); setContent('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Document indexing failed'); } finally { setBusy(false); }
  }

  async function ask(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setResult(null);
    try { const csrfResponse = await fetch('/api/auth/csrf', { credentials: 'include' }); const { csrf_token: csrfToken } = await csrfResponse.json(); const response = await fetch('/api/ai/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken }, credentials: 'include', body: JSON.stringify({ question, conversation_id: conversationId }) }); if (!response.ok) throw new Error((await response.json()).detail || 'Assistant unavailable'); const chatResult: ChatResult = await response.json(); setConversationId(chatResult.conversation_id); setResult(chatResult); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Assistant unavailable'); } finally { setBusy(false); }
  }

  return <AuthenticatedLayout><div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[0.8fr_1.2fr]"><section className="space-y-5"><p className="text-xs font-semibold uppercase tracking-caps text-accent-600">Private knowledge desk</p><h1 className="font-display text-4xl font-bold text-ink-900">Ask your documents.</h1><p className="text-ink-500">Answers are limited to evidence indexed from your own documents.</p><form onSubmit={addDocument} className="space-y-3 rounded-tile border border-ink-100 bg-white p-6 shadow-tile"><h2 className="font-semibold text-ink-900">Add a text document</h2><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title" className="w-full rounded border p-2" /><input required value={sourceName} onChange={(event) => setSourceName(event.target.value)} placeholder="Source name" className="w-full rounded border p-2" /><textarea required value={content} onChange={(event) => setContent(event.target.value)} placeholder="Paste document text" rows={8} className="w-full rounded border p-2" /><button disabled={busy} className="rounded bg-accent-600 px-4 py-2 font-semibold text-white disabled:opacity-50">{busy ? 'Indexing...' : 'Index document'}</button></form><div className="space-y-2"><h2 className="font-semibold text-ink-900">Your indexed sources</h2>{documents.length === 0 ? <p className="text-sm text-ink-500">No documents indexed yet.</p> : documents.map((document) => <p key={document.id} className="text-sm text-ink-600">{document.title} · {document.chunk_count} chunks</p>)}</div></section><section className="rounded-tile border border-ink-100 bg-white p-6 shadow-tile"><form onSubmit={ask} className="flex gap-3"><input required value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question" className="min-w-0 flex-1 rounded border p-3" /><button disabled={busy} className="rounded bg-ink-900 px-4 py-2 font-semibold text-white disabled:opacity-50">Ask</button></form>{error && <p role="alert" className="mt-5 rounded bg-red-50 p-3 text-red-700">{error}</p>}{result && <div className="mt-8 space-y-5"><p className="whitespace-pre-wrap text-ink-900">{result.answer}</p>{result.answerable && <div><h2 className="text-xs font-semibold uppercase tracking-caps text-ink-500">Sources</h2><ul className="mt-2 space-y-1 text-sm text-ink-600">{result.citations.map((citation) => <li key={citation.citation_id}>{citation.citation_id}: {citation.source_label}, chunk {citation.chunk_index}</li>)}</ul></div>}</div>}</section></div></AuthenticatedLayout>;
}
