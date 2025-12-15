import React, { useState, useEffect, useCallback } from 'react';
import '../index.css';

import StartForm from './StartForm';
import ReviewPanel from './ReviewPanel';
import DraftViewer from './DraftViewer';
import AgentStream from './AgentStream';
import StatusIndicator from './StatusIndicator';

const API_BASE_URL = 'http://127.0.0.1:8000';

const INITIAL_STATE = {
    threadId: null,
    status: 'IDLE', // IDLE | RUNNING | AWAITING_HUMAN_REVIEW | COMPLETED | FAILED
    currentDraft: '',
    critique: null,
    streamEvents: [],
    loading: false,
    error: null,
    humanDecision: '',
};

function ProtocolWorkbench() {
    const [state, setState] = useState(INITIAL_STATE);
    const { threadId, status, currentDraft, critique, loading, error, humanDecision } = state;

    /* ----------------------------------------------------
       Ensure humanDecision is populated when review starts
    -----------------------------------------------------*/
    useEffect(() => {
        if (
            status === 'AWAITING_HUMAN_REVIEW' &&
            currentDraft &&
            humanDecision !== currentDraft
        ) {
            setState(s => ({ ...s, humanDecision: currentDraft }));
        }
    }, [status, currentDraft]);

    /* ----------------------------------------------------
       SSE PARSER — STATUS IS AUTHORITATIVE
    -----------------------------------------------------*/
    const parseStreamData = (chunk) => {
    const lines = chunk.split('\n\n').filter(Boolean);

    lines.forEach(line => {
        if (!line.startsWith('data: ')) return;

        try {
            const payload = JSON.parse(line.slice(6));

            setState(prev => {
                const next = { ...prev };

                /* ---------------------------
                   🔥 STATUS FIX (CRITICAL)
                ----------------------------*/
                    const incomingStatus =
                        payload.status ??
                        payload.data?.status ??
                        payload.data?.output?.status;

                    if (incomingStatus) {
                        console.log('[SSE STATUS]', incomingStatus);
                        next.status = incomingStatus;
                    }

                    /* ---------------------------
                    Thread ID fix
                    ----------------------------*/
                    if (payload.thread_id || payload.data?.thread_id) {
                        next.threadId =
                            payload.thread_id ?? payload.data.thread_id;
                    }

                    /* ---------------------------
                    Draft updates
                    ----------------------------*/
                    const draft =
                        payload.data?.current_draft ??
                        payload.data?.currentDraft ??
                        payload.data?.output?.current_draft;

                    if (draft) {
                        next.currentDraft = draft;
                            if (prev.status === 'AWAITING_HUMAN_REVIEW') {
                                next.initialDecision = draft;
    }
                    }

                    /* ---------------------------
                    Stream events (logs only)
                    ----------------------------*/
                    if (payload.event || payload.type) {
                        next.streamEvents = [
                            ...(prev.streamEvents || []),
                            payload
                        ];
                    }

                    /* ---------------------------
                    Finalization
                    ----------------------------*/
                    if (incomingStatus === 'COMPLETED') {
                        next.loading = false;
                    }

                    if (incomingStatus === 'AWAITING_HUMAN_REVIEW') {
                        next.loading = false;
                    }

                    switch (payload.type) {

                        case 'meta':
                            next.threadId = payload.thread_id;
                            next.status = payload.status ?? 'RUNNING';
                            next.loading = true;
                            break;

                        case 'draft_update':
                            next.currentDraft =
                                payload.data?.current_draft ??
                                payload.data?.currentDraft ??
                                prev.currentDraft;
                            next.status = 'RUNNING';
                            break;

                        case 'workflow_status':
                            next.status = payload.status;
                            break;

                        case 'critique_report':
                        case 'safety_report':
                            next.critique = payload.data;
                            break;

                        case 'final_result':
                            next.status = payload.data.status;
                            next.currentDraft =
                                payload.data.current_draft ??
                                payload.data.currentDraft ??
                                prev.currentDraft;
                            next.loading = false;
                            break;

                        case 'error':
                            next.error = payload.message;
                            next.status = 'FAILED';
                            next.loading = false;
                            break;

                        default:
                            break;
                    }

                    return next;
                });

            } catch (e) {
                console.error('Bad SSE JSON:', e);
            }
        });
    };

    /* ----------------------------------------------------
       START WORKFLOW (STREAM)
    -----------------------------------------------------*/
    const startWorkflow = useCallback(async (userIntent) => {
        setState({
            ...INITIAL_STATE,
            loading: true,
            status: 'RUNNING',
        });

        try {
            const response = await fetch(`${API_BASE_URL}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_intent: userIntent }),
            });

            if (!response.ok) throw new Error('Failed to start workflow');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                let idx;
                while ((idx = buffer.indexOf('\n\n')) !== -1) {
                    const chunk = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);
                    parseStreamData(chunk);
                }
            }

        } catch (err) {
            setState(s => ({
                ...s,
                error: err.message,
                status: 'FAILED',
                loading: false,
            }));
        }
    }, []);

    /* ----------------------------------------------------
       APPROVE
    -----------------------------------------------------*/
    const resumeWorkflow = useCallback(async (finalDraft) => {
        setState(s => ({ ...s, loading: true }));

        try {
            const res = await fetch(`${API_BASE_URL}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: threadId,
                    final_draft: finalDraft,
                }),
            });

            const data = await res.json();

            setState(s => ({
                ...s,
                status: data.status,
                currentDraft: data.current_draft ?? s.currentDraft,
                loading: false,
                humanDecision: '',
            }));

        } catch (err) {
            setState(s => ({
                ...s,
                error: err.message,
                loading: false,
            }));
        }
    }, [threadId]);

    /* ----------------------------------------------------
       REVISE
    -----------------------------------------------------*/
    const reviseWorkflow = useCallback(async (editedDraft) => {
        setState(s => ({ ...s, loading: true }));

        try {
            const res = await fetch(`${API_BASE_URL}/revise`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    thread_id: threadId,
                    edited_draft: editedDraft,
                }),
            });

            const data = await res.json();

            setState(s => ({
                ...s,
                status: data.status,
                currentDraft: data.current_draft ?? s.currentDraft,
                loading: false,
                humanDecision: '',
            }));

        } catch (err) {
            setState(s => ({
                ...s,
                error: err.message,
                loading: false,
            }));
        }
    }, [threadId]);

    /* ----------------------------------------------------
       RENDER
    -----------------------------------------------------*/
    return (
        <div className="min-h-screen bg-gray-100 p-3">
            <div className="max-w-[87rem] mx-auto space-y-7">

                <header>
                    <h1 className="text-4xl font-bold text-green-700 font-sans antialiased">
                        Cerina Protocol Foundry
                    </h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-1 font-sans antialiased">
                        Human-in-the-Loop Dashboard for Autonomous CBT Protocol Generation
                    </p>
                </header>

                <StatusIndicator
                    status={status}
                    loading={loading}
                    error={error}
                    threadId={threadId}
                />

                {!threadId && (
                    <div className="flex items-center justify-center min-h-[70vh]">
                    <StartForm onSubmit={startWorkflow} disabled={loading} />
                    </div>
                )}

                {threadId && (
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                         
                        <AgentStream streamEvents={state.streamEvents} />

                        <div className="lg:col-span-2 space-y-4">
                            <DraftViewer
                                draft={currentDraft}
                                isEditable={status === 'AWAITING_HUMAN_REVIEW'}
                                initialDecision={humanDecision}
                                workflowStatus={status}
                                onDraftChange={text =>
                                    setState(s => ({ ...s, humanDecision: text }))
                                }
                            />

                            {status === 'AWAITING_HUMAN_REVIEW' && (
                                <ReviewPanel
                                    critique={critique}
                                    loading={loading}
                                    onApprove={() =>
                                        resumeWorkflow(humanDecision || currentDraft)
                                    }
                                    onRevise={() =>
                                        reviseWorkflow(humanDecision || currentDraft)
                                    }
                                />
                            )}

                            {status === 'COMPLETED' && (
                                <div className="p-4 bg-green-100 text-green-700 font-semibold rounded">
                                    ✅ Protocol finalized successfully
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default ProtocolWorkbench;
