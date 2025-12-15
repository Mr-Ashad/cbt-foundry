// src/components/AgentStream.jsx
import React, { useEffect, useRef, useState } from 'react';

function StreamItem({ agent, text, accent = 'yellow', delay = 0 }) {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const t = setTimeout(() => setVisible(true), delay);
        return () => clearTimeout(t);
    }, [delay]);

    if (!visible) return null;

    return (
        <div
            className="border-l-2 border-yellow-600 pl-3 py-2 animate-fadeIn"
        >
            <p className={`text-xs font-mono text-${accent}-400 mb-1`}>
                [{agent}]
            </p>
            <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap font-sans">
                {text}
            </p>
        </div>
    );
}

function AgentStream({ streamEvents = [] }) {
    const scrollRef = useRef(null);

    // Smooth auto-scroll when new content appears
    useEffect(() => {
        if (!scrollRef.current) return;

        scrollRef.current.scrollTo({
            top: scrollRef.current.scrollHeight,
            behavior: 'smooth',
        });
    }, [streamEvents]);

    let renderIndex = 0;

    return (
        <div className="flex flex-col p-6 bg-gray-900 rounded-xl shadow-2xl min-h-[114.3vh] max-h-[114.3vh]">
            <h2 className="text-2xl font-mono text-green-400 mb-4">
                Agent Execution Log
            </h2>

            <div
                ref={scrollRef}
                className="flex-1 w-full h-100vh overflow-y-auto space-y-3 pr-2 scrollbar"
            >
                {streamEvents.length === 0 ? (
                    <p className="text-sm text-gray-500">
                        Agent thoughts will stream here when the workflow is running.
                    </p>
                ) : (
                    streamEvents.flatMap((event, index) => {
                        /* ---------- AGENT THOUGHT ---------- */
                        if (event.type === 'agent_thought') {
                            const { agent_name, thought } = event.data || {};
                            const delay = renderIndex++ * 220;

                            return (
                                <StreamItem
                                    key={`thought-${index}`}
                                    agent={agent_name || 'Agent'}
                                    text={thought}
                                    accent="green"
                                    delay={delay}
                                />
                            );
                        }

                        /* ---------- REPORTS ---------- */
                        if (
                            event.type === 'safety_report' ||
                            event.type === 'critique_report'
                        ) {
                            const agentName =
                                event.data?.agent_name ||
                                (event.type === 'safety_report'
                                    ? 'Safety Guardian'
                                    : 'Clinical Critic');

                            return event.data?.feedback?.map((item, idx) => {
                                const delay = renderIndex++ * 220;

                                return (
                                    <StreamItem
                                        key={`report-${index}-${idx}`}
                                        agent={agentName}
                                        text={item}
                                        accent="yellow"
                                        delay={delay}
                                    />
                                );
                            });
                        }

                        return [];
                    })
                )}
            </div>
        </div>
    );
}

export default AgentStream;
